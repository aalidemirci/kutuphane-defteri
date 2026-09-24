"""Ağ Kataloğunun veri erişimi — salt okur bağlantı, eylem kodlu authorizer (tasarım §5.3).

**Bağlantı sırası** (her istek kendi bağlantısını açar ve kapatır):

1. `sqlite3.connect(<dosya URI'si>?mode=ro, uri=True)` — dosya sistemi
   düzeyinde salt okur;
2. `PRAGMA query_only=ON` — bağlantı düzeyinde yazma yasağı;
3. `set_authorizer(yetkilendir)` — eylem kodlu izin tablosu (aşağıda);
4. `set_progress_handler(...)` — uzun süren sorguyu keser.

**Authorizer** (§5.3 tablosu BİREBİR). SQLite, bir görünüm üzerinden okunan
alttaki tablo sütunu için `SQLITE_READ` çağırır ve görünümün adını 5.
argümanda verir (GA-3, UY-11, EK-3):

| Eylem | Karar |
|---|---|
| `SQLITE_SELECT` | izin |
| `SQLITE_FUNCTION` | izin listesi: `like`, `lower`, `count`, `coalesce`, `substr`, `length` |
| `SQLITE_READ`, 5. argüman `GORUNUMLER`'den biri ve (tablo, sütun) sabit izin listesinde | izin |
| `SQLITE_READ`, 5. argüman `None` ve tablo `UST_DUZEY_OKUNABILIR`'de (görünümün kendi sütunları; `count(*)` için boş sütun dahil) | izin |
| Geri kalan her şey | `SQLITE_DENY` |

Adlar ÖNEKLE değil TAM KÜMEYLE denetlenir (F5 düzeltmesi): ileride
`kd_katalog_` önekiyle eklenecek bir tablo ya da görünüm (ör. ham sayı ya da
üye taşıyan bir ara tablo) kendiliğinden ağa açılmaz; kümeye bilinçli eklenir.
`GORUNUMLER`'in görünüm tanımlarıyla (`katalog_gorunumleri.gorunum_tanimlari`)
aynı olduğunu bir test sınar.

Böylece katalog (a) temel tabloları DOĞRUDAN okuyamaz (`SELECT title FROM
kutuphane_work` reddedilir), (b) bir görünüm yanlışlıkla kişi tablosuna ya da
listede olmayan bir sütuna uzansa bile o okuma reddedilir, (c) PRAGMA, ATTACH,
yazma ve izin listesi dışı fonksiyon çalıştıramaz. İzin listesindeki (tablo,
sütun) çiftleri görünüm tanımlarının (`apps/kutuphane/katalog_gorunumleri.py`)
okuduğu kümenin kendisidir; kaydedici authorizer testi ikisini birebir
karşılaştırır (§5.10-4).

**Bilinen sınır (authorizer tek başına yetmez).** SQLite 5. argümanda görünüm
adını da, FROM'daki adlı bir CTE'nin adını da aynı biçimde verir; authorizer
ikisini AYIRAMAZ. Görünümle aynı adı taşıyan bir CTE (`WITH kd_katalog_eser AS
(SELECT title AS baslik FROM kutuphane_work) …`) izin listesindeki (tablo, sütun)
çiftlerini görünümün TANIMINDAKİ süzgeçler (yumuşak silme, nüsha durumu)
olmadan okuyabilir. Barkod, kişi ve ödünç tabloları yine reddedilir (izin
listesinde yoklar). Güvencenin asıl dayanağı katalogdaki bütün SQL'in SABİT
olmasıdır: değerler parametredir, sütun ve sıralama sabit kümeden seçilir,
kullanıcı girdisi SQL metnine girmez ve katalog kaynağında CTE (`WITH`) yoktur
(`katalog/tests/test_veri_erisimi.py` kaynak taramasıyla sınar). Authorizer
bunun üzerine ikinci katmandır.

Bu modül yalnız standart kütüphaneyi kullanır; Django'nun veri katmanına
dokunmaz (§4.1).
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from katalog import sabitler

#: Görünüm adlarının öneki (yalnız adlandırma kuralı; izin kararı TAM kümeyle verilir).
GORUNUM_ONEKI: Final = "kd_katalog_"

#: Katalogun görünümleri: görünüm İÇİNDEN okumada 5. argüman bunlardan biri olmalıdır.
#: `apps/kutuphane/katalog_gorunumleri.py::gorunum_tanimlari` ile aynı (test sınar).
GORUNUMLER: Final = frozenset({"kd_katalog_eser", "kd_katalog_nusha", "kd_katalog_okul"})

#: Üst düzeyde doğrudan okunabilen adlar: görünümler + kişisiz `kd_katalog_populer`
#: tablosu (eser, pencere, sıra; sayı alanı yok — tasarım §5.3, F5 ekleri 5).
UST_DUZEY_OKUNABILIR: Final = GORUNUMLER | frozenset({"kd_katalog_populer"})

#: `SQLITE_FUNCTION` için izin listesi (§5.3).
IZINLI_FONKSIYONLAR: Final = frozenset({"like", "lower", "count", "coalesce", "substr", "length"})

#: Görünümlerin okuyabildiği (tablo, sütun) çiftleri — sabit izin listesi (§5.3).
#: Kişi tabloları, `Acquisition`, `Loan`, `Membership` HİÇ yoktur; nüshanın
#: barkodu, kayıt no'su, TKYS kodu ve eski kayıt no'su, okul satırının müdür
#: adı, demirbaş no'su ve parola parmak izi de yoktur.
IZINLI_OKUMALAR: Final = frozenset(
    {
        ("kutuphane_work", "id"),
        ("kutuphane_work", "title"),
        ("kutuphane_work", "authors"),
        ("kutuphane_work", "translator"),
        ("kutuphane_work", "publisher"),
        ("kutuphane_work", "edition"),
        ("kutuphane_work", "publish_year"),
        ("kutuphane_work", "isbn"),
        ("kutuphane_work", "subjects"),
        ("kutuphane_work", "language"),
        ("kutuphane_work", "resource_type"),
        ("kutuphane_work", "classification_code"),
        ("kutuphane_work", "call_number"),
        ("kutuphane_work", "section_id"),
        ("kutuphane_work", "search_key"),
        ("kutuphane_work", "sort_key"),
        ("kutuphane_work", "author_sort_key"),
        ("kutuphane_work", "subject_sort_key"),
        ("kutuphane_work", "deleted_at"),
        ("kutuphane_copy", "id"),
        ("kutuphane_copy", "work_id"),
        ("kutuphane_copy", "status"),
        ("kutuphane_copy", "is_reference"),
        ("kutuphane_copy", "is_out_of_print"),
        ("kutuphane_copy", "section_id"),
        ("kutuphane_copy", "created_at"),
        ("kutuphane_copy", "deleted_at"),
        ("kutuphane_section", "id"),
        ("kutuphane_section", "name"),
        ("kutuphane_section", "description"),
        ("kutuphane_section", "deleted_at"),
        ("okul_schoolconfig", "id"),
        ("okul_schoolconfig", "school_name"),
        ("okul_schoolconfig", "kutuphane_saatleri"),
        ("okul_schoolconfig", "deleted_at"),
        ("kutuphane_katalogayari", "id"),
        ("kutuphane_katalogayari", "vitrin_acik"),
        ("kutuphane_katalogayari", "konular_acik"),
        ("kutuphane_katalogayari", "deleted_at"),
    }
)

#: Tek bir isteğin veritabanında harcayabileceği en uzun süre (saniye).
VARSAYILAN_SORGU_SURESI: Final = 2.0
#: İlerleme işleyicisinin çağrılma aralığı (SQLite sanal makine komutu).
_ILERLEME_ARALIGI: Final = 1000
#: Başka bir bağlantı yazarken beklenecek en uzun süre (WAL'de okuma beklemez).
_MESGUL_BEKLEME: Final = 2.0


class VeriHatasi(Exception):
    """Katalog veritabanına ulaşamadı (dosya yok, görünüm yok, sorgu kesildi) → 503."""


def yetkilendir(
    eylem: int, arg1: str | None, arg2: str | None, db_adi: str | None, ic: str | None
) -> int:
    """§5.3 authorizer tablosu (modül belgesi). Karşılığı olmayan her şey `SQLITE_DENY`."""
    if eylem == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if eylem == sqlite3.SQLITE_FUNCTION:
        # SQLITE_FUNCTION'da 3. argüman (arg2) fonksiyon adıdır.
        ad = (arg2 or "").lower()
        return sqlite3.SQLITE_OK if ad in IZINLI_FONKSIYONLAR else sqlite3.SQLITE_DENY
    if eylem == sqlite3.SQLITE_READ:
        tablo, sutun = arg1 or "", arg2 or ""
        if ic is not None:
            if ic in GORUNUMLER and (tablo, sutun) in IZINLI_OKUMALAR:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        if tablo in UST_DUZEY_OKUNABILIR:
            return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def baglanti_adresi(db_yolu: Path) -> str:
    """Salt okur SQLite URI'si (`file:///…?mode=ro`)."""
    return db_yolu.resolve().as_uri() + "?mode=ro"


