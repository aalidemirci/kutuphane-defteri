"""Komisyon belgeleri: ayıklama (E7), nadir eserler (E8), bağış ön kaydı ve sonucu (E16) — F8.

Tasarım §10 (E7 tablosu "ayıklama gerekçesinden TMY yoluna" bağlayıcıdır), §6.2,
F8 ekleri. Her madde atfı `docs/mevzuat/` metninden doğrulanır (testler alıntıları
depodaki metinle karşılaştırır).

**E7 — Ayıklama belgeleri** (bir ayıklama teklifinin belgeleri; sözlük §2):

| Belge | Ne zaman | İçerik |
|---|---|---|
| Ayıklama teklif listesi | teklifte kalem varsa | Seçim ve Ayıklama Komisyonuna sunulan liste: gerekçe (Md. 12/1 bendi) ve önerilen TMY yolu; imza: teklif eden kütüphane yöneticisi |
| Ayıklama tutanağı | komisyon kararı bağlandıktan sonra | Md. 12/1'in "bir tutanakla tespit" hükmü: ayıklanmasına karar verilenler ve komisyonun ayıklamadığı kalemler (gerekçesiyle); imza: komisyon başkanı ve üyeler (karardan, ŞİFRELİ alan) |
| Kayıttan düşme teklif listesi | kararlı teklifte kayıttan düşme kalemi varsa | Kayıttan Düşme Teklif ve Onay Tutanağına esas HAZIRLIK (TMY 10/1-e): 27/1 ve 28 yolları ayrı tabloda, onaylanmayanlar ayrı; TMY komisyonu imzası (28'de en az üç kişi — 28/1; 27/1'de isteğe bağlı — 10/1-e) ve harcama yetkilisinin OLUR'u |
| İmha tutanağı | onaylı teklifte imha kararı varsa (28/5) | şablondur: yalnız imha kararının kapsadığı 28 kalemleri (kalem düzeyinde); imha tarihi, yeri ve yöntemi elle yazılır; imza TMY komisyonu (ilk üye işin uzmanı — 28/1) |
| Devir listesi (PDF + XLSX) | kararlı teklifte devir kalemi varsa | Md. 12/1 son cümlesi; 24/2 (MEB okulu) ya da 31 (başka kamu idaresi); imza: devreden, devralan, harcama yetkilisi |

Program TKYS'nin yerine GEÇMEZ: Kayıttan Düşme Teklif ve Onay Tutanağı ve Varlık
İşlem Fişi resmî belgelerdir ve Taşınır Kayıt ve Yönetim Sistemi'nde düzenlenir; bu
çıktılar onlara dayanak hazırlığıdır ve bunu dipnotta söyler. "İmha" sözcüğü
YALNIZ imha tutanağında geçer (sözlük §1: "imha yalnız imha tutanağı bağlamında").

**E8 — El yazması ve nadir eserler listesi** (Md. 12/2): komisyon kararına bağlı
liste; imza komisyonundur (karar bağlanmamışsa boş imza satırları).

**E16 — Bağış ön kayıt listesi** (Md. 10/3): komisyona sunulan liste; "Kabul / Ret"
sütunu komisyonun elle doldurması içindir. Kararın sonucu bu belgeye YAZILMAZ; onu
kararın ardından **Bağış değerlendirme sonucu** verir (25.09.2026 kullanıcı kararı,
tasarım F8 ekleri 13): kabul ve ret edilen kalemler, ret gerekçeleri, kararın tarih ve
sayısı, edinim tarihi — taşınır kayıt yetkilisinin Varlık İşlem Fişine (TMY 16/1)
dayanak ve bağışçıya bilgi. TMY'de "bağış kabul tutanağı" diye bir belge yoktur; ad
bilinçle "tutanak" değildir. Program TMY belgesi (VİF, Taşınır Geçici Alındısı) ve
değer tespit komisyonu tutanağı üretmez.

Kişisel veri: komisyon başkanı ve üyeleri, TMY komisyonu, harcama yetkilisi ve
bağışçı adları ŞİFRELİ alanlardan yalnız belgenin kendisine çözülür (imza
alanları, bağışçı satırı). Belgeler yalnız yönetici kipinde basılır (uçlar görevli
izin listesinde değildir). Ödünç ve üye verisi hiçbir belgeye girmez.

PDF'ler yalnız `shared.pdf.html_to_pdf` kapısından üretilir (CLAUDE.md §3). Bu modül
veritabanına YAZMAZ. Hata iletilerinde kişi adı yoktur.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_ayiklama
from apps.kutuphane.models import (
    WEEDING_EXCLUDED_STATES,
    WEEDING_WRITE_OFF_PATHS,
    CommissionDecision,
    Copy,
    DonationIntake,
    DonationIntakeItem,
    DonationIntakeStatus,
    DonationItemDecision,
    RareWorksSubmission,
    RareWorksSubmissionStatus,
    WeedingBatch,
    WeedingBatchStatus,
    WeedingCriterion,
    WeedingItem,
    WeedingItemState,
    WeedingReason,
    WeedingTmyPath,
)
from apps.okul.models import SchoolConfig
from shared.letterhead import letterhead_context
from shared.pdf import html_to_pdf

SABLON: Final = "documents/komisyon_listesi.html"

# ---------------------------------------------------------------------------
# Belge adları (sözlük §2: E7, E8, E16 — cümle düzeninde, sözlük §3) — ekran ve indirme adları
# ---------------------------------------------------------------------------
TEKLIF_LISTESI_ADI: Final = "Ayıklama teklif listesi"
AYIKLAMA_TUTANAGI_ADI: Final = "Ayıklama tutanağı"
KAYITTAN_DUSME_ADI: Final = "Kayıttan düşme teklif listesi"
IMHA_TUTANAGI_ADI: Final = "İmha tutanağı"
DEVIR_LISTESI_ADI: Final = "Devir listesi"
NADIR_ESER_ADI: Final = "El yazması ve nadir eserler listesi"
BAGIS_LISTESI_ADI: Final = "Bağış ön kayıt listesi"
BAGIS_SONUCU_ADI: Final = "Bağış değerlendirme sonucu"

#: Ayıklama belgelerinin adres adları (`library/weeding-batches/<pk>/documents/<belge>/`).
TEKLIF_LISTESI: Final = "teklif-listesi"
AYIKLAMA_TUTANAGI: Final = "ayiklama-tutanagi"
KAYITTAN_DUSME: Final = "kayittan-dusme"
IMHA_TUTANAGI: Final = "imha-tutanagi"
DEVIR_LISTESI: Final = "devir-listesi"

PDF: Final = "pdf"
XLSX: Final = "xlsx"


@dataclass(frozen=True)
class AyiklamaBelgesi:
    """Bir ayıklama belgesinin tanımı: adres adı, belge adı, biçimleri."""

    slug: str
    ad: str
    bicimler: tuple[str, ...] = (PDF,)


#: Ayıklama belgeleri, ekrandaki ve kılavuzdaki sırasıyla (iş sırası).
AYIKLAMA_BELGELERI: Final[tuple[AyiklamaBelgesi, ...]] = (
    AyiklamaBelgesi(TEKLIF_LISTESI, TEKLIF_LISTESI_ADI),
    AyiklamaBelgesi(AYIKLAMA_TUTANAGI, AYIKLAMA_TUTANAGI_ADI),
    AyiklamaBelgesi(KAYITTAN_DUSME, KAYITTAN_DUSME_ADI),
    AyiklamaBelgesi(IMHA_TUTANAGI, IMHA_TUTANAGI_ADI),
    AyiklamaBelgesi(DEVIR_LISTESI, DEVIR_LISTESI_ADI, (PDF, XLSX)),
)
_BELGE_TANIMLARI: Final[dict[str, AyiklamaBelgesi]] = {b.slug: b for b in AYIKLAMA_BELGELERI}

# ---------------------------------------------------------------------------
# İletiler (kişisel veri YOK)
# ---------------------------------------------------------------------------
UNKNOWN_DOCUMENT_MESSAGE: Final = "Böyle bir ayıklama belgesi yok."
UNKNOWN_FORMAT_MESSAGE: Final = "Bu belge bu biçimde üretilmez."
NO_ITEMS_MESSAGE: Final = "Teklifte kalem yok."
NEEDS_DECISION_MESSAGE: Final = "Komisyon kararı bağlandıktan sonra basılır."
NO_WRITE_OFF_MESSAGE: Final = "Teklifte kayıttan düşme kalemi yok."
NO_TRANSFER_MESSAGE: Final = "Teklifte devir kalemi yok."
NEEDS_DESTRUCTION_MESSAGE: Final = (
    "Yalnız harcama yetkilisinin onayında imha kararı işaretlenmiş teklifte basılır "
    "(Taşınır Mal Yönetmeliği md. 28/5)."
)
NO_DESTRUCTION_ITEMS_MESSAGE: Final = "İmha kararının kapsadığı hurdaya ayırma kalemi yok."
RARE_EMPTY_MESSAGE: Final = "Listede eser yok."
DONATION_EMPTY_MESSAGE: Final = "Bağış ön kaydında kalem yok."
DONATION_NOT_DECIDED_MESSAGE: Final = "Komisyon kararı uygulandıktan sonra basılır."

# ---------------------------------------------------------------------------
# Mevzuat metinleri — docs/mevzuat ile BİREBİR (testler sınar)
# ---------------------------------------------------------------------------
#: Okul Kütüphaneleri Yönetmeliği Md. 12/1 son cümlesinden önceki cümle (devir).
MD12_1_DEVIR: Final = (
    "10 uncu maddenin birinci fıkrasının (b) bendine uygun olmayan kaynaklar uygun okullara "
    "veya kurumlara devredilir."
)
#: Md. 12/2.
MD12_2: Final = (
    "Seçim ve Ayıklama Komisyonu tarafından tespit edilen el yazmaları ve nadir eserler "
    "listesi, Genel Müdürlüğe gönderilir."
)
#: Md. 10/3.
MD10_3: Final = (
    "Okul kütüphanesine bağışlanacak kitaplar, bu Yönetmelik çerçevesinde Seçim ve Ayıklama "
    "Komisyonu tarafından değerlendirilir."
)
#: TMY 28/5'in son iki cümlesinin ilki (imhayı kim yapar).
TMY28_5_IMHA: Final = "İmha, komisyon veya komisyonun gözetiminde uzman kişiler tarafından yapılır."

TKYS_DIPNOTU: Final = (
    "Bu çıktı hazırlıktır. Resmî Kayıttan Düşme Teklif ve Onay Tutanağı ve Varlık İşlem Fişi "
    "Taşınır Kayıt ve Yönetim Sistemi'nde (TKYS) düzenlenir."
)
DEVIR_DIPNOTU: Final = (
    "Bu liste devrin hazırlığıdır. Çıkış, Varlık İşlem Fişiyle Taşınır Kayıt ve Yönetim "
    "Sistemi'nde (TKYS) yapılır."
)
BAGIS_DIPNOTU: Final = (
    "Bu çıktı hazırlıktır: taşınır kayıt yetkilisinin Varlık İşlem Fişine dayanak ve bağışçıya "
    "bilgi içindir. Programın kataloglaması taşınır kaydı değildir; bağışın giriş kaydı Taşınır "
    "Kayıt ve Yönetim Sistemi'nde (TKYS) yapılır."
)
#: TMY 16/1 ve 13/2-c'nin sade anlatımı (Bağış değerlendirme sonucunun notu; testler
#: dayandığı ifadeleri depodaki fıkra metninde arar).
BAGIS_TMY_NOTU: Final = (
    "Kabul edilen kaynaklar taşınır kayıt yetkilisince Varlık İşlem Fişi düzenlenerek kayıtlara "
    "alınır; fişin bir nüshası bağışçıya verilir (Taşınır Mal Yönetmeliği md. 16/1). Kayda esas "
    "değer, bağışçının belgeyle belirttiği değer, yoksa değer tespit komisyonunca belirlenen "
    "değerdir (md. 13/2-c)."
)

# ---------------------------------------------------------------------------
# Belgede kullanılan kısa adlar (ekranın uzun etiketleri tabloya sığmaz)
# ---------------------------------------------------------------------------
GEREKCE_BELGE: Final[dict[str, str]] = {
    WeedingReason.WORN: "Aşırı kullanımdan yıpranmış (Md. 12/1-a)",
    WeedingReason.OBSOLETE: "Bilimsel değeri kalmamış (Md. 12/1-b)",
    WeedingReason.LEVEL_MISMATCH: "Kurumun düzeyine uygun değil (Md. 12/1-c; 10/1-b)",
    WeedingReason.CRITERIA_MISMATCH: "10. maddedeki ölçütlere uygun değil (Md. 12/1-ç)",
}
#: Uyulmayan ölçütün Md. 10 bendi (`WeedingCriterion`).
OLCUT_BENDI: Final[dict[str, str]] = {
    WeedingCriterion.GENERAL_AIMS: "Md. 10/1-a",
    WeedingCriterion.AGE_LEVEL: "Md. 10/1-b",
    WeedingCriterion.VALUES: "Md. 10/1-c",
    WeedingCriterion.PERSONALITY: "Md. 10/1-ç",
    WeedingCriterion.TURKISH: "Md. 10/1-d",
    WeedingCriterion.THINKING: "Md. 10/1-e",
    WeedingCriterion.LITERACIES: "Md. 10/1-f",
    WeedingCriterion.PROHIBITED: "Md. 10/4",
}
YOL_BELGE: Final[dict[str, str]] = {
    WeedingTmyPath.TMY_27: "Kayıttan düşme (TMY md. 27/1)",
    WeedingTmyPath.TMY_28: "Hurdaya ayırma (TMY md. 28)",
    WeedingTmyPath.TMY_24_2: "Devir: MEB okulu (TMY md. 24/2)",
    WeedingTmyPath.TMY_31: "Devir: başka kamu idaresi (TMY md. 31)",
}
KAYITTAN_DUSME_TABLOLARI: Final[dict[str, str]] = {
    WeedingTmyPath.TMY_27: "KULLANILMAZ HÂLE GELEN KAYNAKLAR (TMY MD. 27/1)",
    WeedingTmyPath.TMY_28: "HURDAYA AYRILAN KAYNAKLAR (TMY MD. 28)",
}

BOS_TARIH: Final = "…/…/……"
BOS_YER: Final = "……………………………………"
#: Devir kaleminin kurumu henüz yazılmamışsa künyede (tasarım F8 ekleri 4: onaydan önce yazılır).
KURUM_YAZILMADI: Final = "Yazılmadı"
#: TMY 28/1: hurdaya ayırmayı değerlendiren komisyonun üyelerinden biri işin uzmanıdır.
UZMAN_ROLU: Final = "Komisyon üyesi (işin uzmanı)"
UYE_ROLU: Final = "Komisyon üyesi"


# ---------------------------------------------------------------------------
# Ortak yardımcılar
# ---------------------------------------------------------------------------
def _gun(on: date | None = None) -> date:
    return on or timezone.localdate()


def _tarih(gun: date | None) -> str:
    return f"{gun:%d.%m.%Y}" if gun is not None else "—"


def belge_dosya_adi(ad: str, gun: date | None = None, *, bicim: str = PDF) -> str:
    """'Ayıklama-Tutanağı_25.09.2026.pdf' — belge adı + yerel tarih (sözlük §3)."""
    return f"{ad.replace(' ', '-')}_{_gun(gun):%d.%m.%Y}.{bicim}"


def _okul_adi(config: SchoolConfig) -> str:
    return " ".join((config.school_name or config.kisa_ad or "").split())


def _antet(config: SchoolConfig) -> dict[str, str]:
    return letterhead_context(
        school_name=_okul_adi(config),
        district=config.district,
        principal_name=config.principal_name,
    )


def _tek_satir(metin: str) -> str:
    return " ".join((metin or "").split())


def _satirlar(metin: str) -> list[str]:
    """Serbest metnin boş olmayan satırları (komisyon üyeleri: satır başına bir kişi)."""
    return [_tek_satir(s) for s in (metin or "").splitlines() if s.strip()]


def _barkod(copy: Copy) -> str:
    return barcode_module.format_barcode(copy.barcode)


def _h(deger: Any, cls: str = "") -> dict[str, str]:
    """Tablo hücresi."""
    return {"v": "" if deger is None else str(deger), "c": cls}


def _sutun(baslik: str, genislik: int, cls: str = "") -> dict[str, Any]:
    return {"header": baslik, "width": genislik, "cls": cls}


def _tablo(
    baslik: str, sutunlar: list[dict[str, Any]], satirlar: list[list[dict[str, str]]], bos: str
) -> dict[str, Any]:
    assert sum(int(s["width"]) for s in sutunlar) == 100, "sütun genişlikleri %100 olmalı"
    return {"title": baslik, "columns": sutunlar, "rows": satirlar, "empty": bos}


def _bilgi(pairs: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"label": e, "value": v} for e, v in pairs]


def _imza_izgarasi(
    kisiler: Sequence[dict[str, str]], *, sutun: int = 3
) -> list[list[dict[str, str]]]:
    """İmza hücrelerini `sutun`'luk satırlara böler (son satır eksik kalabilir)."""
    return [list(kisiler[i : i + sutun]) for i in range(0, len(kisiler), sutun)]


