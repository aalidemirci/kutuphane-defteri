"""Ağ Kataloğu görünümleri — `kd_katalog_*` SQL tanımları ve yaşam döngüsü (tasarım §5.3).

Ağ Kataloğu (`backend/katalog/`) veriye YALNIZ bu görünümlerden ulaşır: salt
okur bağlantısının authorizer'ı, 5. argümanı `kd_katalog_` ile başlamayan her
tablo okumasını reddeder. Görünümler bu yüzden ağa açılan yüzeyin **veri
sözleşmesidir** ve üç kuralı TANIMLARINDA taşır:

1. **Kişi verisi girmez.** `Loan`, `Membership`, `Acquisition` ve kişi
   tabloları (`okul_student`, `okul_personnel`, bağış ön kaydı, komisyon
   kararı) hiçbir görünümde geçmez. Nüshanın barkodu, kayıt no'su, TKYS kodu,
   eski kayıt no'su ve edinimi de geçmez (§5.1 "Asla görünmez" sütunu). Okul
   satırından yalnız okul adı ve kütüphane saatleri okunur; müdür adı,
   bilgisayarın demirbaş no'su ve parola parmak izi AYNI TABLODADIR ama
   görünüme girmez. Koruma: `katalog/tests/test_veri_erisimi.py` kaydedici bir
   authorizer'la okunan (tablo, sütun) kümesini anlık görüntüyle karşılaştırır
   ve F6/F7'de yeniden koşar.
2. **Yumuşak silinmiş kayıt ve elden çıkmış nüsha görünmez** (§5.1, EK-7).
   Nüsha durumu için süzgeç BEYAZ LİSTEDİR (`GORUNUR_DURUMLAR`): kayıp,
   kayıttan düşülmüş ve devredilmiş nüsha görünmez; ileride eklenecek yeni bir
   durum da bilinçli olarak listeye alınana dek görünmez (fail-closed). Bütün
   sayaçlar yalnız bu süzgeçten geçen nüshalardan türer.
3. **"Ödünç verilmez" tek türetimdir** (§5.1, UY-12): danışma kaynağı YA DA
   piyasada mevcudu yok YA DA süreli yayın (ve savunma derinliği olarak dijital
   kaynak — `Copy.is_loanable` ile aynı dört koşul). `odunc_verilmez = 0 VE
   durum = rafta` ≡ `Copy.is_loanable` ≡ `selectors.LOANABLE_Q`; parite testi
   bütün kombinasyonlarda karşılaştırır.

**Eser görünür mü?** Silinmemiş eser, en az bir görünür nüshası varsa
görünür. Nüshasız eserlerden yalnız dijital kaynaklar (künye olarak
listelenir, dosya dağıtılmaz — §5.1) ve süreli yayınlar (ciltlenmedikçe kayda
girmez, TMY 15/4; kütüphanede okunur) görünür. Bütün nüshaları kayıttan
düşülmüş bir kitap katalogda "0 nüsha" diye durmaz: kütüphanede yoktur.

**Fonksiyonlar.** Authorizer `SQLITE_FUNCTION`'ı izin listesiyle sınırlar
(`like`, `lower`, `count`, `coalesce`, `substr`, `length`) ve SQLite görünüm
gövdesindeki fonksiyonları da sorgu anında yetkilendirir. Bu yüzden
tanımlarda bu altısı dışında fonksiyon KULLANILMAZ (`CASE`, `IN`, `EXISTS`
fonksiyon değildir).

**Yaşam döngüsü** (UY-10). Django'nun SQLite şema düzenleyicisi alan
değiştirirken tabloyu yeniden kurar (yeni tablo → kopya → eskiyi sil → yeniden
adlandır); tabloya bağlı bir görünüm varken son adım "görünümde bulunmayan
tablo" hatasıyla düşer. Görünümler bu yüzden göçlerde kalıcı DURMAZ:
`pre_migrate` hepsini düşürür, `post_migrate` hepsini yeniden kurar
(fikirdeş: önce `DROP VIEW IF EXISTS`, sonra `CREATE VIEW`). Kurulumdan sonra
her görünüm `SELECT … LIMIT 0` ile sınanır; sınamadan geçmeyen görünüm
düşürülür ve günlüğe yazılır — katalog o veriye ulaşamaz, 503 döner (fail-closed).
Kancalar `KutuphaneConfig.ready()` içinde bağlanır.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, Final

from django.db import DatabaseError
from django.db.backends.base.base import BaseDatabaseWrapper

from apps.kutuphane.models import (
    DIGITAL_RESOURCE_TYPES,
    TERMINAL_COPY_STATUSES,
    CopyStatus,
    KatalogAyari,
    ResourceType,
)
from apps.okul.models import SchoolConfig

logger = logging.getLogger("kutuphane_defteri.katalog")

#: Ağ Kataloğunda görünen nüsha durumları (BEYAZ LİSTE — modül belgesi, madde 2).
GORUNUR_DURUMLAR: Final[tuple[str, ...]] = (
    CopyStatus.AVAILABLE,
    CopyStatus.ON_LOAN,
    CopyStatus.DELIVERED,
    CopyStatus.IN_REPAIR,
)
#: Görünmeyen durumlar: kayıp ve elden çıkmış nüshalar (§5.1). İki liste
#: birlikte `CopyStatus`'un tamamını kapsar (koruma testi).
GIZLI_DURUMLAR: Final[tuple[str, ...]] = (CopyStatus.LOST, *TERMINAL_COPY_STATUSES)

#: Nüshası olmadan da görünen kaynak türleri (dijital + süreli yayın).
NUSHASIZ_GORUNEN_TURLER: Final[tuple[str, ...]] = (
    *DIGITAL_RESOURCE_TYPES,
    ResourceType.PERIODICAL,
)
#: "Ödünç verilmez" türetimine giren kaynak türleri (süreli yayın + dijital).
ODUNC_VERILMEZ_TURLER: Final[tuple[str, ...]] = (
    ResourceType.PERIODICAL,
    *DIGITAL_RESOURCE_TYPES,
)

#: Görünüm adlarının öneki — authorizer yalnız bu önekle gelen okumaya izin verir.
GORUNUM_ONEKI: Final = "kd_katalog_"

_TABLO_ESER: Final = "kutuphane_work"
_TABLO_NUSHA: Final = "kutuphane_copy"
_TABLO_BOLUM: Final = "kutuphane_section"
_TABLO_OKUL: Final = "okul_schoolconfig"
_TABLO_AYAR: Final = KatalogAyari._meta.db_table


def _sql_liste(degerler: Iterable[str]) -> str:
    """Sabit kod listesini SQL `IN (...)` gövdesine çevirir.

    Değerler bu modülün sabitleridir (model seçenekleri); kullanıcı girdisi
    buraya ulaşmaz. Yine de tek tırnak içeren bir değer tanımı bozmasın diye
    denetlenir.
    """
    kalemler = []
    for deger in degerler:
        metin = str(deger)
        if not metin.replace("_", "").isalnum() or not metin.isascii():
            raise ValueError(f"Görünüm tanımına güvenli olmayan sabit girdi: {metin!r}")
        kalemler.append(f"'{metin}'")
    return ", ".join(kalemler)


def _gorunur_nusha_kosulu(takma_ad: str) -> str:
    """Bir nüshanın katalogda görünme koşulu (silinmemiş + beyaz listedeki durum)."""
    return (
        f"{takma_ad}.deleted_at IS NULL "
        f"AND {takma_ad}.status IN ({_sql_liste(GORUNUR_DURUMLAR)})"
    )


def _nusha_sayaci(ek_kosul: str = "") -> str:
    """Eserin görünür nüshalarından türeyen bir sayaç (ilişkili alt sorgu)."""
    # Görünüm tanımları yalnız bu modülün sabitlerinden kurulur (kullanıcı girdisi yok).
    kosul = f" AND {ek_kosul}" if ek_kosul else ""
    gorunur = _gorunur_nusha_kosulu("c")
    return f"(SELECT count(*) FROM {_TABLO_NUSHA} AS c WHERE c.work_id = w.id AND {gorunur}{kosul})"  # noqa: S608


def _odunc_verilmez_ifadesi(nusha: str, eser: str) -> str:
    """ "Ödünç verilmez" türetimi (modül belgesi, madde 3) — 1/0."""
    return (
        f"(CASE WHEN {nusha}.is_reference OR {nusha}.is_out_of_print "
        f"OR {eser}.resource_type IN ({_sql_liste(ODUNC_VERILMEZ_TURLER)}) "
        "THEN 1 ELSE 0 END)"
    )


def _durum_esit(takma_ad: str, durum: str) -> str:
    """`c.status = 'AVAILABLE'` biçiminde koşul (değer model sabitinden gelir)."""
    return f"{takma_ad}.status = {_sql_liste([durum])}"


def _eser_sql() -> str:
    odunc_verilmez = (
        f"(c.is_reference OR c.is_out_of_print "
        f"OR w.resource_type IN ({_sql_liste(ODUNC_VERILMEZ_TURLER)}))"
    )
    rafta = _durum_esit("c", CopyStatus.AVAILABLE)
    return f"""