@contextmanager
def baglan(
    db_yolu: Path,
    *,
    sorgu_suresi: float = VARSAYILAN_SORGU_SURESI,
    saat: Callable[[], float] = time.monotonic,
    yetkilendirici: Callable[[int, str | None, str | None, str | None, str | None], int] = (
        yetkilendir
    ),
) -> Iterator[sqlite3.Connection]:
    """Bağlantı sırası (modül belgesi) — çıkışta bağlantı HER DURUMDA kapanır.

    `yetkilendirici` yalnız testler içindir (kaydedici authorizer, §5.10-4);
    kaydedici de her kararı bu modülün `yetkilendir`'ine bırakmalıdır.
    """
    if not db_yolu.is_file():
        raise VeriHatasi("veritabanı dosyası bulunamadı")
    try:
        conn = sqlite3.connect(
            baglanti_adresi(db_yolu), uri=True, timeout=_MESGUL_BEKLEME, check_same_thread=True
        )
    except sqlite3.Error as exc:
        raise VeriHatasi("veritabanı açılamadı") from exc
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.set_authorizer(yetkilendirici)
        son_an = saat() + sorgu_suresi

        def ilerleme() -> int:
            # Sıfır dışı dönüş sorguyu keser (sqlite3.OperationalError "interrupted").
            return 1 if saat() > son_an else 0

        conn.set_progress_handler(ilerleme, _ILERLEME_ARALIGI)
        yield conn
    except sqlite3.Error as exc:
        raise VeriHatasi("katalog sorgusu tamamlanamadı") from exc
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sorgular — yalnız `kd_katalog_*` görünümleri ve `kd_katalog_populer` tablosu
# ---------------------------------------------------------------------------
_ESER_SUTUNLARI: Final = (
    "id, baslik, yazarlar, cevirmen, yayinevi, baski, yil, isbn, konular, dil, tur, "
    "sinif_kodu, ana_sinif, yer_no, bolum_adi, bolum_tarifi, nusha_sayisi, rafta, "
    "oduncte, sinifta, onarimda, odunc_verilmez_sayisi, odunc_verilebilir"
)


