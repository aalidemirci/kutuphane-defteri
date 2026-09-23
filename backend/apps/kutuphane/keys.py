"""Türkçe arama ve sıralama anahtarları + yer numarası üretimi (T7, D2, D11).

**Sorun** (CLAUDE.md §2-8, tasarım §13 D2). SQLite'ın `LIKE`'ı ve BINARY
sıralaması Türkçe harflerde çalışmaz: "ŞİİR" ile "şiir" eşleşmez, Ç/Ğ/İ/Ö/Ş/Ü
kod noktası sırasında 'Z'den sonra gelir, 'I' ile 'İ' iki uca düşer. Kullanıcıya
gösterilen her liste ve her arama bu yüzden ham alanla değil, bu modülün
ürettiği ANAHTAR alanlarla çalışır.

**Tek katlama kaynağı.** Yeni bir katlama kuralı YAZILMAZ: büyük harfe çevirme
`shared.text.tr_upper`, aksan katlaması `apps.okul.normalize.fold_diacritics`,
alfabe sırası `apps.okul.normalize.tr_sort_key`. Bu modül yalnız o kuralların
DB'de saklanabilir bir dizgeye dönüşmüş hâlidir.

**Sıralama anahtarı neden dizge?** `tr_sort_key` Python sıralaması için demet
döndürür; DB `order_by` demeti göremez. `tr_collation_key` aynı sıralamayı
karakter karakter dizgeye çevirir: alfabedeki her harf, alfabe sırasına göre
özel kullanım alanındaki (U+E000…) bir karaktere eşlenir; alfabe dışı
karakterler (boşluk, '/', '-', rakam) olduğu gibi kalır ve kod noktaları
U+E000'in altında olduğu için harflerden ÖNCE gelir — `tr_sort_key`'in
(öncelik, değer) demetiyle birebir aynı sıra. SQLite TEXT karşılaştırması
UTF-8 bayt sırasıdır, o da kod noktası sırasıyla aynıdır; yani `ORDER BY
sort_key` Türk alfabesi sırasını verir.

Q/W/X Türk alfabesinde yoktur ama Türkçe künyede sıradandır ("Wuthering
Heights", Woolf); `tr_sort_key` onları Latin sırasındaki yerlerine koyar.
Düzeltme işaretli ve aksanlı harfler ('Kâmil', 'Émile') düz karşılıklarına
katlanır: 'Kâmil' ile 'Kamil' yan yana sıralanır (eşit anahtar; sıra `pk` ile
kararlıdır).

Bilinen sapmalar: (1) kod noktası U+E000'den büyük alfabe dışı karakterler
(emoji gibi) tek bir karaktere (U+D7FF) katlanır ve kendi aralarında sıra
kaybeder; (2) Latin DIŞI yazılar (Yunan, Kiril, Arap) alfabe dışı sayılır ve
harflerden önce sıralanır. İkisi de eser adında beklenmez; harflerin sırasını
bozmamak için bilinçli seçimdir.

**Arama anahtarı.** `fold_search` metni büyük harfe çevirir ve harf/rakam
dışındaki her şeyi tek boşluğa indirir. Aynı işlev hem yazmada (anahtar alanı)
hem okumada (kullanıcının sorgusu) çağrılır — kapı budur: sorgu da anahtarla
aynı katlamadan geçmezse arama sessizce boş döner.
"""

from __future__ import annotations

import re

from apps.kutuphane import isbn as isbn_module
from apps.okul.normalize import fold_diacritics, split_full_name, tr_sort_key
from shared.text import tr_upper

#: Alfabe harflerinin eşlendiği özel kullanım alanının başı (U+E000).
_LETTER_BASE = 0xE000
#: Alfabe dışı ama U+E000'den büyük karakterlerin katlandığı karakter (geçerli,
#: vekil (surrogate) olmayan en büyük kod noktalarından biri).
_OTHER_CEILING = 0xD7FF

#: "Konu" alanında birden çok konuyu ayıran işaretler (katalog Excel sözlüğüyle
#: aynı kural — `import_schema` aynı ayraçları kullanır).
SUBJECT_SEPARATORS = re.compile(r"[,;]")
#: Çoklu yazar ayracı: sözlükteki yazım "Ad Soyad, Ad Soyad".
AUTHOR_SEPARATORS = re.compile(r"[,;]")

#: Yer numarasına giren yazar kısaltmasının uzunluğu (sırt etiketi geleneği).
CALL_NUMBER_AUTHOR_LETTERS = 3


def tr_collation_key(value: object) -> str:
    """Türk alfabesi sırasını koruyan, DB'de `order_by` ile kullanılabilir anahtar.

    Uzunluk girdiyle birebir aynıdır (karakter başına bir karakter), bu yüzden
    500 karakterlik bir alan 500 karakterlik anahtar üretir.
    """
    return "".join(
        chr(_LETTER_BASE + deger) if oncelik else chr(min(deger, _OTHER_CEILING))
        for oncelik, deger in tr_sort_key("" if value is None else str(value))
    )