CREATE VIEW kd_katalog_eser AS
SELECT
    w.id AS id,
    w.title AS baslik,
    w.authors AS yazarlar,
    w.translator AS cevirmen,
    w.publisher AS yayinevi,
    w.edition AS baski,
    w.publish_year AS yil,
    w.isbn AS isbn,
    w.subjects AS konular,
    w.language AS dil,
    w.resource_type AS tur,
    w.classification_code AS sinif_kodu,
    substr(w.classification_code, 1, 1) AS ana_sinif,
    w.call_number AS yer_no,
    s.name AS bolum_adi,
    s.description AS bolum_tarifi,
    w.search_key AS arama,
    w.sort_key AS sira,
    w.author_sort_key AS yazar_sira,
    w.subject_sort_key AS konu_sira,
    {_nusha_sayaci()} AS nusha_sayisi,
    {_nusha_sayaci(rafta)} AS rafta,
    {_nusha_sayaci(_durum_esit("c", CopyStatus.ON_LOAN))} AS oduncte,
    {_nusha_sayaci(_durum_esit("c", CopyStatus.DELIVERED))} AS sinifta,
    {_nusha_sayaci(_durum_esit("c", CopyStatus.IN_REPAIR))} AS onarimda,
    {_nusha_sayaci(odunc_verilmez)} AS odunc_verilmez_sayisi,
    {_nusha_sayaci(f"{rafta} AND NOT {odunc_verilmez}")} AS odunc_verilebilir
