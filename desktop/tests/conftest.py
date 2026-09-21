"""Masaüstü testleri için ortak kurulum.

Bu testler Django *uygulamasını* (apps/okul) çalıştırmaz —
oturum belirteci middleware'i yalnız `HttpRequest`/`HttpResponse` sözleşmesine
dokunur. Bu yüzden gerçek `config.settings` yerine asgari bir ayar kümesi
kurulur: veritabanı, uygulama kaydı ve migration gerekmez, testler milisaniyede
koşar. Uçtan uca açılış doğrulaması `test_main.py`'deki `--autotest` alt-süreç
testinde gerçek ayarlarla yapılır.

`desktop.main.run` açılışta `faulthandler`ı `logs/cokme.log`a bağlar
(`enable_crash_log`, 19.09.2026). Bu SÜREÇ GENELİNDE bir ayardır: testlerde
gerçekten çağrılırsa pytest'in kendi çöküş çıktısı geçici bir dosyaya kayardı.
Aşağıdaki fikstür onu etkisizleştirir; gerçek davranış `test_logging_setup.py`
içinde AYRI bir alt süreçte, gerçek bir yerel çöküşle sınanır.
"""

from __future__ import annotations

import faulthandler
import logging
from collections.abc import Iterator

import django
import pytest
from django.conf import settings


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: yavaş, uçtan uca alt-süreç testi")


@pytest.fixture(autouse=True)
def _faulthandler_etkisiz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(faulthandler, "enable", lambda *args, **kwargs: None)


@pytest.fixture
def kd_gunlugu() -> Iterator[list[logging.LogRecord]]:
    """`kutuphane_defteri` ağacındaki günlük kayıtlarını toplar.

    `caplog` yetmez: `configure_logging` üst günlükçüde `propagate=False` yapar
    ve başka bir test onu çağırdıysa kayıtlar köke ulaşmaz.
    """
    kayitlar: list[logging.LogRecord] = []

    class _Toplayici(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            kayitlar.append(record)

    gunlukcu = logging.getLogger("kutuphane_defteri")
    toplayici = _Toplayici(level=logging.DEBUG)
    onceki_duzey = gunlukcu.level
    gunlukcu.setLevel(logging.DEBUG)
    gunlukcu.addHandler(toplayici)
    try:
        yield kayitlar
    finally:
        gunlukcu.removeHandler(toplayici)
        gunlukcu.setLevel(onceki_duzey)


if not settings.configured:
    settings.configure(
        DEBUG=False,
        ALLOWED_HOSTS=["127.0.0.1", "localhost"],
        DEFAULT_CHARSET="utf-8",
        USE_TZ=True,
        TIME_ZONE="Europe/Istanbul",
        INSTALLED_APPS=[],
        DATABASES={},
    )
    django.setup()
