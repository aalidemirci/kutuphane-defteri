"""Sentetik katalog dosyası üreteci (testler için) — depoya büyük dosya girmez.

Ölçüm kapısı 10.000 satırlık bir dosya ister (tasarım §14.1 F3). O dosya depoya
KONMAZ: burada çalışma anında üretilir. İki gerekçe: ikili dosyalar depoyu
şişirir ve `packaging/depo_sizintisi.py`'nin denetlediği "veri biçimi" taramasını
gereksiz yere meşgul eder (CLAUDE.md §2-12).

**Veriler uydurmadır ve kişisel veri taşımaz:** eser adları kamu malı klasik
eserlerden, yazarlar çoktan ölmüş kişilerden alınmıştır (kitap künyesi kişisel
veri değildir — `tests/ortak.py` ile aynı kural). ISBN numaraları UYDURMADIR:
sağlama hanesi doğru hesaplanır ki program numarayı "bozuk" diye işaretlemesin,
ama gerçek bir kitaba ait değildir.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from io import BytesIO
from typing import Any

from openpyxl import Workbook

from apps.kutuphane import isbn as isbn_module
from apps.kutuphane.import_schema import CATALOG_SHEET, COLUMNS

#: Kamu malı eser adları (sentetik satırların künye çekirdeği).
KLASIKLER: tuple[tuple[str, str, str], ...] = (
    ("Kürk Mantolu Madonna", "Sabahattin Ali", "Türk edebiyatı, roman"),
    ("Çalıkuşu", "Reşat Nuri Güntekin", "Türk edebiyatı, roman"),
    ("Mai ve Siyah", "Halit Ziya Uşaklıgil", "Türk edebiyatı, roman"),
    ("Sinekli Bakkal", "Halide Edip Adıvar", "Türk edebiyatı, roman"),
    ("Safahat", "Mehmet Akif Ersoy", "Türk edebiyatı, şiir"),
    ("Huzur", "Ahmet Hamdi Tanpınar", "Türk edebiyatı, roman"),
    ("Telemak", "Fénelon", "Fransız edebiyatı, roman"),
    ("Suç ve Ceza", "Fyodor Dostoyevski", "Rus edebiyatı, roman"),
    ("Gurur ve Önyargı", "Jane Austen", "İngiliz edebiyatı, roman"),
    ("Kamus-ı Türkî", "Şemseddin Sami", "Türkçe, sözlük"),
)

#: Sentetik dosyanın kullandığı bölüm adları (kontrollü listeyle eşleşsin diye
#: testler bu bölümleri önceden açar ya da "yeni bölüm" kararıyla açtırır).
BOLUMLER: tuple[str, ...] = ("Edebiyat", "Tarih", "Danışma")

#: Uydurma ISBN'lerin ön eki (978 + Türkiye ülke kodu 605). Kalan altı hane sıra
#: numarasıdır: ölçüm dosyasındaki 10.000 satırın her biri AYRI numara alır —
#: numaralar tekrarlansaydı satırlar birbirini "şüpheli" yapar ve ölçüm gerçek
#: bir devir aktarımını taklit etmezdi.
_ISBN_PREFIX = "978605"
_ISBN_SERI_UZUNLUGU = 6


def sentetik_isbn(sira: int) -> str:
    """Sağlaması geçerli UYDURMA ISBN-13 (gerçek bir kitaba ait değildir)."""
    govde = f"{_ISBN_PREFIX}{sira % 10**_ISBN_SERI_UZUNLUGU:0{_ISBN_SERI_UZUNLUGU}d}"
    return govde + isbn_module.isbn13_check_digit(govde)


def sentetik_satirlar(adet: int, *, ilk_sira: int = 1) -> list[dict[str, Any]]:
    """`adet` satırlık künye listesi üretir (adlar ve ISBN'ler birbirinden ayrı).

    Her satırın eser adı benzersizdir: aynı adlı satırlar tek esere bağlanır
    (kova kuralı) ve ölçüm o zaman "10.000 nüsha" değil "10.000 nüsha, 10 eser"
    olurdu — ölçüm gerçek bir devir aktarımını taklit etmelidir.
    """
    satirlar: list[dict[str, Any]] = []
    for sayac in range(adet):
        sira = ilk_sira + sayac
        ad, yazar, konu = KLASIKLER[sayac % len(KLASIKLER)]
        satirlar.append(
            {
                "title": f"{ad} — {sira}. kitap",
                "authors": yazar,
                "publisher": "Örnek Yayınevi",
                "publish_year": 2000 + (sayac % 25),
                "isbn": sentetik_isbn(sira),
                "subjects": konu,
                "classification_code": f"8{sayac % 100:02d}.1",
                "language": "Türkçe",
                "resource_type": "Kitap",
                "copies": 1,
                "shelf_location": BOLUMLER[sayac % len(BOLUMLER)],
            }
        )
    return satirlar


def katalog_dosyasi(
    satirlar: Sequence[Mapping[str, Any]], *, sheet_name: str = CATALOG_SHEET
) -> bytes:
    """Satırları programın kendi sütun sözlüğüyle .xlsx dosyasına yazar.

    Başlıklar `import_schema.COLUMNS`'tan gelir: test, şablonun verdiği dosyanın
    aynısını üretir ve içe aktarım onu hiç dokunulmadan okuyabilmelidir.
    """
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = sheet_name
    ws.append([sutun.header for sutun in COLUMNS])
    for satir in satirlar:
        ws.append([satir.get(sutun.key) for sutun in COLUMNS])
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def baslikli_dosya(
    basliklar: Sequence[str],
    satirlar: Sequence[Sequence[Any]],
    *,
    sheet_name: str = CATALOG_SHEET,
    on_satirlar: Sequence[Sequence[Any]] = (),
) -> bytes:
    """Başlıkları ELLE verilen dosya (eşanlam, kayık başlık, tanınmayan sütun testleri).

    `on_satirlar` başlık satırının ÜSTÜNE yazılır: okulun listelerinde kurum
    başlığı ve boş satırlar bulunur, başlık tespiti onları atlamalıdır.
    """
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = sheet_name
    for satir in on_satirlar:
        ws.append(list(satir))
    ws.append(list(basliklar))
    for satir in satirlar:
        ws.append(list(satir))
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
