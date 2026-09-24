"""Etiket içeriği: basılacak kalemler ve yer numarasının sırt satırlarına bölünmesi.

Motorun girdisi ya **nüsha listesi** (sırt ve barkod etiketi) ya da **numara
listesi**dir (önceden basılmış boş barkod etiketi — yöntem B, §8.1). İkisi de
`LabelItem` listesine çevrilir; sıra olduğu gibi korunur (basım sırası çağıranın
kararıdır — D20: yer numarası, içe aktarma satırı ya da barkod).

**Yer numarasının satırları** (§7.2, sözlük "yer numarası": sınıflama / yazar
kodu / cilt-nüsha). Kural yer numarasının kendisinden türetilir, ayrı alan
gerekmez: boşlukla ayrılmış parçalar alt alta basılır.

| Yer numarası | Sırt satırları |
|---|---|
| `813.54 STE` | `813.54` / `STE` |
| `894.3533 ALİ 2. cilt` | `894.3533` / `ALİ` / `2. cilt` |
| `REF 030 ANA` | `REF` / `030` / `ANA` |
| `813.54` | `813.54` |

Üçten çok parça varsa üçüncü satır kalanların hepsini taşır. Bölme yalnız
boşluktandır: Dewey kodundaki `/` (bölümleme işareti, "813/.54") ve `.` satır
bölmez. Yer numarası boşsa programın ürettiği karşılık kullanılır
(`keys.build_call_number`: sınıflama kodu + yazar soyadının ilk üç harfi);
o da boşsa sırtta "—" basılır, kullanıcı eksikliği etikette görür.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import keys
from apps.kutuphane.labels.geometry import MAX_LABELS_PER_DOCUMENT, LabelError
from apps.kutuphane.labels.metrics import clean_text

if TYPE_CHECKING:
    from apps.kutuphane.models import Copy

#: Sırt etiketinde yer numarasının en çok satır sayısı (§7.2).
MAX_SPINE_LINES = 3
#: Yer numarası hiç yoksa sırta basılan işaret.
MISSING_CALL_NUMBER = "—"


class LabelContent(StrEnum):
    """Bir tabakaya basılan etiketin içeriği (motor düzeyi)."""

    SPINE = "SPINE"  # sırt etiketi: yer numarası + kısa okul adı
    BARCODE = "BARCODE"  # barkod etiketi: barkod, numara, yer numarası, eser adı, okul
    BLANK_BARCODE = "BLANK_BARCODE"  # önceden basılmış boş barkod etiketi (yöntem B)


class LabelSelection(StrEnum):
    """Kullanıcının seçtiği basım (uç ve basım partisi düzeyi).

    `BOTH` motorda iki parçadır (önce sırt tabakaları, sonra barkod tabakaları);
    ikisi aynı sıra ve hücre planını paylaşır (§7.2).
    """

    SPINE = "SPINE"
    BARCODE = "BARCODE"
    BOTH = "BOTH"
    BLANK_BARCODE = "BLANK_BARCODE"


#: Başka kolların kullandığı eş adlar (basım kuyruğu boş barkoda "BLANK" der).
_SELECTION_ALIASES = {"BLANK": LabelSelection.BLANK_BARCODE}


def parse_selection(value: object) -> LabelSelection:
    """Seçim değerini çözer; tanınmayan değerde `LabelError`."""
    metin = str(value or "").strip()
    if metin in _SELECTION_ALIASES:
        return _SELECTION_ALIASES[metin]
    try:
        return LabelSelection(metin)
    except ValueError as exc:
        raise LabelError("Geçerli bir etiket türü seçin.", field="content") from exc


#: Seçimin parçaları (sayfa sırası budur).
SELECTION_CONTENTS: dict[LabelSelection, tuple[LabelContent, ...]] = {
    LabelSelection.SPINE: (LabelContent.SPINE,),
    LabelSelection.BARCODE: (LabelContent.BARCODE,),
    LabelSelection.BOTH: (LabelContent.SPINE, LabelContent.BARCODE),
    LabelSelection.BLANK_BARCODE: (LabelContent.BLANK_BARCODE,),
}


@dataclass(frozen=True)
class LabelItem:
    """Basılacak tek etiketin verisi (kişisel veri yok — kitap künyesi ve numara).

    `held`: hücre BOŞ bırakılır, yeri tutulur. Basım partisinin PDF'i yeniden
    alınırken partideki bir nüsha sonradan silinmiş ya da elden çıkmışsa o
    nüshanın etiketi basılmaz, ama sonraki etiketler kaymaz: sırt ve barkod
    tabakası ve yarım kalan tabaka partinin ilk hücre düzenini korur.
    """

    barcode: str
    title: str = ""
    call_number: str = ""
    held: bool = False

    @property
    def printed_number(self) -> str:
        """Okunur numara: '2026000123' → '2026-000123'."""
        return barcode_module.format_barcode(self.barcode)


def validate_copy_barcode(value: str, *, field: str = "barcodes") -> str:
    """Nüsha barkodu mu (10 hane, yıl önekli)? Code128-C çift hane ister, 10 uyar."""
    rakamlar = str(value or "")
    if (
        len(rakamlar) != barcode_module.BARCODE_LENGTH
        or not rakamlar.isascii()
        or not rakamlar.isdigit()
        or not barcode_module.has_scan_year_prefix(rakamlar)
    ):
        raise LabelError(
            "Etikete yalnız 10 haneli nüsha barkodu basılır (ör. 2026-000123).", field=field
        )
    return rakamlar


def validate_items(items: Iterable[LabelItem], *, field: str = "items") -> list[LabelItem]:
    """Boş, çok uzun ve yinelenen barkodlu listeleri reddeder.

    Aynı barkod bir belgede iki kez basılmaz: iki etiket iki kitaba yapıştırılır
    ve bir numara iki kitapta görünür — numaranın tekilliği etiketle bozulur.
    """
    liste = list(items)
    if not liste:
        raise LabelError("Basılacak etiket yok.", field=field)
    if all(kalem.held for kalem in liste):
        raise LabelError(
            "Bu partinin nüshalarının hiçbirine artık etiket basılamaz: hepsi silinmiş ya "
            "da elden çıkmış.",
            field=field,
        )
    if len(liste) > MAX_LABELS_PER_DOCUMENT:
        raise LabelError(
            f"Tek seferde en çok {MAX_LABELS_PER_DOCUMENT} etiket basılabilir; "
            "listeyi parçalara bölün.",
            field=field,
        )
    gorulen: set[str] = set()
    for kalem in liste:
        validate_copy_barcode(kalem.barcode, field=field)
        if kalem.barcode in gorulen:
            raise LabelError(
                f"{barcode_module.format_barcode(kalem.barcode)} numarası listede iki kez var; "
                "bir numara yalnız bir etikete basılır.",
                field=field,
            )
        gorulen.add(kalem.barcode)
    return liste


def call_number_of(work_call_number: str, classification_code: str, authors: str) -> str:
    """Eserin yer numarası; boşsa programın ürettiği karşılık (`keys.build_call_number`)."""
    yer = clean_text(work_call_number)
    return yer or clean_text(keys.build_call_number(classification_code, authors))


def items_from_copies(copies: Iterable[Copy], *, hold_unprintable: bool = False) -> list[LabelItem]:
    """Nüshalardan etiket kalemleri — verilen sıra korunur.

    `select_related("work")` ile gelmesi önerilir. Silinmiş nüsha ya da eser
    (yumuşak silme ileri FK'da süzülmez — CLAUDE.md §3) ve elden çıkmış nüsha
    (kayıttan düşülmüş, devredilmiş) reddedilir.

    `hold_unprintable=True` (basım partisinin PDF'i): böyle bir nüsha reddedilmez,
    hücresi BOŞ bırakılır (`LabelItem.held`) — parti bir iz kaydıdır ve yeniden
    basımda hücre düzeni kaymaz.
    """
    from apps.kutuphane.models import TERMINAL_COPY_STATUSES

    kalemler: list[LabelItem] = []
    for nusha in copies:
        eser = nusha.work
        if hold_unprintable and not nusha.is_labelable:
            kalemler.append(LabelItem(barcode=nusha.barcode, held=True))
            continue
        if nusha.deleted_at is not None or eser.deleted_at is not None:
            raise LabelError(
                f"{barcode_module.format_barcode(nusha.barcode)} numaralı nüsha silinmiş; "
                "etiketi basılmaz.",
                field="copy_ids",
            )
        if nusha.status in TERMINAL_COPY_STATUSES:
            raise LabelError(
                f"{barcode_module.format_barcode(nusha.barcode)} numaralı nüsha elde değil "
                f"({nusha.get_status_display()}); etiketi basılmaz.",
                field="copy_ids",
            )
        kalemler.append(
            LabelItem(
                barcode=nusha.barcode,
                title=clean_text(eser.title),
                call_number=call_number_of(
                    eser.call_number, eser.classification_code, eser.authors
                ),
            )
        )
    return kalemler


def items_from_barcodes(barcodes: Iterable[str]) -> list[LabelItem]:
    """Numara listesinden boş barkod etiketi kalemleri (künye yok) — sıra korunur."""
    return [
        LabelItem(barcode=validate_copy_barcode(str(numara), field="barcodes"))
        for numara in barcodes
    ]


def split_call_number(value: object, *, max_lines: int = MAX_SPINE_LINES) -> list[str]:
    """Yer numarasını sırt satırlarına böler (modül belgesindeki tablo)."""
    parcalar = clean_text(value).split()
    if not parcalar:
        return []
    if len(parcalar) <= max_lines:
        return parcalar
    return [*parcalar[: max_lines - 1], " ".join(parcalar[max_lines - 1 :])]
