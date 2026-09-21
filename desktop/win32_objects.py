"""Windows adlı çekirdek nesneleri — mutex ve olaylar tek yerde (tasarım §2.3, §4.2-1/5).

Program iki tür adlı nesne açar:

- **Mutex'ler** `KutuphaneDefteri` ve `Global\\KutuphaneDefteri` (`desktop/lock.py`):
  kurucu ve kaldırıcı programın kapanmasını bunlar kaybolana dek bekler.
- **Olaylar** `KutuphaneDefteri.Goster` ve `KutuphaneDefteri.Kapat`
  (`desktop/instance_channel.py`): ikinci açılış pencereyi öne getirir, kurucu
  programı düzenli kapatır.

**Güvenlik tanımlayıcısı neden açıkça verilir.** Varsayılan tanımlayıcı nesneye
yalnız onu açan hesabı ve SYSTEM'i yazar. Önerilen kurulum yolunda (tasarım §4.5)
kurucu kütüphane masası hesabında başlatılır ve UAC penceresine BTR'nin kimliği
girilir: yükseltilmiş kurucu BAŞKA BİR HESAPLA çalışır. Varsayılan tanımlayıcıyla
`OpenEventW` ve Inno'nun `CheckForMutexes`'i (`OpenMutex`) erişim reddi alır;
Inno bunu "mutex yok" diye okur ve program açıkken dosyaların üzerine yazmaya
kalkar. Bu yüzden nesneler yalnız gereken hakla şu dört alıcıya açılır:

    SY  SYSTEM                 BA  Yöneticiler (UAC'de yükseltilmiş kurucu)
    IU  etkileşimli oturumlar  OW  nesnenin sahibi (programı açan hesap)

Mutex'lere yalnız `SYNCHRONIZE` (varlık denetimi), olaylara ek olarak
`EVENT_MODIFY_STATE` (sinyal) verilir. Bu, başka bir etkileşimli kullanıcının
programın penceresini açtırabilmesi ya da onu kapattırabilmesi demektir; tek
etkisi kesintidir, veri yoluna açılmaz (Çık koruması zaten kaza önleyicidir,
§4.2-4). Tanımlayıcı kurulamazsa varsayılanla devam edilir ve günlüğe yazılır.

Windows dışında işlevler etkisizdir (`None`/`False` döner). Gerçek gövdeler
platform dalındadır: Docker'daki mypy onları görmez, `--platform win32` ile
ayrıca denetlenir.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Final

logger = logging.getLogger("kutuphane_defteri.win32")

SYNCHRONIZE: Final = 0x00100000
EVENT_MODIFY_STATE: Final = 0x0002
#: `WaitForMultipleObjects` sonuçları ve sonsuz bekleme.
WAIT_OBJECT_0: Final = 0x00000000
WAIT_FAILED: Final = 0xFFFFFFFF
INFINITE: Final = 0xFFFFFFFF
#: `CreateEventExW` bayrakları: 0 = otomatik sıfırlanan, başlangıçta işaretsiz.
_AUTO_RESET: Final = 0
_SDDL_REVISION_1: Final = 1

#: Erişim verilen alıcılar (modül belgesi).
TRUSTEES: Final = ("SY", "BA", "IU", "OW")


def sddl_for(access_mask: int) -> str:
    """Yalnız verilen hakla, `TRUSTEES`'e izin veren SDDL dizesi."""
    return "D:" + "".join(f"(A;;0x{access_mask:x};;;{trustee})" for trustee in TRUSTEES)


