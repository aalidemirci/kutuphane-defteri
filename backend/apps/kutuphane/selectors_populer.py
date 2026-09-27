"""Çok okunanlar — okuma tarafı (F10; tasarım §5.3, §10 E12). KİŞİSİZ ve SAYISIZ.

Kaynak YALNIZ `kd_katalog_populer` tablosudur (gün değişimi kapısının yazdığı sıra —
`services.populer`): Raporlar ekranı, Genel Bakış kartı ve Ayın Kitapları afişi (E12)
Ağ Kataloğu vitriniyle AYNI tabloyu okur, ödünç tablosuna uzanmaz. Dönen alanlar
sıra, eser kimliği, kaynak adı ve yazardır; ödünç, üye ya da farklı üye sayısı
YOKTUR (sözlük: "çok okunanlarda sayı gösterilmez, yalnız sıra").

Silinmiş eser listelenmez ve sıra boşluksuz yeniden numaralanır (tablodaki satır
hesap anının sırasıdır; eser sonradan silinmiş olabilir).
"""

from __future__ import annotations

from typing import Any, Final

from django.db.models import Max

from apps.kutuphane.models import KatalogPopuler, PopulerPencereTuru
from apps.kutuphane.services.populer import esik

AYLAR: Final = (
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)

#: Genel Bakış kartında pencere başına gösterilen eser sayısı.
PANO_ADEDI: Final = 3


def pencere_etiketi(pencere_turu: str, pencere: str) -> str:
    """'2026-09' → 'Eylül 2026'; '2026-2027/1' → '2026-2027 ders yılı 1. dönem'."""
    if pencere_turu == PopulerPencereTuru.AY:
        yil, _, ay = pencere.partition("-")
        if yil.isdigit() and ay.isdigit() and 1 <= int(ay) <= 12:
            return f"{AYLAR[int(ay) - 1]} {yil}"
        return pencere
    yil_adi, _, sira = pencere.partition("/")
    if sira:
        return f"{yil_adi} ders yılı {sira}. dönem"
    return f"{yil_adi} ders yılı"


def pencereler(pencere_turu: str) -> list[dict[str, Any]]:
    """Türün hesaplanmış pencereleri, en yeniden eskiye (boş pencere satır tutmaz)."""
    satirlar = (
        KatalogPopuler.objects.filter(pencere_turu=pencere_turu)
        .values("pencere")
        .annotate(son_hesap=Max("hesaplanma"), donmus=Max("dondu"))
        .order_by("-pencere")
    )
    return [
        {
            "window_type": pencere_turu,
            "window": satir["pencere"],
            "label": pencere_etiketi(pencere_turu, satir["pencere"]),
            "frozen": bool(satir["donmus"]),
            "computed_on": satir["son_hesap"],
        }
        for satir in satirlar
    ]


def son_pencere(pencere_turu: str) -> str | None:
    """Vitrinle aynı kural: en son hesaplanan pencere (`katalog.veri.cok_okunanlar`)."""
    satir = (
        KatalogPopuler.objects.filter(pencere_turu=pencere_turu)
        .order_by("-hesaplanma", "-pencere")
        .values_list("pencere", flat=True)
        .first()
    )
    return str(satir) if satir is not None else None


def siralama(pencere_turu: str, pencere: str) -> list[dict[str, Any]]:
    """Pencerenin eserleri sırasıyla — yalnız sıra, kaynak adı ve yazar (sayı YOK)."""
    satirlar = (
        KatalogPopuler.objects.filter(
            pencere_turu=pencere_turu, pencere=pencere, eser__deleted_at__isnull=True
        )
        .select_related("eser")
        .order_by("sira")
    )
    return [
        {
            "rank": sira,
            "work_id": satir.eser_id,
            "title": satir.eser.title,
            "authors": satir.eser.authors,
        }
        for sira, satir in enumerate(satirlar, start=1)
    ]


def pencere_ozeti(pencere_turu: str, pencere: str | None) -> dict[str, Any] | None:
    """Bir pencerenin kartı: ad, donmuş mu, hesap günü ve sıralı eserler; yoksa `None`."""
    if not pencere:
        return None
    ust = KatalogPopuler.objects.filter(pencere_turu=pencere_turu, pencere=pencere).aggregate(
        son_hesap=Max("hesaplanma"), donmus=Max("dondu")
    )
    if ust["son_hesap"] is None:
        return None
    return {
        "window_type": pencere_turu,
        "window": pencere,
        "label": pencere_etiketi(pencere_turu, pencere),
        "frozen": bool(ust["donmus"]),
        "computed_on": ust["son_hesap"],
        "works": siralama(pencere_turu, pencere),
    }


def raporlar_ozeti() -> dict[str, Any]:
    """Raporlar ekranı: eşik, iki türün pencere listesi ve son pencereleri."""
    return {
        "k_threshold": esik(),
        "term_windows": pencereler(PopulerPencereTuru.DONEM),
        "month_windows": pencereler(PopulerPencereTuru.AY),
        "term": pencere_ozeti(PopulerPencereTuru.DONEM, son_pencere(PopulerPencereTuru.DONEM)),
        "month": pencere_ozeti(PopulerPencereTuru.AY, son_pencere(PopulerPencereTuru.AY)),
    }


def pano_ozeti(adet: int = PANO_ADEDI) -> dict[str, Any]:
    """Genel Bakış kartı: son dönem ve son ayın ilk birkaç eseri (sayısız)."""

    def kisa(ozet: dict[str, Any] | None) -> dict[str, Any] | None:
        if ozet is None:
            return None
        return {**ozet, "works": ozet["works"][:adet]}

    return {
        "term": kisa(
            pencere_ozeti(PopulerPencereTuru.DONEM, son_pencere(PopulerPencereTuru.DONEM))
        ),
        "month": kisa(pencere_ozeti(PopulerPencereTuru.AY, son_pencere(PopulerPencereTuru.AY))),
    }
