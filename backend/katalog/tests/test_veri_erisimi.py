"""Ağ Kataloğunun veri erişimi — authorizer, görünümler, parite (tasarım §5.3, §5.10-4/5/11).

§5.10-4 **F6 ve F7'de yeniden koşar**: `Loan` ve `Membership` o fazlarda gelir.
Bugün bu tablolar olmadığı için "doğrudan okunamaz" iki yoldan sınanır:
(1) authorizer işlevine bu tabloların adıyla doğrudan sorulur; (2) aynı adlı
tablolar ve onlara uzanan kötü bir görünüm taşıyan ayrı bir SQLite dosyası
katalog bağlantısıyla açılır. F6'da gerçek tablolar gelince (2)'deki kurgu
test veritabanının kendisiyle de koşar ve kaydedici authorizer anlık görüntüsü
(aşağıda) hiç değişmemelidir.
"""

from __future__ import annotations

import itertools
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.models.signals import post_migrate, pre_migrate

from apps.kutuphane import katalog_gorunumleri, selectors
from apps.kutuphane.apps import KutuphaneConfig
from apps.kutuphane.models import (
    Copy,
    CopyStatus,
    KatalogPopuler,
    PopulerPencereTuru,
    ResourceType,
    Work,
)
from apps.kutuphane.tests.ortak import bolum, edinim, eser, nusha
from katalog import veri
from katalog.tests.conftest import KatalogIstemcisi

pytestmark = pytest.mark.django_db(transaction=True)

OKUMA = sqlite3.SQLITE_READ
SECIM = sqlite3.SQLITE_SELECT
FONKSIYON = sqlite3.SQLITE_FUNCTION
DENY = sqlite3.SQLITE_DENY
OK = sqlite3.SQLITE_OK


def _db_yolu() -> Path:
    return Path(str(connection.settings_dict["NAME"]))


# ====================================================== §5.3 authorizer tablosu (birim)


@pytest.mark.parametrize(
    ("eylem", "a1", "a2", "ic", "karar"),
    [
        # SQLITE_SELECT → izin
        (SECIM, None, None, None, OK),
        # SQLITE_FUNCTION → izin listesi
        *[(FONKSIYON, None, ad, None, OK) for ad in sorted(veri.IZINLI_FONKSIYONLAR)],
        (FONKSIYON, None, "LIKE", "kd_katalog_eser", OK),
        *[
            (FONKSIYON, None, ad, None, DENY)
            for ad in ("upper", "max", "sum", "load_extension", "sqlite_version", "randomblob")
        ],
        # SQLITE_READ, görünüm içinden, izin listesindeki (tablo, sütun) → izin
        (OKUMA, "kutuphane_work", "title", "kd_katalog_eser", OK),
        (OKUMA, "kutuphane_copy", "status", "kd_katalog_nusha", OK),
        # ... listede olmayan sütun ya da tablo → RED (görünüm içinden bile)
        (OKUMA, "kutuphane_copy", "barcode", "kd_katalog_nusha", DENY),
        (OKUMA, "kutuphane_copy", "acquisition_id", "kd_katalog_nusha", DENY),
        (OKUMA, "okul_schoolconfig", "principal_name", "kd_katalog_okul", DENY),
        (OKUMA, "okul_schoolconfig", "app_password_hash", "kd_katalog_okul", DENY),
        (OKUMA, "kutuphane_loan", "membership_id", "kd_katalog_eser", DENY),
        (OKUMA, "kutuphane_membership", "card_no", "kd_katalog_eser", DENY),
        (OKUMA, "okul_student", "first_name", "kd_katalog_eser", DENY),
        (OKUMA, "kutuphane_acquisition", "source_note", "kd_katalog_nusha", DENY),
        # ... önekli olmayan bir görünümden → RED
        (OKUMA, "kutuphane_work", "title", "baska_gorunum", DENY),
        # ... önekli ama görünüm KÜMESİNDE olmayan ad (ör. `WITH kd_katalog_x AS …` CTE'si,
        # ileride eklenecek bir görünüm) → RED: karar önekle değil tam kümeyle verilir
        (OKUMA, "kutuphane_work", "title", "kd_katalog_x", DENY),
        (OKUMA, "kutuphane_work", "deleted_at", "kd_katalog_populer", DENY),
        # SQLITE_READ, 5. argüman boş: yalnız kd_katalog_* (görünüm sütunu, count(*) boş sütun)
        (OKUMA, "kd_katalog_eser", "baslik", None, OK),
        (OKUMA, "kd_katalog_eser", "", None, OK),
        (OKUMA, "kd_katalog_populer", "eser_id", None, OK),
        # ... önekli ama kümede olmayan tablo (ör. F10'da eklenecek ham sayı tablosu) → RED
        (OKUMA, "kd_katalog_ham_sayilar", "sayi", None, DENY),
        (OKUMA, "kd_katalog_x", "title", None, DENY),
        (OKUMA, "kutuphane_work", "title", None, DENY),
        (OKUMA, "kutuphane_loan", "id", None, DENY),
        (OKUMA, "kutuphane_membership", "id", None, DENY),
        (OKUMA, "sqlite_master", "sql", None, DENY),
        # Geri kalan her şey → RED
        (sqlite3.SQLITE_PRAGMA, "query_only", "OFF", None, DENY),
        (sqlite3.SQLITE_INSERT, "kutuphane_work", None, None, DENY),
        (sqlite3.SQLITE_UPDATE, "kutuphane_work", "title", None, DENY),
        (sqlite3.SQLITE_DELETE, "kutuphane_work", None, None, DENY),
        (sqlite3.SQLITE_ATTACH, "x.db", None, None, DENY),
        (sqlite3.SQLITE_TRANSACTION, "BEGIN", None, None, DENY),
        (sqlite3.SQLITE_RECURSIVE, None, None, None, DENY),
        (sqlite3.SQLITE_CREATE_TEMP_TABLE, "t", None, None, DENY),
    ],
)
def test_authorizer_tasarim_tablosunu_birebir_uygular(
    eylem: int, a1: str | None, a2: str | None, ic: str | None, karar: int
) -> None:
    assert veri.yetkilendir(eylem, a1, a2, "main", ic) == karar