def karar_metni(karar: CommissionDecision | None) -> str:
    """'12.06.2027 tarihli ve 2027/4 sayılı' (sayı yoksa yalnız tarih)."""
    if karar is None:
        return "—"
    tarih = _tarih(karar.decision_date)
    sayi = _tek_satir(karar.decision_no)
    return f"{tarih} tarihli ve {sayi} sayılı" if sayi else f"{tarih} tarihli"


def komisyon_imzalari(
    karar: CommissionDecision | None, *, bos_uye: int = 2
) -> list[dict[str, str]]:
    """Seçim ve Ayıklama Komisyonunun imza hücreleri: başkan + üyeler (ŞİFRELİ alanlardan).

    Karar yoksa ya da silinmişse boş imza satırları (başkan + `bos_uye` üye).
    """
    if karar is None or karar.deleted_at is not None:
        return [{"name": "", "role": "Komisyon başkanı"}] + [
            {"name": "", "role": "Üye"} for _ in range(bos_uye)
        ]
    unvan = _tek_satir(karar.chair_title)
    baskan = {
        "name": _tek_satir(karar.chair_name),
        "role": f"Komisyon başkanı — {unvan}" if unvan else "Komisyon başkanı",
    }
    uyeler = [{"name": ad, "role": "Üye"} for ad in _satirlar(karar.participants_text)]
    if not uyeler:
        uyeler = [{"name": "", "role": "Üye"} for _ in range(bos_uye)]
    return [baskan, *uyeler]


