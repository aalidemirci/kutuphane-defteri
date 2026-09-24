"""Etiket basım kuyruğu, basım kaydı (D10) ve doğrulama okutması (F4-Q, tasarım §7.2).

**PDF üretmek "basıldı" demek DEĞİLDİR** (D10). OYS işareti PDF üretilince
koyuyordu; yazıcı sıkışınca, kâğıt ters takılınca ya da PDF hiç
yazdırılmayınca nüshalar kuyruktan düşüyor ve kayboluyordu. Burada:

1. `create_batch` bir **basım partisi** açar (hangi nüshalar, hangi sırayla,
   hangi şablon/kalibrasyon/başlangıç hücresiyle). İşaretlere DOKUNMAZ.
2. `render_batch_pdf` partinin PDF'ini üretir — istenildiği kadar, her hâlde
   yeniden (aynı partinin yeniden basımı). İşaretlere DOKUNMAZ.
3. `confirm_batch` — kullanıcının "Basıldı olarak işaretle" demesi. İşaretler
   yazılır; her nüshanın ESKİ işaretleri kalemde saklanır.
4. `revert_batch` — basım işaretini **geri alır**: işaretler onaydan önceki
   değerlerine döner, parti SİLİNMEZ (iz kalır).
5. `discard_batch` — onaylanmamış partiden vazgeçer (iz kalır).
6. `reprint_batch` — aynı nüshaları AYNI SIRAYLA yeni bir partide basar
   (başka başlangıç hücresi, şablon ya da kalibrasyonla).

**Geri almanın iki kuralı.**

- *Sonraki basım önce gelir.* Bir nüshanın işareti bu partiden SONRA başka bir
  partiyle yeniden yazıldıysa ve o parti hâlâ onaylıysa geri alma reddedilir
  ("önce o partiyi geri alın"). Aksi hâlde eski partinin geri alınması
  yenisinin işaretini silerdi. Sonraki parti geri alınmışsa engel kalkar;
  doğrulandığı için işareti o partide korunan nüshaya dokunulmaz.
- *Okutulmuş etiket basılmıştır.* Barkod etiketi içeren partide, onaydan sonra
  barkodu okutularak doğrulanan nüshanın İKİ işareti de (barkod ve sırt)
  KORUNUR: etiketler kitabın üzerinde, barkod okundu; nüsha ne barkod ne sırt
  kuyruğuna döner (kullanıcı kararı 24.09.2026). Böyle bir nüshaya
  dokunulmadığı için sonraki bir partinin işareti de geri almayı engellemez.
  Yalnız doğrulanmamış nüshalar kuyruğa döner. Tipik durum: 5 tabakanın 3'ü
  kaymış basıldı, düzgün çıkanlar yapıştırılıp okutuldu, gerisi geri alınır.
  Yalnız sırt etiketi basan partide doğrulama yoktur (sırt barkod taşımaz):
  bütün nüshaların sırt işareti geri alınır.

**Barkod etiketinin yeniden basımı doğrulamayı sıfırlar**: yeni etiket henüz
okutulmamıştır, "doğrulanmamışlar" listesine girer. Geri almada eski doğrulama
geri gelir.

**Doğrulama okutması** (`verify_scan`): etiket yapıştırıldıktan sonra okutulur
→ `label_verified_at`. Yanlış kod türü (ISBN, üye kartı, henüz bağlanmamış boş
etiket) ayırt edilir ve Türkçe ileti verilir; okutma bir OLAYDIR, hata değil —
sonuç her durumda bir yanıt gövdesidir (tarama ekranı odağı kaybetmesin).
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_kuyruk
from apps.kutuphane.barcode import ScanKind
from apps.kutuphane.models import (
    BARCODE_PRINT_KINDS,
    MAX_LABELS_PER_JOB,
    MAX_LABELS_PER_JOB_TEXT,
    SPINE_PRINT_KINDS,
    TERMINAL_COPY_STATUSES,
    Copy,
    LabelCalibration,
    LabelOrder,
    LabelPrintBatch,
    LabelPrintBatchItem,
    LabelPrintBatchStatus,
    LabelPrintKind,
    LabelSheetTemplate,
)
from apps.kutuphane.services import barcode_reservations, label_render


# ---------------------------------------------------------------------------
# Parti açma
# ---------------------------------------------------------------------------
def _require_choice(value: str, choices: Sequence[str], field: str, label: str) -> None:
    if value not in choices:
        raise ValidationError({field: f"Geçerli bir {label} seçin."})


def _checked_copy_ids(copy_ids: Sequence[int]) -> list[int]:
    """Seçilen nüsha kimlikleri: boş değil, sınırı aşmıyor, hepsi etiketlenebilir.

    Yinelenen kimlik tek sayılır (aynı nüshanın iki etiketi aynı partide
    basılmaz). Silinmiş nüsha bulunamaz sayılır; kayıttan düşülmüş ya da
    devredilmiş nüshaya etiket basılmaz.
    """
    kimlikler = list(dict.fromkeys(int(pk) for pk in copy_ids))
    if not kimlikler:
        raise ValidationError({"copies": "Etiketi basılacak nüshaları seçin."})
    if len(kimlikler) > MAX_LABELS_PER_JOB:
        raise ValidationError(
            {
                "copies": (
                    f"Bir basım partisine en çok {MAX_LABELS_PER_JOB_TEXT} nüsha girer; seçimi bölün."
                )
            }
        )
    durumlar = dict(Copy.objects.filter(pk__in=kimlikler).values_list("pk", "status"))
    eksik = [pk for pk in kimlikler if pk not in durumlar]
    if eksik:
        raise ValidationError(
            {"copies": f"Seçilen nüshalardan {len(eksik)} tanesi bulunamadı ya da silinmiş."}
        )
    dusen = [pk for pk in kimlikler if durumlar[pk] in TERMINAL_COPY_STATUSES]
    if dusen:
        raise ValidationError(
            {
                "copies": (
                    f"Seçilen nüshalardan {len(dusen)} tanesi kayıttan düşülmüş ya da "
                    "devredilmiş; bunlara etiket basılmaz."
                )
            }
        )
    return kimlikler


@transaction.atomic
def create_batch(
    *,
    kind: str,
    template: LabelSheetTemplate,
    calibration: LabelCalibration | None = None,
    order: str = LabelOrder.CALL_NUMBER,
    start_cell: int = 1,
    copy_ids: Sequence[int],
    spine_template: LabelSheetTemplate | None = None,
    spine_calibration: LabelCalibration | None = None,
    include_qr: bool = False,
    reprint_of: LabelPrintBatch | None = None,
    keep_order: bool = False,
) -> LabelPrintBatch:
    """Basım partisi açar ("basım onayı bekliyor"). İşaretlere DOKUNMAZ (D10).

    Nüshalar seçilen sıraya dizilir (D20); `keep_order` yalnız yeniden basım
    içindir — verilen sıra olduğu gibi korunur (aynı partinin aynı dizilişi).
    Ayrı sırt tabakası (`spine_template`) yalnız "sırt ve barkod etiketi"
    basımında seçilir.
    """
    _require_choice(kind, LabelPrintKind.values, "kind", "etiket içeriği")
    _require_choice(order, LabelOrder.values, "order", "basım sırası")
    if kind != LabelPrintKind.BOTH and (spine_template or spine_calibration):
        raise ValidationError(
            {
                "spine_template": (
                    "Ayrı sırt tabakası yalnız “sırt ve barkod etiketi” basımında seçilir."
                )
            }
        )
    label_render.validate_print_setup(
        template=template,
        calibration=calibration,
        start_cell=start_cell,
        spine_template=spine_template,
        spine_calibration=spine_calibration,
    )
    kimlikler = _checked_copy_ids(copy_ids)
    if not keep_order:
        kimlikler = selectors_kuyruk.ordered_copy_ids(Copy.objects.filter(pk__in=kimlikler), order)
    parti: LabelPrintBatch = LabelPrintBatch.objects.create(
        kind=kind,
        template=template,
        calibration=calibration,
        spine_template=spine_template,
        spine_calibration=spine_calibration,
        include_qr=include_qr,
        order=order,
        start_cell=start_cell,
        copy_count=len(kimlikler),
        reprint_of=reprint_of,
    )
    LabelPrintBatchItem.objects.bulk_create(
        [
            LabelPrintBatchItem(batch=parti, copy_id=pk, position=sira)
            for sira, pk in enumerate(kimlikler, start=1)
        ]
    )
    return parti


def queue_copy_ids(
    *,
    kind: str,
    order: str,
    filters: selectors_kuyruk.QueueFilters | None = None,
    limit: int = MAX_LABELS_PER_JOB,
) -> list[int]:
    """Kuyruğun seçilen sıradaki İLK `limit` nüshası ("kuyruktan bas").

    Kuyruk sınırdan uzunsa kalanlar kuyrukta kalır; sıra korunduğu için bir
    sonraki parti kaldığı yerden devam eder.
    """
    _require_choice(kind, LabelPrintKind.values, "kind", "etiket içeriği")
    _require_choice(order, LabelOrder.values, "order", "basım sırası")
    if not 1 <= int(limit) <= MAX_LABELS_PER_JOB:
        raise ValidationError(
            {"limit": f"Bir basım partisine 1 ile {MAX_LABELS_PER_JOB_TEXT} arasında nüsha girer."}
        )
    kimlikler = selectors_kuyruk.ordered_copy_ids(
        selectors_kuyruk.label_queue(kind, filters), order
    )
    if not kimlikler:
        raise ValidationError({"copies": "Kuyrukta bu süzgece uyan nüsha yok."})
    return kimlikler[: int(limit)]


# ---------------------------------------------------------------------------
# Onay, geri alma, vazgeçme, yeniden basım
# ---------------------------------------------------------------------------
_STATUS_REJECTIONS: dict[str, str] = {
    LabelPrintBatchStatus.CONFIRMED: "Bu parti zaten basıldı olarak işaretli.",
    LabelPrintBatchStatus.REVERTED: (
        "Bu partinin basım işareti geri alındı; aynı nüshaları yeniden basmak için "
        "“Yeniden bas”ı kullanın."
    ),
    LabelPrintBatchStatus.DISCARDED: (
        "Bu partiden vazgeçildi; aynı nüshaları basmak için “Yeniden bas”ı kullanın."
    ),
    LabelPrintBatchStatus.PENDING: "Bu parti henüz basıldı olarak işaretlenmedi.",
}


def _require_status(batch: LabelPrintBatch, expected: str) -> None:
    if batch.status != expected:
        raise ValidationError({"batch": _STATUS_REJECTIONS[batch.status]})


def _locked(batch: LabelPrintBatch) -> LabelPrintBatch:
    """Partiyi işlem içinde yeniden okur (çift tıklamada ikinci istek eski hâli görmesin)."""
    parti: LabelPrintBatch = LabelPrintBatch.objects.select_for_update().get(pk=batch.pk)
    return parti


def _items(batch: LabelPrintBatch) -> list[LabelPrintBatchItem]:
    return list(batch.items.select_related("copy", "copy__work").order_by("position"))


def _active_later_stamps(
    batch: LabelPrintBatch, copy_ids: Sequence[int]
) -> tuple[set[tuple[int, Any]], set[tuple[int, Any]]]:
    """Bu partiden SONRA onaylanmış ve hâlâ ONAYLI partilerin bu nüshalardaki damgaları.

    Dönen: ({(nüsha, barkod damgası)}, {(nüsha, sırt damgası)}). Geri alınmış
    parti burada yoktur: doğrulandığı için işaretleri korunan nüshanın
    damgası geri alınmış partinindir ve önceki partinin geri alınmasını
    ENGELLEMEZ (aksi hâlde iki parti de bir daha geri alınamazdı). Önceki
    partiler de yoktur: onayda atlanan (silinmiş) nüsha önceki basımın
    damgasını taşır ve bu partinin geri alınmasını engellemez.
    """
    barkod: set[tuple[int, Any]] = set()
    sirt: set[tuple[int, Any]] = set()
    satirlar = (
        LabelPrintBatchItem.objects.filter(
            copy_id__in=list(copy_ids),
            batch__confirmed_at__gt=batch.confirmed_at,
            batch__reverted_at__isnull=True,
        )
        .exclude(batch_id=batch.pk)
        .values_list("copy_id", "batch__confirmed_at", "batch__kind")
    )
    for copy_id, damga, tur in satirlar:
        if tur in BARCODE_PRINT_KINDS:
            barkod.add((copy_id, damga))
        if tur in SPINE_PRINT_KINDS:
            sirt.add((copy_id, damga))
    return barkod, sirt


@transaction.atomic
def confirm_batch(batch: LabelPrintBatch) -> LabelPrintBatch:
    """ "Basıldı olarak işaretle" — işaretleri yazar, eski değerleri kalemde saklar.

    Barkod etiketi içeren partide doğrulama sıfırlanır: yeni etiket henüz
    okutulmamıştır. Sırt etiketinin doğrulaması yoktur (barkod taşımaz).

    Parti açıldıktan sonra silinmiş ya da elden çıkmış nüsha (`Copy.is_labelable`)
    İŞARETLENMEZ: PDF'te hücresi boş kalmıştır. Kalemde eski değerleri yine
    saklanır; geri alma o nüshaya dokunmaz.
    """
    parti = _locked(batch)
    _require_status(parti, LabelPrintBatchStatus.PENDING)
    simdi = timezone.now()
    kalemler = _items(parti)
    nushalar: list[Copy] = []
    for kalem in kalemler:
        nusha = kalem.copy
        kalem.previous_printed_at = nusha.label_printed_at
        kalem.previous_verified_at = nusha.label_verified_at
        kalem.previous_spine_printed_at = nusha.spine_label_printed_at
        if not nusha.is_labelable:
            continue
        if parti.prints_barcode:
            nusha.label_printed_at = simdi
            nusha.label_verified_at = None
        if parti.prints_spine:
            nusha.spine_label_printed_at = simdi
        nushalar.append(nusha)
    LabelPrintBatchItem.objects.bulk_update(
        kalemler, ["previous_printed_at", "previous_verified_at", "previous_spine_printed_at"]
    )
    Copy.all_objects.bulk_update(
        nushalar, ["label_printed_at", "label_verified_at", "spine_label_printed_at"]
    )
    parti.confirmed_at = simdi
    parti.save(update_fields=["confirmed_at", "updated_at"])
    return parti


def _kept_verified(batch: LabelPrintBatch, copy: Copy) -> bool:
    """Geri almada bu nüshanın işaretleri KORUNUR mu? (kullanıcı kararı 24.09.2026)

    Barkod etiketi içeren partide barkodu okutularak doğrulanmış nüsha: etiketler
    kitabın üzerindedir, barkod okunmuştur. İki işaret de (barkod ve sırt)
    olduğu gibi kalır; nüsha hiçbir kuyruğa dönmez. Yalnız sırt basan partide
    doğrulama yoktur (sırt etiketi barkod taşımaz), korunan nüsha da yoktur.
    """
    return batch.prints_barcode and copy.label_verified_at is not None


@transaction.atomic
def revert_batch(batch: LabelPrintBatch) -> dict[str, Any]:
    """Basım işaretini geri alır → `{batch, restored, requeued, kept_verified}`.

    Kurallar modül başlığında: sonraki basım önce geri alınır; onaydan sonra
    barkodu okutularak doğrulanmış nüshanın iki işareti de (barkod ve sırt)
    korunur (`_kept_verified`).

    Üç sayaç, partideki nüshalar üzerinden:

    - `restored`: işareti bu basımdan önceki hâline dönen nüsha sayısı.
    - `requeued`: bunlardan KUYRUĞA dönen, yani bu partinin bastığı etiketlerden
      en az biri artık basılmamış görünen nüsha sayısı (`requeued ≤ restored`).
      Yeniden basım partisinde işaret önceki basımın damgasına döner, nüsha
      kuyruğa girmez.
    - `kept_verified`: okutularak doğrulandığı için işaretleri korunan nüsha.
      Bu nüshalara DOKUNULMAZ: `restored`'a da `requeued`'a da girmezler
      (`restored + kept_verified ≤ nüsha sayısı`).

    İşareti bu partinin damgasını taşımayan nüsha iki türlüdür: damga hâlâ
    onaylı BAŞKA bir partininse geri alma reddedilir; değilse (doğrulandığı için
    işareti geri alınmış sonraki bir partide korunmuş ya da onayda silinmiş
    olduğu için hiç işaretlenmemiş) o nüshaya dokunulmaz. İşaretleri korunacak
    (doğrulanmış) nüsha reddi tetiklemez: ona dokunulmadığı için sonraki
    partinin işareti silinmez.
    """
    parti = _locked(batch)
    _require_status(parti, LabelPrintBatchStatus.CONFIRMED)
    damga = parti.confirmed_at
    kalemler = _items(parti)
    aktif_barkod, aktif_sirt = _active_later_stamps(parti, [k.copy_id for k in kalemler])
    sonradan = [
        kalem
        for kalem in kalemler
        if not _kept_verified(parti, kalem.copy)
        and (
            (
                parti.prints_barcode
                and kalem.copy.label_printed_at != damga
                and (kalem.copy_id, kalem.copy.label_printed_at) in aktif_barkod
            )
            or (
                parti.prints_spine
                and kalem.copy.spine_label_printed_at != damga
                and (kalem.copy_id, kalem.copy.spine_label_printed_at) in aktif_sirt
            )
        )
    ]
    if sonradan:
        raise ValidationError(
            {
                "batch": (
                    f"Bu partideki {len(sonradan)} nüshanın etiketi daha sonra başka bir "
                    "partiyle yeniden basıldı. Önce o partinin basım işaretini geri alın."
                )
            }
        )
    korunan = 0
    donen = 0
    kuyruga = 0
    nushalar: list[Copy] = []
    for kalem in kalemler:
        nusha = kalem.copy
        if _kept_verified(parti, nusha):
            # Okutulmuş etiket kitabın üzerindedir: barkod ve sırt işareti korunur
            # (damga bu partinin ya da doğrulandığı için korunan sonraki basımın).
            korunan += 1
            continue
        degisti = False
        if parti.prints_barcode and nusha.label_printed_at == damga:
            nusha.label_printed_at = kalem.previous_printed_at
            nusha.label_verified_at = kalem.previous_verified_at
            degisti = True
        if parti.prints_spine and nusha.spine_label_printed_at == damga:
            nusha.spine_label_printed_at = kalem.previous_spine_printed_at
            degisti = True
        if not degisti:
            continue
        donen += 1
        bos_barkod = parti.prints_barcode and nusha.label_printed_at is None
        bos_sirt = parti.prints_spine and nusha.spine_label_printed_at is None
        if nusha.is_labelable and (bos_barkod or bos_sirt):
            kuyruga += 1
        nushalar.append(nusha)
    Copy.all_objects.bulk_update(
        nushalar, ["label_printed_at", "label_verified_at", "spine_label_printed_at"]
    )
    parti.reverted_at = timezone.now()
    parti.save(update_fields=["reverted_at", "updated_at"])
    return {"batch": parti, "restored": donen, "requeued": kuyruga, "kept_verified": korunan}


@transaction.atomic
def discard_batch(batch: LabelPrintBatch) -> LabelPrintBatch:
    """Onaylanmamış partiden vazgeçer (parti iz olarak kalır; işaretlere dokunulmaz)."""
    parti = _locked(batch)
    _require_status(parti, LabelPrintBatchStatus.PENDING)
    parti.discarded_at = timezone.now()
    parti.save(update_fields=["discarded_at", "updated_at"])
    return parti


class _Unset(enum.Enum):
    """Alanın hiç gönderilmediğini söyleyen işaret; `None` "kalibrasyonsuz" demektir."""

    UNSET = "unset"


#: `reprint_batch(calibration=…)` verilmediğinde: eski partinin kalibrasyonu taşınır.
UNSET: Final = _Unset.UNSET


@transaction.atomic
def reprint_batch(
    batch: LabelPrintBatch,
    *,
    kind: str | None = None,
    template: LabelSheetTemplate | None = None,
    calibration: LabelCalibration | None | _Unset = UNSET,
    start_cell: int | None = None,
) -> LabelPrintBatch:
    """Aynı nüshaları AYNI SIRAYLA yeni bir partide basar (`reprint_of` izli).

    Verilmeyen ayar eski partiden alınır. Şablon değişirse eski kalibrasyon o
    şablona ait olmadığı için taşınmaz (kalibrasyon şablon + yazıcı çiftidir).
    `calibration=None` AÇIKÇA "kalibrasyonsuz (kaymasız) bas" demektir; eski
    kalibrasyon yalnız alan hiç verilmediğinde (`UNSET`) taşınır — ön yüzün
    "Yazıcı: yok" seçimi `null` gönderir ve bu seçim yutulmamalıdır.
    Ayrı sırt tabakası ve QR seçimi yalnız içerik "sırt ve barkod etiketi"
    kaldıkça taşınır. Parti açıldıktan sonra silinmiş ya da elden çıkmış
    nüsha (`Copy.is_labelable`) yeni partiye ALINMAZ, kalanların sırası
    korunur; hiçbiri kalmadıysa ret. (Aynı hücre düzeniyle yeniden basmak için
    ESKİ partinin PDF'i yeniden alınır: orada o nüshanın hücresi boş kalır.)
    """
    yeni_sablon = template if template is not None else batch.template
    yeni_kalibrasyon: LabelCalibration | None
    if not isinstance(calibration, _Unset):
        yeni_kalibrasyon = calibration
    elif yeni_sablon.pk == batch.template_id:
        yeni_kalibrasyon = batch.calibration
    else:
        yeni_kalibrasyon = None
    yeni_icerik = kind or batch.kind
    ayri_sirt = yeni_icerik == LabelPrintKind.BOTH
    kimlikler = [kalem.copy_id for kalem in _items(batch) if kalem.copy.is_labelable]
    if not kimlikler:
        raise ValidationError(
            {
                "batch": (
                    "Bu partinin nüshalarının hiçbirine artık etiket basılamaz: hepsi silinmiş "
                    "ya da elden çıkmış."
                )
            }
        )
    return create_batch(
        kind=yeni_icerik,
        template=yeni_sablon,
        calibration=yeni_kalibrasyon,
        spine_template=batch.spine_template if ayri_sirt else None,
        spine_calibration=batch.spine_calibration if ayri_sirt else None,
        include_qr=batch.include_qr,
        order=batch.order,
        start_cell=start_cell if start_cell is not None else batch.start_cell,
        copy_ids=kimlikler,
        reprint_of=batch,
        keep_order=True,
    )


# ---------------------------------------------------------------------------
# PDF — etiket motoruna tek kapıdan (işaretlere DOKUNMAZ)
# ---------------------------------------------------------------------------
def render_batch_pdf(batch: LabelPrintBatch) -> bytes:
    """Partinin PDF'i — her hâlinde yeniden üretilebilir, işaretlere dokunmaz (D10).

    Partideki bir nüsha sonradan silinmiş ya da elden çıkmışsa etiketi basılmaz
    ve HÜCRESİ BOŞ kalır: sonraki etiketler kaymaz, yarım tabakanın ve sırt ile
    barkod tabakasının hücre düzeni partinin ilk basımıyla aynıdır.
    """
    label_render.validate_print_setup(
        template=batch.template,
        calibration=batch.calibration,
        start_cell=batch.start_cell,
        spine_template=batch.spine_template,
        spine_calibration=batch.spine_calibration,
    )
    return label_render.render_job(
        label_render.LabelJob(
            kind=batch.kind,
            template=batch.template,
            calibration=batch.calibration,
            start_cell=batch.start_cell,
            copies=tuple(selectors_kuyruk.batch_copies(batch)),
            spine_template=batch.spine_template,
            spine_calibration=batch.spine_calibration,
            include_qr=batch.include_qr,
            hold_unprintable=True,
        )
    )


#: İçeriğin belge adı (sözlük §2 E1). `labels.render.DOCUMENT_NAMES` ile AYNIDIR
#: (eşitliği test sınar); oradan içe aktarılmaz, çünkü motor paketi WeasyPrint'i
#: yükler ve kuyruk uçları onu yüklemez (`label_render` modül başlığı).
DOCUMENT_NAMES: dict[str, str] = {
    LabelPrintKind.SPINE: "Sırt Etiketi",
    LabelPrintKind.BARCODE: "Barkod Etiketi",
    LabelPrintKind.BOTH: "Sırt ve Barkod Etiketi",
}


def batch_pdf_filename(batch: LabelPrintBatch) -> str:
    """İndirme adı: belge adı + yerel tarih ('Sırt-ve-Barkod-Etiketi_24.09.2026.pdf').

    Sözlük §3 ve ön yüzün `etiketDosyaAdi` ile aynı biçim. Parti numarası iç
    kimliktir, dosya adına girmez (sözlük §1 "Basım kaydı").
    """
    gun = timezone.localdate()
    return f"{DOCUMENT_NAMES[batch.kind].replace(' ', '-')}_{gun:%d.%m.%Y}.pdf"


# ---------------------------------------------------------------------------
# Doğrulama okutması (§7.2)
# ---------------------------------------------------------------------------
VERIFY_OK = "Etiket doğrulandı."
VERIFY_ALREADY = "Bu etiket daha önce doğrulandı."
VERIFY_EMPTY = "Kitabın kütüphane etiketini okutun."
VERIFY_MEMBER_CARD = "Bu bir üye kartı. Kitabın kütüphane etiketini okutun."
VERIFY_UNKNOWN = "Bu kod tanınmadı. Kitabın kütüphane etiketini okutun."
VERIFY_RESERVED = (
    "Bu etiket henüz bir kitaba bağlanmadı. Kitabı Hızlı Kayıt ekranında kaydederken bu "
    "etiketi okutun."
)
#: Hızlı Kayıt'ın iletisiyle (`barcode_reservations.BIND_CANCELLED`) aynı yönerge:
#: bağlanmamış numaranın kitabı kayıtlı değildir, basılacak bir nüsha etiketi yoktur.
VERIFY_CANCELLED = (
    "Bu etiketin numarası iptal edildi; kullanılamaz. Etiketi kitaptan sökün, başka bir boş "
    "etiket yapıştırın ve kitabı Hızlı Kayıt ekranında o etiketle kaydedin."
)
VERIFY_NO_COPY = "Bu barkodla kayıtlı nüsha yok. Etiketi kütüphane yöneticisine gösterin."
VERIFY_DELETED = "Bu barkodun nüshası silinmiş. Etiketi kitaptan sökün."
VERIFY_TERMINAL = "Bu nüsha kayıttan düşülmüş ya da devredilmiş; etiketi doğrulanmaz."
VERIFY_NOT_PRINTED = (
    "Bu nüshanın barkod etiketi basıldı olarak işaretlenmemiş. Önce basım partisini "
    "“Basıldı olarak işaretle” ile onaylayın, sonra yeniden okutun."
)
#: Görevli kipinde yönetici işine yönelten iletilerin yerine geçer: basım onayı ve Hızlı
#: Kayıt görevliye kapalıdır, iletinin yönergesi uygulanamazdı (sözlük §5: görevli
#: "kütüphane yöneticisine" yönlendirilir).
STAFF_REFER = "Kitabı ayırın ve kütüphane yöneticisine gösterin."
_STAFF_MESSAGES: Final[dict[str, str]] = {
    VERIFY_NOT_PRINTED: (
        f"Bu nüshanın barkod etiketi basıldı olarak işaretlenmemiş. {STAFF_REFER}"
    ),
    VERIFY_RESERVED: f"Bu etiket henüz bir kitaba bağlanmadı. {STAFF_REFER}",
    VERIFY_CANCELLED: f"Bu etiketin numarası iptal edildi; kullanılamaz. {STAFF_REFER}",
}


#: Görevli kipinde tarama sonucunun nüsha özeti (kullanıcı kararı 24.09.2026): masadaki
#: görevliye eser adı ve barkod yeterlidir. İç kimlik, yer numarası ve basım damgaları
#: yönetici ekranının bilgisidir; alan listesi anlık görüntüyle sınanır.
STAFF_COPY_FIELDS: Final[tuple[str, ...]] = ("barcode", "barcode_display", "work_title")


def _copy_brief(copy: Copy, *, staff: bool = False) -> dict[str, Any]:
    """Tarama sonucunda gösterilen nüsha özeti (kişisel veri YOK).

    `staff`: görevli kipi — yalnız `STAFF_COPY_FIELDS`.
    """
    ozet: dict[str, Any] = {
        "id": copy.pk,
        "barcode": copy.barcode,
        "barcode_display": barcode_module.format_barcode(copy.barcode),
        "work_title": copy.work.title,
        "call_number": copy.work.call_number,
        "label_printed_at": copy.label_printed_at,
        "label_verified_at": copy.label_verified_at,
    }
    if staff:
        return {alan: ozet[alan] for alan in STAFF_COPY_FIELDS}
    return ozet


def _scan_result(
    result: str,
    kind: ScanKind,
    message: str,
    copy: Copy | None = None,
    *,
    staff: bool = False,
) -> dict[str, Any]:
    return {
        "result": result,
        "kind": str(kind),
        "message": message,
        "copy": _copy_brief(copy, staff=staff) if copy is not None else None,
    }


@transaction.atomic
def verify_scan(value: object, *, staff: bool = False) -> dict[str, Any]:
    """Doğrulama okutması → `{result, kind, message, copy}`.

    `result`: "verified" (yazıldı) · "already_verified" · "rejected" (yazma yok).
    `staff`: istek görevli kipinden geldi — kural ve yazma aynıdır; nüsha özeti
    daralır (`STAFF_COPY_FIELDS`) ve yönetici işine yönelten ileti görevliyi
    yöneticiye yönlendirir (`_STAFF_MESSAGES`). Görevli kipinde açık tek etiket
    ucu budur (kullanıcı kararı 24.09.2026, `apps/okul/kip_izinleri.py`).
    """
    info = barcode_reservations.describe_scan(value)
    reddet = "rejected"

    def sonuc(result: str, message: str, copy: Copy | None = None) -> dict[str, Any]:
        if staff:
            message = _STAFF_MESSAGES.get(message, message)
        return _scan_result(result, info.kind, message, copy, staff=staff)

    if not info.digits:
        return sonuc(reddet, VERIFY_EMPTY)
    if info.kind == ScanKind.ISBN:
        return sonuc(reddet, barcode_module.ISBN_SCAN_MESSAGE)
    if info.kind == ScanKind.MEMBER_CARD:
        return sonuc(reddet, VERIFY_MEMBER_CARD)
    if info.kind == ScanKind.UNKNOWN:
        return sonuc(reddet, VERIFY_UNKNOWN)
    if info.kind == ScanKind.CANCELLED:
        return sonuc(reddet, VERIFY_CANCELLED)
    if info.kind == ScanKind.RESERVED:
        return sonuc(reddet, VERIFY_RESERVED)
    nusha = info.copy
    if nusha is None:
        return sonuc(reddet, VERIFY_NO_COPY)
    if nusha.deleted_at is not None:
        return sonuc(reddet, VERIFY_DELETED)
    if nusha.status in TERMINAL_COPY_STATUSES:
        return sonuc(reddet, VERIFY_TERMINAL, nusha)
    if nusha.label_printed_at is None:
        return sonuc(reddet, VERIFY_NOT_PRINTED, nusha)
    if nusha.label_verified_at is not None:
        return sonuc("already_verified", VERIFY_ALREADY, nusha)
    nusha.label_verified_at = timezone.now()
    nusha.save(update_fields=["label_verified_at", "updated_at"])
    return sonuc("verified", VERIFY_OK, nusha)
