"""Yıl sonu kütüphane raporu belgesi (E9) — F8; tasarım §10, F8 ekleri 8.

Okul Kütüphaneleri Yönetmeliği Md. 12/1: "Her ders yılı sonunda kütüphane kaynakları,
kütüphaneci veya görevlendirilen öğretmen tarafından gözden geçirilir ve tespit edilen
hususlar raporla okul müdürlüğüne bildirilir." Uygulama Kılavuzu 2.4: kitap durumu,
kazandırılan ve ayıklanan kaynaklar okul yönetimine raporlanır.

Belge resmî yazı düzenindedir: sayı ve tarih, konu, "OKUL MÜDÜRLÜĞÜNE", gövde,
"Bilgilerinize arz ederim." ve imza (kütüphane yöneticisi — ad BASILMAZ, elle imzalanır).
Bölümler: tespit edilen hususlar (+ onarım, hasar, kayıp sayıları) · koleksiyon özeti ·
yıl içinde kazandırılanlar (edinim yoluna göre) · ayıklanan ve devredilen · kişisiz
ödünç istatistiği.

**KİŞİSEL VERİ YOK** (E9 kod kapısı, CLAUDE.md §2-5 profil yasağı): sayılar
`services.annual_review.review_stats`'tan gelir ve kişisizdir (üye türü ve sınıf düzeyi
kırılımında k farklı üyeden az olan grubun sayısı basılmaz, "—" yazılır; toplamdan geri
hesaplanamasın diye tamamlayıcı gizleme seçicidedir); bu modül
kişi tablosu, üyelik, ödünç satırı ya da şifreli alan OKUMAZ. Testi
`tests/test_yil_raporu_belgesi.py` sentetik adlarla dolu bir yıl kurar ve PDF metnini
tarar.

Sonlandırılmamış rapor "Taslak" ibaresiyle basılır (sayılar basım anındaki
kayıtlardandır); sonlandırılmış raporun sayıları dondurulmuştur ve yeniden basım aynı
sayıları taşır. PDF yalnız `shared.pdf.html_to_pdf` kapısından üretilir. Veritabanına
YAZMAZ.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any, Final

from django.template.loader import render_to_string
from django.utils import timezone

from apps.kutuphane import selectors_yil_raporu
from apps.kutuphane.models import (
    OPEN_CASE_RESOLUTIONS,
    AcquisitionMethod,
    AnnualLibraryReview,
    CaseResolution,
    CopyStatus,
    ResourceType,
    WeedingReason,
    WeedingTmyPath,
)
from apps.kutuphane.services import annual_review as review_service
from apps.okul.models import SchoolConfig
from shared.letterhead import letterhead_context
from shared.pdf import html_to_pdf

SABLON: Final = "documents/yil_sonu_raporu.html"
BELGE_ADI: Final = "Yıl sonu kütüphane raporu"

#: Md. 12/1'in ilk cümlesi — docs/mevzuat ile BİREBİR (test sınar).
MD12_1_RAPOR: Final = (
    "Her ders yılı sonunda kütüphane kaynakları, kütüphaneci veya görevlendirilen öğretmen "
    "tarafından gözden geçirilir ve tespit edilen hususlar raporla okul müdürlüğüne bildirilir."
)
MUHATAP: Final = "OKUL MÜDÜRLÜĞÜNE"
IMZA_ROLU: Final = "Kütüphane yöneticisi"
TASLAK_NOTU: Final = "TASLAK — Rapor sonlandırılmadı; sayılar basım anındaki kayıtlardandır."
BOS_TESPIT: Final = "Tespit edilen husus yazılmadı."
ESIK_ALTI: Final = "—"

#: Üye türü (sözlük: öğrenci / öğretmen / diğer personel) — raporda Başlık düzeninde.
UYE_TURU: Final[dict[str, str]] = {
    "STUDENT": "Öğrenci",
    "TEACHER": "Öğretmen",
    "STAFF": "Diğer personel",
}
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


def _gun(on: date | None = None) -> date:
    return on or timezone.localdate()


def _tarih(gun: date | None) -> str:
    return f"{gun:%d.%m.%Y}" if gun is not None else "…/…/……"


def _iso_tarih(metin: str | None) -> str:
    """'2027-06-18' → '18.06.2027' (dondurulmuş sayılar ISO metin taşır)."""
    if not metin:
        return "—"
    try:
        return _tarih(date.fromisoformat(str(metin)))
    except ValueError:
        return str(metin)


def _sayi(deger: Any) -> str:
    """Türkçe binlik ayırıcıyla sayı: 12345 → '12.345'."""
    try:
        return f"{int(deger):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _kirilim(sayilar: Mapping[str, Any], etiketler: Iterable[tuple[str, str]]) -> str:
    """Sıfır olmayan kalemler: 'Rafta: 120 · Ödünçte: 14' (hiçbiri yoksa '—')."""
    parcalar = [
        f"{etiket}: {_sayi(sayilar.get(kod, 0))}"
        for kod, etiket in etiketler
        if int(sayilar.get(kod, 0) or 0) > 0
    ]
    return " · ".join(parcalar) if parcalar else "—"


def _esikli(hucre: Mapping[str, Any] | None) -> str:
    if not hucre or hucre.get("below_threshold") or hucre.get("loans") is None:
        return ESIK_ALTI
    return _sayi(hucre.get("loans"))


def _aktif(sayi: Any) -> str:
    """Aktif üye sayısı; eşik altında (`None`) "—"."""
    return ESIK_ALTI if sayi is None else _sayi(sayi)


def _ay(metin: str) -> str:
    """'2026-09' → 'Eylül 2026'."""
    try:
        yil, ay = str(metin).split("-")
        return f"{AYLAR[int(ay) - 1]} {yil}"
    except (ValueError, IndexError):
        return str(metin)


def _satir(etiket: str, deger: str, *, alt: bool = False) -> dict[str, Any]:
    return {"label": etiket, "value": deger, "sub": alt}


# ---------------------------------------------------------------------------
# Bölümler — `selectors_yil_raporu.annual_review_stats` şemasıyla (sürüm 1)
# ---------------------------------------------------------------------------
def _tespitler(findings_text: str, f: Mapping[str, Any]) -> dict[str, Any]:
    cozumler = f.get("resolutions") or {}
    return {
        "title": "1. TESPİT EDİLEN HUSUSLAR",
        "text": findings_text.strip() or BOS_TESPIT,
        "rows": [
            _satir("Onarım, hasar ve kayıp", "", alt=True),
            _satir("Onarıma gönderilen nüsha", _sayi(f.get("repairs_sent"))),
            _satir("Onarımdan dönen nüsha", _sayi(f.get("repairs_returned"))),
            _satir("Rapor tarihinde onarımda olan nüsha", _sayi(f.get("in_repair_now"))),
            _satir("Açılan hasar dosyası", _sayi(f.get("damage_cases"))),
            _satir("Açılan kayıp dosyası", _sayi(f.get("loss_cases"))),
            _satir(
                "Dosyaların çözümü",
                _kirilim(
                    cozumler,
                    (
                        (kod, etiket)
                        for kod, etiket in CaseResolution.choices
                        if kod not in OPEN_CASE_RESOLUTIONS
                    ),
                ),
            ),
            _satir("Kayıttan düşme önerisi", _sayi(f.get("write_off_proposals"))),
            _satir("Rapor tarihinde çözülmemiş dosya", _sayi(f.get("open_cases_now"))),
            _satir("Rapor tarihinde kayıp nüsha", _sayi(f.get("lost_copies_now"))),
        ],
        "notes": [],
    }


def _koleksiyon(c: Mapping[str, Any]) -> dict[str, Any]:
    satirlar = [
        _satir("Katalogdaki eser", _sayi(c.get("catalog_work_count"))),
        _satir("Elde nüshası bulunan eser", _sayi(c.get("work_count"))),
        _satir(
            "Kayıt defterindeki nüsha (kayıttan düşülen ve devredilenler dahil)",
            _sayi(c.get("register_count")),
        ),
        _satir("Elde bulunan nüsha", _sayi(c.get("in_stock_count"))),
        _satir("Nüsha durumları", _kirilim(c.get("status_counts") or {}, CopyStatus.choices)),
        _satir(
            "Kaynak türleri (elde bulunan)",
            _kirilim(c.get("resource_type_counts") or {}, ResourceType.choices),
        ),
        _satir("Danışma kaynağı", _sayi(c.get("reference_count"))),
        _satir("El yazması ve nadir eser", _sayi(c.get("rare_count"))),
    ]
    bolumler = c.get("sections") or []
    if bolumler:
        satirlar.append(_satir("Bölümlere göre elde bulunan nüsha", "", alt=True))
        satirlar += [
            _satir(str(b.get("section") or "Bölümü belirtilmemiş"), _sayi(b.get("copies")))
            for b in bolumler
        ]
    return {
        "title": "2. KOLEKSİYON ÖZETİ (RAPOR TARİHİNDE)",
        "text": None,
        "rows": satirlar,
        "notes": [],
    }


def _kazandirilanlar(a: Mapping[str, Any]) -> dict[str, Any]:
    """Kazandırılan = Md. 10/5'in dört yolu; kayıt içi girişler ayrı alt başlıkta (F8)."""
    yollar = a.get("copies_by_method") or {}
    etiketler = dict(AcquisitionMethod.choices)
    satirlar = [
        _satir(str(etiketler[kod]), _sayi(yollar.get(kod, 0)))
        for kod in selectors_yil_raporu.KAZANDIRMA_YOLLARI
    ]
    satirlar += [
        _satir("Toplam kazandırılan nüsha", _sayi(a.get("total_copies"))),
        _satir("Eser sayısı", _sayi(a.get("works"))),
        _satir(
            "Bağış değerlendirmesi",
            f"{_sayi(a.get('donation_intakes_decided'))} bağış ön kaydı karara bağlandı; "
            f"{_sayi(a.get('donation_items_accepted'))} kalem kabul edildi, "
            f"{_sayi(a.get('donation_items_rejected'))} kalem reddedildi",
        ),
        _satir("Kayıt içi girişler (kazandırılan sayılmaz)", "", alt=True),
    ]
    satirlar += [
        _satir(str(etiketler[kod]), _sayi(yollar.get(kod, 0)))
        for kod in selectors_yil_raporu.KAYIT_ICI_YOLLAR
    ]
    return {
        "title": "3. YIL İÇİNDE KAZANDIRILAN KAYNAKLAR",
        "keep": True,
        "text": None,
        "rows": satirlar,
        "notes": [
            "Kazandırılan nüsha Yönetmelik Md. 10/5'te sayılan yollardan (Bakanlık gönderimi, "
            "satın alma, bağış, değişim) gelen nüshadır. Mevcut koleksiyonun programa aktarımı "
            "ve sayım fazlasının kayda alınması kayıt içi giriştir, toplama girmez.",
        ],
    }