def test_izinli_fonksiyonlar_tasarimdaki_listedir() -> None:
    assert veri.IZINLI_FONKSIYONLAR == {"like", "lower", "count", "coalesce", "substr", "length"}


def test_gorunum_kumesi_gorunum_tanimlariyla_ayni() -> None:
    """Authorizer'ın tam ad kümesi görünüm tanımlarıyla aynı (F5 düzeltmesi: önek yok)."""
    assert veri.GORUNUMLER == set(katalog_gorunumleri.gorunum_tanimlari())
    assert veri.UST_DUZEY_OKUNABILIR == veri.GORUNUMLER | {"kd_katalog_populer"}


# ============================================== §5.10-4 gerçek bağlantıda authorizer


def test_gorunum_uzerinden_like_ve_count_gecer() -> None:
    nusha(eser(title="Kürk Mantolu Madonna"))

    with veri.baglan(_db_yolu()) as conn:
        sayi = conn.execute("SELECT count(*) FROM kd_katalog_eser").fetchone()[0]
        bulunan = conn.execute(
            "SELECT baslik FROM kd_katalog_eser WHERE arama LIKE ? ESCAPE '\\'", ("%MADONNA%",)
        ).fetchall()

    assert sayi == 1
    assert [r["baslik"] for r in bulunan] == ["Kürk Mantolu Madonna"]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT title FROM kutuphane_work",
        "SELECT count(*) FROM kutuphane_copy",
        "SELECT barcode FROM kutuphane_copy",
        "SELECT source_note FROM kutuphane_acquisition",
        "SELECT first_name FROM okul_student",
        "SELECT principal_name FROM okul_schoolconfig",
        "SELECT sql FROM sqlite_master",
        "SELECT upper(baslik) FROM kd_katalog_eser",
        "PRAGMA query_only=OFF",
        "PRAGMA table_info(kd_katalog_eser)",
        "ATTACH DATABASE ':memory:' AS baska",
        "INSERT INTO kd_katalog_populer (eser_id) VALUES (1)",
        "DELETE FROM kd_katalog_populer",
        "CREATE TEMP TABLE t (x)",
        "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r) SELECT n FROM r",
    ],
)
def test_katalog_baglantisi_tablolari_dogrudan_okuyamaz_pragma_ve_yazma_reddedilir(
    sql: str,
) -> None:
    with pytest.raises(veri.VeriHatasi), veri.baglan(_db_yolu()) as conn:
        conn.execute(sql).fetchall()


