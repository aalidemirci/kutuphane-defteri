"""Kayıp, hasar ve onarım — Md. 19 dosyaları ve D3 akışları (tasarım §9-9, §6.2, §13 D3).

OYS'nin `circulation.report_lost` / `resolve_case` yollarından UYARLA (§12): rol,
`by_user` ve denetim kaydı düştü; çözüm durumları sözlüğe uyarlandı
(`CaseResolution`); asıl kayıttan düşme bu fazda YAPILMAZ, yalnız önerilir.

KURALLAR (her biri testle kilitli — `tests/test_kayip_hasar.py`):

1. **Md. 19 kademe kapısı.** Bedel yolları ("Bedel belirlendi", "Bedel teslim
   alındı", "Bedelle aynısı alındı", "Bedelle başka eser alındı") ve piyasa
   bedeli kaydı YALNIZ ortaöğretimde açılır (`SchoolConfig.kademe`; kademe
   seçilmemişse kapalı — fail-closed). İlkokul ve ortaokulda yalnız "Bulundu",
   "Aynısı temin edildi", "Onarıldı" ve "Kayıttan düşme önerildi" yolları vardır.
   TEK istisna: bedeli teslim alınmış dosyanın iki kapanış yolu kademe sonradan
   değişse de açık kalır (alınmış bedelin kullanımı kaydedilmelidir; dosya
   kilitlenmez).
2. **Program tahsilat yapmaz** ve disiplin sürecini başlatmaz (OKY 164/1-g bir
   disiplin konusudur, programın işi değildir). Bedel iki ADIMDIR (25.09.2026
   kullanıcı kararı): "Bedel belirlendi" (o günkü piyasa bedeli kaydedilir;
   kişinin açık işi SÜRER, ilişik listesinde kalır) → "Bedel teslim alındı"
   (kişinin açık işi BİTER: ilişik listesinden çıkar, E5 basılabilir; dosya OKUL
   İÇİN açık kalır ve yalnız "Bedelle aynısı alındı" ya da "Bedelle başka eser
   alındı" ile kapanır). Program yalnız kaydeder; dil "bedel belirlendi", "bedel
   teslim alındı"dır — asla borç, ceza ya da tahsilat. İkinci adım geri alınmaz.
3. **Kayıp bildirimi** (`report_lost`): ödünçteki nüshanın ödüncü "Kayba dönüştü"
   ile KAPANIR (sayı sınırına ve gecikmeye artık sayılmaz; yükümlülük dosyadır),
   teslimdeki nüshanın teslimi aynı biçimde kapanır; nüsha "Kayıp" olur.
   "Bulundu" ile nüsha rafa döner; ödünç yeniden açılmaz. Nüshanın açık HASAR
   dosyası varsa (hasar dosyası nüshayı dolaşımdan çıkarmaz; kitap ödünçte,
   teslimde ya da rafta kaybolabilir) o dosya aynı işlemde "Kayba dönüştü" ile
   kapanır ve kayıp dosyası açılır; hasar dosyasının sorumlusu ve notu kendi
   kaydında kalır (F7 düzeltme turu).
4. **Hasar dosyası** (`open_damage_case`, D3): nüsha kütüphanede olmalıdır (rafta
   ya da onarımda). Ödünçteki kitap önce iade alınır, teslimdeki önce geri
   alınır; sorumlu, iadesi alınan ödünç ya da geri alınan teslimle gösterilir.
   Dosya açılışı nüshayı dolaşımdan ÇIKARMAZ (kitap okunabilir durumda olabilir);
   "onarıma gönder" seçilirse nüsha "Onarımda"ya geçer.
5. **Onarım** (`send_to_repair` / `return_from_repair`, D3): "Rafta" ⇄
   "Onarımda"; her gidiş bir `CopyRepair` kaydıdır (yıl sonu raporu — E9).
6. **Kayıttan düşme yalnız ÖNERİDİR** (`WRITE_OFF_PROPOSED`, "Bedelle başka eser
   alındı"): dosyada `write_off_proposed_at` işaretlenir, nüshanın durumu
   değişmez. Asıl kayıttan düşme TMY yoludur (ayıklama F8, sayım F9). Öneri geri
   alınabilir: "Kayıttan düşme önerildi" ile kapanmış KAYIP dosyasında nüsha hâlâ
   "Kayıp"sa kitap bulununca "Bulundu" seçilir — öneri kalkar, nüsha rafa döner
   (F7 düzeltme turu). "Bedelle başka eser alındı"da bu yol yoktur: Md. 19 o yolda
   kaybedilenin kaydının silinmesini ister.
7. **TMY 32/3 durdurması** kayıp bildirimini ve kayıp dosyası çözümünü kapsar
   (§9-10, D4): iki yol `services.tmy_kapisi.ensure_open`'dan geçer (F7'de boş,
   F9 doldurur). Hangi çözümün kapsamda olduğunu `tmy_kapisi.dosya_cozumu_kapsamda_mi`
   söyler (onarım ve iki bedel adımı kapsam dışıdır — bedelin belirlenmesi ve
   teslim alınması TMY'de giriş-çıkış değildir).
8. Nüsha başına tek AÇIK dosya ve tek açık onarım (DB kısıtları + servis
   iletisi). Dosya işlemleri yalnız yönetici kipindedir (§4.4 "kayıp dosyaları"
   görevliye kapalı); kişi yazan işlemler parola kurulu değilse 409 alır.
9. **Kişinin açık işi** (`open_case_obligations`, ilişik listesi, E5) yalnız
   "Çözüm bekliyor" ve "Bedel belirlendi"dir (`PERSON_OPEN_RESOLUTIONS`); "Bedel
   teslim alındı" dosyası Kayıp ve Hasar ekranında okulun açık işi olarak kalır,
   kişiye yazılmaz.

Hata ve günlük metinleri KİŞİ ADI İÇERMEZ.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Final

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.kutuphane import selectors_teslim
from apps.kutuphane.models import (
    OPEN_CASE_RESOLUTIONS,
    PRICE_RESOLUTIONS,
    TERMINAL_COPY_STATUSES,
    WRITE_OFF_RESOLUTIONS,
    CaseResolution,
    CaseType,
    Copy,
    CopyRepair,
    CopyStatus,
    Delivery,
    DeliveryStatus,
    Loan,
    LoanStatus,
    LossDamageCase,
    Membership,
)
from apps.kutuphane.services import nusha_durumu, tmy_kapisi
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul.models import Personnel, SchoolConfig, SchoolLevel, Student
from apps.okul.services import app_password, persons

logger = logging.getLogger("kutuphane_defteri.kutuphane")

type Person = Student | Personnel

#: Sorumlu notunun üst sınırı (karakter; serializer ile aynı).
RESPONSIBLE_NOTE_MAX: Final = 500

# ---------------------------------------------------------------------------
# İletiler (kişisel veri YOK — sözlük: kayıp, hasar, onarım; "zayi", "borç" değil)
# ---------------------------------------------------------------------------
PRICE_ONLY_ORTAOGRETIM_MESSAGE = (
    "Bedel seçenekleri yalnız ortaöğretim okullarında sunulur (Md. 19). Okulun kademesi "
    "Ayarlar → Okul Bilgileri'nde seçilir."
)
PRICE_ONLY_ON_PRICE_PATH_MESSAGE = "Piyasa bedeli yalnız “Bedel belirlendi” adımında kaydedilir."
PRICE_REQUIRED_MESSAGE = "Bedel kaydı için o günkü piyasa bedelini yazın."
CASE_CLOSED_MESSAGE = "Bu dosya zaten kapanmış."
CASE_OPEN_EXISTS_MESSAGE = (
    "Bu nüshanın çözülmemiş bir kayıp/hasar dosyası var. Önce o dosyayı çözün."
)
RESOLUTION_INVALID_MESSAGE = "Geçerli bir çözüm seçin."
RESOLUTION_NOT_ALLOWED_MESSAGE = "“{cozum}” bu dosyada seçilemez."
COPY_MISSING_MESSAGE = "Nüsha bulunamadı."
COPY_TERMINAL_MESSAGE = "Kayıttan düşülmüş ya da devredilmiş nüshaya dosya açılmaz."
LOST_ALREADY_MESSAGE = "Nüsha zaten kayıp kaydında."
LOST_IN_REPAIR_MESSAGE = (
    "Onarımdaki nüsha için kayıp bildirilemez; önce onarımdan dönüşünü işleyin."
)
DAMAGE_ON_LOAN_MESSAGE = "Ödünçteki nüsha için önce iade alın; hasar dosyası iadeden sonra açılır."
DAMAGE_DELIVERED_MESSAGE = (
    "Teslimdeki nüsha için önce geri alın; hasar dosyası geri almadan sonra açılır."
)
DAMAGE_LOST_MESSAGE = "Kayıp nüshaya hasar dosyası açılmaz."
LOAN_MISMATCH_MESSAGE = "Seçilen ödünç bu nüshaya ait değil."
LOAN_STILL_OPEN_MESSAGE = "Seçilen ödünç hâlâ açık; önce iade alın."
DELIVERY_MISMATCH_MESSAGE = "Seçilen teslim bu nüshaya ait değil."
DELIVERY_STILL_OPEN_MESSAGE = "Seçilen teslim hâlâ açık; önce geri alın."
MEMBERSHIP_MISMATCH_MESSAGE = (
    "Seçilen üyelik, ödüncü alan üyelikle aynı değil. Sorumlu ödünçten belirlenir."
)
MEMBERSHIP_MISSING_MESSAGE = "Üyelik bulunamadı."
REPORTED_IN_FUTURE_MESSAGE = "Tespit tarihi bugünden sonra olamaz."
NOTE_TOO_LONG_MESSAGE = f"Sorumlu notu en çok {RESPONSIBLE_NOTE_MAX} karakter olabilir."
COPY_STATE_CHANGED_MESSAGE = "Nüshanın durumu bu arada değişti; ekranı yenileyin."
FOUND_NOT_LOST_MESSAGE = "Nüsha kayıp durumunda değil; “Bulundu” seçilemez."
REPAIR_NOT_AVAILABLE_MESSAGE = "Onarıma yalnız raftaki nüsha gönderilir ({durum})."
REPAIR_NOT_IN_REPAIR_MESSAGE = "Nüsha onarımda değil."
CASE_OPEN_OBLIGATION = "{sayi} çözülmemiş kayıp/hasar dosyası var."


# ---------------------------------------------------------------------------
# Md. 19 kademe kapısı
# ---------------------------------------------------------------------------
def price_options_available() -> bool:
    """Bedel seçenekleri sunulur mu? YALNIZ ortaöğretimde (Md. 19; kademe boşsa hayır)."""
    return SchoolConfig.load().kademe == SchoolLevel.ORTAOGRETIM


def oneri_geri_alinabilir(case: LossDamageCase) -> bool:
    """Kapanmış kayıp dosyasında kayıttan düşme önerisi "Bulundu" ile geri alınabilir mi?

    Yalnız "Kayıttan düşme önerildi" ile kapanmış KAYIP dosyasında ve nüsha hâlâ
    "Kayıp"ken (asıl kayıttan düşme — F8/F9 — yapılmamış, nüsha başka bir yola
    geçmemiş). "Bedelle başka eser alındı" bu yolu açmaz (Md. 19: kaybedilenin
    kaydı silinerek başka eser alınır).
    """
    return (
        not case.is_open
        and case.case_type == CaseType.LOST
        and case.resolution == CaseResolution.WRITE_OFF_PROPOSED
        and case.copy.status == CopyStatus.LOST
    )


def allowed_resolutions(
    case: LossDamageCase, *, price_options: bool | None = None
) -> tuple[str, ...]:
    """Dosyanın şu anki durumundan seçilebilecek çözümler (`CaseResolution` sırasıyla).

    - Kapanmış dosyada hiçbiri — TEK istisna: "Kayıttan düşme önerildi" ile
      kapanmış kayıp dosyasında nüsha hâlâ "Kayıp"sa "Bulundu" (öneri geri alınır;
      asıl kayıttan düşme yapılmadıkça kitap rafa dönebilir).
    - "Bulundu" yalnız kayıpta, "Onarıldı" yalnız hasarda.
    - Bedel yolları yalnız ortaöğretimde ve SIRAYLA: "Bedel belirlendi" →
      "Bedel teslim alındı" → "Bedelle aynısı / başka eser alındı". "Bedel
      belirlendi" dosyasında bedel yeniden belirlenebilir (düzeltme) ve bulunma,
      temin ve öneri yolları açık kalır (kitap sonradan bulunabilir; kişinin işi
      henüz sürer).
    - "Bedel teslim alındı" dosyasında YALNIZ iki kapanış yolu vardır ("Bedelle
      aynısı alındı", "Bedelle başka eser alındı") ve kademeden bağımsızdır:
      bedel alınmıştır, okulun açık işi kademe sonradan değişse de kapanabilmelidir.
    - "Kayba dönüştü" hiçbir zaman seçilemez (kayıp bildiriminin işidir).
    """
    if not case.is_open:
        return (CaseResolution.FOUND_RETURNED,) if oneri_geri_alinabilir(case) else ()
    if case.resolution == CaseResolution.PRICE_RECEIVED:
        return (CaseResolution.CLOSED_SAME_REPURCHASED, CaseResolution.CLOSED_OTHER_REPURCHASED)
    bedel = price_options_available() if price_options is None else price_options
    yollar: set[str] = {CaseResolution.REPLACED_SAME, CaseResolution.WRITE_OFF_PROPOSED}
    if case.case_type == CaseType.LOST:
        yollar.add(CaseResolution.FOUND_RETURNED)
    else:
        yollar.add(CaseResolution.REPAIRED)
    if bedel:
        yollar.add(CaseResolution.PRICE_DETERMINED)
        if case.resolution == CaseResolution.PRICE_DETERMINED:
            yollar.add(CaseResolution.PRICE_RECEIVED)
    return tuple(deger for deger in CaseResolution.values if deger in yollar)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _canli_nusha(copy: Copy) -> Copy:
    nusha: Copy | None = Copy.objects.select_related("work").filter(pk=copy.pk).first()
    if nusha is None:
        raise ValidationError(COPY_MISSING_MESSAGE)
    return nusha


def _not(responsible_note: str) -> str:
    metin = (responsible_note or "").strip()
    if len(metin) > RESPONSIBLE_NOTE_MAX:
        raise ValidationError({"responsible_note": NOTE_TOO_LONG_MESSAGE})
    return metin


def _tespit_tarihi(reported_on: date | None) -> date:
    bugun = timezone.localdate()
    tarih = reported_on or bugun
    if tarih > bugun:
        raise ValidationError({"reported_on": REPORTED_IN_FUTURE_MESSAGE})
    return tarih


def _acik_dosya_yok(copy: Copy) -> None:
    if selectors_teslim.open_case_for_copy(copy.pk) is not None:
        raise ValidationError(CASE_OPEN_EXISTS_MESSAGE)


def _hasari_kayba_donustur(dosya: LossDamageCase, simdi: datetime) -> None:
    """Açık hasar dosyasını "Kayba dönüştü" ile kapatır (kayıp bildiriminin parçası).

    Sorumlu, not ve (varsa) belirlenen bedelle teslim kaydı dosyanın kendi kaydında kalır; kayıp
    dosyasına taşınmaz — kaybın sorumlusu ödünçten ya da bildirimden gelir.
    """
    dosya.resolution = CaseResolution.CONVERTED_TO_LOSS
    dosya.resolved_at = simdi
    dosya.write_off_proposed_at = None
    dosya.save(update_fields=["resolution", "resolved_at", "write_off_proposed_at", "updated_at"])


def _uyelik(membership: Membership | None) -> Membership | None:
    if membership is None:
        return None
    guncel: Membership | None = Membership.objects.filter(pk=membership.pk).first()
    if guncel is None:
        raise ValidationError({"membership_id": MEMBERSHIP_MISSING_MESSAGE})
    return guncel


def _dosya_ac(**alanlar: object) -> LossDamageCase:
    """Dosyayı yazar; tek açık dosya kısıtı yarışta da Türkçe iletiye döner."""
    try:
        with transaction.atomic():
            dosya: LossDamageCase = LossDamageCase.objects.create(**alanlar)
            return dosya
    except IntegrityError as exc:
        raise ValidationError(CASE_OPEN_EXISTS_MESSAGE) from exc


def _onarimi_kapat(copy_pk: int) -> None:
    """Açık onarım kaydını bugünle kapatır ve nüshayı "Onarımda"dan rafa döndürür."""
    acik = selectors_teslim.open_repair_for_copy(copy_pk)
    if acik is not None:
        acik.returned_on = max(timezone.localdate(), acik.sent_on)
        acik.save(update_fields=["returned_on", "updated_at"])
    nusha_durumu.gecir(copy_pk, eski=CopyStatus.IN_REPAIR, yeni=CopyStatus.AVAILABLE)


# ---------------------------------------------------------------------------
# Kayıp bildirimi
# ---------------------------------------------------------------------------
@transaction.atomic
def report_lost(
    *,
    copy: Copy,
    membership: Membership | None = None,
    responsible_note: str = "",
    reported_on: date | None = None,
) -> LossDamageCase:
    """Kayıp bildirimi: kayıp dosyası açar, nüsha "Kayıp" olur (kural 3).

    Ödünçteki nüshada açık ödünç "Kayba dönüştü" ile kapanır ve dosya o ödünce ve
    üyeliğe bağlanır (`membership` verildiyse ödüncün üyeliğiyle aynı olmalıdır).
    Teslimdeki nüshada açık teslim aynı biçimde kapanır ve dosya teslime bağlanır;
    `membership` verilirse dosyanın kişisi o üyedir (teslim alan değil — kişi bağı
    önce üyeliğe bakar, `selectors_teslim.case_person`). Raftaki nüsha için sorumlu
    `membership` ya da `responsible_note` ile gösterilebilir (ikisi de isteğe
    bağlıdır). Nüshanın açık HASAR dosyası varsa o dosya "Kayba dönüştü" ile
    kapanır (kural 3); açık KAYIP dosyası nüshayı zaten "Kayıp" yapmıştır.
    """
    require_admin_mode()
    app_password.require_password_set()
    tmy_kapisi.ensure_open(tmy_kapisi.KAYIP_BILDIRIMI)
    nusha = _canli_nusha(copy)
    notu = _not(responsible_note)
    tarih = _tespit_tarihi(reported_on)
    uyelik = _uyelik(membership)
    if nusha.status in TERMINAL_COPY_STATUSES:
        raise ValidationError(COPY_TERMINAL_MESSAGE)
    if nusha.status == CopyStatus.LOST:
        raise ValidationError(LOST_ALREADY_MESSAGE)
    if nusha.status == CopyStatus.IN_REPAIR:
        raise ValidationError(LOST_IN_REPAIR_MESSAGE)
    hasar_dosyasi = selectors_teslim.open_case_for_copy(nusha.pk)
    if hasar_dosyasi is not None and hasar_dosyasi.case_type != CaseType.DAMAGED:
        raise ValidationError(CASE_OPEN_EXISTS_MESSAGE)

    simdi = timezone.now()
    odunc = Loan.objects.filter(copy_id=nusha.pk, status=LoanStatus.OPEN).first()
    if odunc is not None:
        if uyelik is not None and odunc.membership_id != uyelik.pk:
            raise ValidationError({"membership_id": MEMBERSHIP_MISMATCH_MESSAGE})
        uyelik = odunc.membership
        odunc.status = LoanStatus.LOST_CONVERTED
        odunc.lost_at = simdi
        odunc.save(update_fields=["status", "lost_at", "updated_at"])
    teslim = selectors_teslim.open_delivery_for_copy(nusha.pk)
    if teslim is not None:
        teslim.status = DeliveryStatus.LOST_CONVERTED
        teslim.lost_at = simdi
        teslim.save(update_fields=["status", "lost_at", "updated_at"])

    if not nusha_durumu.gecir(nusha.pk, eski=nusha.status, yeni=CopyStatus.LOST):
        raise ValidationError(COPY_STATE_CHANGED_MESSAGE)
    if hasar_dosyasi is not None:
        # Tek açık dosya kısıtı: hasar dosyası kayıp dosyasından ÖNCE kapanır.
        _hasari_kayba_donustur(hasar_dosyasi, simdi)
    dosya = _dosya_ac(
        copy=nusha,
        case_type=CaseType.LOST,
        membership=uyelik,
        loan=odunc,
        delivery=teslim,
        responsible_note=notu,
        reported_on=tarih,
    )
    if hasar_dosyasi is not None:
        logger.info("Kayıp bildirimi işlendi; hasar dosyası kayba dönüştü, kayıp dosyası açıldı.")
    else:
        logger.info("Kayıp bildirimi işlendi; kayıp dosyası açıldı.")
    return dosya


# ---------------------------------------------------------------------------
# Hasar dosyası (D3)
# ---------------------------------------------------------------------------
@transaction.atomic
def open_damage_case(
    *,
    copy: Copy,
    loan: Loan | None = None,
    delivery: Delivery | None = None,
    membership: Membership | None = None,
    responsible_note: str = "",
    reported_on: date | None = None,
    send_to_repair: bool = False,
) -> LossDamageCase:
    """Hasar dosyası açar (D3; kural 4). Nüsha rafta ya da onarımda olmalıdır.

    `loan`: iadesi alınmış ödünç (sorumlu üyelik ondan gelir); `delivery`: geri
    alınmış teslim. `membership` verildiyse ödüncün üyeliğiyle aynı olmalıdır.
    `send_to_repair`: raftaki nüsha aynı işlemde onarıma gönderilir; nüsha zaten
    onarımdaysa açık onarım kaydı dosyaya bağlanır.
    """
    require_admin_mode()
    app_password.require_password_set()
    nusha = _canli_nusha(copy)
    notu = _not(responsible_note)
    tarih = _tespit_tarihi(reported_on)
    uyelik = _uyelik(membership)
    engeller: dict[str, str] = {
        CopyStatus.ON_LOAN: DAMAGE_ON_LOAN_MESSAGE,
        CopyStatus.DELIVERED: DAMAGE_DELIVERED_MESSAGE,
        CopyStatus.LOST: DAMAGE_LOST_MESSAGE,
    }
    if nusha.status in TERMINAL_COPY_STATUSES:
        raise ValidationError(COPY_TERMINAL_MESSAGE)
    if nusha.status in engeller:
        raise ValidationError(engeller[nusha.status])
    _acik_dosya_yok(nusha)
    if loan is not None:
        if loan.copy_id != nusha.pk:
            raise ValidationError({"loan_id": LOAN_MISMATCH_MESSAGE})
        if loan.status == LoanStatus.OPEN:
            raise ValidationError({"loan_id": LOAN_STILL_OPEN_MESSAGE})
        if uyelik is not None and loan.membership_id not in (None, uyelik.pk):
            raise ValidationError({"membership_id": MEMBERSHIP_MISMATCH_MESSAGE})
        uyelik = uyelik or loan.membership
    if delivery is not None:
        if delivery.copy_id != nusha.pk:
            raise ValidationError({"delivery_id": DELIVERY_MISMATCH_MESSAGE})
        if delivery.is_open:
            raise ValidationError({"delivery_id": DELIVERY_STILL_OPEN_MESSAGE})

    dosya = _dosya_ac(
        copy=nusha,
        case_type=CaseType.DAMAGED,
        membership=uyelik,
        loan=loan,
        delivery=delivery,
        responsible_note=notu,
        reported_on=tarih,
    )
    if nusha.status == CopyStatus.IN_REPAIR:
        CopyRepair.objects.filter(
            copy_id=nusha.pk, returned_on__isnull=True, case__isnull=True
        ).update(case=dosya, updated_at=timezone.now())
    elif send_to_repair:
        _onarima_gonder(nusha, dosya)
    logger.info("Hasar dosyası açıldı.")
    return dosya


@transaction.atomic
def update_case_note(case: LossDamageCase, *, responsible_note: str) -> LossDamageCase:
    """Açık dosyanın sorumlu notunu günceller (şifreli alan; yalnız yönetici kipi)."""
    require_admin_mode()
    app_password.require_password_set()
    dosya: LossDamageCase = LossDamageCase.objects.get(pk=case.pk)
    if not dosya.is_open:
        raise ValidationError(CASE_CLOSED_MESSAGE)
    dosya.responsible_note = _not(responsible_note)
    dosya.save(update_fields=["responsible_note", "updated_at"])
    return dosya


# ---------------------------------------------------------------------------
# Çözüm durum makinesi
# ---------------------------------------------------------------------------
def _nushayi_rafa_dondur(dosya: LossDamageCase) -> None:
    """Nüsha kaynağı yerine geldi: kayıpta "Kayıp"tan, hasarda "Onarımda"dan rafa döner.

    Hasar dosyası nüshayı dolaşımdan çıkarmadığı için hasarda nüsha rafta, ödünçte
    ya da teslimde olabilir: yalnız onarımdaysa (onarım kaydı kapanarak) rafa döner.
    """
    if dosya.case_type == CaseType.LOST:
        if not nusha_durumu.gecir(dosya.copy_id, eski=CopyStatus.LOST, yeni=CopyStatus.AVAILABLE):
            raise ValidationError(FOUND_NOT_LOST_MESSAGE)
        return
    _onarimi_kapat(dosya.copy_id)


@transaction.atomic
def resolve_case(
    case: LossDamageCase, *, resolution: str, market_price: Decimal | None = None
) -> LossDamageCase:
    """Dosyayı çözer (kural 1, 2, 6, 7). Tahsilat YOK — bedel ve teslimi yalnız kaydedilir.

    Geçişler (seçilebilirler: `allowed_resolutions`):

    - "Bedel belirlendi" (yalnız ortaöğretim): piyasa bedeli zorunlu, adımın zamanı
      yazılır; dosya AÇIK kalır ve kişinin açık işi sürer, nüshaya dokunulmaz.
    - "Bedel teslim alındı" (yalnız "Bedel belirlendi"den): adımın zamanı yazılır;
      kişinin açık işi biter, dosya okul için AÇIK kalır, nüshaya dokunulmaz.
    - "Bulundu" (kayıp) · "Aynısı temin edildi" · "Bedelle aynısı alındı": kaynak
      yerine geldi — kayıpta nüsha rafa döner; hasarda nüsha onarımdaysa rafa döner.
    - "Onarıldı" (hasar): nüsha onarımdaysa onarım kapanır ve rafa döner.
    - "Kayıttan düşme önerildi" · "Bedelle başka eser alındı": öneri işaretlenir,
      nüshanın durumu DEĞİŞMEZ (asıl kayıttan düşme F8/F9).
    - Kapanmış dosyada yalnız öneri geri alınır: "Kayıttan düşme önerildi" ile
      kapanmış kayıp dosyasında nüsha hâlâ "Kayıp"sa "Bulundu" (öneri kalkar, nüsha
      rafa döner — `oneri_geri_alinabilir`). Öbür her istek "zaten kapanmış" alır.

    `market_price` yalnız "Bedel belirlendi"de kabul edilir (teslim alınan bedel
    sonradan değiştirilmez). TMY 32/3 kapısı yalnız kapsamdaki çözümlerde sorulur
    (`tmy_kapisi.dosya_cozumu_kapsamda_mi`).
    """
    require_admin_mode()
    app_password.require_password_set()
    dosya: LossDamageCase | None = (
        LossDamageCase.objects.select_related("copy").filter(pk=case.pk).first()
    )
    if dosya is None:
        raise ValidationError(COPY_MISSING_MESSAGE)
    if not dosya.is_open and resolution not in allowed_resolutions(dosya, price_options=False):
        raise ValidationError(CASE_CLOSED_MESSAGE)
    if resolution not in CaseResolution.values or resolution == CaseResolution.PENDING:
        raise ValidationError({"resolution": RESOLUTION_INVALID_MESSAGE})
    if tmy_kapisi.dosya_cozumu_kapsamda_mi(dosya.case_type, resolution):
        tmy_kapisi.ensure_open(tmy_kapisi.DOSYA_COZUMU)
    bedel = price_options_available()
    # Bedeli teslim alınmış dosyanın kapanışı kademeden bağımsızdır (kural 1).
    teslim_alinmis = dosya.resolution == CaseResolution.PRICE_RECEIVED
    if (
        (resolution in PRICE_RESOLUTIONS or market_price is not None)
        and not bedel
        and not teslim_alinmis
    ):
        alan = "resolution" if resolution in PRICE_RESOLUTIONS else "market_price"
        raise ValidationError({alan: PRICE_ONLY_ORTAOGRETIM_MESSAGE})
    if resolution not in allowed_resolutions(dosya, price_options=bedel):
        etiket = CaseResolution(resolution).label
        raise ValidationError({"resolution": RESOLUTION_NOT_ALLOWED_MESSAGE.format(cozum=etiket)})
    if market_price is not None and resolution != CaseResolution.PRICE_DETERMINED:
        raise ValidationError({"market_price": PRICE_ONLY_ON_PRICE_PATH_MESSAGE})
    if resolution == CaseResolution.PRICE_DETERMINED and market_price is None:
        raise ValidationError({"market_price": PRICE_REQUIRED_MESSAGE})

    simdi = timezone.now()
    if market_price is not None:
        if market_price <= 0:
            raise ValidationError({"market_price": PRICE_REQUIRED_MESSAGE})
        dosya.market_price = market_price
        dosya.price_determined_at = simdi
    if resolution in PRICE_RESOLUTIONS and dosya.market_price is None:
        raise ValidationError({"market_price": PRICE_REQUIRED_MESSAGE})
    if resolution == CaseResolution.PRICE_RECEIVED:
        dosya.price_received_at = simdi
    if resolution in (
        CaseResolution.FOUND_RETURNED,
        CaseResolution.REPLACED_SAME,
        CaseResolution.CLOSED_SAME_REPURCHASED,
    ):
        _nushayi_rafa_dondur(dosya)
    elif resolution == CaseResolution.REPAIRED:
        _onarimi_kapat(dosya.copy_id)
    dosya.resolution = resolution
    dosya.resolved_at = None if resolution in OPEN_CASE_RESOLUTIONS else simdi
    dosya.write_off_proposed_at = simdi if resolution in WRITE_OFF_RESOLUTIONS else None
    dosya.save(
        update_fields=[
            "resolution",
            "market_price",
            "price_determined_at",
            "price_received_at",
            "resolved_at",
            "write_off_proposed_at",
            "updated_at",
        ]
    )
    logger.info("Kayıp/hasar dosyasına çözüm işlendi.")
    return dosya


# ---------------------------------------------------------------------------
# Onarım (D3)
# ---------------------------------------------------------------------------
def _onarima_gonder(nusha: Copy, dosya: LossDamageCase | None) -> CopyRepair:
    if not nusha_durumu.gecir(nusha.pk, eski=CopyStatus.AVAILABLE, yeni=CopyStatus.IN_REPAIR):
        guncel = Copy.all_objects.get(pk=nusha.pk)
        raise ValidationError(
            REPAIR_NOT_AVAILABLE_MESSAGE.format(durum=guncel.get_status_display())
        )
    try:
        with transaction.atomic():
            kayit: CopyRepair = CopyRepair.objects.create(
                copy=nusha, case=dosya, sent_on=timezone.localdate()
            )
            return kayit
    except IntegrityError as exc:
        raise ValidationError(COPY_STATE_CHANGED_MESSAGE) from exc


@transaction.atomic
def send_to_repair(copy: Copy, *, case: LossDamageCase | None = None) -> CopyRepair:
    """Onarıma gönder: "Rafta" → "Onarımda" + onarım kaydı (D3). Yalnız yönetici kipi.

    `case` verilmezse nüshanın çözülmemiş HASAR dosyası (varsa) kayda bağlanır.
    """
    require_admin_mode()
    nusha = _canli_nusha(copy)
    if nusha.status != CopyStatus.AVAILABLE:
        raise ValidationError(REPAIR_NOT_AVAILABLE_MESSAGE.format(durum=nusha.get_status_display()))
    dosya = case
    if dosya is None:
        acik = selectors_teslim.open_case_for_copy(nusha.pk)
        dosya = acik if acik is not None and acik.case_type == CaseType.DAMAGED else None
    kayit = _onarima_gonder(nusha, dosya)
    logger.info("Nüsha onarıma gönderildi.")
    return kayit


@transaction.atomic
def return_from_repair(copy: Copy) -> CopyRepair | None:
    """Onarımdan dön: onarım kaydı kapanır, "Onarımda" → "Rafta" (D3). Yalnız yönetici kipi.

    Hasar dosyasını KENDİLİĞİNDEN kapatmaz: Md. 19 yükümlülüğü (ortaöğretimde temin
    ya da bedel) onarımdan bağımsızdır; dosya "Onarıldı" ile ayrıca çözülür.
    Kaydı olmayan (eski veriden gelen) "Onarımda" nüsha da rafa döner; dönüş None.
    """
    require_admin_mode()
    nusha = _canli_nusha(copy)
    acik = selectors_teslim.open_repair_for_copy(nusha.pk)
    if nusha.status != CopyStatus.IN_REPAIR and acik is None:
        raise ValidationError(REPAIR_NOT_IN_REPAIR_MESSAGE)
    _onarimi_kapat(nusha.pk)
    logger.info("Nüsha onarımdan döndü.")
    if acik is None:
        return None
    acik.refresh_from_db()
    return acik


# ---------------------------------------------------------------------------
# Kişi kayıt defterine kaydolan kanca (apps.okul.services.persons)
# ---------------------------------------------------------------------------
def open_case_obligations(person: Person) -> list[str]:
    """Açık yükümlülük: kişinin çözülmemiş kayıp/hasar dosyaları (ad içermez).

    Yalnız "Çözüm bekliyor" ve "Bedel belirlendi" sayılır (kural 9): bedeli teslim
    alınmış dosya okulun işidir, kişiyi silmeyi ya da ilişiği engellemez.
    """
    sayi = selectors_teslim.open_cases_for_person(person).count()
    return [CASE_OPEN_OBLIGATION.format(sayi=sayi)] if sayi else []


def register_hooks() -> None:
    """Kancayı kişi kayıt defterine kaydeder (fikirdeş — `KutuphaneConfig.ready`)."""
    persons.register_obligation_check(open_case_obligations)
