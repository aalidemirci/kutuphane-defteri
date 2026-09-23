"""ISBN ile künye getirme (U13, tasarım §8.5) — **varsayılan KAPALI** dış kapı.

Bu paket programın **ikinci ve son** dış kapısıdır (T11: ilki güncelleme
denetimidir). Kapının on sert kuralı tasarım §8.5'tedir ve hepsi testle
kilitlenmiştir (§5.10-19):

1. Ayar varsayılan kapalıdır; kapalıyken kod **hiç** ağa çıkmaz (`servis`).
2. Yalnız kullanıcının başlattığı tek istek; açılışta, arka planda ve **toplu
   içe aktarımda ASLA** (`servis.kullanici_istegi` bağlamı olmadan sorgu
   reddedilir). Saniyede en çok bir istek (`istemci`).
3. Dışarı yalnız normalize ISBN gider; istek başlıkları, sorgu dizesi ve gövde
   testle dolaşılır (`istemci`).
4. Yanıt **güvenilmeyen girdidir**: boyut ve alan tavanı, denetim karakteri
   temizliği, NFC, HTML varlık çözümü, kısa zaman aşımı, yönlendirme aynı host
   içinde en çok bir kez (`temizlik`, `istemci`).
5. Kullanıcı onaylamadan hiçbir alana yazılmaz: bu paket **yalnız öneri
   üretir**, `Work` satırına HİÇ yazmaz. Yazma kullanıcının kendi kaydettiği
   `library/works/` isteğiyle olur. Çevirmen alanı dışarıdan doldurulmaz.
6. Yerel önbellek: aynı ISBN ikinci kez sorulmaz (`onbellek`).
7. TLS sistem sertifika deposundan doğrulanır, sistem proxy'si kullanılır
   (`istemci`; `certifi` KULLANILMAZ — MEBNET'in SSL denetimli proxy'si
   arkasında sessizce patlardı).
8. Ağ Kataloğu süreci bu paketi hiç görmez (§5.10-20 koruma testi
   `katalog/tests/test_koruma.py`).
9. Fail-open: uç ölürse, yavaşsa ya da engelliyse program aksamaz; elle giriş
   ve Excel içe aktarımı her koşulda tam işlevlidir.
10. Konum dili: öneri "Dış kaynaktan alındı, doğrulayın" rozetiyle, kaynak adı
    ve tarihiyle sunulur (docs/sozluk.md); "resmî künye" denmez.

Yeni Python bağımlılığı YOKTUR: ağ istemcisi `urllib.request`, MARCXML
ayrıştırması `xml.etree` (dış varlık ve DTD kapalı), çevrimdışı dosya yolu
zaten bağımlı olunan `openpyxl`.
"""

from __future__ import annotations