def _ayiklanan(w: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "title": "4. AYIKLANAN VE DEVREDİLEN KAYNAKLAR",
        "keep": True,
        "text": None,
        "rows": [
            _satir("Kayıttan düşülen nüsha", _sayi(w.get("withdrawn"))),
            _satir("Devredilen nüsha", _sayi(w.get("transferred"))),
            _satir("Uygulanan ayıklama teklifi", _sayi(w.get("batches_applied"))),
            _satir(
                "Gerekçeye göre (Md. 12/1)",
                _kirilim(w.get("by_reason") or {}, WeedingReason.choices),
            ),
            _satir(
                "Taşınır Mal Yönetmeliği yoluna göre",
                _kirilim(w.get("by_path") or {}, WeedingTmyPath.choices),
            ),
        ],
        "notes": [],
    }


def _odunc(d: Mapping[str, Any]) -> dict[str, Any]:
    k = int(d.get("k_threshold") or 0)
    turler = d.get("by_member_type") or {}
    duzeyler = d.get("by_class_level") or []
    aylar = d.get("by_month") or []
    teslim = d.get("deliveries") or {}
    aktif = d.get("active_members") or {}
    satirlar = [
        _satir("Verilen ödünç", _sayi(d.get("loans"))),
        _satir("İade", _sayi(d.get("returns"))),
        _satir("Ödünç alan farklı üye", _sayi(d.get("distinct_borrowers"))),
        _satir(
            "Üye türüne göre ödünç",
            " · ".join(f"{ad}: {_esikli(turler.get(kod))}" for kod, ad in UYE_TURU.items()),
        ),
        _satir(
            "Sınıf düzeyine göre ödünç",
            " · ".join(f"{int(s['class_level'])}. sınıf: {_esikli(s)}" for s in duzeyler) or "—",
        ),
        _satir(
            "Aylara göre ödünç",
            " · ".join(f"{_ay(s['month'])}: {_sayi(s['loans'])}" for s in aylar) or "—",
        ),
        _satir(
            "Teslim",
            f"Sınıf kitaplığına: {_sayi(teslim.get('section'))} · "
            f"Öğretmene: {_sayi(teslim.get('teacher'))}",
        ),
        _satir(
            "Rapor tarihinde aktif üye",
            " · ".join(f"{ad}: {_aktif(aktif.get(kod))}" for kod, ad in UYE_TURU.items()),
        ),
    ]
    return {
        "title": "5. ÖDÜNÇ İSTATİSTİĞİ",
        "keep": True,
        "text": None,
        "rows": satirlar,
        "notes": [
            f"Rapor kişisizdir: üye bazında bilgi içermez. Üye türü ve sınıf düzeyi kırılımında "
            f"{k} farklı üyeden azının ödünç aldığı grubun sayısı gösterilmez ({ESIK_ALTI}); "
            "gizlenen sayı toplamdan çıkarılarak bulunamasın diye gerektiğinde bir grup daha "
            f"gizlenir. {k} kişiden az aktif üyesi olan türün sayısı da gösterilmez. Sınıf düzeyi "
            "kaydı olmayan öğrencilerin ödüncü düzey kırılımına girmez. Teslim ödünç değildir; "
            "ayrı sayılır.",
        ],
    }


