"""Zorunlu yönetici parolası — kurma, açma, doğrulama, değiştirme, kurtarma.

Tasarım §4.3, §4.4 (kilit), §6.3. `shared.crypto` kriptografik ilkelleri
(Argon2id türetme, zarf sarmalama, şifreli alanlar, kör indeks) sağlar; bu
modül BÜTÜN AKIŞI yönetir:

    guvenlik.json (veri dizini)          SQLite (db.sqlite3)
    ├── kdf parametreleri                ├── okul_student.first_name .. token
    ├── parola: {tuz, sarmal(DEK)}       ├── okul_personnel.first_name  token
    ├── kurtarma: {tuz, sarmal(DEK)}     └── okul_schoolconfig
    └── gecis: TAMAM|SIFRELENIYOR            └── app_password_hash = parmak izi

**Yönetici parolası zorunludur ve parolasız dal YOKTUR** (§6.3-6: KS'deki
"parolayı kaldır" akışı, çözme geçişi ve düz yedekler F1'de söküldü). Kurulum
sihirbazının ilk adımı parola + kurtarma anahtarıdır; parola kurulmadan kişi
yazan uçlar 409 `parola_gerekli` döner (`apps/okul/permissions.py`,
`require_password_set`), şifreli alan anahtarsız yazmaz (`KeyMissingError`).

**DEK (veri anahtarı) hiçbir yerde açık durmaz**; iki kez sarmalanır: bir kez
paroladan türetilen anahtarla, bir kez de yazdırılabilir kurtarma anahtarından
türetilenle. Parola unutulursa kurtarma anahtarı veriyi kurtarır. DEK kurulumda
bir kez üretilir ve hiç değişmez: parola değişimi de kurtarma anahtarının
yenilenmesi de yalnız ilgili sarmalı yeniler; kör indeks, yedek anahtarı
(`yedekleme.json`) ve eski yedekler geçerli kalır.

FAIL-CLOSED DURUM SORGUSU (GA-2, §4.3): "parola kurulu mu?" sorusunun cevabı
güvenlik dosyasının VARLIĞI **ya da** DB'deki anahtar parmak izidir. Kilitliyken
`guvenlik.json` silinir ya da yeniden adlandırılırsa program "parolasız"a
dönmez: parmak izi dolu + dosya yok = **güvenlik dosyası kayıp** kilidi
(`security_file_missing`). Dosya silinmeyip içi boşaltılır ya da bozulursa da
aynı kilide düşülür (kullanılabilirlik kuralı tektir:
`desktop.backup_crypto.is_usable_security_state`; günlük yedek aynı kuralla
başlıksız yedek almaz). Bu durumda yalnız durum uçları ve yedekten geri
yükleme açıktır (`lock_middleware`); geri yükleme `guvenlik.json`'u yedeğin
kurtarma başlığından yeniden yazar, bozuk dosyayı arşivler
(`backup_restore._ensure_state_file`). `enable()` bu durumda reddeder.
Tek istisna (F1-E): dosya kullanılamıyor AMA parmak izi boş ve şifreli alan
taşıyan bütün tablolar boşsa korunacak veri yoktur; "güvenlik dosyasını sıfırla
ve kuruluma dön" yolu dosyayı arşivleyip ilk açılış hâline döner
(`state_reset_available`, `reset_unusable_state`).

KURTARMA ANAHTARI ÇIKTISI (E14): `verify_recovery_key` anahtarı kurtarma
sarmalına VE bellekteki anahtara karşı doğrular (yanlışta kademeli gecikme);
yalnız o zaman PDF basılır (`services.recovery_key_document`). Anahtar
sunucuda saklanmaz, hiçbir günlüğe ve hata iletisine yazılmaz.

KURTARMA ANAHTARININ DOĞRULANMASI (F1 eki, 22.09.2026 kullanıcı kararı 2):
kurulum, anahtarın saklandığı doğrulanmadan tamamlanmaz. Sihirbaz iki grubu
istemcide denetledikten sonra bellekteki TAM anahtarı gönderir;
`confirm_recovery_key` onu `verify_recovery_key` kuralıyla doğrular ve
`guvenlik.json`'un kurtarma bölümüne doğrulama damgasını (`kurtarma.dogrulandi`,
ISO zaman damgası) atomik yazar. Damga sarmalla birlikte yaşar: yenilemede
yeni kurtarma bölümü damgasız yazılır. DB'de alan yoktur (migration gerekmez);
`recovery_key_confirmed()` ve `status()` damgayı okur.

KURTARMA ANAHTARINI YENİLEME (aynı kararın 3. maddesi; F11 görev devrinin bu
parçası F1'e çekildi): `renew_recovery_key(password=…)` yalnız kilit açıkken
çalışır, yönetici parolasını bellekteki anahtara karşı doğrular, YENİ anahtar
ve YENİ tuzla aynı DEK'i sarmalar. Önceki `guvenlik.json` önce
`guvenlik-arsiv-<damga>.json` olarak KOPYALANIR (silinmez; `guvenlik.json` hiçbir
an yok olmaz, yarıda kesilen yenileme dosyayı kayıp hâline düşürmez), sonra yeni
durum atomik yazılır. Yeni anahtar yanıtla BİR KEZ döner. DEK değişmediği için
kayıtlar, kör indeks ve yedek anahtarı aynen kalır; bunun iki sonucu vardır ve
arayüz ile kılavuz ikisini de söyler:

* her yedek, alındığı anın `guvenlik.json`'unu başlığında taşır
  (`backup_crypto.recovery_metadata`/`usable_recovery_header`): yenilemeden
  ÖNCE alınmış yedek, güncel güvenlik dosyası yokken (başka bilgisayar, kayıp
  dosya) yalnız ESKİ kurtarma anahtarıyla ya da o dönemin parolasıyla açılır;
  bu bilgisayarda güncel dosya yerindeyken yeni anahtar ve güncel parola da
  açar (`backup_restore._candidate_states`). Yenilemeden SONRA alınan yedekler
  yeni başlığı taşır;
* yenileme, ele geçmiş bir anahtara karşı koruma DEĞİLDİR: eski yedekler ve
  arşivlenen dosya eski anahtarla açılmaya devam eder. Yenilemenin amacı
  kaydedilemeyen ya da kaybolan kâğıdın yerine yenisini koymaktır.

Güvenlik dosyasını değiştiren işlemler (doğrulama damgası, yenileme, parola
değişimi, kurtarmayla parola yenileme, yarım geçişin tamamlanması) süreç içi bir
kilitle sıralanır: oku-değiştir-yaz arasına başka bir yazım girip onu ezmesin.

NEDEN GÜVENLİK DOSYASI VERİ DİZİNİNDE, DB'DE DEĞİL?
  * Yedekler (`backups/gunluk-*.kdbak`) X25519 + AES-256-GCM kapsayıcılarıdır;
    DB kopyası tek başına ad, okul no ve kart no açmaz.
  * DB'de yalnız anahtarın PARMAK İZİ durur; yanlış eşleşme (başka kurulumun
    güvenlik dosyası) sessizce bozuk çözme yerine açık ret üretir.

KURULUMUN ÇÖKME GÜVENLİĞİ: `enable()` yalnız kişi tabloları boşken çalışır,
ama sıra yine her kesinti noktasında anahtarı koruyacak biçimde kurulmuştur:

    1. guvenlik.json yazılır (gecis=SIFRELENIYOR) ......... anahtar artık kayıp değil
    2. Geçiş öncesi şifreli yedek (`pre-parola-*.kdbak`)
    3. TEK veritabanı işlemi: şifreli satırlar + parmak izi ... ya hep ya hiç
    4. guvenlik.json güncellenir (gecis=TAMAM)

  Kesinti 1-3 arası: dosya var, parmak izi boş → kilit açılışı `resume_pending`
  ile tamamlar. Kesinti 3-4 arası: parmak izi yazılı; `resume_pending` yalnız
  dosyadaki damgayı düzeltir (satır yeniden yazımı fikirdeştir).

YANLIŞ PAROLA DENEMESİ: kalıcı kilitlenme YOKTUR — çevrimdışı bir programda
hesabı açacak bir yönetici yoktur, kilitlenme kendi kendine hizmet reddi
olurdu. Bunun yerine (a) Argon2id maliyeti her denemeyi ~0,2 sn yapar, (b) art
arda hatalarda süreç içi kademeli gecikme uygulanır. Çevrimdışı saldırıya karşı
gerçek koruma Argon2id parametreleri + tam disk şifrelemesidir (BitLocker/LUKS).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from desktop.backup import database_snapshot, encrypt_legacy_backups
from desktop.backup_crypto import (
    BACKUP_SUFFIX,
    BackupCryptoError,
    config_path,
    encrypt_to_path,
    ensure_public_config,
    load_public_key,
    parse_security_state,
    recovery_metadata,
)
from django.apps import apps as django_apps
from django.conf import settings
from django.db import connection, models, transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.okul.models import Personnel, SchoolConfig, Student
from shared import crypto
from shared.exceptions import PASSWORD_REQUIRED_MESSAGE

logger = logging.getLogger("kutuphane_defteri.guvenlik")

# --- Dosya/dizin çözümü -----------------------------------------------------
STATE_FILE_NAME = "guvenlik.json"
# Testler ve taşınabilir kip için: verilirse güvenlik dosyasının/yedeklerin yeri.
ENV_SECURITY_DIR = "KD_SECURITY_DIR"
ENV_BACKUP_DIR = "KD_BACKUP_DIR"

STATE_VERSION = 1

# Geçiş durumu damgaları (dosyada saklanır). Parolasız dal olmadığı için tek
# geçiş yönü vardır: şifreleme.
TRANSITION_DONE = "TAMAM"
TRANSITION_ENCRYPTING = "SIFRELENIYOR"

MIN_PASSWORD_LENGTH = 8

#: Kurtarma bölümündeki doğrulama damgası (ISO zaman damgası; F1 eki, karar 2).
#: Sarmalla birlikte yaşar: yenilenen kurtarma bölümü damgasız yazılır.
RECOVERY_CONFIRMED_FIELD = "dogrulandi"
#: Kenara alınan güvenlik dosyalarının ad öneki (`guvenlik-arsiv-<damga>.json`);
#: geri yükleme (`backup_restore._ensure_state_file`) ve `recovery_metadata`
#: aynı deseni kullanır.
STATE_ARCHIVE_PREFIX = "guvenlik-arsiv-"

# Güvenlik dosyasını oku-değiştir-yaz işlemlerinin süreç içi sırası (modül başlığı).
# Yeniden girilebilir: kurtarmayla açılış `_adopt_key` → `resume_pending` zincirini
# kilit içindeyken çağırır.
_state_lock = threading.RLock()

# Kurtarma anahtarı: 20 rastgele bayt → base32 (32 karakter) → 8 dörtlü grup.
RECOVERY_KEY_BYTES = 20
RECOVERY_GROUP_SIZE = 4
# Base32 alfabesinde 0/1/8/9 yoktur; elle yazımda en sık karışan ikili düzeltilir.
_RECOVERY_FIXUPS = str.maketrans({"0": "O", "1": "I", "8": "B"})
#: Türkçe klavyede büyük harfle yazılan "i" noktalı "İ" (U+0130) olur ve Python'un
#: `upper()`'ı onu "I"ya çevirmez; noktasız "ı" da güvence için eşlenir. Anahtar
#: alfabesi ASCII'dir (A-Z, 2-7): ikisi de "I"dır. Ön yüz aynı eşlemeyi uygular
#: (`frontend/src/modules/guvenlik/kurtarma.ts`).
_RECOVERY_TURKISH_I = str.maketrans({"İ": "I", "ı": "I"})

# Art arda yanlış denemede uygulanan gecikme (saniye). Son değer tavandır.
FAILURE_DELAYS: tuple[float, ...] = (0.0, 0.0, 1.0, 2.0, 4.0)
_failed_attempts = 0

# Kullanıcıya görünen iletiler (sözlük: "yönetici parolası"). Ara katman ve
# arayüz aynı metni kullanır (sözleşme §2). `PASSWORD_REQUIRED_MESSAGE`'ın tek
# kaynağı `shared.exceptions`'tır (409 gövdesi oradan kurulur).
SECURITY_FILE_MISSING_MESSAGE = (
    "Güvenlik dosyası (guvenlik.json) bulunamadı ya da okunamıyor. Kayıtlar açılamaz. "
    "Dosyanın sağlam bir kopyasını veri klasörüne geri koyun ya da bir yedekten geri yükleyin."
)
_NOT_SET_MESSAGE = "Yönetici parolası kurulu değil."
_WRONG_PASSWORD_MESSAGE = "Parola hatalı."  # noqa: S105 — kullanıcı iletisi, parola değil
_WRONG_RECOVERY_MESSAGE = (
    "Kurtarma anahtarı hatalı. Yazdırdığınız kâğıttaki anahtarı olduğu gibi girin."
)
_LOCKED_MESSAGE = "Kayıtlar kilitli. Önce yönetici parolasıyla kilidi açın."
RESET_NOT_ALLOWED_MESSAGE = (
    "Güvenlik dosyası sıfırlanamaz: bu yol yalnız hiç kişi kaydı girilmemiş ve kayıtların "
    "anahtarı henüz veritabanına işlenmemiş bir kurulumda, güvenlik dosyası okunamıyorken "
    "açıktır. Dosyanın sağlam bir kopyasını veri klasörüne geri koyun ya da bir yedekten "
    "geri yükleyin."
)


class AppPasswordError(ValueError):
    """Kullanıcıya gösterilecek Türkçe hata (view katmanı 400'e çevirir)."""


class PasswordRequired(crypto.KeyMissingError):
    """Yönetici parolası kurulmadan kişi yazılmak istendi (409 `parola_gerekli`).

    `KeyMissingError`'ın alt sınıfıdır: parola yoksa anahtar da yoktur ve
    `shared.exceptions.kd_exception_handler` ikisini aynı 409 yanıtına çevirir.
    """

    def __init__(self, message: str = PASSWORD_REQUIRED_MESSAGE) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Yol yardımcıları
# ---------------------------------------------------------------------------
def _data_dir() -> Path:
    return Path(os.environ.get(ENV_SECURITY_DIR) or settings.DATA_DIR)


def state_path() -> Path:
    """`guvenlik.json` yolu — veri dizininde, db.sqlite3'ün yanında."""
    return _data_dir() / STATE_FILE_NAME


def backup_dir() -> Path:
    """Yedek dizini. Paketlenmiş kipte `<veri kökü>/backups` (desktop/paths.py)."""
    override = os.environ.get(ENV_BACKUP_DIR)
    if override:
        return Path(override)
    # settings.DATA_DIR = <kök>/data → yedekler <kök>/backups (desktop/paths.py yerleşimi).
    return Path(settings.DATA_DIR).parent / "backups"


# ---------------------------------------------------------------------------
# Durum dosyası
# ---------------------------------------------------------------------------
def read_state() -> dict[str, Any] | None:
    """Güvenlik dosyasını okur; yoksa None. Bozuksa Türkçe hata yükseltir."""
    path = state_path()
    if not path.is_file():
        return None
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AppPasswordError(
            "Güvenlik dosyası (guvenlik.json) okunamadı ya da bozuk. Dosyanın sağlam bir "
            "kopyasını veri klasörüne geri koyun ya da bir yedekten geri yükleyin; dosya "
            "olmadan şifreli alanlar açılamaz."
        ) from exc
    if not isinstance(data, dict):
        raise AppPasswordError("Güvenlik dosyası (guvenlik.json) beklenen biçimde değil.")
    return data


def _require_state() -> dict[str, Any]:
    """Güvenlik dosyasını okur; yoksa kayıp mı hiç kurulmamış mı olduğunu söyler."""
    state = read_state()
    if state is None:
        if _stored_fingerprint():
            raise AppPasswordError(SECURITY_FILE_MISSING_MESSAGE)
        raise AppPasswordError(_NOT_SET_MESSAGE)
    return state


def _write_state(data: dict[str, Any]) -> None:
    """Dosyayı ATOMİK yazar (önce .tmp, sonra yerine koy) — yarım dosya kalmaz."""
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _archive_target() -> Path:
    """Boş bir `guvenlik-arsiv-<damga>.json` yolu (aynı saniyede ikinci arşiv ezilmez)."""
    yol = state_path()
    damga = timezone.localtime().strftime("%Y-%m-%d-%H%M%S")
    arsiv = yol.with_name(f"{STATE_ARCHIVE_PREFIX}{damga}.json")
    sira = 2
    while arsiv.exists():
        arsiv = yol.with_name(f"{STATE_ARCHIVE_PREFIX}{damga}-{sira}.json")
        sira += 1
    return arsiv


def _copy_state_to_archive() -> Path:
    """Güncel güvenlik dosyasının baytlarını arşive KOPYALAR (asıl dosya yerinde kalır).

    Arşiv de atomik yazılır (.tmp → yerine koy): yarım arşiv dosyası kalmaz.
    """
    arsiv = _archive_target()
    temp = arsiv.with_name(arsiv.name + ".tmp")
    temp.write_bytes(state_path().read_bytes())
    temp.replace(arsiv)
    return arsiv


# ---------------------------------------------------------------------------
# Geçiş öncesi yedek
# ---------------------------------------------------------------------------
def database_file() -> Path | None:
    """Canlı veritabanı dosyasının yolu; dosya tabanlı değilse (testler) None."""
    if connection.vendor != "sqlite":  # pragma: no cover — program yalnız SQLite kullanır
        return None
    ad = str(connection.settings_dict.get("NAME") or "")
    # Django'nun SQLite test veritabanı bellek içidir (`file:...mode=memory...`).
    if not ad or ad == ":memory:" or "mode=memory" in ad:
        return None
    return Path(ad)


def take_transition_backup(label: str) -> Path | None:
    """Geçiş ÖNCESİ tam veritabanı kopyası alır; yolunu döndürür (alınamazsa None).

    Masaüstü kabuğuyla aynı RAM-içi SQLite görüntüsü ve `.kdbak` şifreli kapsayıcı
    yordamları kullanılır. Adı rotasyon desenlerine ÇAKIŞMAZ (`pre-parola-*`);
    kabuğun 14 günlük rotasyonu bu dosyalara DOKUNMAZ.

    KOPYA AYRI BİR BAĞLANTIDAN alınır (canlı Django bağlantısından DEĞİL): açık
    bir işlem varken `sqlite3.Connection.backup()` SQLITE_BUSY'de sonsuz döngüye
    girer — testte donma olarak yakalandı. Ayrı bağlantı WAL dosyasını da
    okuduğu için kopya tutarlıdır.

    Bellek-içi veritabanında (testler) yedek ATLANIR ve None döner; çağıranlar
    yedeği zorunlu koşul saymaz, ama gerçek kurulumda daima alınır.
    """
    kaynak = database_file()
    if kaynak is None or not kaynak.exists():
        logger.warning("Veritabanı dosya tabanlı değil; geçiş öncesi yedek atlandı.")
        return None
    hedef_dizin = backup_dir()
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    damga = timezone.localtime().strftime("%Y-%m-%d-%H%M%S")
    hedef = hedef_dizin / f"pre-parola-{label}-{damga}{BACKUP_SUFFIX}"
    try:
        encrypt_to_path(
            database_snapshot(kaynak),
            hedef,
            load_public_key(_data_dir()),
            recovery_header=recovery_metadata(_data_dir()),
        )
    except (sqlite3.Error, OSError, BackupCryptoError):
        logger.exception("Geçiş öncesi yedek alınamadı.")
        raise AppPasswordError(
            "Güvenlik değişikliği öncesi yedek alınamadı; işlem yapılmadı. "
            "Veri klasöründe yer olduğundan emin olup yeniden deneyin."
        ) from None
    logger.info("Geçiş öncesi yedek alındı: %s", hedef.name)
    return hedef


# ---------------------------------------------------------------------------
# Şifreli alan kayıt defteri + toplu yeniden yazma
# ---------------------------------------------------------------------------
def encrypted_field_map() -> list[tuple[type[models.Model], tuple[str, ...]]]:
    """Şifreli alan taşıyan tüm modeller — elle liste YOK, koddan okunur.

    Yeni bir `EncryptedTextField` eklendiğinde geçiş aracı onu KENDİLİĞİNDEN
    kapsar; unutulan alan yüzünden yarı şifreli sicil oluşmaz.
    """
    sonuc: list[tuple[type[models.Model], tuple[str, ...]]] = []
    for model in django_apps.get_models():
        alanlar = tuple(f.name for f in crypto.encrypted_fields_of(model))
        if alanlar:
            sonuc.append((model, alanlar))
    return sonuc


def protected_field_labels() -> list[str]:
    """Arayüzde "hangi alanlar korunuyor" listesi (Türkçe, tekilleştirilmiş)."""
    etiketler: list[str] = []
    for model, _ in encrypted_field_map():
        for alan in crypto.encrypted_fields_of(model):
            etiket = str(getattr(alan, "verbose_name", alan.name))
            if etiket not in etiketler:
                etiketler.append(etiket)
    return etiketler


def _rewrite_rows() -> int:
    """Tüm şifreli alanları OKUYUP GERİ YAZAR (şifreler); yazılan satır sayısını döndürür.

    FİKİRDEŞTİR (idempotent): okuma daima düz metin verdiğinden ikinci koşu
    aynı sonucu üretir, çift şifreleme OLUŞAMAZ. Anahtar yüklü olmalıdır.
    """
    toplam = 0
    for model, alanlar in encrypted_field_map():
        # Soft-delete edilmiş satırlar da kapsanır: silinmiş öğrencinin adı
        # da kişisel veridir (`all_objects`).
        manager = getattr(model, "all_objects", model._default_manager)
        for nesne in manager.all().iterator(chunk_size=200):
            nesne.save(update_fields=list(alanlar))
            toplam += 1
    return toplam


def _write_fingerprint(value: str) -> None:
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.app_password_hash = value
    config.save(update_fields=["app_password_hash", "updated_at"])


def _stored_fingerprint() -> str:
    return SchoolConfig.load().app_password_hash


def _persons_exist() -> bool:
    """Kişi tablolarında (silinmişler dahil) satır var mı?"""
    return bool(Student.all_objects.exists() or Personnel.all_objects.exists())


# ---------------------------------------------------------------------------
# Kurtarma anahtarı
# ---------------------------------------------------------------------------
def generate_recovery_key() -> str:
    """Yazdırılabilir kurtarma anahtarı üretir (ör. `A1B2-C3D4-...`, 8 grup)."""
    ham = base64.b32encode(os.urandom(RECOVERY_KEY_BYTES)).decode("ascii").rstrip("=")
    return "-".join(
        ham[i : i + RECOVERY_GROUP_SIZE] for i in range(0, len(ham), RECOVERY_GROUP_SIZE)
    )


def normalize_recovery_key(value: str) -> str:
    """Kullanıcının yazdığı anahtarı normalleştirir (tire/boşluk, küçük harf, İ/ı, 0/1/8).

    Yalnız ASCII harf ve rakam kalır — ön yüzdeki `kurtarmaAnahtariniNormallestir`
    ile birebir aynı kural (iki taraf aynı örnek tablosuyla sınanır).
    """
    buyuk = value.strip().translate(_RECOVERY_TURKISH_I).upper()
    sade = "".join(ch for ch in buyuk if ch.isascii() and ch.isalnum())
    return sade.translate(_RECOVERY_FIXUPS)


def recovery_key_groups(value: str) -> list[str]:
    """Anahtarı dörtlü gruplara ayırır (çıktı ve ekranın ortak biçimi): ['ABCD', …]."""
    sade = normalize_recovery_key(value)
    return [sade[i : i + RECOVERY_GROUP_SIZE] for i in range(0, len(sade), RECOVERY_GROUP_SIZE)]


# ---------------------------------------------------------------------------
# Deneme gecikmesi
# ---------------------------------------------------------------------------
def _delay_after_failure() -> None:
    """Kademeli gecikme — klavye başındaki deneyene karşı; kalıcı kilit YOK."""
    global _failed_attempts
    gecikme = FAILURE_DELAYS[min(_failed_attempts, len(FAILURE_DELAYS) - 1)]
    _failed_attempts += 1
    if gecikme:
        time.sleep(gecikme)


def _reset_failures() -> None:
    global _failed_attempts
    _failed_attempts = 0


# ---------------------------------------------------------------------------
# Durum sorgusu
# ---------------------------------------------------------------------------
def is_password_set() -> bool:
    """Yönetici parolası kurulu mu? Fail-closed: dosya VAR **ya da** DB parmak izi dolu.

    Dosya varsa DB'ye gidilmez (her istekte çağrılır). Dosya yoksa parmak izi
    sorulur: dolu olması parolanın kurulduğunu, dosyanın ise KAYBOLDUĞUNU
    gösterir — program "parolasız"a dönmez.
    """
    if state_path().is_file():
        return True
    return bool(_stored_fingerprint())


def _state_file_usable(path: Path) -> bool:
    """Var olan güvenlik dosyası DEK'i açmaya yeter biçimde mi? (tek kural: backup_crypto)"""
    try:
        ham = path.read_bytes()
    except OSError:
        return False
    return parse_security_state(ham) is not None


def security_file_missing() -> bool:
    """Güvenlik dosyası kayıp mı? (GA-2 kayıp kilidi)

    İki hâl aynı kilide düşer:

    * dosya yok + DB'de parmak izi dolu (silinmiş ya da yeniden adlandırılmış);
    * dosya VAR ama kullanılamıyor: okunamıyor, boş, bozuk JSON ya da bölümleri
      eksik (`backup_crypto.is_usable_security_state` — günlük yedeğin başlık
      kuralıyla aynıdır). Böyle bir dosyayla kilit hiçbir parolayla açılmaz;
      olağan kilit ekranında bırakmak kullanıcıyı çıkışsız bırakırdı (durum ucu
      500, geri yükleme 423). Parmak izinden bağımsızdır (fail-closed: dosyanın
      neyi koruduğu bilinemez) ve DB'ye gitmez.

    Dosya varsa yalnız dosya okunur (her API isteğinde çağrılır; ~1 KB).
    """
    yol = state_path()
    if yol.is_file():
        return not _state_file_usable(yol)
    return bool(_stored_fingerprint())


def _encrypted_rows_exist() -> bool:
    """Şifreli alan taşıyan herhangi bir tabloda (silinmişler dahil) satır var mı?

    Liste elle tutulmaz (`encrypted_field_map`): F6'da gelen üyelik/ödünç
    tabloları da kendiliğinden kapsanır.
    """
    for model, _ in encrypted_field_map():
        manager = getattr(model, "all_objects", model._default_manager)
        if manager.exists():
            return True
    return False


#: Parola kurulurken alınan geçiş yedeğinin adı (`take_transition_backup("acilis")`).
#: `enable()` yalnız kişi tabloları boşken çalıştığı için bu yedek kişi verisi taşımaz.
_TRANSITION_BACKUP_PREFIX = "pre-parola-"
#: Yedek klasöründe veri taşıyabilen dosyalar: şifreli yedek ve (dönüştürülmemiş) eski düz yedek.
_DATA_BACKUP_SUFFIXES = (BACKUP_SUFFIX, ".sqlite3")


def _data_backups_exist() -> bool:
    """Yedek klasöründe kişi verisi taşıyabilecek bir yedek var mı?

    Parola kurulurken alınan geçiş yedeği (`pre-parola-*`) sayılmaz: o an kişi
    tabloları boştur. Hangi anahtarla şifrelendiğine bakılmaz — yedeğin varlığı
    "korunan veri olabilir" demektir (fail-closed).
    """
    dizin = backup_dir()
    if not dizin.is_dir():
        return False
    return any(
        yol.is_file()
        and yol.suffix in _DATA_BACKUP_SUFFIXES
        and not yol.name.startswith(_TRANSITION_BACKUP_PREFIX)
        for yol in dizin.iterdir()
    )


def state_reset_available() -> bool:
    """ "Güvenlik dosyasını sıfırla ve kuruluma dön" yolu açık mı? (F1-E, GA-2 eki)

    DÖRT koşul birden (biri eksikse yol görünmez, uç 409 döner):

    1. güvenlik dosyası VAR ama kullanılamıyor (boş, bozuk, bölümleri eksik —
       `security_file_missing` ile aynı kural). Dosya hiç yoksa ve parmak izi
       boşsa zaten "parola kurulmamış" hâlidir, sıfırlanacak bir şey yoktur;
    2. DB'de anahtar parmak izi BOŞ: şifreleme geçişi hiç tamamlanmamış, yani
       bu veritabanında o anahtarla şifrelenmiş kalıcı bir satır yoktur;
    3. şifreli alan taşıyan bütün tablolar (silinmişler dahil) BOŞ;
    4. yedek klasöründe veri taşıyabilen yedek YOK (`_data_backups_exist`).
       Veritabanı kaybolup boş yeniden oluştuğunda 2 ve 3 sağlanır ama eski
       kayıtlar yedeklerde durur; o zaman doğru yol yedekten geri yüklemedir.
       Sıfırlama yeni anahtarla yeni günlük yedek zinciri başlatırdı ve 14 günlük
       rotasyon eski anahtarla şifreli yedekleri sessizce silerdi.

    Bu koşullarda bozuk dosya korunacak hiçbir veriyi açmıyordur; kullanıcıyı
    yalnız dosyayı elle silebileceği bir çıkmazda bırakmak yerine dosya
    ARŞİVLENİR (silinmez) ve program ilk açılış hâline döner.
    """
    yol = state_path()
    if not yol.is_file() or _state_file_usable(yol):
        return False
    if _stored_fingerprint():
        return False
    if _encrypted_rows_exist():
        return False
    return not _data_backups_exist()


class StateResetNotAllowed(AppPasswordError):
    """Sıfırlama koşulları sağlanmıyor (görünüm 409 `sifirlama_uygun_degil` döner)."""


def reset_unusable_state() -> str:
    """Kullanılamayan güvenlik dosyasını arşivler, programı "parola kurulmamış" hâline döndürür.

    Yalnız `state_reset_available()` doğruyken çalışır; aksi hâlde
    `StateResetNotAllowed`. Dosya `guvenlik-arsiv-<damga>.json` adıyla kenara
    alınır (geri yüklemenin arşiv adıyla aynı desen); eski yedek açık anahtarı
    (`yedekleme.json`) da `yedekleme-arsiv-<damga>.json` olur — ilk açılışta
    ikisi de yoktur ve yeni parola kurulurken yenisi yazılır. Arşiv dosyasının
    adını döndürür.
    """
    if not state_reset_available():
        raise StateResetNotAllowed(RESET_NOT_ALLOWED_MESSAGE)
    damga = timezone.localtime().strftime("%Y-%m-%d-%H%M%S")
    yol = state_path()
    # Aynı saniyede geri yükleme ya da yenileme arşivi varsa üstüne yazılmaz.
    arsiv = _archive_target()
    yol.replace(arsiv)
    yedek_ayari = config_path(_data_dir())
    if yedek_ayari.is_file():
        yedek_ayari.replace(yedek_ayari.with_name(f"yedekleme-arsiv-{damga}.json"))
    crypto.unload_key()
    _reset_failures()
    logger.warning(
        "Kullanılamayan güvenlik dosyası arşivlendi (%s); kurulum yeniden başlar.", arsiv.name
    )
    return arsiv.name


def is_locked() -> bool:
    """Parola kurulu ve anahtar bellekte değil mi?"""
    return is_password_set() and not crypto.is_unlocked()


def require_password_set() -> None:
    """Yönetici parolası kurulmamışsa `PasswordRequired` (409 `parola_gerekli`) yükseltir.

    Kişi yazan uçların izin sınıfı (`permissions.RequiresAdminPassword`) ve
    kişi yazan servisler savunma derinliği için çağırır.
    """
    if not is_password_set():
        raise PasswordRequired()


def status() -> dict[str, Any]:
    """Arayüzün okuduğu durum özeti (sır içermez). HİÇ hata yükseltmez.

    Kullanılamayan güvenlik dosyası `security_file_missing` olarak raporlanır
    (arayüz kayıp ekranını ve geri yükleme kartını gösterir); durum ucu 500
    dönseydi arayüz kilit de kayıp da gösteremezdi.
    """
    kayip = security_file_missing()
    state: dict[str, Any] | None = None
    if not kayip:
        try:
            state = read_state()
        except AppPasswordError:  # iki okuma arasında bozulduysa (yarış) — yine kayıp
            kayip = True
    kurulu = state is not None or kayip
    gecis = str(state.get("gecis", TRANSITION_DONE)) if state else TRANSITION_DONE
    return {
        "password_set": kurulu,
        "locked": kurulu and not crypto.is_unlocked(),
        "security_file_missing": kayip,
        # Kayıp ekranındaki "sıfırla ve kuruluma dön" yolu (yalnız korunan veri yokken).
        "reset_available": kayip and state_reset_available(),
        "transition_pending": state is not None and gecis != TRANSITION_DONE,
        "transition": gecis if state is not None and gecis != TRANSITION_DONE else "",
        # Kurtarma anahtarının saklandığı doğrulandı mı? (damga; kurulum kapısı)
        "recovery_key_confirmed": _recovery_confirmed_in(state),
        "protected_fields": protected_field_labels(),
    }


def _recovery_confirmed_in(state: dict[str, Any] | None) -> bool:
    """Durumun kurtarma bölümünde doğrulama damgası var mı? Hata yükseltmez."""
    if not isinstance(state, dict):
        return False
    bolum = state.get("kurtarma")
    if not isinstance(bolum, dict):
        return False
    damga = bolum.get(RECOVERY_CONFIRMED_FIELD)
    return isinstance(damga, str) and bool(damga)


def recovery_key_confirmed() -> bool:
    """Kurtarma anahtarının saklandığı doğrulandı mı? HİÇ hata yükseltmez.

    `setup/status/` (sağlık denetimi ucu) ve `setup/complete/` kapısı sorar:
    yalnız güvenlik dosyası okunur (~1 KB), DB'ye gidilmez. Dosya yok, okunamıyor
    ya da damga yoksa yanlış döner (fail-closed: kurulum tamamlanmaz).
    """
    try:
        return _recovery_confirmed_in(read_state())
    except AppPasswordError:
        return False


# ---------------------------------------------------------------------------
# Kurma / değiştirme / doğrulama
# ---------------------------------------------------------------------------
def _validate_password(password: str) -> str:
    parola = password.strip()
    if len(parola) < MIN_PASSWORD_LENGTH:
        raise AppPasswordError(f"Parola en az {MIN_PASSWORD_LENGTH} karakter olmalıdır.")
    return parola


def _build_state(data_key: bytes, *, password: str, recovery_key: str) -> dict[str, Any]:
    kdf = crypto.DEFAULT_KDF
    parola_tuz = crypto.new_salt()
    kurtarma_tuz = crypto.new_salt()
    return {
        "surum": STATE_VERSION,
        "olusturma": timezone.localtime().isoformat(timespec="seconds"),
        "kdf": kdf.to_dict(),
        "parola": {
            "salt": base64.b64encode(parola_tuz).decode("ascii"),
            "sarmal": crypto.wrap_key(
                data_key,
                wrapping_key=crypto.derive_key(password, salt=parola_tuz, params=kdf),
            ),
        },
        "kurtarma": {
            "salt": base64.b64encode(kurtarma_tuz).decode("ascii"),
            "sarmal": crypto.wrap_key(
                data_key,
                wrapping_key=crypto.derive_key(
                    normalize_recovery_key(recovery_key), salt=kurtarma_tuz, params=kdf
                ),
            ),
        },
        "gecis": TRANSITION_ENCRYPTING,
    }


def enable(*, password: str) -> str:
    """Yönetici parolasını kurar; TEK SEFERLİK kurtarma anahtarını döndürür.

    Yalnız ilk kurulumda çalışır (§6.3-4): güvenlik dosyası yokken, DB'de
    parmak izi boşken VE kişi tabloları (silinmişler dahil) boşken. Parmak izi
    doluysa ya parola zaten kurulmuştur ya da güvenlik dosyası kaybolmuştur;
    ikisinde de yeni bir anahtar üretmek eski kayıtları okunamaz bırakırdı.

    Dönen kurtarma anahtarı hiçbir yerde AÇIK saklanmaz — çağıran onu kullanıcıya
    bir kez gösterir (yazdırma/indirme), sonrasında yalnız sarmalı kalır.
    """
    if read_state() is not None:
        raise AppPasswordError("Yönetici parolası zaten kurulu.")
    if _stored_fingerprint():
        raise AppPasswordError(
            "Yönetici parolası daha önce kurulmuş, ancak güvenlik dosyası (guvenlik.json) "
            "bulunamadı. Yeni parola kurulamaz; dosyanın yedeğini veri klasörüne geri koyun "
            "ya da bir yedekten geri yükleyin."
        )
    if _persons_exist():
        raise AppPasswordError(
            "Kayıtlı öğrenci, öğretmen ya da diğer personel varken yönetici parolası "
            "kurulamaz. Parola, kurulum sihirbazının ilk adımında, kişi kaydından önce kurulur."
        )
    parola = _validate_password(password)

    veri_anahtari = crypto.new_data_key()
    kurtarma = generate_recovery_key()
    state = _build_state(veri_anahtari, password=parola, recovery_key=kurtarma)
    # Sıra kritik: dosya ÖNCE yazılır. Ters sırada, parmak izi ile dosya yazımı
    # arasındaki bir kesinti anahtarı yok ederdi (veri kaybı).
    _write_state(state)
    yedek_ayar_yolu = _data_dir() / "yedekleme.json"
    onceki_yedek_ayari = yedek_ayar_yolu.read_bytes() if yedek_ayar_yolu.is_file() else None
    try:
        ensure_public_config(_data_dir(), veri_anahtari, replace=True)
        encrypt_legacy_backups(backup_dir(), _data_dir())
        take_transition_backup("acilis")
    except Exception:  # noqa: BLE001 - başarısız kurulumun iki dosyası birlikte geri alınır
        state_path().unlink(missing_ok=True)
        if onceki_yedek_ayari is None:
            yedek_ayar_yolu.unlink(missing_ok=True)
        else:
            yedek_ayar_yolu.write_bytes(onceki_yedek_ayari)
        raise

    crypto.load_key(veri_anahtari)
    _run_encrypt_pass(veri_anahtari)
    state["gecis"] = TRANSITION_DONE
    _write_state(state)
    _reset_failures()
    logger.info("Yönetici parolası kuruldu.")
    return kurtarma


def _run_encrypt_pass(data_key: bytes) -> int:
    """Şifreleme geçişi — satırlar ve parmak izi TEK işlemde yazılır."""
    with transaction.atomic():
        yazilan = _rewrite_rows()
        _write_fingerprint(crypto.key_fingerprint(data_key))
    return yazilan


def unlock(*, password: str) -> None:
    """Parolayla kilidi açar; yarım kalmış geçiş varsa tamamlar."""
    state = _require_state()
    veri_anahtari = _unwrap_with_password(state, password)
    _adopt_key(state, veri_anahtari)


def verify_password(password: str) -> None:
    """Parolayı, BELLEKTEKİ anahtara karşı doğrular (kip yükseltmesi, `app/quit/`).

    Sarmal çözülür ve çıkan DEK'in parmak izi yüklü anahtarınkiyle
    karşılaştırılır. Böylece başka bir kurulumdan getirilmiş (parolası bilinen)
    bir `guvenlik.json` ile yükseltme yapılamaz. Yanlışsa `AppPasswordError`
    ("Parola hatalı.") + kademeli gecikme. Anahtar bellekte değilse (kilitli)
    doğrulama yapılamaz; çağıran önce kilidi açtırmalıdır.
    """
    _check_password(_require_state(), password)


@sensitive_variables("password", "veri_anahtari")
def _check_password(state: dict[str, Any], password: str) -> bytes:
    """Parolayı verilen duruma VE bellekteki anahtara karşı doğrular; DEK'i döndürür."""
    aktif = crypto.active_fingerprint()
    if aktif is None:
        raise AppPasswordError(_LOCKED_MESSAGE)
    veri_anahtari = _unwrap_with_password(state, password)
    if crypto.key_fingerprint(veri_anahtari) != aktif:
        _delay_after_failure()
        raise AppPasswordError(_WRONG_PASSWORD_MESSAGE)
    _reset_failures()
    return veri_anahtari


@sensitive_variables("recovery_key", "veri_anahtari")
def _check_recovery_key(state: dict[str, Any], recovery_key: str) -> None:
    """Kurtarma anahtarını verilen duruma VE bellekteki anahtara karşı doğrular."""
    aktif = crypto.active_fingerprint()
    if aktif is None:
        raise AppPasswordError(_LOCKED_MESSAGE)
    veri_anahtari = _unwrap_with_recovery(state, recovery_key)
    if crypto.key_fingerprint(veri_anahtari) != aktif:
        _delay_after_failure()
        raise AppPasswordError(_WRONG_RECOVERY_MESSAGE)
    _reset_failures()


@sensitive_variables("recovery_key")
def verify_recovery_key(recovery_key: str) -> list[str]:
    """Kurtarma anahtarını doğrular; anahtarın dörtlü gruplarını döndürür (E14 çıktısı).

    İki denetim: anahtar `guvenlik.json`'daki KURTARMA SARMALINI açmalı (yanlış
    yazılmış anahtarın kâğıda basılmasını önler) VE çıkan DEK bellekteki
    anahtarla aynı olmalı (başka kurulumun dosyasıyla doğrulama yapılamaz;
    `verify_password` ile aynı kural). Yanlışsa `AppPasswordError` + kademeli
    gecikme — yanlış anahtar denemesi kaba kuvvete kapı olmasın. Kilitliyken
    doğrulama yapılmaz (kilit ara katmanı zaten 423 ile keser).

    Anahtar hiçbir iletiye, günlüğe ya da istisnaya yazılmaz.
    """
    _check_recovery_key(_require_state(), recovery_key)
    return recovery_key_groups(recovery_key)


@sensitive_variables("recovery_key")
def confirm_recovery_key(recovery_key: str) -> None:
    """Anahtarın saklandığını doğrular ve damgayı `guvenlik.json`'a yazar (F1 eki, karar 2).

    Sihirbaz (ve Ayarlar → Güvenlik) iki grubu istemcide denetledikten sonra
    TAM anahtarı gönderir. Doğrulama `verify_recovery_key` ile aynı kuraldır:
    anahtar kurtarma sarmalını açmalı ve çıkan DEK bellekteki anahtar olmalı;
    yanlışsa `AppPasswordError` + kademeli gecikme, damga yazılmaz. Kilitliyken
    doğrulama yapılmaz (kilit ara katmanı da 423 ile keser).

    Doğrulama ile yazım AYNI okunmuş durum üzerinde, kilit altında yapılır:
    arada bir yenileme olsaydı eski anahtarın damgası yeni sarmala yazılırdı.
    Damga fikirdeştir: doğrulanmış anahtar yeniden doğrulanınca zaman güncellenir.
    """
    with _state_lock:
        state = _require_state()
        _check_recovery_key(state, recovery_key)
        bolum = state.get("kurtarma")
        if not isinstance(bolum, dict):  # pragma: no cover — sarmal açıldıysa bölüm vardır
            raise AppPasswordError("Güvenlik dosyasının kurtarma bölümü okunamadı.")
        bolum[RECOVERY_CONFIRMED_FIELD] = timezone.localtime().isoformat(timespec="seconds")
        _write_state(state)
    logger.info("Kurtarma anahtarının saklandığı doğrulandı.")


@sensitive_variables("password", "veri_anahtari", "yeni_anahtar")
def renew_recovery_key(*, password: str) -> str:
    """Kurtarma anahtarını yeniler; YENİ anahtarı döndürür (yanıtta BİR KEZ gösterilir).

    Yalnız kilit açıkken: parola `verify_password` kuralıyla (sarmal + bellekteki
    anahtarın parmak izi) doğrulanır; yanlışsa "Parola hatalı." + kademeli
    gecikme ve hiçbir dosya değişmez. Sonra:

    1. güncel `guvenlik.json` `guvenlik-arsiv-<damga>.json` olarak KOPYALANIR
       (asıl dosya yerinde kalır: kesinti dosyayı kayıp hâline düşürmez);
    2. aynı DEK YENİ anahtar ve YENİ tuzla sarmalanır; parola bölümü, KDF
       parametreleri ve geçiş damgası olduğu gibi kalır; kurtarma bölümü
       DAMGASIZ yazılır (yeni anahtar yeniden doğrulanana dek kurulum kapısı ve
       Güvenlik ekranı uyarır);
    3. yeni durum atomik yazılır.

    DEK değişmez: kayıtlar, kör indeks ve yedek anahtarı (`yedekleme.json`)
    aynen kalır, kilit açılışı (anahtar dönemi) değişmez — kip etkilenmez.
    Anahtar hiçbir günlüğe, iletiye ya da istisnaya yazılmaz.
    """
    with _state_lock:
        state = _require_state()
        veri_anahtari = _check_password(state, password)
        yeni_anahtar = generate_recovery_key()
        kdf = crypto.KdfParams.from_dict(dict(state.get("kdf", {})))
        tuz = crypto.new_salt()
        yeni_durum = dict(state)
        yeni_durum["kurtarma"] = {
            "salt": base64.b64encode(tuz).decode("ascii"),
            "sarmal": crypto.wrap_key(
                veri_anahtari,
                wrapping_key=crypto.derive_key(
                    normalize_recovery_key(yeni_anahtar), salt=tuz, params=kdf
                ),
            ),
        }
        arsiv = _copy_state_to_archive()
        _write_state(yeni_durum)
    logger.info(
        "Kurtarma anahtarı yenilendi; önceki güvenlik dosyası %s olarak saklandı.", arsiv.name
    )
    return yeni_anahtar


def unlock_with_recovery(*, recovery_key: str, new_password: str) -> None:
    """Kurtarma anahtarıyla açar ve YENİ parola belirler (parola sıfırlama).

    Kurtarma sarmalı DEĞİŞMEZ — aynı yazdırılmış anahtar geçerli kalır. Yeni bir
    anahtar üretmek, kullanıcının elindeki kâğıdı sessizce geçersizleştirirdi.
    Anahtar yalnız kullanıcı isteyince yenilenir (`renew_recovery_key`).
    """
    with _state_lock:
        state = _require_state()
        parola = _validate_password(new_password)
        veri_anahtari = _unwrap_with_recovery(state, recovery_key)

        kdf = crypto.KdfParams.from_dict(dict(state.get("kdf", {})))
        tuz = crypto.new_salt()
        state["parola"] = {
            "salt": base64.b64encode(tuz).decode("ascii"),
            "sarmal": crypto.wrap_key(
                veri_anahtari, wrapping_key=crypto.derive_key(parola, salt=tuz, params=kdf)
            ),
        }
        _write_state(state)
        _adopt_key(state, veri_anahtari)
    logger.info("Kurtarma anahtarıyla giriş yapıldı; parola yenilendi.")


def change_password(*, current_password: str, new_password: str) -> None:
    """Parolayı değiştirir. Veri YENİDEN ŞİFRELENMEZ — yalnız sarmal yenilenir."""
    with _state_lock:
        state = _require_state()
        yeni = _validate_password(new_password)
        veri_anahtari = _unwrap_with_password(state, current_password)

        kdf = crypto.KdfParams.from_dict(dict(state.get("kdf", {})))
        tuz = crypto.new_salt()
        state["parola"] = {
            "salt": base64.b64encode(tuz).decode("ascii"),
            "sarmal": crypto.wrap_key(
                veri_anahtari, wrapping_key=crypto.derive_key(yeni, salt=tuz, params=kdf)
            ),
        }
        _write_state(state)
        _adopt_key(state, veri_anahtari)
    logger.info("Yönetici parolası değiştirildi.")


def resume_pending(*, force: bool = False) -> dict[str, Any]:
    """Yarım kalmış şifreleme geçişini tamamlar. Anahtarın yüklü olması gerekir.

    `force=True`: damga "tamam" dese bile şifreleme geçişi YENİDEN koşulur.
    Geçiş fikirdeş olduğu için bu güvenlidir ve destek senaryosunun elidir —
    örneğin satırların bir bölümü elle düz metne dönmüşse
    (`manage.py app_password resume --force`).
    """
    with _state_lock:
        state = read_state()
        if state is None:
            return {"resumed": False, "rows": 0, "transition": ""}
        if not crypto.is_unlocked():
            raise AppPasswordError("Geçişi tamamlamak için önce yönetici parolasıyla açın.")

        gecis = str(state.get("gecis", TRANSITION_DONE))
        parmak = crypto.active_fingerprint() or ""
        if force or gecis != TRANSITION_DONE or _stored_fingerprint() != parmak:
            satir = _run_encrypt_pass(_require_raw_key())
            state["gecis"] = TRANSITION_DONE
            _write_state(state)
            logger.info("Şifreleme geçişi tamamlandı (%d kayıt).", satir)
            return {"resumed": True, "rows": satir, "transition": TRANSITION_ENCRYPTING}
        return {"resumed": False, "rows": 0, "transition": ""}


def lock() -> None:
    """Anahtarı bellekten düşürür. Parola kurulu değilse bir şey değişmez."""
    crypto.unload_key()


# ---------------------------------------------------------------------------
# İç yardımcılar
# ---------------------------------------------------------------------------
def _require_raw_key() -> bytes:
    ham = crypto.active_key()
    if ham is None:  # pragma: no cover — çağrı yerleri kilidin açık olduğunu doğrular
        raise AppPasswordError("Veri anahtarı bellekte değil; yönetici parolasıyla yeniden açın.")
    return ham


def _adopt_key(state: dict[str, Any], data_key: bytes) -> None:
    """Anahtarı yükler, DB eşleşmesini doğrular, gerekiyorsa geçişi tamamlar."""
    parmak = crypto.key_fingerprint(data_key)
    kayitli = _stored_fingerprint()
    gecis = str(state.get("gecis", TRANSITION_DONE))
    if kayitli and kayitli != parmak:
        raise AppPasswordError(
            "Bu güvenlik dosyası bu veritabanına ait değil (anahtar eşleşmiyor). "
            "Doğru guvenlik.json dosyasını veri klasörüne koyup yeniden deneyin; "
            "yanlış dosyayla açmak kayıtları okunamaz hâle getirir."
        )
    crypto.load_key(data_key)
    # replace=True (birleşme incelemesi): bu noktada DEK, DB parmak izine karşı
    # KANITLANDI — otorite dosya değil anahtardır. Bayat/uyumsuz yedekleme.json
    # (ör. çapraz-DEK geri yükleme artığı) burada sessizce onarılır; replace=False
    # olsaydı kilit açma her denemede "anahtar eşleşmiyor" hatasıyla düşerdi.
    ensure_public_config(_data_dir(), data_key, replace=True)
    encrypt_legacy_backups(backup_dir(), _data_dir())
    _reset_failures()
    if gecis != TRANSITION_DONE or not kayitli:
        resume_pending()


def _unwrap_with_password(state: dict[str, Any], password: str) -> bytes:
    bolum = dict(state.get("parola", {}))
    return _unwrap(bolum, state, password, _WRONG_PASSWORD_MESSAGE)


def _unwrap_with_recovery(state: dict[str, Any], recovery_key: str) -> bytes:
    bolum = dict(state.get("kurtarma", {}))
    return _unwrap(bolum, state, normalize_recovery_key(recovery_key), _WRONG_RECOVERY_MESSAGE)


def _unwrap(bolum: dict[str, Any], state: dict[str, Any], secret: str, hata_mesaji: str) -> bytes:
    tuz_b64 = str(bolum.get("salt", ""))
    sarmal = str(bolum.get("sarmal", ""))
    if not tuz_b64 or not sarmal:
        raise AppPasswordError(
            "Güvenlik dosyası eksik (tuz veya sarmal yok). Öbür yolu (yönetici parolası "
            "ya da kurtarma anahtarı) deneyin ya da bir yedekten geri yükleyin."
        )
    kdf = crypto.KdfParams.from_dict(dict(state.get("kdf", {})))
    sarmalama = crypto.derive_key(secret, salt=base64.b64decode(tuz_b64), params=kdf)
    try:
        return crypto.unwrap_key(sarmal, wrapping_key=sarmalama)
    except Exception as exc:  # noqa: BLE001 — InvalidToken ve biçim hataları aynı yanıta çıkar
        _delay_after_failure()
        raise AppPasswordError(hata_mesaji) from exc
