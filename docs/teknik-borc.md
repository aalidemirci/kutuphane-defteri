# Teknik borç kütüğü

Buraya giren her kalem **biliniyor ve kabul edilmiş** demektir; denetimlerde
yeniden raporlanmaz (gerekçenin kendisi çürütülmedikçe). Kaynak: genel
tasarım §4.3 (tehdit modeli), §15 (açık kararlar), §16 (riskler). Kalem
kapanınca silinmez, "Kapanan" bölümüne tarihle taşınır.

## Açık

- **TB1 — Şube, üye türü ve zaman damgası düz metinde (U9'un kalan riski;
  tasarım §4.3, §6.3):** adlar, okul no, kart no ve kişi metinleri Fernet'le
  şifreli, eşleştirme kör indeksle yapılır. Ama şube, üye türü, barkod, eser
  adları ve ödünç/iade tarihleri **düz** kalır: katalog araması, sıralama ve
  sayım bunlara DB'de erişmek zorundadır. Veri dizinini kopyalayan biri ad,
  okul no ve kart no olmadan kişiye doğrudan ulaşamaz; ama **küçük şubede**
  "9/C'den bir öğrenci şu tarihte şu kitabı aldı" bilgisi kişiyi tahmin
  ettirebilir. Öğretmenin branşı ve unvanı hiç alınmadığı için öğretmen branş
  üzerinden tanınmaz (V2-01). Azaltma: ayrı kütüphane masası Windows hesabı +
  BitLocker önerisi (`docs/kurulum.md`), aktif üyenin iade edilmiş ödünçlerinde
  kişi bağının ders yılı sonu + 1 yıl sonra koparılması (§6.4). **Aydınlatma
  metnine (E13) yazılır.**

- **TB2 — Ağ kataloğunda bağlantı tüketme (slowloris; tasarım §4.3 GA-12,
  §5.2):** waitress'in `connection_limit` değeri sunucu geneline uygulanır, IP
  başına sınır tanımaz; `channel_timeout` yalnız hiç veri gelmeyen bağlantıyı
  keser. Yavaş gönderen bir istemci havuzu doldurabilir. Karşılık (F5):
  katalog için ayrı havuz, `connection_limit=300`, `channel_timeout=30`, kabul
  anında IP başına eşzamanlı bağlantı sınırı (dispatcher alt sınıfı, ör. 20),
  `REMOTE_ADDR` başına token-bucket. **Kalan risk yalnız katalogun erişilemez
  olmasıdır**; veri riski yoktur, yönetim sunucusu ayrı dinleyicidedir.

- **TB3 — `PRAGMA synchronous=FULL` maliyeti ölçülmedi (T15, A18):** WAL +
  `NORMAL` elektrik kesintisinde son işlemleri geri alabilir; dolaşımda bu
  sessiz kayıptır (SU-18). Bu yüzden `FULL` seçildi; her commit fsync bekler.
  Dolaşımın yazma hacmi düşük olduğu için maliyetin hissedilmeyeceği
  varsayılıyor. **F0'da ölçülüp sonuç buraya yazılacak** (okutma başına süre,
  toplu içe aktarımda toplam süre; HDD'li eski masaüstünde ayrıca). Toplu
  içe aktarım yavaşsa işlem tek transaction'da tutulur, `synchronous` gevşetilmez.

- **TB4 — Logo geçici: kelebek çizimi (F0 kopyası):** `packaging/ikonlar/
  logo_uret.py` kardeş projenin koltuk-karesi kelebeğini üretiyor; açıklaması
  da o projenin salon krokisini anlatıyor. Kütüphaneye özgü bir çizim
  gelene kadar ikon ve logo bu yer tutucudur. Değiştirmek için
  `kutuphane-defteri-logo.png` yeniden üretilip `ikon_uret.py` koşulur
  (sözleşme hazır). Aynı dosyadaki "kelebek" sözcüğü kimlik kalıntısı
  taramasına (tasarım §2.3) takılır; logo değişince kendiliğinden kapanır.
  okulapp.org'daki proje görseli (`public/kutuphane-defteri.png`) de aynı
  logodan türeyecek (tasarım §17).

- **TB5 — Linux derleme tabanı Debian 11 destek dışı (kardeş projeden devralındı;
  A6):** `.deb` Pardus 21 uyumu için `python:3.12-bullseye` kabında derlenir;
  Debian 11 LTS 31.08.2026'da bitti. Güvenlik deposu tarihli arşive
  sabitlendi (`packaging/linux/apt_dene.sh`). Sıradaki kırılma: `bullseye` ANA
  deposunun da `archive.debian.org`'a taşınması; belirtisi derleme kabında
  404'tür, çözümü aynı sabitlemenin ana depo satırlarına uygulanmasıdır.
  Kalıcı çözüm Pardus 21 desteğinin ne zaman bırakılacağı kararıdır (taban
  bookworm'a çıkarsa glibc yükselir, Pardus 21'de paket açılmaz). **Karar
  kullanıcıdadır**, saha kurulumlarına bakılarak verilir.

- **TB6 — İmzasız exe + dinleyen port (tasarım §16-15):** kurulum dosyası
  imzasızdır; tarayıcıyla indirilince SmartScreen "tanınmayan uygulama"
  uyarısı çıkar. Ağ kataloğu açıkken dinleyen port bazı antivirüslerde ek
  uyarıya yol açabilir. Azaltma: SHA-256 doğrulaması (`docs/kurulum.md`),
  onedir paket (yanlış pozitifi azaltır). İmzalama v2 işidir.

- **TB7 — Her güncelleme yönetici (BTR) ister (U4, tasarım §16-14):** kurulum
  Program Files'a yapılır ve güvenlik duvarı kuralı kurucuda eklenir; bu
  yüzden her sürüm geçişinde UAC'ye yönetici kimliği girilir. Güncelleme BTR'nin
  takvimine bağlı kalabilir. Azaltma: güncelleme kipinde güvenlik duvarı
  kuralına dokunulmaz (değiştirilmiş port ve BTR'nin eklediği bloklar korunur);
  güncelleme denetimi yalnız düğmeyle yapılır, program kendisi indirmeye
  zorlamaz.

- **TB8 — Anonimleştirilen bağlar yedeklerde bir süre kalır (V2-02, §6.4):**
  günlük ve `pre-anonim` yedeklerde en çok 14 gün; `pre-migrate` yedeklerinde
  son 5 güncellemeye kadar (tetik anında eski `pre-migrate`ler silinir).
  Kullanıcının indirdiği şifreli yedekler ve USB kopyaları okulun elindedir;
  imha kuralı kılavuzda yazılır. Aydınlatma metni bu kapsamı aynen söyler.

- **TB9 — Kişisel Verilerin Silinmesi… Yönetmeliği depoda yok (§6.4):**
  anonimleştirme onayının azami bekleme süresi (6 ay) bu Yönetmeliğin
  periyodik imha hükmüne göre ayarlanacak. Metin resmî kaynaktan birebir
  alınana kadar bu Yönetmeliğe madde atfı yazılmaz
  (`docs/mevzuat/BENIOKU.md` §2).

## Kapanan

*(henüz yok)*
