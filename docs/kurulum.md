# Kütüphane Defteri — Kurulum ve Sorun Giderme Kılavuzu

Bu kılavuz programı kuracak kişi içindir: kütüphane yöneticisi (kütüphaneci ya
da kütüphaneden sorumlu öğretmen) ile okulun bilişim teknolojileri rehber
öğretmeni (BTR). "Çıkış kodları" bölümü BTR için ayrılmıştır.

> **Durum:** Program geliştirme aşamasındadır; henüz yayımlanmış sürüm yoktur.
> Bu belge ilk sürüm için **hedeflenen** kurulum düzenini anlatır (genel
> tasarım §4-§5). Özellikler fazlarla gelir; belge, sürüm çıkmadan önce
> programın gerçek davranışıyla adım adım yeniden doğrulanır. "Hazırlanıyor"
> diye işaretli bölümün içeriği henüz yazılmadı.

Veri okulda kalır: tek bir yerel veritabanı dosyası, telemetri yok, bulut yok.
Program **açılışta internete çıkmaz** ve okul dışına kişisel veri göndermez.
Dışarıya istek yalnız **sizin başlattığınız iki durumda** gider:

1. **Güncelleme denetimi** — Ayarlar → Güncelleme'de "Denetle" düğmesine
   bastığınızda yayımlanan son sürümü sorar.
2. **ISBN ile künye getirme** — kitabın numarasından eser bilgilerini getirir.
   Bu özellik **varsayılan olarak kapalıdır**, ayarlardan siz açarsınız ve her
   sorguyu siz başlatırsınız. Dışarı yalnız kitabın numarası (ISBN) gider;
   okulun adı, kitap listeniz ya da kişi bilgisi gitmez. Kapalıyken program bu
   yönde hiçbir bağlantı kurmaz.

Ağ kataloğu hiçbir durumda internete çıkmaz.

## 1. Kurulumdan önce

Bu hazırlıkları kurulumdan önce yapın; sonradan değiştirmek zahmetlidir.

### 1.1 Bilgisayar okul demirbaşı olmalı

Program **yalnız kurum demirbaşı bir bilgisayara** kurulur (Bilgi ve Sistem
Güvenliği Yönergesi md. 11/8, 11/23). Kurulum sihirbazı "bu bilgisayar okul
demirbaşıdır" onayını ister; bilgisayarın demirbaş no'su isteğe bağlıdır.
Kişisel bilgisayara kurmayın.

### 1.2 Kütüphane masası için ayrı Windows hesabı (önerilir)

Masada öğrenci görevliler çalışacağı için bilgisayarda **yönetici yetkisi
olmayan, ayrı bir "kütüphane masası" Windows hesabı** açılmasını öneririz.
Hesabı BTR açar.

- Program ve kütüphane yöneticisinin günlük işi bu hesapta yürür.
- Bu hesapta e-Okul, MEBBİS, DYS, e-posta ve kişisel oturumlar **açılmaz**.
  Masadaki öğrenci tarayıcıda açık kalmış bir oturuma ulaşamamalıdır.
- Programın verisi, programı çalıştıran hesabın klasöründe durur
  (`%LOCALAPPDATA%\KutuphaneDefteri`). Başka bir hesaptan açılan program o
  veriyi görmez; bu bilinçli bir tercihtir.
- e-Okul'dan alınan öğrenci ve personel listeleri bu hesaba şifreli bir
  taşıyıcıyla getirilir ve içe aktarımdan sonra silinir.

### 1.3 Disk şifreleme (önerilir)

