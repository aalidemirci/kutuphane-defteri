"""Tek-instance kilidi + kurucuya görünen mutex'ler + ikinci açılış sinyali (tasarım §4.2).

İki kopya aynı SQLite dosyasına yazarsa WAL kilitleri yüzünden kullanıcı
"veritabanı kilitli" hatalarıyla karşılaşır; daha kötüsü iki pencere aynı dosya
üzerinde farklı işlem yapar. Bu yüzden ikinci kopya **pencere açmaz**.

Yöntem işletim sistemine göre değişir ama sözleşme aynıdır: bir dosya açılır ve
üzerine paylaşımsız kilit konur. Kilit süreç ölünce (çökme dahil) işletim sistemi
tarafından bırakılır — bayat PID dosyası sorunu yaşanmaz.

**`acquire()` hata fırlatmaya devam eder** (§4.2-1, denetim GA-11). İkinci
açılışta pencereyi öne getirme ayrı yardımcıdadır (`signal_running_instance`) ve
yalnız bayraksız normal açılışta çağrılır (`desktop/main.py`). Sinyal kilide
gömülseydi `--geri-yukle` kısayolu hiçbir şey yapmadan 0 koduyla çıkar,
kullanıcı geri yüklemenin yapıldığını sanardı.

**Mutex'ler (yalnız Windows).** Kilide EK olarak `KutuphaneDefteri` ve
`Global\\KutuphaneDefteri` açılır (§2.3). Tek-instance güvencesi onlardan GELMEZ;
kurucu ve kaldırıcı programı `KutuphaneDefteri.Kapat` olayıyla kapattıktan sonra
ikisinin de kaybolmasını bekler (§4.2-5; Inno `AppMutex` kullanılmaz). `Global\\`
biçimi başka bir Windows oturumunda (hızlı kullanıcı değiştirme) çalışan kopyayı
da görünür kılar. Güvenlik tanımlayıcısının gerekçesi `desktop/win32_objects.py`.

Mutex tanıtıcıları `release()`'te KAPATILMAZ: süreç tamamen bitene dek yaşarlar
(Inno belgesinin önerisi). Erken kapatılsalardı kurucu, çıkmakta olan sürecin
exe'sinin ve `_internal/` dosyalarının üzerine yazmaya kalkardı.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Final

from desktop import instance_channel, win32_objects
from desktop.errors import AlreadyRunningError

#: Kurucudaki `[Code]` beklemesiyle birebir aynı olmak ZORUNDA
#: (packaging/windows/kutuphane-defteri.iss → `ProgramMutexleri`).
APP_MUTEX_NAME: Final = "KutuphaneDefteri"
GLOBAL_APP_MUTEX_NAME: Final = "Global\\KutuphaneDefteri"
APP_MUTEX_NAMES: Final = (APP_MUTEX_NAME, GLOBAL_APP_MUTEX_NAME)

_MESSAGE = "Kütüphane Defteri zaten çalışıyor. Aynı anda yalnızca bir kopya açılabilir."
_HINT = (
    "Program tepside çalışıyor olabilir: saatin yanındaki simgeden 'Pencereyi aç'ı "
    "seçin. Simge görünmüyorsa oturumu kapatıp açın."
)

MutexCreator = Callable[[str], int | None]


def _apply_exclusive_lock(handle: BinaryIO) -> None:
    """Dosyaya bloklamayan paylaşımsız kilit koyar; alınamazsa OSError yükseltir."""
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_lock(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class SingleInstanceLock:
    """Kilit dosyası üzerinden tek-instance güvencesi (context manager).

    `platform` ve `mutex_creator` yalnız testler içindir: Windows mutex yolu
    Linux'ta sahte yaratıcıyla sınanır.
    """

    def __init__(
        self,
        path: Path,
        *,
        platform: str = sys.platform,
        mutex_creator: MutexCreator | None = None,
    ) -> None:
        self._path = path
        self._handle: BinaryIO | None = None
        self._platform = platform
        self._mutex_creator: MutexCreator = mutex_creator or win32_objects.create_mutex
        self._mutex_handles: list[int] = []

    @property
    def path(self) -> Path:
        return self._path

    @property
    def handle(self) -> BinaryIO | None:
        """Kilit alınmışsa açık dosya tanıtıcısı, aksi halde None (test/teşhis)."""
        return self._handle

    @property
    def mutex_handles(self) -> tuple[int, ...]:
        """Açılmış mutex tanıtıcıları (Windows; süreç ömrünce kalır)."""
        return tuple(self._mutex_handles)

    def acquire(self) -> None:
        """Kilidi alır; başka bir kopya çalışıyorsa `AlreadyRunningError` yükseltir."""
        if self._handle is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # "a+b": yoksa oluşturur, varsa içeriğini korur (dosyaya bir şey yazmıyoruz —
        # kilit dosyanın kendisinde, içeriğinde değil; PID dosyası bayatlayabilirdi).
        handle: BinaryIO = self._path.open("a+b")
        try:
            _apply_exclusive_lock(handle)
        except OSError as exc:
            handle.close()
            raise AlreadyRunningError(_MESSAGE, hint=_HINT) from exc
        self._handle = handle
        self._open_app_mutexes()

    def _open_app_mutexes(self) -> None:
        """Windows'ta iki mutex'i açar. Başarısızlık açılışı DURDURMAZ.

        Tek-instance güvencesi dosya kilidindedir; mutex'ler yalnız kurucunun
        "program kapandı mı" beklemesi içindir. Aynı süreçte ikinci `acquire`
        (testler, geri yükleme) var olan tanıtıcıları korur.
        """
        if self._platform != "win32" or self._mutex_handles:
            return
        for name in APP_MUTEX_NAMES:
            try:
                mutex = self._mutex_creator(name)
            except OSError:
                mutex = None
            if mutex is not None:
                self._mutex_handles.append(mutex)

    def release(self) -> None:
        """Dosya kilidini bırakır. Kilit alınmamışsa sessizce döner.

        Mutex'ler bilerek açık kalır (modül belgesi): süreç bitince işletim
        sistemi kapatır.
        """
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            _release_lock(handle)
        except OSError:
            # Kilit zaten düşmüşse (dosya silinmiş vb.) kapatmak yeterli.
            pass
        finally:
            handle.close()

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


def is_instance_running(lock_path: Path) -> bool:
    """Bu veri dizinini kullanan bir kopya çalışıyor mu? (kilidi alıp hemen bırakır)

    Kilidi kendisi tutmayan teşhis kipleri içindir (`--pdf-duman`): çalışan kopya
    varsa 2 koduyla çıkarlar (§4.2-1). Mutex açmaz.
    """
    probe = SingleInstanceLock(lock_path, platform="")
    try:
        probe.acquire()
    except AlreadyRunningError:
        return True
    probe.release()
    return False


def signal_running_instance(
    root: Path,
    *,
    sender: Callable[[Path, str], bool] | None = None,
) -> bool:
    """Çalışan kopyadan penceresini göstermesini ister; ulaştıysa `True` (§4.2-1).

    YALNIZ bayraksız normal açılışta çağrılır. `False` dönerse (çalışan kopya
    kanal kurmamış, ör. `--autotest`) çağıran "zaten çalışıyor" iletisine düşer.
    """
    send = sender or instance_channel.send_command
    try:
        return send(root, instance_channel.COMMAND_SHOW)
    except OSError:
        return False