def _tmy_komisyonu(batch: WeedingBatch, *, zorunlu: bool) -> list[dict[str, str]]:
    """TMY komisyonunun imza hücreleri (10/1-e, 28/1): kayıtlı adlar ya da boş satırlar.

    Zorunluysa (28 yolu) ad yoksa en az üç boş satır (28/1: "en az üç kişiden").
    Hurdaya ayırmada 28/1 üyelerden birinin "işin uzmanı" olmasını ister: ilk satır
    "Komisyon üyesi (işin uzmanı)" rolüyle basılır (ekran ve kılavuz işin uzmanını
    ilk satıra yazdırır).
    """
    adlar = _satirlar(batch.tmy_commission_members)
    hucreler = (
        [{"name": ad, "role": UYE_ROLU} for ad in adlar]
        if adlar
        else ([{"name": "", "role": UYE_ROLU} for _ in range(3)] if zorunlu else [])
    )
    if zorunlu and hucreler:
        hucreler[0] = {**hucreler[0], "role": UZMAN_ROLU}
    return hucreler


def _harcama_yetkilisi(batch: WeedingBatch, *, baslik: str = "OLUR") -> dict[str, str]:
    """Harcama yetkilisinin onay bloğu: kayıtlıysa ad ve tarih, değilse boş (elle doldurulur)."""
    onayli = batch.status in (WeedingBatchStatus.APPROVED, WeedingBatchStatus.APPLIED)
    return {
        "heading": baslik,
        "date": _tarih(batch.approved_on) if onayli and batch.approved_on else BOS_TARIH,
        "name": _tek_satir(batch.approved_by_name) if onayli else "",
        "role": "Harcama yetkilisi",
    }


def _gerekce_metni(kalem: WeedingItem) -> str:
    metin = GEREKCE_BELGE.get(kalem.reason, str(kalem.get_reason_display()))
    if kalem.reason == WeedingReason.CRITERIA_MISMATCH and kalem.criterion:
        bent = OLCUT_BENDI.get(kalem.criterion, "")
        ad = str(kalem.get_criterion_display())
        return f"{metin}: {ad} ({bent})" if bent else f"{metin}: {ad}"
    return metin


def _yol_metni(kalem: WeedingItem) -> str:
    metin = YOL_BELGE.get(kalem.tmy_path, str(kalem.get_tmy_path_display()))
    hedef = _tek_satir(kalem.transfer_target)
    return f"{metin} — {hedef}" if kalem.is_transfer and hedef else metin


def _baglam(
    *,
    baslik: str,
    gun: date,
    info: Iterable[tuple[str, str]],
    alt_baslik: str = "",
    paragraflar: Sequence[str] = (),
    tablolar: Sequence[dict[str, Any]] = (),
    notlar: Sequence[str] = (),
    imza_basligi: str = "",
    imzalar: Sequence[dict[str, str]] = (),
    tekil_imza: dict[str, str] | None = None,
    onay: dict[str, str] | None = None,
    dipnot: str = "",
) -> dict[str, Any]:
    config = SchoolConfig.load()
    return {
        **_antet(config),
        "document_title": baslik,
        "subtitle": alt_baslik,
        "issued_on": _tarih(gun),
        "info": _bilgi(info),
        "paragraphs": list(paragraflar),
        "tables": list(tablolar),
        "notes": list(notlar),
        "signature_title": imza_basligi,
        "signature_rows": _imza_izgarasi(imzalar),
        "single_signature": tekil_imza,
        "approval": onay,
        "footnote": dipnot,
    }


def _pdf(baglam: dict[str, Any]) -> bytes:
    return html_to_pdf(render_to_string(SABLON, baglam))


# ---------------------------------------------------------------------------
# E7 — ayıklama belgeleri
# ---------------------------------------------------------------------------
def _kalemler(batch: WeedingBatch) -> list[WeedingItem]:
    return list(selectors_ayiklama.batch_items(batch))


def _komisyon_ayiklamadi(kalem: WeedingItem) -> bool:
    return kalem.state == WeedingItemState.KEPT_BY_COMMISSION


def _ayiklananlar(kalemler: Iterable[WeedingItem]) -> list[WeedingItem]:
    """Komisyonun ayıklanmasına karar verdiği kalemler (onaylanmayanlar dahil)."""
    return [k for k in kalemler if not _komisyon_ayiklamadi(k)]