Programın kendisi adları, okul numaralarını, kart numaralarını ve kişiyle ilgili
açıklamaları şifreler. Ama eser adları, şube ve ödünç tarihleri şifresizdir;
küçük bir şubede kişi tahmin edilebilir. Tam koruma için bilgisayarın diskini
**BitLocker** ile şifreleyin (Windows sürümünüz desteklemiyorsa "Cihaz
şifrelemesi"). Pardus'ta disk şifrelemesi işletim sistemi kurulurken seçilir.

### 1.4 Parola ve kurtarma anahtarı

- Yönetici parolası **zorunludur**; sihirbazın ilk adımında belirlenir.
- Parolanın görevlendirilmiş **en az iki kişide** bulunması önerilir: sorumlu
  öğretmen ve kütüphanede görevli memur ya da sorumlu müdür yardımcısı.
- Sihirbaz tek seferlik bir **kurtarma anahtarı** verir. Anahtarı yazdırın,
  PDF olarak USB belleğe kaydedin ya da elle yazın; program anahtarın iki
  grubunu sakladığınız kopyadan geri yazdırarak doğrular. **Kurulum bu
  doğrulama yapılmadan tamamlanmaz.** Anahtar müdürlükte kapalı zarfta
  saklanır. Parola da anahtar da kaybolursa şifreli veri açılamaz.
- Anahtar ekranda değilken (program kapandı, anahtar kaydedilemedi) sihirbazın
  1. adımı iki yol sunar: kâğıttaki anahtarın tamamını yazıp doğrulamak ya da
  yönetici parolasıyla **yeni bir anahtar üretmek**. Aynı iki yol Ayarlar →
  Güvenlik'te de vardır ("Kurtarma Anahtarını Doğrula", "Kurtarma Anahtarını
  Yenile").
- **Yenileme eski kâğıdı hemen gereksiz kılmaz.** Kayıtların anahtarı değişmez;
  yalnız kurtarma kilidi yenilenir. Her yedek, alındığı günün güvenlik
  dosyasını içinde taşır: yenilemeden önce alınmış bir yedek bu bilgisayarda
  (güvenlik dosyası yerindeyken) yeni anahtarla ya da güncel parolayla açılır,
  ama başka bir bilgisayarda ya da güvenlik dosyası kaybolduğunda yalnız eski
  anahtarla (ya da o dönemin parolasıyla) açılır. USB'deki eski yedekler
  duruyorsa eski kâğıdı "Eski anahtar — <tarih> öncesi yedekler için" diye
  işaretleyip ayrı saklayın. Bu bilgisayarda eski bir yedeği geri yüklerken
  güncel parolayı ya da yeni anahtarı kullanın: eski anahtarla geri yükleme
  güvenlik dosyasını da yedeğin dönemine döndürür.
- Yenileme, **ele geçmiş** bir anahtara karşı koruma değildir: eski yedekler ve
  veri klasöründe `guvenlik-arsiv-<tarih>.json` adıyla saklanan önceki güvenlik
  dosyası eski anahtarla açılabilir. Böyle bir durumda yönetici parolasını da
  değiştirin.
- Elinizdeki anahtarın temiz bir çıktısını sonradan Ayarlar → Güvenlik →
  "Kurtarma anahtarı çıktısı"ndan alabilirsiniz; program anahtarı doğrular,
  yanlış yazılmış anahtarı basmaz. Anahtar programda saklanmaz: kaybolduysa
  yeniden gösterilemez, yalnız yenisi üretilebilir.

### 1.5 Elektrik kesintisi

Kütüphane bilgisayarı için bir kesintisiz güç kaynağı (UPS) önerilir. Program
her kaydı diske yazmadan işlemi tamamlanmış saymaz. Yine de kapanış düzgün
olmazsa bir sonraki açılışta "son işlemleri kontrol edin" uyarısı çıkar.

## 2. Hangi dosyayı indirmeliyim?

Kurulum dosyaları okulapp.org'un indirme sayfasında (`indir.okulapp.org`)
yayımlanır. MEB ağında GitHub erişimi kapalı olabileceği için bu adres
önceliklidir; aynı dosyalar GitHub Releases sayfasında da bulunur.

| Dosya | Kimin için |
|---|---|
| `kutuphane-defteri-<sürüm>-win64-setup.exe` | Windows 10/11 — önerilen kurulum |
| `kutuphane-defteri-<sürüm>-win64-portable.zip` | Windows — kurulumsuz (Ağ Kataloğu ve otomatik başlatma yok, §3.3) |
| `kutuphane-defteri_<sürüm>_amd64.deb` | Pardus ve Debian tabanlılar — önerilen |
| `kutuphane-defteri-<sürüm>-linux-x64.tar.gz` | Linux — yönetici parolası olmadan |
| `SHA256SUMS.txt` | İndirilen dosyayı doğrulamak için (§9) |

## 3. Windows kurulumu

### 3.1 Kurulum paketi ile (önerilen)

Kurulum **yönetici yetkisi ister**: program `Program Files` altına kurulur ve
Ağ Kataloğu için güvenlik duvarı kuralı kurulum sırasında eklenir.

1. Kütüphane masası hesabında oturum açın (§1.2).
2. `kutuphane-defteri-<sürüm>-win64-setup.exe` dosyasını **bu hesapta**
   çalıştırın.
3. Windows'un yönetici onay penceresi (UAC) açılınca **BTR yönetici hesabının
   kullanıcı adını ve parolasını** girer.

   Kurulumu BTR kendi oturumunda başlatmasın: otomatik başlatma görevi
   kurucuyu başlatan hesaba yazılır; BTR'nin oturumunda başlatılırsa program
   masa hesabında kendiliğinden açılmaz.
4. Kurucu şu seçenekleri sunar:
   - **Oturum açılınca başlat:** program oturum açılışında kilit ekranıyla
     açılır ve tepsiye iner (§5).
   - **Yerel ağdan katalog taramasına izin ver:** güvenlik duvarına yalnız
     yerel alt ağdan gelen bağlantılara izin veren bir kural ekler. Kural tek
     başına bir şey açmaz; Ağ Kataloğu program içinden ayrıca açılır (§8).
5. Bilgisayarda Microsoft Edge WebView2 yoksa kurucu kurar. Gömülü önyükleyici
   internet ister; ağı kısıtlı bilgisayarda WebView2'yi önceden kurun.

İmzasız paket olduğu için SmartScreen "tanınmayan uygulama" uyarısı verebilir:
"Ek bilgi" → "Yine de çalıştır". Önce §9'daki SHA-256 doğrulamasını yapın.

Program açıkken kurulum ya da kaldırma başlatılırsa kurucu programa kapanma
isteği gönderir ve 30 saniyeye kadar bekler. Program kapanmazsa "tepsideki
simgeden Çık'ı seçin" iletisi çıkar. Kurucu programı zorla kapatmaz.

### 3.2 Güncelleme

Her güncelleme de yönetici yetkisi ister; BTR'nin UAC'ye kimlik girmesi
gerekir. Güncelleme sırasında güvenlik duvarı kuralına dokunulmaz:
değiştirilmiş port ve BTR'nin eklediği ağ blokları korunur. Program her sürüm
geçişinden önce kendiliğinden bir yedek alır.

Yeni sürümü görmek için Ayarlar → Güncelleme → **Denetle**. Kurulum dosyasını
indirip masa hesabında çalıştırın (§3.1'deki gibi).

### 3.3 Taşınabilir sürüm (kurulum yapmadan)

`...portable.zip` dosyasını bir klasöre açın, `kutuphane-defteri.exe`'yi
çalıştırın. Veriler yine `%LOCALAPPDATA%\KutuphaneDefteri` altına yazılır; zip'i
silmek verileri silmez. Taşınabilir sürümde **Ağ Kataloğu sunulmaz** (güvenlik
duvarı kuralı kurulu programın yoluna bağlıdır) ve otomatik başlatma yoktur.

## 4. Pardus / Linux kurulumu

Paket **Pardus 21 ve Pardus 23** ile bu sürümlerin dayandığı Debian 11 ve
Debian 12 üzerinde çalışacak biçimde üretilir.

### 4.1 `.deb` paketi ile (önerilen)

```bash
sudo apt install ./kutuphane-defteri_<sürüm>_amd64.deb
```

Bağımlılıklar dağıtımın deposundan kurulur; bu yüzden kurulum sırasında
bilgisayarın depoya erişimi olmalıdır. Program menüde "Kütüphane Defteri"
olarak görünür; uçbirimden `kutuphane-defteri` ile de açılır.

Linux sürümü, pencereyi çizen kütüphaneleri LGPLv3 lisansıyla birlikte
dağıtır. Bu dosyalar kurulum klasöründe (`/opt/kutuphane-defteri`) ayrı ayrı
durur; isteyen kendi sürümüyle değiştirebilir.

### 4.2 Taşınabilir arşiv ile (yönetici parolası olmadan)

```bash
tar -xzf kutuphane-defteri-<sürüm>-linux-x64.tar.gz
cd kutuphane-defteri-<sürüm>
./kur.sh
```

`kur.sh` programı kullanıcı klasörüne kurar ve menü kaydını ekler. Kaldırmak
için `./kaldir.sh`.

Güncellemede yeni `.deb` dosyasını §4.1'deki komutla kurmanız yeterlidir.
Program içinden indirme yalnız Windows kurulum dosyası içindir.

## 5. İlk açılış ve günlük kullanım

1. Sihirbaz sırayla sorar: **yönetici parolası ve kurtarma anahtarı** (§1.4;
   anahtarın saklandığı doğrulanmadan kurulum tamamlanmaz),
   okul bilgileri (kademe, kısa ad, demirbaş onayı), ders yılı, dönemler ve
   öğrenciye kapalı günler (ara tatil, yarıyıl).
   Kurulum bitince Genel Bakış'taki **Başlangıç Yol Haritası** sıradaki
   işleri (e-Okul aktarımları, kapalı günler, katalog şablonu, anahtarın
   saklanması, parolanın paylaşılması, BTR görüşmesi) gösterir.
2. *(Sonraki sürümde.)* Program bir **Kütüphane aydınlatma metni** üretecek; bu
   metnin e-Okul aktarımından önce duyurulması gerekir. Bugünkü sürümde metin
   programda yoktur; okulun kendi aydınlatma metnini kullanın.
3. Öğrenci ve personel listelerini e-Okul'un Excel raporlarından aktarırsınız
   (TCKN istenmez ve tutulmaz): öğrenci için *OOG01001R020 — Sınıf/Şube
   Öğrenci Listesi*, personel için *OOK01001R1 — Personel Listesi*. e-Okul
   dosyaları `.XLS` uzantısıyla iner; açıp düzenlemeniz gerekmez. Aktarmadan
   önce **Önizle** hiçbir şey yazmadan etkisini gösterir.
4. Kitap listesi Excel şablonuyla aktarılır (kılavuzda anlatılır).

**Pencere ve tepsi.** Pencerenin çarpı düğmesi programı kapatmaz, pencereyi
gizler; program saatin yanındaki simge alanında (tepside) çalışmaya devam
eder. Programı kapatmak için tepsideki simgeden **Çık**'ı seçin. *(Sonraki
sürümde:* görevli kipinde Çık yönetici parolası isteyecek; bugünkü sürümde
tepsi menüsü kip okumaz ve Çık parolasızdır.*)*

**Oturum açılmadan program çalışmaz.** Windows oturumu açılmadan ne program ne
Ağ Kataloğu kalkar. Bilgisayar sabah açıldığında masa hesabında oturum açın.

## 6. Verileriniz nerede? Yedekleme

| İçerik | Windows | Pardus/Linux |
|---|---|---|
| Veritabanı + ayarlar | `%LOCALAPPDATA%\KutuphaneDefteri\data` | `~/.local/share/kutuphane-defteri/data` |
| Otomatik yedekler | `%LOCALAPPDATA%\KutuphaneDefteri\backups` | `~/.local/share/kutuphane-defteri/backups` |
| Günlükler | `%LOCALAPPDATA%\KutuphaneDefteri\logs` | `~/.local/state/kutuphane-defteri/logs` |

Program **her açılışta** o güne ait bir otomatik yedek alır
(`gunluk-<tarih>.kdbak`; aynı gün yeniden açılırsa ikinci yedek almaz) ve 14
gün saklar; her sürüm güncellemesinden önce ayrıca bir yedek bırakır
(`pre-migrate-<sürüm>-<tarih>.kdbak`, son 5 adet). Yedekler şifrelidir ve ancak
yönetici parolası ya da kurtarma anahtarıyla açılır. Yönetici parolası
kurulmadan (ilk açılış) yedek alınmaz; ilk yedek parola kurulduktan sonraki
açılışta alınır.

> **Bugünkü sürümde yedek açılışa bağlıdır.** Program tepside günlerce açık
> kalırsa o günlerin yedeği alınmaz; gün değişiminde kendiliğinden yedek alan
> günlük kapı sonraki sürümde gelecek. O zamana kadar bilgisayarı her sabah
> kapatıp açın ya da haftada bir programı tepsiden Çık'la kapatıp yeniden
> açın.

Yedekler bilgisayarın kendisindedir: disk bozulursa onlar da gider. Ayda bir
Ayarlar → Güvenlik'ten **şifreli yedek indirip** USB belleğe alın ve USB'yi
bilgisayardan ayrı saklayın.

### 6.1 Yedekten geri dönme

* **Windows:** Başlat menüsündeki **"Kütüphane Defteri — Yedekten Geri
  Yükle"** kısayolunu çalıştırın. (Komut isteminden:
  `"<kurulum klasörü>\kutuphane-defteri.exe" --geri-yukle`)
