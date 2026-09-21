"""Zorunlu yönetici parolası — anahtar tutucu, Argon2id türetme, şifreli alanlar, kör indeks.

Tasarım §4.3, §6.3 (U9, T14). SQLCipher ve "kapanışta dosyayı şifrele"
reddedildi; seçilen yol OYS'nin (Okul Yönetim Sistemi) sahada test edilmiş
`shared/fields.py` Fernet alan şifrelemesidir. Bu dosya o alanı bu programın
gerçeklerine uyarlar. OYS'den FARKLAR:

1. **Anahtar ayardan değil, ÇALIŞMA ZAMANINDAN gelir.** OYS'de anahtar
   `settings.FIELD_ENCRYPTION_KEY` (.env) ile sabittir; burada yönetici
   parolasından (ya da kurtarma anahtarından) çözülen veri anahtarıdır (DEK) ve
   programın kilidi açılana kadar YOKTUR. Bu yüzden `lru_cache`'li Fernet
   KULLANILAMAZ — anahtar süreç ömrü içinde yüklenir, boşaltılır, değişir.
2. **Parolasız kip YOKTUR (fail-closed, §6.3-3).** Yönetici parolası
   zorunludur; kurulum sihirbazının ilk adımıdır ve parola kurulmadan kişi
   yazan her uç 409 döner. Anahtar bellekte değilken `EncryptedTextField`
   boş olmayan bir değeri YAZMAZ, `KeyMissingError` yükseltir: kilitliyken ya
   da parola hiç kurulmamışken kişi adı düz metin olarak diske düşemez. KS'deki
   "parolasız kipte alanlar DÜZ yazılır" dalı ve onun geçiş aracı
   (`plaintext_writes`) F1'de söküldü (§6.3-6).
3. **Kör indeks VARDIR (T14 — KS'nin "BLIND INDEX YOKTUR" kararından BİLİNÇLİ
   sapma).** Okul no ve kart no da şifrelendiği için (U9) kart okutma, e-Okul
   eşleştirmesi ve iptal kart denetimi tam eşleşmeyle `blind_index()`
   değerinden yapılır; teklik kısıtı indekse konur. Anahtar DEK'ten HKDF ile
   türediği için parola değişimi indeksi bozmaz. Normalleştirme çağıranın
   işidir (ör. `apps/okul/normalize.py`); bu modül yalnız HMAC'i hesaplar.

ANAHTARIN BELLEKTEKİ YERİ: anahtar süreç genelinde, bu modülün `_holder`
nesnesinde tutulur ve kilit açıldıktan sonra kilitlenene dek bellekte kalır.
Gerekçe: yönetim yüzeyi yalnız 127.0.0.1'de ve tek masaya hizmet eder
(`desktop/session_guard.py`); anahtarı bağlayacağımız bir kullanıcı oturumu
yoktur, masadaki kişi ayrımı kiple yapılır (§4.4). Anahtarı her istekte yeniden
türetmek Argon2id maliyetini (~0,2 sn) her tıklamaya yayardı. Kilitleme =
programı kapatmak VEYA açık "Kilitle" eylemi (`POST /security/lock/` →
`unload_key()`). Her yükleme ve boşaltma `key_epoch()` sayacını artırır; kip
katmanı yeni bir kilit açılışını buradan anlar. Anahtar diske YAZILMAZ,
loglanmaz, hata mesajında yankılanmaz.

ŞİFRELİ ALANDA DB ARAMASI YOKTUR (U9): Fernet her şifrelemede farklı token
ürettiği için şifreli alan üzerinde DB tarafı filtre/LIKE/sıralama çalışmaz
(`Student.objects.filter(first_name=…)` daima boş döner). Ad temelli arama,
sıralama ve teklik selector katmanında Python ile; kimlik eşleştirmesi kör
indeksle yapılır.
"""

from __future__ import annotations

import base64
import hmac
import secrets
import threading
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, cast

from argon2.low_level import Type as Argon2Type
from argon2.low_level import hash_secret_raw
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.db import models

# Veri anahtarı (DEK) uzunluğu — Fernet 32 baytlık anahtar ister.
KEY_BYTES = 32
# Argon2id tuzu (parola başına ve kurtarma anahtarı başına ayrı üretilir).
SALT_BYTES = 16