def _etkin(kalemler: Iterable[WeedingItem]) -> list[WeedingItem]:
    """Teklif dışı bırakılmamış kalemler (komisyon ayıkladı, harcama yetkilisi onayladı)."""
    return [k for k in kalemler if k.state not in WEEDING_EXCLUDED_STATES]


def _imha_kalemleri(kalemler: Iterable[WeedingItem]) -> list[WeedingItem]:
    """İmha kararının (TMY 28/5) kapsadığı etkin hurdaya ayırma kalemleri — kalem düzeyinde."""
    return [
        k for k in _etkin(kalemler) if k.tmy_path == WeedingTmyPath.TMY_28 and k.destruction_decided
    ]


def _kararli(batch: WeedingBatch) -> bool:
    return batch.status in (
        WeedingBatchStatus.DECIDED,
        WeedingBatchStatus.APPROVED,
        WeedingBatchStatus.APPLIED,
    )


def weeding_document_blocker(batch: WeedingBatch, slug: str) -> str:
    """Belge basılamıyorsa nedeni (kullanıcı metni), basılabiliyorsa boş metin."""
    if slug not in _BELGE_TANIMLARI:
        return UNKNOWN_DOCUMENT_MESSAGE
    kalemler = _kalemler(batch)
    if not kalemler:
        return NO_ITEMS_MESSAGE
    if slug == TEKLIF_LISTESI:
        return ""
    if not _kararli(batch):
        return NEEDS_DECISION_MESSAGE
    ayiklanan = _ayiklananlar(kalemler)
    if slug == AYIKLAMA_TUTANAGI:
        return ""
    if slug == KAYITTAN_DUSME:
        return (
            ""
            if any(k.tmy_path in WEEDING_WRITE_OFF_PATHS for k in ayiklanan)
            else (NO_WRITE_OFF_MESSAGE)
        )
    if slug == DEVIR_LISTESI:
        return "" if any(k.is_transfer for k in _etkin(ayiklanan)) else NO_TRANSFER_MESSAGE
    # İmha tutanağı (28/5): onaylı teklifte imha kararı ve etkin 28 kalemi.
    if (
        batch.status not in (WeedingBatchStatus.APPROVED, WeedingBatchStatus.APPLIED)
        or not batch.destruction_decided
    ):
        return NEEDS_DESTRUCTION_MESSAGE
    if not _imha_kalemleri(kalemler):
        return NO_DESTRUCTION_ITEMS_MESSAGE
    return ""


def weeding_documents(batch: WeedingBatch) -> list[dict[str, Any]]:
    """Teklifin belgeleri ve basılabilirlikleri (ekran düğmeleri buradan kurulur)."""
    sonuc = []
    for belge in AYIKLAMA_BELGELERI:
        engel = weeding_document_blocker(batch, belge.slug)
        sonuc.append(
            {
                "kind": belge.slug,
                "title": belge.ad,
                "formats": list(belge.bicimler),
                "available": engel == "",
                "reason": engel,
            }
        )
    return sonuc


def ensure_weeding_document(batch: WeedingBatch, slug: str, bicim: str = PDF) -> AyiklamaBelgesi:
    """Belge tanımını döndürür; basılamıyorsa ya da biçim yoksa `ValidationError`."""
    belge = _BELGE_TANIMLARI.get(slug)
    if belge is None:
        raise ValidationError(UNKNOWN_DOCUMENT_MESSAGE)
    if bicim not in belge.bicimler:
        raise ValidationError({"kind": UNKNOWN_FORMAT_MESSAGE})
    engel = weeding_document_blocker(batch, slug)
    if engel:
        raise ValidationError(engel)
    return belge


def _yol_ozeti(kalemler: Sequence[WeedingItem]) -> str:
    dusme = sum(1 for k in kalemler if k.tmy_path in WEEDING_WRITE_OFF_PATHS)
    devir = sum(1 for k in kalemler if k.is_transfer)
    return f"{len(kalemler)} kaynak (kayıttan düşme: {dusme}, devir: {devir})"


_KALEM_SUTUNLARI: Final = [
    _sutun("Sıra", 6, "sayi"),
    _sutun("Barkod", 14),
    _sutun("Kaynak adı", 25),
    _sutun("Yazar", 20),
    _sutun("Yıl", 7, "sayi"),
    _sutun("Gerekçe", 14),
    _sutun("TMY yolu", 14),
]


def _kalem_satiri(sira: int, kalem: WeedingItem) -> list[dict[str, str]]:
    eser = kalem.copy.work
    return [
        _h(sira, "sayi"),
        _h(_barkod(kalem.copy), "tek"),
        _h(eser.title),
        _h(eser.authors),
        _h(eser.publish_year or "", "sayi"),
        _h(_gerekce_metni(kalem)),
        _h(_yol_metni(kalem)),
    ]


def proposal_list_context(batch: WeedingBatch, *, on: date | None = None) -> dict[str, Any]:
    """Ayıklama teklif listesi — Seçim ve Ayıklama Komisyonuna sunulan liste."""
    gun = _gun(on)
    kalemler = _kalemler(batch)
    info = [("Ders yılı", batch.school_year.name)]
    if batch.submitted_at is not None:
        info.append(("Komisyona sunulma tarihi", _tarih(timezone.localdate(batch.submitted_at))))
    info += [("Teklif edilen", _yol_ozeti(kalemler)), ("Durum", str(batch.get_status_display()))]
    return _baglam(
        baslik="AYIKLAMA TEKLİF LİSTESİ",
        gun=gun,
        info=info,
        paragraflar=[
            "Aşağıda bilgileri yazılı kütüphane kaynaklarının, Okul Kütüphaneleri Yönetmeliği "
            "Md. 12/1'de sayılan nedenlerle ayıklanması Seçim ve Ayıklama Komisyonunun "
            "değerlendirmesine sunulur. Kaynaklar komisyon kararına ve harcama yetkilisinin "
            "onayına kadar kütüphane kaydında kalır.",
        ],
        tablolar=[
            _tablo(
                "",
                _KALEM_SUTUNLARI,
                [_kalem_satiri(i, k) for i, k in enumerate(kalemler, start=1)],
                NO_ITEMS_MESSAGE,
            )
        ],
        notlar=[
            "Önerilen yol, ayıklama gerekçesine göre belirlenir: yıpranan kaynak kullanılmaz "
            "hâle gelme (TMY md. 27/1) ya da hurdaya ayırma (TMY md. 28) yoluyla, bilimsel değeri "
            "kalmayan ve 10. maddedeki ölçütlere uygun olmayan kaynak hurdaya ayırma yoluyla "
            "kayıttan düşülür; kurumun düzeyine uygun olmayan kaynak devir yoluna konur. Md. "
            "12/1, yaş ve gelişim düzeyine uygun olmayan kaynağın (Md. 10/1-b) uygun okullara "
            "veya kurumlara devredilmesini ister.",
        ],
        tekil_imza={"date": _tarih(gun), "name": "", "role": "Teklif eden — Kütüphane yöneticisi"},
    )


def proposal_list_pdf(batch: WeedingBatch, *, on: date | None = None) -> bytes:
    return _pdf(proposal_list_context(batch, on=on))