@pytest.mark.parametrize(
    "sql",
    [
        # Önekli ama görünüm kümesinde olmayan adlı CTE: eskiden önek kuralından geçip
        # yumuşak silinmiş eserin adını görünüm süzgeçleri olmadan okuyordu.
        "WITH kd_katalog_x AS (SELECT title, deleted_at FROM kutuphane_work) "
        "SELECT * FROM kd_katalog_x",
        "WITH kd_katalog_populer AS (SELECT title FROM kutuphane_work) "
        "SELECT * FROM kd_katalog_populer",
        "WITH kd_katalog_eser AS (SELECT barcode FROM kutuphane_copy) SELECT * FROM kd_katalog_eser",
        "SELECT * FROM (SELECT title FROM kutuphane_work) AS kd_katalog_x",
    ],
)
def test_onekli_cte_ve_alt_sorgu_temel_tabloyu_okuyamaz(sql: str) -> None:
    """F5 düzeltmesi (authorizer ad kümesi).

    BİLİNEN SINIR: görünümle AYNI adı taşıyan bir CTE (`WITH kd_katalog_eser AS
    (SELECT title AS baslik FROM kutuphane_work) …`) izin listesindeki çiftleri
    görünüm süzgeçleri olmadan okuyabilir; SQLite 5. argümanda görünümü CTE'den
    ayırmaz. Bu yol katalogda keyfi SQL çalışabilseydi açılırdı; katalogdaki
    bütün SQL sabittir ve kaynakta `WITH` yoktur (aşağıdaki kaynak taraması).
    """
    eser(title="Silinecek Eser").delete()

    with pytest.raises(veri.VeriHatasi), veri.baglan(_db_yolu()) as conn:
        conn.execute(sql).fetchall()


def _katalog_sql_dizeleri() -> list[tuple[str, int, str]]:
    """Katalog paketindeki (testler hariç) SQL taşıyan dize sabitleri: (dosya, satır, dize)."""
    import ast

    kok = Path(veri.__file__).resolve().parent
    bulunan: list[tuple[str, int, str]] = []
    for dosya in sorted(kok.glob("*.py")):
        agac = ast.parse(dosya.read_text(encoding="utf-8"))
        belgeler = {
            id(dugum.body[0].value)
            for dugum in ast.walk(agac)
            if isinstance(dugum, ast.Module | ast.ClassDef | ast.FunctionDef)
            and dugum.body
            and isinstance(dugum.body[0], ast.Expr)
            and isinstance(dugum.body[0].value, ast.Constant)
        }
        for dugum in ast.walk(agac):
            if id(dugum) in belgeler:
                continue  # belge metni SQL değildir
            if isinstance(dugum, ast.Constant) and isinstance(dugum.value, str):
                if "SELECT" in dugum.value or "FROM " in dugum.value:
                    bulunan.append((dosya.name, dugum.lineno, dugum.value))
    return bulunan


def test_katalog_kaynaginda_cte_ve_dinamik_tablo_adi_yok() -> None:
    """Authorizer görünümü CTE'den ayıramaz; güvence katalog SQL'inin SABİT olmasıdır.

    Katalog paketindeki hiçbir SQL dizesi `WITH` (CTE) içermez ve okunan adlar
    yalnız `UST_DUZEY_OKUNABILIR` kümesindendir.
    """
    import re

    dizeler = _katalog_sql_dizeleri()
    assert dizeler, "katalog SQL'i bulunamadı (tarama bozuk)"
    for dosya, satir, dize in dizeler:
        if "SELECT" not in dize:
            continue
        assert not re.search(r"\bWITH\b", dize, flags=re.IGNORECASE), f"{dosya}:{satir}"
        for ad in re.findall(r"\bFROM\s+([a-z_]+)", dize):
            assert ad in veri.UST_DUZEY_OKUNABILIR, f"{dosya}:{satir}: {ad}"


def test_baglanti_dosya_duzeyinde_salt_okurdur() -> None:
    assert veri.baglanti_adresi(_db_yolu()).startswith("file:")
    assert veri.baglanti_adresi(_db_yolu()).endswith("?mode=ro")
    # authorizer olmadan bile (yalnız mode=ro + query_only) yazma olmaz:
    with (
        pytest.raises(veri.VeriHatasi),
        veri.baglan(_db_yolu(), yetkilendirici=lambda *a: OK) as conn,
    ):
        conn.execute("DELETE FROM kd_katalog_populer")


def test_uzun_sorgu_ilerleme_isleyicisiyle_kesilir() -> None:
    work = eser(title="Uzun Sorgu")
    for _ in range(12):
        nusha(work)
    zaman = iter([0.0, *[100.0] * 10_000])  # ilk okuma son anı kurar, sonrası geçmiş

    with pytest.raises(veri.VeriHatasi), veri.baglan(_db_yolu(), saat=lambda: next(zaman)) as conn:
        conn.execute(
            "SELECT count(*) FROM kd_katalog_nusha AS a, kd_katalog_nusha AS b, "
            "kd_katalog_nusha AS c"
        ).fetchall()


