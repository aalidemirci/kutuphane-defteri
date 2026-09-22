"""Kurum yapılandırması (SchoolConfig singleton) + kurulum sihirbazı kapısı + yol haritası.

OYS `core.services.school_config` ikamesi (KS'den alındı). Farklar: env (`OYS_*`)
fallback YOK — tek doğruluk kaynağı DB satırıdır; `principal_name` Müdür
hesabından değil doğrudan yapılandırmadan gelir (login'siz program).
`setup_completed` yalnız `mark_setup_completed` ile değişir — sihirbaz kapısının
düz alan güncellemesiyle yanlışlıkla açılması/kapanması önlenir.

SİHİRBAZ SIRASI (tasarım §6.3-1, §14.1 F1) — adım anahtarları API'de ve ön
yüzde aynıdır (`SETUP_STEPS`):

1. `password` — yönetici parolası + kurtarma anahtarı (atlanamaz). Adım ancak
   parola kurulu VE anahtarın saklandığı doğrulanmışsa tamamdır (F1 eki,
   22.09.2026 kullanıcı kararı 2): sihirbaz iki grubu istemcide denetler, sonra
   TAM anahtarı `security/recovery-key/confirm/`'a gönderir; sunucu onu kurtarma
   sarmalına karşı doğrulayıp `guvenlik.json`'a damga yazar
   (`app_password.confirm_recovery_key`). Anahtar sunucuda saklanmaz. Kurulumu
   bu karardan önce tamamlanmış (damgasız) kurulum kilitlenmez; yol haritası ve
   Güvenlik ekranı uyarı gösterir (`recovery_key_confirmed`).
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
    recovery_confirmed: bool | None = None,
) -> list[str]:
    """Eksik sihirbaz adımları (`SETUP_STEPS` sırasıyla); hepsi tamamsa boş liste.

    1. adım parola kurulu değilse YA DA kurtarma anahtarı doğrulanmamışsa
    eksiktir. `setup_status` zaten okuduğu değerleri geçirir (sağlık denetimi
    ucu hafif kalsın diye aynı sorgu iki kez koşmaz); verilmeyenler burada okunur.
    """
    config = config if config is not None else get_school_config()
    if active_year is _HESAPLA:
        active_year = _active_year_summary()
    if password_set is None:
        password_set = app_password.is_password_set()
    if recovery_confirmed is None:
        recovery_confirmed = password_set and app_password.recovery_key_confirmed()
    eksik: list[str] = []
    if not password_set or not recovery_confirmed:
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
        if app_password.is_password_set():
            parcalar.append(
                "1. adım (yönetici parolası): kurtarma anahtarı doğrulanmadı. Anahtarı "
                "sakladıktan sonra istenen iki grubunu yazarak doğrulayın; kaydedemediyseniz "
                "yenisini üretin."
            )
        else:
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


def _stored_roadmap(config: SchoolConfig) -> dict[str, Any]:
    """SAKLANAN işaretlerin arındırılmış hâli — bilinmeyen anahtar dışarı çıkmaz.

    Yazma yolları (işaretleme, gizleme) bunu kullanır: kullanıcının "gizle"
    tercihi `roadmap_state`'in kapısı yüzünden sessizce silinmesin.
    """
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


def roadmap_state(
    config: SchoolConfig, *, recovery_confirmed: bool | None = None
) -> dict[str, Any]:
    """Arayüzün gördüğü yol haritası durumu (saklanan işaretler + gizleme kapısı).

    Kurtarma anahtarının saklandığı doğrulanmamışsa kart GİZLİ KALAMAZ (`hidden`
    yanlış döner): "kurtarma anahtarı doğrulanmadı" uyarısı kartın içindedir ve
    Genel Bakış kartı basmazsa uyarı hiç görünmezdi — kartı geri getirecek bir
    arayüz yolu da yoktur (işaret kutuları ve gizleme düğmesi kartın içindedir).
    Bu, var olan "eksik madde varken kart gizli kalmaz" kuralının damgaya
    uygulanmasıdır; SAKLANAN tercih değişmez, damga gelince kart yine gizlenir.

    `recovery_confirmed` verilmezse güvenlik dosyasından okunur; `setup_status`
    zaten bildiği için geçirir (aynı dosya iki kez okunmasın).
    """
    state = _stored_roadmap(config)
    dogrulandi = (
        app_password.recovery_key_confirmed() if recovery_confirmed is None else recovery_confirmed
    )
    state["hidden"] = state["hidden"] and dogrulandi
    return state


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
    state = _stored_roadmap(config)
    if done:
        state["marks"][item] = timezone.localdate().isoformat()
    else:
        state["marks"].pop(item, None)
        state["hidden"] = False  # eksik madde varken kart gizli kalmaz
    _save_roadmap(config, state)
    return roadmap_state(config)


@transaction.atomic
def set_roadmap_hidden(*, hidden: bool) -> dict[str, Any]:
    """Kartı gizler/gösterir. Gizleme yalnız bütün maddeler tamamlanınca yapılır.

    Kurtarma anahtarı doğrulanmamışken gizlenemez: uyarı kartın içindedir
    (F1 eki 10). Kapı hem burada hem `roadmap_state`'tedir — eski bir kurulumda
    damgasızken kart zaten gizli kaydedilmiş olabilir.
    """
    config: SchoolConfig
    config, _created = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    state = _stored_roadmap(config)
    if hidden:
        durum = setup_status()
        if not durum["recovery_key_confirmed"]:
            raise RoadmapError(
                "Kurtarma anahtarının saklandığı doğrulanmadan başlangıç yol haritası "
                "gizlenemez. Anahtarı Ayarlar → Güvenlik'te doğrulayın."
            )
        otomatik_eksik = [k for k, tamam in roadmap_auto_items(durum).items() if not tamam]
        elle_eksik = [m for m in ROADMAP_MANUAL_ITEMS if m not in state["marks"]]
        if otomatik_eksik or elle_eksik:
            raise RoadmapError("Başlangıç yol haritası bütün maddeler tamamlanınca gizlenebilir.")
    state["hidden"] = hidden
    _save_roadmap(config, state)
    return roadmap_state(config)


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
    anahtar_dogrulandi = parola_kurulu and app_password.recovery_key_confirmed()
    return {
        "setup_completed": config.setup_completed,
        "password_set": parola_kurulu,
        # Kurtarma anahtarının saklandığı doğrulandı mı? (1. adımın ikinci koşulu)
        "recovery_key_confirmed": anahtar_dogrulandi,
        "school_name": config.school_name,
        "school_info_complete": not missing_school_fields(config),
        "has_active_school_year": aktif_yil is not None,
        "active_school_year": aktif_yil,
        "missing_steps": missing_setup_steps(
            config=config,
            active_year=aktif_yil,
            password_set=parola_kurulu,
            recovery_confirmed=anahtar_dogrulandi,
        ),
        "student_count": selectors.student_count(),
        "personnel_count": selectors.personnel_count(),
        "class_section_count": selectors.class_sections().count(),
        "school_break_count": selectors.school_break_count(
            start=aktif_yil["start_date"] if aktif_yil else None,
            end=aktif_yil["end_date"] if aktif_yil else None,
        ),
        "roadmap": roadmap_state(config, recovery_confirmed=anahtar_dogrulandi),
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