def weeding_report_context(batch: WeedingBatch, *, on: date | None = None) -> dict[str, Any]:
    """Ayıklama tutanağı — Md. 12/1: ayıklanmasına karar verilenler bir tutanakla tespit edilir."""
    gun = _gun(on)
    kalemler = _kalemler(batch)
    ayiklanan = _ayiklananlar(kalemler)
    ayiklanmayan = [k for k in kalemler if _komisyon_ayiklamadi(k)]
    karar = batch.commission_decision
    info = [
        ("Seçim ve Ayıklama Komisyonu kararı", karar_metni(karar)),
        ("Ders yılı", batch.school_year.name),
        ("Ayıklanan", _yol_ozeti(ayiklanan)),
    ]
    if ayiklanmayan:
        info.append(("Komisyonun ayıklamadığı", f"{len(ayiklanmayan)} kaynak"))
    tablolar = [
        _tablo(
            "AYIKLANMASINA KARAR VERİLEN KAYNAKLAR",
            _KALEM_SUTUNLARI,
            [_kalem_satiri(i, k) for i, k in enumerate(ayiklanan, start=1)],
            "Komisyon hiçbir kaynağın ayıklanmasına karar vermedi.",
        )
    ]
    if ayiklanmayan:
        tablolar.append(
            _tablo(
                "KOMİSYONUN AYIKLANMASINA KARAR VERMEDİĞİ KAYNAKLAR",
                [
                    _sutun("Sıra", 6, "sayi"),
                    _sutun("Barkod", 14),
                    _sutun("Kaynak adı", 32),
                    _sutun("Yazar", 18),
                    _sutun("Komisyonun gerekçesi", 30),
                ],
                [
                    [
                        _h(i, "sayi"),
                        _h(_barkod(k.copy), "tek"),
                        _h(k.copy.work.title),
                        _h(k.copy.work.authors),
                        _h(_tek_satir(k.exclusion_reason)),
                    ]
                    for i, k in enumerate(ayiklanmayan, start=1)
                ],
                "",
            )
        )
    return _baglam(
        baslik="AYIKLAMA TUTANAĞI",
        gun=gun,
        info=info,
        paragraflar=[
            f"Seçim ve Ayıklama Komisyonu, {karar_metni(karar)} kararıyla aşağıda bilgileri "
            "yazılı kütüphane kaynaklarının Okul Kütüphaneleri Yönetmeliği Md. 12/1'de sayılan "
            "nedenlerle ayıklanmasına karar vermiştir. Bu tutanak aşağıda imzası bulunanlarca "
            "düzenlenmiştir.",
            "Ayıklanan kaynakların kayıtlardan düşümü Taşınır Mal Yönetmeliği hükümlerine göre "
            f"yapılır. Md. 12/1: “{MD12_1_DEVIR}”",
        ],
        tablolar=tablolar,
        imza_basligi="SEÇİM VE AYIKLAMA KOMİSYONU",
        imzalar=komisyon_imzalari(karar),
    )


def weeding_report_pdf(batch: WeedingBatch, *, on: date | None = None) -> bytes:
    return _pdf(weeding_report_context(batch, on=on))


_DUSME_SUTUNLARI: Final = [
    _sutun("Sıra", 6, "sayi"),
    _sutun("Barkod", 14),
    _sutun("Kaynak adı", 27),
    _sutun("Yazar", 20),
    _sutun("TKYS kodu", 13),
    _sutun("Gerekçe", 20),
]


def _dusme_satiri(sira: int, kalem: WeedingItem) -> list[dict[str, str]]:
    return [
        _h(sira, "sayi"),
        _h(_barkod(kalem.copy), "tek"),
        _h(kalem.copy.work.title),
        _h(kalem.copy.work.authors),
        _h(kalem.copy.external_asset_ref or "—"),
        _h(_gerekce_metni(kalem)),
    ]


def write_off_context(batch: WeedingBatch, *, on: date | None = None) -> dict[str, Any]:
    """Kayıttan düşme teklif listesi — Kayıttan Düşme Teklif ve Onay Tutanağına esas hazırlık.

    TMY 10/1-e: tutanak en az üç kişilik komisyonca imzalanır ve harcama yetkilisince
    onaylanır; yok olma ve yıpranma hâllerinde durumu belgeleyen tutanak varsa komisyon
    kurulması gerekmeksizin harcama yetkilisince onaylanır. Ayıklama tutanağının bu
    tutanak sayılması bir yorumdur; belge onu sonuç cümlesi olarak değil, harcama
    yetkilisinin takdiri olarak yazar. Hurdaya ayırmada (28) komisyon zorunludur (28/1).

    Kalemlerin hepsi Md. 12/1 gerekçesiyle ayıklanandır: kayıp ve hasar dosyasının
    kayıttan düşme önerisi ayıklamaya konmaz, sayımda düşülür (25.09.2026 kullanıcı
    kararı, tasarım F8 ekleri 34). 27/1 paragrafı TMY 27/1'in lafzıyla yazılır.
    """
    gun = _gun(on)
    kalemler = _kalemler(batch)
    dusulecek = [k for k in _ayiklananlar(kalemler) if k.tmy_path in WEEDING_WRITE_OFF_PATHS]
    onaylanmayan = [k for k in dusulecek if k.state == WeedingItemState.NOT_APPROVED]
    etkin = [k for k in dusulecek if k.state != WeedingItemState.NOT_APPROVED]
    yol27 = [k for k in etkin if k.tmy_path == WeedingTmyPath.TMY_27]
    yol28 = [k for k in etkin if k.tmy_path == WeedingTmyPath.TMY_28]
    onayli = batch.status in (WeedingBatchStatus.APPROVED, WeedingBatchStatus.APPLIED)
    dayanak = (
        f"Seçim ve Ayıklama Komisyonunun {karar_metni(batch.commission_decision)} "
        "kararı ve Ayıklama tutanağı"
    )
    info = [
        ("Dayanak", dayanak),
        ("Ders yılı", batch.school_year.name),
        (
            "Kayıttan düşülecek",
            f"{len(etkin)} kaynak (TMY md. 27/1: {len(yol27)}, TMY md. 28: {len(yol28)})",
        ),
        ("Harcama yetkilisinin onayı", _tarih(batch.approved_on) if onayli else "Onay bekliyor"),
    ]
    paragraflar: list[str] = []
    if yol27:
        paragraflar.append(
            "Yıpranma, kırılma veya bozulma gibi nedenlerle kullanılamaz hâle gelen kaynaklar "
            "Kayıttan Düşme Teklif ve Onay Tutanağı ve Varlık İşlem Fişi düzenlenerek "
            "kayıtlardan çıkarılır (Taşınır Mal Yönetmeliği md. 27/1). Kasıt, kusur, ihmal veya "
            "tedbirsizlik olup olmadığını harcama yetkilisi değerlendirir (md. 27/3); olağan "
            "kullanımdan kaynaklanan yıpranmadan dolayı sorumluluk aranmaz (md. 5/8)."
        )
    if yol28:
        paragraflar.append(
            "Ekonomik ömrünü tamamlamış ya da kullanılmasında yarar görülmeyen kaynaklar, "
            "harcama yetkilisinin belirleyeceği en az üç kişiden oluşan komisyonca değerlendirilir; "
            "hurdaya ayrılmasına karar verilenler harcama yetkilisinin onayıyla kayıtlardan "
            "çıkarılır (Taşınır Mal Yönetmeliği md. 28/1, 28/3, 28/4)."
        )
    komisyon = _tmy_komisyonu(batch, zorunlu=bool(yol28))
    notlar: list[str] = []
    if not komisyon:
        notlar.append(
            "Durumu belgeleyen tutanak, rapor ve benzeri belgelerin bulunması hâlinde Kayıttan "
            "Düşme Teklif ve Onay Tutanağı komisyon kurulması gerekmeksizin harcama yetkilisince "
            "onaylanabilir (Taşınır Mal Yönetmeliği md. 10/1-e). Ayıklama tutanağının bu belge "
            "sayılıp sayılmayacağını harcama yetkilisi değerlendirir; komisyon kurulacaksa en az "
            "üç kişidir."
        )
    tablolar = [
        _tablo(
            KAYITTAN_DUSME_TABLOLARI[yol],
            _DUSME_SUTUNLARI,
            [_dusme_satiri(i, k) for i, k in enumerate(grup, start=1)],
            "",
        )
        for yol, grup in ((WeedingTmyPath.TMY_27, yol27), (WeedingTmyPath.TMY_28, yol28))
        if grup
    ]
    if onaylanmayan:
        tablolar.append(
            _tablo(
                "KAYITTAN DÜŞÜLMEYEN KAYNAKLAR",
                [
                    _sutun("Sıra", 6, "sayi"),
                    _sutun("Barkod", 14),
                    _sutun("Kaynak adı", 32),
                    _sutun("Yazar", 18),
                    _sutun("Onaylanmama gerekçesi", 30),
                ],
                [
                    [
                        _h(i, "sayi"),
                        _h(_barkod(k.copy), "tek"),
                        _h(k.copy.work.title),
                        _h(k.copy.work.authors),
                        _h(_tek_satir(k.exclusion_reason)),
                    ]
                    for i, k in enumerate(onaylanmayan, start=1)
                ],
                "",
            )
        )
    return _baglam(
        baslik="KAYITTAN DÜŞME TEKLİF LİSTESİ",
        alt_baslik="Kayıttan Düşme Teklif ve Onay Tutanağına esas hazırlık çıktısı",
        gun=gun,
        info=info,
        paragraflar=paragraflar,
        tablolar=tablolar,
        notlar=notlar,
        imza_basligi="KOMİSYON" if komisyon else "",
        imzalar=komisyon,
        onay=_harcama_yetkilisi(batch),
        dipnot=TKYS_DIPNOTU,
    )