def test_veritabani_dosyasi_yoksa_veri_hatasi(tmp_path: Path) -> None:
    with pytest.raises(veri.VeriHatasi), veri.baglan(tmp_path / "yok.sqlite3"):
        pass


# ------------------------------------------------ Loan / Membership (F6 öncesi kurgu)


def _loan_kurgusu(yol: Path) -> None:
    """Yarının şemasını taklit eden ayrı bir dosya: ödünç ve üyelik tabloları +
    bu tablolara uzanan (yanlışlıkla yazılmış) bir katalog görünümü.

    Kötü görünüm GERÇEK bir görünüm adını (`kd_katalog_nusha`) taşır: reddin
    nedeni ad değil (tablo, sütun) izin listesi olsun. Önekli ama kümede olmayan
    bir ad (`kd_katalog_iyi`) ayrıca reddedilir (F5 düzeltmesi: tam ad kümesi)."""
    baglanti = sqlite3.connect(yol)
    baglanti.executescript(
        """
        CREATE TABLE kutuphane_work (id INTEGER PRIMARY KEY, title TEXT, deleted_at TEXT);
        CREATE TABLE kutuphane_membership (id INTEGER PRIMARY KEY, card_no TEXT);
        CREATE TABLE kutuphane_loan (id INTEGER PRIMARY KEY, work_id INT, membership_id INT);
        CREATE VIEW kd_katalog_nusha AS
            SELECT w.title AS baslik, m.card_no AS kart FROM kutuphane_work w
            JOIN kutuphane_loan l ON l.work_id = w.id
            JOIN kutuphane_membership m ON m.id = l.membership_id;
        CREATE VIEW kd_katalog_eser AS SELECT w.title AS baslik FROM kutuphane_work w;
        CREATE VIEW kd_katalog_iyi AS SELECT w.title AS baslik FROM kutuphane_work w;
        INSERT INTO kutuphane_work VALUES (1, 'Deneme', NULL);
        INSERT INTO kutuphane_membership VALUES (1, '12345678');
        INSERT INTO kutuphane_loan VALUES (1, 1, 1);
        """
    )
    baglanti.commit()
    baglanti.close()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM kutuphane_loan",
        "SELECT * FROM kutuphane_membership",
        "SELECT title FROM kutuphane_work",
        "SELECT baslik, kart FROM kd_katalog_nusha",
        "SELECT baslik FROM kd_katalog_nusha",
        # önekli ama görünüm kümesinde olmayan ad: izinli sütunu okusa da reddedilir
        "SELECT baslik FROM kd_katalog_iyi",
    ],
)
def test_odunc_ve_uyelik_tablolari_dogrudan_da_gorunumden_de_okunamaz(
    tmp_path: Path, sql: str
) -> None:
    yol = tmp_path / "yarin.sqlite3"
    _loan_kurgusu(yol)

    with pytest.raises(veri.VeriHatasi), veri.baglan(yol) as conn:
        conn.execute(sql).fetchall()


def test_kurguda_izinli_okuma_gecer(tmp_path: Path) -> None:
    """Kurgu doğru: izin listesindeki sütunu okuyan (kümedeki adlı) görünüm geçer."""
    yol = tmp_path / "yarin.sqlite3"
    _loan_kurgusu(yol)

    with veri.baglan(yol) as conn:
        assert [r[0] for r in conn.execute("SELECT baslik FROM kd_katalog_eser")] == ["Deneme"]


# ================================== §5.10-4 kaydedici authorizer: okunan (tablo, sütun)


@pytest.fixture
def kaydedici(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, set[Any]]]:
    """Katalogun her bağlantısına, kararı `veri.yetkilendir`'e bırakan kaydedici takar."""
    kayit: dict[str, set[Any]] = {"okuma": set(), "fonksiyon": set(), "red": set()}
    asil_baglan = veri.baglan

    def kaydeden(eylem: int, a1: Any, a2: Any, db: Any, ic: Any) -> int:
        karar = veri.yetkilendir(eylem, a1, a2, db, ic)
        if eylem == OKUMA and ic is not None:
            kayit["okuma"].add((a1, a2))
        if eylem == FONKSIYON:
            kayit["fonksiyon"].add(a2)
        if karar != OK:
            kayit["red"].add((eylem, a1, a2, ic))
        return karar

    @contextmanager
    def baglan(db_yolu: Path, **kw: Any) -> Iterator[sqlite3.Connection]:
        with asil_baglan(db_yolu, yetkilendirici=kaydeden, **kw) as conn:
            yield conn

    monkeypatch.setattr(veri, "baglan", baglan)
    yield kayit


