"""Kip testlerinin ortak yardımcıları (toplanmaz: dosya adı `test_` ile başlamaz)."""

from __future__ import annotations

from collections.abc import Callable

from apps.okul.models import SchoolConfig
from apps.okul.services import app_password

DOGRU_PAROLA = "Dogru-Yonetici-Parolasi-1"
YANLIS_PAROLA = "Yanlis-Parola-9"


def kurulum_durumunu_yaz(*, tamam: bool) -> None:
    """`SchoolConfig.setup_completed`'ı doğrudan yazar (DB gerekir).

    Kurulum bitene kadar süreler kipi düşürmez (F1 eki, karar 2-1); süre
    testleri (§5.10-14) kurulumu tamamlanmış ortamda koşar, kurulum sırasındaki
    davranış ayrı testlerdedir. Sihirbaz kapısı (`setup/complete/`) burada
    atlanır: kip testleri yalnız bayrağı okur.
    """
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.setup_completed = tamam
    config.save(update_fields=["setup_completed", "updated_at"])


class SahteSaat:
    """Enjekte edilebilir monoton saat: `ilerlet()` ile zaman elle ilerler."""

    def __init__(self, baslangic: float = 10_000.0) -> None:
        self.simdi = baslangic

    def __call__(self) -> float:
        return self.simdi

    def ilerlet(self, saniye: float) -> None:
        self.simdi += saniye


def sahte_dogrulayici(cagrilar: list[str]) -> Callable[[str], None]:
    """`app_password.verify_password` taklidi: yalnız `DOGRU_PAROLA` geçer.

    Gerçek doğrulama (sarmal çözme, parmak izi, kademeli gecikme) A kolunun
    servisinde ve kendi testlerindedir; kip testleri yalnız sözleşmeye (yanlışsa
    `AppPasswordError("Parola hatalı.")`) güvenir. Uçtan uca bir test gerçek
    doğrulamayı ayrıca koşar (`test_kip_uclari.py`).
    """

    def dogrula(password: str) -> None:
        cagrilar.append(password)
        if password != DOGRU_PAROLA:
            raise app_password.AppPasswordError("Parola hatalı.")

    return dogrula