def write_off_pdf(batch: WeedingBatch, *, on: date | None = None) -> bytes:
    return _pdf(write_off_context(batch, on=on))


def destruction_report_context(batch: WeedingBatch, *, on: date | None = None) -> dict[str, Any]:
    """İmha tutanağı ŞABLONU (TMY 28/5) — imha tarihi, yeri ve yöntemi elle yazılır."""
    gun = _gun(on)
    kalemler = _imha_kalemleri(_kalemler(batch))
    return _baglam(
        baslik="İMHA TUTANAĞI",
        gun=gun,
        info=[
            ("Harcama yetkilisinin onayı", _tarih(batch.approved_on)),
            ("Kaynak sayısı", str(len(kalemler))),
            ("İmha tarihi", BOS_TARIH),
            ("İmha yeri", BOS_YER),
            ("İmha yöntemi", BOS_YER),
        ],
        paragraflar=[
            "Taşınır Mal Yönetmeliği md. 28/1'e göre oluşturulan komisyonca ekonomik değerinin "
            "olmadığına ya da teknik, sağlık, güvenlik ve benzeri nedenlerle imha edilmesinin "
            "şart olduğuna karar verilen ve harcama yetkilisinin "
            f"{_tarih(batch.approved_on)} tarihli onayıyla imhası uygun görülen aşağıdaki "
            "kütüphane kaynakları imha edilmiştir (md. 28/5). Bu tutanak aşağıda imzası "
            "bulunanlarca düzenlenmiştir.",
        ],
        tablolar=[
            _tablo(
                "",
                [
                    _sutun("Sıra", 6, "sayi"),
                    _sutun("Barkod", 15),
                    _sutun("Kaynak adı", 39),
                    _sutun("Yazar", 24),
                    _sutun("TKYS kodu", 16),
                ],
                [
                    [
                        _h(i, "sayi"),
                        _h(_barkod(k.copy), "tek"),
                        _h(k.copy.work.title),
                        _h(k.copy.work.authors),
                        _h(k.copy.external_asset_ref or "—"),
                    ]
                    for i, k in enumerate(kalemler, start=1)
                ],
                "",
            )
        ],
        notlar=[
            f"Taşınır Mal Yönetmeliği md. 28/5: “{TMY28_5_IMHA}” Tutanak imha sırasında "
            "doldurulur; imha tarihi, yeri ve yöntemi elle yazılır. İmha edilen taşınırlar "
            "Varlık İşlem Fişi düzenlenerek kayıtlardan çıkarılır (md. 28/7).",
        ],
        imza_basligi="KOMİSYON",
        imzalar=_tmy_komisyonu(batch, zorunlu=True),
    )


def destruction_report_pdf(batch: WeedingBatch, *, on: date | None = None) -> bytes:
    return _pdf(destruction_report_context(batch, on=on))


def transfer_items(batch: WeedingBatch) -> list[WeedingItem]:
    """Devredilecek (ya da devredilmiş) kalemler — teklif dışı bırakılanlar hariç."""
    return [k for k in _etkin(_ayiklananlar(_kalemler(batch))) if k.is_transfer]


def _hedefler(kalemler: Sequence[WeedingItem]) -> list[str]:
    """Devralacak kurumlar (sırasıyla, tekrarsız); yazılmamış kurum boş metindir."""
    return list(dict.fromkeys(_tek_satir(k.transfer_target) for k in kalemler))


def transfer_list_context(batch: WeedingBatch, *, on: date | None = None) -> dict[str, Any]:
    """Devir listesi (Md. 12/1 son cümlesi; TMY 24/2 ya da 31)."""
    gun = _gun(on)
    kalemler = transfer_items(batch)
    hedefler = _hedefler(kalemler)
    tek_hedef = len(hedefler) == 1
    yollar = {k.tmy_path for k in kalemler}
    info = [
        ("Seçim ve Ayıklama Komisyonu kararı", karar_metni(batch.commission_decision)),
        ("Ders yılı", batch.school_year.name),
        ("Devredilecek", f"{len(kalemler)} kaynak"),
    ]
    if tek_hedef:
        info.insert(0, ("Devralacak okul ya da kurum", hedefler[0] or KURUM_YAZILMADI))
    sutunlar = [
        _sutun("Sıra", 6, "sayi"),
        _sutun("Barkod", 14),
        _sutun("Kaynak adı", 27 if tek_hedef else 23),
        _sutun("Yazar", 16 if tek_hedef else 14),
        _sutun("Yayınevi", 14 if tek_hedef else 11),
        _sutun("Yıl", 7, "sayi"),
        _sutun("TKYS kodu", 16 if tek_hedef else 9),
    ]
    if not tek_hedef:
        sutunlar.append(_sutun("Devralacak", 16))
    satirlar = []
    for i, k in enumerate(kalemler, start=1):
        eser = k.copy.work
        satir = [
            _h(i, "sayi"),
            _h(_barkod(k.copy), "tek"),
            _h(eser.title),
            _h(eser.authors),
            _h(eser.publisher),
            _h(eser.publish_year or "", "sayi"),
            _h(k.copy.external_asset_ref or "—"),
        ]
        if not tek_hedef:
            kurum = _tek_satir(k.transfer_target) or KURUM_YAZILMADI
            satir.append(_h(f"{kurum} ({YOL_BELGE[k.tmy_path]})"))
        satirlar.append(satir)
    notlar: list[str] = []
    if WeedingTmyPath.TMY_24_2 in yollar:
        notlar.append(
            "MEB okuluna devirde Varlık İşlem Fişi düzenlenir ve bir nüshası devredilen harcama "
            "biriminin taşınır kayıt yetkilisine verilir (Taşınır Mal Yönetmeliği md. 24/2)."
        )
    if WeedingTmyPath.TMY_31 in yollar:
        notlar.append(
            "Başka bir kamu idaresine devir bedelsizdir (Taşınır Mal Yönetmeliği md. 31/1); "
            "çıkış Varlık İşlem Fişiyle yapılır ve bir nüshası devralan idareye verilir (md. 24/1)."
        )
    return _baglam(
        baslik="DEVİR LİSTESİ",
        gun=gun,
        info=info,
        paragraflar=[
            "Aşağıda bilgileri yazılı kütüphane kaynakları, kurumun düzeyine uygun olmadıkları için "
            "Seçim ve Ayıklama Komisyonu kararıyla ayıklanmış ve devredilmek üzere ayrılmıştır. "
            f"Okul Kütüphaneleri Yönetmeliği Md. 12/1: “{MD12_1_DEVIR}”",
        ],
        tablolar=[_tablo("", sutunlar, satirlar, NO_TRANSFER_MESSAGE)],
        notlar=notlar,
        imzalar=[
            {"name": "", "role": "Devreden — Kütüphane yöneticisi"},
            {
                "name": "",
                "role": (
                    f"Devralan — {hedefler[0]}"
                    if tek_hedef and hedefler[0]
                    else "Devralan okul ya da kurum"
                ),
            },
        ],
        onay=_harcama_yetkilisi(batch),
        dipnot=DEVIR_DIPNOTU,
    )


