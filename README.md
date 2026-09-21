# Kütüphane Defteri

Okul kütüphaneleri için geliştirilmekte olan **çevrimdışı** bir masaüstü
programı (Windows 10/11 ve Pardus). Kütüphanenin günlük işlerini tek
bilgisayarda yürütmesi hedeflenir:

- **Katalog ve etiket:** Excel'den toplu katalog girişi, Türkçe harflere duyarlı
  arama ve yazar/eser/konu sıralaması, barkodlu sırt ve nüsha etiketleri.
- **Dolaşım masası:** üye kartı ve barkod okuyucuyla ödünç ve iade, sınıf
  kitaplığına ya da öğretmene toplu teslim, iade hatırlatma pusulası.
- **Sayım, komisyon ve ayıklama:** sayım tutanağı, ayıklama kararları, bağış ön
  kaydı ve Taşınır Mal Yönetmeliği için hazırlık çıktıları.
- **İki kip:** masada çalışan öğrenci görevliler için yalnız dolaşımı açan
  görevli kipi; ayarlar, raporlar ve kişi verisi yönetici parolasının
  arkasında.

Kurallar Okul Kütüphaneleri Yönetmeliği'ne (RG 23.11.2024/32731) göre
yazılır: on beş günlük sabit ödünç süresi, öğrenciye 3, öğretmene 5 kitap
sınırı, ödünç verilmeyen kaynaklar. Program kendini okulun kütüphane işlerini
yürüttüğü **yerel bir araç** olarak konumlar; Bakanlığın otomasyon sisteminin
yerine geçtiğini iddia etmez ve verisini açık, belgelenmiş bir biçimde dışa
aktarır.

## Veri okulda kalır

Tek bir yerel veritabanı; bulut ve telemetri yok. Yönetici parolası
zorunludur: öğrenci ve personel adları, okul numaraları ve kart numaraları
şifreli saklanır, yedekler de şifrelidir. TC kimlik numarası, veli bilgisi ve
cinsiyet hiç toplanmaz. Programın okul dışına yaptığı tek istek, kullanıcı
"Denetle" düğmesine bastığında yayımlanan son sürümü sormaktır.

## Ağ Kataloğu

Programın kardeşlerinden farkı: isteğe bağlı olarak açılan **Ağ Kataloğu**
sayesinde okul ağındaki bilgisayarlar ve etkileşimli tahtalar kataloğu
tarayıcıyla, salt okur olarak tarayabilir.

| Gösterir | Göstermez |
|---|---|
| Künye: eser adı, yazar, yayınevi, yıl, konu, ISBN | Üye listesi, üye adı, sınıfı, kart numarası |
| Raf yeri ve bölüm | Kimin ödünç aldığı, iade tarihi, ödünç geçmişi |
| Nüsha özeti ("3 nüsha · 2 rafta · 1 ödünçte") | Kayıp ve hasar kayıtları, bedeller, bağışçı |
| Yeni gelenler, çok okunanlar (sayı göstermeden) | Yönetim ekranları, yedek, dışa aktarım |
| Yazar, eser ve konu dizinleri | — |

Ağ Kataloğu varsayılan olarak **kapalıdır**, yalnız yönetici açar. Açık
olduğunda bile kişisel veriye erişemez: ayrı bir sunucudan, yalnız katalog
görünümlerini okuyabilen salt okur bir bağlantıyla çalışır. Kullanıcıdan veri
toplamaz, arama terimlerini ve IP adreslerini kaydetmez.

## Durum

**Geliştirmede.** İskelet fazı (F0) sürüyor; henüz yayımlanmış sürüm yoktur.
Tasarım ve faz planı: [docs/tasarim/2026-09-21-genel-tasarim.md](docs/tasarim/2026-09-21-genel-tasarim.md).
Hedeflenen kurulum düzeni: [docs/kurulum.md](docs/kurulum.md).

Masaüstü ve paketleme iskeleti kardeş proje Kelebek Sınav'dan, iş mantığı OYS
(okulapp) kütüphane modülünden türetilmektedir.

## Lisans

[PolyForm Noncommercial License 1.0.0](LICENSE). Ticari olmayan kullanım
serbesttir; ticari satış, ücretli dağıtım ya da barındırılan hizmet olarak
sunum için ayrı yazılı izin gerekir (bkz. `LICENSE`).
