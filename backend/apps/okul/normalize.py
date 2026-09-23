"""Öğrenci içe aktarımı için saf (DB'siz) normalize ediciler.

KS'den alındı (KS bunu DD `apps/okul/normalize.py` dosyasından sadeleştirmişti):
TCKN/telefon/doğum tarihi/cinsiyet normalize edicileri YOKTUR — program bu
verileri hiç toplamaz (tasarım §6.1). Sınıf/şube ayrıştırması seviye kümesiyle
PARAMETRİKTİR; varsayılan küme okul içi sabittir (`GRADE_LEVELS`).

Okul numarasının kör indeks normalleştirmesi (`normalize_student_number`) de
buradadır: yazma (`Student.save`) ve arama (`selectors`) aynı kuralı kullanır.

Saf fonksiyonlardır — kolay test edilir (tests/test_normalize). DB eşleştirme
ve yazma `services/imports.py`'dadır.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection

from shared.text import tr_upper as _tr_upper

#: Okulda geçerli sınıf seviyeleri — OKUL İÇİ SABİT (1-12: ilkokul, ortaokul,
#: lise). Ders çizelgesine ya da okul türüne bağlı DEĞİLDİR; kademeye göre
#: daraltma F1'de `SchoolConfig.kademe` ile gelir (tasarım §6.1).
GRADE_LEVELS: tuple[int, ...] = tuple(range(1, 13))

#: Hazırlık sınıfının seviye kodu (KS temsili: etiket 'Hz/A'). Yalnız
#: `SchoolConfig.has_prep_class` açıkken geçerli kümeye girer.
PREP_LEVEL = 0

# Türkçe karakter → ASCII büyük. YALNIZ anahtar kelime eşlemesi içindir
# ('HAZIRLIK' tanıma); şube harfine UYGULANMAZ — bkz. `_ascii_upper` / `tr_upper`.
_TR_UPPER_MAP = str.maketrans(
    {
        "ş": "S",
        "Ş": "S",
        "ı": "I",
        "İ": "I",
        "ğ": "G",
        "Ğ": "G",
        "ü": "U",
        "Ü": "U",
        "ö": "O",
        "Ö": "O",
        "ç": "C",
        "Ç": "C",
    }
)

#: Hazırlık sınıfını metinden tanıma deseni ('HAZIRLIK/A', 'HAZ A', 'HZ-B'…).
_PREP_RE = re.compile(r"\bHA?Z(IRLIK)?\b")


#: Şube harfi olabilecek karakterler (Türk alfabesi + ASCII).
_SECTION_CHARS = r"A-Za-zÇĞİÖŞÜçğıöşü"


def _ascii_upper(value: str) -> str:
    """Türkçe karakterleri ASCII'ye indirip büyük harfe çevirir (ANAHTAR KELİME eşlemesi).

    YALNIZ anahtar kelime araması içindir ('HAZIRLIK' tanıma gibi). Şube harfi
    için KULLANILMAZ: 'İ' ile 'I'yı tek harfe katlar — bkz. `tr_upper`.
    """
    return value.translate(_TR_UPPER_MAP).upper()


def tr_upper(value: str) -> str:
    """Türkçeye uygun büyük harf ('10/i' → '10/İ', '9/ş' → '9/Ş').

    ŞUBE HARFİ KATLAMASININ TEK DOĞRU YOLU BUDUR. `_ascii_upper` ile katlamak
    (30.08.2026 öncesi davranış) Türk alfabesinin ayrı harflerini birleştirir:
    e-Okul sınıf listesi şubeleri Türk alfabesi sırasıyla açar (…G, H, I, İ,
    J, K…), yani orta ölçekli bir okulda **hem 10/I hem 10/İ** bulunur. ASCII
    katlaması bu iki şubeyi tek şubeye çökertip iki ayrı sınıfın öğrencilerini
    sessizce aynı şubeye yazardı — gerçek bir e-Okul ihracında yakalandı.
    """
    return _tr_upper(value)  # tek uygulama: shared/text.py


#: Türk alfabesinin KENDİ harfleri: aksan ayıklamasından MUAFTIR. NFD ayrışması
#: 'İ'yi 'I' + birleşen noktaya, 'Ç'yi 'C'ye indirir; ayıklama bu harfleri
#: yutarsa Türkçenin AYRI harfleri tek harfe çöker — `tr_upper`'ın gerekçesinin
#: aynısı (10/I ile 10/İ iki ayrı şubedir).
_KORUNAN_HARFLER = frozenset("ÇĞIİÖŞÜçğıiöşü")

#: NFD ayrışmasının Türkçe için YANLIŞ ya da eksik sonuç verdiği harfler.
#: 'Î' ayrışınca NOKTASIZ 'I'ya iner; oysa düzeltme işaretli î Türkçede
#: NOKTALI i'dir ("millî", "Kâmil"). Ayrışmayan Latin harfleri (Ø, Æ, Ł…) da
#: elle eşlenir: ayıklama onlara dokunmaz, alfabe dışında kalırlardı.
_AKSAN_ISTISNALARI = {
    "Î": "İ",
    "Í": "İ",
    "Ì": "İ",
    "Ï": "İ",
    "Ĩ": "İ",
    "Ī": "İ",
    "Į": "İ",
    "Ø": "O",
    "Œ": "O",
    "Æ": "A",
    "Đ": "D",
    "Ð": "D",
    "Ł": "L",
    "Þ": "T",
    "ø": "o",
    "œ": "o",
    "æ": "a",
    "đ": "d",
    "ð": "d",
    "ł": "l",
    "þ": "t",
}

#: Karakter başına bir kez hesaplanan katlama (her kayıt ve her arama çağırır).
_AKSAN_ONBELLEGI: dict[str, str] = {}


def _harf_katla(ch: str) -> str:
    """Tek karakterin aksansız karşılığı; çözülemiyorsa karakterin kendisi."""
    if ch in _KORUNAN_HARFLER:
        return ch
    eslenik = _AKSAN_ISTISNALARI.get(ch)
    if eslenik is not None:
        return eslenik
    ayrisik = unicodedata.normalize("NFD", ch)
    temiz = "".join(parca for parca in ayrisik if not unicodedata.combining(parca))
    # Uzunluk 1:1 KALMALI: anahtar alanları girdiyle aynı boyda saklanır
    # (`Work.sort_key` 500 hane) ve Hangul gibi yazılar NFD'de birden çok
    # birleşmeyen parçaya ayrılır. Ayrışma tek harfe inmiyorsa dokunulmaz.
    return temiz if len(temiz) == 1 else ch


def fold_diacritics(value: object) -> str:
    """Düzeltme işaretli ve aksanlı Latin harflerini düz karşılığına indirir.

    'Kâmil' → 'Kamil', 'Rüzgâr' → 'Rüzgar', 'Émile' → 'Emile'. TÜRK ALFABESİNİN
    HARFLERİNE DOKUNMAZ: Ç/Ğ/I/İ/Ö/Ş/Ü olduğu gibi kalır, yani 'ılık' ile
    'ilik' ayrı kalmayı sürdürür (T7).

    Gerekçe iki yönlüdür: düzeltme işareti çoğu klavyede zahmetlidir, kullanıcı
    "rüzgar" yazar ama künye "Rüzgâr" girilmiştir (arama); ve 'Â' Türk
    alfabesinde bulunmadığı için sıralamada harflerin önüne düşerdi (sıralama).
    """
    metin = "" if value is None else str(value)
    sonuc: list[str] = []
    for ch in metin:
        katlanmis = _AKSAN_ONBELLEGI.get(ch)
        if katlanmis is None:
            katlanmis = _harf_katla(ch)
            _AKSAN_ONBELLEGI[ch] = katlanmis
        sonuc.append(katlanmis)
    return "".join(sonuc)


#: Türk alfabesi sırası — şube harfi artık katlanmadığı için sıralama da
#: Türkçeleşmek ZORUNDA: kod noktası sırasında Ç/Ğ/İ/Ö/Ş/Ü harfleri 'Z'den
#: BÜYÜKTÜR, yani '10/Ç' ile '10/İ' basılan evrakta listenin sonuna düşer ve
#: '10/I' ile '10/İ' iki uca ayrılırdı.
#:
#: Q/W/X Türk alfabesinde YOKTUR ama Türkçe metinde sıradandır: okul
#: kütüphanesinin İngilizce bölümü ("Wuthering Heights", "Quo Vadis") ve
#: yabancı yazar adları (Woolf, Wilde) bu harflerle başlar. Alfabe dışı
#: sayılsalardı 0 önceliğiyle listenin EN BAŞINA düşerlerdi; bu yüzden Latin
#: sırasındaki yerlerine konurlar (…P Q R… ve …V W X Y Z), ICU'nun Türkçe
#: sıralamasıyla aynı.
_TR_ALFABE = "0123456789ABCÇDEFGĞHIİJKLMNOÖPQRSŞTUÜVWXYZ"
_TR_SIRA = {harf: sira for sira, harf in enumerate(_TR_ALFABE)}


def tr_sort_key(value: object) -> tuple[tuple[int, int], ...]:
    """Türk alfabesine göre sıralama anahtarı ('C' < 'Ç' < 'D', 'I' < 'İ' < 'J').

    Yalnız şube harfi için değil, ÇOK KELİMELİ adlar için de kullanılabilir.
    Bu yüzden her karakter (öncelik, değer) ikilisine açılır: alfabe dışı
    karakterler (boşluk, '/', '-') 0 önceliğiyle harflerden ÖNCE gelir — ASCII
    sezgisiyle aynı ('A Blok' < 'AB Blok'), aksi hâlde ayraç
    sınırındaki adlar birbirine karışırdı. Karşılaştırma büyük harf üzerinden
    yapılır (`tr_upper`) ve aksanlar düz karşılıklarına katlanır
    (`fold_diacritics`): 'Kâmil' ile 'Kamil' yan yana sıralanır, alfabe dışına
    düşmez.
    """
    buyuk = fold_diacritics(tr_upper("" if value is None else str(value)))
    return tuple(
        (1, _TR_SIRA[ch]) if ch in _TR_SIRA else (0, ord(ch))  #
        for ch in buyuk
    )


def normalize_class_section(
    value: object, *, valid_levels: Collection[int] = GRADE_LEVELS
) -> tuple[int, str] | None:
    """'10/A', '10-A', '10 A' → (10, 'A'); küme dışı seviye veya çözümsüz → None.

    `valid_levels` okul yapılandırmasından gelir (`SchoolConfig.grade_levels`).
    0 (Hazırlık) kümede ise 'HAZIRLIK/A', 'HZ A' gibi metinler (0, 'A') çözülür.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    levels = frozenset(int(v) for v in valid_levels)
    folded = _ascii_upper(s)
    prep = _PREP_RE.search(folded) if PREP_LEVEL in levels else None
    if prep is not None:
        # Anahtar kelime KATLANMIŞ metinde bulunur, şube harfi HAM metinden
        # alınır — 'Hazırlık/İ' şubesi 'I'ya çökmesin (tr_upper gerekçesi).
        if len(folded) == len(s):  # translate+upper 1:1 kaldıysa konumlar eşleşir
            kalan = s[: prep.start()] + " " + s[prep.end() :]
        else:  # savunma dalı: katlama uzunluğu değiştirdiyse ASCII'ye düş
            kalan = _PREP_RE.sub(" ", folded)
        harfler = re.sub(rf"[^{_SECTION_CHARS}]", " ", kalan).split()
        if not harfler:
            return None
        return PREP_LEVEL, tr_upper(harfler[-1])
    level_m = re.search(r"\d{1,2}", s)
    section_m2 = re.search(rf"[{_SECTION_CHARS}]+", s)
    if level_m is None or section_m2 is None:
        return None
    level = int(level_m.group())
    if level not in levels:
        return None
    section = tr_upper(section_m2.group())
    return level, section


