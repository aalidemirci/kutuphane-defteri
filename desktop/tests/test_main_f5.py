"""Açılış/kapanış akışının F5 bağlantıları (tasarım §4.2, §4.5, T9, T16, TB13, TB14).

* Çık (§4.2-4, §5.10-18): arayüzdeki Çık (`POST app/quit/`) masaüstü kancasıyla
  pencere denetçisine bağlanır ve kapanış yanıt gönderildikten SONRA, ayrı iş
  parçacığında başlar; tepsideki Çık görevli kipinde parolayı SPA'da ister.
* Düzenli kapanışta WAL checkpoint (TB14).
* `--tepside`: pencere yalnız tepsi kurulduysa gizli açılır.
* Yükseltilmiş yardımcı kip veri dizini, günlük ve kilit AÇMAZ.
* Gün değişimi kapısının yerleşik işleri (günlük yedek + rotasyon, IP denetimi).

Backend kancası (`apps.okul.masaustu_kanca`) ve `app/quit/` görünümü backend
testlerindedir (`backend/apps/okul/tests/test_cikis_ucu.py`).
"""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from desktop import guvenlik_duvari
from desktop import main as main_mod
from desktop.django_bootstrap import is_parcacigi_baglantisiyla, wal_checkpoint
from desktop.paths import ENV_APP_HOME, resolve_app_paths
from desktop.tray import TrayActions
from desktop.window import WindowController

# ------------------------------------------------------------ Çık kancası


def test_arayuzden_cik_yanittan_sonra_ayri_is_parcaciginda_kapanisi_baslatir() -> None:
    goruldu: list[str] = []
    olay = threading.Event()

    class _Denetci:
        def request_quit(self) -> None:
            goruldu.append(threading.current_thread().name)
            olay.set()

    kanca = main_mod.cikis_kancasi(_Denetci())  # type: ignore[arg-type]
    baslangic = time.monotonic()
    kanca()  # HTTP isteği iş parçacığı: hemen döner
    assert time.monotonic() - baslangic < 0.1
    assert goruldu == []

    assert olay.wait(5)
    assert goruldu == ["kd-cikis"]


def test_tepsi_eylemleri_kip_matrisi_hedeflerine_baglanir() -> None:
    denetci = WindowController(platform="linux")
    kontrol = SimpleNamespace(
        tepsi_satiri=lambda: "Ağ Kataloğu: kapalı",
        acik_mi=lambda: False,
        kapatilabilir_mi=lambda: False,
        ac=lambda: {},
        kapat=lambda: {},
        adres=lambda: None,
    )

    eylemler = main_mod.tepsi_eylemleri(denetci, kontrol)  # type: ignore[arg-type]

    assert eylemler.show == denetci.show
    assert eylemler.quit == denetci.request_quit
    assert eylemler.quit_gorevli == denetci.ask_quit_in_spa  # parola SPA'da (§4.2-4)
    assert eylemler.kip is main_mod.kip_durumu  # tek durum kaynağı KipDurumu (T16)
    assert eylemler.katalog_satiri is kontrol.tepsi_satiri
    # Aç/kapa "kapat"ı ayar açık ama katalog açılamamışken de sunar (F5 düzeltmesi).
    assert eylemler.katalog_kapatilabilir is kontrol.kapatilabilir_mi
    assert eylemler.gorevli_kipine_gec is not None and eylemler.kilitle is not None


def test_katalog_denetcisi_yoksa_tepsi_yalniz_ac_ve_cik() -> None:
    denetci = WindowController(platform="linux")

    eylemler = main_mod.tepsi_eylemleri(denetci, None)

    assert eylemler == TrayActions(show=denetci.show, quit=denetci.request_quit)


def test_katalog_ac_kapa_tepsi_dongusunu_bekletmez() -> None:
    """Güvenlik duvarı denetimi saniyeler sürer: tepsi komutu ayrı iş parçacığında koşar."""
    olay = threading.Event()
    adlar: list[str] = []

    def yavas() -> None:
        adlar.append(threading.current_thread().name)
        olay.set()

    main_mod._arka_planda("kd-katalog-ac", yavas)()

    assert olay.wait(5)
    assert adlar == ["kd-katalog-ac"]


# ----------------------------------------------------------- tepside açılış


class _Tepsi:
    def __init__(self, var: bool) -> None:
        self.available = var

    def stop(self) -> None:
        pass


@pytest.mark.parametrize(("tepsi_var", "gizli"), [(True, True), (False, False)])
def test_tepside_acilis_yalniz_tepsi_varsa_gizli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tepsi_var: bool, gizli: bool
) -> None:
    kayit: dict[str, Any] = {}
    monkeypatch.setattr(main_mod, "start_tray", lambda eylemler, **_: _Tepsi(tepsi_var))

    def pencere(url: str, **kw: Any) -> None:
        kayit.update(kw)

    monkeypatch.setattr(main_mod, "open_window", pencere)

    main_mod.run_window_session(
        "http://127.0.0.1:1/", tmp_path, None, platform="linux", tepside=True
    )

    assert kayit["hidden"] is gizli