def transfer_list_pdf(batch: WeedingBatch, *, on: date | None = None) -> bytes:
    return _pdf(transfer_list_context(batch, on=on))


#: Devir listesi XLSX sütunları (başlık, genişlik).
DEVIR_XLSX_SUTUNLARI: Final[tuple[tuple[str, int], ...]] = (
    ("Sıra", 6),
    ("Barkod", 14),
    ("Kaynak adı", 48),
    ("Yazar(lar)", 30),
    ("Yayınevi", 24),
    ("Yayın yılı", 10),
    ("ISBN", 16),
    ("TKYS kodu", 18),
    ("Devralacak okul ya da kurum", 34),
    ("TMY yolu", 34),
)


def transfer_list_xlsx(batch: WeedingBatch, *, on: date | None = None) -> bytes:
    """Devir listesi (XLSX) — PDF'le aynı satırlar; devralan kurum kendi kaydına aktarabilir."""
    gun = _gun(on)
    kalemler = transfer_items(batch)
    config = SchoolConfig.load()
    wb = Workbook()
    wb.properties.title = DEVIR_LISTESI_ADI
    ws = wb.active
    assert ws is not None  # yeni çalışma kitabında etkin sayfa daima vardır
    ws.title = DEVIR_LISTESI_ADI
    kalin = Font(bold=True)
    ws.append([_okul_adi(config) or "—"])
    ws.append([DEVIR_LISTESI_ADI])
    ws.append(
        [
            f"Düzenlenme tarihi: {_tarih(gun)} · Seçim ve Ayıklama Komisyonu kararı: "
            f"{karar_metni(batch.commission_decision)} · Ders yılı: {batch.school_year.name}"
        ]
    )
    ws["A1"].font = kalin
    ws["A2"].font = Font(bold=True, size=13)
    ws.append([])  # boş ayraç satırı (hücre oluşturmaz: `max_row` değişmez)
    ws.append([ad for ad, _ in DEVIR_XLSX_SUTUNLARI])
    # Başlık satırı eklendikten SONRA okunur: boş `append` hücre açmadığı için önceden
    # `max_row + 1` bir satır geride kalıyordu (biçim boş satıra, bölme başlığın üstüne).
    baslik_satiri = ws.max_row
    dolgu = PatternFill("solid", fgColor="E8EEF6")
    ince = Side(style="thin", color="B7C3D0")
    for sutun, (_, genislik) in enumerate(DEVIR_XLSX_SUTUNLARI, start=1):
        hucre = ws.cell(row=baslik_satiri, column=sutun)
        hucre.font = kalin
        hucre.fill = dolgu
        hucre.border = Border(bottom=ince)
        hucre.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(sutun)].width = genislik
    for i, k in enumerate(kalemler, start=1):
        eser = k.copy.work
        ws.append(
            [
                i,
                _barkod(k.copy),
                eser.title,
                eser.authors,
                eser.publisher,
                eser.publish_year,
                eser.isbn13 or eser.isbn,
                k.copy.external_asset_ref,
                _tek_satir(k.transfer_target),
                YOL_BELGE[k.tmy_path],
            ]
        )
    ws.freeze_panes = ws.cell(row=baslik_satiri + 1, column=1)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def weeding_document(batch: WeedingBatch, slug: str, bicim: str = PDF) -> bytes:
    """Belgeyi üretir (basılabilirlik ve biçim önce denetlenir)."""
    ensure_weeding_document(batch, slug, bicim)
    if bicim == XLSX:
        return transfer_list_xlsx(batch)
    uretici = {
        TEKLIF_LISTESI: proposal_list_pdf,
        AYIKLAMA_TUTANAGI: weeding_report_pdf,
        KAYITTAN_DUSME: write_off_pdf,
        IMHA_TUTANAGI: destruction_report_pdf,
        DEVIR_LISTESI: transfer_list_pdf,
    }[slug]
    return uretici(batch)


def weeding_document_filename(slug: str, bicim: str = PDF, gun: date | None = None) -> str:
    return belge_dosya_adi(_BELGE_TANIMLARI[slug].ad, gun, bicim=bicim)


# ---------------------------------------------------------------------------
# E8 — el yazması ve nadir eserler listesi (Md. 12/2)
# ---------------------------------------------------------------------------
def rare_works_context(
    submission: RareWorksSubmission, *, on: date | None = None
) -> dict[str, Any]:
    gun = _gun(on)
    satirlar = list(selectors_ayiklama.submission_items(submission))
    if not satirlar:
        raise ValidationError(RARE_EMPTY_MESSAGE)
    karar = submission.commission_decision
    info = [
        ("Seçim ve Ayıklama Komisyonu kararı", karar_metni(karar) if karar else "Bağlanmadı"),
        ("Ders yılı", submission.school_year.name),
        ("Eser sayısı", str(len(satirlar))),
    ]
    if submission.status == RareWorksSubmissionStatus.SENT and submission.sent_on is not None:
        yazi = _tek_satir(submission.sent_document_no)
        info.append(
            (
                "Genel Müdürlüğe gönderim",
                f"{_tarih(submission.sent_on)} tarihli ve {yazi} sayılı yazıyla"
                if yazi
                else f"{_tarih(submission.sent_on)} tarihinde",
            )
        )
    return _baglam(
        baslik="EL YAZMASI VE NADİR ESERLER LİSTESİ",
        gun=gun,
        info=info,
        paragraflar=[
            "Okul kütüphanesinde bulunan ve Seçim ve Ayıklama Komisyonunca el yazması ya da nadir "
            "eser olarak tespit edilen kaynaklar aşağıda gösterilmiştir. Okul Kütüphaneleri "
            f"Yönetmeliği Md. 12/2: “{MD12_2}”",
        ],
        tablolar=[
            _tablo(
                "",
                [
                    _sutun("Sıra", 6, "sayi"),
                    _sutun("Barkod", 14),
                    _sutun("Kaynak adı", 29),
                    _sutun("Yazar", 17),
                    _sutun("Yayınevi", 13),
                    _sutun("Yıl", 7, "sayi"),
                    _sutun("Yer numarası", 14),
                ],
                [
                    [
                        _h(i, "sayi"),
                        _h(_barkod(s.copy), "tek"),
                        _h(s.copy.work.title),
                        _h(s.copy.work.authors),
                        _h(s.copy.work.publisher),
                        _h(s.copy.work.publish_year or "", "sayi"),
                        _h(s.copy.work.call_number or "—"),
                    ]
                    for i, s in enumerate(satirlar, start=1)
                ],
                "",
            )
        ],
        imza_basligi="SEÇİM VE AYIKLAMA KOMİSYONU",
        imzalar=komisyon_imzalari(karar),
    )


def rare_works_pdf(submission: RareWorksSubmission, *, on: date | None = None) -> bytes:
    return _pdf(rare_works_context(submission, on=on))