@dataclass(frozen=True)
class KdfParams:
    """Argon2id maliyet parametreleri.

    Varsayılan, RFC 9106'nın "düşük bellek" profilidir (64 MiB / t=3 / p=4):
    okul bilgisayarında ~0,2 sn sürer, ama çalınmış bir veri klasörüne karşı
    kaba kuvvet denemesini de aynı oranda pahalılaştırır. Parametreler
    `guvenlik.json` içinde SAKLANIR; ileride artırılırsa eski dosyalar kendi
    parametreleriyle açılmaya devam eder (ileri uyumluluk).
    """

    time_cost: int = 3
    memory_cost: int = 65536  # KiB → 64 MiB
    parallelism: int = 4

    def to_dict(self) -> dict[str, int]:
        return {
            "time_cost": self.time_cost,
            "memory_cost": self.memory_cost,
            "parallelism": self.parallelism,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KdfParams:
        return cls(
            time_cost=int(data.get("time_cost", cls.time_cost)),
            memory_cost=int(data.get("memory_cost", cls.memory_cost)),
            parallelism=int(data.get("parallelism", cls.parallelism)),
        )


# Modül düzeyi varsayılan — testler ucuz profile indirir (Argon2 kasten yavaştır).
DEFAULT_KDF = KdfParams()


# ---------------------------------------------------------------------------
# Anahtar türetme ve sarmalama (zarf şifreleme)
# ---------------------------------------------------------------------------
# Neden ZARF (envelope) şifreleme? Kurtarma anahtarı şartı bunu ZORUNLU kılar:
# aynı veriyi hem parolayla hem kurtarma anahtarıyla açabilmek için, alanları
# şifreleyen anahtar (DEK) ikisinden de BAĞIMSIZ olmalı ve iki ayrı sarmalda
# saklanmalıdır. Yan faydaları:
#   * Parola değişimi veriyi YENİDEN ŞİFRELEMEZ — yalnız sarmal değişir (anlık,
#     yarıda kalma riski yok).
#   * DEK hiç değişmediği için ESKİ YEDEKLER (`gunluk-*.sqlite3`) parola
#     değiştikten sonra da açılabilir kalır.


def new_data_key() -> bytes:
    """Rastgele veri anahtarı (DEK) üretir."""
    return secrets.token_bytes(KEY_BYTES)


def new_salt() -> bytes:
    """Rastgele Argon2id tuzu üretir."""
    return secrets.token_bytes(SALT_BYTES)


def derive_key(secret: str, *, salt: bytes, params: KdfParams | None = None) -> bytes:
    """Parola/kurtarma anahtarından Argon2id ile 32 baytlık sarmalama anahtarı türetir."""
    kdf = params or DEFAULT_KDF
    return hash_secret_raw(
        secret=secret.encode("utf-8"),
        salt=salt,
        time_cost=kdf.time_cost,
        memory_cost=kdf.memory_cost,
        parallelism=kdf.parallelism,
        hash_len=KEY_BYTES,
        type=Argon2Type.ID,
    )


def _fernet_for(raw_key: bytes) -> Fernet:
    """Ham 32 bayttan Fernet örneği (Fernet base64 kodlu anahtar ister)."""
    return Fernet(base64.urlsafe_b64encode(raw_key))


def wrap_key(data_key: bytes, *, wrapping_key: bytes) -> str:
    """DEK'i sarmalar (şifreler). Dönen metin `guvenlik.json` içinde saklanır."""
    return _fernet_for(wrapping_key).encrypt(data_key).decode("ascii")


def unwrap_key(wrapped: str, *, wrapping_key: bytes) -> bytes:
    """Sarmalı çözer. Yanlış parola/kurtarma anahtarında `InvalidToken` yükselir.

    AYRI BİR "doğrulama hash'i" TUTULMAZ: Fernet token'ı kimlik doğrulamalıdır
    (HMAC), yani sarmalın başarıyla çözülmesi parolanın doğruluğunun kanıtıdır.
    Ayrıca bir parola özeti saklamak, o özeti çevrimdışı kırma denemesine hedef
    yapardı — az sır, az yüzey.
    """
    return _fernet_for(wrapping_key).decrypt(wrapped.encode("ascii"))


def key_fingerprint(data_key: bytes) -> str:
    """Veri anahtarının tek yönlü parmak izi (DB ↔ güvenlik dosyası eşleşmesi için).

    `SchoolConfig.app_password_hash` alanına yazılır. Parolanın özeti DEĞİLDİR:
    DB kopyaları (yedekler) okul dışına çıkabilir, içlerinde parola özeti
    bulunması çevrimdışı kaba kuvvete davetiye olurdu.
    """
    return "v1:" + hmac.new(data_key, b"kd-anahtar-parmak-izi", sha256).hexdigest()


# Kör indeks anahtarının HKDF bağlamı (tasarım §6.3, T14). Değişirse bütün
# kör indeks sütunları yeniden hesaplanmalıdır — sabit, sürüm ekiyle değişir.
BLIND_INDEX_INFO = b"kd-kor-indeks"


def _derive_blind_index_key(data_key: bytes) -> bytes:
    """DEK'ten kör indeks HMAC anahtarı: HKDF-SHA256(salt=None, info="kd-kor-indeks")."""
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=BLIND_INDEX_INFO).derive(
        data_key
    )


