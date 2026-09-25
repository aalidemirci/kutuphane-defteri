"""Ayıklama — Seçim ve Ayıklama Komisyonu teklifi, harcama yetkilisi onayı, TMY yolu (F8).

OYS `apps/kutuphane/weeding.py`'den UYARLA (tasarım §12): rol, `by_user` ve
`approved_by` (kullanıcı hesabı) düştü; harcama yetkilisinin adı şifreli serbest
metindir. Zincir ikiye ayrıldı (D15): ayıklamaya **Seçim ve Ayıklama
Komisyonu** karar verir (Md. 12/1: "Seçim ve Ayıklama Komisyonu tarafından ...
ayıklanmasına karar verilen kaynaklar, bir tutanakla tespit edilerek Taşınır
Mal Yönetmeliği hükümlerine göre kayıtlardan düşümü yapılır"); kayıttan düşmeyi
ve devri **harcama yetkilisi** onaylar (TMY 10/1-e, 28/4; devirde 24, 31).

KURALLAR (her biri testle kilitli — `tests/test_ayiklama.py`):

1. **E7 tablosu** (tasarım §10; `models.WEEDING_PATHS` tek kaynak): yıpranma →
   27/1 ya da ekonomik ömrü bittiyse 28; bilimsel değer kaybı ve 10. madde
   ölçütlerine aykırılık → 28; düzeye uygunsuzluk → YALNIZ devir (24/2 MEB okulu,
   31 başka idare). **Devir yalnız düzeye uygunsuzlukla, düzeye uygunsuzluk yalnız
   devirle; 10/1-b gerekçeli kalem 28 yoluna GİDEMEZ** (Md. 12/1: "10 uncu maddenin
   birinci fıkrasının (b) bendine uygun olmayan kaynaklar uygun okullara veya
   kurumlara devredilir"). Kapı üç katmandadır: servis iletisi, DB kısıtı
   (`ck_weedingitem_e7_path`, `ck_weedingitem_criterion`) ve uygulamada yeniden
   denetim.
2. **Nadir eser ayıklanamaz** (programın kuralı — D14; Md. 12/2 nadir eserin
   listesinin Genel Müdürlüğe gönderilmesini düzenler): `Copy.is_rare_or_manuscript`
   işaretli nüsha teklife eklenemez; teklif sürerken işaretlenirse komisyon
   kararı bağlanamaz (komisyon o kalemi "ayıklanmasına karar vermedi" diye
   işaretler), onay ve uygulama reddedilir. Nadir eserin yolu Genel Müdürlüğe
   gönderilen listedir (`services.rare_works`).
3. **Yalnız raftaki nüsha** ayıklanır: açık ödünç, açık teslim ya da çözülmemiş
   kayıp/hasar dosyası olan nüsha konamaz; onarımdaki nüsha önce onarımdan
   döner; kayıp nüsha ayıklanmaz (Md. 12/1 gerekçelerinden değildir — kaydı
   sayımda kapanır); kayıttan düşülmüş ve devredilmiş nüsha zaten çıkmıştır.
   Bir nüsha aynı anda yalnız bir süren teklifte bulunur.
4. **F7'nin kayıttan düşme önerisi ayıklanmaz** ("Kayıttan düşme önerildi" ya da
   "Bedelle başka eser alındı" ile kapanmış dosya — 25.09.2026 kullanıcı kararı,
   tasarım F8 ekleri 34): Md. 12/1'in bentleri kaybı ve hasarı saymaz; kayıp ve
   hasar dosyasının önerisi sayımda TMY 27/1 yolundan, kayıp/hasar tutanağıyla
   komisyonsuz (harcama yetkilisinin onayıyla — 10/1-e) düşülür. Aday listesi
   önerileri almaz; ekran onları ayrı gösterir ve teklife eklenmeleri reddedilir.
   Hasar önerisi yalnız EKLEMEDE engeldir: teklif sürerken yazılan öneri
   komisyonun Md. 12/1 gerekçesiyle verdiği kararı düşürmez (uygulanırsa nüsha
   ayıklamayla çıkar, öneri boşa düşer).
5. **Durum makinesi** (`WeedingBatchStatus`): taslak → komisyona sunuldu →
   komisyon kararı bağlandı → harcama yetkilisi onayladı → uygulandı. Kalem
   silme yalnız taslakta; teklifi geri çekmek (sunulmuş, kararı bağlanmış ya da
   onaylanmış teklif) onu bütün sonraki kayıtlarıyla taslağa döndürür; uygulanmamış
   teklif iptal edilebilir. Nüsha durumu YALNIZ uygulamada değişir. Geri çekilen
   teklife AYNI komisyon kararı ancak kalemler o kararın ayıklanmasına karar
   verdiği kalemlerin içinde kaldıysa yeniden bağlanır (yeni kalem, değişen
   gerekçe ya da yol, komisyonun ayıklamadığı kalem → yeni karar gerekir).
6. **Karar türü "Ayıklama"dır** (D7 — `commissions.require_decision_type`).
7. **Onay** (TMY): harcama yetkilisinin adı ve onay tarihi zorunludur; onay
   tarihi bugünden sonra ve komisyon kararından önce olamaz (VİF dayanağını
   oluşturan belgeden önceki tarihi taşıyamaz — 10/1-a). Hurdaya ayırma (28)
   yolunda kalem varsa TMY komisyonunun adları zorunludur ve en az üç kişidir
   (28/1); 27/1 yolunda komisyon isteğe bağlıdır: durumu belgeleyen tutanak varsa
   harcama yetkilisi komisyon kurulmadan onaylar (10/1-e) — Ayıklama tutanağının
   bu tutanak sayılıp sayılmayacağı harcama yetkilisinin değerlendirmesidir. İmha
   kararı yalnız 28 yolunda ve kalem düzeyindedir (28/5; kapsam dışı 28 kalemi
   için 28/8). Devir kaleminde devralacak kurum onaydan önce yazılır.
8. **Uygulama TEK işlemdir**: TMY 32/3 durdurma kapısı (`tmy_kapisi.ensure_open`)
   kayıttan düşme ve devir için ayrı ayrı sorulur; her kalem yeniden denetlenir
   (kural 2-3) ve nüsha "Rafta"dan KOŞULLU geçer (`nusha_durumu.gecir`): bir
   kitap engelliyse hiçbir nüshaya dokunulmaz. Nüsha "Ayıklandı (kayıttan
   düşüldü)" ya da "Devredildi" olur — terminal durumlar, yumuşak silme DEĞİL.
9. Yalnız yönetici kipinde (`require_admin_mode`); şifreli adlar parola
   kurulmadan yazılmaz (`KeyMissingError` → 409).

Hata ve günlük metinleri KİŞİ ADI İÇERMEZ.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_ayiklama, selectors_teslim
from apps.kutuphane.models import (
    CRITERIA_MISMATCH_CRITERIA,
    OPEN_WEEDING_STATUSES,
    TERMINAL_COPY_STATUSES,
    TMY_COMMISSION_MIN_MEMBERS,
    WEEDING_EXCLUDED_STATES,
    WEEDING_PATHS,
    WEEDING_TRANSFER_PATHS,
    WEEDING_WRITE_OFF_PATHS,
    CommissionDecision,
    CommissionDecisionType,
    Copy,
    CopyStatus,
    Loan,
    LoanStatus,
    WeedingBatch,
    WeedingBatchStatus,
    WeedingCriterion,
    WeedingItem,
    WeedingItemState,
    WeedingReason,
    WeedingTmyPath,
)
from apps.kutuphane.services import commissions, masa, nusha_durumu, tmy_kapisi
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul import selectors as okul_selectors
from apps.okul.models import SchoolYear
from apps.okul.services import app_password

logger = logging.getLogger("kutuphane_defteri.kutuphane")

#: Tek istekte teklife eklenebilecek en çok nüsha (bir işlem sigortası).
MAX_ITEMS_PER_ADD: Final = 500
#: Serbest metin alanlarının üst sınırı (model ile aynı).
TEXT_MAX: Final = 255
APPROVER_MAX: Final = 120

# ---------------------------------------------------------------------------
# İletiler (kişisel veri YOK — sözlük: ayıklama, kayıttan düşme, devir)
# ---------------------------------------------------------------------------
NO_SCHOOL_YEAR_MESSAGE = "Önce etkin ders yılını tanımlayın (Ayarlar → Ders Yılları)."
STATE_MESSAGES: Final[dict[str, str]] = {
    "draft_only": "Bu işlem yalnız taslak teklifte yapılır; önce teklifi geri çekin.",
    "submit": "Yalnız taslak teklif komisyona sunulur.",
    "withdraw": "Yalnız komisyona sunulmuş, kararı bağlanmış ya da onaylanmış teklif geri çekilir.",
    "decision": "Komisyon kararı yalnız komisyona sunulmuş teklife bağlanır.",
    "approve": "Harcama yetkilisi onayı yalnız komisyon kararı bağlanmış teklife işlenir.",
    "apply": "Yalnız harcama yetkilisinin onayladığı teklif uygulanır.",
    "cancel_applied": (
        "Uygulanmış teklif iptal edilemez: nüshalar kayıttan düşülmüş ya da devredilmiştir."
    ),
    "cancel_cancelled": "Teklif zaten iptal edilmiş.",
    "target": "Devralacak kurum ancak onaydan önce değiştirilir.",
}
NO_ITEMS_MESSAGE = "Teklifte en az bir kalem olmalıdır."
NO_REMAINING_MESSAGE = (
    "Ayıklanacak kalem kalmadı. Bütün kalemler ayıklanmayacaksa teklifi iptal edin."
)
NO_COPIES_MESSAGE = "Eklenecek nüsha seçilmedi."
TOO_MANY_MESSAGE = f"Tek seferde en çok {MAX_ITEMS_PER_ADD} nüsha eklenir."
REASON_INVALID_MESSAGE = "Geçerli bir ayıklama gerekçesi seçin."
PATH_INVALID_MESSAGE = "Geçerli bir TMY yolu seçin."
LEVEL_ONLY_TRANSFER_MESSAGE = (
    "Kurumun düzeyine uygun olmayan kaynak kayıttan düşme yoluna gidemez: Md. 12/1, yaş ve "
    "gelişim düzeyine uygun olmayan kaynağın (Md. 10/1-b) uygun okullara veya kurumlara "
    "devrini ister; program düzeye uygunsuzluğu yalnız devir yoluna bağlar."
)
TRANSFER_ONLY_LEVEL_MESSAGE = (
    "Programda devir yalnız “Kurumun düzeyine uygun değil” gerekçesiyle yapılır; Md. 12/1 "
    "devri yaş ve gelişim düzeyine uygun olmayan kaynak (Md. 10/1-b) için öngörür."
)
SCRAP_ONLY_MESSAGE = "Bu gerekçe hurdaya ayırma yoluna (TMY 28) gider."
CRITERION_REQUIRED_MESSAGE = "Uyulmayan ölçütü seçin (Md. 10)."
CRITERION_AGE_LEVEL_MESSAGE = (
    "Yaş ve gelişim düzeyine uygun olmayan kaynak (Md. 10/1-b) devredilir (Md. 12/1): "
    "programda “Kurumun düzeyine uygun değil” gerekçesiyle eklenir, hurdaya ayırma yoluna "
    "gidemez."
)
CRITERION_INVALID_MESSAGE = "Geçerli bir ölçüt seçin."
CRITERION_ONLY_CRITERIA_MESSAGE = (
    "Ölçüt yalnız “10. maddedeki ölçütlere uygun değil” gerekçesinde seçilir."
)
TARGET_ONLY_TRANSFER_MESSAGE = "Devralacak kurum yalnız devirde yazılır."
TARGET_REQUIRED_MESSAGE = "{kitap}: devralacak okulu ya da kurumu yazın."
TEXT_TOO_LONG_MESSAGE = f"En çok {TEXT_MAX} karakter yazılabilir."
ALREADY_IN_BATCH_MESSAGE = "Nüsha bu teklifte zaten var."
ITEM_NOT_IN_BATCH_MESSAGE = "Kalem bu teklife ait değil."
EXCLUSION_REASON_REQUIRED_MESSAGE = "Ayıklanmayan her kalemin gerekçesi yazılmalıdır."
EXCLUSION_NOT_PROPOSED_MESSAGE = "Yalnız teklif listesindeki kalem dışarıda bırakılır."
APPROVER_REQUIRED_MESSAGE = "Onaylayan harcama yetkilisinin adını yazın."
APPROVER_TOO_LONG_MESSAGE = f"Ad en çok {APPROVER_MAX} karakter olabilir."
APPROVED_ON_REQUIRED_MESSAGE = "Onay tarihini yazın."
APPROVED_IN_FUTURE_MESSAGE = "Onay tarihi bugünden sonra olamaz."
APPROVED_BEFORE_DECISION_MESSAGE = "Onay tarihi komisyon kararının tarihinden önce olamaz."
TMY_COMMISSION_REQUIRED_MESSAGE = (
    "Hurdaya ayırma yolundaki kalemleri harcama yetkilisinin belirlediği komisyon "
    "değerlendirir (TMY 28/1): komisyon üyelerini satır başına bir kişi yazın."
)
TMY_COMMISSION_MIN_MESSAGE = (
    f"Komisyon en az {TMY_COMMISSION_MIN_MEMBERS} kişiden oluşur (TMY 10/1-e, 28/1)."
)
DESTRUCTION_ONLY_SCRAP_MESSAGE = (
    "İmha kararı yalnız hurdaya ayırma yolundaki kalemler için verilir (TMY 28/5)."
)
DESTRUCTION_ITEM_MESSAGE = (
    "İmha kararı yalnız onaylanan hurdaya ayırma kalemlerine verilir (TMY 28/5)."
)
DESTRUCTION_ITEMS_WITHOUT_DECISION_MESSAGE = "İmha kararı işaretlenmeden kalem seçilemez."
DESTRUCTION_NO_ITEMS_MESSAGE = "İmha kararının kapsadığı en az bir kalem seçilmelidir."
RACE_MESSAGE = "{kitap}: nüshanın durumu bu arada değişti; teklifi yeniden açın."

BATCH_MISSING_MESSAGE = "Teklif bulunamadı."
DECISION_MISSING_MESSAGE = "Komisyon kararı bulunamadı."

# Ayıklama engelleri (kural 2-3) — kitap kimliğiyle birlikte basılır, kişi adı yok.
COPY_MISSING_MESSAGE = "Nüsha bulunamadı."
TERMINAL_MESSAGE = "Kayıttan düşülmüş ya da devredilmiş nüsha ayıklamaya konamaz."
RARE_MESSAGE = (
    "El yazması ya da nadir eser ayıklanamaz; listesi Genel Müdürlüğe gönderilir (Md. 12/2)."
)
RARE_AT_DECISION_MESSAGE = (
    "{kitap}: el yazması ya da nadir eser olarak işaretli; ayıklanamaz. Kalemi “Komisyon "
    "ayıklanmasına karar vermedi” olarak işaretleyin."
)
DECISION_ITEMS_CHANGED_MESSAGE = (
    "Bu komisyon kararı teklif geri çekilmeden önce bağlıydı ve aşağıdaki kalemler o karardan "
    "sonra değişti (yeni kalem, değişen gerekçe ya da TMY yolu, ya da komisyonun "
    "ayıklanmasına karar vermediği kalem). Bu kalemler için yeni bir komisyon kararı "
    "gerekir: {kitaplar}."
)
ON_LOAN_MESSAGE = "Ödünçteki nüsha ayıklamaya konamaz; önce iade alın."
DELIVERED_MESSAGE = "Sınıf kitaplığındaki nüsha ayıklamaya konamaz; önce teslimden geri alın."
LOST_MESSAGE = (
    "Kayıp nüsha ayıklamaya konmaz (Md. 12/1 gerekçelerinden değildir); kaydı sayımda kapanır."
)
IN_REPAIR_MESSAGE = "Onarımdaki nüsha ayıklamaya konamaz; önce onarımdan dönüşünü işleyin."
OPEN_CASE_MESSAGE = "Nüshanın çözülmemiş kayıp/hasar dosyası var; önce dosyayı çözün."
DAMAGE_PROPOSAL_MESSAGE = (
    "Hasar dosyasında kayıttan düşme önerilen nüsha ayıklamaya konmaz (Md. 12/1 "
    "gerekçelerinden değildir); sayımda kayıttan düşülür."
)
OTHER_BATCH_MESSAGE = "Nüsha süren başka bir ayıklama teklifinde."


# ---------------------------------------------------------------------------
# E7 — gerekçeden TMY yoluna (kural 1)
# ---------------------------------------------------------------------------
def default_path(reason: str) -> str:
    """Gerekçenin varsayılan TMY yolu (E7 tablosunun ilk yolu)."""
    if reason not in WEEDING_PATHS:
        raise ValidationError({"reason": REASON_INVALID_MESSAGE})
    return WEEDING_PATHS[reason][0]


def allowed_paths(reason: str) -> tuple[str, ...]:
    """Gerekçenin seçilebilir TMY yolları (E7 tablosu)."""
    if reason not in WEEDING_PATHS:
        raise ValidationError({"reason": REASON_INVALID_MESSAGE})
    return WEEDING_PATHS[reason]


def ensure_path(reason: str, tmy_path: str) -> None:
    """(gerekçe, yol) çifti E7 tablosunda yoksa gerekçeli `ValidationError` (kural 1)."""
    yollar = allowed_paths(reason)
    if tmy_path not in WeedingTmyPath.values:
        raise ValidationError({"tmy_path": PATH_INVALID_MESSAGE})
    if tmy_path in yollar:
        return
    if reason == WeedingReason.LEVEL_MISMATCH:
        raise ValidationError({"tmy_path": LEVEL_ONLY_TRANSFER_MESSAGE})
    if tmy_path in WEEDING_TRANSFER_PATHS:
        raise ValidationError({"tmy_path": TRANSFER_ONLY_LEVEL_MESSAGE})
    raise ValidationError({"tmy_path": SCRAP_ONLY_MESSAGE})


def _olcut(reason: str, criterion: str) -> str:
    """Md. 10 ölçütü: yalnız 12/1-ç kaleminde ve 10/1-b dışında (kural 1)."""
    olcut = (criterion or "").strip()
    if reason != WeedingReason.CRITERIA_MISMATCH:
        if olcut:
            raise ValidationError({"criterion": CRITERION_ONLY_CRITERIA_MESSAGE})
        return ""
    if not olcut:
        raise ValidationError({"criterion": CRITERION_REQUIRED_MESSAGE})
    if olcut == WeedingCriterion.AGE_LEVEL:
        raise ValidationError({"criterion": CRITERION_AGE_LEVEL_MESSAGE})
    if olcut not in CRITERIA_MISMATCH_CRITERIA:
        raise ValidationError({"criterion": CRITERION_INVALID_MESSAGE})
    return olcut


def _kurum(tmy_path: str, transfer_target: str, *, acik_verildi: bool) -> str:
    kurum = (transfer_target or "").strip()
    if len(kurum) > TEXT_MAX:
        raise ValidationError({"transfer_target": TEXT_TOO_LONG_MESSAGE})
    if tmy_path in WEEDING_TRANSFER_PATHS:
        return kurum
    if kurum and acik_verildi:
        raise ValidationError({"transfer_target": TARGET_ONLY_TRANSFER_MESSAGE})
    return ""


@dataclass(frozen=True)
class _Kalem:
    reason: str
    criterion: str
    tmy_path: str
    transfer_target: str


def _kalem_alanlari(
    *,
    reason: str,
    tmy_path: str = "",
    criterion: str = "",
    transfer_target: str = "",
    target_given: bool = True,
) -> _Kalem:
    if reason not in WeedingReason.values:
        raise ValidationError({"reason": REASON_INVALID_MESSAGE})
    yol = (tmy_path or "").strip() or default_path(reason)
    ensure_path(reason, yol)
    return _Kalem(
        reason=reason,
        criterion=_olcut(reason, criterion),
        tmy_path=yol,
        transfer_target=_kurum(yol, transfer_target, acik_verildi=target_given),
    )


# ---------------------------------------------------------------------------
# Ayıklama engeli (kural 2-3)
# ---------------------------------------------------------------------------
def _kitap(copy: Copy) -> str:
    return barcode_module.format_barcode(copy.barcode)


def ayiklama_engeli(copy: Copy, *, batch: WeedingBatch | None = None) -> str:
    """Nüsha ayıklamaya konabilir mi? Konamazsa kişisel veri taşımayan gerekçe, yoksa ''.

    `batch` verilirse o teklifin kendi kalemi "başka teklifte" sayılmaz
    (onay ve uygulamadaki yeniden denetim). Sıra kullanıcıya en yararlı gerekçeyi
    verir: nadir eser engeli durumdan bağımsızdır ve önce söylenir. Hasar
    dosyasının kayıttan düşme önerisi yalnız EKLEMEDE (`batch` yokken) engeldir
    (kural 4).
    """
    if copy.deleted_at is not None or copy.work.deleted_at is not None:
        return COPY_MISSING_MESSAGE
    if copy.status in TERMINAL_COPY_STATUSES:
        return TERMINAL_MESSAGE
    if copy.is_rare_or_manuscript:
        return RARE_MESSAGE
    if (
        copy.status == CopyStatus.ON_LOAN
        or Loan.objects.filter(copy_id=copy.pk, status=LoanStatus.OPEN).exists()
    ):
        return ON_LOAN_MESSAGE
    if (
        copy.status == CopyStatus.DELIVERED
        or selectors_teslim.open_delivery_for_copy(copy.pk) is not None
    ):
        return DELIVERED_MESSAGE
    if copy.status == CopyStatus.LOST:
        return LOST_MESSAGE
    if copy.status == CopyStatus.IN_REPAIR:
        return IN_REPAIR_MESSAGE
    if selectors_teslim.open_case_for_copy(copy.pk) is not None:
        return OPEN_CASE_MESSAGE
    if batch is None and selectors_ayiklama.has_damage_write_off_proposal(copy.pk):
        return DAMAGE_PROPOSAL_MESSAGE
    if copy.status != CopyStatus.AVAILABLE:
        return f"{copy.get_status_display()} — ayıklamaya konamaz."
    baska = selectors_ayiklama.open_batch_items_for_copy(copy.pk)
    if batch is not None:
        baska = baska.exclude(batch_id=batch.pk)
    if baska.exists():
        return OTHER_BATCH_MESSAGE
    return ""


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _taze(batch: WeedingBatch) -> WeedingBatch:
    guncel: WeedingBatch | None = (
        WeedingBatch.objects.select_related("commission_decision").filter(pk=batch.pk).first()
    )
    if guncel is None:
        raise ValidationError(BATCH_MISSING_MESSAGE)
    return guncel


def _durum(batch: WeedingBatch, izinli: Sequence[str], ileti: str) -> None:
    if batch.status not in izinli:
        raise ValidationError({"status": ileti})


def _metin(deger: str, alan: str) -> str:
    metin = (deger or "").strip()
    if len(metin) > TEXT_MAX:
        raise ValidationError({alan: TEXT_TOO_LONG_MESSAGE})
    return metin


def _cozulen_nushalar(
    *, barcodes: Sequence[object], copy_ids: Sequence[int]
) -> tuple[list[Copy], list[str]]:
    """Okutulan kodlar ve seçilen kimlikler → nüshalar (tekrarlar tekilleşir) + hatalar."""
    nushalar: list[Copy] = []
    gorulen: set[int] = set()
    hatalar: list[str] = []
    for sira, deger in enumerate(barcodes, start=1):
        okutma = masa.kitap_coz(deger, staff=False)
        if okutma.copy is None:
            # Ham kod YANKILANMAZ (üye kartı okutulmuş olabilir): sıra numarası yeter.
            hatalar.append(f"{sira}. okutma: {okutma.message}")
            continue
        if okutma.copy.pk not in gorulen:
            gorulen.add(okutma.copy.pk)
            nushalar.append(okutma.copy)
    bulunan = {c.pk: c for c in Copy.objects.select_related("work").filter(pk__in=list(copy_ids))}
    for sira, kimlik in enumerate(copy_ids, start=1):
        nusha = bulunan.get(int(kimlik))
        if nusha is None:
            hatalar.append(f"{sira}. seçim: {COPY_MISSING_MESSAGE}")
            continue
        if nusha.pk not in gorulen:
            gorulen.add(nusha.pk)
            nushalar.append(nusha)
    return nushalar, hatalar


def _uyeler(metin: str) -> list[str]:
    return [satir.strip() for satir in (metin or "").splitlines() if satir.strip()]


def _dislama(batch: WeedingBatch, dislananlar: Mapping[int, str] | None, yeni_durum: str) -> None:
    """Teklif listesindeki kalemleri gerekçesiyle dışarıda bırakır (kalem SİLİNMEZ)."""
    for kimlik, gerekce in (dislananlar or {}).items():
        kalem: WeedingItem | None = WeedingItem.objects.filter(batch=batch, pk=int(kimlik)).first()
        if kalem is None:
            raise ValidationError({"items": ITEM_NOT_IN_BATCH_MESSAGE})
        if kalem.state != WeedingItemState.PROPOSED:
            raise ValidationError({"items": EXCLUSION_NOT_PROPOSED_MESSAGE})
        metin = _metin(str(gerekce or ""), "items")
        if not metin:
            raise ValidationError({"items": EXCLUSION_REASON_REQUIRED_MESSAGE})
        kalem.state = yeni_durum
        kalem.exclusion_reason = metin
        kalem.save(update_fields=["state", "exclusion_reason", "updated_at"])


def _kalanlar(batch: WeedingBatch) -> list[WeedingItem]:
    return list(selectors_ayiklama.batch_items(batch).filter(state=WeedingItemState.PROPOSED))


def _kalem_izi(kalem: WeedingItem) -> list[object]:
    """Kalemin kişisiz izi: komisyon kararının neye verildiği (nüsha, gerekçe, ölçüt, yol).

    Devralacak kurum ize girmez: komisyon "devredilsin" dedikten sonra kurum
    düzeltilebilir (F8 ekleri 4).
    """
    return [int(kalem.copy_id), kalem.reason, kalem.criterion, kalem.tmy_path]


def _imha_kalemleri(
    kalanlar: Sequence[WeedingItem], karar_var: bool, secilen: Sequence[int] | None
) -> list[int]:
    """İmha kararının kapsadığı kalem kimlikleri (TMY 28/5 — kalem düzeyinde)."""
    hurda = [k.pk for k in kalanlar if k.tmy_path == WeedingTmyPath.TMY_28]
    if not karar_var:
        if secilen:
            raise ValidationError({"destruction_items": DESTRUCTION_ITEMS_WITHOUT_DECISION_MESSAGE})
        return []
    if secilen is None:
        return hurda
    kimlikler = list(dict.fromkeys(int(k) for k in secilen))
    if not kimlikler:
        raise ValidationError({"destruction_items": DESTRUCTION_NO_ITEMS_MESSAGE})
    if any(k not in hurda for k in kimlikler):
        raise ValidationError({"destruction_items": DESTRUCTION_ITEM_MESSAGE})
    return kimlikler


# ---------------------------------------------------------------------------
# Teklif
# ---------------------------------------------------------------------------
@transaction.atomic
def create_batch(*, school_year: SchoolYear | None = None, notes: str = "") -> WeedingBatch:
    """Taslak ayıklama teklifi açar (ders yılı verilmezse etkin yıl)."""
    require_admin_mode()
    yil = school_year if school_year is not None else okul_selectors.active_school_year()
    if yil is None or yil.deleted_at is not None:
        raise ValidationError({"school_year": NO_SCHOOL_YEAR_MESSAGE})
    batch: WeedingBatch = WeedingBatch.objects.create(school_year=yil, notes=notes or "")
    logger.info("Ayıklama teklifi açıldı.")
    return batch


@transaction.atomic
def update_batch(batch: WeedingBatch, *, notes: str) -> WeedingBatch:
    """Teklifin notlarını günceller (uygulanmış ya da iptal edilmiş teklif değişmez)."""
    require_admin_mode()
    guncel = _taze(batch)
    _durum(guncel, OPEN_WEEDING_STATUSES, STATE_MESSAGES["cancel_applied"])
    guncel.notes = notes or ""
    guncel.save(update_fields=["notes", "updated_at"])
    return guncel


@transaction.atomic
def delete_batch(batch: WeedingBatch) -> None:
    """Yanlış açılmış TASLAK teklifi kalemleriyle yumuşak siler.

    Sunulmuş teklif silinmez (komisyonun önüne gitmiş listedir); vazgeçme yolu
    iptaldir ve kayıt kalır.
    """
    require_admin_mode()
    guncel = _taze(batch)
    _durum(guncel, (WeedingBatchStatus.DRAFT,), STATE_MESSAGES["draft_only"])
    WeedingItem.objects.filter(batch=guncel).delete()
    guncel.delete()


# ---------------------------------------------------------------------------
# Kalemler (D15: kalem silme)
# ---------------------------------------------------------------------------
@transaction.atomic
def add_items(
    batch: WeedingBatch,
    *,
    reason: str,
    barcodes: Sequence[object] = (),
    copy_ids: Sequence[int] = (),
    tmy_path: str = "",
    criterion: str = "",
    transfer_target: str = "",
) -> list[WeedingItem]:
    """Taslak teklife nüsha ekler — TEK işlem (bir nüsha engelliyse hiçbiri eklenmez).

    Nüshalar okutulan kodlarla (`barcodes`) ya da aday listesinden seçilen
    kimliklerle (`copy_ids`) verilir; hepsi aynı gerekçe ve TMY yolunu alır
    (yol verilmezse E7 tablosunun varsayılanı). Engeller kitap kitap
    `{"barcodes": [...]}` olarak döner (400). Nüshanın F7 kayıttan düşme önerisi
    varsa kalem o dosyaya bağlanır.
    """
    require_admin_mode()
    guncel = _taze(batch)
    _durum(guncel, (WeedingBatchStatus.DRAFT,), STATE_MESSAGES["draft_only"])
    alanlar = _kalem_alanlari(
        reason=reason, tmy_path=tmy_path, criterion=criterion, transfer_target=transfer_target
    )
    toplam = len(barcodes) + len(copy_ids)
    if toplam == 0:
        raise ValidationError({"barcodes": NO_COPIES_MESSAGE})
    if toplam > MAX_ITEMS_PER_ADD:
        raise ValidationError({"barcodes": TOO_MANY_MESSAGE})
    nushalar, hatalar = _cozulen_nushalar(barcodes=barcodes, copy_ids=copy_ids)
    bu_teklifte = set(WeedingItem.objects.filter(batch=guncel).values_list("copy_id", flat=True))
    for nusha in nushalar:
        engel = ALREADY_IN_BATCH_MESSAGE if nusha.pk in bu_teklifte else ayiklama_engeli(nusha)
        if engel:
            hatalar.append(f"{_kitap(nusha)}: {engel}")
    if hatalar:
        raise ValidationError({"barcodes": hatalar})
    if not nushalar:
        raise ValidationError({"barcodes": NO_COPIES_MESSAGE})

    eklenen: list[WeedingItem] = []
    for nusha in nushalar:
        try:
            with transaction.atomic():
                eklenen.append(
                    WeedingItem.objects.create(
                        batch=guncel,
                        copy=nusha,
                        reason=alanlar.reason,
                        criterion=alanlar.criterion,
                        tmy_path=alanlar.tmy_path,
                        transfer_target=alanlar.transfer_target,
                    )
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"barcodes": [f"{_kitap(nusha)}: {ALREADY_IN_BATCH_MESSAGE}"]}
            ) from exc
    logger.info("Ayıklama teklifine %d kalem eklendi.", len(eklenen))
    return eklenen


@transaction.atomic
def update_item(
    item: WeedingItem,
    *,
    reason: str | None = None,
    tmy_path: str | None = None,
    criterion: str | None = None,
    transfer_target: str | None = None,
) -> WeedingItem:
    """Kalemi günceller.

    Taslakta gerekçe, ölçüt, TMY yolu ve devralacak kurum değişir. Gerekçe
    değişip yol verilmezse ve eski yol yeni gerekçeye uymuyorsa E7'nin
    varsayılanı alınır; kayıttan düşme yoluna geçen kalemin kurum adı temizlenir.
    Sunulmuş ya da kararı bağlanmış teklifte YALNIZ devralacak kurum değişir
    (komisyon "devredilsin" dedikten sonra okul bulunabilir); onaydan sonra hiçbir
    alan değişmez.
    """
    require_admin_mode()
    kalem: WeedingItem | None = (
        WeedingItem.objects.select_related("batch", "copy").filter(pk=item.pk).first()
    )
    if kalem is None:
        raise ValidationError({"items": ITEM_NOT_IN_BATCH_MESSAGE})
    teklif = kalem.batch
    if teklif.status != WeedingBatchStatus.DRAFT:
        if reason is not None or tmy_path is not None or criterion is not None:
            raise ValidationError({"status": STATE_MESSAGES["draft_only"]})
        _durum(
            teklif,
            (WeedingBatchStatus.SUBMITTED, WeedingBatchStatus.DECIDED),
            STATE_MESSAGES["target"],
        )
        if transfer_target is None:
            return kalem
        kalem.transfer_target = _kurum(kalem.tmy_path, transfer_target, acik_verildi=True)
        kalem.save(update_fields=["transfer_target", "updated_at"])
        return kalem

    yeni_gerekce = reason if reason is not None else kalem.reason
    yol = tmy_path
    if yol is None:
        yol = kalem.tmy_path if kalem.tmy_path in allowed_paths(yeni_gerekce) else ""
    olcut = criterion
    if olcut is None:
        olcut = kalem.criterion if yeni_gerekce == WeedingReason.CRITERIA_MISMATCH else ""
    alanlar = _kalem_alanlari(
        reason=yeni_gerekce,
        tmy_path=yol,
        criterion=olcut,
        transfer_target=kalem.transfer_target if transfer_target is None else transfer_target,
        target_given=transfer_target is not None,
    )
    kalem.reason = alanlar.reason
    kalem.criterion = alanlar.criterion
    kalem.tmy_path = alanlar.tmy_path
    kalem.transfer_target = alanlar.transfer_target
    kalem.save(update_fields=["reason", "criterion", "tmy_path", "transfer_target", "updated_at"])
    return kalem


@transaction.atomic
def remove_item(item: WeedingItem) -> None:
    """Kalemi yumuşak siler — YALNIZ taslakta (D15)."""
    require_admin_mode()
    kalem: WeedingItem | None = (
        WeedingItem.objects.select_related("batch").filter(pk=item.pk).first()
    )
    if kalem is None:
        raise ValidationError({"items": ITEM_NOT_IN_BATCH_MESSAGE})
    _durum(kalem.batch, (WeedingBatchStatus.DRAFT,), STATE_MESSAGES["draft_only"])
    kalem.delete()


# ---------------------------------------------------------------------------
# Durum geçişleri
# ---------------------------------------------------------------------------
@transaction.atomic
def submit_batch(batch: WeedingBatch) -> WeedingBatch:
    """Taslak → komisyona sunuldu. En az bir kalem; her kalem yeniden denetlenir."""
    require_admin_mode()
    guncel = _taze(batch)
    _durum(guncel, (WeedingBatchStatus.DRAFT,), STATE_MESSAGES["submit"])
    kalemler = list(selectors_ayiklama.batch_items(guncel))
    if not kalemler:
        raise ValidationError({"items": NO_ITEMS_MESSAGE})
    _engelleri_denetle(guncel, kalemler)
    guncel.status = WeedingBatchStatus.SUBMITTED
    guncel.submitted_at = timezone.now()
    guncel.save(update_fields=["status", "submitted_at", "updated_at"])
    logger.info("Ayıklama teklifi komisyona sunuldu.")
    return guncel


@transaction.atomic
def withdraw_batch(batch: WeedingBatch) -> WeedingBatch:
    """Teklifi geri çeker (D15): sunulmuş, kararı bağlanmış ya da onaylanmış → taslak.

    Sonraki adımların bütün kayıtları temizlenir: komisyon kararı bağı, onay
    (şifreli ad dahil), imha kararı ve kalemlerin dışarıda bırakılma işaretleri
    (kalemler yeniden "Teklif listesinde" olur). Liste yeniden düzenlenip sunulur.

    Karar bağlıysa kararın ayıklanmasına karar verdiği kalemlerin kişisiz izi
    saklanır (`withdrawn_decision`, `withdrawn_items`): aynı karar yeniden
    bağlanırken kalemler bu izin içinde kalmalıdır (`bind_decision`).
    """
    require_admin_mode()
    guncel = _taze(batch)
    _durum(
        guncel,
        (WeedingBatchStatus.SUBMITTED, WeedingBatchStatus.DECIDED, WeedingBatchStatus.APPROVED),
        STATE_MESSAGES["withdraw"],
    )
    if guncel.commission_decision_id is not None:
        guncel.withdrawn_decision_id = guncel.commission_decision_id
        guncel.withdrawn_items = sorted(
            _kalem_izi(k)
            for k in selectors_ayiklama.batch_items(guncel)
            if k.state != WeedingItemState.KEPT_BY_COMMISSION
        )
    simdi = timezone.now()
    WeedingItem.objects.filter(batch=guncel, state__in=WEEDING_EXCLUDED_STATES).update(
        state=WeedingItemState.PROPOSED, exclusion_reason="", updated_at=simdi
    )
    WeedingItem.objects.filter(batch=guncel, destruction_decided=True).update(
        destruction_decided=False, updated_at=simdi
    )
    guncel.status = WeedingBatchStatus.DRAFT
    guncel.submitted_at = None
    guncel.commission_decision = None
    guncel.decided_at = None
    guncel.approved_by_name = ""
    guncel.approved_on = None
    guncel.approved_at = None
    guncel.tmy_commission_members = ""
    guncel.destruction_decided = False
    guncel.save(
        update_fields=[
            "status",
            "submitted_at",
            "commission_decision",
            "decided_at",
            "approved_by_name",
            "approved_on",
            "approved_at",
            "tmy_commission_members",
            "destruction_decided",
            "withdrawn_decision",
            "withdrawn_items",
            "updated_at",
        ]
    )
    logger.info("Ayıklama teklifi geri çekildi.")
    return guncel


@transaction.atomic
def bind_decision(
    batch: WeedingBatch,
    *,
    commission_decision: CommissionDecision,
    kept: Mapping[int, str] | None = None,
) -> WeedingBatch:
    """Komisyon kararını bağlar: komisyona sunuldu → komisyon kararı bağlandı.

    Karar "Ayıklama" türünde olmalıdır (D7). `kept`: komisyonun ayıklanmasına
    karar VERMEDİĞİ kalemler (kalem kimliği → gerekçe); kalemler silinmez, "Komisyon
    ayıklanmasına karar vermedi" olur. En az bir kalem ayıklanmalıdır.

    Ayıklanan kalemlerde nadir eser işaretli nüsha olamaz (teklif sürerken
    işaretlenmiş olabilir; komisyon o kalemi ayıklamamış olarak işaretler). Teklif
    geri çekilmeden önce bağlı olan karar yeniden bağlanıyorsa ayıklanan kalemler o
    kararın kapsadığı kalemlerin içinde kalmalıdır (modül belgesi, kural 5).
    """
    require_admin_mode()
    guncel = _taze(batch)
    _durum(guncel, (WeedingBatchStatus.SUBMITTED,), STATE_MESSAGES["decision"])
    if commission_decision.deleted_at is not None:
        raise ValidationError({"commission_decision": DECISION_MISSING_MESSAGE})
    commissions.require_decision_type(commission_decision, CommissionDecisionType.WEEDING)
    _dislama(guncel, kept, WeedingItemState.KEPT_BY_COMMISSION)
    kalanlar = _kalanlar(guncel)
    if not kalanlar:
        raise ValidationError({"items": NO_REMAINING_MESSAGE})
    nadir = [
        RARE_AT_DECISION_MESSAGE.format(kitap=_kitap(k.copy))
        for k in kalanlar
        if k.copy.is_rare_or_manuscript
    ]
    if nadir:
        raise ValidationError({"items": nadir})
    if (
        guncel.withdrawn_decision_id is not None
        and guncel.withdrawn_decision_id == commission_decision.pk
    ):
        kapsam = {tuple(iz) for iz in (guncel.withdrawn_items or [])}
        degisen = [_kitap(k.copy) for k in kalanlar if tuple(_kalem_izi(k)) not in kapsam]
        if degisen:
            raise ValidationError(
                {
                    "commission_decision": DECISION_ITEMS_CHANGED_MESSAGE.format(
                        kitaplar=", ".join(degisen)
                    )
                }
            )
    guncel.status = WeedingBatchStatus.DECIDED
    guncel.commission_decision = commission_decision
    guncel.decided_at = timezone.now()
    guncel.save(update_fields=["status", "commission_decision", "decided_at", "updated_at"])
    logger.info("Ayıklama teklifine komisyon kararı bağlandı.")
    return guncel


@transaction.atomic
def approve_batch(
    batch: WeedingBatch,
    *,
    approved_by_name: str,
    approved_on: date | None,
    tmy_commission_members: str = "",
    destruction_decided: bool = False,
    destruction_items: Sequence[int] | None = None,
    not_approved: Mapping[int, str] | None = None,
) -> WeedingBatch:
    """Harcama yetkilisi onayını işler: komisyon kararı bağlandı → onaylandı (kural 7).

    `not_approved`: onaylanmayan kalemler (28/2: komisyonun hurdaya ayrılmasını
    uygun görmediği ya da harcama yetkilisinin onaylamadığı) — gerekçesiyle
    işaretlenir. Onaylayanın adı ve TMY komisyonunun adları ŞİFRELİ saklanır.

    `destruction_items`: imha kararının (28/5) kapsadığı kalemler; verilmezse
    onaylanan bütün 28 kalemleri. Kapsam dışı kalan 28 kalemi hurdaya ayrılır ama
    imha tutanağına girmez (ekonomik değeri olan hurdada 28/8).
    """
    require_admin_mode()
    app_password.require_password_set()
    guncel = _taze(batch)
    _durum(guncel, (WeedingBatchStatus.DECIDED,), STATE_MESSAGES["approve"])
    ad = (approved_by_name or "").strip()
    if not ad:
        raise ValidationError({"approved_by_name": APPROVER_REQUIRED_MESSAGE})
    if len(ad) > APPROVER_MAX:
        raise ValidationError({"approved_by_name": APPROVER_TOO_LONG_MESSAGE})
    if approved_on is None:
        raise ValidationError({"approved_on": APPROVED_ON_REQUIRED_MESSAGE})
    if approved_on > timezone.localdate():
        raise ValidationError({"approved_on": APPROVED_IN_FUTURE_MESSAGE})
    karar = guncel.commission_decision
    if karar is not None and approved_on < karar.decision_date:
        raise ValidationError({"approved_on": APPROVED_BEFORE_DECISION_MESSAGE})

    _dislama(guncel, not_approved, WeedingItemState.NOT_APPROVED)
    kalanlar = _kalanlar(guncel)
    if not kalanlar:
        raise ValidationError({"items": NO_REMAINING_MESSAGE})
    hurda = any(k.tmy_path == WeedingTmyPath.TMY_28 for k in kalanlar)
    uyeler = _uyeler(tmy_commission_members)
    if hurda and not uyeler:
        raise ValidationError({"tmy_commission_members": TMY_COMMISSION_REQUIRED_MESSAGE})
    if uyeler and len(uyeler) < TMY_COMMISSION_MIN_MEMBERS:
        raise ValidationError({"tmy_commission_members": TMY_COMMISSION_MIN_MESSAGE})
    if destruction_decided and not hurda:
        raise ValidationError({"destruction_decided": DESTRUCTION_ONLY_SCRAP_MESSAGE})
    imha_kalemleri = _imha_kalemleri(kalanlar, bool(destruction_decided), destruction_items)
    eksik_kurum = [
        TARGET_REQUIRED_MESSAGE.format(kitap=_kitap(k.copy))
        for k in kalanlar
        if k.tmy_path in WEEDING_TRANSFER_PATHS and not k.transfer_target.strip()
    ]
    if eksik_kurum:
        raise ValidationError({"transfer_target": eksik_kurum})
    _engelleri_denetle(guncel, kalanlar)

    guncel.status = WeedingBatchStatus.APPROVED
    guncel.approved_by_name = ad
    guncel.approved_on = approved_on
    guncel.approved_at = timezone.now()
    guncel.tmy_commission_members = "\n".join(uyeler)
    guncel.destruction_decided = bool(destruction_decided)
    if imha_kalemleri:
        WeedingItem.objects.filter(pk__in=imha_kalemleri).update(
            destruction_decided=True, updated_at=timezone.now()
        )
    guncel.save(
        update_fields=[
            "status",
            "approved_by_name",
            "approved_on",
            "approved_at",
            "tmy_commission_members",
            "destruction_decided",
            "updated_at",
        ]
    )
    logger.info("Ayıklama teklifine harcama yetkilisi onayı işlendi.")
    return guncel


@dataclass(frozen=True)
class WeedingApplyResult:
    """Uygulamanın sonucu (kişisiz sayılar)."""

    batch: WeedingBatch
    withdrawn: int
    transferred: int


def _engelleri_denetle(batch: WeedingBatch, kalemler: Sequence[WeedingItem]) -> None:
    """Teklif listesindeki kalemlerin nüshalarını yeniden denetler (kural 2-3)."""
    hatalar: list[str] = []
    for kalem in kalemler:
        if kalem.state != WeedingItemState.PROPOSED:
            continue
        nusha: Copy = Copy.all_objects.select_related("work").get(pk=kalem.copy_id)
        engel = ayiklama_engeli(nusha, batch=batch)
        if engel:
            hatalar.append(f"{_kitap(nusha)}: {engel}")
    if hatalar:
        raise ValidationError({"items": hatalar})


@transaction.atomic
def apply_batch(batch: WeedingBatch) -> WeedingApplyResult:
    """Onaylanan teklifi uygular — TEK işlem (kural 8).

    TMY 32/3 kapısı: kayıttan düşme varsa `KAYITTAN_DUSME`, devir varsa `DEVIR`
    sorulur (F9 doldurur). Kalemler yeniden denetlenir; nüsha "Rafta"dan koşullu
    olarak "Ayıklandı (kayıttan düşüldü)" ya da "Devredildi"ye geçer. Bir nüsha
    geçemezse bütün işlem geri sarılır.
    """
    require_admin_mode()
    guncel = _taze(batch)
    _durum(guncel, (WeedingBatchStatus.APPROVED,), STATE_MESSAGES["apply"])
    kalemler = _kalanlar(guncel)
    if not kalemler:
        raise ValidationError({"items": NO_REMAINING_MESSAGE})
    if any(k.tmy_path in WEEDING_WRITE_OFF_PATHS for k in kalemler):
        tmy_kapisi.ensure_open(tmy_kapisi.KAYITTAN_DUSME)
    if any(k.tmy_path in WEEDING_TRANSFER_PATHS for k in kalemler):
        tmy_kapisi.ensure_open(tmy_kapisi.DEVIR)
    _engelleri_denetle(guncel, kalemler)

    simdi = timezone.now()
    dusulen = devredilen = 0
    for kalem in kalemler:
        hedef = (
            CopyStatus.TRANSFERRED
            if kalem.tmy_path in WEEDING_TRANSFER_PATHS
            else CopyStatus.WITHDRAWN_WEEDED
        )
        if not nusha_durumu.gecir(kalem.copy_id, eski=CopyStatus.AVAILABLE, yeni=hedef):
            raise ValidationError({"items": [RACE_MESSAGE.format(kitap=_kitap(kalem.copy))]})
        if hedef == CopyStatus.TRANSFERRED:
            devredilen += 1
        else:
            dusulen += 1
    WeedingItem.objects.filter(pk__in=[k.pk for k in kalemler]).update(
        state=WeedingItemState.APPLIED, updated_at=simdi
    )
    guncel.status = WeedingBatchStatus.APPLIED
    guncel.applied_at = simdi
    guncel.save(update_fields=["status", "applied_at", "updated_at"])
    logger.info(
        "Ayıklama teklifi uygulandı: %d nüsha kayıttan düşüldü, %d nüsha devredildi.",
        dusulen,
        devredilen,
    )
    return WeedingApplyResult(batch=guncel, withdrawn=dusulen, transferred=devredilen)


@transaction.atomic
def cancel_batch(batch: WeedingBatch, *, reason: str = "") -> WeedingBatch:
    """Uygulanmamış teklifi iptal eder; nüshalara dokunulmaz, kayıt kalır."""
    require_admin_mode()
    guncel = _taze(batch)
    if guncel.status == WeedingBatchStatus.APPLIED:
        raise ValidationError({"status": STATE_MESSAGES["cancel_applied"]})
    if guncel.status == WeedingBatchStatus.CANCELLED:
        raise ValidationError({"status": STATE_MESSAGES["cancel_cancelled"]})
    guncel.status = WeedingBatchStatus.CANCELLED
    guncel.cancelled_at = timezone.now()
    guncel.cancel_reason = _metin(reason, "reason")
    guncel.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    logger.info("Ayıklama teklifi iptal edildi.")
    return guncel