#: Yalnız ASCII rakam ('²' gibi Unicode basamaklar `str.isdigit()`'i geçer ama
#: okul numarası değildir).
_ASCII_DIGITS_RE = re.compile(r"[0-9]+")


def normalize_student_number(value: object) -> str:
    """Okul numarasının kör indeks biçimi (tasarım §6.3, T14): '0123' ≡ '123' ≡ ' 1 23 '.

    Kör indeks tam eşleşmedir; bu yüzden aynı numaranın farklı yazımları AYNI
    değere inmelidir. Kural bilinçli olarak dardır:

    - bütün boşluklar atılır (Excel'den kopyalamada araya giren boşluk dahil);
    - değer yalnız rakamsa baştaki sıfırlar atılır ('0123' → '123'; '000' → '0');
    - harf içeren numara olduğu gibi kalır (e-Okul numaraları rakamdır; başka
      biçimde tahmin yürütülmez).

    Excel'in '123.0' biçimi burada ÇÖZÜLMEZ: ayrıştırıcı (`excel_ogrenci._str`)
    onu zaten '123'e indirir; iki yerde çözmek iki ayrı kural doğururdu.
    Yazmada (`Student.save`) ve aramada (`selectors`) aynı fonksiyon çağrılır.
    """
    if value is None:
        return ""
    sade = "".join(str(value).split())
    if _ASCII_DIGITS_RE.fullmatch(sade):
        return sade.lstrip("0") or "0"
    return sade


def split_full_name(value: object) -> tuple[str, str]:
    """'EMRE CAN YILMAZ' → ('EMRE CAN', 'YILMAZ'); tek kelime → (kelime, '').

    Son kelime soyad kabul edilir. Title Case uygulanmaz — ham bırakılır
    (görüntü biçimi sistemin başka katmanında uygulanır; TR büyük harf tuzağı).
    """
    if value is None:
        return "", ""
    parts = str(value).split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]