def test_tepside_bayragi() -> None:
    assert main_mod.build_parser().parse_args([]).tepside is False
    assert main_mod.build_parser().parse_args(["--tepside"]).tepside is True


# ------------------------------------------------------ yükseltilmiş kip


def test_yukseltilmis_yardimci_kip_veri_dizini_gunluk_ve_kilit_acmaz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alinan: list[list[str]] = []

    def acilmamali(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("yükseltilmiş kip olağan açılışa girdi")

    monkeypatch.setattr(main_mod, "resolve_paths", acilmamali)
    monkeypatch.setattr(main_mod, "configure_logging", acilmamali)
    monkeypatch.setattr(main_mod, "SingleInstanceLock", acilmamali)

    def yukseltilmis(argv: list[str]) -> int:
        alinan.append(list(argv))
        return 0

    monkeypatch.setattr(guvenlik_duvari, "yukseltilmis_kip", yukseltilmis)

    kod = main_mod.run(["--guvenlik-duvari-kurali", "--port", "9100"])

    assert kod == 0
    assert alinan == [["--guvenlik-duvari-kurali", "--port", "9100"]]


# ------------------------------------------------------------ WAL (TB14)


def test_kapanista_wal_checkpoint_wal_dosyasini_bosaltir(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    with closing(sqlite3.connect(db)) as yazar:
        yazar.execute("PRAGMA journal_mode=WAL")
        yazar.execute("PRAGMA wal_autocheckpoint=0")
        yazar.execute("CREATE TABLE odunc (id INTEGER PRIMARY KEY, barkod TEXT)")
        yazar.executemany("INSERT INTO odunc (barkod) VALUES (?)", [(str(i),) for i in range(200)])
        yazar.commit()
        wal = db.with_name("db.sqlite3-wal")
        assert wal.stat().st_size > 0  # işlenmiş sayfalar hâlâ WAL'de

        assert wal_checkpoint(db) is True

        assert wal.stat().st_size == 0  # TRUNCATE: WAL ana dosyaya aktarıldı ve kırpıldı
    with closing(sqlite3.connect(db)) as okur:
        assert okur.execute("SELECT COUNT(*) FROM odunc").fetchone()[0] == 200


def test_wal_checkpoint_veritabani_yoksa_sessiz(tmp_path: Path) -> None:
    assert wal_checkpoint(tmp_path / "yok.sqlite3") is False


def test_wal_checkpoint_okuyucu_varken_kismi_kalir_ve_cikisi_durdurmaz(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    with closing(sqlite3.connect(db)) as yazar, closing(sqlite3.connect(db)) as okur:
        yazar.execute("PRAGMA journal_mode=WAL")
        yazar.execute("PRAGMA wal_autocheckpoint=0")
        yazar.execute("CREATE TABLE t (x)")
        yazar.commit()
        okur.execute("BEGIN")
        okur.execute("SELECT * FROM t").fetchall()  # okuma işlemi açık: anlık görüntü tutuluyor
        yazar.execute("INSERT INTO t VALUES (1)")
        yazar.commit()

        assert wal_checkpoint(db) is False
        okur.execute("COMMIT")


# ----------------------------------------------------- iş parçacığı bağlantısı


class _Baglanti:
    def __init__(self) -> None:
        self.connection: object | None = None
        self.in_atomic_block = False
        self.kapatildi = 0

    def close(self) -> None:
        self.kapatildi += 1


def test_is_parcacigi_baglantisi_yalniz_kendi_actigini_kapatir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tepsi ve `kd-gunluk` bağlantı bırakırsa Windows'ta geri yükleme takası düşer."""
    sahte = _Baglanti()
    monkeypatch.setattr("django.db.connections", {"default": sahte})

    assert is_parcacigi_baglantisiyla(lambda: 42) == 42
    assert sahte.kapatildi == 1  # çağrının açtığı (önceden yoktu) kapatıldı

    sahte.connection = object()  # HTTP isteği iş parçacığı: bağlantı önceden açık
    is_parcacigi_baglantisiyla(lambda: None)
    assert sahte.kapatildi == 1  # isteğin bağlantısına dokunulmadı


# ------------------------------------------------------ gün değişimi işleri


def test_gunluk_yedek_isi_yedek_alinmazsa_rotasyon_kosmaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)})
    olaylar: list[str] = []
    monkeypatch.setattr(main_mod, "daily_backup", lambda *a, **k: None)
    monkeypatch.setattr(main_mod, "rotate_backups", lambda *a, **k: olaylar.append("rotasyon"))

    assert main_mod.gunluk_yedek_isi(paths, bugun=lambda: date(2026, 9, 24))() is False
    assert olaylar == []

    monkeypatch.setattr(main_mod, "daily_backup", lambda *a, **k: tmp_path / "gunluk.kdbak")
    assert main_mod.gunluk_yedek_isi(paths, bugun=lambda: date(2026, 9, 24))() is True
    assert olaylar == ["rotasyon"]