MUTEX_SDDL: Final = sddl_for(SYNCHRONIZE)
EVENT_SDDL: Final = sddl_for(SYNCHRONIZE | EVENT_MODIFY_STATE)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    from functools import cache

    class _SecurityAttributes(ctypes.Structure):
        _fields_ = (
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", wintypes.LPVOID),
            ("bInheritHandle", wintypes.BOOL),
        )

    _PSA = ctypes.POINTER(_SecurityAttributes)

    @cache
    def _libs() -> tuple[ctypes.WinDLL, ctypes.WinDLL]:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

        kernel32.CreateMutexExW.argtypes = (_PSA, wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD)
        kernel32.CreateMutexExW.restype = wintypes.HANDLE
        kernel32.CreateEventExW.argtypes = (_PSA, wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD)
        kernel32.CreateEventExW.restype = wintypes.HANDLE
        kernel32.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.OpenEventW.restype = wintypes.HANDLE
        kernel32.SetEvent.argtypes = (wintypes.HANDLE,)
        kernel32.SetEvent.restype = wintypes.BOOL
        kernel32.WaitForMultipleObjects.argtypes = (
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.BOOL,
            wintypes.DWORD,
        )
        kernel32.WaitForMultipleObjects.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
        kernel32.LocalFree.restype = wintypes.HLOCAL

        convert = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.ULONG),
        )
        convert.restype = wintypes.BOOL
        return kernel32, advapi32

    @contextmanager
    def _security_attributes(sddl: str) -> Iterator[Any]:
        """SDDL'den `SECURITY_ATTRIBUTES` işaretçisi; kurulamazsa `None` (varsayılan)."""
        kernel32, advapi32 = _libs()
        descriptor = wintypes.LPVOID()
        ok = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, _SDDL_REVISION_1, ctypes.byref(descriptor), None
        )
        if not ok:
            logger.warning(
                "Adlı nesne güvenlik tanımlayıcısı kurulamadı (hata %d); varsayılanla devam.",
                ctypes.get_last_error(),
            )
            yield None
            return
        attributes = _SecurityAttributes(
            ctypes.sizeof(_SecurityAttributes), descriptor.value, False
        )
        try:
            yield ctypes.byref(attributes)
        finally:
            kernel32.LocalFree(descriptor)

    def _as_handle(raw: int | None) -> int | None:
        return int(raw) if raw else None

    def create_mutex(name: str) -> int | None:
        """Adlı mutex'i açar ya da var olanı `SYNCHRONIZE` ile açar; olmazsa `None`.

        Mutex'in sahibi olunmaz (`dwFlags=0`): yalnız VARLIĞI sinyaldir.
        """
        kernel32, _ = _libs()
        with _security_attributes(MUTEX_SDDL) as attributes:
            handle = kernel32.CreateMutexExW(attributes, name, 0, SYNCHRONIZE)
        if not handle:
            logger.warning("'%s' mutex'i açılamadı (hata %d).", name, ctypes.get_last_error())
        return _as_handle(handle)

    def create_event(name: str | None) -> int | None:
        """Otomatik sıfırlanan olay; `name=None` adsız (süreç içi) olaydır."""
        kernel32, _ = _libs()
        access = SYNCHRONIZE | EVENT_MODIFY_STATE
        if name is None:
            handle = kernel32.CreateEventExW(None, None, _AUTO_RESET, access)
        else:
            with _security_attributes(EVENT_SDDL) as attributes:
                handle = kernel32.CreateEventExW(attributes, name, _AUTO_RESET, access)
        if not handle:
            logger.warning("'%s' olayı açılamadı (hata %d).", name, ctypes.get_last_error())
        return _as_handle(handle)

    def open_event(name: str) -> int | None:
        """Başka bir sürecin olayını yalnız sinyal hakkıyla açar; yoksa `None`."""
        kernel32, _ = _libs()
        return _as_handle(kernel32.OpenEventW(EVENT_MODIFY_STATE, False, name))

    def set_event(handle: int) -> bool:
        kernel32, _ = _libs()
        return bool(kernel32.SetEvent(handle))

    def wait_any(handles: Sequence[int]) -> int | None:
        """Tanıtıcılardan biri işaretlenene dek bekler; dizinini döndürür, hatada `None`.

        Birden çoğu işaretliyse en küçük dizin döner (Windows sözleşmesi): çağıran
        öncelikli olanı öne koyar.
        """
        kernel32, _ = _libs()
        array = (wintypes.HANDLE * len(handles))(*handles)
        result = int(kernel32.WaitForMultipleObjects(len(handles), array, False, INFINITE))
        if WAIT_OBJECT_0 <= result < WAIT_OBJECT_0 + len(handles):
            return result - WAIT_OBJECT_0
        logger.warning("Adlı olay beklemesi başarısız (sonuç %#x).", result)
        return None

    def close_handle(handle: int) -> None:
        kernel32, _ = _libs()
        kernel32.CloseHandle(handle)

else:
    # Windows dışında adlı nesne yoktur: işlevler etkisizdir.

    def create_mutex(name: str) -> int | None:
        return None

    def create_event(name: str | None) -> int | None:
        return None

    def open_event(name: str) -> int | None:
        return None

    def set_event(handle: int) -> bool:
        return False

    def wait_any(handles: Sequence[int]) -> int | None:
        return None

    def close_handle(handle: int) -> None:
        return None
