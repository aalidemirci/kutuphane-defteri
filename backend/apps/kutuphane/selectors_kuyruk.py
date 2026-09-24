"""Etiket kuyruğu, basım partileri ve boş barkod aralıkları — salt okuma sorguları (F4-Q).

`selectors.py`'nin kuralları burada da geçerlidir (T7, D9): Türkçe sıralama
anahtarla ya da Python'da yapılır, her sıra kararlı bir son anahtarla biter.

**Kuyruk üç tanedir, işaret iki tanedir** (`models.Copy`):

| Kuyruk (basım içeriği) | Nüsha kuyrukta ise |
|---|---|
| Barkod etiketi | `label_printed_at` boş |
| Sırt etiketi | `spine_label_printed_at` boş |
| Sırt ve barkod etiketi | İKİSİ de boş |

"İkisi birden" kuyruğu bilinçli olarak KESİŞİMDİR: barkod etiketi zaten basılmış
bir nüsha (ör. yöntem B'de önceden basılmış etiketi bağlanan kitap) bu kuyrukta
görünseydi, "ikisi birden" basımı kitaba İKİNCİ bir barkod etiketi basardı. O
nüsha yalnız sırt kuyruğunda görünür.

Kuyruğa kayıttan düşülmüş/devredilmiş (`TERMINAL_COPY_STATUSES`) ve silinmiş
nüsha girmez.

**Basım sırası seçilebilir** (D20): yer numarası (varsayılan), içe aktarma
sırası, barkod. Yer numarası sırası DB'de kurulamaz (Dewey sayısı + Türkçe
yazar kodu + cilt/nüsha sayısı) ve Python'da yapılır; kuyruk bunun için önce
yalnız KİMLİKLERİ sıralar (`ordered_copy_ids`), nesneleri sayfa sayfa getirir
(`copies_by_ids`) — 10.000 nüshalık bir kuyrukta her sayfa isteği bütün
nesneleri kurmaz.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import Count, Q, QuerySet

from apps.kutuphane.models import (
    TERMINAL_COPY_STATUSES,
    BarcodeReservation,
    Copy,
    LabelOrder,
    LabelPrintBatch,
    LabelPrintBatchItem,
    LabelPrintKind,
    ReservedBarcode,
)
from apps.okul.normalize import tr_sort_key

#: Yer numarasının sınıflama kısmı: Dewey sayısı ('813', '813.54', Türkçe
#: yazımda virgülle '813,54'). Ondalık kısım SAYI DEĞİL rakam dizisi olarak
#: karşılaştırılır — Dewey'de 813.54 < 813.6'dır (doğal sayı sıralaması ters
#: sonuç verirdi: 54 > 6).
_DEWEY = re.compile(r"(\d+)(?:[.,](\d+))?")
#: Doğal sıra koşuları: ondalıklı sayı ('813.54', '920,05') TEK koşudur ve Dewey
#: kuralıyla karşılaştırılır; tamsayı ve harf koşuları ayrıdır. Harfle biten
#: nokta ('c.2') ondalık sayılmaz: önünde rakam yoktur.
_RUN = re.compile(r"\d+[.,]\d+|\d+|\D+")


# ---------------------------------------------------------------------------
# Süzgeçler
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QueueFilters:
    """Kuyruk süzgeçleri: bölüm, edinim partisi, boş barkod aralığı, kayıt tarihi.

    Tarihler nüshanın KAYIT (açılış) gününe bakar ve yerel gündür
    (`Europe/Istanbul` — Django `__date` araması etkin saat dilimiyle çevirir).
    `reservation`, yöntem B'de önceden basılmış etiketi bağlanan nüshaları
    seçer: sırt etiketleri genellikle aralık aralık basılır.
    """

    section_id: int | None = None
    acquisition_id: int | None = None
    reservation_id: int | None = None
    created_from: date | None = None
    created_to: date | None = None

    def apply(self, qs: QuerySet[Copy]) -> QuerySet[Copy]:
        if self.section_id is not None:
            qs = qs.filter(section_id=self.section_id)
        if self.acquisition_id is not None:
            qs = qs.filter(acquisition_id=self.acquisition_id)
        if self.reservation_id is not None:
            qs = qs.filter(reserved_barcode__reservation_id=self.reservation_id)
        if self.created_from is not None:
            qs = qs.filter(created_at__date__gte=self.created_from)
        if self.created_to is not None:
            qs = qs.filter(created_at__date__lte=self.created_to)
        return qs


def queue_condition(kind: str) -> Q:
    """Bir basım içeriğinin kuyruk koşulu (bkz. modül başlığındaki tablo)."""
    barkod = Q(label_printed_at__isnull=True)
    sirt = Q(spine_label_printed_at__isnull=True)
    if kind == LabelPrintKind.BARCODE:
        return barkod
    if kind == LabelPrintKind.SPINE:
        return sirt
    return barkod & sirt


def labelable_copies() -> QuerySet[Copy]:
    """Etiket basılabilecek nüshalar: canlı ve kayıttan düşülmemiş."""
    return Copy.objects.exclude(status__in=TERMINAL_COPY_STATUSES)


def label_queue(kind: str, filters: QueueFilters | None = None) -> QuerySet[Copy]:
    """Etiket kuyruğu (sırasız küme — sıra `ordered_copy_ids` ile verilir)."""
    qs = labelable_copies().filter(queue_condition(kind))
    return (filters or QueueFilters()).apply(qs)


def unverified_labels(filters: QueueFilters | None = None) -> QuerySet[Copy]:
    """Barkod etiketi basılmış ama okutularak DOĞRULANMAMIŞ nüshalar (§7.2)."""
    qs = labelable_copies().filter(label_printed_at__isnull=False, label_verified_at__isnull=True)
    return (filters or QueueFilters()).apply(qs)


# ---------------------------------------------------------------------------
# Sıralama (D20)
# ---------------------------------------------------------------------------
def _number_key(run: str) -> tuple[int, int, str]:
    """Sayı koşusunun anahtarı: (0, tamsayı kısmı, ondalık kısmın rakam DİZİSİ).

    Dewey kuralı: ondalık kısım sayı değil rakam dizisidir — 813 < 813.54 < 813.6.
    """
    eslesme = _DEWEY.fullmatch(run)
    assert eslesme is not None
    return (0, int(eslesme.group(1)), eslesme.group(2) or "")


def _natural(token: str) -> tuple[tuple[Any, ...], ...]:
    """Parçanın doğal sıra anahtarı: sayı koşuları SAYI, harfler Türk alfabesi.

    Cilt/nüsha eki ('c.2', 'c.10') sayı olarak sıralanır; yazar kodu ('STE',
    'ÇAK') Türk alfabesiyle ('C' < 'Ç' < 'D'). Önekli yer numarasının Dewey
    sayısı ('Ç 813.54', 'R 920.05') da Dewey kuralıyla sıralanır: '813.54' <
    '813.6' (54 > 6 diye tersine dönmez).
    """
    return tuple(
        _number_key(kosu) if kosu[0].isdigit() else (1, tr_sort_key(kosu))
        for kosu in _RUN.findall(token)
    )


def call_number_sort_key(value: object) -> tuple[Any, ...]:
    """Yer numarasının raf sırası anahtarı (sınıflama → yazar kodu → cilt/nüsha).

    - İlk parça Dewey sayısıysa sayı gibi sıralanır: '92' < '100', ondalık
      kısım rakam dizisidir ('813.54' < '813.6').
    - Sayıyla başlamayan yer numaraları ('R 920', 'Ç 813') sayılılardan sonra,
      kendi aralarında Türk alfabesiyle sıralanır.
    - Kalan parçalar (önekten sonraki Dewey sayısı, yazar kodu, cilt/nüsha)
      doğal sırayla karşılaştırılır; ondalıklı sayı yine Dewey kuralıyla
      ('Ç 813.54' < 'Ç 813.6').
    - Yer numarası boş nüshalar EN SONA düşer: rafta yeri belli olmayan kitabın
      etiketi rafın sırasını bozmasın.
    """
    parcalar = str(value or "").split()
    if not parcalar:
        return (1,)
    ilk = parcalar[0]
    eslesme = _DEWEY.fullmatch(ilk)
    bas: tuple[Any, ...]
    if eslesme is not None:
        bas = (0, int(eslesme.group(1)), eslesme.group(2) or "")
    else:
        bas = (1, _natural(ilk))
    return (0, bas, tuple(_natural(parca) for parca in parcalar[1:]))


def ordered_copy_ids(qs: QuerySet[Copy], order: str) -> list[int]:
    """Kümedeki nüshaların kimlikleri, seçilen basım sırasında (D20).

    - Yer numarası: raf sırası, eşitlikte eserin Türkçe ad anahtarı, sonra kayıt
      no (aynı eserin nüshaları ardışık basılır).
    - İçe aktarma sırası: nüshaların kayıt sırası (`pk` — SQLite `AUTOINCREMENT`,
      geri gitmez). Aktarım satırları sırayla işlendiği için bir aktarımın
      içinde bu sıra dosyanın satır sırasıdır.
    - Barkod: kayıt no sırası (barkodun sayı hâli).
    """
    if order == LabelOrder.IMPORT_ROW:
        return list(qs.order_by("pk").values_list("pk", flat=True))
    if order == LabelOrder.BARCODE:
        return list(qs.order_by("accession_no", "pk").values_list("pk", flat=True))
    satirlar = qs.values_list("pk", "work__call_number", "work__sort_key", "accession_no")
    sirali = sorted(
        satirlar,
        key=lambda satir: (call_number_sort_key(satir[1]), satir[2], satir[3], satir[0]),
    )
    return [satir[0] for satir in sirali]


def copies_by_ids(ids: Sequence[int]) -> list[Copy]:
    """Verilen kimliklerdeki nüshalar, VERİLEN SIRADA (bulunamayanlar düşer)."""
    nesneler = Copy.objects.select_related("work", "section").in_bulk(list(ids))
    return [nesneler[pk] for pk in ids if pk in nesneler]


def pending_batch_ids(copy_ids: Iterable[int]) -> dict[int, int]:
    """Nüsha → onay bekleyen en yeni partinin kimliği (kuyrukta "PDF'i alındı" uyarısı).

    Onaylanmamış bir partideki nüsha kuyrukta KALIR (D10: PDF üretmek basmak
    değildir); ama kullanıcı aynı etiketi ikinci kez basmadan önce bunu görmeli.
    """
    sonuc: dict[int, int] = {}
    kalemler = (
        LabelPrintBatchItem.objects.filter(
            copy_id__in=list(copy_ids),
            batch__confirmed_at__isnull=True,
            batch__discarded_at__isnull=True,
            batch__deleted_at__isnull=True,
        )
        .order_by("batch_id")
        .values_list("copy_id", "batch_id")
    )
    for copy_id, batch_id in kalemler:
        sonuc[copy_id] = batch_id
    return sonuc


# ---------------------------------------------------------------------------
# Basım partileri
# ---------------------------------------------------------------------------
#: Partinin durum süzgeci → koşul (durum alanı yoktur, damgalardan türetilir).
BATCH_STATUS_CONDITIONS: dict[str, Q] = {
    "PENDING": Q(confirmed_at__isnull=True, discarded_at__isnull=True),
    "CONFIRMED": Q(confirmed_at__isnull=False, reverted_at__isnull=True),
    "REVERTED": Q(reverted_at__isnull=False),
    "DISCARDED": Q(discarded_at__isnull=False),
}


def label_batches(*, status: str = "") -> QuerySet[LabelPrintBatch]:
    """Basım geçmişi (en yeniden eskiye)."""
    qs = LabelPrintBatch.objects.select_related(
        "template", "calibration", "spine_template", "spine_calibration"
    )
    if status:
        qs = qs.filter(BATCH_STATUS_CONDITIONS[status])
    return qs


def batch_copies(batch: LabelPrintBatch) -> list[Copy]:
    """Partinin nüshaları BASIM SIRASINDA (`position`) — silinmiş nüsha dahil.

    Parti bir iz kaydıdır: sonradan silinen ya da elden çıkan nüsha partinin
    içeriğinden düşmez. Partinin PDF'i yeniden alınırken o nüshanın etiketi
    basılmaz, HÜCRESİ BOŞ kalır (`LabelJob.hold_unprintable`): listeden
    çıkarmak sonraki etiketleri bir hücre kaydırırdı.
    """
    kalemler = batch.items.select_related("copy", "copy__work", "copy__section").order_by(
        "position"
    )
    return [kalem.copy for kalem in kalemler]


# ---------------------------------------------------------------------------
# Boş barkod aralıkları
# ---------------------------------------------------------------------------
def barcode_reservations() -> QuerySet[BarcodeReservation]:
    """Aralıklar (en yeniden eskiye) + numara başına durum sayaçları (aralık raporu)."""
    qs: QuerySet[BarcodeReservation] = BarcodeReservation.objects.annotate(
        bound_count=Count("numbers", filter=Q(numbers__copy__isnull=False), distinct=True),
        cancelled_count=Count(
            "numbers", filter=Q(numbers__cancelled_at__isnull=False), distinct=True
        ),
        open_count=Count(
            "numbers",
            filter=Q(numbers__copy__isnull=True, numbers__cancelled_at__isnull=True),
            distinct=True,
        ),
    )
    return qs


def reservation_numbers(reservation: BarcodeReservation) -> QuerySet[ReservedBarcode]:
    """Aralığın numaraları (kayıt no sırasında) ve bağlı oldukları nüshanın eseri."""
    return reservation.numbers.select_related("copy", "copy__work").order_by("accession_no")


def reservation_totals() -> dict[str, int]:
    """Bütün aralıkların toplamı: ayrılmış / bağlanmış / iptal / açık."""
    toplam = ReservedBarcode.objects.aggregate(
        reserved=Count("pk"),
        bound=Count("pk", filter=Q(copy__isnull=False)),
        cancelled=Count("pk", filter=Q(cancelled_at__isnull=False)),
    )
    ayrilan = int(toplam["reserved"] or 0)
    baglanan = int(toplam["bound"] or 0)
    iptal = int(toplam["cancelled"] or 0)
    return {
        "reserved": ayrilan,
        "bound": baglanan,
        "cancelled": iptal,
        "open": ayrilan - baglanan - iptal,
    }


def label_summary() -> dict[str, Any]:
    """Etiketler sayfasının ve pano kartının sayaçları (kişisiz)."""
    return {
        "queue": {kind: label_queue(kind).count() for kind in LabelPrintKind.values},
        "unverified": unverified_labels().count(),
        "pending_batches": label_batches(status="PENDING").count(),
        "reservations": reservation_totals(),
    }
