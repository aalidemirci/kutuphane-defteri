# Kütüphane Defteri — Kurulum ve Sorun Giderme Kılavuzu

Bu kılavuz programı kuracak kişi içindir: kütüphane yöneticisi (kütüphaneci ya
da kütüphaneden sorumlu öğretmen) ile okulun bilişim teknolojileri rehber
öğretmeni (BTR). "Çıkış kodları" bölümü BTR için ayrılmıştır.

> **Durum:** İlk yayımlanan sürüm bir **ön sürümdür (beta)**: gerçek okul verisiyle
> kullanmadan önce okulda bir deneme kurulumuyla sınanması önerilir. Deneme için
> adım adım protokol ve uydurma deneme verisi [`docs/saha-kabulu.md`](saha-kabulu.md)'dedir;
> gerçek öğrenci listesi denemede kullanılmaz. Ağ Kataloğunun okul ağında ve tahtalarda
> çalıştığının kanıtı o protokolle alınır (§8).

Veri okulda kalır: tek bir yerel veritabanı dosyası, telemetri yok, bulut yok.
Program **açılışta internete çıkmaz** ve okul dışına kişisel veri göndermez.
Dışarıya istek yalnız **sizin başlattığınız iki durumda** gider:

1. **Güncelleme denetimi** — Ayarlar → Güncelleme'de "Şimdi denetle" düğmesine
   bastığınızda yayımlanan son sürümü programın yayımlandığı GitHub sayfasına sorar
   (§3.2). İstek kişisel veri taşımaz.
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

### 1.6 Görev devri (kütüphane yöneticisi değişince)

Kütüphane yöneticisi tayin, görev değişikliği ya da emeklilikle ayrılınca yetki onda
kalmamalıdır. Ayarlar → Güvenlik → **Görev Devri** kartı (yalnız yönetici kipinde)
tek akıştır:

1. **Parola ve kurtarma anahtarı birlikte yenilenir.** Mevcut yönetici parolası ve
   görevi devralanın belirlediği yeni parola girilir; program yeni bir kurtarma
   anahtarı üretir. Bundan sonra kilidi yeni parola ve yeni anahtar açar (eski
   parolanın sınırı aşağıda). Daha önce görev devri yapılmışsa kart önceki devrin
   adımlarını tamamlanmış gösterir; düğmenin adı "Görev devrini yeniden başlat"tır.
2. **Yeni anahtar saklanır ve doğrulanır** (yazdırın, PDF olarak USB'ye alın ya da
   elle yazın; iki grubu geri yazarak doğrulayın) — kurulumdaki gibi.
3. **Görev devri notu basılır.** Not; teslim edilenlerin listesini (yeni parolanın
   ikinci görevliye kapalı zarfla bildirilmesi, yeni anahtar zarfı, masa hesabının
   değiştirilen parolası, okuyucu ve yazıcı, USB yedekleri), notun düzenlendiği
   gündeki açık işlerin kişisiz sayılarını ve eski yedeklerin durumunu yazar. Görevi
   devreden ve devralanın adları yalnız basılan nottadır; programda saklanmaz. Not
   imzalanıp müdürlükte saklanır.

**Sınır (dürüst söyleyelim):** görev devri kayıtların şifreleme anahtarını
değiştirmez; bütün kayıtların yeni bir anahtarla yeniden şifrelenmesi bu sürümde
yoktur. Her yedek alındığı günün güvenlik bilgisini taşır: devirden önce alınmış
yedekler — bu bilgisayardaki günlük yedekler (14 gün içinde kendiliğinden silinir),
güncelleme öncesi yedekler (son beş güncelleme), parola kurulurken alınan
`pre-parola-*` yedeği (kendiliğinden silinmez) ve USB bellekteki yedekler — ile veri
klasöründeki `guvenlik-arsiv-*.json` dosyaları ESKİ parola ve ESKİ kurtarma
anahtarıyla açılabilir. Daha önemlisi: eski parola ya da eski anahtar bunlardan
biriyle birlikte kayıtların şifreleme anahtarını verir; bu anahtar **devirden SONRA
alınan yedekleri de**, arşiv dosyası `guvenlik.json` yerine konursa bu bilgisayardaki
güncel kayıtları da açar. Görev devri, görevi devredenin bu bilgisayara ve yedeklere
erişimi kesildiğinde anlam taşır: **kütüphane masası Windows hesabının parolasını
değiştirin** ve yenisini görevi devredene vermeyin (§1.2). Devirden sonra yeni bir
şifreli yedek alıp USB'ye koyun ve devirden önce alınmış USB yedeklerini silin (§6.3).
Eski anahtar kâğıdını "Eski anahtar — <tarih> öncesi yedekler için" diye ayrı zarfta
saklayın; o yedekler kalmayınca kâğıdı yırtarak yok edin (gizli bilgi içeren atık
evrak yok edilir — Yönerge md. 10/3). Çalışması sona eren kullanıcı bilişim
sistemlerinin kullanımına yönelik şifreleri iade eder, erişim hakları kaldırılır
(Yönerge md. 6/4); okulda kalan kişinin görev değişikliğinde bu kural kıyasen
uygulanır. Görevi devreden eski parolayı hiçbir yerde saklamaz. Veri sorumluları ile
veri işleyenler öğrendikleri kişisel verileri Kanuna aykırı olarak başkasına
açıklayamaz ve işleme amacı dışında kullanamaz, bu görevden ayrıldıktan sonra da
sürer (KVKK md. 12/4); veri sorumlusu okuldur ve görevi devreden de görevi sırasında
öğrendiği kişisel verileri okulun bu kuralı gereği açıklamaz.

## 2. Hangi dosyayı indirmeliyim?

Kurulum dosyalarının bağlantıları programın okulapp.org'daki sayfasındadır
(`okulapp.org/kutuphane-defteri`); dosyaların kendisi `indir.okulapp.org`'dan
iner. MEB ağında GitHub erişimi kapalı olabileceği için bu yol önceliklidir;
aynı dosyalar GitHub Releases sayfasında da bulunur. `indir.okulapp.org`'un
kendi dizin sayfası yoktur: dosyaya programın sayfasındaki bağlantıdan gidin.

<!-- Bakım notu (kullanıcıya görünmez): programın sayfası (okulapp.org/kutuphane-defteri)
tasarım §17'deki ilk site eklemesiyle yayına girer; 27.09.2026 kullanıcı kararıyla bu iş
okulapp.org deposunda AYRI bir adımdır (içerik: docs/site-icerigi.md); o güne dek bağlantı 404 verir.
Elle denetleme bu belgede (§2, §3.2), kılavuzun Güncelleme bölümünde ve Güncelleme
ekranındaki bağlantıda aynı sayfayı gösterir; dosyalar indir.okulapp.org'dan iner
(tasarım §14.1 F11 ekleri E-6, K-4). -->


