"""Okuma ödülü iç çıktısı (E20) — ADLI, "İç kullanım" ibareli, YALNIZ YÖNETİCİ KİPİ (F10).

Uygulama Kılavuzu 7'nin ÖNERİSİ ("En çok kitap okuyan öğrenciler ödüllendirilerek
teşvik sistemi kurulabilir.") için okulun karar vermesine yardım eden iç çıktıdır;
bağlayıcı değildir ve belge bunu söyler. Adaylar `selectors_okuma_odulu`'dan gelir
(ölçüt, eşitler ve sınırlar orada). Belgede:

- başlıkta ve her sayfanın dibinde **"İç kullanım"** ibaresi: asılmaz, çoğaltılmaz,
  ağda ve velilerle paylaşılmaz (profil yasağı CLAUDE.md §2-5, tasarım §3);
- yalnız sıra, ad soyad ve sınıf/şube — **ödünç ya da eser sayısı basılmaz**, okul no
  basılmaz; konu, sınıflama ve bölüm hiç okunmaz;
- "Ödünç kaydı okunan kitabı göstermez." notu (sözlüğün "Ödünç geçmişi" satırının
  yasakladığı ifadeler kullanılmaz — docs/sozluk.md §1).

Bu modülü yalnız E20 ucu içe aktarır; Ağ Kataloğu, Genel Bakış, Ayın Kitapları afişi
ve yıl sonu raporu içe aktarmaz (`tests/test_profil_yasagi.py`). Kılavuz alıntısı
docs/mevzuat ile BİREBİRDİR (test sınar). PDF yalnız `shared.pdf.html_to_pdf`
kapısından. Veritabanına YAZMAZ.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone

from apps.kutuphane import selectors_okuma_odulu
from apps.kutuphane.labels.metrics import clean_text
from apps.okul.models import SchoolConfig
from apps.okul.normalize import PREP_LEVEL
from shared.letterhead import letterhead_context
from shared.pdf import html_to_pdf

SABLON: Final = "documents/okuma_odulu.html"
#: Belge adı (sözlük §2: E20) — başlık ve indirme adı buradan.
BELGE_ADI: Final = "Okuma ödülü iç çıktısı"
BASLIK: Final = "OKUMA ÖDÜLÜ İÇ ÇIKTISI"
IC_KULLANIM: Final = "İç kullanım"
#: Her sayfanın dibindeki ibare (sayfa numarasıyla aynı kutuda).
DIPNOT: Final = "İç kullanım — asılmaz, çoğaltılmaz, ağda ve velilerle paylaşılmaz."
#: Uygulama Kılavuzu 7'nin son maddesi — docs/mevzuat ile BİREBİR (test sınar).
KILAVUZ_7_ONERISI: Final = (
    "En çok kitap okuyan öğrenciler ödüllendirilerek teşvik sistemi kurulabilir."
)
NOTLAR: Final = (
    "Bu çıktı Uygulama Kılavuzu'nun 7. bölümündeki öneri için hazırlanmıştır; öneri "
    "bağlayıcı değildir, ödül verilip verilmeyeceğine okul karar verir.",
    "Sıra, dönem içinde ödünç alınıp iade edilmiş farklı eser sayısına göredir: aynı "
    "eserin yeniden alınması bir kez sayılır. Eşit olanlar aynı sıradadır. Sayılar "
    "basılmaz.",
    "Ödünç kaydı okunan kitabı göstermez.",
)
BOS_LISTE: Final = "Bu dönemde ve kapsamda ödünç alıp iade eden öğrenci yok."


def _tarih(gun: date) -> str:
    return f"{gun:%d.%m.%Y}"


def kapsam_metni(class_level: int | None) -> str:
    if class_level is None:
        return "Bütün öğrenciler"
    if class_level == PREP_LEVEL:
        return "Hazırlık sınıfları"
    return f"{class_level}. sınıflar"


def belge_dosya_adi(gun: date | None = None) -> str:
    """'Okuma-ödülü-iç-çıktısı_24.06.2027.pdf' — kişi adı YOK."""
    return f"{BELGE_ADI.replace(' ', '-')}_{_tarih(gun or timezone.localdate())}.pdf"


def baglam(
    bas: date,
    son: date,
    *,
    class_level: int | None = None,
    sira_sayisi: int = selectors_okuma_odulu.VARSAYILAN_SIRA,
    gun: date | None = None,
) -> dict[str, Any]:
    adaylar = selectors_okuma_odulu.adaylar(
        bas, son, class_level=class_level, sira_sayisi=sira_sayisi
    )
    if not adaylar:
        raise ValidationError(BOS_LISTE)
    config = SchoolConfig.load()
    return {
        **letterhead_context(
            school_name=" ".join((config.school_name or config.kisa_ad or "").split()),
            district=config.district,
            principal_name=config.principal_name,
        ),
        "document_title": BASLIK,
        "internal_use": IC_KULLANIM,
        "issued_on": _tarih(gun or timezone.localdate()),
        "period": f"{_tarih(bas)} – {_tarih(son)}",
        "scope": kapsam_metni(class_level),
        "rank_limit": sira_sayisi,
        "rows": [
            {"rank": a.sira, "name": clean_text(a.ad), "class_label": a.sinif or "—"}
            for a in adaylar
        ],
        "guide_quote": KILAVUZ_7_ONERISI,
        "notes": NOTLAR,
        "footnote": DIPNOT,
    }


def ic_cikti_pdf(
    bas: date,
    son: date,
    *,
    class_level: int | None = None,
    sira_sayisi: int = selectors_okuma_odulu.VARSAYILAN_SIRA,
) -> bytes:
    return html_to_pdf(
        render_to_string(SABLON, baglam(bas, son, class_level=class_level, sira_sayisi=sira_sayisi))
    )
