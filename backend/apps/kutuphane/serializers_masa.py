"""Dolaşım masası serializer'ları ve masa yanıtlarının ALAN LİSTELERİ (tasarım §4.4, §7.3).

Görevli kipinde yanıtlar DARALIR. Buradaki `STAFF_*` alan listeleri görevlinin
gördüğü yüzeyin tam tarifidir ve anlık görüntüyle sabittir (§5.10-8 —
`tests/test_masa_gorevli_yuzeyi.py`):

* kartla üye çözme: YALNIZ **ad** ve **kalan ödünç hakkı** (sınıf, üye türü,
  açık ödünçler, gecikme YOK — sözlük §5);
* ödünç ver: ileti, nüsha özeti, iade tarihi, uyarılar ve üyenin kalan hakkı;
* iade: ileti ve nüsha özeti — **ödünç alanın kimliği ve gecikme günü YOK**;
* nüsha durum sorgusu: nüshanın durumu ve ödünç verilebilirliği — ödünç kimde,
  ne zaman dönecek YOK;
* katalog okuma (`library/works/`, `library/copies/` GET): Ağ Kataloğunun
  gösterdiği künye ve nüsha alanları; edinim, fiyat, bağışçı, TKYS kodu, eski
  kayıt no, etiket damgaları YOK.

Nüsha özeti etiket doğrulama okutmasındakiyle aynıdır
(`label_queue.STAFF_COPY_FIELDS`): barkod ve kaynak adı.

Yönetici kipindeki (`ADMIN_*`) yanıtlar kişi verisi taşır (ad, sınıf, açık
ödünçler, iade alınan üyenin adı) ve yalnız yönetici kipinde çıkar.
"""

from __future__ import annotations

from typing import Any, Final

from rest_framework import serializers

from apps.kutuphane.models import Copy, Work
from apps.kutuphane.serializers import WorkSerializer
from apps.kutuphane.services import label_queue

# ---------------------------------------------------------------------------
# Alan listeleri (görevli ⊂ yönetici)
# ---------------------------------------------------------------------------
#: Görevli kipinde kartla üye çözme: YALNIZ ad + kalan hak (§4.4).
STAFF_MEMBER_FIELDS: Final[tuple[str, ...]] = ("full_name", "remaining_quota")
ADMIN_MEMBER_FIELDS: Final[tuple[str, ...]] = (
    "membership_id",
    "full_name",
    "member_type",
    "member_type_display",
    "class_label",
    "status",
    "status_display",
    "person_is_active",
    "loan_limit",
    "open_loan_count",
    "overdue_loan_count",
    "remaining_quota",
    "open_loans",
)
#: Yönetici kipindeki üye bağlamının açık ödünç satırı (profil yasağı: konu/sınıflama YOK).
OPEN_LOAN_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "barcode",
    "barcode_display",
    "work_title",
    "loaned_at",
    "due_date",
    "overdue_days",
    "cardless",
    "has_override",
)

#: Masa nüsha özeti — görevlide etiket doğrulamasıyla AYNI (barkod + kaynak adı).
STAFF_COPY_FIELDS: Final[tuple[str, ...]] = tuple(label_queue.STAFF_COPY_FIELDS)
ADMIN_COPY_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "barcode",
    "barcode_display",
    "work_title",
    "call_number",
    "status",
    "status_display",
)
STAFF_COPY_STATUS_FIELDS: Final[tuple[str, ...]] = (
    *STAFF_COPY_FIELDS,
    "status",
    "status_display",
    "is_loanable",
    "not_loanable_reason",
)
ADMIN_COPY_STATUS_FIELDS: Final[tuple[str, ...]] = (
    *ADMIN_COPY_FIELDS,
    "is_loanable",
    "not_loanable_reason",
)

#: Kartla üye çözme zarfı (iki kipte aynı; `member` kipine göre daralır).
CARD_FIELDS: Final[tuple[str, ...]] = ("state", "message", "member")
STAFF_CHECKOUT_FIELDS: Final[tuple[str, ...]] = (
    "message",
    "copy",
    "due_date",
    "warnings",
    "member",
)
ADMIN_CHECKOUT_FIELDS: Final[tuple[str, ...]] = (
    "message",
    "loan_id",
    "copy",
    "due_date",
    "due_date_shifted",
    "warnings",
    "cardless",
    "cardless_reason_display",
    "has_override",
    "override_reason_display",
    "member",
)
#: İade: görevli kipinde ödünç alanın kimliği ve gecikme günü YOK (§4.4).
STAFF_RETURN_FIELDS: Final[tuple[str, ...]] = ("result", "kind", "message", "copy")
ADMIN_RETURN_FIELDS: Final[tuple[str, ...]] = ("result", "kind", "message", "copy", "loan")
RETURN_LOAN_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "member_name",
    "class_label",
    "loaned_at",
    "due_date",
    "overdue_days",
    "cardless",
)
#: Nüsha durum sorgusu: görevlide ödünç kimde YOK.
STAFF_STATUS_FIELDS: Final[tuple[str, ...]] = ("kind", "message", "copy")
ADMIN_STATUS_FIELDS: Final[tuple[str, ...]] = ("kind", "message", "copy", "loan")

#: F9 — masanın kişisiz durumu (`GET library/desk/state/`, iki kipte aynı): sayım için
#: hizmet arası ve okutması açık süren sayım (`{id, round}` ya da `null`). Madde 24, 26.
DESK_STATE_FIELDS: Final[tuple[str, ...]] = ("service_pause", "stocktake_scan")
DESK_STOCKTAKE_FIELDS: Final[tuple[str, ...]] = ("id", "round")

