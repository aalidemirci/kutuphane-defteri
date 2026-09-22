"""Kurum yapılandırması (SchoolConfig singleton) + kurulum sihirbazı kapısı + yol haritası.

OYS `core.services.school_config` ikamesi (KS'den alındı). Farklar: env (`OYS_*`)
fallback YOK — tek doğruluk kaynağı DB satırıdır; `principal_name` Müdür
hesabından değil doğrudan yapılandırmadan gelir (login'siz program).
`setup_completed` yalnız `mark_setup_completed` ile değişir — sihirbaz kapısının
düz alan güncellemesiyle yanlışlıkla açılması/kapanması önlenir.

SİHİRBAZ SIRASI (tasarım §6.3-1, §14.1 F1) — adım anahtarları API'de ve ön
yüzde aynıdır (`SETUP_STEPS`):

1. `password` — yönetici parolası + kurtarma anahtarı (atlanamaz; anahtarın
   saklandığı istemci tarafında iki grubun geri yazdırılmasıyla doğrulanır,
   anahtar sunucuda saklanmaz).
2. `school` — okul adı, kademe, kısa ad ve "bu bilgisayar okul demirbaşıdır"
   onayı (Yönerge 11/8, 11/23). Demirbaş no isteğe bağlıdır.
3. `calendar` — aktif ders yılı ve iki dönemi. Kapalı günler bu adımda girilir
   ama tamamlamanın koşulu değildir (yol haritasında ayrı maddedir).

`setup/complete/` eksik adımda Türkçe 400 (`kurulum_eksik`) döner; hangi adımın
neden eksik olduğu iletidedir (`SetupIncomplete`).

`setup_status()` masaüstü sağlık denetiminin de ucudur (`HEALTH_PATH`): hafif
kalır (birkaç sayım sorgusu) ve KİŞİSEL VERİ İÇERMEZ — yalnız bayraklar,
sayılar, okul adı ve yol haritası işaretleri.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.okul import selectors
from apps.okul.models import SchoolConfig, SchoolLevel
from apps.okul.services import app_password

# Ayar/sihirbaz ekranından güncellenebilir alanlar (whitelist — başka alan yazılamaz).
UPDATABLE_FIELDS: tuple[str, ...] = (
    "school_name",
    "province",
    "district",
    "principal_name",
    "has_prep_class",
    "kademe",
    "kisa_ad",
    "demirbas_onayi",
    "demirbas_no",
)

# Sihirbaz adımları, sırasıyla (API ve ön yüz aynı anahtarları kullanır).
STEP_PASSWORD = "password"  # noqa: S105 — adım anahtarı, parola değil
STEP_SCHOOL = "school"
STEP_CALENDAR = "calendar"
SETUP_STEPS: tuple[str, ...] = (STEP_PASSWORD, STEP_SCHOOL, STEP_CALENDAR)


class SetupIncomplete(ValueError):
    """Kurulum tamamlanamaz: en az bir sihirbaz adımı eksik (400 `kurulum_eksik`)."""

    def __init__(self, missing: list[str], message: str) -> None:
        super().__init__(message)
        self.missing = missing


def get_school_config() -> SchoolConfig:
    """Singleton satırı; yoksa kaydedilmemiş varsayılan (okuma DB'ye yazmaz)."""
    return SchoolConfig.load()


@transaction.atomic
def update_school_config(*, fields: dict[str, Any]) -> SchoolConfig:
    """Kurum yapılandırmasını günceller (whitelist alanları). Satır yoksa oluşturur."""
    config: SchoolConfig
    config, _created = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    update_fields: list[str] = ["updated_at"]
    for name in UPDATABLE_FIELDS:
        if name in fields:
            setattr(config, name, fields[name])
            update_fields.append(name)
    config.save(update_fields=update_fields)
    return config


# ---------------------------------------------------------------------------
# Sihirbaz adımları
# ---------------------------------------------------------------------------
def missing_school_fields(config: SchoolConfig) -> list[str]:
    """2. adımın eksik alanları — kullanıcı diliyle (sözlük), sırasıyla."""
    eksik: list[str] = []
    if not config.school_name.strip():
        eksik.append("okul adı")
    if config.kademe not in SchoolLevel.values:
        eksik.append("kademe")
    if not config.kisa_ad.strip():
        eksik.append("kısa ad")
    if not config.demirbas_onayi:
        eksik.append("“Bu bilgisayar okul demirbaşıdır” onayı")
    return eksik


def _active_year_summary() -> dict[str, Any] | None:
    """Aktif ders yılının özeti (kişisel veri yok); yoksa None."""
    yil = selectors.active_school_year()
    if yil is None:
        return None
    siralar = set(selectors.school_terms(school_year_id=yil.pk).values_list("sequence", flat=True))
    return {
        "id": yil.pk,
        "name": yil.name,
        "start_date": yil.start_date.isoformat(),
        "end_date": yil.end_date.isoformat(),
        # İki dönem de tanımlı mı? (dönem bazlı raporlar ve tarih → dönem çözümü)
        "terms_ready": siralar == {1, 2},
    }


_HESAPLA: Any = object()  # "çağıran vermedi, burada hesapla" işareti (None geçerli bir değerdir)


def missing_setup_steps(
    *,
    config: SchoolConfig | None = None,
    active_year: Any = _HESAPLA,
    password_set: bool | None = None,
) -> list[str]:
    """Eksik sihirbaz adımları (`SETUP_STEPS` sırasıyla); hepsi tamamsa boş liste.

    `setup_status` zaten okuduğu değerleri geçirir (sağlık denetimi ucu hafif
    kalsın diye aynı sorgu iki kez koşmaz); verilmeyenler burada okunur.
    """
    config = config if config is not None else get_school_config()
    if active_year is _HESAPLA:
        active_year = _active_year_summary()
    if password_set is None:
        password_set = app_password.is_password_set()
    eksik: list[str] = []
    if not password_set:
        eksik.append(STEP_PASSWORD)
    if missing_school_fields(config):
        eksik.append(STEP_SCHOOL)
    if active_year is None or not active_year["terms_ready"]:
        eksik.append(STEP_CALENDAR)
    return eksik


def setup_incomplete_message(missing: list[str], *, config: SchoolConfig) -> str:
    """`setup/complete/` ret iletisi: hangi adım neden eksik (Türkçe, iç kod yok)."""
    parcalar: list[str] = []
    if STEP_PASSWORD in missing:
        parcalar.append("1. adım (yönetici parolası): yönetici parolası kurulmadı.")
    if STEP_SCHOOL in missing:
        alanlar = ", ".join(missing_school_fields(config))
        parcalar.append(f"2. adım (okul bilgileri): {alanlar} eksik.")
    if STEP_CALENDAR in missing:
        parcalar.append(
            "3. adım (ders yılı): aktif bir ders yılı ve iki dönemin tarihleri tanımlanmalı."
        )
    return "Kurulum tamamlanamadı. " + " ".join(parcalar)


@transaction.atomic
def mark_setup_completed() -> SchoolConfig:
    """Kurulum sihirbazını tamamlanmış işaretler; eksik adımda `SetupIncomplete`.

    Kapı sunucudadır: ön yüzün adım kapıları atlanarak (ör. doğrudan istekle)
    parolasız ya da demirbaş onaysız bir kurulum tamamlanamaz.
    """
    config: SchoolConfig
    config, _created = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    eksik = missing_setup_steps(config=config)
    if eksik:
        raise SetupIncomplete(eksik, setup_incomplete_message(eksik, config=config))
    config.setup_completed = True
    config.save(update_fields=["setup_completed", "updated_at"])
    return config


# ---------------------------------------------------------------------------
# Başlangıç Yol Haritası (Genel Bakış kartı)
# ---------------------------------------------------------------------------
# Kendiliğinden tespit edilen maddeler ön yüzde `setup_status` sayılarından
# okunur (öğrenci/personel sayısı, aktif ders yılındaki öğrenciye kapalı gün
# sayısı). Burada yalnız KULLANICININ İŞARETLEDİĞİ maddeler tutulur: program
# bunların yapıldığını bilemez (zarfın kapatılması, parolanın paylaşılması…).
ROADMAP_MANUAL_ITEMS: tuple[str, ...] = (
    "katalog_sablonu",  # katalog Excel şablonunu indirip doldurmaya başla
    "kurtarma_zarfi",  # kurtarma anahtarını müdürlükte kapalı zarfta sakla
    "parola_paylasimi",  # yönetici parolasını en az iki görevlendirilmiş kişiyle paylaş
    "btr_gorusmesi",  # Ağ Kataloğu için BTR ile görüş (bilgi maddesi)
)

_ROADMAP_MARKS = "isaretler"
_ROADMAP_HIDDEN = "gizli"


class RoadmapError(ValueError):
    """Yol haritası isteği geçersiz (Türkçe ileti; 400)."""


def roadmap_state(config: SchoolConfig) -> dict[str, Any]:
    """Saklanan işaretlerin ARINDIRILMIŞ hâli — bilinmeyen anahtar dışarı çıkmaz."""
    ham: Any = config.yol_haritasi if isinstance(config.yol_haritasi, dict) else {}
    isaretler: Any = ham.get(_ROADMAP_MARKS)
    isaretler = isaretler if isinstance(isaretler, dict) else {}
    return {
        "marks": {
            madde: str(isaretler[madde])
            for madde in ROADMAP_MANUAL_ITEMS
            if isinstance(isaretler.get(madde), str) and isaretler[madde]
        },
        "hidden": bool(ham.get(_ROADMAP_HIDDEN, False)),
    }


def roadmap_auto_items(status: dict[str, Any]) -> dict[str, bool]:
    """Kendiliğinden tespit edilen maddeler (`setup_status` sayılarından)."""
    return {
        "ogrenci_aktarimi": int(status["student_count"]) > 0,
        "personel_aktarimi": int(status["personnel_count"]) > 0,
        "kapali_gunler": int(status["school_break_count"]) > 0,
    }


def _save_roadmap(config: SchoolConfig, state: dict[str, Any]) -> None:
    config.yol_haritasi = {_ROADMAP_MARKS: state["marks"], _ROADMAP_HIDDEN: state["hidden"]}
    config.save(update_fields=["yol_haritasi", "updated_at"])


@transaction.atomic
def set_roadmap_mark(item: str, *, done: bool) -> dict[str, Any]:
    """Kullanıcının işaretlediği bir maddeyi işaretler ya da işareti kaldırır."""
    if item not in ROADMAP_MANUAL_ITEMS:
        raise RoadmapError("Bu madde elle işaretlenemez.")
    config: SchoolConfig
    config, _created = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    state = roadmap_state(config)
    if done:
        state["marks"][item] = timezone.localdate().isoformat()
    else:
        state["marks"].pop(item, None)
        state["hidden"] = False  # eksik madde varken kart gizli kalmaz
    _save_roadmap(config, state)
    return state


@transaction.atomic
def set_roadmap_hidden(*, hidden: bool) -> dict[str, Any]:
    """Kartı gizler/gösterir. Gizleme yalnız bütün maddeler tamamlanınca yapılır."""
    config: SchoolConfig
    config, _created = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    state = roadmap_state(config)
    if hidden:
        durum = setup_status()
        otomatik_eksik = [k for k, tamam in roadmap_auto_items(durum).items() if not tamam]
        elle_eksik = [m for m in ROADMAP_MANUAL_ITEMS if m not in state["marks"]]
        if otomatik_eksik or elle_eksik:
            raise RoadmapError("Başlangıç yol haritası bütün maddeler tamamlanınca gizlenebilir.")
    state["hidden"] = hidden
    _save_roadmap(config, state)
    return state


# ---------------------------------------------------------------------------
# Durum özeti (sihirbaz + kurulum kapısı + masaüstü sağlık denetimi)
# ---------------------------------------------------------------------------
def setup_status() -> dict[str, Any]:
    """`GET setup/status/` — hafif, KİŞİSEL VERİ İÇERMEZ (modül başlığı).

    Alan kümesi hem ön yüz `SetupStatus` tipinin hem masaüstü sağlık denetiminin
    sözleşmesidir; değişirse ikisi birlikte gözden geçirilir.
    """
    config = get_school_config()
    aktif_yil = _active_year_summary()
    parola_kurulu = app_password.is_password_set()
    return {
        "setup_completed": config.setup_completed,
        "password_set": parola_kurulu,
        "school_name": config.school_name,
        "school_info_complete": not missing_school_fields(config),
        "has_active_school_year": aktif_yil is not None,
        "active_school_year": aktif_yil,
        "missing_steps": missing_setup_steps(
            config=config, active_year=aktif_yil, password_set=parola_kurulu
        ),
        "student_count": selectors.student_count(),
        "personnel_count": selectors.personnel_count(),
        "class_section_count": selectors.class_sections().count(),
        "school_break_count": selectors.school_break_count(
            start=aktif_yil["start_date"] if aktif_yil else None,
            end=aktif_yil["end_date"] if aktif_yil else None,
        ),
        "roadmap": roadmap_state(config),
    }


def get_letterhead_identity() -> dict[str, str]:
    """Resmî evrak antedi için kurum kimliği.

    Döner: `school_name`, `district`, `province`, `principal_name` — hepsi düz
    metin. Okul adı boşsa OYS paritesiyle 'Okul' yer tutucusu; ilçe/müdür boş
    kalabilir (antet şablonu yer tutucu basar).
    """
    config = get_school_config()
    return {
        "school_name": config.school_name.strip() or "Okul",
        "district": config.district.strip(),
        "province": config.province.strip(),
        "principal_name": config.principal_name.strip(),
    }
