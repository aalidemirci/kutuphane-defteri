"""Üye kartı basımı: kart basımı kuyruğu, basım sırası ve onaylı basım işareti (E2, D8, D10).

**Kart basımı kuyruğu** = kartı henüz "basıldı" işaretlenmemiş AKTİF üyelikler
(`Membership.card_printed_at` boş). Yeni üyelik ve "Kartı yenile" üyeliği
kuyruğa koyar (`services.memberships`); "Basıldı olarak işaretle" çıkarır,
"Basım işaretini geri al" geri koyar.

**D10 kuralı** (etiketlerle aynı): PDF üretmek "basıldı" demek DEĞİLDİR. Kart
PDF'i hiçbir işarete dokunmaz; işaret yalnız onay diyaloğundan geçen
`confirm_printed` ile yazılır ve `revert_printed` ile geri alınır. Etiketteki
basım partisi (`LabelPrintBatch`) kart için YOKTUR: kartın tek işareti üyelik
satırındadır ve geri alma işareti boşaltır (kart kuyruğa döner). Model ve göç
değişmesin diye bilinçli seçildi; kart basımının partili geçmişi gerekirse ayrı
kalemdir.

**Basım sırası** (§7.2, KM-24): öğrenciler sınıf → şube (Türk alfabesi) → okul no
→ ad, sonra personel ada göre (`selectors_dolasim.memberships_sorted`). Sınıf
yalnız SIRALAMA içindir, karta basılmaz. Böylece şube tabakası sınıf listesi
sırasıyla çıkar ve kartlar sınıfa dağıtılırken aranmaz.

Yalnız AKTİF (ve kişisi aktif) üyeliğe kart basılır: sonlanmış üyeliğin ya da
ayrılmış kişinin kartı okutulunca masa "üyelik sonlanmış" der, kart basmak
yanlış bir güven verir. Günlüğe yalnız SAYI yazılır (ad yok — sözlük §5).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.kutuphane import selectors_dolasim
from apps.kutuphane.labels.card import (
    POSITION_NOTE,
    STAFF_POSITION_NOTE,
    CardItem,
    member_type_text,
)
from apps.kutuphane.models import Membership, MembershipStatus, MemberType
from apps.okul.services import app_password

logger = logging.getLogger("kutuphane_defteri.kutuphane")

EMPTY_SELECTION_MESSAGE = "Kart seçilmedi."
MISSING_MESSAGE = (
    "Seçilen üyeliklerden bazıları bulunamadı ya da artık aktif değil. Listeyi yenileyip "
    "yeniden seçin."
)


def card_queue(
    *,
    printed: bool = False,
    member_type: str = "",
    class_level: int | None = None,
    class_section: str = "",
    search: str = "",
) -> list[Membership]:
    """Kart basımı kuyruğu (`printed=False`) ya da kartı basılmış aktif üyelikler — basım sırasıyla.

    Kişisi ayrılmış ya da silinmiş aktif üyelik listeye girmez (ayrılış kancası
    üyeliği zaten sonlandırır; bu yalnız savunmadır).
    """
    satirlar = selectors_dolasim.memberships(
        status=MembershipStatus.ACTIVE,
        member_type=member_type,
        class_level=class_level,
        class_section=class_section,
        search=search,
    )
    return [
        m for m in satirlar if (m.card_printed_at is not None) == printed and m.person_is_active
    ]


def memberships_for_print(membership_ids: Sequence[int]) -> list[Membership]:
    """Basılacak üyelikler, BASIM SIRASIYLA. Aktif olmayan ya da bulunamayan kimlik → 400.

    Listeden sessizce düşen bir kart, kullanıcının saydığı kartla basılanı
    ayırırdı; bu yüzden eksik kimlik reddedilir.
    """
    kimlikler = list(dict.fromkeys(int(i) for i in membership_ids))
    if not kimlikler:
        raise ValidationError({"membership_ids": [EMPTY_SELECTION_MESSAGE]})
    bulunan = list(
        Membership.objects.select_related("student", "personnel").filter(
            pk__in=kimlikler, status=MembershipStatus.ACTIVE
        )
    )
    gecerli = [m for m in bulunan if m.person_is_active]
    if len(gecerli) != len(kimlikler):
        raise ValidationError({"membership_ids": [MISSING_MESSAGE]})
    return selectors_dolasim.memberships_sorted(gecerli)


def card_items(memberships: Sequence[Membership]) -> list[CardItem]:
    """Üyeliklerden kart kalemleri (sıra korunur). Sınıf karta GİRMEZ.

    Md. 20 konum kalıbı yalnız öğrenci ve öğretmen kartına basılır; diğer personelin
    kartında madde atfı yoktur (Md. 20/1 kartı öğretmen ve öğrenciye öngörür).
    """
    return [
        CardItem(
            card_no=str(m.card_no),
            full_name=m.full_name,
            member_type=member_type_text(m.get_member_type_display()),
            note=STAFF_POSITION_NOTE if m.member_type == MemberType.STAFF else POSITION_NOTE,
        )
        for m in memberships
    ]


@transaction.atomic
def confirm_printed(membership_ids: Sequence[int]) -> int:
    """Seçilen kartları "basıldı" işaretler; işaretlenen SAYISINI döndürür.

    Zaten işaretli kart yeniden işaretlenmez (ilk basım tarihi korunur). Seçimde
    aktif olmayan ya da bulunamayan üyelik varsa hiçbiri işaretlenmez.
    """
    app_password.require_password_set()
    uyelikler = memberships_for_print(membership_ids)
    simdi = timezone.now()
    kimlikler = [m.pk for m in uyelikler if m.card_printed_at is None]
    sayi = Membership.objects.filter(pk__in=kimlikler, card_printed_at__isnull=True).update(
        card_printed_at=simdi, updated_at=simdi
    )
    logger.info("%d üye kartı basıldı olarak işaretlendi.", sayi)
    return int(sayi)


@transaction.atomic
def revert_printed(membership_ids: Sequence[int]) -> int:
    """Seçilen kartların basım işaretini geri alır (kart kuyruğa döner); sayıyı döndürür."""
    app_password.require_password_set()
    uyelikler = memberships_for_print(membership_ids)
    simdi = timezone.now()
    sayi = Membership.objects.filter(
        pk__in=[m.pk for m in uyelikler], card_printed_at__isnull=False
    ).update(card_printed_at=None, updated_at=simdi)
    logger.info("%d üye kartının basım işareti geri alındı.", sayi)
    return int(sayi)