FROM {_TABLO_ESER} AS w
LEFT JOIN {_TABLO_BOLUM} AS s ON s.id = w.section_id AND s.deleted_at IS NULL
WHERE w.deleted_at IS NULL
  AND (
    w.resource_type IN ({_sql_liste(NUSHASIZ_GORUNEN_TURLER)})
    OR EXISTS (
        SELECT 1 FROM {_TABLO_NUSHA} AS c
        WHERE c.work_id = w.id AND {_gorunur_nusha_kosulu('c')}
    )
  )
"""  # noqa: S608 — yalnız modül sabitleri


def _nusha_sql() -> str:
    return f"""
CREATE VIEW kd_katalog_nusha AS
SELECT
    c.id AS id,
    c.work_id AS eser_id,
    c.status AS durum,
    {_odunc_verilmez_ifadesi('c', 'w')} AS odunc_verilmez,
    coalesce(cs.name, ws.name) AS bolum_adi,
    c.created_at AS eklenme
FROM {_TABLO_NUSHA} AS c
JOIN {_TABLO_ESER} AS w ON w.id = c.work_id AND w.deleted_at IS NULL
LEFT JOIN {_TABLO_BOLUM} AS cs ON cs.id = c.section_id AND cs.deleted_at IS NULL
LEFT JOIN {_TABLO_BOLUM} AS ws ON ws.id = w.section_id AND ws.deleted_at IS NULL
WHERE {_gorunur_nusha_kosulu('c')}
"""


def _okul_sql() -> str:
    # Tek satır her durumda döner (okul ve ayar satırı henüz yoksa da): taban
    # `(SELECT 1)`'dir, iki tablo ona sol birleşimle bağlanır.
    return f"""