def _butun_sayfalar(katalog: KatalogIstemcisi, eser_idleri: list[int]) -> list[int]:
    adresler = [
        "/",
        "/ara",
        "/ara?q=madonna",
        "/ara?tur=kitap&konu=8",
        "/eserler",
        "/eserler/K",
        "/eserler/diger",
        "/yazarlar",
        "/yazarlar/A",
        "/konular",
        "/konular/T",
        "/hakkinda",
        *[f"/eser/{i}" for i in eser_idleri],
    ]
    return [katalog.get(adres).code for adres in adres_listesi_tekil(adresler)]


def adres_listesi_tekil(adresler: list[str]) -> list[str]:
    return list(dict.fromkeys(adresler))


def _genis_kurgu() -> list[int]:
    b = bolum(name="Edebiyat", description="Roman, şiir ve öykü")
    w1 = eser(
        title="Kürk Mantolu Madonna",
        authors="Sabahattin Ali",
        subjects="Türk edebiyatı, roman",
        classification_code="813.54",
        section=b,
        isbn="978-605-00-0000-1",
    )
    nusha(w1, section=b)
    nusha(w1, is_reference=True)
    w2 = eser(title="Tarih Atlası", authors="", subjects="Tarih", resource_type=ResourceType.BOOK)
    nusha(w2)
    w3 = eser(title="1984", authors="George Orwell")
    nusha(w3)
    w4 = eser(title="Bilim Dergisi", resource_type=ResourceType.PERIODICAL)
    w5 = eser(title="Çevrimiçi Ansiklopedi", resource_type=ResourceType.EDATABASE)
    KatalogPopuler.objects.create(
        eser=w1,
        pencere_turu=PopulerPencereTuru.DONEM,
        pencere="2026-2027/1",
        sira=1,
        hesaplanma="2026-09-20",
    )
    return [w.pk for w in (w1, w2, w3, w4, w5)]


def test_gorunumlerin_okudugu_tablo_sutun_kumesi_anlik_goruntuyle_ayni(
    katalog: KatalogIstemcisi, kaydedici: dict[str, set[Any]]
) -> None:
    """Okunan küme izin listesinin TAMAMIDIR: fazlası reddedilirdi, eksiği ölü izindir."""
    kodlar = _butun_sayfalar(katalog, _genis_kurgu())

    assert set(kodlar) == {200}, kodlar
    assert kaydedici["red"] == set()
    assert kaydedici["okuma"] == veri.IZINLI_OKUMALAR
    assert kaydedici["fonksiyon"] <= veri.IZINLI_FONKSIYONLAR


#: Görünümlerin temel aldığı tablolar — yalnız bunlar (§5.3).
IZINLI_TABLOLAR = frozenset(
    {
        "kutuphane_work",
        "kutuphane_copy",
        "kutuphane_section",
        "okul_schoolconfig",
        "kutuphane_katalogayari",
    }
)
#: Görünümlere ASLA girmeyecek sütunlar (kişi, tanımlayıcı, bedel, taşınır kaydı).
YASAK_SUTUNLAR = frozenset(
    {
        ("kutuphane_copy", "barcode"),
        ("kutuphane_copy", "accession_no"),
        ("kutuphane_copy", "external_asset_ref"),
        ("kutuphane_copy", "old_register_no"),
        ("kutuphane_copy", "acquisition_id"),
        ("okul_schoolconfig", "principal_name"),
        ("okul_schoolconfig", "demirbas_no"),
        ("okul_schoolconfig", "app_password_hash"),
        ("kutuphane_katalogayari", "secili_ip"),
        ("kutuphane_katalogayari", "port"),
        ("kutuphane_katalogayari", "tahta_cidrleri"),
    }
)


def test_izin_listesi_yalniz_katalog_tablolarini_ve_kisisiz_sutunlari_kapsar() -> None:
    assert {tablo for tablo, _ in veri.IZINLI_OKUMALAR} == IZINLI_TABLOLAR
    assert veri.IZINLI_OKUMALAR.isdisjoint(YASAK_SUTUNLAR)