@dataclass(frozen=True)
class OkulBilgisi:
    okul_adi: str
    saatler: str
    vitrin_acik: bool
    konular_acik: bool


@dataclass(frozen=True)
class Sayfa:
    """Sayfalı sonuç: satırlar + toplam + (kırpılmış) sayfa numarası."""

    satirlar: list[dict[str, Any]]
    toplam: int
    sayfa: int
    sayfa_sayisi: int


def _satir(row: sqlite3.Row) -> dict[str, Any]:
    return {anahtar: row[anahtar] for anahtar in row.keys()}


def like_kacir(metin: str) -> str:
    """`LIKE ? ESCAPE '\\'` için `%`, `_` ve `\\` kaçırılır."""
    return metin.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def sayfa_kirp(istenen: int, toplam: int) -> tuple[int, int]:
    """`sayfa` değeri `1..min(ceil(toplam/20), 500)` aralığına kırpılır (§5.3)."""
    sayfa_sayisi = max(1, min(-(-toplam // sabitler.SAYFA_BOYUTU), sabitler.EN_COK_SAYFA))
    return max(1, min(istenen, sayfa_sayisi)), sayfa_sayisi


def okul_bilgisi(conn: sqlite3.Connection) -> OkulBilgisi:
    row = conn.execute(
        "SELECT okul_adi, saatler, vitrin_acik, konular_acik FROM kd_katalog_okul"
    ).fetchone()
    if row is None:  # görünüm her durumda tek satır döner; savunma
        return OkulBilgisi("", "", True, True)
    return OkulBilgisi(
        okul_adi=str(row["okul_adi"] or ""),
        saatler=str(row["saatler"] or ""),
        vitrin_acik=bool(row["vitrin_acik"]),
        konular_acik=bool(row["konular_acik"]),
    )


def _sayfali(
    conn: sqlite3.Connection,
    *,
    kosullar: Sequence[str],
    degerler: Sequence[object],
    siralama: str,
    sayfa: int,
) -> Sayfa:
    # Koşullar bu modülün sabit parçalarıdır; kullanıcı değerleri yalnız parametredir.
    where = f" WHERE {' AND '.join(kosullar)}" if kosullar else ""
    sayim_sql = f"SELECT count(*) FROM kd_katalog_eser{where}"  # noqa: S608
    toplam = int(conn.execute(sayim_sql, degerler).fetchone()[0])
    gecerli, sayfa_sayisi = sayfa_kirp(sayfa, toplam)
    satirlar = conn.execute(
        f"SELECT {_ESER_SUTUNLARI} FROM kd_katalog_eser{where} "  # noqa: S608 — sabit parçalar
        f"ORDER BY {siralama} LIMIT ? OFFSET ?",
        (*degerler, sabitler.SAYFA_BOYUTU, (gecerli - 1) * sabitler.SAYFA_BOYUTU),
    ).fetchall()
    return Sayfa([_satir(r) for r in satirlar], toplam, gecerli, sayfa_sayisi)


def ara(
    conn: sqlite3.Connection,
    *,
    parcalar: Sequence[str],
    tur: str | None,
    ana_sinif: str | None,
    sayfa: int,
) -> Sayfa:
    """Arama: her parça `arama` anahtarında AND ile aranır (§5.3); kaynak adına göre sıralı.

    `parcalar` çağıran tarafından `search_key` ile AYNI katlamadan geçirilmiştir.
    """
    kosullar: list[str] = []
    degerler: list[object] = []
    for parca in parcalar:
        kosullar.append("arama LIKE ? ESCAPE '\\'")
        degerler.append(f"%{like_kacir(parca)}%")
    if tur is not None:
        kosullar.append("tur = ?")
        degerler.append(tur)
    if ana_sinif is not None:
        kosullar.append("ana_sinif = ?")
        degerler.append(ana_sinif)
    return _sayfali(conn, kosullar=kosullar, degerler=degerler, siralama="sira, id", sayfa=sayfa)


def harf_dizini(
    conn: sqlite3.Connection,
    *,
    sutun: str,
    harf_anahtari: str | None,
    diger_ust_siniri: str,
    sayfa: int,
) -> Sayfa:
    """Alfabetik dizin sayfası: `sutun` sıralama anahtarının ilk karakteri harfe eşit.

    `harf_anahtari` None ise "Diğer" sayfasıdır: anahtarı harf karakterlerinin
    en küçüğünden (`diger_ust_siniri`) önce gelen, boş olmayan adlar.
    """
    _sutun_dogrula(sutun)
    if harf_anahtari is None:
        kosullar = [f"{sutun} <> ''", f"{sutun} < ?"]
        degerler: list[object] = [diger_ust_siniri]
    else:
        kosullar = [f"substr({sutun}, 1, 1) = ?"]
        degerler = [harf_anahtari]
    return _sayfali(
        conn, kosullar=kosullar, degerler=degerler, siralama=f"{sutun}, sira, id", sayfa=sayfa
    )


def ilk_harf_sayilari(conn: sqlite3.Connection, *, sutun: str) -> dict[str, int]:
    """Sıralama anahtarının ilk karakteri → eser sayısı (harf çubuğunda boş harfler için)."""
    _sutun_dogrula(sutun)
    satirlar = conn.execute(
        f"SELECT substr({sutun}, 1, 1) AS ilk, count(*) AS adet FROM kd_katalog_eser "  # noqa: S608 — sütun sabit kümeden
        f"WHERE {sutun} <> '' GROUP BY ilk"
    ).fetchall()
    return {str(r["ilk"]): int(r["adet"]) for r in satirlar}


def ana_sinif_sayilari(conn: sqlite3.Connection) -> dict[str, int]:
    satirlar = conn.execute(
        "SELECT ana_sinif, count(*) AS adet FROM kd_katalog_eser GROUP BY ana_sinif"
    ).fetchall()
    return {str(r["ana_sinif"] or ""): int(r["adet"]) for r in satirlar}


def _sutun_dogrula(sutun: str) -> None:
    if sutun not in {eksen[0] for eksen in sabitler.EKSENLER.values()}:
        raise ValueError(f"Dizin sütunu sabit kümede değil: {sutun!r}")


def eser(conn: sqlite3.Connection, eser_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        f"SELECT {_ESER_SUTUNLARI} FROM kd_katalog_eser WHERE id = ?",  # noqa: S608 — sabit sütunlar
        (eser_id,),
    ).fetchone()
    return None if row is None else _satir(row)


def nushalar(conn: sqlite3.Connection, eser_id: int) -> list[dict[str, Any]]:
    satirlar = conn.execute(
        "SELECT durum, odunc_verilmez, bolum_adi FROM kd_katalog_nusha "
        "WHERE eser_id = ? ORDER BY id",
        (eser_id,),
    ).fetchall()
    return [_satir(r) for r in satirlar]


def yeni_gelenler(conn: sqlite3.Connection, *, adet: int = 10) -> list[dict[str, Any]]:
    """En son kayda giren nüshaların eserleri (`Copy.created_at`, §5.1), tekrarsız."""
    siralar = conn.execute(
        "SELECT eser_id FROM kd_katalog_nusha ORDER BY eklenme DESC, id DESC LIMIT ?",
        (adet * 20,),
    ).fetchall()
    idler = list(dict.fromkeys(int(r["eser_id"]) for r in siralar))[:adet]
    return _eserler_sirasiyla(conn, idler)


def cok_okunanlar(conn: sqlite3.Connection, *, adet: int = 10) -> list[dict[str, Any]]:
    """Son hesaplanan DÖNEM penceresinin sırası (sayı gösterilmez, yalnız sıra — §5.3)."""
    siralar = conn.execute(
        "SELECT p.eser_id AS eser_id FROM kd_katalog_populer AS p "
        "WHERE p.pencere_turu = 'DONEM' AND p.pencere = ("
        "  SELECT q.pencere FROM kd_katalog_populer AS q WHERE q.pencere_turu = 'DONEM' "
        "  ORDER BY q.hesaplanma DESC, q.pencere DESC LIMIT 1"
        ") ORDER BY p.sira LIMIT ?",
        (adet,),
    ).fetchall()
    return _eserler_sirasiyla(conn, [int(r["eser_id"]) for r in siralar])


def _eserler_sirasiyla(conn: sqlite3.Connection, idler: Sequence[int]) -> list[dict[str, Any]]:
    """Kimlik listesindeki eserler, listedeki sırayla (görünmeyen eser düşer)."""
    if not idler:
        return []
    yer_tutucular = ", ".join("?" for _ in idler)
    satirlar = conn.execute(
        f"SELECT {_ESER_SUTUNLARI} FROM kd_katalog_eser WHERE id IN ({yer_tutucular})",  # noqa: S608 — yer tutucular
        tuple(idler),
    ).fetchall()
    bulunan = {int(r["id"]): _satir(r) for r in satirlar}
    return [bulunan[i] for i in idler if i in bulunan]
