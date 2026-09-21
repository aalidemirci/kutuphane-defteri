"""Kütüphane Defteri — Django ayarları (tek dosya, tek kullanıcılı masaüstü uygulama).

OYS'nin (Okul Yönetim Sistemi) çok-kullanıcılı/ağ-merkezli ayar dosyasının
(config/settings/{base,dev,prod}.py) aksine burada TEK dosya yeterli: program tek
bilgisayarda çalışır ve bu ayarların sürdüğü YÖNETİM sunucusu yalnız 127.0.0.1'i
dinler (girişsiz yüzey bu varsayıma dayanır). Yerel ağa açılan tek yüzey salt-okur
Ağ Kataloğu'dur; o Django istek zincirini, bu ayarların MIDDLEWARE/URLconf'unu
ve ORM'yi KULLANMAYAN ayrı bir dinleyicidir (desktop/katalog_server.py — tasarım
§4.1, §5). Sırlar `django-environ` OLMADAN doğrudan `os.environ` üzerinden okunur
(bağımlılık yüzeyi küçük tutulur).
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Veri dizini — masaüstü paket kurulumunda platform veri dizinine bağlanır
# ---------------------------------------------------------------------------
# `KD_DATA_DIR` env değişkeni ile geçersiz kılınabilir (Electron/PyInstaller
# paketleyicisi `platformdirs.user_data_dir()` sonucunu buraya verecek).
# Varsayılan geliştirmede `backend/data/` (repo içi, .gitignore'da).
DATA_DIR = Path(os.environ.get("KD_DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _bool_env(name: str, default: bool) -> bool:
    """Basit boolean env okuyucu (django-environ yok — settings sade kalsın)."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Güvenlik
# ---------------------------------------------------------------------------
# Yerel tek-kullanıcılı masaüstü uygulaması — ağ üzerinden erişilmez, bu yüzden
# sabit bir geliştirme anahtarı güvenlik riski oluşturmaz (kriptografik oturum
# yok). Üretim paketlemesinde `KD_SECRET_KEY` env ile geçersiz kılınabilir.
SECRET_KEY = os.environ.get(
    "KD_SECRET_KEY",
    "django-insecure-kutuphane-defteri-yerel-masaustu-gelistirme-anahtari",
)

# Varsayılan FALSE (KVKK): DEBUG hata sayfası yerel değişkenlerdeki ham
# TCKN/telefonu döker — paketlenmiş uygulamada asla açık kalmamalı. Geliştirme
# ortamı docker-compose.yml'de KD_DEBUG=1 ile açar.
DEBUG = _bool_env("KD_DEBUG", False)

# Vite geliştirme proxy'si Docker Compose ağında servise ``backend`` adıyla
# ulaşır (frontend/vite.config.ts). Üretim masaüstü sunucusu yine yalnız
# 127.0.0.1'e bağlanır; bu ad yalnız kapalı geliştirme ağı içindir.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "backend"]

# ---------------------------------------------------------------------------
# Uygulamalar
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.okul",
    "apps.kutuphane",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Yedekten geri yükleme uygulandıktan sonra "yeniden başlat" kapısı: süreç
    # içi durum (bellekteki anahtar, bekleyen göçler) diskteki veriyi artık
    # tarif etmez; tüm API 503 restart_required ile kesilir. Kilit kapısından
    # ÖNCE durur — geri yükleme kilit durumunu da bayatlatır.
    "apps.okul.restart_gate.RestartRequiredMiddleware",
    # Kilit kapısı (tasarım §4.3, §6.3): güvenlik dosyası kayıpken (423
    # guvenlik_dosyasi_kayip) ve kilit açılmadıysa (423 locked) veri uçlarını
    # keser. Parola hiç kurulmamışsa kapı geçirir; kişi yazan uçları izin
    # sınıfı 409 parola_gerekli ile keser.
    "apps.okul.lock_middleware.AppLockMiddleware",
    # Kip kapısı (U5, tasarım §4.4): kilit açık ve kip görevliyken izin listesi
    # dışındaki /api/ isteklerini 403 kip_yetkisiz ile keser; X-KD-Etkinlik
    # başlıklı istekte yönetici kipinin boşta sayacını tazeler. Kilit
    # kapısından SONRA durur: kilitliyken (423) istek buraya gelmez.
    "apps.okul.kip_middleware.KipMiddleware",
]