# ---------------------------------------------------------------------------
# E16 — bağış ön kayıt listesi (Md. 10/3)
# ---------------------------------------------------------------------------
def donation_intake_context(intake: DonationIntake, *, on: date | None = None) -> dict[str, Any]:
    gun = _gun(on)
    kalemler = list(intake.items.all().order_by("pk"))
    if not kalemler:
        raise ValidationError(DONATION_EMPTY_MESSAGE)
    info = [("Geliş tarihi", _tarih(intake.received_date))]
    bagisci = _tek_satir(intake.donor_name)
    if bagisci:
        info.append(("Bağışçı", bagisci))
    info += [
        ("Kalem", f"{len(kalemler)} kaynak, {sum(k.copies for k in kalemler)} nüsha"),
        ("Durum", str(intake.get_status_display())),
    ]
    notlar = [
        "“Kabul / Ret” sütunu komisyon değerlendirmesinde doldurulur. Komisyon kararıyla kabul "
        "edilen kaynaklar katalog kaydına alınır; reddedilenler gerekçesiyle kayıtta kalır.",
    ]
    if intake.status == DonationIntakeStatus.CANCELLED:
        notlar.append("Bu bağış ön kaydı iptal edilmiştir.")
    return _baglam(
        baslik="BAĞIŞ ÖN KAYIT LİSTESİ",
        gun=gun,
        info=info,
        paragraflar=[
            "Okul kütüphanesine bağış olarak gelen ve aşağıda bilgileri yazılı kaynaklar Seçim ve "
            "Ayıklama Komisyonunun değerlendirmesine sunulur; kaynaklar komisyon kararına kadar "
            f"katalog kaydına alınmaz. Okul Kütüphaneleri Yönetmeliği Md. 10/3: “{MD10_3}”",
        ],
        tablolar=[
            _tablo(
                "",
                [
                    _sutun("Sıra", 6, "sayi"),
                    _sutun("Kaynak adı", 27),
                    _sutun("Yazar", 15),
                    _sutun("Yayınevi", 13),
                    _sutun("Yıl", 7, "sayi"),
                    _sutun("ISBN", 13),
                    _sutun("Nüsha", 8, "sayi"),
                    _sutun("Kabul / Ret", 11),
                ],
                [
                    [
                        _h(i, "sayi"),
                        _h(k.title),
                        _h(k.authors),
                        _h(k.publisher),
                        _h(k.publish_year or "", "sayi"),
                        _h(k.isbn),
                        _h(k.copies, "sayi"),
                        _h(""),
                    ]
                    for i, k in enumerate(kalemler, start=1)
                ],
                "",
            )
        ],
        notlar=notlar,
        tekil_imza={"date": _tarih(gun), "name": "", "role": "Hazırlayan — Kütüphane yöneticisi"},
    )


def donation_intake_pdf(intake: DonationIntake, *, on: date | None = None) -> bytes:
    return _pdf(donation_intake_context(intake, on=on))


# ---------------------------------------------------------------------------
# Bağış değerlendirme sonucu (Md. 10/3; TMY 16/1) — 25.09.2026 kullanıcı kararı, F8 ekleri 13
# ---------------------------------------------------------------------------
def donation_result_blocker(intake: DonationIntake) -> str:
    """Bağış değerlendirme sonucu basılamıyorsa nedeni, basılabiliyorsa boş metin.

    Yalnız komisyon kararı uygulanmış ("Karar işlendi") ön kayıtta basılır: sonuç,
    kararın kalem kalem dökümüdür.
    """
    if intake.status != DonationIntakeStatus.DECIDED:
        return DONATION_NOT_DECIDED_MESSAGE
    if not intake.items.exists():
        return DONATION_EMPTY_MESSAGE
    return ""


def _nusha_sayisi(kalemler: Sequence[DonationIntakeItem]) -> str:
    return f"{len(kalemler)} kaynak, {sum(k.copies for k in kalemler)} nüsha"


def donation_result_context(intake: DonationIntake, *, on: date | None = None) -> dict[str, Any]:
    """Bağış değerlendirme sonucu — komisyona sunulan ön kaydın karar sonrası dökümü.

    TMY'de "bağış kabul tutanağı" diye bir belge YOKTUR (10/1'in belge listesi); bağış
    teslim alındığında taşınır kayıt yetkilisi Varlık İşlem Fişi düzenler ve bir
    nüshasını bağışçıya verir (16/1). Bu çıktı o fişe dayanak ve bağışçıya bilgidir:
    kabul edilen ve reddedilen kalemler, ret gerekçeleri, kararın tarih ve sayısı,
    edinim tarihi. Resmî belge sanısı doğurmasın diye adı "tutanak" değildir ve
    dipnot TKYS'yi anar. Bağışçının adı (şifreli alan) yalnız bu belgeye çözülür; uç
    yalnız yönetici kipindedir.
    """
    engel = donation_result_blocker(intake)
    if engel:
        raise ValidationError(engel)
    gun = _gun(on)
    kalemler = list(intake.items.all().order_by("pk"))
    kabul = [k for k in kalemler if k.decision == DonationItemDecision.ACCEPTED]
    ret = [k for k in kalemler if k.decision == DonationItemDecision.REJECTED]
    karar = intake.commission_decision
    info = [("Geliş tarihi", _tarih(intake.received_date))]
    bagisci = _tek_satir(intake.donor_name)
    if bagisci:
        info.append(("Bağışçı", bagisci))
    info.append(("Seçim ve Ayıklama Komisyonu kararı", karar_metni(karar)))
    edinim = intake.acquisition
    if edinim is not None and edinim.deleted_at is None:
        info.append(("Edinim tarihi", _tarih(edinim.date)))
    info.append(("Sonuç", f"Kabul: {_nusha_sayisi(kabul)} · Ret: {_nusha_sayisi(ret)}"))
    tablolar = [
        _tablo(
            "KABUL EDİLEN KAYNAKLAR",
            [
                _sutun("Sıra", 6, "sayi"),
                _sutun("Kaynak adı", 34),
                _sutun("Yazar", 26),
                _sutun("Yıl", 7, "sayi"),
                _sutun("ISBN", 17),
                _sutun("Nüsha", 10, "sayi"),
            ],
            [
                [
                    _h(i, "sayi"),
                    _h(k.title),
                    _h(k.authors),
                    _h(k.publish_year or "", "sayi"),
                    _h(k.isbn),
                    _h(k.copies, "sayi"),
                ]
                for i, k in enumerate(kabul, start=1)
            ],
            "Komisyon hiçbir kaynağı kabul etmedi.",
        )
    ]
    if ret:
        tablolar.append(
            _tablo(
                "REDDEDİLEN KAYNAKLAR",
                [
                    _sutun("Sıra", 6, "sayi"),
                    _sutun("Kaynak adı", 40),
                    _sutun("Nüsha", 9, "sayi"),
                    _sutun("Ret gerekçesi", 45),
                ],
                [
                    [
                        _h(i, "sayi"),
                        _h(k.title),
                        _h(k.copies, "sayi"),
                        _h(_tek_satir(k.reject_reason)),
                    ]
                    for i, k in enumerate(ret, start=1)
                ],
                "",
            )
        )
    return _baglam(
        baslik="BAĞIŞ DEĞERLENDİRME SONUCU",
        gun=gun,
        info=info,
        paragraflar=[
            "Okul kütüphanesine bağış olarak gelen kaynaklar Seçim ve Ayıklama Komisyonunun "
            f"{karar_metni(karar)} kararıyla değerlendirilmiştir; sonuç aşağıda gösterilmiştir. "
            f"Okul Kütüphaneleri Yönetmeliği Md. 10/3: “{MD10_3}”",
        ],
        tablolar=tablolar,
        notlar=[BAGIS_TMY_NOTU],
        tekil_imza={"date": _tarih(gun), "name": "", "role": "Hazırlayan — Kütüphane yöneticisi"},
        dipnot=BAGIS_DIPNOTU,
    )


def donation_result_pdf(intake: DonationIntake, *, on: date | None = None) -> bytes:
    return _pdf(donation_result_context(intake, on=on))
