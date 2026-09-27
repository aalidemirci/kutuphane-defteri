"""Ayın Kitapları afişi (E12) — eser bazlı, eşikli, SAYISIZ (F10; tasarım §10, §5.3).

Dayanak (kod yorumunda; afişe yazılmaz — afiş bir duyurudur, yazışma değildir):
Yönetmelik Md. 15/1-ğ "çok okunan ve okunmasında fayda görülen kitaplar listesini
belirli aralıklarla ilan"; Uygulama Kılavuzu 6.2 "o ay en çok okunan kitapların
tanıtıldığı 'Ayın Kitapları' panosu düzenlenebilir".

Afiş AY penceresinin sırasını `kd_katalog_populer`'den okur (`selectors_populer`) —
Ağ Kataloğu vitrininin okuduğu tablonun kendisi: eşik (en az k FARKLI üye) hesapta
uygulanmıştır, tabloya eşiği geçmeyen eser yazılmaz. **Afişte yalnız sıra, kaynak
adı ve yazar vardır**: ödünç, üye ya da farklı üye sayısı yoktur; kişi adı, adlı
sıralama ve sınıf/şube bilgisi hiç okunmaz (profil yasağı CLAUDE.md §2-5; kaynak
taraması `tests/test_profil_yasagi.py`). Sürmekte olan ay "… itibarıyla" notuyla
basılır; kapanmış (dondurulmuş) ay son hâliyle.

Sayfa bütçesi TEK sayfadır: kaynak adı ölçülerek en çok iki satıra, yazar tek
satıra sığdırılır (`labels.card.wrap_text`, `labels.metrics.fit_text` — DejaVu
ölçüleri; sığmayan "…" ile kısalır). Test en uzun künyelerle 10 eser basar
(`tests/test_ayin_kitaplari.py`). PDF yalnız `shared.pdf.html_to_pdf` kapısından.
Veritabanına YAZMAZ.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone

from apps.kutuphane import selectors_populer
from apps.kutuphane.labels.card import wrap_text
from apps.kutuphane.labels.metrics import clean_text, fit_text
from apps.kutuphane.models import PopulerPencereTuru
from apps.okul.models import SchoolConfig
from shared.pdf import html_to_pdf

SABLON: Final = "documents/ayin_kitaplari.html"
#: Belge adı (sözlük §2: E12) — indirme adı buradan.
BELGE_ADI: Final = "Ayın Kitapları afişi"
BASLIK: Final = "AYIN KİTAPLARI"
DIPNOT: Final = (
    "Sıralama bu ayın ödünç kayıtlarından kişisiz olarak hesaplanır; kaç kez ödünç "
    "alındığı gösterilmez."
)
BOS_PENCERE: Final = (
    "Bu ay için çok okunanlar listesi yok: listeye girecek kadar farklı üyenin ödünç "
    "aldığı eser bulunmuyor."
)

#: Kaynak adı ve yazar sütununun genişlik bütçesi (A4, 16 mm kenar payları, sıra
#: sütunu ve hücre dolgusu düşülmüş; güvenlik payı bırakılmış).
METIN_GENISLIGI_MM: Final = 148.0
BASLIK_PUNTOLARI: Final = (14.0, 12.5, 11.5)
YAZAR_PUNTOSU: Final = 10.5


def _tarih(gun: date) -> str:
    return f"{gun:%d.%m.%Y}"


def belge_dosya_adi(pencere: str, gun: date | None = None) -> str:
    """'Ayın-Kitapları-afişi_2026-09_01.10.2026.pdf' — belge adı + ay + yerel tarih."""
    tarih = _tarih(gun or timezone.localdate())
    return f"{BELGE_ADI.replace(' ', '-')}_{pencere}_{tarih}.pdf"


def _eser_satiri(eser: dict[str, Any]) -> dict[str, Any]:
    satirlar, boy = wrap_text(
        eser["title"], METIN_GENISLIGI_MM, BASLIK_PUNTOLARI, bold=True, max_lines=2
    )
    yazar = clean_text(eser["authors"])
    return {
        "rank": eser["rank"],
        "title_lines": satirlar,
        "title_size": f"{boy:g}",
        "authors": fit_text(yazar, METIN_GENISLIGI_MM, YAZAR_PUNTOSU) if yazar else "",
    }


def afis_baglami(pencere: str) -> dict[str, Any]:
    """Afişin bağlamı; pencere yoksa ya da boşsa sözleşmeli 400 (`ValidationError`)."""
    ozet = selectors_populer.pencere_ozeti(PopulerPencereTuru.AY, pencere)
    if ozet is None or not ozet["works"]:
        raise ValidationError(BOS_PENCERE)
    config = SchoolConfig.load()
    hesap = ozet["computed_on"]
    return {
        "school_name": " ".join((config.school_name or config.kisa_ad or "").split()),
        "title": BASLIK,
        "month_label": ozet["label"],
        "as_of": None if ozet["frozen"] else _tarih(hesap),
        "works": [_eser_satiri(eser) for eser in ozet["works"]],
        "footnote": DIPNOT,
        "title_size_pt": f"{BASLIK_PUNTOLARI[0]:g}",
        "author_size_pt": f"{YAZAR_PUNTOSU:g}",
    }


def afis_pdf(pencere: str) -> bytes:
    return html_to_pdf(render_to_string(SABLON, afis_baglami(pencere)))
