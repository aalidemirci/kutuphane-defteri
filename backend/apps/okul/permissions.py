"""DRF izin sınıfları — kişi yazan uçların yönetici parolası kapısı (tasarım §6.3-2).

Program hesapsızdır (masadaki kişi ayrımı kiple yapılır, §4.4); buradaki izin
sınıfı kimlik sormaz, **programın durumunu** sorar: yönetici parolası
kurulmadan kişi yazan bir uç (öğrenci/personel oluşturma, güncelleme, silme,
içe aktarma önizleme ve uygulama; F6'da üyelik) çalışmaz, **409
`parola_gerekli`** döner. Okuma yöntemleri serbesttir.

Neden 403 değil 409? İstek yetkisiz değildir; programın durumu işlemle
çelişir ("önce parolayı kurun"). Arayüz bu kodu tanır ve kullanıcıyı kurulum
sihirbazının ilk adımına yönlendirir.

Savunma derinliği: izin sınıfı unutulsa bile şifreli alan anahtarsız yazmaz
(`shared.crypto.KeyMissingError` → yine 409). Koruma testi
(`tests/test_kisi_yazan_uclar.py`) URL desenlerini dolaşır ve bu sınıfı taşıyan
uçları açık bir listeyle karşılaştırır. Yeni bir kişi uç eklenince (C kolu,
F6 üyelik) bu sınıf takılır ve listeye eklenir.
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from apps.okul.services import app_password


class RequiresAdminPassword(BasePermission):
    """Yazma yöntemlerinde (POST/PUT/PATCH/DELETE) yönetici parolası kurulu olmalı."""

    def has_permission(self, request: Request, view: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True
        # Kurulu değilse `PasswordRequired` → kd_exception_handler → 409 parola_gerekli.
        app_password.require_password_set()
        return True
