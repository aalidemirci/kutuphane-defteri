# Kütüphane Defteri

Okul kütüphaneleri için **çevrimdışı** bir masaüstü programı (Windows 10/11 ve
Pardus). Kütüphanenin günlük işlerini tek bilgisayarda yürütür:

- **Katalog ve etiket:** Excel'den toplu katalog girişi ya da — hazır liste yoksa —
  önce barkod etiketini yapıştırıp kitabı elde okutarak kayıt; Türkçe harflere
  duyarlı arama ve yazar/eser/konu sıralaması; barkodlu sırt ve nüsha etiketleri.
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
şifreli saklanır, yedekler de şifrelidir. T.C. kimlik numarası, veli bilgisi ve
cinsiyet hiç toplanmaz. Program açılışta internete çıkmaz; okul dışına istek
yalnız kullanıcının başlattığı iki durumda gider: "Şimdi denetle" düğmesine
basıldığında yayımlanan son sürümü programın GitHub sayfasına sormak ve —
varsayılan kapalı olan ayar açıldıysa — bir kitabın ISBN'inden künye getirmek.
İkincisinde dışarı yalnız kitabın numarası gider; kişisel veri hiçbir durumda
çıkmaz.

## Ağ Kataloğu

Programın kardeşlerinden farkı: isteğe bağlı olarak açılan **Ağ Kataloğu**
sayesinde okul ağındaki bilgisayarlar ve etkileşimli tahtalar kataloğu
tarayıcıyla, salt okur olarak tarayabilir.

| Gösterir | Göstermez |
|---|---|
| Künye: kaynak adı, yazar, yayınevi, yıl, konu, ISBN | Üye listesi, üye adı, sınıfı, kart numarası |
| Yer numarası ve bölüm | Kimin ödünç aldığı, iade tarihi, ödünç geçmişi |
| Nüsha özeti ("3 nüsha · 2 rafta · 1 ödünçte") | Kayıp ve hasar kayıtları, bedeller, bağışçı |
| Yeni gelenler, çok okunanlar (sayı göstermeden) | Yönetim ekranları, yedek, dışa aktarım |
| Kaynak adı, yazar ve konu dizinleri | — |

Ağ Kataloğu varsayılan olarak **kapalıdır**, yalnız yönetici açar. Açık
olduğunda bile kişisel veriye erişemez: ayrı bir sunucudan, yalnız katalog
görünümlerini okuyabilen salt okur bir bağlantıyla çalışır. Kullanıcıdan veri
toplamaz, arama terimlerini ve IP adreslerini kaydetmez.

## Durum

**İlk ön sürüm (beta) hazırlanıyor.** Programın bütün bölümleri yazıldı; ilk sürüm
bir ön sürümdür ve gerçek bir okul ortamında adım adım sınanır. Gerçek okul verisiyle
kullanmadan önce şifreli yedek alın.

- Kurulum, güncelleme, yeni bilgisayara taşıma ve kaldırma: [docs/kurulum.md](docs/kurulum.md)
- Ağ Kataloğu için okulun bilişim teknolojileri rehber öğretmenine (BTR):
  [docs/ag-kurulumu.md](docs/ag-kurulumu.md)
- Deneme kurulumu için saha kabul protokolü ve uydurma deneme verisi:
  [docs/saha-kabulu.md](docs/saha-kabulu.md)
- Tasarım ve kararlar: [docs/tasarim/2026-09-21-genel-tasarim.md](docs/tasarim/2026-09-21-genel-tasarim.md)

Paketler yayımlandığında GitHub Releases sayfasında ve programın sayfasında
(`okulapp.org/kutuphane-defteri`; dosyalar `indir.okulapp.org`'dan iner) bulunur.
Paketler imzasızdır; indirdiğiniz dosyayı `SHA256SUMS.txt` ile doğrulayın (siteden
indirildiyse adı `SHA256SUMS-<sürüm>.txt`; Linux'ta `sha256sum -c <dosya> --ignore-missing`).

Masaüstü ve paketleme iskeleti aynı ailenin sınav programından (kardeş depo), iş
mantığı OYS (okulapp) kütüphane modülünden türetilmiştir.

## Lisans

[PolyForm Noncommercial License 1.0.0](LICENSE). Ticari olmayan kullanım
serbesttir; ticari satış, ücretli dağıtım ya da barındırılan hizmet olarak
sunum için ayrı yazılı izin gerekir (bkz. `LICENSE`). Pakete giren üçüncü taraf
bileşenlerin lisans metinleri paketle birlikte dağıtılır; depodaki kopyası ve LGPL
bileşenlerinin kaynak adresleri: [THIRD_PARTY_LICENSES/BENIOKU.txt](THIRD_PARTY_LICENSES/BENIOKU.txt).
