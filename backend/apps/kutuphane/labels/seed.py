"""Hazır etiket şablonları — kod içi tohum (migration GEREKMEZ; §7.2, F4 sözleşmesi).

`ensure_default_templates()` şablon tablosu HİÇ kullanılmamışsa (silinmişler dahil
tek satır yoksa) aşağıdaki listeyi yazar; bir kez yazıldıktan sonra kullanıcının
düzenlemesine ve silmesine saygı gösterilir, şablonlar geri getirilmez. Etiket
şablonları ekranı ilk açıldığında ve motor varsayılan şablon aradığında çağrılır.

**Ölçülerin kaynağı.** Ölçü "yaklaşık" değilse iki yoldan doğrulanmıştır:
üreticinin şablon bilgisi ve A4'e simetrik yerleşimin aritmetiği. Doğrulanamayan
ölçü şablon adında "yaklaşık ölçü" diye işaretlidir; her durumda ilk basımdan
önce kalibrasyon sayfası basılır (yazıcı sapması şablona değil kalibrasyona
yazılır).

**Adlar kullanıcıya görünür** (şablon seçicisi, basım geçmişi): kâğıt boyunun
kısa adı YAZILMAZ, ölçü milimetreyle verilir (sözlük §1 "Etiket şablonu"; sayfa
her şablonda 210 × 297 mm'dir). Aşağıdaki başlıklardaki kısa ad yalnız bu
yorumdadır.

1. **38,1 × 21,2 mm, 65'li A4 (5 × 13) — varsayılan barkod tabakası** (§7.2:
   "A4'te 65 etiket, ör. Tanex TW-2065"; Avery L7651 ile aynı yerleşim).
   Kaynak: Label Planet LP65/38 şablon bilgisi (labelplanet.co.uk, "Label
   Printing Template Information: LP65/38", 24.09.2026'da okundu): üst ve alt
   kenar 10,7 mm, sol ve sağ kenar 4,75 mm, yatay adım 40,6 mm (aralık 2,5 mm),
   dikey adım 21,2 mm (aralık 0). Aritmetik: (210 − 5 × 38,1 − 4 × 2,5) / 2 =
   4,75 ve (297 − 13 × 21,2) / 2 = 10,7 — iki kaynak örtüşür.
2. **Sırt etiketi, 38,1 × 21,2 mm, 65'li A4 — varsayılan sırt tabakası.**
   Barkod tabakasıyla AYNI ızgaradır: sırt ve barkod etiketleri aynı sıra ve
   hücre düzeninde basılır (§7.2) ve motor iki şablonun satır × sütun
   düzeninin eşit olmasını ister. Sırt ölçümüne göre başka tabaka seçilirse
   (saha hazırlığı S4) kullanıcı yeni şablon tanımlar.
3. **48,5 × 25,4 mm, 44'lü A4 (4 × 11) — QR'a uygun** (§7.2). Etiket ölçüsü
   ve adet üretici bilgisidir (ör. Tanex TW-2044, "48,5 × 25,4 mm 44'lü";
   satıcı sayfalarında 24.09.2026'da okundu). **Avery Zweckform 3657 aynı etiket
   ölçüsündedir ama 40'lıdır (4 × 10, üstte ve altta geniş kenar boşluğu); bu
   şablona uymaz** — o tabaka için kullanıcı 10 satırlı yeni şablon tanımlar.
   Kenar boşlukları YAYIMLANMIŞ bir kaynaktan doğrulanamadı, simetrik
   yerleşimden hesaplandı: (210 − 4 × 48,5) / 2 = 8,0 ve (297 − 11 × 25,4) / 2
   = 8,8, aralık 0. Adında "yaklaşık ölçü" yazar — kalibrasyonla düzeltin.
4. **52,5 × 29,7 mm, 40'lı A4 (4 × 10) — QR'a uygun, kenarsız** (§7.2; ör.
   Avery Zweckform 3651). 4 × 52,5 = 210 ve 10 × 29,7 = 297: tabaka kenardan
   kenaradır, kenar boşluğu ve aralık 0'dır (aritmetik kesin). Yazıcının
   basamadığı kenar payı (yaygın lazer yazıcılarda 4,23 mm, bazılarında 5 mm)
   dış sütun ve satırlara düşer: etiket düzeni bar, QR modülü ve yazıyı sayfa
   kenarından en az 5 mm içeride tutar (`geometry.PRINT_SAFE_MARGIN_MM`,
   `layout.ink_insets`), kalibrasyon sayfası da cetvelini bu tabakada iç
   kenarlara koyar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.kutuphane.models import LabelKind, LabelSheetTemplate


@dataclass(frozen=True)
class TemplateSeed:
    name: str
    kind: str
    page_margin_top: Decimal
    page_margin_left: Decimal
    label_width: Decimal
    label_height: Decimal
    rows: int
    cols: int
    gutter_x: Decimal = Decimal("0")
    gutter_y: Decimal = Decimal("0")
    is_default: bool = False


DEFAULT_TEMPLATES: tuple[TemplateSeed, ...] = (
    TemplateSeed(
        name="Barkod etiketi — 38,1 × 21,2 mm, 65'li",
        kind=LabelKind.BARCODE,
        page_margin_top=Decimal("10.70"),
        page_margin_left=Decimal("4.75"),
        label_width=Decimal("38.10"),
        label_height=Decimal("21.20"),
        rows=13,
        cols=5,
        gutter_x=Decimal("2.50"),
        is_default=True,
    ),
    TemplateSeed(
        name="Barkod etiketi (QR'a uygun) — 48,5 × 25,4 mm, 44'lü (yaklaşık ölçü)",
        kind=LabelKind.BARCODE,
        page_margin_top=Decimal("8.80"),
        page_margin_left=Decimal("8.00"),
        label_width=Decimal("48.50"),
        label_height=Decimal("25.40"),
        rows=11,
        cols=4,
    ),
    TemplateSeed(
        name="Barkod etiketi (QR'a uygun) — 52,5 × 29,7 mm, 40'lı (kenarsız)",
        kind=LabelKind.BARCODE,
        page_margin_top=Decimal("0"),
        page_margin_left=Decimal("0"),
        label_width=Decimal("52.50"),
        label_height=Decimal("29.70"),
        rows=10,
        cols=4,
    ),
    TemplateSeed(
        name="Sırt etiketi — 38,1 × 21,2 mm, 65'li",
        kind=LabelKind.SPINE,
        page_margin_top=Decimal("10.70"),
        page_margin_left=Decimal("4.75"),
        label_width=Decimal("38.10"),
        label_height=Decimal("21.20"),
        rows=13,
        cols=5,
        gutter_x=Decimal("2.50"),
        is_default=True,
    ),
)


def ensure_default_templates() -> int:
    """Şablon tablosu hiç kullanılmamışsa hazır şablonları yazar; yazılan sayıyı döndürür.

    İşlem `transaction_mode=IMMEDIATE` altında yazma kilidiyle başlar: aynı
    anda gelen iki istekten ikincisi birincinin yazdıklarını görür ve bir şey
    yazmaz (çift tohum olmaz).
    """
    with transaction.atomic():
        if LabelSheetTemplate.all_objects.exists():
            return 0
        for tohum in DEFAULT_TEMPLATES:
            LabelSheetTemplate.objects.create(
                name=tohum.name,
                kind=tohum.kind,
                page_margin_top=tohum.page_margin_top,
                page_margin_left=tohum.page_margin_left,
                label_width=tohum.label_width,
                label_height=tohum.label_height,
                rows=tohum.rows,
                cols=tohum.cols,
                gutter_x=tohum.gutter_x,
                gutter_y=tohum.gutter_y,
                is_default=tohum.is_default,
            )
        return len(DEFAULT_TEMPLATES)


def default_template(kind: str) -> LabelSheetTemplate | None:
    """Türün varsayılan (canlı) şablonu; tohum gerekiyorsa önce yazılır."""
    ensure_default_templates()
    return LabelSheetTemplate.objects.filter(kind=kind, is_default=True).first()
