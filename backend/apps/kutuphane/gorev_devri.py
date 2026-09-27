"""Görev devri: açık işler özeti ve Görev devri notu (E18; tasarım §4.4 SU-25, §10; F11).

Kütüphane yöneticisi değişince (tayin, görev değişikliği, emeklilik) yetkinin
ayrılan kişide kalmaması gerekir. Tek akış Ayarlar → Güvenlik → **Görev Devri**
kartındadır (yalnız yönetici kipi):

1. **Parola ve kurtarma anahtarı birlikte yenilenir** —
   `app_password.start_handover` (TEK atomik yazım, önceki dosya arşive kopyalanır).
2. **Yeni anahtar saklanır ve doğrulanır** — F1'in paneli ve
   `security/recovery-key/confirm/` (aynı damga).
3. **Görev devri notu (E18) basılır** — bu modül. Not ancak güncel kurtarma
   bölümünde görev devri damgası VE doğrulama damgası varken basılır; aksi 409
   `gorev_devri_eksik`.

**Kişisel veri.** Görevi devreden ve devralanın adları yalnız istek gövdesinde
gelir ve yalnız PDF'e basılır: programda SAKLANMAZ, günlüğe ve dosya adına
yazılmaz (boş bırakılırsa elle doldurulacak çizgi basılır). Belgedeki öbür her şey
kişisizdir: açık işler yalnız sayıdır (kim, ne kitap yok).

**Dürüst dil (TB17, TB23; F11 düzeltme turu).** Görev devri kayıtların şifreleme
anahtarını (DEK) DEĞİŞTİRMEZ — bütün alanları yeni anahtarla yeniden şifrelemek, kör
indeksleri, verilmiş kart defterini ve yedek anahtarını yeniden kurmak demektir ve v1
dışında kalır. Sonucu yalnız "eski yedekler" değildir: eski parola ya da eski anahtar,
ESKİ bir güvenlik başlığıyla (devirden önce alınmış herhangi bir yedeğin içindeki,
veri klasöründeki arşiv dosyası, yedek klasöründeki ilk kurulum yedeği) birlikte
DEK'i verir; yedeklerin anahtarı DEK'ten türediği için bu, devirden SONRA alınan
yedekleri de açar, arşiv dosyası `guvenlik.json` yerine konursa bu bilgisayardaki
güncel veriyi de. Görev devri bu yüzden görevi devredenin bu bilgisayara (masa
hesabının parolası değişir) ve yedeklere erişimi kesildiğinde anlam taşır; not bunu
ve sayıları yazar. Mevzuat atıfları depodaki metinden doğrulanır ve fıkranın
öznesine bağlanır: KVKK md. 12/4'ün öznesi veri sorumlusudur (okul) — yükümlülük
görevden ayrılınca da sürer; Yönerge md. 6/4 çalışması sona eren kullanıcıyı anlatır
(şifrelerin ve donanımın iadesi, erişim haklarının kaldırılması), okulda kalan
kişinin görev değişikliğinde kıyasen uygulanır.

PDF yalnız `shared.pdf.html_to_pdf` kapısından üretilir. Bu modül veritabanına
YAZMAZ.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.kutuphane import selectors_dolasim, selectors_kuyruk, selectors_sayim
from apps.kutuphane.models import (
    OPEN_CASE_RESOLUTIONS,
    CaseResolution,
    CopyRepair,
    Delivery,
    DeliveryStatus,
    DonationIntake,
    DonationIntakeStatus,
    LabelPrintBatchStatus,
    Loan,
    LoanStatus,
    LossDamageCase,
    WeedingBatch,
    WeedingBatchStatus,
)
from apps.kutuphane.services import saklama
from apps.okul import selectors as okul_selectors
from apps.okul.models import SchoolConfig
from apps.okul.services import app_password, live_restore
from shared.letterhead import letterhead_context
from shared.pdf import html_to_pdf

#: Belgenin adı (sözlük §1 "Görev devri"; §2 E18) — başlık ve indirme adı buradan.
BELGE_ADI: Final = "Görev Devri Notu"
SABLON: Final = "documents/gorev_devri_notu.html"

#: Ad ve ek not sınırları (sayfa bütçesi bu uzunluklarla sınanır).
AD_EN_COK: Final = 120
NOT_EN_COK: Final = 600
#: Ek notun en çok satır sayısı (F11 düzeltme turu): not kutusu satır sonlarını korur
#: (`white-space: pre-wrap`); 600 karakter içinde kısa satırlarla yazılmış bir liste
#: (ör. 47 satır) notu üç sayfaya taşıyordu. Fazla satırlar son satırda " · " ile
#: birleşir — metin kaybolmaz, sayfa bütçesi (en çok iki sayfa) korunur.
NOT_SATIR_EN_COK: Final = 8

EKSIK_MESAJI: Final = (
    "Görev devri notu, görev devri başlatılıp yeni kurtarma anahtarının saklandığı "
    "doğrulanmadan basılamaz. Ayarlar → Güvenlik → Görev Devri kartındaki adımları "
    "tamamlayın."
)

#: Teslim edilenler — belgeye boş kutuyla basılır, toplantıda elle işaretlenir.
#: F11 düzeltme turu: yeni parolayı görevi devralan KENDİSİ belirler (ekran ve kılavuz),
#: devreden onu teslim edemez; masa hesabının parolası DEĞİŞTİRİLİR — görev devri
#: kayıtların şifreleme anahtarını değiştirmediği için görevi devredenin bu bilgisayara
#: erişimi kesilmelidir (Yönerge md. 6/4 "erişim hakları kaldırılır").
TESLIM_KALEMLERI: Final[tuple[str, ...]] = (
    "Yeni yönetici parolası: görevi devralan belirledi; parolayı bilen ikinci görevliye "
    "kapalı zarfla bildirildi",
    "Yeni kurtarma anahtarı çıktısı: kapalı zarfta, müdürlükte saklanmak üzere",
    "Kütüphane masası Windows hesabının parolası değiştirildi; yeni parola görevi "
    "devralana verildi",
    "Barkod okuyucu, etiket yazıcısı ve kalan etiket tabakaları",
    "USB bellekteki şifreli yedekler",
)


@dataclass(frozen=True)
class AcikIs:
    """Açık işler özetinin bir satırı (kişisiz sayı)."""

    anahtar: str
    etiket: str
    sayi: int

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.anahtar, "label": self.etiket, "count": self.sayi}


def acik_isler() -> list[AcikIs]:
    """Devir anındaki açık işlerin KİŞİSİZ sayıları (kim, hangi kitap yok)."""
    havuz = okul_selectors.leave_pool_counts()
    canli_sayim = selectors_sayim.live_stocktake()
    return [
        AcikIs(
            "acik_odunc",
            "İade edilmemiş ödünç",
            Loan.objects.filter(status=LoanStatus.OPEN).count(),
        ),
        AcikIs("geciken_odunc", "İade tarihi geçmiş ödünç", selectors_dolasim.overdue_count()),
        AcikIs(
            "acik_teslim",
            "Geri alınmamış teslim (sınıf kitaplığı ve öğretmen)",
            Delivery.objects.filter(status=DeliveryStatus.OPEN).count(),
        ),
        AcikIs(
            "acik_dosya",
            "Açık kayıp/hasar dosyası",
            LossDamageCase.objects.filter(resolution__in=OPEN_CASE_RESOLUTIONS).count(),
        ),
        AcikIs(
            "bedel_bekleyen",
            "Bunlardan bedel adımında bekleyen",
            LossDamageCase.objects.filter(
                resolution__in=(CaseResolution.PRICE_DETERMINED, CaseResolution.PRICE_RECEIVED)
            ).count(),
        ),
        AcikIs(
            "onarimda",
            "Onarımdaki nüsha",
            CopyRepair.objects.filter(returned_on__isnull=True).count(),
        ),
        AcikIs("canli_sayim", "Sonuçlanmamış sayım", 1 if canli_sayim is not None else 0),
        AcikIs(
            "ayiklama",
            "Sonuçlanmamış ayıklama teklifi",
            WeedingBatch.objects.exclude(
                status__in=(WeedingBatchStatus.APPLIED, WeedingBatchStatus.CANCELLED)
            ).count(),
        ),
        AcikIs(
            "bagis",
            "Karar bekleyen bağış ön kaydı",
            DonationIntake.objects.filter(status=DonationIntakeStatus.PENDING).count(),
        ),
        AcikIs(
            "etiket_partisi",
            "Basım onayı bekleyen etiket partisi",
            selectors_kuyruk.label_batches(status=LabelPrintBatchStatus.PENDING).count(),
        ),
        AcikIs(
            "ayrilis_havuzu",
            "Ayrılış kararı bekleyen kişi",
            int(havuz.get("student_count", 0)) + int(havuz.get("personnel_count", 0)),
        ),
        # F11 (§6.4): saklama onayı da devredilen bir iştir — onay beklemesinin altı ay
        # sınırı görevi devralanın üzerine kalır. Kayıt yazmayan önizleme; yalnız sayı.
        AcikIs(
            "saklama_onayi",
            "Saklama süresi dolmuş, onay bekleyen kayıt",
            int(saklama.plan_hesapla().ozet()["total"]),
        ),
    ]


def _an(deger: str | None) -> datetime | None:
    if not deger:
        return None
    try:
        an = datetime.fromisoformat(deger)
    except ValueError:
        return None
    return timezone.localtime(an if timezone.is_aware(an) else timezone.make_aware(an))


def _gg_aa_yyyy_ss_dd(an: datetime | None) -> str:
    return f"{an:%d.%m.%Y %H:%M}" if an else ""


@dataclass(frozen=True)
class EskiYedekler:
    """Devirden önce alınmış (eski parola ve eski anahtarla açılabilen) kopyalar."""

    yedek_sayisi: int
    en_eski: str
    arsiv_sayisi: int


def eski_yedekler(devir_ani: datetime | None) -> EskiYedekler:
    """Bu bilgisayardaki yedeklerden devirden önce alınanlar ve arşiv dosyaları.

    Yedek listesi `live_restore.list_backups()`'tandır (değişme anı yerel dilim).
    Devir yoksa (henüz başlatılmadı) hepsi "eski" sayılır. USB bellektekiler
    programın göremediği kopyalardır; belge onları ayrıca anar.
    """
    liste = live_restore.list_backups().get("backups", [])
    eskiler: list[datetime] = []
    for satir in liste:
        an = _an(str(satir.get("modified_at") or ""))
        if an is None:
            continue
        if devir_ani is None or an < devir_ani:
            eskiler.append(an)
    arsivler = sorted(
        app_password.state_path().parent.glob(f"{app_password.STATE_ARCHIVE_PREFIX}*.json")
    )
    return EskiYedekler(
        yedek_sayisi=len(eskiler),
        en_eski=f"{min(eskiler):%d.%m.%Y}" if eskiler else "",
        arsiv_sayisi=len(arsivler),
    )


def durum() -> dict[str, Any]:
    """Görev Devri kartının okuduğu özet (kişisel veri yok)."""
    bilgi = app_password.handover_info()
    baslangic = _an(bilgi["started_at"]) if bilgi else None
    dogrulandi = _an(bilgi["confirmed_at"]) if bilgi else None
    eski = eski_yedekler(baslangic)
    return {
        "started_at": baslangic.isoformat(timespec="seconds") if baslangic else None,
        "confirmed_at": dogrulandi.isoformat(timespec="seconds") if dogrulandi else None,
        "note_available": baslangic is not None and dogrulandi is not None,
        "open_work": [satir.as_dict() for satir in acik_isler()],
        "old_backup_count": eski.yedek_sayisi,
        "oldest_backup": eski.en_eski,
        "archive_count": eski.arsiv_sayisi,
    }


def _ciftler(satirlar: list[AcikIs]) -> list[tuple[AcikIs, AcikIs | None]]:
    """Açık işler iki sütunda basılır (sayfa bütçesi): sol sütun ilk yarı, sağ ikinci yarı."""
    yari = (len(satirlar) + 1) // 2
    sol, sag = satirlar[:yari], satirlar[yari:]
    return [(s, sag[i] if i < len(sag) else None) for i, s in enumerate(sol)]


class GorevDevriEksik(ValueError):
    """Devir başlatılmadı ya da yeni anahtar doğrulanmadı — not basılmaz (409)."""


def not_dosya_adi(an: datetime | None = None) -> str:
    """'Görev-Devri-Notu_27.09.2026.pdf' — yerel gün; ad taşımaz."""
    gun = timezone.localtime(an) if an else timezone.localtime()
    return f"{BELGE_ADI.replace(' ', '-')}_{gun:%d.%m.%Y}.pdf"


def _temiz(metin: str, sinir: int, *, en_cok_satir: int | None = None) -> str:
    """Denetim karakterlerini atar, boşlukları sadeleştirir, sınırda keser.

    `en_cok_satir` verilirse fazla satırlar son satırda " · " ile birleşir (sayfa
    bütçesi — satır sayısı karakter sınırından bağımsız olarak sayfayı uzatır).
    """
    satirlar = [
        " ".join("".join(ch for ch in satir if ch.isprintable()).split())
        for satir in (metin or "").splitlines()
    ]
    dolu = [s for s in satirlar if s]
    if en_cok_satir is not None and len(dolu) > en_cok_satir:
        dolu = [*dolu[: en_cok_satir - 1], " · ".join(dolu[en_cok_satir - 1 :])]
    return "\n".join(dolu)[:sinir].strip()


@sensitive_variables("devreden", "devralan", "ek_not", "baglam")
def not_pdf(*, devreden: str = "", devralan: str = "", ek_not: str = "") -> bytes:
    """E18 PDF'i. Devir + doğrulama damgası yoksa `GorevDevriEksik`."""
    bilgi = app_password.handover_info()
    if not bilgi or not bilgi.get("confirmed_at"):
        raise GorevDevriEksik(EKSIK_MESAJI)
    baslangic = _an(bilgi["started_at"])
    dogrulandi = _an(bilgi["confirmed_at"])
    eski = eski_yedekler(baslangic)
    config = SchoolConfig.load()
    baglam = {
        **letterhead_context(
            school_name=config.school_name,
            district=config.district,
            principal_name=config.principal_name,
        ),
        "document_title": "GÖREV DEVRİ NOTU",
        "issued_on": f"{timezone.localdate():%d.%m.%Y}",
        "asset_no": config.demirbas_no.strip(),
        "devreden": _temiz(devreden, AD_EN_COK).replace("\n", " "),
        "devralan": _temiz(devralan, AD_EN_COK).replace("\n", " "),
        "ek_not": _temiz(ek_not, NOT_EN_COK, en_cok_satir=NOT_SATIR_EN_COK),
        "devir_ani": _gg_aa_yyyy_ss_dd(baslangic),
        "devir_gunu": f"{baslangic:%d.%m.%Y}" if baslangic else "",
        "dogrulama_ani": _gg_aa_yyyy_ss_dd(dogrulandi),
        "teslim_kalemleri": TESLIM_KALEMLERI,
        "acik_is_ciftleri": _ciftler(acik_isler()),
        "eski_yedek_sayisi": eski.yedek_sayisi,
        "en_eski_yedek": eski.en_eski,
        "arsiv_sayisi": eski.arsiv_sayisi,
        "mudur": (config.principal_name or "").strip(),
    }
    return html_to_pdf(render_to_string(SABLON, baglam))