def fold_search(value: object) -> str:
    """Arama katlaması: Türkçe-güvenli büyük harf + aksan katlaması + harf/rakam dışı → boşluk.

    Hem `search_key` üretiminde hem kullanıcı sorgusunda çağrılır. Küçük/büyük
    harf farkı ('şiir'/'ŞİİR'), noktalama farkı ('Madonna,'/'Madonna') ve
    düzeltme işareti farkı ('Rüzgâr'/'rüzgar', 'Kâmil'/'Kamil') burada erir;
    'I' ile 'İ' AYRI kalır (tr_upper: 'i' → 'İ', 'ı' → 'I').

    Düzeltme işareti neden katlanır: çoğu klavyede 'â' yazmak zahmetlidir,
    kullanıcı "rüzgar" arar; künye ise Excel'den ya da kitabın künye
    sayfasından "Rüzgâr" girilmiştir. Katlama olmadan kayıt aramayla hiç
    bulunmaz ve kullanıcı aynı eseri ikinci kez kataloglar. SQLite'ın `LIKE`'ı
    yalnız ASCII harflerde katlama yapar, yani 'Â' ile 'A' başka hiçbir
    katmanda eşleşmez.
    """
    metin = fold_diacritics(tr_upper("" if value is None else str(value)))
    parcalar: list[str] = []
    bosluk = True
    for ch in metin:
        if ch.isalnum():
            parcalar.append(ch)
            bosluk = False
        elif not bosluk:
            parcalar.append(" ")
            bosluk = True
    return "".join(parcalar).strip()


def first_of(value: object, separators: re.Pattern[str]) -> str:
    """Ayraçlı listenin ilk öğesi (boşlukları kırpılmış); liste boşsa ''."""
    metin = "" if value is None else str(value)
    for parca in separators.split(metin):
        kirpik = parca.strip()
        if kirpik:
            return kirpik
    return ""


def first_author(authors: object) -> str:
    """Yazar listesinin ilk adı ('Sabahattin Ali, Yaşar Kemal' → 'Sabahattin Ali')."""
    return first_of(authors, AUTHOR_SEPARATORS)


def author_surname(authors: object) -> str:
    """İlk yazarın soyadı — sezgi: SON sözcük (D11, sözlük "Ad Soyad" sırası).

    Çok sözcüklü soyadlarda ('Ahmet Hamdi Tanpınar' doğru, 'Halide Edip Adıvar'
    doğru, ama 'Mehmet Akif Ersoy Yılmazoğlu' gibi bileşik soyadlar) sezgi
    yanılabilir; bu yüzden ürettiği tek alan (`Work.call_number`) ELLE
    DEĞİŞTİRİLEBİLİR bırakılmıştır.
    """
    _ad, soyad = split_full_name(first_author(authors))
    if soyad:
        return soyad
    return first_author(authors)


def author_sort_name(authors: object) -> str:
    """Yazar sıralamasının kaynağı: 'Sabahattin Ali' → 'Ali Sabahattin'.

    Katalogda yazar ekseni SOYADA göre sıralanır (Md. 11/1 yazar adı ekseni);
    soyad sezgisi `author_surname` ile AYNI tek kaynaktan gelir, yani yer
    numarasıyla sıralama aynı soyadı görür.
    """
    ad, soyad = split_full_name(first_author(authors))
    if not soyad:
        return ad
    return f"{soyad} {ad}".strip()


def first_subject(subjects: object) -> str:
    """Konu listesinin ilk öğesi (konu ekseni sıralamasının kaynağı)."""
    return first_of(subjects, SUBJECT_SEPARATORS)


def work_search_key(
    *,
    title: object = "",
    authors: object = "",
    subjects: object = "",
    isbn: object = "",
    isbn13: object = "",
) -> str:
    """Eserin arama anahtarı: ad + yazar + konu + ISBN, katlanmış ve birleştirilmiş.

    ISBN iki biçimiyle de girer (kullanıcının yazdığı normalleştirilmiş hâli ve
    13 haneli karşılığı): okul, elindeki 10 haneli numarayla da arama yapabilsin.
    """
    parcalar: list[str] = [
        fold_search(title),
        fold_search(authors),
        fold_search(subjects),
        isbn_module.normalize_isbn(isbn),
        str(isbn13 or ""),
    ]
    return " ".join(parca for parca in dict.fromkeys(parcalar) if parca)


def search_terms(query: object) -> list[str]:
    """Kullanıcı sorgusunu arama anahtarında aranacak parçalara böler.

    Sözcükler AYRI parçalardır ve hepsi birden aranır ("kürk madonna" → iki
    parça): kullanıcı sözcük sırasını hatırlamak zorunda kalmaz. ISBN gibi
    görünen (en az 10 rakam taşıyan, rakam/tire/X'ten ibaret) parçalar
    rakamlarına indirilir, böylece '978-605-...' yazımı da eşleşir.
    """
    parcalar: list[str] = []
    for ham in str(query or "").split():
        rakamlar = isbn_module.normalize_isbn(ham)
        if len(rakamlar) >= isbn_module.ISBN10_LENGTH and _is_isbn_shaped(ham):
            parcalar.append(rakamlar)
            continue
        katlanmis = fold_search(ham)
        if katlanmis:
            parcalar.append(katlanmis)
    return list(dict.fromkeys(parcalar))


def _is_isbn_shaped(token: str) -> bool:
    """Parça yalnız rakam, tire, nokta, boşluk ve 'X' taşıyor mu? (ISBN yazımı)"""
    return all(ch.isascii() and (ch.isdigit() or ch in "-.xX") for ch in token)


def build_call_number(classification_code: object, authors: object) -> str:
    """Yer numarası: sınıflama kodu + yazar soyadının ilk üç harfi ('813.54 STE').

    Büyük harfe çevirme `tr_upper` iledir (D11): çıplak `.upper()` 'i' harfini
    'I' basar ve 'İnce' soyadı 'INC' olurdu. Sırt etiketinde aynı eserin bütün
    nüshaları aynı yer numarasını taşır; alan elle değiştirilebilir.
    """
    kod = str(classification_code or "").strip()
    soyad = author_surname(authors)
    kisaltma = tr_upper(soyad)[:CALL_NUMBER_AUTHOR_LETTERS] if soyad else ""
    return " ".join(parca for parca in (kod, kisaltma) if parca)