CREATE VIEW kd_katalog_okul AS
SELECT
    coalesce(sc.school_name, '') AS okul_adi,
    coalesce(sc.kutuphane_saatleri, '') AS saatler,
    coalesce(ka.vitrin_acik, 1) AS vitrin_acik,
    coalesce(ka.konular_acik, 1) AS konular_acik
FROM (SELECT 1 AS tek) AS t
LEFT JOIN {_TABLO_OKUL} AS sc ON sc.id = {SchoolConfig.SINGLETON_PK} AND sc.deleted_at IS NULL
LEFT JOIN {_TABLO_AYAR} AS ka ON ka.id = {KatalogAyari.SINGLETON_PK} AND ka.deleted_at IS NULL
"""


def gorunum_tanimlari() -> dict[str, str]:
    """Görünüm adı → `CREATE VIEW` metni.

    Görünümler birbirine dayanmaz (her biri yalnız temel tablolardan okur);
    böylece authorizer'ın gördüğü (tablo, sütun) kümesi yalnız gerçek tablo
    sütunlarından oluşur. Yine de sabit sırada kurulur ve düşürülür.
    """
    return {
        "kd_katalog_eser": _eser_sql(),
        "kd_katalog_nusha": _nusha_sql(),
        "kd_katalog_okul": _okul_sql(),
    }


GORUNUM_ADLARI: Final[tuple[str, ...]] = ("kd_katalog_eser", "kd_katalog_nusha", "kd_katalog_okul")


def _sqlite_mi(connection: BaseDatabaseWrapper) -> bool:
    return connection.vendor == "sqlite"


def gorunumleri_dusur(connection: BaseDatabaseWrapper) -> None:
    """Bütün `kd_katalog_*` görünümlerini düşürür (fikirdeş)."""
    if not _sqlite_mi(connection):
        return
    with connection.cursor() as cursor:
        for ad in GORUNUM_ADLARI:
            cursor.execute(f'DROP VIEW IF EXISTS "{ad}"')


def gorunumleri_kur(connection: BaseDatabaseWrapper) -> list[str]:
    """Görünümleri (yeniden) kurar ve `SELECT … LIMIT 0` ile sınar.

    Kurulamayan ya da sınamadan geçmeyen görünüm düşürülür ve adı döndürülür
    (boş liste = hepsi sağlam). Hata YÜKSELTİLMEZ: göç işlemini ve programın
    açılışını görünüm yüzünden durdurmak, yönetim işlerini de durdururdu;
    katalog eksik görünümde 503 döner.
    """
    if not _sqlite_mi(connection):
        return []
    bozuk: list[str] = []
    for ad, tanim in gorunum_tanimlari().items():
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'DROP VIEW IF EXISTS "{ad}"')
                cursor.execute(tanim)
                cursor.execute(f'SELECT * FROM "{ad}" LIMIT 0')  # noqa: S608 — sabit ad
        except DatabaseError:
            logger.exception("Ağ Kataloğu görünümü kurulamadı: %s", ad)
            bozuk.append(ad)
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'DROP VIEW IF EXISTS "{ad}"')
            except DatabaseError:
                logger.exception("Bozuk görünüm düşürülemedi: %s", ad)
    return bozuk


def _baglanti(using: str) -> BaseDatabaseWrapper:
    from django.db import connections

    return connections[using]


def pre_migrate_gorunumleri_dusur(*, using: str = "default", **kwargs: Any) -> None:
    """`pre_migrate` kancası: şema düzenleyici tabloyu yeniden kurmadan ÖNCE."""
    gorunumleri_dusur(_baglanti(using))


def post_migrate_gorunumleri_kur(*, using: str = "default", **kwargs: Any) -> None:
    """`post_migrate` kancası: bütün göçler bittikten SONRA (fikirdeş)."""
    gorunumleri_kur(_baglanti(using))