@pytest.mark.parametrize(
    "kelime",
    [
        "kutuphane_loan",  # yalın "loan" nüsha durumu 'ON_LOAN'da da geçer
        "membership",
        "acquisition",
        "donation",
        "commission",
        "okul_student",
        "okul_personnel",
        "barcode",
        "accession",
        "external_asset_ref",
        "old_register_no",
        "principal_name",
        "demirbas",
        "password",
    ],
)
def test_gorunum_tanimlari_kisi_ve_tanimlayici_tablolarina_uzanmaz(kelime: str) -> None:
    for ad, tanim in katalog_gorunumleri.gorunum_tanimlari().items():
        assert kelime not in tanim.lower(), f"{ad} görünümünde '{kelime}' geçiyor"


# ================================================== §5.10-5 alan listesi (anlık görüntü)


def _sutunlar(ad: str) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(f'PRAGMA table_info("{ad}")')
        return [satir[1] for satir in cursor.fetchall()]


def test_gorunumlerin_alan_listesi_anlik_goruntuyle_ayni() -> None:
    assert _sutunlar("kd_katalog_eser") == [
        "id",
        "baslik",
        "yazarlar",
        "cevirmen",
        "yayinevi",
        "baski",
        "yil",
        "isbn",
        "konular",
        "dil",
        "tur",
        "sinif_kodu",
        "ana_sinif",
        "yer_no",
        "bolum_adi",
        "bolum_tarifi",
        "arama",
        "sira",
        "yazar_sira",
        "konu_sira",
        "nusha_sayisi",
        "rafta",
        "oduncte",
        "sinifta",
        "onarimda",
        "odunc_verilmez_sayisi",
        "odunc_verilebilir",
    ]
    assert _sutunlar("kd_katalog_nusha") == [
        "id",
        "eser_id",
        "durum",
        "odunc_verilmez",
        "bolum_adi",
        "eklenme",
    ]
    assert _sutunlar("kd_katalog_okul") == ["okul_adi", "saatler", "vitrin_acik", "konular_acik"]
    assert _sutunlar("kd_katalog_populer") == [
        "id",
        "pencere_turu",
        "pencere",
        "sira",
        "hesaplanma",
        "dondu",
        "eser_id",
    ]


# ========================================================= görünümlerin yaşam döngüsü


def _gorunumler() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'view'")
        return {satir[0] for satir in cursor.fetchall()}


def test_migrate_sonrasi_her_gorunum_limit_0_sorgusundan_gecer() -> None:
    assert set(katalog_gorunumleri.GORUNUM_ADLARI) <= _gorunumler()
    with connection.cursor() as cursor:
        for ad in katalog_gorunumleri.GORUNUM_ADLARI:
            cursor.execute(f'SELECT * FROM "{ad}" LIMIT 0')  # noqa: S608 — sabit ad


def test_kancalar_kutuphane_uygulamasina_bagli() -> None:
    from django.apps import apps

    config = apps.get_app_config("kutuphane")
    assert isinstance(config, KutuphaneConfig)
    assert pre_migrate.has_listeners(sender=config)
    assert post_migrate.has_listeners(sender=config)


def test_dusurme_ve_kurma_fikirdes() -> None:
    katalog_gorunumleri.gorunumleri_dusur(connection)
    katalog_gorunumleri.gorunumleri_dusur(connection)
    assert not (set(katalog_gorunumleri.GORUNUM_ADLARI) & _gorunumler())

    assert katalog_gorunumleri.gorunumleri_kur(connection) == []
    assert katalog_gorunumleri.gorunumleri_kur(connection) == []
    assert set(katalog_gorunumleri.GORUNUM_ADLARI) <= _gorunumler()


def test_migrate_gorunumleri_dusurup_yeniden_kurar(monkeypatch: pytest.MonkeyPatch) -> None:
    """`pre_migrate` düşürür, `post_migrate` kurar: `migrate` sonunda görünümler yerindedir."""
    olaylar: list[str] = []
    asil_dusur = katalog_gorunumleri.gorunumleri_dusur
    asil_kur = katalog_gorunumleri.gorunumleri_kur

    def dusur(c: Any) -> None:
        olaylar.append("dusur")
        asil_dusur(c)

    def kur(c: Any) -> list[str]:
        olaylar.append("kur")
        return asil_kur(c)

    monkeypatch.setattr(katalog_gorunumleri, "gorunumleri_dusur", dusur)
    monkeypatch.setattr(katalog_gorunumleri, "gorunumleri_kur", kur)

    call_command("migrate", verbosity=0)

    assert olaylar == ["dusur", "kur"]
    assert set(katalog_gorunumleri.GORUNUM_ADLARI) <= _gorunumler()


