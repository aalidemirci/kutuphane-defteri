"""ISBN normalleştirme, ISBN-10 → ISBN-13 çevrimi ve sağlama denetimi (tasarım §6.2, F2).

Saf fonksiyonlardır (DB'siz, yan etkisiz). `Work.isbn` kullanıcının YAZDIĞI
numarayı olduğu gibi tutar; `Work.isbn13` bu modülün ürettiği normalleştirilmiş
13 haneli biçimdir ve arama ile eşleştirme onun üzerinden yapılır.

**Sağlama hatası kaydı ENGELLEMEZ** (tasarım §6.2, F2 sözleşmesi §3): saha
verisi bozuktur — eski kitapların künye sayfasındaki numara yanlış basılmış
olabilir, Excel dosyasında rakam düşmüş olabilir. Program numarayı kaydeder ve
`isbn_warning()` ile uyarı döndürür; uyarı önizlemede ve eser formunda görünür.
Aynı ISBN'li birden çok eser olabilir (teklik kısıtı YOKTUR).

**978/979 ayrımı** (§7.1): masadaki okuyucuya kitabın arka kapağındaki ISBN
barkodu okutulduğunda program bunu tanır ve özel ileti verir. Kütüphane etiketi
10 hanedir ve yıl ile başlar; ISBN barkodu 13 hanedir ve 978/979 ile başlar —
uzunluk ve ön ek iki türü ayırır.
"""

from __future__ import annotations

#: ISBN-13 numaralarının EAN ön ekleri (Bookland). Barkod ayrımının dayanağı.
ISBN13_PREFIXES: tuple[str, ...] = ("978", "979")

ISBN10_LENGTH = 10
ISBN13_LENGTH = 13

#: Okuyucuya ya da forma gösterilen uyarılar (docs/sozluk.md diline uyar).
WARNING_LENGTH = (
    "ISBN 10 ya da 13 haneli olmalıdır. Numara olduğu gibi kaydedildi; "
    "kitabın künye sayfasından denetleyin."
)
WARNING_CHECKSUM = (
    "ISBN'in son hanesi (sağlama hanesi) tutmuyor. Numara olduğu gibi kaydedildi; "
    "kitabın künye sayfasından denetleyin."
)
WARNING_PREFIX = (
    "13 haneli ISBN numaraları 978 ya da 979 ile başlar. Numara olduğu gibi kaydedildi; "
    "kitabın künye sayfasından denetleyin."
)
WARNING_X_PLACEMENT = (
    "ISBN'de “X” yalnız 10 haneli numaranın SON hanesinde bulunabilir. Numara olduğu gibi "
    "kaydedildi ama 13 haneli biçime çevrilemedi: bu eser 13 haneli numarayla aranamaz. "
    "Kitabın künye sayfasından denetleyin."
)

_DIGITS = frozenset("0123456789")


def normalize_isbn(value: object) -> str:
    """Ham ISBN'i sadeleştirir: rakam ve sağlama harfi 'X' dışındaki her şey atılır.

    Tire, boşluk, nokta ve "ISBN" ön eki elenir. Küçük 'x' büyütülürken çıplak
    `.upper()` KULLANILMAZ (CLAUDE.md §2-9): tek karakter eşlemesiyle yapılır,
    Türkçe metne uygulanma riski doğmasın.
    """
    if value is None:
        return ""
    out: list[str] = []
    for ch in str(value):
        if ch in _DIGITS:
            out.append(ch)
        elif ch in ("x", "X"):
            out.append("X")
    return "".join(out)


def isbn10_check_digit(body: str) -> str:
    """ISBN-10'un sağlama hanesi (ilk 9 rakamdan; 10 değeri 'X' basılır)."""
    total = sum((index + 1) * int(ch) for index, ch in enumerate(body[:9]))
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def isbn13_check_digit(body: str) -> str:
    """ISBN-13'ün sağlama hanesi (ilk 12 rakamdan; 1-3-1-3 ağırlıklı mod 10)."""
    total = sum(int(ch) * (3 if index % 2 else 1) for index, ch in enumerate(body[:12]))
    return str((10 - total % 10) % 10)