| Dosya | Kimin için |
|---|---|
| `kutuphane-defteri-<sürüm>-win64-setup.exe` | Windows 10/11 — önerilen kurulum |
| `kutuphane-defteri-<sürüm>-win64-portable.zip` | Windows — kurulumsuz (Ağ Kataloğu sunulmaz, otomatik başlatma yok, §3.3) |
| `kutuphane-defteri_<sürüm>_amd64.deb` | Pardus ve Debian tabanlılar — önerilen |
| `kutuphane-defteri-<sürüm>-linux-x64.tar.gz` | Linux — kurulum için sistem yöneticisi (sudo) yetkisi gerekmez (Ağ Kataloğu yok, §4.2) |
| `SHA256SUMS.txt` | İndirilen dosyayı doğrulamak için (§9); `indir.okulapp.org`'da sürümlü adla: `SHA256SUMS-<sürüm>.txt` |

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
   kurulum dosyasını başlatan hesaba yazılır; BTR'nin oturumunda başlatılırsa program
   masa hesabında kendiliğinden açılmaz.
4. Kurulum penceresi önce lisans sözleşmesini (PolyForm Noncommercial) gösterir;
   kabul edilmeden kurulum sürmez. Ardından şu seçenekleri sunar:
   - **Oturum açılınca Kütüphane Defteri'ni başlat:** Görev Zamanlayıcı'ya,
     kurulum dosyasını başlatan hesabın oturum açılışında tetiklenen bir görev
     ("Kutuphane Defteri") yazar. Program kilit ekranıyla açılır. Alt seçenek
     **Pencereyi açmadan tepside başlat** pencereyi göstermeden tepsiye iner
     (§5). Kaldırmada görev silinir.
   - **Yerel ağdan katalog taramasına izin ver (güvenlik duvarı kuralı):**
     önce programa ait eski engelleme kurallarını siler, sonra yalnız yerel alt
     ağdan (`LocalSubnet`) gelen TCP bağlantılarına izin veren "Kutuphane
     Defteri Katalog" kuralını ekler (Etki alanı, Özel ve Genel profilleri).
     Port, kayıt defterindeki `HKLM\SOFTWARE\KutuphaneDefteri\KatalogPortu`
     değerinden okunur, yoksa 8765'tir. Kural tek başına bir şey açmaz; Ağ
     Kataloğu program içinden ayrıca açılır (§8).
5. Bilgisayarda Microsoft Edge WebView2 yoksa kurulum onu da kurar. Gömülü önyükleyici
   internet ister; ağı kısıtlı bilgisayarda WebView2'yi önceden kurun.