class KeyMissingError(RuntimeError):
    """Veri anahtarı bellekte değilken şifreli alana boş olmayan değer yazılmak istendi.

    Fail-closed (§6.3-3): parola kurulmamışken ya da program kilitliyken kişi
    verisi düz metin olarak diske düşmez, işlem bu hatayla durur.
    `shared.exceptions.kd_exception_handler` bunu 409 `parola_gerekli`
    yanıtına çevirir (parola kuruluysa kilitli durum zaten ara katmanda 423
    ile kesilir).
    """

    def __init__(self, message: str = "Veri anahtarı bellekte değil.") -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Süreç-geneli anahtar tutucu
# ---------------------------------------------------------------------------
class _KeyHolder:
    """Çalışma zamanı anahtar durumu (süreç geneli, iş parçacığı güvenli).

    `waitress` istekleri birden çok iş parçacığında karşılar; durum tek masaya
    ait olduğu için süreç geneli tutulur, kilitle korunur. Kör indeks anahtarı
    yüklemede BİR KEZ türetilir ve anahtarla birlikte düşer.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._fernet: Fernet | None = None
        self._raw: bytes | None = None
        self._blind_key: bytes | None = None
        self._epoch = 0

    def load(self, raw_key: bytes) -> None:
        blind_key = _derive_blind_index_key(raw_key)
        fernet = _fernet_for(raw_key)
        with self._lock:
            self._raw = raw_key
            self._fernet = fernet
            self._blind_key = blind_key
            self._epoch += 1

    def unload(self) -> None:
        with self._lock:
            self._raw = None
            self._fernet = None
            self._blind_key = None
            self._epoch += 1

    @property
    def unlocked(self) -> bool:
        return self._fernet is not None

    @property
    def epoch(self) -> int:
        return self._epoch

    def fingerprint(self) -> str | None:
        raw = self._raw
        return key_fingerprint(raw) if raw is not None else None

    def raw(self) -> bytes | None:
        return self._raw

    def fernet(self) -> Fernet | None:
        return self._fernet

    def blind_key(self) -> bytes | None:
        return self._blind_key


_holder = _KeyHolder()


def load_key(raw_key: bytes) -> None:
    """Veri anahtarını belleğe alır (kilidi açar); `key_epoch()` artar."""
    _holder.load(raw_key)


def unload_key() -> None:
    """Anahtarı bellekten düşürür (kilitler); `key_epoch()` artar. Diske hiçbir şey yazılmaz."""
    _holder.unload()


def is_unlocked() -> bool:
    """Veri anahtarı bellekte mi?"""
    return _holder.unlocked


def key_epoch() -> int:
    """Her `load_key` ve `unload_key` çağrısında artan süreç içi sayaç.

    Kip katmanı (`apps/okul/kip.py`) gördüğü son değeri saklar; değer
    değişmişse ve anahtar yüklüyse bu yeni bir kilit açılışıdır (yönetici kipi,
    sayaçlar sıfırdan).
    """
    return _holder.epoch


def active_fingerprint() -> str | None:
    """Yüklü anahtarın parmak izi; anahtar yoksa None."""
    return _holder.fingerprint()


def active_key() -> bytes | None:
    """Yüklü veri anahtarı (ham). YALNIZ geçiş aracı içindir; asla loglanmaz/döndürülmez."""
    return _holder.raw()


def blind_index(normalized: str) -> str:
    """Kör indeks: `HMAC-SHA256(HKDF(DEK, info="kd-kor-indeks"), değer)` (64 onaltılık hane).

    Belirlenimcidir: aynı DEK ve aynı değer daima aynı indeksi verir; bu yüzden
    tam eşleşme ve teklik kısıtı DB'de çalışır. Normalleştirme ÇAĞIRANIN
    işidir (okul no, kart no için ayrı kurallar vardır). Boş dize `""` döner
    ("veri yok" hâli DB'de de boş görünür, kısmi teklik kısıtları buna
    dayanır). Anahtar bellekte değilse `KeyMissingError`.
    """
    if normalized == "":
        return ""
    key = _holder.blind_key()
    if key is None:
        raise KeyMissingError("Kör indeks için veri anahtarı bellekte değil.")
    return hmac.new(key, normalized.encode("utf-8"), sha256).hexdigest()


# ---------------------------------------------------------------------------
# Model alanları
# ---------------------------------------------------------------------------
class EncryptedTextField(models.TextField):  # type: ignore[type-arg]  # Any davranışı korunur
    """Fernet ile şifreli saklanan metin alanı; anahtar yokken yazmaz (fail-closed).

    Python tarafında daima düz metin (str) gibi davranır. DB sütunu TEXT'tir,
    içerik base64 Fernet token'ıdır. Boş dize şifrelenmez.

    KİLİTLİYKEN OKUMA: `from_db_value` çözemediği değeri OLDUĞU GİBİ döndürür
    (token okunamaz ama patlamaz). Aynı tolerans, yarım kalmış bir şifreleme
    geçişinden (elektrik kesintisi) kalan düz satırların okunmasını da sağlar;
    geçiş kaldığı yerden tamamlanır (`app_password.resume_pending`).
    """

    description = "Yönetici parolasının veri anahtarıyla Fernet ile şifrelenen metin alanı"

    def get_prep_value(self, value: Any) -> str | None:
        """Python değeri → DB'ye yazılacak şifreli metin; anahtar yoksa `KeyMissingError`."""
        if value is None:
            return None
        text = str(value)
        # Boş dize ŞİFRELENMEZ: "veri yok" hâli DB'de de boş görünmeli — kısmi
        # tekillik kısıtları ve `blank=True` semantiği buna dayanır.
        if text == "":
            return ""
        fernet = _holder.fernet()
        if fernet is None:
            # Fail-closed (§6.3-3): düz metin yazmak yerine dur.
            raise KeyMissingError()
        return fernet.encrypt(text.encode("utf-8")).decode("ascii")

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> str | None:
        """DB'den okunan metin → düz metin (token ise çözülür)."""
        if value is None or value == "":
            return cast("str | None", value)
        fernet = _holder.fernet()
        if fernet is None:
            # Kilitli: token çözülemez, olduğu gibi döner (okunamaz ama patlamaz).
            return cast("str | None", value)
        try:
            return fernet.decrypt(str(value).encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError):
            # Yarım kalmış geçişten düz satır veya anahtar uyuşmazlığı.
            # UnicodeEncodeError: Fernet token'ı daima ASCII'dir; Türkçe harf
            # içeren değer tanım gereği düz metindir (OYS Tur 522 dersi).
            return cast("str | None", value)


class EncryptedCharField(EncryptedTextField):
    """CharField arayüzlü şifreli alan (form/serializer `max_length` doğrulaması için)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Şifreli token düz metinden uzundur → DB sütunu TEXT kalır; max_length
        # YALNIZ doğrulama amaçlıdır. Atama super SONRASINDA: `Field.__init__`
        # kendi (None) değeriyle ezer (OYS F52 dersi).
        max_length = kwargs.pop("max_length", None)
        super().__init__(*args, **kwargs)
        self.max_length = max_length

    def deconstruct(self) -> tuple[str, str, list[Any], dict[str, Any]]:
        """Göç dosyasına `max_length`'i geri koyar (`__init__`'te pop'landı)."""
        name, path, args, kwargs = cast(
            "tuple[str, str, list[Any], dict[str, Any]]", super().deconstruct()
        )
        if self.max_length is not None:
            kwargs["max_length"] = self.max_length
        return name, path, args, kwargs


def encrypted_fields_of(model: type[models.Model]) -> tuple[models.Field[Any, Any], ...]:
    """Modelin şifreli alanları (kayıt defteri elle tutulmaz, koddan okunur)."""
    return tuple(f for f in model._meta.get_fields() if isinstance(f, EncryptedTextField))