def is_isbn10_shaped(value: str) -> bool:
    """Normalleştirilmiş numara ISBN-10 BİÇİMİNDE mi? (9 rakam + rakam ya da 'X')

    Biçim, sağlamadan AYRI sorudur: 'X' yalnız sağlama hanesinde bulunabilir,
    ortasında 'X' taşıyan bir numaranın sağlaması hiç hesaplanamaz. İkisi tek
    `False`'a katlanırsa kullanıcıya "son hane tutmuyor" denir — oysa sorun
    numaranın biçimidir ve 13 haneye çevrilemediği söylenmemiş olur.
    """
    return len(value) == ISBN10_LENGTH and value[:9].isdigit()


def is_valid_isbn10(value: str) -> bool:
    """Normalleştirilmiş 10 haneli numaranın sağlaması tutuyor mu?"""
    if not is_isbn10_shaped(value):
        return False
    return value[9] == isbn10_check_digit(value)


def is_valid_isbn13(value: str) -> bool:
    """Normalleştirilmiş 13 haneli numaranın sağlaması tutuyor mu?"""
    if len(value) != ISBN13_LENGTH or not value.isdigit():
        return False
    return value[12] == isbn13_check_digit(value)


def isbn10_to_13(value: str) -> str:
    """ISBN-10 → ISBN-13 ('978' ön eki + ilk 9 rakam + yeni sağlama); çözülemezse ''.

    Kaynak numaranın sağlaması TUTMASA DA çevrilir: sağlama uyarısı ayrı kanaldır
    (`isbn_warning`), çevrim onu beklemez.
    """
    if not is_isbn10_shaped(value):
        return ""
    body = "978" + value[:9]
    return body + isbn13_check_digit(body)


def to_isbn13(value: object) -> str:
    """Ham ISBN → 13 haneli normal biçim; 10/13 hane dışında ya da bozuksa ''.

    Normalleştirilmiş numara zaten 13 haneliyse (sağlaması tutmasa da) olduğu gibi
    döner: bozuk sağlama kaydı engellemez, yalnız uyarı doğurur.
    """
    digits = normalize_isbn(value)
    if len(digits) == ISBN13_LENGTH and digits.isdigit():
        return digits
    if len(digits) == ISBN10_LENGTH:
        return isbn10_to_13(digits)
    return ""


def isbn_warning(value: object) -> str:
    """Kullanıcıya gösterilecek ISBN uyarısı; numara sağlamsa ya da boşsa ''.

    Sıra bilinçlidir: önce uzunluk (numara hiç okunamadı), sonra BİÇİM ('X'
    yanlış yerde), sonra ön ek, sonra sağlama. Tek bir uyarı gösterilir —
    kullanıcıyı üç satırla karşılamaz.
    """
    digits = normalize_isbn(value)
    if not digits:
        return ""
    if len(digits) == ISBN10_LENGTH:
        if not is_isbn10_shaped(digits):
            return WARNING_X_PLACEMENT
        return "" if is_valid_isbn10(digits) else WARNING_CHECKSUM
    if len(digits) == ISBN13_LENGTH:
        if not digits.isdigit():  # 13 hanenin içinde 'X' — uzunluk doğru, biçim değil
            return WARNING_X_PLACEMENT
        if not digits.startswith(ISBN13_PREFIXES):
            return WARNING_PREFIX
        return "" if is_valid_isbn13(digits) else WARNING_CHECKSUM
    return WARNING_LENGTH


def is_isbn_barcode(value: object) -> bool:
    """Okutulan kod kitabın ISBN barkodu mu? (13 hane + 978/979 — §7.1)

    Kütüphane etiketi 10 hanedir; bu yüzden uzunluk ve ön ek ayrımı yeterlidir.
    Sağlama hanesi DENETLENMEZ: bozuk basılmış bir ISBN barkodu da ISBN
    barkodudur, kullanıcıya aynı ileti gösterilir.
    """
    digits = normalize_isbn(value)
    return len(digits) == ISBN13_LENGTH and digits.isdigit() and digits.startswith(ISBN13_PREFIXES)
