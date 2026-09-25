"""Kütüphane iş mantığı — yazma yolları ve işlem (transaction) sınırı.

Görünümler ORM'e doğrudan yazmaz: katalog kuralları (nüsha açılabilir mi, bağış
komisyon kararı istiyor mu, numara nereden geliyor) tek yerde durur ve testleri
API'den bağımsız koşar. Salt okuma sorguları `apps.kutuphane.selectors`'tadır.

Alt modüller (OYS'nin tek `services.py` dosyası bölündü — tasarım §12):

- `numbering`: nüsha barkodu ve kayıt no sayacı (tek sayaç, asla yeniden kullanılmaz);
- `catalog`: bölüm, eser, nüsha ve edinim yazma yolları;
- `commissions`: komisyon kararı + karar türü denetimi (D7);
- `donations`: bağış ön kaydı ve karardan sonra toplu kataloglama;
- `policy`: kütüphane politikası (tek satır) okuma ve yazma;
- `memberships` (F6): üyelik, kart no (asla yeniden kullanılmaz), kartı yenile,
  sonlandırma ve kişi kayıt defterlerine kaydolan kancalar;
- `circulation` (F6): ödünç ve iade — §9 dolaşım kurallarının tek yeri;
- `yonetici_kipi` (F6): "yalnız yönetici kipinde" işlerin servis katmanı kapısı;
- `weeding` (F8): ayıklama teklifi — E7 yolu, komisyon kararı, harcama yetkilisi onayı;
- `rare_works` (F8): el yazması ve nadir eserler listesi (Md. 12/2);
- `annual_review` (F8): yıl sonu kütüphane raporu (Md. 12/1, E9 — kişisiz);
- `stocktake` (F9): sayım — anlık görüntü, okutma, 32/6 ikinci sayım, onay (32/7 noksan,
  27/1 hasar, TMY 17 fazla), iptal; iki ayrı seçenek (TMY 32/3 durdurması — kapısı
  `tmy_kapisi`; sayım için hizmet arası — kapısı `circulation.checkout`). İade hiçbir
  durumda kilitlenmez.

Hatalar `django.core.exceptions.ValidationError` ile yükseltilir; DRF katmanında
`shared.exceptions.kd_exception_handler` bunu 400'e ve `{code, message, fields}`
gövdesine çevirir. Dolaşım kuralı retleri `circulation.DolasimReddi` (400 + kararlı
`code`), yönetici kipi retleri `yonetici_kipi.KipYetkisiz`dir (403 `kip_yetkisiz`).
"""

from __future__ import annotations
