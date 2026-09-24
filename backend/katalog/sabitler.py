"""Ağ Kataloğunun sabit kümeleri ve kullanıcı metinleri (tasarım §5.3, §5.4; sözlük).

Katalog `apps.*` modüllerini içe aktaramaz (§4.1 değişmezi), bu yüzden
kaynak türü ve nüsha durumu adları burada DA yazılıdır. Tek kaynak yine
modeldir: `katalog/tests/test_sabitler.py` buradaki kod ve adları
`ResourceType` ve `CopyStatus` seçenekleriyle birebir karşılaştırır — sözlük
(`docs/sozluk.md`) değişince iki yer birlikte değişir, test bunu zorlar.

Sorgu parametreleri SABİT KÜMEDİR (§5.3): `tur` bu modüldeki kısa adlardan,
`konu` DOS ana sınıf hanesinden (0-9), harf dizinleri `HARFLER`'den biri
olmak zorundadır; başka değer 404 alır.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

#: Sayfa başına sonuç (§5.3).
SAYFA_BOYUTU: Final = 20
#: Sayfa numarasının üst sınırı (§5.3: `1..min(ceil(toplam/20), 500)`).
EN_COK_SAYFA: Final = 500
#: Arama metninin üst sınırı (karakter, §5.3). Fazlası kırpılır.
EN_UZUN_ARAMA: Final = 100

#: `?tur=` kısa adı → `Work.resource_type` kodu (adres çubuğunda Türkçe, ASCII).
TURLER: Final = MappingProxyType(
    {
        "kitap": "BOOK",
        "sureli-yayin": "PERIODICAL",
        "gorsel-isitsel": "AV_MATERIAL",
        "e-kitap": "EBOOK",
        "e-veri-tabani": "EDATABASE",
    }
)
#: Kaynak türü kodu → kullanıcı adı (sözlük: "kaynak türü"; `ResourceType` ile birebir).
TUR_ADLARI: Final = MappingProxyType(
    {
        "BOOK": "Kitap",
        "PERIODICAL": "Süreli yayın",
        "AV_MATERIAL": "Görsel-işitsel materyal",
        "EBOOK": "E-kitap",
        "EDATABASE": "E-veri tabanı",
    }
)
#: Dijital kaynak türleri: nüshası yoktur, künye olarak listelenir (§5.1).
DIJITAL_TURLER: Final = frozenset({"EBOOK", "EDATABASE"})

#: Katalogda görünen nüsha durumları → kullanıcı adı (sözlük; `CopyStatus` ile birebir).
#: Görünmeyen durumlar (kayıp, kayıttan düşülmüş, devredilmiş) burada YOKTUR.
DURUM_ADLARI: Final = MappingProxyType(
    {
        "AVAILABLE": "Rafta",
        "ON_LOAN": "Ödünçte",
        "DELIVERED": "Sınıf kitaplığında",
        "IN_REPAIR": "Onarımda",
    }
)
#: Danışma kaynağının hâli — durum DEĞİLDİR, `is_reference`'tan türer (sözlük).
ODUNC_VERILMEZ: Final = "Ödünç verilmez — kütüphanede okunur"

#: Dewey Onlu Sınıflama (DOS) ana sınıfları: hane → ad.
ANA_SINIFLAR: Final = MappingProxyType(
    {
        "0": "000 Genel Konular",
        "1": "100 Felsefe ve Psikoloji",
        "2": "200 Din",
        "3": "300 Toplum Bilimleri",
        "4": "400 Dil ve Dil Bilimi",
        "5": "500 Doğa Bilimleri ve Matematik",
        "6": "600 Teknoloji (Uygulamalı Bilimler)",
        "7": "700 Güzel Sanatlar",
        "8": "800 Edebiyat",
        "9": "900 Coğrafya ve Tarih",
    }
)

#: Alfabetik dizin harfleri: Türk alfabesi + künyede sık geçen Q, W, X
#: (Türk alfabesi sırasında, `tr_sort_key` ile aynı yerlerinde).
HARFLER: Final[tuple[str, ...]] = tuple("ABCÇDEFGĞHIİJKLMNOÖPQRSŞTUÜVWXYZ")
#: Harfle başlamayan adların (rakam, noktalama) dizin sayfası.
DIGER: Final = "diger"
DIGER_ADI: Final = "Diğer"

#: Dizin eksenleri (Md. 11/1: kaynak adı, yazar adı, konu) → (yol, görünüm sütunu, başlık).
EKSENLER: Final = MappingProxyType(
    {
        "eserler": ("sira", "Kaynak Adı Dizini"),
        "yazarlar": ("yazar_sira", "Yazar Dizini"),
        "konular": ("konu_sira", "Konu Dizini"),
    }
)
