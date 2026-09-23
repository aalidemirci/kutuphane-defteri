"""Kütüphane iş mantığı — yazma yolları ve işlem (transaction) sınırı.

Görünümler ORM'e doğrudan yazmaz: katalog kuralları (nüsha açılabilir mi, bağış
komisyon kararı istiyor mu, numara nereden geliyor) tek yerde durur ve testleri
API'den bağımsız koşar. Salt okuma sorguları `apps.kutuphane.selectors`'tadır.

Alt modüller (OYS'nin tek `services.py` dosyası bölündü — tasarım §12):

- `numbering`: nüsha barkodu ve kayıt no sayacı (tek sayaç, asla yeniden kullanılmaz);
- `catalog`: bölüm, eser, nüsha ve edinim yazma yolları;
- `commissions`: komisyon kararı + karar türü denetimi (D7);
- `donations`: bağış ön kaydı ve karardan sonra toplu kataloglama;
- `policy`: kütüphane politikası (tek satır) okuma ve yazma.

Hatalar `django.core.exceptions.ValidationError` ile yükseltilir; DRF katmanında
`shared.exceptions.kd_exception_handler` bunu 400'e ve `{code, message, fields}`
gövdesine çevirir.
"""

from __future__ import annotations
