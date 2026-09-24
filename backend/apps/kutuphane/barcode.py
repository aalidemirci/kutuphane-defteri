"""Nüsha barkodu ve kayıt no biçimi; okutulan kodun türünün ayrımı (tasarım §7.1).

Şema (§7.1, docs/sozluk.md):

| | Biçim | Örnek |
|---|---|---|
| Nüsha | 10 hane: `YYYY` + 6 hane sıra | `2026000123`, basılı `2026-000123` |
| Üye kartı | 8 hane: `9` + 6 rastgele + 1 sağlama | `94718263` |
| Kitabın ISBN barkodu | 13 hane, 978/979 | — (`apps.kutuphane.isbn`) |

Uzunluk ve ön ek üç türü ayırır; bu yüzden masadaki okuyucuya ne okutulursa
okutulsun program ne gördüğünü bilir ve kullanıcıya doğru iletiyi verir.

**Kayıt no barkodun sayı hâlidir** (sözlük: `Copy.accession_no` "kayıt no",
`Copy.barcode` "barkod"): `int("2026000123") == 2026000123`. İki alan da TEK
sayaçtan (`CopyCounter`) doğar ve **asla yeniden kullanılmaz** — silinen
nüshanın numarası başka nüshaya verilmez (düz `unique`, kısmi değil).

Salt rakam olması bilinçlidir (T8): TR-Q klavyede okuyucunun "-" karakteri "*"
olur, harfli kodlarda ı/i karışır. `shared/barcode128.py` Code128-C ile basar;
C alt kümesi **çift** uzunluk ister, 10 hane bu şartı sağlar (F4).
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from apps.kutuphane import isbn as isbn_module

#: Nüsha barkodunun uzunluğu (4 hane yıl + 6 hane sıra).
BARCODE_LENGTH = 10
#: Yıl içindeki sıra numarasının hane sayısı.
SEQUENCE_DIGITS = 6
#: Bir yılda üretilebilecek en büyük sıra numarası.
MAX_SEQUENCE = 10**SEQUENCE_DIGITS - 1
#: Üye kartı numarasının uzunluğu ve ön eki (F6'da üretilir; burada yalnız ayrım).
MEMBER_CARD_LENGTH = 8
MEMBER_CARD_PREFIX = "9"

#: Nüsha barkodunun YIL ön ekinin okutmada makul sayıldığı aralık. Sayaç yılı
#: `timezone.localdate().year`'dır, yani program bu yüzyılın numaralarını
#: üretir; elle yazılan 10 haneli bir ISBN-10'un ilk dört hanesi ise yayıncı
#: grubudur ("0975…", "3540…", "9752…") ve bu aralığın dışına düşer. Ayrım
#: `isbn.py` docstring'inin dayanağıdır ("kütüphane etiketi yıl ile başlar").
SCAN_YEAR_MIN = 2000
SCAN_YEAR_MAX = 2999

#: Okuyucuya ISBN barkodu okutulduğunda gösterilen ileti (§7.1, sözlük).
ISBN_SCAN_MESSAGE = "Bu ISBN barkodu. Kitabın kütüphane etiketini okutun."


class ScanKind(StrEnum):
    """Okutulan ya da elle yazılan kodun türü.

    `RESERVED` (F4, yöntem B): biçimce nüsha barkodudur ama numara bir boş
    barkod aralığında AYRILMIŞ, henüz hiçbir nüshaya BAĞLANMAMIŞ ve İPTAL
    EDİLMEMİŞTİR. Dolaşım masası (F6) buna "bu etiket henüz bir kitaba
    bağlanmadı" der. `CANCELLED`: ayrılmış ama İPTAL EDİLMİŞ numara — bir daha
    hiçbir kitaba bağlanamaz; etiket kitaptan sökülür. İkisi de salt biçimden
    anlaşılamaz; `classify_scan`'e verilen sorgu işleviyle ayrılır.
    """

    COPY = "COPY"
    RESERVED = "RESERVED"
    CANCELLED = "CANCELLED"
    MEMBER_CARD = "MEMBER_CARD"
    ISBN = "ISBN"
    UNKNOWN = "UNKNOWN"


class BarcodeRangeError(ValueError):
    """Yıl ya da sıra numarası şemanın dışına taştı (sayaç tükendi)."""


def build_barcode(year: int, sequence: int) -> str:
    """(yıl, sıra) → 10 haneli barkod. Taşmada `BarcodeRangeError`.

    Yıl dört haneyle sınırlıdır; sıra 1-999999 arasındadır. Sınırın aşılması
    sessiz bir çakışma değil, açık bir hata olmalıdır: barkod tekil kalmalı.
    """
    if not 1000 <= year <= 9999:
        raise BarcodeRangeError("Barkod yılı dört haneli olmalıdır.")
    if not 1 <= sequence <= MAX_SEQUENCE:
        raise BarcodeRangeError(
            f"Bir yılda en çok {MAX_SEQUENCE} nüsha numarası üretilebilir; sayaç doldu."
        )
    return f"{year:04d}{sequence:0{SEQUENCE_DIGITS}d}"


def accession_no_of(barcode: str) -> int:
    """Barkodun sayı hâli (kayıt no). '2026000123' → 2026000123."""
    return int(barcode)


def format_barcode(barcode: str) -> str:
    """Basılı ve ekranda gösterilen biçim: '2026000123' → '2026-000123'.

    Biçimlendirme YALNIZ görüntüdür: saklanan, aranan ve okutulan değer
    rakamlardan ibarettir.
    """
    digits = normalize_scan(barcode)
    if len(digits) != BARCODE_LENGTH:
        return barcode
    return f"{digits[:4]}-{digits[4:]}"


def normalize_scan(value: object) -> str:
    """Okuyucu ya da klavye girdisini sadeleştirir: rakam dışındaki her şey atılır.

    Okuyucular sonuna Enter, bazı modeller araya boşluk ya da tire koyar; kullanıcı
    basılı biçimi ('2026-000123') elle de yazabilir. Aynı yardımcının bir eşi ön
    yüzde bulunur (§7.1).
    """
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if ch.isascii() and ch.isdigit())


def has_scan_year_prefix(digits: str) -> bool:
    """10 haneli kodun ilk dört hanesi makul bir barkod yılı mı? (`SCAN_YEAR_*`)"""
    if len(digits) != BARCODE_LENGTH or not digits.isdigit():
        return False
    return SCAN_YEAR_MIN <= int(digits[:4]) <= SCAN_YEAR_MAX


def classify_scan(
    value: object, *, reservation_kind: Callable[[str], ScanKind | None] | None = None
) -> ScanKind:
    """Okutulan kodun türünü söyler (§7.1).

    **Ayrılmış numara** (F4): `reservation_kind` verilirse, biçimce nüsha
    barkodu olan kod ona sorulur; bağlanmamış ayrılmış numarada `RESERVED` ya da
    `CANCELLED`, değilse `None` döner. İşlev veritabanına bakan çağırandan gelir
    (`services.barcode_reservations`) — bu modül saf kalır ve ön yüzdeki eşi
    (`tarama.ts`) gibi yalnız biçime bakar. Verilmezse davranış F2'deki gibidir.

    ISBN barkodu ayrımı `apps.kutuphane.isbn` ile yapılır — 978/979 kuralının
    tek kaynağı orasıdır. Tanınmayan kod `UNKNOWN` döner; masa ekranı (F6) buna
    göre ileti verir.

    **10 hane neden tek başına yetmez.** Kullanıcı kitabın künye sayfasındaki
    eski ISBN-10'u kutuya ELLE yazabilir; o da 10 hanedir ve nüsha barkodundan
    yalnız yıl ön ekiyle ayrılır (`SCAN_YEAR_MIN`…`SCAN_YEAR_MAX`). Yıl gibi
    görünmeyen 10 haneli bir numara sağlaması tutuyorsa ISBN-10 sayılır ve
    kullanıcı "nüsha bulunamadı" yerine doğru iletiyi görür.

    **Kabul edilen kalan belirsizlik (TB22):** ilk dört hanesi 2000-2999
    aralığına düşen ISBN-10'lar (Fransızca grup, "20…") nüsha barkodundan
    ayrılamaz; `SCAN_YEAR_MAX = 2999` üst duvarı da bir varsayımdır. Salt
    rakamdan oluşan 10 haneli iki şema arasında bu kaçınılmazdır; ISBN-10
    zaten 2007'den beri basılmıyor ve okulun elindeki numaralar 13 hanelidir.
    Kütükteki kalem: `docs/teknik-borc.md` TB22.
    """
    digits = normalize_scan(value)
    if len(digits) == BARCODE_LENGTH:
        if has_scan_year_prefix(digits):
            ayrilmis = reservation_kind(digits) if reservation_kind is not None else None
            return ayrilmis if ayrilmis is not None else ScanKind.COPY
        return ScanKind.ISBN if isbn_module.is_valid_isbn10(digits) else ScanKind.UNKNOWN
    if len(digits) == MEMBER_CARD_LENGTH and digits.startswith(MEMBER_CARD_PREFIX):
        return ScanKind.MEMBER_CARD
    if isbn_module.is_isbn_barcode(digits):
        return ScanKind.ISBN
    return ScanKind.UNKNOWN