* **Pardus/Linux:** uçbirimden `kutuphane-defteri --geri-yukle`

Program tepside çalışıyorsa araç açılmaz ve "Program tepside çalışıyor.
Tepsideki simgeden Çık'ı seçip yeniden deneyin." iletisini verir.

Araç yedekleri en yeniden eskiye listeler; seçtiğiniz yedek veritabanının
yerine konur. Yönetici parolası (parola sonradan değiştiyse yedeğin alındığı
dönemdeki parola) ya da kurtarma anahtarı sorulur. Kurtarma anahtarı sonradan
yenilendiyse: bu bilgisayarda güvenlik dosyası yerindeyken **yeni** anahtar
eski yedekleri de açar; dosya yoksa (ya da yedek başka bilgisayarda açılıyorsa)
yedeğin alındığı dönemin anahtarı gerekir (§1.4). Mevcut veritabanı SİLİNMEZ;
`db-onceki-<tarih>` adıyla `data` klasöründe saklanır. İşlem bitince programı
normal açın.

### 6.2 "Güvenlik dosyası bulunamadı ya da okunamıyor" ekranı

Kayıtların anahtarı `data` klasöründeki `guvenlik.json` dosyasında durur.
Dosya silinir, adı değişir ya da içi boşalır/bozulursa (ör. Not Defteri'nde
açılıp yanlışlıkla kaydedilirse) program kayıtları açmaz ve bu ekranı
gösterir; yeni parola da kurulamaz. İki çıkış yolu vardır (üçüncüsü yalnız
hiç kişi kaydı girilmemiş kurulumda görünür, aşağıda):

