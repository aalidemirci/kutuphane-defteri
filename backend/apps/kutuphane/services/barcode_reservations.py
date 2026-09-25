"""Boş barkod aralığı — ayırma, iptal, basım işareti ve hızlı kayıtta bağlama (yöntem B).

Okulun ASIL yolu budur (tasarım §8.1, S8 — 23.09.2026): hazır bir liste yoktur.
Akış:

1. **Ayır** — kullanıcı adet girer; numaralar nüsha sayacından (tek sayaç,
   `services.numbering.reserve_identities`) ardışık alınır.
2. **Bas** — ayrılmış numaralar için boş barkod etiketi basılır (etiket motoru,
   `services.label_render`); kullanıcı basımı onaylar (D10 kuralı: PDF üretmek
   "basıldı" değildir).
3. **Yapıştır** — etiketler raf başında kitaplara yapıştırılır.
4. **Bağla** — hızlı kayıtta kitap elde künye girilir, kitaptaki etiket
   okutulur ve nüsha O numarayla açılır (`bind_label`).
5. **İptal** — kullanılmayan (bozulan, kaybolan) etiketin numarası iptal edilir.

**Numara asla yeniden verilmez** (§7.1). Bunun dört kapısı vardır:

- sayaç ayrılan numaraların ötesine geçmiştir (`next_copy_identity` onları
  üretemez);
- bağlı numara ikinci kez bağlanamaz (`ReservedBarcode.copy` OneToOne,
  `Copy.barcode` düz `unique`, servis denetimi kilit altında yeniden yapılır);
- iptal edilen numara bağlanamaz ve iptali geri alan bir yol YOKTUR;
- nüsha yaratan öbür yollar barkodu dışarıdan kabul etmez
  (`catalog.PROTECTED_COPY_FIELDS`).

Kullanıcı iletileri docs/sozluk.md diliyle yazılır ("kütüphane etiketi",
"okutun"); iç kodlar metne girmez.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane.barcode import ScanKind
from apps.kutuphane.models import (
    MAX_LABELS_PER_JOB,
    MAX_LABELS_PER_JOB_TEXT,
    Acquisition,
    BarcodeReservation,
    Copy,
    LabelCalibration,
    LabelSheetTemplate,
    ReservedBarcode,
    Work,
)
from apps.kutuphane.services import catalog, label_render, numbering, tmy_kapisi

# ---------------------------------------------------------------------------
# Okutulan kodun çözümü (classify_scan + veritabanı)
# ---------------------------------------------------------------------------


def reservation_kind(digits: str) -> ScanKind | None:
    """Bağlanmamış ayrılmış numaranın türü: açıksa `RESERVED`, iptal edildiyse `CANCELLED`.

    Numara ayrılmamışsa ya da bir nüshaya bağlandıysa `None` (nüsha barkodudur).
    """
    satir = (
        ReservedBarcode.objects.filter(barcode=digits, copy__isnull=True)
        .values("cancelled_at")
        .first()
    )
    if satir is None:
        return None
    return ScanKind.CANCELLED if satir["cancelled_at"] is not None else ScanKind.RESERVED


def classify(value: object) -> ScanKind:
    """`barcode.classify_scan`'in veritabanını bilen hâli: ayrılmış numara ayrı türdür.

    Açık numara `RESERVED` (F6 masası: "bu etiket henüz bir kitaba bağlanmadı"),
    iptal edilmiş numara `CANCELLED` (etiket sökülür) döner.
    """
    return barcode_module.classify_scan(value, reservation_kind=reservation_kind)


@dataclass(frozen=True)
class ScanInfo:
    """Okutulan kodun türü ve (varsa) arkasındaki kayıtlar.

    `copy` silinmiş nüsha da olabilir (`Copy.all_objects`): silinmiş nüshanın
    numarası yeniden kullanılmaz, kullanıcıya "kayıt yok" yerine doğru neden
    söylenmelidir.
    """

    kind: ScanKind
    digits: str
    copy: Copy | None = None
    reserved: ReservedBarcode | None = None

    @property
    def is_cancelled_reservation(self) -> bool:
        return self.reserved is not None and self.reserved.cancelled_at is not None

    @property
    def is_open_reservation(self) -> bool:
        return (
            self.kind == ScanKind.RESERVED
            and self.reserved is not None
            and self.reserved.cancelled_at is None
        )


def describe_scan(value: object) -> ScanInfo:
    """Okutulan kodu çözer: tür + nüsha + ayrılmış numara satırı."""
    digits = barcode_module.normalize_scan(value)
    kind = classify(value)
    if kind not in (ScanKind.COPY, ScanKind.RESERVED, ScanKind.CANCELLED):
        return ScanInfo(kind=kind, digits=digits)
    reserved = ReservedBarcode.objects.select_related("reservation").filter(barcode=digits).first()
    copy = None
    if kind == ScanKind.COPY:
        copy = Copy.all_objects.select_related("work").filter(barcode=digits).first()
    return ScanInfo(kind=kind, digits=digits, copy=copy, reserved=reserved)


# ---------------------------------------------------------------------------
# Hızlı kayıtta bağlama — iletiler
# ---------------------------------------------------------------------------
BIND_EMPTY = "Kitaba yapıştırdığınız kütüphane etiketini okutun."
BIND_ISBN = "Bu ISBN barkodu. Kitaba yapıştırdığınız kütüphane etiketini okutun."
BIND_MEMBER_CARD = "Bu bir üye kartı numarası. Kitaba yapıştırdığınız kütüphane etiketini okutun."
BIND_UNKNOWN = "Bu kod bir kütüphane etiketi değil. Kitaba yapıştırdığınız etiketi okutun."
BIND_NOT_RESERVED = (
    "Bu numara boş barkod aralığından ayrılmış bir etiket değil. Yalnız Boş Barkod "
    "Aralığı'ndan basılan etiketler hızlı kayıtta bağlanabilir."
)
BIND_CANCELLED = (
    "Bu etiketin numarası iptal edildi; kullanılamaz. Etiketi kitaptan sökün ve başka bir "
    "boş etiket yapıştırın."
)
BIND_DELETED_COPY = (
    "Bu numara silinmiş bir nüshaya aitti; numaralar yeniden kullanılmaz. Etiketi kitaptan "
    "sökün ve başka bir boş etiket yapıştırın."
)
BIND_READY = "Etiket boş; kayıtta nüsha bu numarayla açılacak."
#: Etiketsiz kitap için ön yüzün sunduğu yol (bugünkü davranış: sayaçtan yeni numara).
NEW_NUMBER_HINT = "Kitapta etiket yoksa “Etiket yok — yeni numara ver” seçeneğini kullanın."


def _bound_message(copy: Copy) -> str:
    """Numara zaten bir nüshaya bağlı: hangi kitaba bağlı olduğu söylenir (kişisel veri yok).

    En olası durum, elinizdeki kitabın ZATEN kayıtlı olmasıdır (raflar karışır,
    iki kişi aynı rafı işler): ileti önce bunu söyler. Yeni numara önerilmez —
    aynı kitabı ikinci kez kaydetmek sayımda bulunamayacak bir nüsha açardı.
    """
    return (
        f"Bu etiket zaten kayıtlı bir nüshanın: {barcode_module.format_barcode(copy.barcode)} "
        f"— {copy.work.title}. Elinizdeki kitap buysa kitap zaten kayıtlıdır; yeniden "
        "kaydetmeyin. Başka bir kitapsa etiketi sökün ve kitaba başka bir boş etiket yapıştırın."
    )


def bind_rejection(info: ScanInfo) -> str:
    """Okutulan kod bağlanamıyorsa Türkçe gerekçe; bağlanabiliyorsa ''."""
    if not info.digits:
        return BIND_EMPTY
    if info.kind == ScanKind.ISBN:
        return BIND_ISBN
    if info.kind == ScanKind.MEMBER_CARD:
        return BIND_MEMBER_CARD
    if info.kind == ScanKind.UNKNOWN:
        return BIND_UNKNOWN
    if info.kind == ScanKind.CANCELLED:
        return BIND_CANCELLED
    if info.kind == ScanKind.RESERVED:
        return ""
    # Biçimce nüsha barkodu ama açık bir ayrılmış numara değil.
    if info.copy is not None:
        if info.copy.deleted_at is not None:
            return BIND_DELETED_COPY
        return _bound_message(info.copy)
    return BIND_NOT_RESERVED


def check_label(value: object) -> dict[str, Any]:
    """Hızlı kayıt ön denetimi: okutulan etiket bağlanabilir mi? (yazma YOK)

    Ön yüz eseri açmadan ÖNCE sorar: bağlanamayacak bir etiket için eser açılıp
    nüshasız kalmasın.

    Ret ipucu ("Etiket yok — yeni numara ver") numara başka bir CANLI nüshaya
    bağlıyken verilmez: kitap büyük olasılıkla zaten kayıtlıdır (`_bound_message`).

    F9: TMY 32/3 durdurması sürerken etiket bağlanabilir DEĞİLDİR (nüsha açma kapısı
    `catalog.validate_new_copy`'dedir; ön denetim onu önceden söyler — eser açılıp
    nüshasız kalmasın). Yeni numara ipucu da verilmez: o yol da aynı kapıya takılır.
    """
    info = describe_scan(value)
    durdurma = tmy_kapisi.durdurma_iletisi(tmy_kapisi.EDINIM)
    gerekce = durdurma or bind_rejection(info)
    bagli = info.copy if info.copy is not None and info.copy.deleted_at is None else None
    ipucu = NEW_NUMBER_HINT if gerekce and not durdurma and bagli is None else ""
    return {
        "bindable": not gerekce,
        "kind": str(info.kind),
        "barcode": info.digits,
        "barcode_display": barcode_module.format_barcode(info.digits) if info.digits else "",
        "reservation": info.reserved.reservation_id if info.reserved is not None else None,
        "copy": bagli.pk if bagli is not None else None,
        "work_title": bagli.work.title if bagli is not None else "",
        "message": gerekce or BIND_READY,
        "hint": ipucu,
    }


@transaction.atomic
def bind_label(*, label: object, work: Work, acquisition: Acquisition, **fields: Any) -> Copy:
    """Önceden basılmış boş etiketin numarasıyla TEK nüsha açar (hızlı kayıt, yöntem B).

    Sıra: önce etiket (kullanıcının az önce okuttuğu şey), sonra nüsha kuralları
    (`catalog.validate_new_copy` — sayaçlı yolla AYNI kapı). Numara satırı
    kilit altında yeniden okunur ve durumu yeniden denetlenir: iki istek aynı
    etiketi bağlamaya çalışırsa ikincisi Türkçe retle döner; son savunma
    `ReservedBarcode.copy` (OneToOne) ve `Copy.barcode` (düz `unique`)
    kısıtlarıdır.

    Etiket kitabın üzerindedir ve az önce okutulmuştur, bu yüzden nüsha
    **barkod etiketi basılmış ve doğrulanmış** olarak açılır: basım tarihi
    aralığın basım onayıdır (onaylanmamışsa şimdi), doğrulama şimdidir. Sırt
    etiketi işareti boş kalır — nüsha sırt kuyruğuna girer (künye tamamlanınca
    yer numarası basılır).
    """
    info = describe_scan(label)
    gerekce = bind_rejection(info)
    if gerekce:
        raise ValidationError({"label_code": gerekce})
    assert info.reserved is not None  # bind_rejection '' döndüyse açık bir numaradır
    numara = ReservedBarcode.objects.select_for_update().select_related("reservation")
    satir = numara.get(pk=info.reserved.pk)
    if satir.copy_id is not None or satir.cancelled_at is not None:
        # Denetim ile kilit arasında durum değişti (ikinci istek).
        raise ValidationError({"label_code": bind_rejection(describe_scan(satir.barcode))})

    alanlar = catalog.validate_new_copy(work=work, acquisition=acquisition, **fields)
    simdi = timezone.now()
    copy: Copy = Copy.objects.create(
        accession_no=satir.accession_no,
        barcode=satir.barcode,
        label_printed_at=satir.reservation.printed_at or simdi,
        label_verified_at=simdi,
        **alanlar,
    )
    satir.copy = copy
    satir.bound_at = simdi
    satir.save(update_fields=["copy", "bound_at"])
    return copy


# ---------------------------------------------------------------------------
# Ayırma, iptal, basım işareti
# ---------------------------------------------------------------------------
@transaction.atomic
def reserve(count: int, *, note: str = "") -> BarcodeReservation:
    """`count` numaralık boş barkod aralığı ayırır (tek işlem, ardışık, aynı yıl).

    Sayaç dolacaksa HİÇBİR numara ayrılmaz (Türkçe ret; sayaç yerinde kalır).
    """
    if not 1 <= int(count) <= MAX_LABELS_PER_JOB:
        raise ValidationError(
            {"count": f"Tek seferde 1 ile {MAX_LABELS_PER_JOB_TEXT} arasında numara ayrılır."}
        )
    try:
        kimlikler = numbering.reserve_identities(int(count))
    except barcode_module.BarcodeRangeError as exc:
        raise ValidationError({"count": str(exc)}) from exc
    ilk = kimlikler[0][1]
    son = kimlikler[-1][1]
    aralik: BarcodeReservation = BarcodeReservation.objects.create(
        year=int(ilk[:4]),
        first_barcode=ilk,
        last_barcode=son,
        count=len(kimlikler),
        note=str(note or "").strip(),
    )
    ReservedBarcode.objects.bulk_create(
        [ReservedBarcode(reservation=aralik, accession_no=no, barcode=kod) for no, kod in kimlikler]
    )
    return aralik


def _normalized_barcodes(values: Sequence[object]) -> list[str]:
    """Kullanıcının yazdığı ya da okuttuğu numaraları rakamlara indirir (sıra korunur)."""
    return list(dict.fromkeys(barcode_module.normalize_scan(value) for value in values))


@transaction.atomic
def cancel_numbers(
    reservation: BarcodeReservation,
    *,
    barcodes: Sequence[object] | None = None,
    reason: str = "",
) -> int:
    """Aralığın kullanılmayan numaralarını İPTAL eder; iptal edilen sayıyı döndürür.

    `barcodes` verilmezse aralığın bütün AÇIK numaraları iptal edilir (bağlı
    olanlar olduğu gibi kalır). Verilirse her numara bu aralıkta olmalı ve bir
    nüshaya bağlı olmamalıdır; zaten iptal edilmiş numara sessizce atlanır.

    İptal GERİ ALINMAZ ve numara sayaca DÖNMEZ (§7.1): etiket basılmış olabilir,
    bir kitaba yapıştırılmış ve kaybolmuş olabilir — aynı numaranın ikinci bir
    etikette yaşaması masada iki kitabı birbirine karıştırırdı.
    """
    acik = reservation.numbers.select_for_update().filter(
        copy__isnull=True, cancelled_at__isnull=True
    )
    if barcodes is not None:
        istenen = [kod for kod in _normalized_barcodes(barcodes) if kod]
        if not istenen:
            raise ValidationError({"barcodes": "İptal edilecek numarayı yazın ya da okutun."})
        bulunan = {
            satir.barcode: satir for satir in reservation.numbers.filter(barcode__in=istenen)
        }
        yabanci = [kod for kod in istenen if kod not in bulunan]
        if yabanci:
            raise ValidationError(
                {
                    "barcodes": (
                        "Şu numaralar bu aralıkta değil: "
                        + ", ".join(barcode_module.format_barcode(kod) for kod in yabanci)
                        + "."
                    )
                }
            )
        bagli = [kod for kod in istenen if bulunan[kod].copy_id is not None]
        if bagli:
            raise ValidationError(
                {
                    "barcodes": (
                        "Şu numaralar bir nüshaya bağlı; iptal edilemez: "
                        + ", ".join(barcode_module.format_barcode(kod) for kod in bagli)
                        + "."
                    )
                }
            )
        acik = acik.filter(barcode__in=istenen)
    return int(
        acik.update(cancelled_at=timezone.now(), cancel_reason=str(reason or "").strip()[:255])
    )


def _locked(reservation: BarcodeReservation) -> BarcodeReservation:
    """Aralığı işlem içinde yeniden okur: çift tıklamada ikinci istek eski hâli görmesin.

    Uç aralığı işlem DIŞINDA okur; durum denetimi o bayat nesneye bakarsa iki
    istek de "işaretsiz" görür (`label_queue._locked` ile aynı desen).
    """
    aralik: BarcodeReservation = BarcodeReservation.objects.select_for_update().get(
        pk=reservation.pk
    )
    return aralik


@transaction.atomic
def confirm_print(reservation: BarcodeReservation) -> BarcodeReservation:
    """ "Basıldı olarak işaretle" — aralığın boş etiketleri basıldı (D10 kuralı).

    Durum kilit altında TAZE satırdan denetlenir (çift tıklamada ikinci istek
    reddedilir); yazılan damga çağıranın nesnesine de işlenir ve o döner.
    """
    kilitli = _locked(reservation)
    if kilitli.printed_at is not None:
        raise ValidationError(
            {"reservation": "Bu aralığın etiketleri zaten basıldı olarak işaretli."}
        )
    if not kilitli.numbers.filter(cancelled_at__isnull=True).exists():
        raise ValidationError(
            {"reservation": "Bu aralığın bütün numaraları iptal edilmiş; basılacak etiket yok."}
        )
    kilitli.printed_at = timezone.now()
    kilitli.save(update_fields=["printed_at", "updated_at"])
    reservation.printed_at = kilitli.printed_at
    reservation.updated_at = kilitli.updated_at
    return reservation


@transaction.atomic
def revert_print(reservation: BarcodeReservation) -> BarcodeReservation:
    """Basım işaretini geri alır; aralıktan kitaba bağlanmış etiket varsa reddeder.

    Bağlanmış etiket, basımın gerçekten yapıldığının kanıtıdır (kitabın üzerinde
    okutuldu). Basımı bozulan etiketler için doğru yol, o numaraları iptal edip
    yeni bir aralık ayırmaktır. Durum `confirm_print` gibi taze satırdan denetlenir.
    """
    kilitli = _locked(reservation)
    if kilitli.printed_at is None:
        raise ValidationError(
            {"reservation": "Bu aralığın etiketleri basıldı olarak işaretli değil."}
        )
    bagli = kilitli.numbers.filter(copy__isnull=False).count()
    if bagli:
        raise ValidationError(
            {
                "reservation": (
                    f"Bu aralıktan {bagli} etiket kitaplara bağlandı; basım işareti geri "
                    "alınamaz. Bozulan etiketlerin numaralarını iptal edin."
                )
            }
        )
    kilitli.printed_at = None
    kilitli.save(update_fields=["printed_at", "updated_at"])
    reservation.printed_at = None
    reservation.updated_at = kilitli.updated_at
    return reservation


# ---------------------------------------------------------------------------
# Basım (PDF) — etiket motoruna tek kapıdan
# ---------------------------------------------------------------------------
def printable_numbers(
    reservation: BarcodeReservation, *, barcodes: Sequence[object] | None = None
) -> list[str]:
    """Boş etiketi basılacak numaralar: AÇIK olanlar (bağlı ve iptal edilmiş basılmaz).

    `barcodes` verilirse yalnız onlar (ör. bozulan tek etiketin yeniden basımı);
    her biri bu aralığın açık numarası olmalıdır. Bağlı numaranın etiketi artık
    bir nüshanındır ve olağan basım partisiyle basılır; iptal edilen numaranın
    etiketi hiç basılmaz.
    """
    acik = list(
        reservation.numbers.filter(copy__isnull=True, cancelled_at__isnull=True)
        .order_by("accession_no")
        .values_list("barcode", flat=True)
    )
    if barcodes is None:
        if not acik:
            raise ValidationError({"reservation": "Bu aralıkta basılacak açık numara kalmadı."})
        return acik
    istenen = [kod for kod in _normalized_barcodes(barcodes) if kod]
    acik_kume = set(acik)
    uygunsuz = [kod for kod in istenen if kod not in acik_kume]
    if uygunsuz or not istenen:
        raise ValidationError(
            {
                "barcodes": (
                    "Yalnız bu aralığın bağlanmamış ve iptal edilmemiş numaraları basılır: "
                    + ", ".join(barcode_module.format_barcode(kod) for kod in uygunsuz)
                    + "."
                )
                if uygunsuz
                else "Basılacak numarayı yazın."
            }
        )
    return sorted(istenen)


def open_numbers(barcodes: Sequence[object]) -> list[str]:
    """Aralıktan bağımsız boş etiket basımı (önizleme ucu) için numara kapısı.

    Her numara boş barkod aralığından AYRILMIŞ, bağlanmamış ve iptal edilmemiş
    olmalıdır — `printable_numbers` ile aynı kural. Aksi hâlde iptal edilmiş
    numaranın etiketi yeniden basılabilir, başka bir nüshaya bağlı numara ikinci
    bir kitaba yapıştırılabilir ya da sayacın henüz vermediği bir numara basılır
    ve sayaç onu ileride başka bir nüshaya verince iki kitap aynı etiketi taşır.
    Sıra korunur; yinelenen numarayı motor reddeder (`validate_items`).
    """
    istenen = [barcode_module.normalize_scan(value) for value in barcodes]
    istenen = [kod for kod in istenen if kod]
    if not istenen:
        raise ValidationError({"barcodes": "Basılacak numarayı yazın."})
    acik = set(
        ReservedBarcode.objects.filter(
            barcode__in=istenen, copy__isnull=True, cancelled_at__isnull=True
        ).values_list("barcode", flat=True)
    )
    uygunsuz = list(dict.fromkeys(kod for kod in istenen if kod not in acik))
    if uygunsuz:
        raise ValidationError(
            {
                "barcodes": (
                    "Boş barkod etiketi yalnız Boş Barkod Aralığı'ndan ayrılmış, bağlanmamış "
                    "ve iptal edilmemiş numaralara basılır: "
                    + ", ".join(barcode_module.format_barcode(kod) for kod in uygunsuz)
                    + "."
                )
            }
        )
    return istenen


def render_pdf(
    reservation: BarcodeReservation,
    *,
    template: LabelSheetTemplate,
    calibration: LabelCalibration | None = None,
    start_cell: int = 1,
    barcodes: Sequence[object] | None = None,
    include_qr: bool = False,
) -> bytes:
    """Aralığın boş barkod etiketlerinin PDF'i. İŞARETE DOKUNMAZ (D10)."""
    label_render.validate_print_setup(
        template=template, calibration=calibration, start_cell=start_cell
    )
    numaralar = printable_numbers(reservation, barcodes=barcodes)
    return label_render.render_job(
        label_render.LabelJob(
            kind=label_render.BLANK_KIND,
            template=template,
            calibration=calibration,
            start_cell=start_cell,
            barcodes=tuple(numaralar),
            include_qr=include_qr,
        )
    )


#: Belge adı (sözlük §2 E1; `labels.render.DOCUMENT_NAMES` ve ön yüzün
#: `BOS_BARKOD_BELGE_ADI` ile AYNI — eşitliği test sınar).
BLANK_DOCUMENT_NAME = "Boş Barkod Etiketi"


def pdf_filename(reservation: BarcodeReservation) -> str:
    """İndirme adı: belge adı + numara aralığı + yerel tarih (sözlük §3).

    'Boş-Barkod-Etiketi_2026-000001_2026-000065_24.09.2026.pdf' — ön yüzün
    `bosBarkodDosyaAdi` ile aynı biçim; iç kimlik (aralık numarası) geçmez.
    """
    ilk = barcode_module.format_barcode(reservation.first_barcode)
    son = barcode_module.format_barcode(reservation.last_barcode)
    gun = timezone.localdate()
    return f"{BLANK_DOCUMENT_NAME.replace(' ', '-')}_{ilk}_{son}_{gun:%d.%m.%Y}.pdf"