Kurulum klasöründe (`C:\Program Files\Kütüphane Defteri`) programın lisansı
(`LICENSE.txt`) ve pakete giren üçüncü taraf bileşenlerin lisans metinleri de bulunur
(`THIRD_PARTY_LICENSES\`; dizini, LGPL bileşenlerinin kaynak adresleri ve kaynak kodu için
yazılı teklif `BENIOKU.txt`'de — istek yolu programın GitHub deposunun Issues sayfasıdır).

İmzasız paket olduğu için SmartScreen "tanınmayan uygulama" uyarısı verebilir:
"Ek bilgi" → "Yine de çalıştır". Önce §9'daki SHA-256 doğrulamasını yapın.

Program açıkken kurulum ya da kaldırma başlatılırsa kurulum programa kapanma
isteği gönderir ve 30 saniyeye kadar bekler; program düzenli kapanır (görevli
kipinde de). Program kapanmazsa kurulum penceresi "tepsideki simgeden Çık'ı seçin"
iletisini gösterir. Program zorla kapatılmaz.

### 3.2 Güncelleme

Her güncelleme de yönetici yetkisi ister; BTR'nin UAC'ye kimlik girmesi
gerekir. Güncelleme sırasında güvenlik duvarı kuralına dokunulmaz:
değiştirilmiş port ve BTR'nin eklediği ağ blokları korunur. Program her sürüm
geçişinden önce kendiliğinden bir yedek alır.

Yeni sürümü görmek için Ayarlar → Güncelleme → **Şimdi denetle**. Kurulum dosyasını
indirip masa hesabında çalıştırın (§3.1'deki gibi).

**Ön sürüm (beta).** Adında `-beta.` geçen sürümler ön sürümdür; GitHub'da "Pre-release"
diye işaretlidir. Ön sürüm kullanan bilgisayar hem sonraki ön sürümü hem kararlı sürümü
görür (yayımlananların en yenisi önerilir); kararlı sürüm kullanan bilgisayara ön sürüm
önerilmez.

Program yayımlanan son sürümü yalnız bu düğmeyle ve **GitHub'dan** sorar (açılışta
internete çıkmaz; kurulum dosyası da GitHub'dan, SHA-256 özetiyle doğrulanarak
indirilir). MEB ağında GitHub'a erişim kapalı olabilir; o zaman ekranda şu ileti
çıkar: "GitHub'a ulaşılamadı; okul ağında engellenmiş olabilir. Yeni sürümü
indir.okulapp.org'dan elle denetleyebilirsiniz." İletinin altındaki
`okulapp.org/kutuphane-defteri` bağlantısı programın sayfasını bilgisayarın
tarayıcısında açar: yeni sürüm oradadır, kurulum dosyası `indir.okulapp.org`'dan
iner (§2). Dosyayı §9'daki gibi doğrulayın. Program `indir.okulapp.org`'a ve
programın sayfasına kendisi istek atmaz; bağlantıyı tarayıcı açar. BTR okul ağında
GitHub'a erişim isterse hedefler ve sınama komutları Ağ Hizmeti Bilgi Notu'nda
yazılıdır; erişim talebi Yardım Masası Modülü'nden açılır (§8.7'deki yol).

"GitHub ile güvenli bağlantı doğrulanamadı…" iletisi ağ engeli değildir: önce
bilgisayarın tarih ve saatini denetleyin (yanlış saatte sertifika geçersiz görünür);
saat doğruysa okul ağı güvenli bağlantıları araya girerek denetliyor olabilir, BTR'ye
bildirin. Program doğrulamayı gevşetmez.

### 3.3 Taşınabilir sürüm (kurulum yapmadan)

`...portable.zip` dosyasını bir klasöre açın, `kutuphane-defteri.exe`'yi
çalıştırın. Veriler yine `%LOCALAPPDATA%\KutuphaneDefteri` altına yazılır; zip'i
silmek verileri silmez. Taşınabilir sürümde **Ağ Kataloğu sunulmaz** ve otomatik
başlatma yoktur: kurulumun güvenlik duvarı kuralı kurulu programın yoluna bağlıdır,
bu yüzden güvenlik duvarı denetimi geçmez ve katalog okul ağına açılmaz. Ağ
Doktoru'ndaki “Kuralı ekle/güncelle” düğmesi (yönetici izni ister) kuralı taşınabilir
sürümün kendi yoluna yazarsa katalog açılır; aynı bilgisayarda kurulu program varsa
kural onunkinin yerini alır ve kurulu programın katalogu açılmaz olur. Bu yol
önerilmez: Ağ Kataloğu gerekiyorsa programı kurulum dosyasıyla kurun (§3.1).
Pardus'un taşınabilir arşivinde katalog hiç açılmaz (§4.2).

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
durur; isteyen kendi sürümüyle değiştirebilir. Programın ve üçüncü taraf
bileşenlerin lisans bildirimleri `/usr/share/doc/kutuphane-defteri/` altındadır
(`copyright` ve `THIRD_PARTY_LICENSES/BENIOKU.txt`; LGPL bileşenlerinin kaynak
adresleri ve kaynak kodu için yazılı teklif de oradadır).

**Güncelleme:** önce programdan **Çık** (tepsiden ya da üst çubuktan), sonra yeni
`.deb`'i aynı komutla kurun. Windows kurulumunun açık programa gönderdiği kapanma isteği
Pardus paketinde YOKTUR: program açıkken kurulum yapılırsa dosyalar çalışan programın
altında değişir. Kaldırmadan (`sudo apt remove kutuphane-defteri`) önce de programdan
çıkın.

### 4.2 Taşınabilir arşiv ile (sistem yöneticisi yetkisi gerekmez)

```bash
tar -xzf kutuphane-defteri-<sürüm>-linux-x64.tar.gz
cd kutuphane-defteri-<sürüm>
./kur.sh
```

`kur.sh` programı kullanıcı klasörüne kurar ve menü kaydını ekler. Kaldırmak
için `./kaldir.sh`. Taşınabilir arşivde **Ağ Kataloğu açılamaz** (Windows'un
taşınabilir sürümünde de sunulmaz, §3.3); ufw profili ve firewalld servis tanımı da
yalnız `.deb` paketiyle gelir. Katalog gerekiyorsa programı `.deb` paketiyle kurun
(§4.1) — **önce** taşınabilir sürümden çıkıp arşivdeki `./kaldir.sh` ile kaldırın.
Kaldırılmazsa `kur.sh`'in eklediği menü kaydı ve uçbirim kısayolu (`~/.local/bin`)
`.deb`'inkinin önüne geçer: menü ve `kutuphane-defteri` komutu taşınabilir sürümü
açmayı sürdürür, katalog açılmaz (program bu durumu tanır ve `./kaldir.sh`'i
söyler). Hangi sürümün açıldığını uçbirimde `kutuphane-defteri --dagitim-duman`
yazar ("kurulu" ya da "tasinabilir"). İki sürüm aynı veri klasörünü kullanır
(`~/.local/share/kutuphane-defteri`); `./kaldir.sh` verilere dokunmaz.

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
2. **Kütüphane aydınlatma metni** e-Okul aktarımından önce duyurulur. Metni
   **Kişiler → Üyeler** sekmesinin altındaki **Üyelik Belgeleri** bölümünden
   basarsınız: okul adı, ilçe ve müdür adı **Ayarlar → Okul Bilgileri**'nden
   gelir; başvuru adresi ve iletişim bilgisi yalnız o basıma yazılır. Aynı
   bölümdeki **Masa kartı** masada görev yapan öğrenciye göreve başlamadan
   verilir.
3. Öğrenci ve personel listelerini e-Okul'un Excel raporlarından aktarırsınız
   (TCKN istenmez ve tutulmaz): öğrenci için *OOG01001R020 — Sınıf/Şube
   Öğrenci Listesi*, personel için *OOK01001R1 — Personel Listesi*. e-Okul
   dosyaları `.XLS` uzantısıyla iner; açıp düzenlemeniz gerekmez. Aktarmadan
   önce **Önizle** hiçbir şey yazmadan etkisini gösterir.
4. Kitap listesi varsa Excel şablonuyla aktarılır; hazır liste yoksa (çoğu okulda
   böyledir) **önce etiket** yolu izlenir: boş barkod etiketleri basılıp kitaplara
   yapıştırılır, kitap Hızlı Kayıt'ta okutularak kaydedilir (kılavuzda anlatılır).

**Pencere ve tepsi.** Pencerenin çarpı düğmesi programı kapatmaz, pencereyi
gizler; program saatin yanındaki simge alanında (tepside) çalışmaya devam
eder. Programı kapatmak için üst çubuktaki **Çık** düğmesini ya da tepsideki
simgenin menüsünden **Çık**'ı seçin: program Ağ Kataloğunu kapatır ve
veritabanını tek dosyada toparlayarak düzenli kapanır.

- Görevli kipinde Çık **yönetici parolası** ister (tepsiden seçilirse pencere
  öne gelir ve parola orada sorulur). Bu koruma kaza önleyicidir, güvenlik
  sınırı değildir: Görev Yöneticisi süreci her durumda kapatabilir.
- Yönetici kipinde ve kilitliyken üst çubuktaki Çık yalnız onay ister;
  tepsiden seçilen Çık onay sormadan kapatır.
- Tepsi menüsü kipe göre değişir: Ağ Kataloğunu açıp kapatma ve "Görevli
  kipine geç" yalnız yönetici kipindedir; kilitliyken menüde pencere, Ağ
  Kataloğunun durumu ve Çık kalır.
- Masaüstünde sistem tepsisi yoksa (bazı Pardus masaüstleri) çarpı pencereyi
  küçültür; çıkış yolu üst çubuktaki Çık düğmesidir.

**Oturum açılmadan program çalışmaz.** Windows oturumu açılmadan ne program ne
Ağ Kataloğu kalkar. Bilgisayar sabah açıldığında masa hesabında oturum açın.

## 6. Verileriniz nerede? Yedekleme

| İçerik | Windows | Pardus/Linux |
|---|---|---|
| Veritabanı + ayarlar | `%LOCALAPPDATA%\KutuphaneDefteri\data` | `~/.local/share/kutuphane-defteri/data` |
| Otomatik yedekler | `%LOCALAPPDATA%\KutuphaneDefteri\backups` | `~/.local/share/kutuphane-defteri/backups` |
| Günlükler | `%LOCALAPPDATA%\KutuphaneDefteri\logs` | `~/.local/state/kutuphane-defteri/logs` |

Program **her gün** o güne ait bir otomatik yedek alır
(`gunluk-<tarih>.kdbak`): açılışta ve program açık kaldığı sürece gün
değişince (aşağıdaki "Gün değişimi"). Aynı gün ikinci yedek almaz; yedekleri 14
gün saklar ve her sürüm güncellemesinden önce ayrıca bir yedek bırakır
(`pre-migrate-<sürüm>-<tarih>.kdbak`, son 5 adet). Saklama işlemi (Ayarlar →
Saklama) onaylanınca işlemden hemen önce bir yedek daha alınır
(`pre-anonim-<tarih>-<saat>.kdbak`); günlük yedekler gibi 14 gün saklanır ve işlem
kendinden önce alınmış `pre-migrate` yedeklerini siler (§6.3). Yedekler şifrelidir ve
ancak yönetici parolası ya da kurtarma anahtarıyla açılır. Yönetici parolası
kurulmadan (ilk açılış) yedek alınmaz; ilk yedek parola kurulduktan sonraki ilk
denetimde, en geç bir saat içinde alınır.

Program yedek klasöründe yalnız bu üç adla başlayan dosyaları yönetir. Klasöre elle
konan dosyaları (ör. taşımada kopyalanan yedek) silmez; gerekmiyorlarsa onları
kütüphane yöneticisi siler. Geri yüklemenin `data` klasöründe kenara aldığı
`db-onceki-<tarih>-<saat>.sqlite3` dosyalarını (ve `-wal`/`-shm` eşlerini) geri yükleme
silmez; saklama işlemi onaylanınca adındaki tarih işlem anından 14 günden eski olanlar
silinir (§6.3). Daha yenilerini gerekmiyorlarsa kütüphane yöneticisi siler.

**Gün değişimi.** Program tepside günlerce açık kalabilir. Günlük işler bu
yüzden açılışa değil tarihe bağlıdır: program açılışta ve açık kaldığı sürece
saatte bir tarihi denetler; gün değiştiyse o günün yedeğini alır, 14 günden
eski yedekleri siler, çok okunanlar listesini yeniler, saklama süresi dolan
kayıtları tarar (tarama hiçbir kaydı değiştirmez; silme ve anonimleştirme yalnız
yöneticinin onayıyla yapılır, §6.3) ve bilgisayarın ağ adresini denetler (adres değiştiyse Ağ
Doktoru'nun "Katalog Durumu" kartında "… Afişi yeniden basın, yer imlerini
güncelleyin." uyarısı çıkar, §8.3). Bir iş yapılamazsa (ör. parola henüz
kurulmadıysa) bir saat sonra yeniden denenir. Yedek için kilidin açılması
gerekmez; kayıtlar kilitliyken de alınır. Bilgisayar kapalıyken ya da uykudayken
yedek alınmaz; uykudan uyanan bilgisayarda en geç bir saat içinde alınır.

Yedekler bilgisayarın kendisindedir: disk bozulursa onlar da gider. Ayda bir
Ayarlar → Güvenlik'ten **şifreli yedek indirip** USB belleğe alın ve USB'yi
bilgisayardan ayrı saklayın (kural §6.3).

**USB belleğe yedek hatırlatması.** Program son şifreli yedek indirmesinin tarihini veri
klasöründe (`data/dis-yedek.json`; kişisel veri yok) tutar. Son indirmeden 30 gün
geçince — hiç indirme yoksa yönetici parolası kurulduktan 7 gün sonra — Genel
Bakış'ta **Şifreli Yedeği USB Belleğe Alın** kartı çıkar. Süre Ayarlar → Güvenlik →
"Şifreli Veritabanı Yedeği" kartından 7-90 gün arasında değiştirilir. Program
dosyanın USB belleğe gerçekten kopyalandığını bilemez; kart son indirmeyi söyler.
Tarih veritabanında olmadığı için yedekten geri yükleme onu geri sarmaz; yeni
bilgisayarda kart, orada ilk indirme yapılana dek görünür.

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
`db-onceki-<tarih>` adıyla `data` klasöründe saklanır (saklama işlemi bu dosyalardan
14 günden eski olanları siler, §6.3). İşlem bitince programı
normal açın. `data` klasöründeki `verilmis-kartlar.txt` dosyasını silmeyin: verilmiş
üye kartı numaralarının (kişisiz) listesidir ve geri yüklenen yedekten sonra
basılmış kartların numarasının başka bir üyeye yeniden verilmesini önler.

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

### 6.3 Saklama işlemi ve USB bellekteki yedekler

Program süresi dolan kişisel verileri her gün tarar ama **kendiliğinden hiçbir şey
silmez**: silme ve kişiyle bağı koparma (anonimleştirme) kütüphane yöneticisinin
Ayarlar → Saklama'daki onayıyla, tek seferde yapılır (süreler ve kurallar programın
Kullanım Kılavuzu'ndaki "Saklama ve Anonimleştirme" bölümündedir). İşlem veritabanını
değiştirir; kayıtların eski hâli bir süre daha yedeklerde kalır:

- günlük yedeklerde ve işlemden hemen önce alınan `pre-anonim` yedeğinde en çok
  14 gün (sonra kendiliğinden silinir);
- `pre-migrate` yedeklerinde kalmaz: işlem, kendinden önce alınmış güncelleme
  öncesi yedekleri siler;
- `data` klasöründeki `db-onceki-<tarih>` dosyalarında (geri yüklemenin kenara aldığı
  önceki veritabanı): işlem, adındaki tarih işlem anından 14 günden eski olanları
  `-wal`/`-shm` eşleriyle siler; daha yenileri yakın tarihli bir geri yüklemeden dönüş
  için kalır, gerekmiyorlarsa kütüphane yöneticisi siler;
- yedek klasörüne elle konan dosyalarda: program bunlara dokunmaz, gerekmiyorlarsa
  kütüphane yöneticisi siler;
- indirilip USB belleğe (ya da okulun ağ diskine) alınan yedeklerde: bunlar
  programın dışındadır.

**USB bellekteki yedekler okulun sorumluluğundadır.** Program onlara ulaşamaz ve
onları silemez; saklanmalarının ve silinmelerinin düzenini okul müdürlüğü belirler.
Personel USB bellekteki ve harici diskteki bilgilerin güvenliğini sağlar; bu
ortamlara konan önemli veri şifrelenerek saklanır (Bilgi ve Sistem Güvenliği
Yönergesi md. 10/5). Önerilen düzen (okul müdürlüğü başka bir düzen belirleyebilir):

1. İndirilen yedek bilgisayarın İndirilenler klasörüne düştüyse USB belleğe
   **taşıyın**; bilgisayarda kopya bırakmayın, Geri Dönüşüm Kutusu'nu da denetleyin.
   Yedeği e-postayla göndermeyin, ortak klasöre ya da bulut depolama hizmetine
   koymayın (Yönerge md. 11/23).
2. USB bellekte **son iki yedeği** tutun; yenisini alınca daha eskilerini silin.
3. **Saklama işleminden sonra** yeni bir şifreli yedek alın ve işlemden önce alınmış
   USB yedeklerini silin: eski yedekler silinen kayıtları taşımayı sürdürür.
   Saklama ekranının "Son İşlem" kartı, işlemden sonra şifreli yedek indirilmediyse
   bunu hatırlatır.
4. **Görev devrinden sonra** (§1.6) yeni bir şifreli yedek alın ve devirden önce
   alınmış USB yedeklerini silin: onlar eski parolayla ve eski kurtarma anahtarıyla
   açılır; eski parola onlarla birlikte devirden sonraki yedekleri de açtırır.
5. Belleği başka bir işe vermeden ya da elden çıkarmadan önce içindeki yedekleri
   silin.
6. Bellek kaybolur ya da çalınırsa durumu hemen okul müdürlüğüne bildirin. Yedek
   şifrelidir; başka bir bilgisayarda ancak alındığı günün yönetici parolasıyla ya
   da o günün kurtarma anahtarıyla açılır, bugünkü parolayı değiştirmek onu korumaz.
   Kişisel verilerin kanuni olmayan yollarla başkalarınca elde edilmesi hâlinde
   yapılacak bildirimi (KVKK md. 12/5) okul müdürlüğü değerlendirir.

## 7. Yeni bilgisayara taşıma — kontrol listesi

Bilgisayar değişirse, yeniden kurulursa ya da disk değişirse sırayla:

1. [ ] Eski bilgisayarda Ayarlar → Güvenlik'ten **şifreli yedek** indirin ve
       USB'ye alın. Yönetici parolasının ya da kurtarma anahtarının elinizde
       olduğunu doğrulayın. Yedeği taşımadan hemen önce alın: sonra yapılan
       ödünç ve iadeler yedekte olmaz.
   [ ] Aynı USB'ye eski bilgisayarın `data` klasöründeki
       **`verilmis-kartlar.txt`** dosyasını da kopyalayın (kişisel veri yoktur;
       verilmiş üye kartı numaralarının kişisiz listesidir). Yedekten sonra
       basılmış bir kartın numarası yeni bilgisayarda başka bir üyeye verilmesin.
2. [ ] Yeni bilgisayarın **okul demirbaşı** olduğunu doğrulayın (§1.1) ve
       **kütüphane masası hesabını** açın (§1.2). Disk şifrelemesini açın
       (§1.3).
3. [ ] Programı masa hesabında, BTR'nin UAC kimliğiyle **kurun** (§3.1).
       "Yerel ağdan katalog taramasına izin ver" seçeneğini işaretleyin. Kurulumun
       sonunda program açılırsa kurulum sihirbazında parola kurmadan kapatın;
       kurduysanız sorun değil: geri yükleme o kurulumun güvenlik dosyasını
       `guvenlik-arsiv-*.json`, boş veritabanını `db-onceki-*` adıyla kenara alır
       (bu durum da geri yükleme provasında sınanır).
4. [ ] İndirdiğiniz şifreli yedeği **geri yükleyin** (§6.1; programı önce
       açmanız gerekmez). Yedek, eski bilgisayarın yönetici parolasıyla ya da
       kurtarma anahtarıyla açılır; güvenlik dosyası yedeğin içinden yeniden
       kurulur. Geri yükleme veri klasörünü oluşturur: programı açmadan önce
       `verilmis-kartlar.txt`'yi yeni bilgisayarın `data` klasörüne koyun.
5. [ ] Programı açın; kilidi aynı parolayla açın. Kitap, üye ve açık ödünç
       sayılarını eski bilgisayardaki son durumla karşılaştırın. Sayılar tutunca
       `backups` klasörüne kopyaladığınız yedek dosyasını silin: program elle konan
       dosyayı kendisi silmez (§6), USB'deki kopya yeter. Genel Bakış'taki
       **Şifreli Yedeği USB Belleğe Alın** kartı yeni bilgisayarda ilk indirmeye dek
       görünür: yeni bilgisayardan da bir şifreli yedek indirip USB'ye alın.
6. [ ] Ağ Kataloğu kullanılıyorsa: Ağ Doktoru'nda **güvenlik duvarı**
       denetiminin beş maddesinin geçtiğini görün. Yedekteki port varsayılandan
       (8765) farklıysa yeni bilgisayarın kuralı kurulumda varsayılan portla
       yazılmıştır ve port maddesi geçmez: Ağ Doktoru'ndaki **Kuralı
       ekle/güncelle** kuralı ve kayıt defteri değerini ayardaki portla yeniden
       yazar (UAC, §8.2).
7. [ ] BTR'den **sabit adres ayırmayı yeni bilgisayarın ağ kartına (MAC
       adresine)** taşımasını isteyin (§8.3). Aksi hâlde bilgisayarın IP adresi
       değişir ve eski adres çalışmaz.
8. [ ] IP adresi değiştiyse **katalog afişini** yeniden basın, tahtalardaki ve
       bilgisayarlardaki **yer imlerini** güncelleyin.
9. [ ] Eski bilgisayardaki veri klasörünü, yedekleri ve günlükleri (§6), yeni
       kurulum çalıştıktan sonra silin (programı kaldırmak onları silmez, §12);
       İndirilenler klasörünü ve Geri Dönüşüm Kutusu'nu da denetleyin. USB
       bellekteki yedekleri §6.3'teki düzene göre saklayın.

Bu akış program içinde "temiz makinede geri yükleme provası" olarak sınanır: boş
veri klasörüne şifreli yedek geri yüklenir, program açılır, kilit aynı parolayla ve
kurtarma anahtarıyla açılır; kişi adları, okul numaraları, katalog, üyelik ve açık
ödünç birebir aynı çıkar. Taşınan `verilmis-kartlar.txt` yedekten sonra verilmiş kart
numarasının yeniden verilmesini engeller; taşınmazsa bu güvence kalmaz. Daha yeni bir
sürümün yedeği eski programa geri yüklenirse program açılmaz (§10.4): önce programı
güncelleyin.

### 7.1 Geri yükleme provası (okulun kendi denemesi)

Yedeğinizin gerçekten açıldığını görmek isterseniz (ör. bilgisayar değişmeden önce
ya da yılda bir) aynı provayı okulun **başka bir demirbaş bilgisayarında** (§1.1)
yapın. Prova kütüphane bilgisayarındaki veriye dokunmaz.

1. [ ] Kütüphane bilgisayarında şifreli yedek indirip USB'ye alın; kurtarma
       anahtarının kâğıdını yanınıza alın.
2. [ ] Prova bilgisayarına programı kurun ya da Windows'ta taşınabilir sürümü bir
       klasöre açın (§3.3; kurulum ve güvenlik duvarı kuralı gerekmez).
3. [ ] Yedeği o bilgisayarın `backups` klasörüne kopyalayın ve geri yükleme aracını
       çalıştırın (§6.1; taşınabilir sürümde Başlat menüsü kısayolu yoktur:
       `kutuphane-defteri.exe --geri-yukle`). Parola yerine **kurtarma anahtarını**
       yazın; böylece kâğıttaki anahtarın da işlediğini görürsünüz.
4. [ ] Programı açın, kilidi yönetici parolasıyla açın; kitap, üye ve açık ödünç
       sayılarını kütüphane bilgisayarındakilerle karşılaştırın. Provada kayıt
       girmeyin.
5. [ ] Programdan **Çık** ile çıkın ve prova bilgisayarındaki veri, yedek ve günlük
       klasörlerini silin (Windows'ta `%LOCALAPPDATA%\KutuphaneDefteri`; Pardus'ta
       `~/.local/share/kutuphane-defteri` ve `~/.local/state/kutuphane-defteri`).
       Programı kurduysanız kaldırın; kaldırmak bu klasörleri silmez (§12).

Kâğıttaki anahtar yedeği açmazsa kütüphane bilgisayarındaki kayıtlar yerindedir:
orada Ayarlar → Güvenlik → **Kurtarma Anahtarını Yenile** ile yeni bir anahtar üretip
saklayın, yeni bir şifreli yedek alın ve provayı o yedekle tekrarlayın.

## 8. Ağ Kataloğu

Ağ Kataloğu, okul ağındaki bilgisayarların ve etkileşimli tahtaların kütüphane
kataloğunu tarayıcıyla, salt okur olarak taramasını sağlar. **Kişisel veri
göstermez:** üye, ödünç alan, iade tarihi ya da ödünç geçmişi yoktur; yalnız
künye, sınıflama kodu, yer numarası, bölüm ve nüshaların durumu (rafta,
ödünçte, sınıf kitaplığında, onarımda) görünür. Bir nüshanın ödünçte olduğu
görünür, kimde olduğu ve ne zaman döneceği görünmez. Arama kaydedilmez, erişim
günlüğü tutulmaz. Katalog kişisel veri taşımadığı için program kilitliyken de
çalışır.

Varsayılan olarak **kapalıdır** ve yalnız yönetici kipinde açılır. Açıldığında
program okul ağına bir port (varsayılan 8765) üzerinden hizmet verir; bu
yüzden açmadan önce okul BTR'sinin bilgisi alınır ve program BTR ile müdürün
imzalayacağı bir **Ağ Hizmeti Bilgi Notu** üretir. BTR için ayrıntılı ağ
kılavuzu [`docs/ag-kurulumu.md`](ag-kurulumu.md)'dir.

Ağ Kataloğu yalnız **hizmet verir**, internete hiç çıkmaz: giden bağlantı bu
bölümün konusu değildir (bkz. belgenin başındaki iki kapı).

### 8.1 Açma

1. Ayarlar → **Ağ Kataloğu** sekmesini açın. İlk açılışta sekmenin başında
   **Ağ Kataloğunu Açmadan Önce** adımları durur.
2. **BTR'yle görüşün:** port, güvenlik duvarı kuralı ve bilgisayarın adresinin
   sabit kalması (DHCP'de sabit adres ayırma, §8.3) konuşulur. Ağ Hizmeti Bilgi Notu'nu basıp
   BTR'ye ve okul müdürüne imzalatın; not okulda saklanır. İzin değil bilgi
   notudur.
3. **Güvenlik duvarı:** Windows'ta kurulumda "Yerel ağdan katalog taramasına
   izin ver" seçildiyse kural hazırdır. Ağ Doktoru'nda beş denetimin geçtiğini
   görün (§8.2). Pardus'ta kuralı BTR açar (§8.5).
4. **Adres:** tek ağ bağlantılı bilgisayarda "Bu bilgisayarın bütün ağ
   bağlantılarında" yeterlidir. İkinci ağ kartı varsa "Yalnız seçili IP
   adresinde" seçeneğiyle katalog yalnız okul ağına açılır.
5. **Ağ Kataloğunu aç** düğmesine basın.
6. Ağ Doktoru'ndan **afişi basın** ve **yer imi dosyalarını** üretip BTR'ye
   verin (§8.4). Afiş basıldıktan sonra adımlar gizlenir.

Katalog tepsiden de açılıp kapatılabilir (yalnız yönetici kipinde). Ayar
kalıcıdır: program yeniden açıldığında katalog da açılır. Windows oturumu
açılmadan ne program ne katalog çalışır. Ağ Kataloğu kurulu programda sunulur:
Windows'un taşınabilir sürümünde ve Pardus'un taşınabilir arşivinde sunulmaz
(§3.3, §4.2).

### 8.2 Ağ Doktoru ve güvenlik duvarı (Windows)

Ağ Doktoru (Ayarlar → Ağ Kataloğu → **Ağ Doktoru**) yalnız yönetici kipinde
açılır. Kataloğun durumunu, portu, bu bilgisayarın ağ bağlantılarını ve
adreslerini, ağ profilini, katalog adresini ve QR kodunu, son hatayı ve günlük
sayfa ve arama sayılarını gösterir.

**Beş denetim.** Katalog okul ağına ancak şunların hepsi tutarsa açılır:

1. programa ait bir gelen izin kuralı var ve etkin;
2. kuraldaki program bu bilgisayardaki `kutuphane-defteri.exe`;
3. kuraldaki port ayardaki portla aynı;
4. kural bu bilgisayarın etkin ağ profilini (Genel, Özel, Etki alanı) kapsıyor
   (uzak adres "her yer" ise uyarı verilir ama dinleme engellenmez);
5. program için bir gelen **engelleme** kuralı yok (eski "Windows Güvenlik
   Uyarısı" penceresinde "İptal"e basılmışsa böyle bir kural kalmış olabilir).

Denetim güvenlik duvarının yapılandırmasını doğrudan okur. Biri tutmazsa ya da
denetim okunamazsa katalog **hiç dinlemez** ve Ağ Doktoru durumu "Güvenlik
duvarı izni yok" olarak gösterir. **Kuralı ekle/güncelle** düğmesi kuralı yeniden
yazar, programa ait engelleme kurallarını siler ve portu kayıt defterine
yazar; Windows yönetici onayı (UAC) ister, kimliği BTR girer. Kurala Ayarlar →
Ağ Kataloğu'ndaki **tahta ağı blokları** da (yerel alt ağa ek olarak) eklenir.

**Dinleyici sınaması.** "Dinleyiciyi sına" kataloğun bu bilgisayardaki her ağ
bağlantısında yanıt verdiğini sınar. Bu sınama güvenlik duvarını ya da VLAN'ı
**kanıtlamaz**: bilgisayarın kendi adresine yapılan bağlantı ağa çıkmaz. Asıl
kanıt okul ağındaki başka bir Windows bilgisayarda PowerShell'de alınır:

```powershell
Test-NetConnection <IP> -Port <port>
```

`TcpTestSucceeded : True` görülmelidir. Ağ Doktoru komutu gerçek adres ve portla
hazır verir.

**Üçüncü parti güvenlik yazılımları.** Bazı antivirüs programlarının kendi
güvenlik duvarı Windows kuralını yok sayabilir. Beş denetim geçtiği hâlde başka
bilgisayardan erişilemiyorsa o yazılımda da `kutuphane-defteri.exe` için
yerel ağdan gelen bağlantıya izin verilmelidir.

### 8.3 Adres ve ağ

- **Adres sabit kalmalıdır.** BTR, DHCP'de bu bilgisayarın ağ kartına (MAC
  adresine) sabit adres ayırır (teknik adı: DHCP rezervasyonu) ya da bunu yetkili
  birimden ister. Kütüphane
  yöneticisi bilgisayarın adresini elle değiştirmez: IP ve MAC adresi yalnız
  Bakanlıkça yetkilendirilmiş kişilerce değiştirilir (Bilgi ve Sistem
  Güvenliği Yönergesi md. 11/6).
- **Adres değişirse** afiş ve yer imleri eski adresi gösterir. Program gün
  değişiminde adresi denetler; son basılan afişteki adresten farklıysa Ağ
  Doktoru'nun "Katalog Durumu" kartında "Bu bilgisayarın IP adresi değişti
  (… → …). Afişi yeniden basın, yer imlerini güncelleyin." uyarısı çıkar.
  Afişi yeniden basın (uyarı yeni afişle kalkar), yer imi dosyalarını yeniden
  üretip eskilerin yerine koyun ve Ağ Hizmeti Bilgi Notu'nu yenileyin; PYS
  talebi açıldıysa yeni adresi bildirin. "Yalnız seçili IP adresinde"
  seçiliyken seçili adres kaybolursa: bilgisayarın tek adresi varsa katalog o
  adreste açılır ve aynı uyarıyı verir, birden çok adresi varsa açılmaz; adres
  Ayarlar → Ağ Kataloğu → Dinleme'den yeniden seçilir.
- **Tahta ağı.** İdari ağ ile tahta ağı çoğu okulda ayrı bölümlerdedir; aradaki
  geçiş okulda değiştirilemez. Tahtalardan erişim yoksa Ağ Doktoru'ndaki
  **PYS talep metnini kopyala** düğmesi "yerel ağ VLAN düzenlemesi — tek yön"
  talebini hazırlar; BTR müdürlük onayıyla FATİH PYS'ye girer.
- **İkinci ağ kartı ya da bilgisayarı tahta ağına bağlamak** yalnız ilçe
  sistem yöneticisinin uygun görüşüyle yapılır. Ağ Doktoru ikinci karttaki
  "katalog bu ağda da erişilebilir" durumunu ve IP yönlendirmenin açık olup
  olmadığını gösterir.

### 8.4 Afiş ve yer imleri

- **Afiş:** adres büyük ve birincildir, QR kodu küçük ve ikincildir (okul
  bilgisayarları ve tahtalar QR okumaz). Afiş basılınca adres hatırlanır.
- **Yer imi dosyaları** (tek arşiv):
  - `pardus-etap/kutuphane-katalogu-chromium.json` → ETAP/Pardus'ta
    `/etc/chromium/policies/managed/` altına: Chromium'un bütün hesaplarda
    görünen yönetilen yer imi;
  - `pardus-etap/kutuphane-katalogu.desktop` → `/usr/share/applications/`
    altına: uygulama menüsü kısayolu (varsayılan tarayıcıda açar);
  - `windows/Kutuphane-Katalogu.url` ve `Kutuphane-Katalogu-Tahta.url` →
    Windows bilgisayarlar ve Windows tahtalar için internet kısayolu.

  Tahtaya giden yer imleri kataloğu büyük dokunma düzeninde (tahta kipi)
  açar; adresin sonunda `?tahta=1` vardır. Kullanıcı başına yer imi yetmez:
  ETAP her öğretmene tahtada ayrı hesap açar ve bir hesaba eklenen yer imi
  öbürlerinde görünmez. Politika dosyası bütün hesaplarda görünür; toplu
  dağıtım (ör. Liderahenk) BTR'nin yetkisindedir.

### 8.5 Pardus

Program Pardus'ta güvenlik duvarı kuralı **açmaz**; paket ufw uygulama profilini
(`/etc/ufw/applications.d/kutuphane-defteri`) ve firewalld servis tanımını
(`/usr/lib/firewalld/services/kutuphane-defteri.xml`) bırakır. Ağ Doktoru
bilgisayardaki aracı ve BTR'nin çalıştıracağı komutu gösterir. Komut **kaynak
sınırlıdır**: yalnız bu bilgisayarın yerel ağına ve Ayarlar → Ağ Kataloğu'ndaki
tahta ağı bloklarına izin verir, her blok ayrı satırdır (Windows kuralındaki
`LocalSubnet` + bloklar kapsamının karşılığı; RFC1918'in tamamı ya da "her yer"
açılmaz, çünkü MEB WAN'ındaki başka kurumlar da özel adres aralığındadır):

```bash
sudo ufw allow from <yerel-ağ> to any app 'Kutuphane Defteri'
sudo ufw allow from <tahta-ağı> to any app 'Kutuphane Defteri'
# firewalld kullanılıyorsa (her blok için bir zengin kural):
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="<yerel-ağ>" service name="kutuphane-defteri" accept'
sudo firewall-cmd --reload
```

Port 8765'ten farklıysa profil yerine port açılır (`sudo ufw allow from <blok> to any
port <port> proto tcp`; firewalld'de zengin kuralda `port port="<port>" protocol="tcp"`).
Taşınabilir arşivde Ağ Kataloğu açılamaz ve Ağ Doktoru komut vermez (§4.2); bu
tanımlar ve komutlar `.deb` ile kurulmuş program içindir (taşınabilir sürüm önce
`./kaldir.sh` ile kaldırılır).

### 8.6 Port değişikliği ve uyku

- **Port** Ayarlar → Ağ Kataloğu → **Portu değiştir** ile değişir. Windows'ta
  güvenlik duvarı kuralı ve kurulumun okuduğu kayıt defteri değeri de yeni
  portla yazılır; UAC onayı verilmezse port değişmez. Port değişince afişi,
  yer imlerini ve Ağ Hizmeti Bilgi Notu'nu yenileyin. Güncellemelerde kural ve
  port korunur (§3.2).
- **Uyku:** Ağ Kataloğu açıkken bilgisayarın boşta uykuya geçmesi engellenir;
  kapak kapatma ya da elle uyutma engellenmez. Ayarlar → Ağ Kataloğu → Uyku
  bölümünden kapatılabilir.

### 8.7 ISBN ile künye getirme — BTR sınaması

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

Çıkan özet `SHA256SUMS.txt` içindeki satırla birebir aynı olmalıdır (dosyaları
`indir.okulapp.org`'dan indirdiyseniz özet dosyasının adı `SHA256SUMS-<sürüm>.txt`'dir;
komuttaki adı ona göre yazın).

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

### 10.4 "Program sürümü eski" (eski program, yeni veri)

İleti başlığı **Program sürümü eski**, metni "Bu veri, programın daha yeni bir
sürümüyle oluşturulmuş. …" Bilgisayardaki program eski, veri yeni: veri daha yeni
bir sürümle açılıp güncellenmiş, sonra bilgisayara eski sürüm kurulmuş (ya da eski
kurulum dosyası yeniden çalıştırılmış). Program veriyi korumak için açılmaz;
veritabanını kendi eski düzenine göre güncellemeye kalkışmadan durur. Programı son
sürüme güncelleyin; veri dosyasına dokunmayın.

Aynı ileti ("… daha yeni bir sürümüyle güncellenmiş: veritabanında bu sürümün
tanımadığı değişiklikler var …") daha yeni bir sürümle alınmış bir yedeği eski
programa geri yükleyince de çıkar: geri yükleme sürüm damgasını (`data/surum.json`)
siler, program bu kez veritabanının kendi güncelleme kaydına bakar. Çözüm yine
programı güncellemektir; eski programla açmak veriyi bozardı. Çıkış kodu 4'tür (§11).
Programın tanımadığı değişikliklerin listesi iletide değil günlük dosyasındadır
(`logs/uygulama.log`, §6'daki tablo); sorunu bildirirken BTR onu oradan alır.

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
| 4 | Veri, programdan yeni bir sürümle yazılmış (sürüm damgası ya da veritabanının güncelleme kaydı; daha yeni sürümün yedeği eski programa geri yüklendiyse de) | programı güncelleyin (§10.4) |
| 5 | Veritabanı güncellenemedi (migrate) | `backups` içindeki `pre-migrate-*` yedeğine §6.1 ile dönüş |
| 6 | Yerel sunucu başlatılamadı | güvenlik yazılımı 127.0.0.1'i engelliyor olabilir |
| 7 | WebView2/pencere motoru yok | §10.1 |
| 8 | PDF duman testi başarısız (`--pdf-duman`) | §10.5 |
| 9 | Geri yükleme (`--geri-yukle`) başarısız | parolayı ya da kurtarma anahtarını doğrulayıp yeniden deneyin; `logs/uygulama.log` |
| 10 | Bağımlılık duman testi başarısız (`--bagimlilik-duman`) | paket eksik üretilmiş; yeniden indirip kurun (§10.5) |
| 11 | Dağıtım duman testi: program beklenen dağıtım türünü bulmadı (`--dagitim-duman <tür>`; derlemede ve kurulum sınamasında kullanılır) | Pardus'ta `.deb` ile kurulan program kendini "kurulu" saymıyorsa Ağ Kataloğu açılmaz; önce §4.2'deki taşınabilir sürüm kaldırmasını denetleyin, sürüyorsa `logs/tanilama.log` ile bildirin |

`--geri-yukle`, `--autotest` ve `--pdf-duman` çalışan bir kopya bulursa 2
koduyla çıkar. Bayraksız ikinci açılış ise çalışan kopyanın penceresini öne
getirir ve 0 koduyla çıkar.

## 12. Programı kaldırma

* **Windows (kurulum paketi):** Ayarlar → Uygulamalar → Kütüphane Defteri →
  Kaldır (yönetici yetkisi ister; UAC'ye BTR kimliği girilir). Güvenlik duvarı
  kuralı, oturum açılışındaki zamanlanmış görev ve kayıt defterindeki port değeri de
  silinir. Program açıksa kaldırma onu önce düzenli kapatır (§3.1).
* **Windows (taşınabilir):** klasörü silin.
* **Pardus/Linux (.deb):** önce BTR açtığı güvenlik duvarı kurallarını kaldırır
  (ör. `sudo ufw delete allow from <yerel-ağ> to any app 'Kutuphane Defteri'`; paket
  kuralı açmadığı gibi kaldırırken de silmez), sonra `sudo apt remove kutuphane-defteri`.
* **Linux (taşınabilir):** arşivdeki `./kaldir.sh`

Kaldırma işlemi **verilerinizi silmez**: katalog, üyeler ve yedekler §6'daki
klasörlerde kalır. Bilgisayar okuldan çıkacaksa (hurdaya ayırma, devir) veri
klasörünü ve yedekleri silin; önce şifreli bir yedeği USB'ye alın.