#: Görevli kipinde katalog okuma — Ağ Kataloğunun künye alanlarına denk (§4.4).
STAFF_WORK_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "title",
    "authors",
    "translator",
    "edition",
    "publisher",
    "publish_year",
    "isbn",
    "subjects",
    "language",
    "resource_type",
    "resource_type_display",
    "classification_code",
    "call_number",
    "section_name",
    "copy_count",
    "available_copy_count",
)
#: Görevli kipinde nüsha listesi — Ağ Kataloğunun nüsha alanlarına denk (durum, bölüm).
STAFF_CATALOG_COPY_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "work",
    "work_title",
    "call_number",
    "section_name",
    "status",
    "status_display",
    "is_loanable",
    "not_loanable_reason",
)

#: Okutulan kodun ve kart no'nun gövdedeki üst sınırı (okuyucu fazladan karakter
#: ekleyebilir; normalleştirme rakamları ayıklar).
KOD_UZUNLUGU: Final = 64


# ---------------------------------------------------------------------------
# İstek gövdeleri
# ---------------------------------------------------------------------------
class MasaUyeSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/desk/member/` — `{card_no}` YA DA (yalnız yönetici) `{membership_id}`."""

    card_no = serializers.CharField(max_length=KOD_UZUNLUGU, required=False, allow_blank=True)
    membership_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        kart = str(attrs.get("card_no") or "").strip()
        if bool(kart) == ("membership_id" in attrs):
            raise serializers.ValidationError("Üye kartını okutun.")
        attrs["card_no"] = kart
        return attrs


class MasaOduncSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/checkout/` — ödünç ver.

    Üye kartla (`card_no`) YA DA kartsız ödünçte üyelik kaydıyla
    (`membership_id` + `cardless_reason`) gelir; ikincisi yalnız yönetici
    kipindedir (ara katman görevli kipinde 403 verir, görünüm ayrıca keser).
    Gerekçelerin kapalı listesi ve açıklama zorunluluğu serviste denetlenir (D12).
    """

    barcode = serializers.CharField(max_length=KOD_UZUNLUGU)
    card_no = serializers.CharField(max_length=KOD_UZUNLUGU, required=False, allow_blank=True)
    membership_id = serializers.IntegerField(min_value=1, required=False)
    override_reason = serializers.CharField(max_length=32, required=False, allow_blank=True)
    override_note = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, trim_whitespace=True
    )
    cardless_reason = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        kart = str(attrs.get("card_no") or "").strip()
        kartsiz = str(attrs.get("cardless_reason") or "").strip()
        uyelik_var = "membership_id" in attrs
        if bool(kart) == uyelik_var:
            raise serializers.ValidationError("Üye kartını okutun.")
        if uyelik_var and not kartsiz:
            raise serializers.ValidationError(
                {"cardless_reason": ["Kartsız ödünçte gerekçe seçilmelidir."]}
            )
        if kart and kartsiz:
            raise serializers.ValidationError(
                {"cardless_reason": ["Kart okutulduysa kartsız ödünç gerekçesi verilmez."]}
            )
        attrs["card_no"] = kart
        attrs["cardless_reason"] = kartsiz
        return attrs


class MasaKodSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/return/` gövdesi ve `GET library/desk/copy-status/` sorgusu."""

    barcode = serializers.CharField(max_length=KOD_UZUNLUGU, allow_blank=True)


class KartKilidiSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/desk/card-unlock/` — gövdede yönetici parolası (GA-7)."""

    password = serializers.CharField(trim_whitespace=False)


# ---------------------------------------------------------------------------
# Görevli kipinde katalog okuma (works / copies GET)
# ---------------------------------------------------------------------------
# Nüsha sayaçlarının TEK türetimi `WorkSerializer`'dadır (listede anotasyon,
# ayrıntıda sayım); görevli serializer'ı aynı yöntemleri çağırır, iki yol farklı
# sayı vermesin.
_ESER_SAYACLARI = WorkSerializer()


class GorevliEserSerializer(serializers.ModelSerializer[Work]):
    """Görevli kipinde eser (künye) — Ağ Kataloğunun alan listesine denk."""

    resource_type_display = serializers.CharField(
        source="get_resource_type_display", read_only=True
    )
    section_name = serializers.SerializerMethodField()
    copy_count = serializers.SerializerMethodField()
    available_copy_count = serializers.SerializerMethodField()

    class Meta:
        model = Work
        fields = list(STAFF_WORK_FIELDS)
        read_only_fields = fields

    def get_section_name(self, obj: Work) -> str | None:
        bolum = obj.section
        return bolum.name if bolum is not None else None

    def get_copy_count(self, obj: Work) -> int:
        return _ESER_SAYACLARI.get_copy_count(obj)

    def get_available_copy_count(self, obj: Work) -> int:
        return _ESER_SAYACLARI.get_available_copy_count(obj)


class GorevliNushaSerializer(serializers.ModelSerializer[Copy]):
    """Görevli kipinde nüsha — durum, bölüm ve ödünç verilebilirlik (Ağ Kataloğuna denk)."""

    work_title = serializers.CharField(source="work.title", read_only=True)
    call_number = serializers.CharField(source="work.call_number", read_only=True)
    section_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_loanable = serializers.BooleanField(read_only=True)
    not_loanable_reason = serializers.CharField(read_only=True)

    class Meta:
        model = Copy
        fields = list(STAFF_CATALOG_COPY_FIELDS)
        read_only_fields = fields

    def get_section_name(self, obj: Copy) -> str | None:
        bolum = obj.section or obj.work.section
        return bolum.name if bolum is not None else None