def _sahte_gunluk_yedek(monkeypatch: pytest.MonkeyPatch) -> None:
    """Günlük yedeği yalnız dosya adıyla taklit eder (şifreleme `test_backup.py`'dedir)."""
    from desktop.backup import DAILY_PREFIX
    from desktop.backup_crypto import BACKUP_SUFFIX

    def yedek(db: Path, klasor: Path, *, today: date) -> Path:
        klasor.mkdir(parents=True, exist_ok=True)
        hedef = klasor / f"{DAILY_PREFIX}-{today.isoformat()}{BACKUP_SUFFIX}"
        hedef.write_bytes(b"x")
        return hedef

    monkeypatch.setattr(main_mod, "daily_backup", yedek)


def test_saat_ileri_sicrarsa_oturum_ici_rotasyon_gecmis_yedekleri_silmez(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bulgu: tepside açık programda saat 14 günden fazla ileri sıçrarsa bütün günlük
    yedekler silinirdi. Rotasyon gerçek geçen süreye (uyku dahil açık kalma saati) göre
    kesilir; "en çok 14 gün" saklama sözü (TB8) bozulmaz."""
    from desktop.backup import DAILY_PREFIX
    from desktop.backup_crypto import BACKUP_SUFFIX

    paths = resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)})
    paths.ensure()
    _sahte_gunluk_yedek(monkeypatch)
    gun = [date(2026, 9, 24)]
    saat = [1_000.0]
    is_ = main_mod.gunluk_yedek_isi(paths, bugun=lambda: gun[0], saat=lambda: saat[0])
    for i in range(1, 10):  # geçmiş dokuz günün yedekleri
        onceki = date(2026, 9, 24) - timedelta(days=i)
        (paths.backups / f"{DAILY_PREFIX}-{onceki.isoformat()}{BACKUP_SUFFIX}").write_bytes(b"x")

    assert is_() is True  # çapa: 24.09, saat 1000
    gun[0] = date(2026, 10, 30)  # saat bir saat içinde 36 gün ileri sıçradı
    saat[0] += 3_600
    assert is_() is True

    kalan = sorted(p.name for p in paths.backups.glob(f"{DAILY_PREFIX}-*{BACKUP_SUFFIX}"))
    assert f"{DAILY_PREFIX}-2026-09-15{BACKUP_SUFFIX}" in kalan  # geçmiş yedekler duruyor
    assert f"{DAILY_PREFIX}-2026-10-30{BACKUP_SUFFIX}" in kalan
    assert len(kalan) == 11


def test_gercekten_gecen_gunlerde_rotasyon_olagan_calisir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uyku dahil saat de ilerlediyse (tatilde uykuda kalan bilgisayar) kesim olağandır."""
    from desktop.backup import DAILY_PREFIX
    from desktop.backup_crypto import BACKUP_SUFFIX

    paths = resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)})
    paths.ensure()
    _sahte_gunluk_yedek(monkeypatch)
    gun = [date(2026, 9, 24)]
    saat = [1_000.0]
    is_ = main_mod.gunluk_yedek_isi(paths, bugun=lambda: gun[0], saat=lambda: saat[0])
    assert is_() is True

    gun[0] = date(2026, 10, 30)
    saat[0] += 36 * 86_400
    assert is_() is True

    kalan = sorted(p.name for p in paths.backups.glob(f"{DAILY_PREFIX}-*{BACKUP_SUFFIX}"))
    assert kalan == [f"{DAILY_PREFIX}-2026-10-30{BACKUP_SUFFIX}"]  # 24.09 kesimden eski


def test_gun_kapisi_yerlesik_isleri_kaydeder_ve_uyku_dinleyicisini_baglar(tmp_path: Path) -> None:
    paths = resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)})
    dinleyiciler: list[Any] = []
    kontrol = SimpleNamespace(
        uyku_gerekli=lambda: False,
        ip_denetle=lambda: True,
        saatlik_denetle=lambda: True,
        uyku_dinleyicisi_ekle=dinleyiciler.append,
    )

    kapi = main_mod.gun_kapisi_kur(paths, kontrol)  # type: ignore[arg-type]

    assert kapi.is_adlari[:2] == ("gunluk-yedek", "ip-denetimi")
    assert dinleyiciler == [kapi.uyandir]