def annual_review_context(review: AnnualLibraryReview) -> dict[str, Any]:
    """E9 bağlamı — sayılar `review_stats`'tan (sonlandırılmışsa dondurulmuş)."""
    config = SchoolConfig.load()
    stats = review_service.review_stats(review)
    yil = review.school_year.name
    donem = stats.get("period") or {}
    okul = " ".join((config.school_name or config.kisa_ad or "").split())
    belge_tarihi = review.document_date
    return {
        **letterhead_context(
            school_name=okul, district=config.district, principal_name=config.principal_name
        ),
        "document_no": " ".join(review.document_no.split()) or "……………",
        "document_date": _tarih(belge_tarihi) if belge_tarihi else "…/…/……",
        "subject": f"Yıl sonu kütüphane raporu ({yil} ders yılı)",
        "draft_note": "" if review.is_finalized else TASLAK_NOTU,
        "addressee": MUHATAP,
        "intro": [
            f"Okul Kütüphaneleri Yönetmeliği Md. 12/1 gereğince {yil} ders yılı sonunda "
            "kütüphane kaynakları gözden geçirilmiştir. Tespit edilen hususlar ile yıl içinde "
            "kazandırılan, ayıklanan ve devredilen kaynaklar aşağıda sunulmuştur. Sayılar "
            f"{_iso_tarih(donem.get('start'))} – {_iso_tarih(donem.get('end'))} dönemine aittir; "
            "koleksiyon özeti rapor tarihindeki durumu gösterir.",
        ],
        "sections": [
            _tespitler(review.findings, stats.get("findings") or {}),
            _koleksiyon(stats.get("collection") or {}),
            _kazandirilanlar(stats.get("acquisitions") or {}),
            _ayiklanan(stats.get("weeding") or {}),
            _odunc(stats.get("circulation") or {}),
        ],
        # Tarih yazının üstündedir (resmî yazı düzeni); imza bloğu tarih yinelemez.
        "signature_date": "",
        "signer_role": IMZA_ROLU,
    }


def annual_review_pdf(review: AnnualLibraryReview) -> bytes:
    return html_to_pdf(render_to_string(SABLON, annual_review_context(review)))


def annual_review_filename(review: AnnualLibraryReview, gun: date | None = None) -> str:
    """'Yıl-sonu-kütüphane-raporu_2026-2027_25.09.2026.pdf'."""
    yil = review.school_year.name.replace("/", "-").replace(" ", "-")
    return f"{BELGE_ADI.replace(' ', '-')}_{yil}_{_gun(gun):%d.%m.%Y}.pdf"