def test_geri_ve_ileri_goc_gorunumleri_kirmaz() -> None:
    """Görünümün dayandığı tablo göçle kalkıp geri gelse de sonunda görünümler sağlamdır."""
    try:
        call_command("migrate", "kutuphane", "0003", verbosity=0)
        # Ayar tablosu yokken okul görünümü kurulamaz: DÜŞÜRÜLÜR, göç durmaz.
        assert "kd_katalog_okul" not in _gorunumler()
    finally:
        call_command("migrate", verbosity=0)
    assert set(katalog_gorunumleri.GORUNUM_ADLARI) <= _gorunumler()


def test_bozuk_gorunum_dusurulur_ve_raporlanir(monkeypatch: pytest.MonkeyPatch) -> None:
    asil = katalog_gorunumleri.gorunum_tanimlari

    def bozuk() -> dict[str, str]:
        tanimlar = asil()
        tanimlar["kd_katalog_nusha"] = "CREATE VIEW kd_katalog_nusha AS SELECT yok FROM yok_tablo"
        return tanimlar

    monkeypatch.setattr(katalog_gorunumleri, "gorunum_tanimlari", bozuk)
    try:
        assert katalog_gorunumleri.gorunumleri_kur(connection) == ["kd_katalog_nusha"]
        assert "kd_katalog_nusha" not in _gorunumler()
        assert "kd_katalog_eser" in _gorunumler()
    finally:
        monkeypatch.undo()
        katalog_gorunumleri.gorunumleri_kur(connection)


def test_gorunur_ve_gizli_durumlar_butun_durumlari_ayrik_kapsar() -> None:
    gorunur = set(katalog_gorunumleri.GORUNUR_DURUMLAR)
    gizli = set(katalog_gorunumleri.GIZLI_DURUMLAR)

    assert gorunur | gizli == set(CopyStatus.values)
    assert not gorunur & gizli
    assert gizli == {
        "LOST",
        "WITHDRAWN_WEEDED",
        "WITHDRAWN_MISSING",
        "WITHDRAWN_LOST",
        "TRANSFERRED",
    }


# =============================================== §5.10-11 "Ödünç verilmez" paritesi


def test_sql_odunc_turetimi_is_loanable_ve_loanable_q_ile_ayni() -> None:
    """Bütün kombinasyonlar: kaynak türü × danışma × piyasada yok × durum (UY-12)."""
    acquisition = edinim()
    turler = (
        ResourceType.BOOK,
        ResourceType.PERIODICAL,
        ResourceType.AV_MATERIAL,
        ResourceType.EBOOK,
        ResourceType.EDATABASE,
    )
    for tur in turler:
        # Nüshalar KİTAP türünde açılır, eserin türü ham `update` ile değişir:
        # servisler dijital eserde nüsha açtırmaz; türetimler kural delinse de
        # aynı cevabı vermek zorundadır (test_models.py'deki kalıp).
        work = eser(title=f"Eser {tur}")
        for danisma, piyasada_yok, durum in itertools.product(
            (False, True), (False, True), CopyStatus.values
        ):
            copy = nusha(work, acquisition, is_reference=danisma, is_out_of_print=piyasada_yok)
            if durum != CopyStatus.AVAILABLE:
                Copy.objects.filter(pk=copy.pk).update(status=durum)
        Work.objects.filter(pk=work.pk).update(resource_type=tur)

    with veri.baglan(_db_yolu()) as conn:
        satirlar = conn.execute("SELECT id, durum, odunc_verilmez FROM kd_katalog_nusha").fetchall()
        eser_sayaclari = {
            int(r["id"]): int(r["odunc_verilebilir"])
            for r in conn.execute("SELECT id, odunc_verilebilir FROM kd_katalog_eser")
        }
    sql_verilebilir = {
        int(r["id"])
        for r in satirlar
        if r["durum"] == CopyStatus.AVAILABLE and int(r["odunc_verilmez"]) == 0
    }
    ozellikle = {c.pk for c in Copy.objects.select_related("work") if c.is_loanable}
    suzgecle = set(Copy.objects.filter(selectors.LOANABLE_Q).values_list("pk", flat=True))

    assert ozellikle, "Kurgu bozuk: hiç ödünç verilebilir nüsha yok"
    assert sql_verilebilir == ozellikle == suzgecle
    # Eser düzeyindeki sayaç da aynı türetimden gelir.
    for work in Work.objects.all():
        beklenen = sum(1 for c in work.copies.all() if c.is_loanable)
        assert eser_sayaclari.get(work.pk, 0) == beklenen, work.title
    # Görünür nüshalar tam olarak beyaz listedeki durumlardır.
    gorunur_idler = {int(r["id"]) for r in satirlar}
    beklenen_gorunur = set(
        Copy.objects.filter(status__in=katalog_gorunumleri.GORUNUR_DURUMLAR).values_list(
            "pk", flat=True
        )
    )
    assert gorunur_idler == beklenen_gorunur


