"""Ağ Kataloğu — Django'dan bağımsız, salt okur WSGI uygulaması (tasarım §4.1, §5).

Bu paket bir Django *uygulaması* DEĞİLDİR: `INSTALLED_APPS`'e girmez, modeli,
göçü, URLconf'u ve middleware'i yoktur. Masaüstü kabuğu onu ikinci bir waitress
dinleyicisiyle sunar (`desktop/katalog_server.py`, iş parçacığı `kd-katalog`).

Değişmezler (koruma testleri §5.10-2/3, `katalog/tests/test_koruma.py`):

- Django'nun istek zinciri, URLconf'u, ORM'si ve veritabanı katmanı içe
  aktarılmaz; uygulama modelleri de. İleride (F5) yalnız şablon motoru gelir,
  veriye `sqlite3` salt okur bağlantıyla ve yalnız katalog görünümlerinden
  ulaşılır.
- Çerez okunmaz, çerez yazılmaz. Yalnız GET/HEAD; gövde 1 KB'ı aşamaz.
- Yönetim API'sinin hiçbir yolu burada karşılık bulmaz (yol tablosu sabittir).
"""
