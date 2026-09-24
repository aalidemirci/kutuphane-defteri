"""Yalnız yönetici kipinde yapılan kütüphane işlerinin servis katmanı kapısı (§4.4, U5).

Görevli kipini asıl kesen ara katmandır (`apps.okul.kip_middleware`): izin
listesi dışındaki her uç, parametre kuralına takılan her istek (ör. gerekçe ya
da kartsız işaret taşıyan ödünç) 403 `kip_yetkisiz` alır. Bu modül AYNI kuralı
servis katmanında bir kez daha söyler (savunma derinliği): tasarımın "yalnız
yönetici kipinde" dediği işler — gecikme engeli istisnası, kartsız ödünç,
kartı yenile — servis doğrudan (bir görünüm, bir komut, bir test) çağrılsa da
görevli kipinde yapılamaz.

Md. 18 sayı sınırı ve Md. 16/1 kaynakları için böyle bir kapı YOKTUR, çünkü
onların istisnası hiçbir kipte yoktur: servisin bu kurallar için bir gerekçe
parametresi hiç bulunmaz (`services.circulation`).

Hata gövdesi ara katmanınkiyle aynıdır (`{code: "kip_yetkisiz", message, fields}`,
403): arayüz iki kaynağı ayırt etmek zorunda kalmaz.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException

from apps.okul.kip import KIP
from apps.okul.kip_middleware import KIP_YETKISIZ_MESAJI

KIP_YETKISIZ_KODU = "kip_yetkisiz"


class KipYetkisiz(APIException):
    """Görevli kipinde yönetici işi istendi — 403 `kip_yetkisiz` (ara katmanla aynı gövde)."""

    status_code = status.HTTP_403_FORBIDDEN
    default_code = KIP_YETKISIZ_KODU
    default_detail = KIP_YETKISIZ_MESAJI


def gorevli_kipinde_mi() -> bool:
    """Kilit açık ve kip görevli mi? (`KIP.gorevli_mi` — süre dolumu dahil)"""
    return KIP.gorevli_mi()


def require_admin_mode() -> None:
    """Görevli kipindeyse `KipYetkisiz` yükseltir; yönetici kipinde sessizce geçer."""
    if gorevli_kipinde_mi():
        raise KipYetkisiz()