# Yerel oturum belirteci koruması (tasarım §5.3 son madde). Program authsuz
# olduğundan, gömülü sunucu ayakta iken aynı makinedeki BAŞKA bir işlem
# 127.0.0.1'e istek atıp öğrenci verisini okuyabilir. Masaüstü başlatıcısı
# (`desktop/main.py`) açılışta rastgele bir belirteç üretip `KD_SESSION_TOKEN`
# ile verir; middleware belirteçsiz istekleri 403'ler.
# Geliştirme/test koşusunda değişken boştur → middleware HİÇ yüklenmez, yani
# backend'in `desktop` paketine bağımlılığı YOKTUR.
if os.environ.get("KD_SESSION_TOKEN"):
    MIDDLEWARE.insert(0, "desktop.session_guard.SessionTokenMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Veritabanı — SQLite (tek kullanıcılı masaüstü uygulama; Postgres yok)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            # WAL: eşzamanlı okuma/yazım; foreign_keys: Django varsayılan olarak
            # açar ama açıkça belirtmek niyeti netleştirir; busy_timeout: kilit
            # çakışmasında 5 sn bekle (masaüstü uygulamada tek süreç ama arka
            # plan görevi olabilir). synchronous=FULL (tasarım T15): WAL+NORMAL
            # tutarlıdır ama elektrik kesintisinde son işlemleri geri alabilir;
            # dolaşım masasında bu "kitap çıktı, kaydı yok" demektir. Dolaşımın
            # yazma hacmi düşük olduğundan her commit diske senkronlanır.
            # secure_delete=ON (tasarım §6.3-5): silinen ve güncellenen içerik
            # serbest sayfalarda okunur biçimde kalmaz, sıfırla ezilir (ör.
            # anonimleştirilen gerekçe metni, silinen kişinin eski satırı).
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA foreign_keys=ON;"
                "PRAGMA busy_timeout=5000;"
                "PRAGMA synchronous=FULL;"
                "PRAGMA secure_delete=ON;"
            ),
            "transaction_mode": "IMMEDIATE",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Yerelleştirme
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Statik dosyalar (whitenoise — ayrı web sunucusu yok)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = DATA_DIR / "static"
# WhiteNoise dizin yoksa her istekte uyarı basar; açılışta oluşturmak yeterli.
STATIC_ROOT.mkdir(parents=True, exist_ok=True)

# Derlenmiş SPA. Masaüstü penceresi kök URL'yi açar; burası servis edilmezse
# kullanıcı programı değil Django hata sayfasını görür (F5-D4 denetiminde
# yakalandı). Paketlenmiş çalışmada PyInstaller çalışma-zamanı kancası
# KD_FRONTEND_DIR'i doldurur; geliştirmede depodaki frontend/dist kullanılır.
FRONTEND_DIR = Path(os.environ.get("KD_FRONTEND_DIR", str(BASE_DIR.parent / "frontend" / "dist")))
# WhiteNoise SPA varlıklarını (/assets/…) doğrudan verir; index.html'i istemci
# tarafı rotalar için config/urls.py'deki catch-all döndürür.
WHITENOISE_ROOT = FRONTEND_DIR
WHITENOISE_INDEX_FILE = True

# ---------------------------------------------------------------------------
# Medya (kullanıcı dosyaları — veri dizini altında)
# ---------------------------------------------------------------------------
MEDIA_ROOT = DATA_DIR / "media"

# Dosya eki yükleme sınırı (MB) — OYS varsayılanıyla aynı.
MAX_UPLOAD_SIZE_MB = int(os.environ.get("KD_MAX_UPLOAD_SIZE_MB", "20"))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
# Tek kullanıcılı masaüstü uygulama — kimlik doğrulama YOK (yerel işletim
# sistemi oturumu zaten tek kullanıcıyı sınırlar). DEFAULT_AUTHENTICATION_CLASSES
# boş + UNAUTHENTICATED_USER None: DRF hiçbir kimlik doğrulama denemesi yapmaz.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 25,
    # `{code, message, fields}` hata sözleşmesi (tasarım §4.3; FE lib/api.ts bunu bekler).
    "EXCEPTION_HANDLER": "shared.exceptions.kd_exception_handler",
}
