"""Ağ Kataloğu uygulamasının Django tarafındaki kurucusu (tasarım §4.1, T16).

Katalog paketi (`backend/katalog/`) `apps.*`'ı ve Django'nun veri katmanını
İÇE AKTARAMAZ (§4.1 değişmezi, §5.10-3). Veritabanının yolu ve Türkçe arama
katlaması ise Django tarafındadır. Bu modül ikisini bir araya getirir:

- `varsayilan_katalogu_kur()` — süreç içi katalog uygulamasını
  (`katalog.app.application`) veriye bağlar. `KutuphaneConfig.ready()` çağırır;
  yani `prepare_django` tamamlanınca masaüstünün yüklediği uygulama (§4.1
  "katalog yalnız prepare_django'dan sonra kalkar") zaten veriye bağlıdır.
- `katalog_uygulamasi(...)` — AYRI bir örnek (testler, yük provası).

Veritabanı yolu İSTEK ANINDA Django ayarından okunur (`veritabani_yolu`):
test çalıştırıcısı yolu test veritabanına çevirdiğinde katalog da onu görür.

Katlama işlevleri `search_key` ve `sort_key` alanlarını üreten işlevlerin
KENDİSİDİR (`apps.kutuphane.keys`): katalog sorgusu, eser kaydedilirken
kullanılan katlamanın aynısından geçer (T7, §5.3 "Arama").
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

from apps.kutuphane import keys
from katalog import app as katalog_app
from katalog.app import KatalogKurulumu, KatalogUygulamasi, create_app
from katalog.bakim import BakimKapisi
from katalog.sayac import GunlukSayaclar
from katalog.sinir import HizSiniri


def veritabani_yolu() -> Path:
    """Programın SQLite dosyası (testlerde test veritabanı; `create_test_db` günceller)."""
    return Path(str(settings.DATABASES["default"]["NAME"]))


def katalog_kurulumu() -> KatalogKurulumu:
    return KatalogKurulumu(
        db_yolu=veritabani_yolu,
        arama_parcalari=keys.search_terms,
        siralama_anahtari=keys.tr_collation_key,
    )


def varsayilan_katalogu_kur() -> KatalogUygulamasi:
    """Süreç içi katalog uygulamasını veriye bağlar ve döndürür (fikirdeş)."""
    katalog_app.application.kur(katalog_kurulumu())
    return katalog_app.application


def katalog_uygulamasi(
    *,
    bakim_kapisi: BakimKapisi | None = None,
    hiz_siniri: HizSiniri | None = None,
    sayaclar: GunlukSayaclar | None = None,
) -> KatalogUygulamasi:
    """Veriye bağlı AYRI bir Ağ Kataloğu örneği (bakım kapısı varsayılan: süreç içi `KAPI`)."""
    return create_app(
        katalog_kurulumu(), bakim_kapisi=bakim_kapisi, hiz_siniri=hiz_siniri, sayaclar=sayaclar
    )