1. Dosyanın sağlam bir kopyası varsa (taşıma sırasında alınan veri klasörü,
   USB bellek) `guvenlik.json`'u `data` klasörüne geri koyun (bozuk dosyanın
   yerine) ve ekrandaki **Yeniden denetle** düğmesine basın. Kilit ekranı gelir.
2. Kopya yoksa aynı ekrandan (ya da §6.1'deki araçla) bir yedeği geri
   yükleyin. Her yedek güvenlik dosyasını da içinde taşır; geri yükleme dosyayı
   yeniden oluşturur. O yedekten sonra girilen kayıtlar kalkar.

Dosya kayıpken ya da bozukken program eski yedekleri silmez ve güvenlik
dosyası olmayan yeni yedek almaz. Geri yükleme bozuk dosyayı silmez,
`guvenlik-arsiv-<tarih>.json` adıyla kenara alır.

**Henüz kişi kaydı girilmemiş kurulum.** Veritabanında hiç öğrenci, öğretmen
ya da diğer personel kaydı yoksa, kayıtların anahtarı veritabanına henüz
işlenmemişse (ör. parola kurulurken işlem yarıda kaldıysa) ve yedek
klasöründe yedek bulunmuyorsa dosya korunan bir veriyi açmıyordur. Bu durumda
aynı ekranda **Güvenlik dosyasını sıfırla ve kuruluma dön** düğmesi çıkar:
bozuk dosya `guvenlik-arsiv-<tarih>.json` adıyla kenara alınır ve sihirbaz
yönetici parolası adımından yeniden açılır. Kişi kaydı ya da yedek varsa bu
düğme görünmez: veritabanı kaybolup boş yeniden oluştuysa eski kayıtlar
yedeklerdedir ve doğru yol yedekten geri yüklemektir (yukarıdaki 2. madde).

## 7. Yeni bilgisayara taşıma — kontrol listesi

Bilgisayar değişirse, yeniden kurulursa ya da disk değişirse sırayla:

1. [ ] Eski bilgisayarda Ayarlar → Güvenlik'ten **şifreli yedek** indirin ve
       USB'ye alın. Yönetici parolasının ya da kurtarma anahtarının elinizde
       olduğunu doğrulayın.
2. [ ] Yeni bilgisayarın **okul demirbaşı** olduğunu doğrulayın (§1.1) ve
       **kütüphane masası hesabını** açın (§1.2). Disk şifrelemesini açın
       (§1.3).
3. [ ] Programı masa hesabında, BTR'nin UAC kimliğiyle **kurun** (§3.1).
       "Yerel ağdan katalog taramasına izin ver" seçeneğini işaretleyin.
4. [ ] İndirdiğiniz şifreli yedeği **geri yükleyin** (§6.1).
5. [ ] Programı açın; kitap, üye ve açık ödünç sayılarını eski bilgisayardaki
       son durumla karşılaştırın.
6. [ ] Ağ Kataloğu kullanılıyorsa: Ağ Doktoru'nda **güvenlik duvarı**
       denetiminin geçtiğini görün (§8).
7. [ ] BTR'den **DHCP rezervasyonunun yeni bilgisayarın ağ kartı (MAC)
       adresine** taşınmasını isteyin. Aksi hâlde bilgisayarın IP adresi
       değişir ve eski adres çalışmaz.
8. [ ] IP adresi değiştiyse **katalog afişini** yeniden basın, tahtalardaki ve
       bilgisayarlardaki **yer imlerini** güncelleyin.
9. [ ] Eski bilgisayardaki veri klasörünü (§6) ve yedekleri, yeni kurulum
       çalıştıktan sonra silin; USB yedeği okulun imha kuralına göre saklayın.

## 8. Ağ Kataloğu (hazırlanıyor)

Ağ Kataloğu, okul ağındaki bilgisayarların ve etkileşimli tahtaların kütüphane
kataloğunu tarayıcıyla, salt okur olarak taramasını sağlar. **Kişisel veri
göstermez:** üye, ödünç alan, iade tarihi ya da ödünç geçmişi yoktur; yalnız
künye, raf yeri ve nüshaların rafta mı ödünçte mi olduğu görünür.

Varsayılan olarak **kapalıdır** ve yalnız yönetici kipinde açılır. Açıldığında
program okul ağına bir port (varsayılan 8765) üzerinden hizmet verir; bu
yüzden açmadan önce okul BTR'sinin bilgisi alınır ve program BTR ile müdürün
imzalayacağı bir **Ağ Hizmeti Bilgi Notu** üretir.

Bu bölüm özellik geldiğinde yazılacak: güvenlik duvarı ve Ağ Doktoru, IP
seçimi ve DHCP rezervasyonu, tahta ağından erişim, yer imi dağıtımı, üçüncü
parti güvenlik duvarları, Pardus'ta ufw/firewalld. BTR için ayrıntılı ağ
kılavuzu `docs/ag-kurulumu.md` olarak hazırlanacak.

Ağ Kataloğu yalnız **hizmet verir**, internete hiç çıkmaz: giden bağlantı bu
bölümün konusu değildir (bkz. belgenin başındaki iki kapı).

### 8.1 ISBN ile künye getirme — BTR sınaması (hazırlanıyor)

Bu özellik kitabın numarasından eser bilgilerini getirir, **varsayılan olarak
kapalıdır** ve ayarlardan açılır. Açmadan önce okul ağından iki adrese
erişilebildiğini BTR ile sınayın. Windows'ta PowerShell'de:

```powershell
Test-NetConnection koha.ekutuphane.gov.tr -Port 210
Test-NetConnection openlibrary.org -Port 443
```

- İkisi de `TcpTestSucceeded : True` verirse özellik okul ağında çalışabilir.
- Biri ya da ikisi başarısızsa adres okul ağının içerik filtresinde kategorisiz
  olabilir; erişim talebi **Yardım Masası Modülü** (`yardimmasasi.meb.gov.tr`)
  üzerinden açılır (Bilgi ve Sistem Güvenliği Yönergesi md. 11/12). Kararı okul
  vermez, bu yüzden süre okulun elinde değildir.
- Hiç açılmazsa program yine çalışır: künyeyi elle girebilir ya da eksik ISBN
  listesini dışa aktarıp **internete bağlı başka bir cihazda** doldurup dosyayı
  geri aktarabilirsiniz.

**Kütüphane bilgisayarına telefon, mobil modem ya da kişisel erişim noktası
bağlayarak internet almayın**; Yönerge md. 11/18 bunu açıkça yasaklar. Çözüm
ayrı bir cihazdır, aynı cihaza ikinci hat değildir.

## 9. İndirilen dosyayı doğrulama

Paketler imzasızdır; bütünlüğü `SHA256SUMS.txt` ile doğrulayın.

Windows (PowerShell):

```powershell
Get-FileHash .\kutuphane-defteri-<sürüm>-win64-setup.exe -Algorithm SHA256
```

Linux:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing
```

Çıkan özet `SHA256SUMS.txt` içindeki satırla birebir aynı olmalıdır.

## 10. Sık karşılaşılan sorunlar

### 10.1 "Microsoft Edge WebView2 bulunamadı" (Windows)

Kurulum paketi WebView2'yi kurar; ağı kısıtlı bilgisayarda ya da taşınabilir
sürümde eksik kalabilir. Program Türkçe yönlendirme verir. Microsoft'un
"Evergreen" kurulum dosyasını indirip kurun, programı yeniden açın.

### 10.2 "Kütüphane Defteri zaten çalışıyor"

Program tek kopya çalışır ve çoğu zaman tepsidedir. Pencere görünmüyorsa saatin
yanındaki simge alanına bakın; simgeye tıklayıp pencereyi açın ya da Çık'ı
seçin.

### 10.3 "Veri dosyası bozuk görünüyor"

Program veriyi korumak için açılmamıştır. §6.1'deki adımlarla son sağlam
yedeğe dönün. Bozuk dosyayı silmeyin.

### 10.4 "Bu veri, programın daha yeni bir sürümüyle oluşturulmuş"

Bilgisayardaki program eski, veri yeni. Programı son sürüme güncelleyin; veri
dosyasına dokunmayın.

### 10.5 PDF üretilmiyor veya Türkçe karakterler bozuk

Komut isteminden ya da uçbirimden teşhis kipini çalıştırın:

```bash
kutuphane-defteri --pdf-duman deneme.pdf
```

Çıkış kodu 0 değilse günlük dosyasıyla birlikte bildirin. Paketin eksiksiz
kurulduğunu ayrıca şu komut söyler (PDF üretmez, hızlıdır):

```bash
kutuphane-defteri --bagimlilik-duman
```

Çıkış kodu 10 ise pakette bir parça eksiktir: kurulum dosyasını yeniden
indirip kurun.

### 10.6 Program açılmıyor ya da aniden kapandı

`logs/uygulama.log` ve `logs/cokme.log` dosyalarının son satırlarına bakın ve
BTR'ye iletin. `cokme.log` ad, numara gibi kişisel veri içermez. Veri klasörü
OneDrive gibi eşitlenen bir klasörün altındaysa program uyarı günlükler;
eşitleme açık veritabanı dosyasını bozabilir.

Program PDF'leri aynı anda değil **sırayla** üretir: bir PDF hazırlanırken
istenen ikincisi birincinin bitmesini bekler.

## 11. Çıkış kodları (BTR için)

`kutuphane-defteri --autotest` pencere açmadan açılış zincirini koşar ve
aşağıdaki kodlardan biriyle çıkar. Kodlar `desktop/errors.py` ile aynıdır.

| Kod | Anlamı | Yapılacak |
|---|---|---|
| 0 | Açılış sağlıklı | — |
| 1 | Beklenmeyen hata | `logs/uygulama.log` son satırları |
| 2 | Program zaten çalışıyor (tepsi dahil) | tepsideki simgeden Çık (§10.2) |
| 3 | Veritabanı bozuk | §6.1 yedekten dönüş |
| 4 | Veri, programdan yeni bir sürümle yazılmış | programı güncelleyin (§10.4) |
| 5 | Veritabanı güncellenemedi (migrate) | `backups` içindeki `pre-migrate-*` yedeğine §6.1 ile dönüş |
| 6 | Yerel sunucu başlatılamadı | güvenlik yazılımı 127.0.0.1'i engelliyor olabilir |
| 7 | WebView2/pencere motoru yok | §10.1 |
| 8 | PDF duman testi başarısız (`--pdf-duman`) | §10.5 |
| 9 | Geri yükleme (`--geri-yukle`) başarısız | parolayı ya da kurtarma anahtarını doğrulayıp yeniden deneyin; `logs/uygulama.log` |
| 10 | Bağımlılık duman testi başarısız (`--bagimlilik-duman`) | paket eksik üretilmiş; yeniden indirip kurun (§10.5) |

`--geri-yukle`, `--autotest` ve `--pdf-duman` çalışan bir kopya bulursa 2
koduyla çıkar. Bayraksız ikinci açılış ise çalışan kopyanın penceresini öne
getirir ve 0 koduyla çıkar.

## 12. Programı kaldırma

* **Windows (kurulum paketi):** Ayarlar → Uygulamalar → Kütüphane Defteri →
  Kaldır (yönetici yetkisi ister). Güvenlik duvarı kuralı da silinir.
* **Windows (taşınabilir):** klasörü silin.
* **Pardus/Linux (.deb):** `sudo apt remove kutuphane-defteri`
* **Linux (taşınabilir):** arşivdeki `./kaldir.sh`

Kaldırma işlemi **verilerinizi silmez**: katalog, üyeler ve yedekler §6'daki
klasörlerde kalır. Bilgisayar okuldan çıkacaksa (hurdaya ayırma, devir) veri
klasörünü ve yedekleri silin; önce şifreli bir yedeği USB'ye alın.
