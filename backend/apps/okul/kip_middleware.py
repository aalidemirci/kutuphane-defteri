"""Kip kapısı — görevli kipinde izin listesi dışındaki API isteklerini keser (§4.4).

`config/settings.py` MIDDLEWARE listesinde `AppLockMiddleware`'den SONRA durur:
kilitliyken (423) ve geri yükleme sonrasında (503) istek buraya hiç gelmez.
Bu kapı YALNIZ kilit açık ve kip görevliyken devreye girer:

* `/api/` altındaki her istek URL adına çözülür (`resolve(path_info)`);
  (ad, yöntem) çifti `kip_izinleri.IZIN_LISTESI`'nde yoksa 403 `kip_yetkisiz`.
  Çözülemeyen `/api/` yolu da 403'tür (fail-closed; görevli kipinde var olmayan
  uç ile kapalı uç ayırt edilmez).
* Reddin gövdesi sabittir ve `code` taşır; böylece arayüz onu oturum belirteci
  403'ünden (`desktop.session_guard`) ayırır (UY-16).
* `HEALTH_PATH` (masaüstü açılış sağlık denetimi, `setup/status/`),
  `security/status/` ve `security/mode/` HİÇBİR durumda kesilmez — yalnız
  OKUMA yöntemlerinde (GET/HEAD). Muafiyet yol eşleşmesidir; yöntemi de
  sınırlamasaydı bu yollardan birine ileride eklenecek bir yazma yöntemi
  (ör. kip sürelerini değiştiren bir PUT) görevli kipinde parolasız açık
  kalır ve dolaşan test onu atladığı için hiçbir test kırılmazdı (denetim
  bulgusu). Diğer yöntemler olağan izin listesi yolundan geçer (fail-closed).
* Güvenlik dosyası kayıpken (GA-2) bu kapı kesmez: kip durumu o an
  `guvenlik_dosyasi_kayip`'tır, görevli değil (`KIP.durum()`), ve neyin açık
  kalacağına kilit kapısı karar verir (yedek listesi + geri yükleme = kayıp
  kilidinin çıkış yolu). Anahtar bellekteyken dosya kaybolup kip görevliye
  inmişse, bu yollar burada kesilseydi çıkış kapanırdı: kayıp durumunda ne kip
  geçişi (409) ne Kilitle (423) mümkündür. Denetim yalnız RED yolunda yapılır;
  yönetici kipindeki sıcak yol dosyaya bakmaz.

Etkinlik: `X-KD-Etkinlik` başlığı taşıyan ve kesilmeyen her `/api/` isteği
`KIP.etkinlik()` çağırır (yönetici kipinin boşta sayacını tazeler). Tembel süre
dolumu `gorevli_mi()` içinde, etkinlikten ÖNCE uygulanır: süresi dolmuş
yönetici kipi geç gelen başlıklı bir istekle dirilmez (§5.10-14). Başlığı
yalnız ön yüz, kullanıcı etkileşiminden hemen sonra gönderir (`lib/api.ts`);
durum ve pano sorguları göndermez.
"""

from __future__ import annotations

from collections.abc import Callable

from desktop.server import HEALTH_PATH
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import Resolver404, resolve

from apps.okul.kip import KIP
from apps.okul.kip_izinleri import izinli_mi
from apps.okul.services import app_password

API_PREFIX = "/api/"
ETKINLIK_BASLIGI = "X-KD-Etkinlik"

# Hiçbir kipte kesilmeyen yollar (§4.4) — yalnız `HIC_KESILMEYEN_YONTEMLER`de.
# Tam yol eşleşmesi: `security/mode/` ÖNEK DEĞİLDİR — `security/mode/staff/`
# görevli kipinde kapalıdır.
HIC_KESILMEYEN_YOLLAR: frozenset[str] = frozenset(
    {
        HEALTH_PATH,
        "/api/v1/security/status/",
        "/api/v1/security/mode/",
    }
)
# Muafiyetin geçerli olduğu yöntemler: yalnız okuma (dosya başı notu).
HIC_KESILMEYEN_YONTEMLER: frozenset[str] = frozenset({"GET", "HEAD"})

KIP_YETKISIZ_MESAJI = "Bu işlem görevli kipinde yapılamaz. Yönetici kipine geçin."

_BODY = {"code": "kip_yetkisiz", "message": KIP_YETKISIZ_MESAJI, "fields": {}}


def uc_adi(path_info: str) -> str | None:
    """Yolun Django URL adı (ad alanlı include'da `ad_alani:ad`); çözülemezse None."""
    try:
        eslesme = resolve(path_info)
    except Resolver404:
        return None
    return eslesme.view_name or None


class KipMiddleware:
    """Görevli kipinde izin listesi dışındaki `/api/` isteklerini 403 ile reddeder."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path
        if not path.startswith(API_PREFIX):
            return self._get_response(request)
        muaf = path in HIC_KESILMEYEN_YOLLAR and (request.method or "") in HIC_KESILMEYEN_YONTEMLER
        if (
            not muaf
            and KIP.gorevli_mi()
            and not izinli_mi(uc_adi(request.path_info), request.method or "", request)
            # Kayıp kilidinde kapıyı kilit kapısı tutar (dosya başı notu).
            and not app_password.security_file_missing()
        ):
            # Gövde sabit: hangi ucun istendiği yankılanmaz.
            return JsonResponse(_BODY, status=403)
        if request.headers.get(ETKINLIK_BASLIGI):
            KIP.etkinlik()
        return self._get_response(request)
