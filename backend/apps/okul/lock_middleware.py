"""Kilit kapısı — açılmamış veriye API erişimini keser (tasarım §4.3, §4.4, §6.3).

Yönetici parolası zorunludur (parolasız kip yok). Parola kurulu ve kilit
açılmamışken hassas alanlar zaten okunamaz (şifreli token döner) ve yazılamaz
(`KeyMissingError`), ama programın "çalışıyormuş gibi" davranıp resmî evraka
çözülememiş metin basması KABUL EDİLEMEZ. Bu ara katman iki kilidi uygular:

1. **Güvenlik dosyası kayıp** (GA-2): DB'de anahtar parmak izi var ama
   `guvenlik.json` yok — ya da dosya var ama kullanılamıyor (boş, bozuk,
   sarmal bölümleri eksik; `app_password.security_file_missing`). Kilitliyken
   dosyanın silinmesi, yeniden adlandırılması ya da bozulması programı
   "parolasız"a döndürmez ve kullanıcıyı çıkışsız bir kilit ekranında da
   bırakmaz; `423 guvenlik_dosyasi_kayip` döner. İletinin metni sözleşmede
   sabittir ("bulunamadı"); arayüzün kayıp ekranı iki hâli birlikte anlatır.
   Anahtar bellekteyken dosya kaybolsa bile kapı
   kapanır: bir sonraki kilitte açılamayacak bir durumda çalışmaya devam etmek
   yerine kullanıcı sorunu hemen görür. Açık kalanlar (tam yol eşleşmesi):
   - `GET setup/status/` — açılış sağlık denetimi (`desktop/server.py::HEALTH_PATH`);
   - `GET security/status/` ve `GET security/mode/` — arayüzün hangi ekranı
     göstereceğini öğrendiği salt okur durum uçları;
   - `POST security/state/reset/` — yalnız korunan veri yokken (parmak izi
     boş + şifreli tablolar boş) bozuk dosyayı arşivleyip kuruluma döner; uç
     koşulu kendisi denetler (aksi 409);
   - `GET backups/` ve `POST backups/restore/` — çıkış yolu: geri yükleme
     `guvenlik.json`'u yedeğin kurtarma başlığından yeniden yazar
     (`backup_restore._ensure_state_file`). Diğer çıkış yolu dosyanın yedeğini
     veri klasörüne geri koymaktır; kapı her istekte diske bakar, dosya
     döndüğü anda normal kilit durumuna geçilir.
2. **Kilitli** (`423 locked`): parola kurulu, anahtar bellekte değil.
   Açık kalanlar:
   - `/api/v1/security/` ön eki — durum, kilit açma, kurtarma anahtarı, kip
     durumu (kilidi açmanın tek yolu bunlar). İstisna `LOCKED_DENIED_PATHS`:
     kurtarma anahtarı çıktısı kilitliyken kesilir (kilit açma yolu değildir);
   - `GET setup/status/` — açılış sağlık denetimi; yanıtı kişisel veri içermez
     ve istek zaten oturum belirteci gerektirir. Kurulum sihirbazının YAZMA
     uçları kapalı kalır;
   - `/api/v1/updates/` — kişisel veri içermeyen sürüm denetimi.

Parola hiç kurulmamışsa ("kurulum" durumu) kapı bir şey yapmaz: kişi yazan
uçları izin sınıfı (`permissions.RequiresAdminPassword`, 409) keser.

API dışı yollar (SPA'nın kendisi, statik dosyalar) daima serbesttir — kilit
ekranı yüklenebilmelidir. **Yerel yedekleme etkilenmez**: günlük yedek bir HTTP
ucu değildir; masaüstü kabuğu onu açılışta açık yedek anahtarıyla alır
(`desktop/main.py`). Ortaya yalnız AES-256-GCM korumalı `.kdbak` çıkar.

Bu ara katman `config/settings.py` MIDDLEWARE listesinde `RestartRequired`'dan
sonra, kip ara katmanından önce durur.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.okul.services import app_password

API_PREFIX = "/api/"
# Kilitliyken izin verilen uçlar (ön ek eşleşmesi).
ALLOWED_PREFIXES = (
    "/api/v1/security/",
    # Açılış sağlık denetimi (bkz. dosya başlığı). YALNIZ bu tekil yol; kurulum
    # sihirbazının diğer uçları kapalıdır.
    "/api/v1/setup/status/",
    # Kişisel veri içermez; kilit ekranında başlayan otomatik sürüm denetimi (F8).
    "/api/v1/updates/",
)
# `security/` ön ekinde olup kilitliyken YİNE DE kesilen uçlar (TAM yol). Kurtarma
# anahtarı çıktısı (E14) bellekteki anahtara karşı doğrular ve kilit açmanın bir
# yolu değildir: kilitliyken açık kalsaydı kurtarma anahtarı için ikinci bir
# deneme kapısı olurdu. Kurulum sihirbazında anahtar zaten açıktır.
LOCKED_DENIED_PATHS = frozenset({"/api/v1/security/recovery-key/pdf/"})
# Güvenlik dosyası kayıpken izin verilen uçlar (TAM yol eşleşmesi, sözleşme §3).
# `security/state/reset/`: kayıp ekranındaki "sıfırla ve kuruluma dön" yolu; uç
# kendi koşullarını (parmak izi boş + şifreli tablolar boş) denetler, aksi 409.
SECURITY_FILE_MISSING_ALLOWED_PATHS = frozenset(
    {
        "/api/v1/setup/status/",
        "/api/v1/security/status/",
        "/api/v1/security/mode/",
        "/api/v1/security/state/reset/",
        "/api/v1/backups/",
        "/api/v1/backups/restore/",
    }
)

_LOCKED_BODY = {
    "code": "locked",
    "message": (
        "Kayıtlar yönetici parolasıyla kilitli. Devam etmek için yönetici parolasını "
        "girin (parolayı unuttuysanız kurtarma anahtarını kullanın)."
    ),
    "fields": {},
}

_SECURITY_FILE_MISSING_BODY = {
    "code": "guvenlik_dosyasi_kayip",
    "message": app_password.SECURITY_FILE_MISSING_MESSAGE,
    "fields": {},
}


class AppLockMiddleware:
    """Güvenlik dosyası kayıpken ve kilitliyken izinli uçlar dışındaki API'yi 423 ile keser."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path
        if path.startswith(API_PREFIX):
            # Gövdeler sabit: hangi ucun istendiği yankılanmaz.
            if app_password.security_file_missing():
                if path not in SECURITY_FILE_MISSING_ALLOWED_PATHS:
                    return JsonResponse(_SECURITY_FILE_MISSING_BODY, status=423)
            elif (
                not path.startswith(ALLOWED_PREFIXES) or path in LOCKED_DENIED_PATHS
            ) and app_password.is_locked():
                return JsonResponse(_LOCKED_BODY, status=423)
        return self._get_response(request)