# ======================================== §5.10-11 yumuşak silme: arama, dizin, sayaç


def _eser_satiri(conn: sqlite3.Connection, eser_id: int) -> Any:
    return conn.execute("SELECT * FROM kd_katalog_eser WHERE id = ?", (eser_id,)).fetchone()


def test_silinmis_ve_elden_cikmis_nushalar_sayaclarda_gorunmez() -> None:
    work = eser(title="Sayaç Eseri")
    rafta = nusha(work)
    oduncte = nusha(work)
    Copy.objects.filter(pk=oduncte.pk).update(status=CopyStatus.ON_LOAN)
    silinen = nusha(work)
    silinen.delete()
    for durum in katalog_gorunumleri.GIZLI_DURUMLAR:
        Copy.objects.filter(pk=nusha(work).pk).update(status=durum)

    with veri.baglan(_db_yolu()) as conn:
        satir = _eser_satiri(conn, work.pk)
        nushalar = conn.execute(
            "SELECT id FROM kd_katalog_nusha WHERE eser_id = ?", (work.pk,)
        ).fetchall()

    assert (satir["nusha_sayisi"], satir["rafta"], satir["oduncte"]) == (2, 1, 1)
    assert {int(r["id"]) for r in nushalar} == {rafta.pk, oduncte.pk}


def test_silinmis_eser_ve_butun_nushasi_elden_cikmis_kitap_gorunmez() -> None:
    silinen = eser(title="Silinen Eser")
    nusha(silinen)
    silinen.delete()
    ayiklanan = eser(title="Ayıklanan Eser")
    Copy.objects.filter(pk=nusha(ayiklanan).pk).update(status=CopyStatus.WITHDRAWN_WEEDED)
    nushasiz_kitap = eser(title="Nüshasız Kitap")
    dijital = eser(title="Dijital Kaynak", resource_type=ResourceType.EBOOK)
    dergi = eser(title="Ciltsiz Dergi", resource_type=ResourceType.PERIODICAL)

    with veri.baglan(_db_yolu()) as conn:
        idler = {int(r["id"]) for r in conn.execute("SELECT id FROM kd_katalog_eser")}
        silinen_nusha = conn.execute(
            "SELECT count(*) FROM kd_katalog_nusha WHERE eser_id = ?", (silinen.pk,)
        ).fetchone()[0]

    assert silinen.pk not in idler
    assert silinen_nusha == 0  # silinmiş eserin canlı nüshası da görünmez
    assert ayiklanan.pk not in idler
    assert nushasiz_kitap.pk not in idler
    assert {dijital.pk, dergi.pk} <= idler


def test_silinmis_eser_aramada_dizinde_ve_sayfasinda_yok(katalog: KatalogIstemcisi) -> None:
    kalan = eser(title="Kalan Madonna", authors="Deneme Yazar")
    nusha(kalan)
    silinen = eser(title="Silinen Madonna", authors="Deneme Yazar")
    nusha(silinen)
    silinen.delete()

    arama = katalog.get("/ara?q=madonna").text
    dizin = katalog.get("/eserler/S").text
    yazar = katalog.get("/yazarlar/Y").text

    assert "Kalan Madonna" in arama and "Silinen Madonna" not in arama
    assert "Silinen Madonna" not in dizin
    assert "Silinen Madonna" not in yazar and "Kalan Madonna" in yazar
    assert katalog.get(f"/eser/{silinen.pk}").code == 404
    assert katalog.get(f"/eser/{kalan.pk}").code == 200


def test_silinmis_bolum_adi_gorunmez() -> None:
    b = bolum(name="Kapanan Bölüm")
    work = eser(title="Bölümlü Eser", section=b)
    nusha(work, section=b)
    b.delete()

    with veri.baglan(_db_yolu()) as conn:
        assert _eser_satiri(conn, work.pk)["bolum_adi"] is None
        assert (
            conn.execute(
                "SELECT bolum_adi FROM kd_katalog_nusha WHERE eser_id = ?", (work.pk,)
            ).fetchone()[0]
            is None
        )
