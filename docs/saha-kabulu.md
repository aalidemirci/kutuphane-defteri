# Kütüphane Defteri — Saha Kabul Protokolü

Bu protokol, programın ilk ön sürümünü (beta) gerçek bir okul ortamında uçtan uca
sınamak içindir: temiz bir Windows 11 bilgisayarda kurulumdan kaldırmaya kadar bütün
zincir, ardından Pardus'ta aynı zincirin kısaltılmış hâli. Kod tarafında yazılı
testlerle kanıtlanamayan her şey — gerçek yazıcı, gerçek barkod okuyucu, okul ağı,
etkileşimli tahta, Windows'un yönetici kurulumu, uyku ve oturum kapanışı — burada bir
adıma bağlıdır. Protokolün sonundaki **eşleme tablosu** (§26) her ertelenmiş saha
kanıtının hangi adımda alındığını gösterir.

> **Gerçek kişi verisi KULLANILMAZ.** Protokol boyunca öğrenci, personel ve katalog
> verisi §1.2'deki **uydurma deneme verisi üreticisinden** gelir. Deneme bir sanal
> makinede ya da sonradan sıfırlanacak bir demirbaş bilgisayarda yapılır; gerçek
> kullanıma geçiş deneme kurulumu temizlendikten sonra yapılır (§25). Ekran görüntüsü,
> hata bildirimi ve not yalnız uydurma veriyle alınır; okulun adı, kişi adları ve okul
> ağının gerçek IP adresleri herkese açık bir yere (GitHub, e-posta, site) yazılmaz.

## 0. Nasıl kullanılır

- Her adım bir işaret kutusudur. Adımın üç satırı vardır: **Yap** (ne yapılır),
  **Gör** (geçmesi için ne görülmeli) ve **Sorun olursa** (nereye bakılır). Beklenen
  görülmediyse kutuyu işaretlemeyin; §27'deki bulgu satırını doldurun ve sonraki
  adıma geçin (bir adımın düşmesi bütün protokolü durdurmaz, bağımlı adımlar yazılıdır).
- "Kaynak" satırı adımın hangi ertelenmiş kanıtı kapattığını söyler (§26).
- Kutuları basılı kopyada kalemle ya da bilgisayardaki yerel bir kopyada işaretleyin.
  Doldurulmuş protokol, kayıt çizelgesi (§0.2) ve bulgu kaydı (§27) **okulda kalır**:
  depoya, GitHub'a (issue dahil) ve e-postaya konmaz; bir bulguyu dışarı bildirmek
  gerekirse yalnız adım numarası ve kişisiz gözlem yazılır.
- Sürelerin tamamı bir oturumda yapılmaz. Önerilen sıra: 1. gün §1-§7 (kurulum, sihirbaz,
  aktarımlar), 2. gün §8-§11 (etiket, üyelik, masa, teslim), 3. gün §12 (Ağ Kataloğu,
  BTR ile birlikte), ardından §13-§23; Pardus (§24) ayrı bir gün.

### 0.1 Sorun olursa bakılacak yerler (her adımda geçerli)

| Ne | Windows | Pardus |
|---|---|---|
| Programın günlüğü | `%LOCALAPPDATA%\KutuphaneDefteri\logs\uygulama.log` | `~/.local/state/kutuphane-defteri/logs/uygulama.log` |
| Yerel çöküş yığını (PDF, pencere) | `…\logs\cokme.log` | `…/logs/cokme.log` |
| Veri ve yedek klasörleri | `%LOCALAPPDATA%\KutuphaneDefteri\data` ve `…\backups` | `~/.local/share/kutuphane-defteri/data` ve `…/backups` |
| Çıkış kodları | `docs/kurulum.md` §11 (0-10) | aynı |
| Kurulum günlüğü | kurulum dosyasını `/LOG="%USERPROFILE%\Desktop\kurulum.log"` ile çalıştırın | `apt` çıktısı |
| Ağ Kataloğunun son hatası | Ayarlar → Ağ Kataloğu → Ağ Doktoru → **Katalog Durumu** kartı | aynı |

Günlükler kişi adı, okul no ve kart no taşımaz; yine de bir bulguya eklemeden önce
okuyun. `docs/kurulum.md` §10 sık sorunları anlatır.

### 0.2 Kayıt çizelgesi

Protokolün başında bir kez doldurun (IP adresi ve kişi adı yazmayın):

| Alan | Değer |
|---|---|
| Tarih ve protokolü uygulayanların görevi (ör. kütüphane yöneticisi, BTR) | |
| Program sürümü (Hakkında ve Lisans) | |
| Bilgisayar: demirbaş mı, sanal makine mi; işlemci, bellek, disk (HDD / SSD) | |
| Windows sürümü ve derlemesi (`winver`) | |
| Microsoft Edge WebView2 sürümü (Uygulamalar listesi) | |
| Yazıcı markası/modeli ve çözünürlüğü (300 / 600 dpi) | |
| Barkod okuyucu markası/modeli (1D / 2D, USB) | |
| Etiket tabakası (ölçü ve adet: ör. 38,1 × 21,2 mm 65'li) | |
| Etkileşimli tahta: işletim sistemi ve tarayıcı sürümü (ETAP, Chromium, Firefox) | |
| Pardus sürümü (21 / 23) ve masaüstü (XFCE / GNOME) | |

## 1. Hazırlık

### 1.1 Ortam

- [ ] **1.1.1 Deneme bilgisayarı ve hesaplar**
  - *Yap:* Temiz bir Windows 11 hazırlayın (sanal makine ya da sıfırlanmış, okul
    demirbaşı bir bilgisayar). BTR iki hesap açar: yönetici yetkisi OLMAYAN
    **kütüphane masası hesabı** ve BTR'nin kendi yönetici hesabı (`docs/kurulum.md`
    §1.2). Mümkünse disk şifrelemesini (BitLocker) açın.
  - *Gör:* Masa hesabı "Standart kullanıcı"dır (Ayarlar → Hesaplar → Diğer kullanıcılar).
  - *Sorun olursa:* Masa hesabı yönetici olursa §2 ve §12'nin "yönetici olmayan hesapta"
    kanıtları geçersizdir; hesabı standart yapıp yeniden başlayın.
  - *Kaynak:* S10.
- [ ] **1.1.2 Donanım ve ikinci cihazlar**
  - *Yap:* Hazır edin: USB barkod okuyucu (2D önerilir), lazer yazıcı, etiket tabakası
    (varsayılan şablon 38,1 × 21,2 mm 65'li), A4 kâğıt, bir USB bellek; okul ağında
    **ikinci bir Windows bilgisayar**; bir **etkileşimli tahta**; geri yükleme provası
    için **ikinci bir demirbaş bilgisayar ya da sanal makine**; §24 için bir Pardus
    bilgisayar. İsteğe bağlı: WebView2 kurulu olmayan bir Windows 10 (§23.2).
  - *Gör:* Okuyucu Not Defteri'ne okutulan kodu yazıp Enter gönderiyor (klavye kipi).
  - *Sorun olursa:* Okuyucu Enter göndermiyorsa üreticinin ayar barkodu kitapçığından
    "CR/Enter sonek" ayarını okutun.
  - *Kaynak:* S4.
- [ ] **1.1.3 BTR ile ağ görüşmesi (§12'den önce)**
  - *Yap:* BTR'yle kütüphane bilgisayarının ağ bölümünü, tahtaların bölümünü, tahta
    tarayıcısının vekil sunucu ayarını ve bilgisayar için **sabit adres ayırma**yı
    (DHCP) konuşun (`docs/ag-kurulumu.md` §4). Tahtalardan erişim kapalıysa PYS talebi
    süreci bu protokolden önce başlar (§12.5).
  - *Gör:* Bilgisayarın adresi sabit; BTR bilgi notunu imzalamaya hazır.
  - *Kaynak:* S1, S2, S3.

### 1.2 Uydurma deneme verisi

Deneme verisi depodaki üreticiyle, geliştirme bilgisayarında Docker'da üretilir
(`scripts/deneme_verisi.py`; yalnız standart kitaplık ve programın zaten kullandığı
openpyxl). Veri dosyaları **depoya girmez**: çıktı klasörü `deneme-verisi/`
`.gitignore`'dadır.

- [ ] **1.2.1 Üret**
  - *Yap:* Depo kökünde (PowerShell):

    ```powershell
    docker compose run --rm -T -w /repo backend python scripts/deneme_verisi.py
    ```

    Git Bash'te komutun başına `MSYS_NO_PATHCONV=1` ekleyin. Seçenekler: `--eser`
    (40-10.000; varsayılan 2.000), `--ogrenci` (varsayılan 750), `--personel`
    (varsayılan 60), `--kademe lise|ortaokul|ilkokul`, `--tohum` (aynı tohum aynı
    veriyi üretir), `--cikti`.
  - *Gör:* `deneme-verisi/` klasöründe altı dosya: `eokul-ogrenci-listesi.xlsx`,
    `eokul-ogrenci-listesi-2-donem.xlsx`, `eokul-personel-listesi.xlsx`,
    `katalog-deneme.xlsx`, `katalog-sorunlu-satirlar.xlsx`, `OZET.txt`. `OZET.txt`
    bu protokolde "OZET" diye anılır ve önizlemelerde görülmesi gereken sayıları yazar.
  - *Sorun olursa:* Docker Desktop elle başlatılır; imaj yoksa
    `docker compose build backend`.
- [ ] **1.2.2 Ne olduğunu bilin**
  - *Yap:* OZET'in başını okuyun.
  - *Gör:* Öğrenci ve personel adları ad ve soyad havuzlarının rastgele
    birleşimidir; okul "Örnek" adını taşır. T.C. kimlik numarası, telefon, adres ve veli
    bilgisi yoktur. e-Okul raporunun "Cinsiyeti" ve "Branşı" sütunları gerçek rapordaki
    gibi doldurulmuştur ama program onları **okumaz** (sınanan davranışlardan biri).
    e-Okul'un kendi dosyası `.XLS`'tir, deneme dosyası `.xlsx`'tir: program biçimi
    dosyanın içinden tanır ve e-Okul yerleşimini (şube blokları, dipnotlar) iki biçimde
    de aynı yoldan okur.
  - *Sorun olursa:* Gerçek bir listeyle karıştırmayın; deneme bitince klasörü ve
    USB'deki kopyasını silin.
- [ ] **1.2.3 Deneme bilgisayarına taşı**
  - *Yap:* `deneme-verisi/` klasörünü USB belleğe kopyalayıp deneme bilgisayarının
    masa hesabında Belgeler altına alın.
  - *Gör:* Altı dosya açılıyor (Excel ya da LibreOffice ile bakmak serbesttir; kaydetmeyin).

### 1.3 Sürümü indir ve doğrula

- [ ] **1.3.1 İndir**
  - *Yap:* Sürümün GitHub Releases sayfasından (ya da programın sayfasından,
    `okulapp.org/kutuphane-defteri`; dosyalar `indir.okulapp.org`'dan iner) Windows
    kurulum dosyasını, taşınabilir zip'i, `.deb`'i, Linux arşivini ve özet dosyasını
    indirin. Özet dosyasının adı GitHub'da `SHA256SUMS.txt`, `indir.okulapp.org`'da
    `SHA256SUMS-<sürüm>.txt`'dir (içerik aynı).
  - *Gör:* GitHub'da sürüm **Pre-release** (ön sürüm) etiketlidir; sürüm notu "Ön
    sürümdür." diye başlar. Beta'da `.deb` dosyasının adındaki `~` noktaya çevrilmiştir
    (`kutuphane-defteri_2026.10.0.beta.1_amd64.deb` gibi).
  - *Sorun olursa:* Pre-release işareti yoksa yayın hattını (`paketleme.yml`, "Release"
    adımı) bildirin.
  - *Kaynak:* kullanıcı kararı 3 (27.09.2026).
- [ ] **1.3.2 Doğrula**
  - *Yap:* `docs/kurulum.md` §9. Windows: `Get-FileHash .\<dosya> -Algorithm SHA256`.
    Pardus: `sha256sum -c SHA256SUMS-<sürüm>.txt --ignore-missing` (GitHub'dan
    indirdiyseniz dosya adı `SHA256SUMS.txt`; `--ignore-missing` indirmediğiniz paketlerin
    satırlarını atlar).
  - *Gör:* Windows'ta özet, özet dosyasındaki satırla birebir aynı; Pardus'ta indirilen her
    dosya için `: OK` (`OK` dışında satır yok).
  - *Kaynak:* TB6.

## 2. Windows kurulumu (temiz Windows 11)

- [ ] **2.1 SmartScreen ve güvenlik yazılımı**
  - *Yap:* Kurulum dosyasını masa hesabında çift tıklayın.
  - *Gör:* İmzasız paket olduğu için SmartScreen "Windows kişisel bilgisayarınızı
    korudu" diyebilir: "Ek bilgi" → "Yine de çalıştır". Defender ya da okulun güvenlik
    yazılımı dosyayı silmez, karantinaya almaz.
  - *Sorun olursa:* Engellenirse güvenlik yazılımının adını ve iletisini §27'ye yazın;
    `docs/kurulum.md`'ye istisna adımı eklenmesi gerekir.
  - *Kaynak:* NOTLAR çek-listesi 13; TB6; risk 15.
- [ ] **2.2 Masa hesabında, BTR'nin UAC kimliğiyle kurulum**
  - *Yap:* Kurulum dosyasını **masa hesabında** başlatın; Windows'un yönetici onay
    penceresine (UAC) **BTR yönetici hesabının** adını ve parolasını girin.
    İsteğe bağlı olarak dosyayı komut isteminden `/LOG="%USERPROFILE%\Desktop\kurulum.log"`
    ile çalıştırın.
  - *Gör:* Kurulum penceresi Türkçedir; ilk sayfalardan biri lisans sözleşmesidir
    (PolyForm Noncommercial; Türkçe harfler bozulmadan görünür) ve kabul edilmeden
    ilerlenmez. Program `C:\Program Files\Kütüphane Defteri` altına kurulur; kurulum
    klasöründe `LICENSE.txt` ve üçüncü taraf lisansları (`THIRD_PARTY_LICENSES\`, içinde
    `BENIOKU.txt`, pakete gerçekten giren sürümlerin dökümü `paket-icerigi.txt` ve sistem
    kütüphanelerinin lisansları `yerel-kutuphaneler\`) bulunur; tepsi kütüphanesinin (LGPL)
    kaynak dosyaları `_internal\pystray\` altında `.py` olarak durur. Son sayfadaki "Kütüphane Defteri
    programını çalıştır" programı **masa hesabıyla** açar ve veri
    `%LOCALAPPDATA%\KutuphaneDefteri` altında, masa hesabının profilinde oluşur (BTR'nin
    profilinde DEĞİL). Programda **Hakkında ve Lisans → Üçüncü Taraf Bileşenler** kartı LGPL
    kitaplıkların telif bildirimini ve bu klasördeki lisans dosyalarını gösterir.
    `BENIOKU.txt`'de "LGPL BİLEŞENLERİNİN KAYNAK KODU İÇİN YAZILI TEKLİF" bölümü vardır (en
    az üç yıl; istek yolu programın GitHub deposunun Issues sayfası).
  - *Sorun olursa:* Veri BTR'nin profilinde oluştuysa (W10) kurulum günlüğünü ve
    `uygulama.log`'u saklayın. Kurulum klasörüne yazma hatası (W8) `uygulama.log`'a
    "Paket ortamı uyarısı:" ile başlayan satır olarak düşer.
  - *Kaynak:* W8, W10, W6, W7, W21, W23; çek-listesi 4; TB28; F12 satırı (Inno, lisans); KB-1
    yazılı teklif (tasarım F12 ekleri karar turu KT-1).
- [ ] **2.3 Kurulum seçenekleri: güvenlik duvarı kuralı ve otomatik başlatma**
  - *Yap:* Kurulum seçeneklerinde "Yerel ağdan katalog taramasına izin ver (güvenlik
    duvarı kuralı)" ve "Oturum açılınca Kütüphane Defteri'ni başlat" işaretli kalsın.
    Kurulumdan sonra BTR yönetici PowerShell'de denetler:

    ```powershell
    $k = Get-NetFirewallRule -DisplayName "Kutuphane Defteri Katalog"
    $k | Format-List DisplayName, Enabled, Direction, Action, Profile
    $k | Get-NetFirewallPortFilter | Format-List LocalPort, Protocol
    $k | Get-NetFirewallAddressFilter | Format-List RemoteAddress
    $k | Get-NetFirewallApplicationFilter | Format-List Program
    reg query HKLM\SOFTWARE\KutuphaneDefteri /v KatalogPortu
    schtasks /Query /TN "Kutuphane Defteri" /V /FO LIST
    ```

  - *Gör:* Tek kural; gelen, izin, etkin; port 8765 TCP; uzak adres `LocalSubnet`;
    profil Etki alanı, Özel ve Genel (ya da `Any`); program yolu
    `C:\Program Files\Kütüphane Defteri\kutuphane-defteri.exe` (Türkçe harfler bozulmadan).
    Kayıt defterinde `KatalogPortu` = 8765 (`reg query` onaltılık basar: `REG_DWORD
    0x223d`). Zamanlanmış görevin "Çalıştıran
    kullanıcı"sı **masa hesabıdır**, tetikleyici oturum açılışıdır.
  - *Sorun olursa:* Kural yoksa kurulum günlüğünde "eklenemedi" satırını arayın (W16);
    görev BTR'nin hesabına yazıldıysa kurulum masa hesabında başlatılmamıştır (W17).
  - *Kaynak:* W16, W17; çek-listesi 14 (ilk kısım), 15; F5 ekleri 16 (güvenlik duvarı
    görevi, zamanlanmış görev); §5.7.
- [ ] **2.4 WebView2**
  - *Yap:* Uygulamalar listesinde "Microsoft Edge WebView2 Runtime"ı arayın.
  - *Gör:* Kurulu (Windows 11'de hazır gelir; eksikse kurulum dosyası sessizce kurar).
    Program penceresi boş beyaz kalmaz.
  - *Sorun olursa:* Pencere açılmazsa çıkış kodu 7'dir (`docs/kurulum.md` §10.1); §23.2'yi yapın.
  - *Kaynak:* W5, W9; F12 satırı (WebView2).
- [ ] **2.5 Tanılama komutları (program kapalıyken)**
  - *Yap:* Masa hesabında PowerShell (program penceresi olan bir exe'yi PowerShell
    beklemez; `Start-Process -Wait -PassThru` şarttır):

    ```powershell
    $exe = "C:\Program Files\Kütüphane Defteri\kutuphane-defteri.exe"
    (Start-Process $exe -ArgumentList "--autotest" -Wait -PassThru).ExitCode
    (Start-Process $exe -ArgumentList "--bagimlilik-duman" -Wait -PassThru).ExitCode
    $pdf = "$env:USERPROFILE\Desktop\pdf-duman.pdf"
    (Start-Process $exe -ArgumentList "--pdf-duman `"$pdf`"" -Wait -PassThru).ExitCode
    ```

    PowerShell 5.1 `-ArgumentList` öğelerini tırnaklamaz; hesap adında boşluk varsa
    (ör. "Kütüphane Masası") PDF yolu yukarıdaki gibi tek dizgede, tırnak içinde verilir.
  - *Gör:* Üçü de `0`. `uygulama.log`'da "Temiz kapanış işareti yazıldı." satırı.
    `pdf-duman.pdf` açılır: antet düzgün, "ĞÜŞİÖÇ ığüşiöç" doğru harflerle, altlıkta
    "Sayfa 1 / 1". `logs\tanilama.log` son duman kipinin çıktısını taşır ("Hedef PDF: …",
    "PDF duman testi başarılı", "Çıkış kodu: 0").
  - *Sorun olursa:* Kod 2 → program açıktır (tepsiden Çık). Duman kipleri (`--pdf-duman`,
    `--bagimlilik-duman`) `uygulama.log`'a YAZMAZ: tanı çıktıları (eksik modül, eksik harf,
    font adları, fontconfig ve `KD_RTHOOK_UYARI` değerleri) `logs\tanilama.log`'dadır (her
    koşuda baştan yazılır; penceresiz programın konsol çıktısı yoktur). Kod 10 → pakette parça
    eksik (tanı dosyasında modül adı). Kod 8 ya da bozuk harf → `tanilama.log` ve yerel çöküş
    için `cokme.log` (W2-W4: pango/fontconfig DLL'leri); "Hedef PDF" satırındaki yolun
    doğruluğuna da bakın.
  - *Kaynak:* çek-listesi 3, 12; W1-W4, W22; F0 kod kapısı (`--pdf-duman`, `--bagimlilik-duman`).

## 3. İlk açılış ve Kurulum Sihirbazı

- [ ] **3.1 İlk açılış**
  - *Yap:* Programı Başlat menüsünden açın.
  - *Gör:* Pencere açılır, **Kurulum Sihirbazı** gelir; adım rayı **Yönetici Parolası** ·
    **Okul Bilgileri** · **Ders Yılı ve Kapalı Günler**. Saatin yanında tepsi simgesi görünür.
  - *Kaynak:* W9; F0 kod kapısı (exe açılır, tepsiye iner).
- [ ] **3.2 Yönetici parolası ve kurtarma anahtarı**
  - *Yap:* Deneme için bir parola belirleyin (gerçek parolanızı kullanmayın). Kurtarma
    anahtarını **yazdırın** (gerçek yazıcı) ve ayrıca **PDF olarak** kaydedin; iki grubu
    geri yazarak doğrulayın.
  - *Gör:* **Kurtarma anahtarı çıktısı** tek sayfa, anahtar okunaklı; doğrulama yapılmadan
    kurulum tamamlanmaz. Anahtar ekranı 5 dakika dokunulmazsa gizlenir ("Anahtar güvenlik
    için gizlendi").
  - *Sorun olursa:* Yanlış grupta bekleme süresi artar (kademeli gecikme); bu beklenen
    davranıştır.
  - *Kaynak:* S11; E14 (§16).
- [ ] **3.3 Okul bilgileri**
  - *Yap:* Okul adı "Örnek Anadolu Lisesi", ilçe "Örnek İlçe", müdür adı ve demirbaş no —
    hepsi UYDURMA (bu alanlar aydınlatma metnine ve belgelere basılır, ekran görüntülerine
    girer); kademe "Ortaöğretim (lise)", kısa ad, "bu bilgisayar okul demirbaşıdır" onayı.
  - *Gör:* Onay kutusu işaretlenmeden ilerlenmez.
  - *Kaynak:* S12.
- [ ] **3.4 Ders yılı ve kapalı günler**
  - *Yap:* Ders yılını ve dönemleri girin; resmî ve dini tatilleri ekleyin; ara tatili ve
    yarıyılı **öğrenciye kapalı gün** olarak ekleyin. **Kurulumu tamamla**.
  - *Gör:* Genel Bakış'ta **Başlangıç Yol Haritası** kartı. Kurulumdan sonra yönetici
    kipi 3 dakika dokunulmazsa **Görevli kipi**ne iner (üst çubukta kip göstergesi).
- [ ] **3.5 Kilitle ve kilidi aç**
  - *Yap:* Üst çubukta **Kilitle** → parolayla açın; bir kez yanlış parola deneyin.
  - *Gör:* "Kayıtlar kilitli" ekranı; yanlış parolada kısa bekleme; doğru parolayla
    yönetici kipi.

## 4. Pencere, tepsi, çıkış ve oturum (Windows)

- [ ] **4.1 Çarpı gizler, tepsi geri getirir**
  - *Yap:* Pencereyi önce küçültüp sonra büyütün, ardından çarpıya basın; tepsi simgesine
    sol tıklayın; sonra sağ tıklayıp **Pencereyi aç**'ı seçin.
  - *Gör:* Çarpı programı kapatmaz, pencereyi gizler; tepsi simgesi görünür (boş ya da
    bozuk değil); sol tık ve **Pencereyi aç** pencereyi önceki boyutuyla getirir.
  - *Sorun olursa:* Simge yoksa `uygulama.log`'da `kutuphane_defteri.tepsi` satırları
    ("Sistem tepsisi hazır." ya da "Tepsi ikonu okunamadı"; W13).
  - *Kaynak:* W13, W22; çek-listesi 7; CLAUDE.md §7 F0 (tepsi simgesi).
- [ ] **4.2 İkinci açılış**
  - *Yap:* Program tepsideyken Başlat menüsünden yeniden açın. Sonra Başlat menüsündeki
    **Kütüphane Defteri — Yedekten Geri Yükle** kısayolunu çalıştırın.
  - *Gör:* İlkinde çalışan pencere öne gelir, ileti kutusu çıkmaz. İkincisinde "Program
    tepside çalışıyor. Tepsideki simgeden Çık'ı seçip yeniden deneyin." (çıkış kodu 2).
  - *Kaynak:* çek-listesi 8; F12 satırı (iki mutex — ikinci açılış kilidi).
- [ ] **4.3 Çık ve temiz kapanış işareti**
  - *Yap:* Tepsiden **Çık**. Görev Yöneticisi'ne bakın.
  - *Gör:* `kutuphane-defteri.exe` Görev Yöneticisi'nde KALMAZ;
    `%LOCALAPPDATA%\KutuphaneDefteri\data\temiz-kapanis.json` VAR.
  - *Sorun olursa:* Süreç kalıyorsa W13 (pystray durdurulmadı); `uygulama.log`.
  - *Kaynak:* W13; çek-listesi 10; CLAUDE.md §7 F0 (Çık); TB14.
- [ ] **4.4 Beklenmedik kapanış**
  - *Yap:* Programı açın, bir kitap ödünç verin (§10'dan sonra da yapılabilir), Görev
    Yöneticisi'nden süreci sonlandırın, programı yeniden açın.
  - *Gör:* `temiz-kapanis.json` yok; `uygulama.log`'da "Önceki oturum beklenmedik biçimde
    kapandı"; yönetici kipinde Genel Bakış'ta **Son Oturumu Kontrol Edin** kartı son
    ödünç ve iadeleri listeler; "Kontrol ettim" kartı kapatır.
  - *Kaynak:* çek-listesi 10; S13 (elektrik kesintisi senaryosu).
- [ ] **4.5 Oturum kapanışı ve yeniden başlatma**
  - *Yap:* Program tepsideyken Windows'u yeniden başlatın (ya da oturumu kapatın).
  - *Gör:* Windows "Bu uygulama kapanmayı engelliyor" ekranında BEKLEMEZ; sonraki
    açılışta günlükte "Önceki oturum düzenli kapanmış."
  - *Sorun olursa:* W14 (.NET `FormClosing` işleyicisi).
  - *Kaynak:* W14; çek-listesi 11.
- [ ] **4.6 Otomatik başlatma**
  - *Yap:* Masa hesabında oturumu kapatıp yeniden açın.
  - *Gör:* Program kendiliğinden, **kilit ekranıyla** açılır ("Kayıtlar kilitli").
    Windows oturumu açılmadan program ve Ağ Kataloğu çalışmaz (beklenen).
  - *Kaynak:* W17; çek-listesi 15; §4.2-3.
- [ ] **4.7 Kipe göre tepsi menüsü ve görevli kipinde Çık**
  - *Yap:* Yönetici kipinde tepsi menüsüne bakın; üst çubuktan **Görevli kipine geç**
    (Ctrl+Shift+G); menüye yeniden bakın; görevli kipinde tepsiden **Çık**.
  - *Gör:* Yönetici kipinde "Ağ Kataloğunu aç/kapat" ve "Görevli kipine geç" var; görevli
    kipinde bunlar kaybolur (menü yenilenir). Görevli kipinde Çık pencereyi öne getirir ve
    **Programdan çık** penceresi yönetici parolası ister; doğru parolayla program kapanır
    ve `temiz-kapanis.json` yazılır.
  - *Sorun olursa:* Menü eski komutları gösteriyorsa W20 (komut yine reddedilir ama bulgu
    yazılır).
  - *Kaynak:* W20; çek-listesi 17 (ikinci kısım); F5 ekleri 16 (pystray menü yenilemesi).

## 5. Kütüphane aydınlatma metni ve masa kartı

- [ ] **5.1 Kütüphane aydınlatma metni**
  - *Yap:* Kişiler → Üyeler → **Üyelik Belgeleri**: uydurma başvuru adresi ve iletişim
    bilgisiyle **Önizle**, sonra yazıcıdan basın.
  - *Gör:* En çok iki sayfa; okul adı, ilçe ve müdür adı Okul Bilgileri'nden gelir;
    Türkçe harfler doğru.
  - *Kaynak:* S7; E13 (§16).
- [ ] **5.2 Masa kartı**
  - *Yap:* Aynı bölümden **Masa kartı**nı basın.
  - *Gör:* Tek sayfa; bölümler **MASADA NASIL ÇALIŞILIR** ve **GİZLİLİK**; iletiler masa
    ekranındakilerle aynı ("Ödünç verilemiyor — kütüphane yöneticisine yönlendirin." gibi).
  - *Kaynak:* S7; E19 (§16); F12 satırı (belgeler: masa kartı).

## 6. e-Okul öğrenci ve personel aktarımı

Ekran: **Kişiler** sayfasının altındaki aktarım panelleri ("e-Okul Raporundan veya
Şablondan Öğrenci Aktar", "… Öğretmen ve Diğer Personeli Aktar"); düğmeler **Önizle** ve
**Aktar**.

- [ ] **6.1 Öğrenci listesi — önizleme**
  - *Yap:* `eokul-ogrenci-listesi.xlsx`'i seçip **Önizle**.
  - *Gör:* OZET §1'deki sayılar: 750 yeni öğrenci (varsayılan boyut), atlanan satır yok;
    uyarılarda "e-Okul sınıf listesi biçimi algılandı: 25 şube bloğu …" notu; şube
    listesinde **9/I** ve **9/İ** AYRI iki şubedir. Önizleme hiçbir kayıt yazmaz.
  - *Sorun olursa:* Atlanan satır varsa satır numarasını ve gerekçeyi yazın; "Zorunlu
    sütun(lar) bulunamadı" e-Okul yerleşiminin tanınmadığını gösterir.
  - *Kaynak:* F12 kod kapısı (e-Okul).
- [ ] **6.2 Öğrenci listesi — aktarım**
  - *Yap:* **Aktar**. Ayarlar → **Şubeler**'e bakın.
  - *Gör:* 750 öğrenci Kişiler → Öğrenciler'de; şubeler oluşmuş; aynı dosyayı yeniden
    yüklemek yeni kayıt açmaz ("zaten aktarıldı"/değişmeyen).
- [ ] **6.3 İkinci dönem listesi — Ayrılış Havuzu**
  - *Yap:* `eokul-ogrenci-listesi-2-donem.xlsx` → **Önizle** → **Aktar**. Genel Bakış'taki
    **Ayrılış Havuzu** kartından Kişiler → **Ayrılış Havuzu**'na gidin; birkaç kişiyi
    "Ayrıldı olarak işaretle", birini "Aktif kalsın" diye karara bağlayın.
  - *Gör:* OZET §2: 8 yeni, 5 güncellenen (şube değiştiren), 12 kişi ayrılış havuzuna
    eklenecek, kalanı değişmeyen. Aktarım **kimseyi ayırmaz ve silmez**; havuzdakiler aktif
    kalır, kararı siz verirsiniz; ayrılan kişi "Ayrıldı · gg.aa.yyyy" rozetiyle kalır.
  - *Kaynak:* F1 ekleri 7 (havuzun sahadaki akışı).
- [ ] **6.4 Personel listesi**
  - *Yap:* `eokul-personel-listesi.xlsx` → **Önizle** → **Aktar**.
  - *Gör:* OZET §3: 60 yeni kişi; öğretmen ve diğer personel sayıları OZET'teki gibi;
    OZET'te yazan satırda "Üye türünü denetleyin: görev bilgisi tanınmadı…" uyarısı. Kişiler
    → Öğretmenler ve Diğer Personel'de görev, branş ya da kadro görünmez (saklanmaz).

## 7. Katalog: Excel ile toplu giriş (önce liste yolu)

Saha gerçeği: okulların çoğunda hazır liste yoktur ve asıl geçiş yolu **önce etiket**tir
(§8.5). Bu bölüm önce liste yolunu ve ölçeği (1.000-10.000 kitap) sınar.

- [ ] **7.1 Önizleme ve bölüm kararları**
  - *Yap:* Ayarlar → Bölümler'e önceden bölüm AÇMAYIN. Katalog → **İçe Aktarma** →
    **Excel Aktarımı** → `katalog-deneme.xlsx` → **Önizle**. **Bölüm listesinde
    bulunmayan değerler**de her değer için **Yeni bölüm aç** → **Yeniden önizle**.
    Süreyi not edin.
  - *Gör:* Başlık "Önizleme — hiçbir kayıt yazılmadı"; OZET §4: 11 bölüm sorulur; kararlardan
    sonra 2.000 yeni eser, OZET'teki kadar "Mevcut esere nüsha" (aynı eserin eski kayıt
    no'lu ayrı satırları), OZET'teki nüsha sayısı; şüpheli, aktarılmadı ve ISBN uyarısı yok;
    ders kitabı varsayılanıyla danışma OZET'teki kadar. "Örnek" sayfası okunmaz.
  - *Sorun olursa:* Sayılar tutmazsa ekran görüntüsü (uydurma veridir) ve `uygulama.log`.
  - *Kaynak:* F12 kod kapısı (Excel katalog); S8 (ölçek).
- [ ] **7.2 Uygula ve ikinci uygulama engeli**
  - *Yap:* **Açılacak Edinim Partisi**ni gözden geçirip **Uygula**; süreyi not edin. Aynı
    dosyayı yeniden **Uygula**.
  - *Gör:* "Aktarım sonucu" önizlemeyle aynı sayıları yazar; ikinci uygulama ENGELLENİR
    ("… tarihinde zaten içe aktarıldı; aynı dosya ikinci kez uygulanamaz …").
- [ ] **7.3 Türkçe arama ve sıralama**
  - *Yap:* Katalog → Eserler'de OZET'teki beş çifti arayın ("şiir"/"ŞİİR", "ılık"/"ILIK",
    "ince"/"İNCE", "ilik"/"İLİK", "ınce"/"INCE"). "Sırala": Kaynak adına göre, Yazar adına
    göre, Konuya göre; listede sayfa sayfa ilerleyin.
  - *Gör:* Her çiftin iki yazımı AYNI sonucu ve OZET'teki sayıyı verir (noktalı ve noktasız
    i ayrı harftir: "ilik" ve "ınce" 0). Sıralama Türk alfabesiyledir: C'den sonra Ç, I'dan
    sonra İ, O'dan sonra Ö, S'den sonra Ş, U'dan sonra Ü; "Wuthering Heights" V ile Y
    arasında. Liste, arama ve sayfa geçişleri takılmadan (bir saniyenin altında) gelir.
  - *Kaynak:* CLAUDE.md §2-8 (T7) sahada; S8.
- [ ] **7.4 Sorunlu satırlar dosyası**
  - *Yap:* `katalog-sorunlu-satirlar.xlsx` → **Önizle** (uygulamayın ya da deneme için
    kararları verip uygulayın).
  - *Gör:* OZET §5'teki satır satır sonuçlar: başlık 4. satırda bulunur; "Sıra" ve "Fiyat"
    tanınmayan sütun; iki **Şüpheli** satır **Karar bekleyen satırlar**da; "Gezi Rafı"
    bölümü sorulur; "Aktarılmadı" satırlarında gerekçe yazar; ciltsiz dergi satırı hatalı.
- [ ] **7.5 Dijital kaynak (elle)**
  - *Yap:* Katalog → **Yeni eser**, kaynak türü **E-kitap**; kaydedin; nüsha eklemeyi deneyin.
  - *Gör:* Eser kaydedilir, **nüsha açılmaz** (Excel'le dijital kaynak aktarılmaz; bu yol elledir).
- [ ] **7.6 Üst ölçek (isteğe bağlı)**
  - *Yap:* `--eser 10000` ile ayrı bir klasöre üretip (deneme kurulumunu sıfırlayarak ya da
    ikinci bir deneme bilgisayarında) aynı adımları yapın.
  - *Gör:* Önizleme ve uygulama tamamlanır; katalog listesi ve arama akıcı kalır. Süreleri
    not edin.
  - *Kaynak:* S8; F3 ölçüm kapısının sahadaki karşılığı.
- [ ] **7.7 ISBN ile künye getirme (isteğe bağlı)**
  - *Yap:* BTR okul ağından iki adresi sınar (`docs/kurulum.md` §8.7:
    `Test-NetConnection koha.ekutuphane.gov.tr -Port 210`,
    `Test-NetConnection openlibrary.org -Port 443`). Ayarlar → Kütüphane Politikası →
    **Künye Getirme**'de ayarı açın; Hızlı Kayıt'ta rafta duran GERÇEK bir kitabın ISBN'ini
    okutup **Künyeyi getir** deyin; sonra ayarı kapatın.
  - *Gör:* Öneri "Dış kaynaktan alındı, doğrulayın" rozetiyle, kaynak adı ve tarihle gelir;
    siz onaylamadan hiçbir alan dolmaz. Ulaşılamazsa "İnternetten getirilemedi, elle
    girebilirsiniz." Deneme verisinin ISBN'leri uydurmadır: sonuç getirmeyebilir ya da ilgisiz
    bir kitabı getirebilir.
  - *Kaynak:* S14, S15.

## 8. Etiketler: önce etiket yolu, gerçek yazıcı, gerçek okuyucu

- [ ] **8.1 Kalibrasyon sayfası ve kayma**
  - *Yap:* Katalog → Etiketler → **Şablonlar ve Kalibrasyon** → varsayılan şablonun
    **Kalibrasyon**'u → **Yeni yazıcı kalibrasyonu** → kalibrasyon sayfasını **gerçek
    boyutta (%100)** basın; ortadaki çizgiyi cetvelle ölçün; köşe cetvellerinde okunan
    değerleri "Okunan yatay/dikey değer"e yazıp **Kaymaya ekle** → yeniden basın.
  - *Gör:* Ortadaki çizgi 100 mm (±0,5); kaymadan sonra cetveller sıfırı gösterir; dört
    köşe aynı yöne kayıyorsa kaymadır, farklıysa ölçek sorunudur (yazdırmada ölçekleme
    açık kalmıştır).
  - *Sorun olursa:* Çizgi 100 mm değilse yazıcı penceresinde "Gerçek boyut"u seçin.
  - *Kaynak:* F4 ekleri 9 (kalibrasyon ölçümü); TB29.
- [ ] **8.2 Tabaka ölçüsü (okulun aldığı tabaka)**
  - *Yap:* Okul 44'lü ya da 40'lı tabaka aldıysa şablonun ölçülerini cetvelle karşılaştırın
    (Avery Zweckform 3657 40'lıdır; hazır 44'lü şablon ona uymaz — TB29).
  - *Gör:* Kenar hücrelerde yazı ve barkod kesilmez (5 mm güvenli kenar payı).
  - *Kaynak:* TB29; S4.
- [ ] **8.3 Sırt ve barkod etiketi partisi (önce liste yolu)**
  - *Yap:* **Basım Kuyruğu** → "Bölüm" süzgeciyle iki bölüm için ayrı ayrı: biri ödünç
    verilebilen, biri danışma (sonraki adımlar ikisini de ister). OZET §4'teki "Bölüm başına
    nüsha" satırından seçin; varsayılan veride **Sanat** (29 nüsha) ve **Danışma** (32
    nüsha). Her biri için "Etiket içeriği" **Sırt ve barkod etiketi** → **Basım partisini
    hazırla** → **Önizle** → **PDF'i indir** → gerçek boyutta basın → **Basıldı olarak
    işaretle**. Etiketleri o bölümün kitaplarına (deneme için boş kitap ya da kartona)
    yapıştırın: §10 ve §11 bu nüshaları okutur.
  - *Gör:* PDF önizlemesi program penceresinde (WebView2) görünür; önizleme ve indirme
    hiçbir işarete dokunmaz; önce sırt, sonra barkod tabakası; etiketler hücrelere oturur;
    Türkçe harfler doğru.
  - *Sorun olursa:* Önizleme görünmezse "PDF'i indir" yolu tam işlevlidir (bulgu yazın).
  - *Kaynak:* F4 ekleri 9 (gerçek yazıcıda basım, WebView2 önizlemesi); E1 (§16).
- [ ] **8.4 Code128 okunurluğu (gerçek okuyucu)**
  - *Yap:* Basılı tabakadaki 20 barkodu Etiketler → **Doğrulama Okutması**'nda okuyucuyla
    okutun; ayrıca 300 ve 600 dpi yazıcı varsa ikisinde de deneyin.
  - *Gör:* Her etiket ilk denemede okunur ve tanınır; "Bu ekranda doğrulanan" sayacı artar.
  - *Sorun olursa:* Okunmayan etiketin yazıcı ayarını (toner tasarrufu kapalı, en yüksek
    kalite) ve okuyucu modelini §27'ye yazın.
  - *Kaynak:* F4 ekleri 9 (gerçek okuyucu); F4 kod kapısı "gerçek okuyucu"; S4.
- [ ] **8.5 Önce etiket yolu (okulun asıl yolu)**
  - *Yap:* Etiketler → **Boş Barkod Aralığı** → **Numara ayır** (ör. 65) → boş barkod
    etiketlerini basıp **Basıldı olarak işaretle** → rafta duran 10 gerçek kitaba
    yapıştırın → Katalog → **Hızlı Kayıt**: kitabın ISBN barkodunu okutun, künyeyi
    girin, **Kitaptaki etiketi okutun** kutusunda yapıştırdığınız etiketi okutun (Enter
    kaydeder) → sonuç kartında **Sırt etiketini bas** → iş bitince kullanılmayan
    numaraları **Seçilenleri iptal et** ile iptal edin.
  - *Gör:* Her kitap tek okutmayla kaydolur; imleç okutma kutusuna döner; ISBN barkodunu
    etiket kutusuna okutmak reddedilir ("Bu ISBN barkodu…"); iptal edilen numara bir daha
    verilmez.
  - *Kaynak:* S8, S9; F4 (yöntem B); CLAUDE.md saha gerçekleri.
- [ ] **8.6 Hızlı okutmada sıraya alma**
  - *Yap:* Doğrulama Okutması'nda 30 etiketi ARA VERMEDEN art arda okutun.
  - *Gör:* Hiçbir okutma kaybolmaz; "Bu ekranda doğrulanan" 30 artar; sırada bekleyen
    okutmalar sırayla işlenir.
  - *Kaynak:* F4 ekleri 9 (hızlı okutmada sıraya alma).
- [ ] **8.7 Doğrulama okutması görevli kipinde**
  - *Yap:* **Görevli kipine geç** → görevli ekranında **Doğrulama okutmasını aç** → 5
    etiket okutun → **Okutmayı bitir**.
  - *Gör:* Görevli yalnız barkodu ve kaynak adını görür; "Doğrulanmamış Etiketler" listesi
    görünmez; Etiketler sayfasının kendisi görevliye kapalıdır.
  - *Kaynak:* F4 ekleri 11.
- [ ] **8.8 Basım işaretini geri alma**
  - *Yap:* **Basım Geçmişi**'nde 8.3'teki partiyi seçip **Basım işaretini geri al**.
  - *Gör:* Doğrulanmış (okutulmuş) nüshaların işaretleri korunur, öbürleri kuyruğa döner;
    ileti sayıları ayrı söyler.

## 9. Üyelik ve üye kartı

- [ ] **9.1 Üyelik açma**
  - *Yap:* Kişiler → **Üyelik İstek Listesi** → bir şube → "Üye olmayanların tümünü seç" →
    **Seçilenleri üye yap**; Kişiler → Üyeler'den bir öğretmene **Personele üyelik aç**.
  - *Gör:* Üyelikler açılır; e-Okul aktarımı kimseyi kendiliğinden üye yapmamıştır.
- [ ] **9.2 Üye kartı basımı**
  - *Yap:* Kişiler → **Kart Basımı** → şube seç → **Kesim çizgisi bas** → **Önizle** →
    gerçek boyutta basın → **Basıldı olarak işaretle**. Kartları kesin.
  - *Gör:* A4'te 2 × 5 kart (85 × 54 mm), kesim çizgileri kartı ortalar; öğrenci ve
    öğretmen kartında Md. 20 konum notu, diğer personelin kartında atıfsız not.
  - *Kaynak:* E2 (§16).
- [ ] **9.3 Kart barkodu okunur**
  - *Yap:* Dolaşım Masası'nda 5 kartı okutun.
  - *Gör:* Her kart ilk denemede okunur; üye bağlamında ad ve "Kalan ödünç hakkı".
  - *Kaynak:* S4 (okuyucu); F6 (kart şeması).
- [ ] **9.4 Kartı yenile**
  - *Yap:* Bir üyelikte **Kartı yenile**; eski kartı masada okutun.
  - *Gör:* "İptal edilmiş kart — kütüphane yöneticisine yönlendirin."; yeni kart çalışır.

## 10. Dolaşım masası ve görevli kipi (gerçek okuyucu)

- [ ] **10.1 Ödünç ve iade (yönetici kipi)**
  - *Yap:* Dolaşım Masası'nda üye kartını, sonra 8.5'te kaydettiğiniz bir kitabın kütüphane
    etiketini okutun; ardından aynı kitabı kart okutmadan okutun.
  - *Gör:* "Ödünç verildi."; iade tarihi bugünden 15 gün sonra (kapalı güne düşerse izleyen
    açık güne kayar ve bu "Md. 18 gereği" diye sunulmaz); ikinci okutma "İade alındı."
- [ ] **10.2 Sayı sınırı ve ödünç verilmeyen kaynak**
  - *Yap:* Bir öğrenciye 4. kitabı, bir öğretmene 6. kitabı vermeyi deneyin (8.3'te
    etiketlenen Sanat nüshaları ve 8.5'teki kitaplar); 8.3'te etiketlenen bir Danışma
    nüshasını ödünç vermeyi deneyin.
  - *Gör:* "Ödünç sınırı dolu (en çok 3 kitap)." / "(en çok 5 kitap)"; "Ödünç verilmez —
    kütüphanede okunur."
- [ ] **10.3 Hızlı okutma**
  - *Yap:* Bir üyeye 3 kitabı art arda HIZLA okutun; sonra 10 kitabı kart okutmadan art arda
    hızla iade okutun.
  - *Gör:* Hiçbir okutma kaybolmaz; "Sırada bekleyen okutma: N" azalır; masadaki "Bu
    ekrandaki son işlemler" her kitabı yazar.
  - *Kaynak:* F6 ekleri başlığı (gerçek okuyucuyla hızlı okutma); F4 ekleri 9.
- [ ] **10.4 Görevli kipi**
  - *Yap:* **Görevli kipine geç**; ödünç ve iade yapın; **Kartsız ödünç** düğmesini arayın;
    menüden bir yönetici sayfasına gitmeyi deneyin.
  - *Gör:* Üye bağlamında yalnız ad ve kalan hak; **Kartsız ödünç** görünmez; gezinme
    bağlantıları yoktur, her adreste görevli ekranı durur. 3 dakika dokunulmayan yönetici
    kipi kendiliğinden görevli kipine iner; mutlak süre 30 dakikadır.
- [ ] **10.5 Kart okutma kilidi**
  - *Yap:* Görevli kipinde okutma kutusuna sağlaması tutmayan 5 kart numarası yazıp Enter'a
    basın (ya da yıpranmış kart okutun); ardından bir kitabı kartsız okutun.
  - *Gör:* Şerit "Kart okutma durduruldu"; kitabın iadesi yine alınır (iade kilitlenmez);
    şeritteki "Yönetici parolası" ile **Kart okutmayı aç** kilidi kaldırır.
- [ ] **10.6 Gecikme, pusula ve gecikmiş listesi (isteğe bağlı, yalnız deneme bilgisayarında)**
  - *Ön koşul (saati değiştiren her adım — 10.6, 19.2):* Saati BTR'nin yönetici kimliğiyle
    değiştirin (masa hesabı standart kullanıcıdır, sistem saatini değiştiremez). Ayarlar →
    Saat ve dil → **Saati otomatik ayarla** kapalı olmalı; sanal makinede konuk saat
    eşitlemesi de (ör. VirtualBox/Hyper-V tümleştirme hizmetinin saat eşitlemesi) kapatılır,
    yoksa saat adımın ortasında geri çekilir. Adım bitince saati geri alıp otomatik ayarı ve
    eşitlemeyi yeniden açın; **saat doğru olmadan §21'e geçmeyin** (GitHub'ın sertifikası
    ileri tarihte süresi dolmuş görünür).
  - *Yap:* Birkaç ödünç verin; deneme bilgisayarının saatini 20 gün ileri alın; programı
    açın (gün değişimi); Genel Bakış → **Gecikmiş Ödünçler** → İade hatırlatma pusulasını
    ve gecikmiş ödünç listesini basın; pusulayı katlayın. Sonra saati geri alın.
  - *Gör:* A4'te üç pusula; katlanınca dışta yalnız ad şeridi ve "KİŞİYE ÖZELDİR" kalır, iç
    yüz (kaynaklar) görünmez; gecikmeli üyede görevli kipinde tek ileti "Ödünç verilemiyor —
    kütüphane yöneticisine yönlendirin." Henüz şifreli yedek indirilmediyse Genel Bakış'ta
    **Şifreli Yedeği USB Belleğe Alın** kartı da görünür (parola kurulduktan 7 gün sonra
    çıkar — F11 B-1); saat geri alınınca kart yeniden kalkar.
  - *Sorun olursa:* Saati ileri almak günlük yedekleri (14 günden eskileri siler) ve saklama
    taramasını da tetikler; bu adımı gerçek veri olan bilgisayarda YAPMAYIN.
  - *Kaynak:* F6 ekleri başlığı (katlanmış pusula); E4 (§16).

## 11. Teslim, kayıp ve ilişik

- [ ] **11.1 Toplu teslim (okuyucuyla)**
  - *Yap:* Dolaşım Masası → **Teslimler** → **Yeni Teslim** → bir şube → etiketi basılı ve
    rafta duran, ödünç verilebilir 20 kitabı (8.3'teki Sanat nüshaları ve 8.5'teki kitaplar;
    §10'da açık kalan ödünçler hariç) okuyucuyla art arda okutun → **Teslim et** → **Teslim
    listesi**ni basın.
  - *Gör:* Sayı sınırı yok; tek işlem; belge no `<yıl>/<sıra>`; liste Dayanıklı Taşınırlar
    Listesi işlevinde, imza alanlarıyla.
  - *Kaynak:* F7 ekleri başlığı (okuyucuyla toplu teslim); E15 (§16).
- [ ] **11.2 Teslimden geri alma (görevli kipinde)**
  - *Yap:* Görevli kipinde görevli ekranı → **Teslimden geri al** → teslim edilen
    kitaplardan 10'unu okutun → **Okutmayı bitir**; yönetici kipinde **Geri Alma**
    sekmesinden **Geri alma dökümü**nü basın.
  - *Gör:* Kitaplar rafa döner; görevli kime teslim edildiğini görmez.
  - *Kaynak:* F7 ekleri başlığı (görevli kipinde geri alma okutması); E15 (§16).
- [ ] **11.3 Kayıp, hasar ve ilişik belgeleri**
  - *Yap:* Masada bir ödünçte **Kayıp bildir** → Kayıp ve Hasar'da dosyayı açıp **Kayıp/hasar
    tutanağı**nı basın; Genel Bakış → **İlişik Listesi** → bir öğrenci için "Kütüphaneden
    ilişiği yoktur" belgesini ve ilişik listesini basın.
  - *Gör:* Ödünç "Kayba dönüştü"; tutanak tek sayfa; bedel yolları yalnız ortaöğretimde.
  - *Kaynak:* F7 ekleri başlığı (F7 belgelerinin yazıcı çıktısı); E5, E6 (§16).

## 12. Ağ Kataloğu (okul ağı, ikinci bilgisayar, tahta)

Bu bölüm BTR'yle birlikte yapılır. Adres ve blokları bu belgeye ya da herhangi bir
herkese açık yere yazmayın; bilgi notu okulda kalır.

- [ ] **12.1 Açmadan önce ve Ağ Hizmeti Bilgi Notu**
  - *Yap:* Ayarlar → **Ağ Kataloğu**; **Ağ Kataloğunu Açmadan Önce** kartının adımlarını
    izleyin; **Ağ Hizmeti Bilgi Notu'nu bas**.
  - *Gör:* Not en çok iki sayfa; demirbaş no, port ve gerekçesi, kuraldaki GERÇEK uzak adres
    ve profil değerleri, beş maddenin sonucu, programın giden bağlantıları, BTR ve müdür
    imza alanları. Not okulda saklanır.
  - *Kaynak:* S6; E3 (§16); F5 ekleri 14.
- [ ] **12.2 Güvenlik duvarı denetimi — yönetici olmayan masa hesabında**
  - *Yap:* Masa hesabında (yükseltilmemiş) Ağ Doktoru → **Güvenlik Duvarı** kartı →
    **Yeniden denetle**.
  - *Gör:* Beş madde **Geçti** (4. maddede uzak adres "her yer" ise yalnız **Uyarı**);
    hiçbiri **Denetlenemedi** değil; ağ profili Türkçe (Etki alanı/Özel/Genel).
  - *Sorun olursa:* "Denetlenemedi" → PowerShell'in masa hesabında
    `Get-NetFirewallRule -PolicyStore ActiveStore` okuyup okuyamadığını BTR denetler (W15);
    `uygulama.log`.
  - *Kaynak:* W15; §5.7 ("yönetici olmayan hesapta sahada doğrulanır"); §5.10-15; F5 ekleri 16.
- [ ] **12.3 Aç ve dinlemeyi doğrula**
  - *Yap:* **Ağ Kataloğunu aç**. BTR yönetici PowerShell'de:
    `netstat -ano | findstr 8765` ve aynı porta başka bir süreçle bağlanmayı dener:

    ```powershell
    $l = [System.Net.Sockets.TcpListener]::new([ipaddress]::Parse("<IP>"), 8765); $l.Start()
    ```

  - *Gör:* Durum **Açık — http://<IP>:8765**; `0.0.0.0:8765` programın süreç numarasıyla
    DİNLİYOR; ikinci süreç aynı porta bağlanamaz (`Start()` "adres kullanımda" ya da "erişim
    reddedildi" hatasıyla düşer). Seçilen adres doğru ağ kartınındır (varsayılan rota).
  - *Kaynak:* W15, TB12 (tüm arayüzde özel kullanım); F5 ekleri 16, 26.
- [ ] **12.4 İkinci bilgisayardan arama**
  - *Yap:* Okul ağındaki ikinci Windows bilgisayarda: `Test-NetConnection <IP> -Port 8765`;
    Chrome ve Edge'de `http://<IP>:8765` adresini açın; "ŞİİR" arayın; bir eserin sayfasına
    girin; `http://<IP>:8765/api/v1/setup/status/` adresini deneyin.
  - *Gör:* `TcpTestSucceeded : True`; tarayıcı adresi **HTTPS'e zorlamadan** açar; arama,
    programın kendi ekranında (Katalog → Eserler) aynı aramanın verdiği sayıyı verir (OZET'teki
    sayıdan §7.4, §7.5 ve §8.5'te eklenen eserler kadar sapabilir); nüshanın "Ödünçte" olduğu
    görünür, kimde olduğu görünmez; `api` adresi 404.
  - *Sorun olursa:* Dinleyici sınaması (Ağ Doktoru) geçip bu adım düşüyorsa sorun güvenlik
    duvarında ya da ağdadır (öz sınama loopback'ten geçer, kanıt değildir).
  - *Kaynak:* §5.10-15 (Chrome'un HTTPS'e zorlamaması); F5 ekleri 18 (gerçek okul ağı);
    F12 kod kapısı (ağdan arama).
- [ ] **12.5 Tahtadan arama ve klavyesiz gezinme**
  - *Yap:* Bir etkileşimli tahtada (ETAP) tarayıcıyla `http://<IP>:8765/?tahta=1`
    adresini açın; ekran klavyesini kullanmadan **Kaynak Adları** → bir harf → bir eser;
    **Yazarlar** ve **Konular** dizinlerini gezin; aramayı ekran klavyesiyle deneyin. Tahtanın
    eski Chromium'u ve Firefox ESR'si varsa ikisinde de açın.
  - *Gör:* Büyük dokunma düzeni (tahta kipi); klavyesiz bir eserin sayfasına ulaşılır;
    sayfalar iki tarayıcıda da bozulmadan görünür.
  - *Sorun olursa:* Adres açılmıyorsa: vekil sunucu istisnası ya da bölümler arası geçiş
    (`docs/ag-kurulumu.md` §4-§5). Erişim okulun denetiminde değilse Ağ Doktoru → **PYS talep
    metnini kopyala** ile talebi başlatın ve adımı "S2'ye bağlı — ertelendi" diye işaretleyin.
  - *Kaynak:* §5.10-15, §5.10-16; F5 ekleri 16 (tahta, ekran klavyesiz gezinme, eski Chromium
    ve Firefox ESR); F12 kod kapısı (tahtadan arama, S2'ye bağlı); risk 1; S1, S2.
- [ ] **12.6 Yer imleri ve afiş**
  - *Yap:* Ağ Doktoru → **Yer imi dosyalarını üret**; BTR politika dosyasını bir tahtaya
    koyar (`/etc/chromium/policies/managed/`), iki ayrı öğretmen hesabıyla bakılır. **Afişi bas**.
  - *Gör:* Yönetilen yer imi iki hesapta da görünür; afiş tek sayfa, adres büyük puntoyla.
  - *Kaynak:* S1 (Liderahenk ile dağıtım yetkisi); E3 (§16).
- [ ] **12.7 Kilitliyken katalog**
  - *Yap:* Programı **Kilitle**; ikinci bilgisayardan arayın.
  - *Gör:* Katalog çalışmaya devam eder (kişisel veri taşımaz).
- [ ] **12.8 Kural yoksa dinlemez**
  - *Yap:* BTR: `Disable-NetFirewallRule -DisplayName "Kutuphane Defteri Katalog"`; Ağ Doktoru
    **Yeniden denetle**; `netstat -ano | findstr 8765`. Sonra
    `Enable-NetFirewallRule -DisplayName "Kutuphane Defteri Katalog"` → **Yeniden denetle**.
  - *Gör:* Durum **Güvenlik duvarı izni yok**; port hiç dinlenmez (127.0.0.1'e de düşmez);
    kural etkinleşince katalog yeniden açılır.
  - *Kaynak:* çek-listesi 14 (ikinci kısım); §5.7; risk 6.
- [ ] **12.9 Portu değiştir (UAC)**
  - *Yap:* Ayarlar → Ağ Kataloğu → **Portu değiştir** → 8766 → UAC'ye BTR kimliği. Bir kez de
    UAC'yi reddedin. Sonra 8765'e geri alın.
  - *Gör:* Onayda kural ve `HKLM\SOFTWARE\KutuphaneDefteri\KatalogPortu` yeni portu gösterir;
    retle "Yönetici izni verilmedi" ve port değişmez. UAC penceresi açıkken öbür ekranlar
    çalışır (bu ekranın düğmeleri kapalıdır — TB30).
  - *Kaynak:* W18; çek-listesi 16; F5 ekleri 16 (UAC yardımcısı), 13.
- [ ] **12.10 Uyku engeli**
  - *Yap:* Katalog açıkken BTR yönetici komut isteminde `powercfg /requests`; katalogu kapatıp
    yeniden bakın; programdan Çık'tan sonra bir kez daha bakın. Kapağı kapatmayı ya da Başlat
    → Uyku'yu deneyin.
  - *Gör:* Katalog açıkken SYSTEM altında `kutuphane-defteri.exe`; kapalıyken ve Çık'tan sonra
    yok; elle uyutma ve kapak kapatma engellenmez.
  - *Kaynak:* W19; çek-listesi 17 (ilk kısım); F5 ekleri 16 (`SetThreadExecutionState`).
- [ ] **12.11 Birkaç istemci aynı anda (gözlem)**
  - *Yap:* En az 5 tahta/bilgisayardan aynı anda katalogda gezinin; bu sırada kütüphane
    bilgisayarında masada ödünç ve iade yapın. BTR'ye tahtaların kütüphane bilgisayarına tek bir
    NAT adresinden mi geldiğini sorun.
  - *Gör:* Katalog sayfaları gelir; masa yavaşlamaz. Tahtalar tek NAT adresinden geliyorsa hız
    sınırı sınıfı birlikte sınırlayabilir (TB2) — gözlemi yazın.
  - *Kaynak:* F5 ekleri 18 (okul ağı ve Windows paketiyle yük provası); TB2.
- [ ] **12.12 Adres değişimi (BTR uygun görürse)**
  - *Yap:* Adres sabitse atlayın. Değişirse programın gün değişiminde verdiği uyarıya bakın.
  - *Gör:* Ağ Doktoru → Katalog Durumu: "Bu bilgisayarın IP adresi değişti (… → …). Afişi
    yeniden basın, yer imlerini güncelleyin."; afiş yeniden basılınca uyarı kalkar.
  - *Kaynak:* S3.

## 13. Sayım

- [ ] **13.1 Taslak ve seçenekler**
  - *Yap:* Katalog → **Sayım** → **Yeni sayım**: uydurma kurul adları; **Yıl sonu sayımı**;
    **Sayım için hizmet arası**; isteğe bağlı **TMY 32/3 durdurması** (kurulun talep tarihi,
    harcama yetkilisinin adı, durdurma tarihi); ödünçteki/teslimdeki/onarımdaki nüsha seçimleri
    → **Sayımı başlat**.
  - *Gör:* Masada ve Yeni Teslim'de şerit "Sayım için hizmet arası — yeni ödünç ve teslim
    yapılamıyor. İade ve teslimden geri alma açık."; yeni ödünç reddedilir; **iade alınır**.
- [ ] **13.2 Sayım okutması (görevli kipinde, gerçek okuyucu)**
  - *Yap:* Görevli ekranı → **Sayım okutmasını aç** → rafta duran gerçek kitapları (8.5) ve
    basılı etiket tabakasını hızla okutun; bir ISBN barkodu ve bir üye kartı da okutun.
  - *Gör:* "Bulundu."; ISBN ve üye kartı sayıma YAZILMAZ; aynı kitabı ikinci kez okutmak
    zararsızdır; görevli ilerlemeyi ve fazlayı görmez; hiçbir okutma kaybolmaz.
  - *Kaynak:* F9 ekleri başlığı (sayım gününün kendisi); madde 24.
- [ ] **13.3 Fazla ve ikinci sayım**
  - *Yap:* Yönetici kipinde bağlanmamış bir boş etiketi okutun; **Etiketsiz kitap ekle**;
    **Sayımı tamamla** → ikinci sayımı yürütüp tamamlayın.
  - *Gör:* Sayım fazlası kartında görünür; tamamlama penceresi okutulmayanların nasıl
    sınıflandığını söyler.
- [ ] **13.4 Sayım tutanağı**
  - *Yap:* **Sayım Belgeleri** → **Önizle**, **PDF'i indir**, **Excel'i indir**; PDF'i basın.
  - *Gör:* "SAYIM TUTANAĞI"; iki seçenek ve iade ayrı satırlarda; ödünç alanın kimliği YOK;
    yıl sonu sayımında ek "TAŞINIR SAYIM VE DÖKÜM CETVELİNE AKTARILACAK SAYILAR" ve "Bu döküm
    Taşınır Sayım ve Döküm Cetveli değildir…" ibaresi; Excel'de üç sayfa.
  - *Kaynak:* F9 ekleri başlığı (E10'un gerçek yazıcı çıktısı); E10 (§16).
- [ ] **13.5 İptal (onay §15.5'te)**
  - *Yap:* Bu sayımı **İptal et**.
  - *Gör:* Şerit kalkar, yeni ödünç açılır; hiçbir nüsha kayıttan düşülmez.
  - *Dikkat:* Burada **Harcama yetkilisinin onayını işle** SEÇMEYİN. Onay okutulmayan BÜTÜN
    nüshaları "Sayım noksanı (kayıttan düşüldü)" yapar (TMY 32/7); deneme verisinde bu
    katalogun neredeyse tamamıdır (3.367 nüshanın yalnız okuttuklarınız kalır). Ondan sonra
    §14.2'deki ayıklama teklifine ve §15.2'deki dökümlere (E17 süre ölçümü, TB36) kayıtta
    nüsha kalmaz. Onay ayrı bir sayımla §15.5'te sınanır.

## 14. Komisyon, ayıklama, nadir eser, bağış ve yıl sonu raporu

- [ ] **14.1 Bağış**
  - *Yap:* Katalog → **Edinimler ve Bağışlar** → **Bağış Ön Kayıtları** → yeni ön kayıt (uydurma
    bağışçı) → **Bağış ön kayıt listesi**ni basın → komisyon kararı → **Bağış değerlendirme
    sonucu**nu basın.
  - *Kaynak:* F8 ekleri başlığı; E16 (§16).
- [ ] **14.2 Ayıklama**
  - *Yap:* Katalog → **Ayıklama** → üç nüshalık teklif (yıpranma, bilimsel değer kaybı, düzeye
    uygunsuzluk) → karar → onay → uygulama; belgeleri basın.
  - *Gör:* Ayıklama teklif listesi, ayıklama tutanağı, kayıttan düşme teklif listesi, imha
    tutanağı ve devir listesi TMY yoluna göre ayrılır; düzeye uygunsuzluk devir yoluna gider.
  - *Kaynak:* F8 ekleri başlığı; E7 (§16).
- [ ] **14.3 Nadir eser ve yıl sonu raporu**
  - *Yap:* **Nadir Eserler** listesi → **El yazması ve nadir eserler listesi**ni basın; Genel
    Bakış → **Yıl Sonu Raporu** (yıl sonu penceresi dışındaysa Yıl Sonu ekranının son adımından)
    → basın.
  - *Gör:* Yıl sonu kütüphane raporunda kişisel veri yok.
  - *Kaynak:* F8 ekleri başlığı; E8, E9 (§16).

## 15. Raporlar ve dökümler

- [ ] **15.1 İstatistik, çok okunanlar, Ayın Kitapları**
  - *Yap:* **Raporlar** → İstatistik; Çok Okunanlar; **Ayın Kitapları afişi**ni basın.
  - *Gör:* Kişisiz sayılar; çok okunanlar en az 5 farklı üye eşiğiyle ve sayısızdır (deneme
    verisinde az ödünç olduğu için boş olabilir — beklenen).
  - *Kaynak:* F10 ekleri başlığı; E12 (§16).
- [ ] **15.2 Dökümler ve süre**
  - *Yap:* Bu adım herhangi bir sayım ONAYINDAN ÖNCE yapılır (§13.5). Raporlar →
    **Dökümler**: Taşınır Kütüphane Defteri dökümü ve Alfabetik katalog dökümü (yazar, eser,
    konu) — önce süzgeçsiz PDF (süreyi saniye olarak ölçün), sonra XLSX.
  - *Gör:* Alfabetik katalog dökümü OZET'teki eser sayısı kadar (2.000 + sonradan eklenenler)
    eseri kapsar; süreli yayınlar dökümlerde yalnız ciltli nüshalarıyla, OZET'teki "ciltli
    süreli yayın" sayısı kadar yer alır (ciltsiz süreli yayına nüsha açılmaz, bu yüzden
    dökümde bulunamaz); iki PDF'in süresi not edilir (Excel dosyası asıl çalışma biçimidir);
    Türkçe sıralama.
  - *Kaynak:* F10 ekleri başlığı; E11, E17 (§16); TB36.
- [ ] **15.3 İç çıktılar**
  - *Yap:* Okuma ödülü iç çıktısını ve kişi dökümünü yönetici kipinde basın; görevli kipinde
    ulaşmayı deneyin.
  - *Gör:* "İç kullanım" ibaresi; görevli kipinde kapalı.
  - *Kaynak:* F10 ekleri başlığı; E20 ve kişi dökümü (§16).
- [ ] **15.4 Dışa aktarım (isteğe bağlı)**
  - *Yap:* Dışa aktarım dosyasını indirin; §18'deki prova bilgisayarında İçe Aktarma'nın "Dışa
    aktarım dosyası" kipiyle okuyun.
  - *Gör:* Katalog aynı sayılarla gelir (`docs/disa-aktarim.md`).
- [ ] **15.5 Sayım onayı (§15.2'den sonra)**
  - *Yap:* Katalog → **Sayım** → yeni bir sayım (TMY 32/3 durdurması ve hizmet arası
    isteğe bağlı) → **Sayımı başlat** → görevli ekranından bir bölümün (ör. 8.3'teki Sanat)
    rafta duran kitaplarını okutun → **Sayımı tamamla** → **Sayım Belgeleri**'ni basın →
    **Harcama yetkilisinin onayını işle**.
  - *Gör:* Onay tek işlemdir: okutulmayan nüshalar "Sayım noksanı (kayıttan düşüldü)" olur,
    fazla tek edinimle kayda girer, şerit kalkar; Taşınır Kütüphane Defteri dökümü düşülen
    nüshaları kayıt no'suyla tutar, Alfabetik katalog dökümüne yalnız kayıtta nüshası kalan
    eserler girer. Bu adımdan sonra deneme kataloğunun büyük kısmı kayıttan düşülmüş olur
    (beklenen; deneme kurulumu §25.1'de temizlenir).
  - *Kaynak:* F9 ekleri başlığı (sayım gününün kendisi: onay ve kayıttan düşme); E10 (§16).

## 16. Belgelerin yazıcı çıktısı (toplu çizelge)

Her belge gerçek yazıcıda **gerçek boyutta** basılır. Ortak denetim: Türkçe harfler (İ/I,
ğ, ş), antet, "Sayfa n / m" altlığı, taşma yok, imza blokları tam, kişisel veri yalnız
belgenin gerektirdiği yerde.

| Belge | Nerede basılır | Ertelendiği yer | Adım | ☐ |
|---|---|---|---|---|
| E1 Sırt / barkod / boş barkod etiketi, kalibrasyon sayfası | Etiketler | F4 ekleri 9 | 8.1, 8.3, 8.5 | |
| E2 Üye kartı | Kişiler → Kart Basımı | F6 | 9.2 | |
| E3 Katalog afişi, Ağ Hizmeti Bilgi Notu | Ağ Doktoru | F5 ekleri 14, 16 | 12.1, 12.6 | |
| E4 İade hatırlatma pusulası, gecikmiş ödünç listesi | Gecikmiş Ödünçler | F6 ekleri başlığı | 10.6 | |
| E5 "Kütüphaneden ilişiği yoktur" belgesi, ilişik listesi | İlişik Listesi | F7 ekleri başlığı | 11.3 | |
| E6 Kayıp/hasar tutanağı | Kayıp ve Hasar | F7 ekleri başlığı | 11.3 | |
| E7 Ayıklama belgeleri | Ayıklama | F8 ekleri başlığı | 14.2 | |
| E8 El yazması ve nadir eserler listesi | Nadir Eserler | F8 ekleri başlığı | 14.3 | |
| E9 Yıl sonu kütüphane raporu | Yıl Sonu Raporu | F8 ekleri başlığı | 14.3 | |
| E10 Sayım tutanağı (+ ek, XLSX) | Sayım | F9 ekleri başlığı | 13.4, 15.5 | |
| E11 Taşınır Kütüphane Defteri dökümü | Raporlar → Dökümler | F10 ekleri başlığı | 15.2 | |
| E12 Ayın Kitapları afişi | Raporlar → Çok Okunanlar | F10 ekleri başlığı | 15.1 | |
| E13 Kütüphane aydınlatma metni | Kişiler → Üyeler | F6 | 5.1 | |
| E14 Kurtarma anahtarı çıktısı | Sihirbaz, Güvenlik | F1 | 3.2 | |
| E15 Teslim listesi, geri alma dökümü | Teslimler | F7 ekleri başlığı | 11.1, 11.2 | |
| E16 Bağış ön kayıt listesi, bağış değerlendirme sonucu | Edinimler ve Bağışlar | F8 ekleri başlığı | 14.1 | |
| E17 Alfabetik katalog dökümü | Raporlar → Dökümler | F10 ekleri başlığı | 15.2 | |
| E18 Görev devri notu | Ayarlar → Güvenlik → Görev Devri | F11 | 20.1 | |
| E19 Masa kartı | Kişiler → Üyeler | F6 | 5.2 | |
| E20 Okuma ödülü iç çıktısı, kişi dökümü | Raporlar | F10 ekleri başlığı | 15.3 | |

## 17. Yedek, USB'ye dış kopya ve gün değişimi

- [ ] **17.1 Günlük yedek**
  - *Yap:* `%LOCALAPPDATA%\KutuphaneDefteri\backups` klasörüne bakın.
  - *Gör:* Parola kurulduktan sonra en geç bir saat içinde `gunluk-<tarih>.kdbak`.
- [ ] **17.2 Şifreli yedeği USB belleğe alma**
  - *Yap:* Ayarlar → Güvenlik → **Şifreli Veritabanı Yedeği** → **Şifreli yedeği indir** →
    dosyayı İndirilenler'den USB belleğe **taşıyın**.
  - *Gör:* Aynı kartta "Son şifreli yedek gg.aa.yyyy tarihinde indirildi (0 gün önce)." ve
    "Genel Bakış 30 gün sonra yeniden hatırlatır." yazar. (Genel Bakış'taki **Şifreli Yedeği
    USB Belleğe Alın** kartı hiç indirme yokken parola kurulduktan 7 gün sonra çıkar; önerilen
    1-3 günlük akışta görünmez — gözlemi §10.6'dadır.)
  - *Kaynak:* F11 ekleri B-1; F12 kod kapısı (yedek).
- [ ] **17.3 Gün değişimi ve uyku**
  - *Yap:* Programı gece tepside açık bırakın; bir gece de bilgisayarı uykuya alıp sabah
    uyandırın.
  - *Gör:* Ertesi gün yeni `gunluk-<tarih>.kdbak` (program kapanmadan); uykudan uyanan
    bilgisayarda en geç bir saat içinde; uyku sonrası rotasyon önceki günlerin yedeklerini
    silmez (14 günden yeni hiçbir yedek kaybolmaz).
  - *Uzun süreli gözlem (gerçek kurulumda, 15. günden sonra):* 14 günden eski günlük
    yedekler kendiliğinden silinir, `backups` klasöründe en çok 14 günlük yedek kalır.
    Protokolün süresi içinde gözlenemez; kod tarafında testlidir.
  - *Kaynak:* F5 ekleri 28 (uyku dahil açık kalma saati, `GetTickCount64`); §5.10-17'nin sahadaki
    karşılığı; T9.
- [ ] **17.4 Eski masaüstünde yazma hızı (HDD)**
  - *Yap:* HDD'li eski bir masaüstünde (deneme bilgisayarı sanal makine ya da SSD'liyse:
    okulun kütüphane bilgisayarında gerçek kurulumdan sonra) bir üyeye 20 kitabı art arda
    ödünç verip hepsini iade okutun. Kronometreyle ölçün: ilk okutmadan son "İade alındı."
    iletisine dek geçen süre ve en uzun tek bekleme.
  - *Gör:* 40 okutmanın toplam süresi okutma hızınızla belirlenir (okutma başına ek bekleme
    yarım saniyeyi geçmez); ölçülen iki değer §27'ye ve kayıt çizelgesindeki disk türüyle
    yazılır.
  - *Sorun olursa:* HDD'li bilgisayarda ölçüm yapılamadıysa kutuyu işaretlemeyin: TB3'ün saha
    ölçümü AÇIK kalır (sanal makinedeki ölçüm TB3'ü kapatmaz).
  - *Kaynak:* TB3 (`synchronous=FULL` saha ölçümü); F4 ekleri 8 (dosya tabanlı WAL beklemesi).

## 18. Temiz bilgisayarda geri yükleme (yedekten yeni bilgisayara)

`docs/kurulum.md` §7 ve §7.1'deki adımlar; ikinci demirbaş bilgisayarda ya da sanal makinede.

- [ ] **18.1 Kurulum ve sihirbazda parola kurulmuş hâl**
  - *Yap:* İkinci bilgisayara programı kurun; kurulum sonunda açılan sihirbazda BAŞKA bir
    deneme parolası kurup programdan **Çık**.
  - *Gör:* Program tepsiden de kapanmış (Görev Yöneticisi).
  - *Kaynak:* F11 düzeltme turu D-11.
- [ ] **18.2 Kurtarma anahtarıyla geri yükleme**
  - *Yap:* 17.2'deki yedeği ikinci bilgisayarın `backups` klasörüne kopyalayın; Başlat →
    **Kütüphane Defteri — Yedekten Geri Yükle**; parola yerine **kâğıttaki kurtarma
    anahtarını** yazın. Birinci bilgisayarın `data\verilmis-kartlar.txt` dosyasını ikinci
    bilgisayarın `data` klasörüne koyun.
  - *Gör:* Geri yükleme başarılı; sihirbazda kurulan yabancı güvenlik dosyası
    `guvenlik-arsiv-*.json`, boş veritabanı `db-onceki-*` adıyla kenara alınır.
  - *Sorun olursa:* Çıkış kodu 9 → anahtarı ya da parolayı denetleyin; `uygulama.log`.
- [ ] **18.3 Karşılaştırma**
  - *Yap:* Programı açın, kilidi BİRİNCİ bilgisayarın parolasıyla açın; kitap, üye ve açık ödünç
    sayılarını karşılaştırın; bir öğrencinin adını ve okul numarasını açın.
  - *Gör:* Sayılar birebir; adlar ve okul numaraları okunur (şifre çözülür); Ağ Kataloğu
    yedekteki ayara göre davranır.
  - *Kaynak:* F11 ekleri B-2 ve K-3 (okulun kendi provası); F12 kod kapısı (yedek/geri yükleme).
- [ ] **18.4 Temizlik**
  - *Yap:* Programdan Çık; ikinci bilgisayardaki veri, yedek ve günlük klasörlerini silin;
    programı kaldırın.
  - *Gör:* Kaldırma veri klasörünü silmez (bu yüzden elle silinir).

## 19. Saklama tetiği

- [ ] **19.1 Önizleme**
  - *Yap:* Ayarlar → **Saklama** → **Süresi Dolan Kayıtlar**; **Ne Kalır** kartını okuyun.
  - *Gör:* Deneme verisinde süre dolmadığı için silinecek ya da bağı koparılacak kayıt yok;
    Ne Kalır kartı yedeklerdeki kopyaları sayar.
- [ ] **19.2 Tetik (isteğe bağlı, yalnız sanal makinede, anlık görüntüyle)**
  - *Ön koşul:* §10.6'daki saat ön koşulu (BTR kimliği, otomatik saat ve konuk saat
    eşitlemesi kapalı). Adımdan ÖNCE sanal makinenin **anlık görüntüsünü** (snapshot) alın.
  - *Yap:* Ayrılış Havuzu'nda birkaç kişiyi ayırın; sanal makinenin saatini 3 yıl ileri alın;
    programı açın; Genel Bakış'taki **Saklama Süresi Dolan Kayıtlar** kartından Saklama
    ekranına gidin → **Silinecek kişileri göster** → **Onayla ve uygula** (yönetici parolası,
    "Bu işlemin geri alınamayacağını anladım"). Gözlemden sonra sanal makineyi **anlık
    görüntüye döndürün** (saat ve veri adım öncesine döner); §20-§23'e ancak ondan sonra
    geçin. Anlık görüntü alınamıyorsa bu adımı protokolün en sonuna (§24'ten önce) bırakın.
  - *Gör:* İşlemden hemen önce `pre-anonim-<tarih>-<saat>.kdbak` yedeği; **Son İşlem** kartı
    şifreli yedek hatırlatması yapar; kişisi silinen bir teslimin yeniden basılan listesinde
    "Anonimleştirilmiş kopya — ıslak imzalı asıl nüsha okul arşivindedir" ibaresi.
  - *Sorun olursa:* Saat ileri alındığında günlük yedekler de silinir; bu adımı gerçek veri
    olan bilgisayarda YAPMAYIN.
  - *Kaynak:* F11 (saklama tetiği — kod kapısında sınandı, sahada gözlem).

## 20. Görev devri

- [ ] **20.1 Görev devri akışı**
  - *Yap:* Ayarlar → Güvenlik → **Görev Devri** → **Görev devrini başlat** (mevcut ve yeni
    deneme parolası) → yeni anahtarı kartın içinde saklatıp doğrulayın → uydurma adlarla
    **Görev devri notunu indir** → basın.
  - *Gör:* Not en çok iki sayfa, imza bloğu tam; "notun düzenlendiği gün açık işler" kişisiz
    sayılardır; teslim listesinde "Kütüphane masası Windows hesabının parolası değiştirildi".
  - *Kaynak:* F11 ekleri B-4; E18 (§16).
- [ ] **20.2 Yeni parola**
  - *Yap:* Kilitle; önce eski parolayla, sonra yeni parolayla açmayı deneyin.
  - *Gör:* Bu bilgisayarda eski parola kilidi açmaz, yeni açar (eski yedeklerin sınırı
    `docs/kurulum.md` §1.6'da yazılıdır).

## 21. Güncelleme denetimi ve güncelleme kurulumu

- [ ] **21.1 Şimdi denetle (okul ağında)**
  - *Yap:* Önce bilgisayarın tarihi ve saati doğru olmalı (§10.6 ve §19.2'den sonra geri
    alındı mı?). Ayarlar → **Güncelleme** → **Şimdi denetle**. BTR:
    `Test-NetConnection api.github.com -Port 443`, `Test-NetConnection github.com -Port 443`
    ve kurulum dosyasının indirildiği adres için `Test-NetConnection
    release-assets.githubusercontent.com -Port 443` (GitHub dosya bağlantısı
    `*.githubusercontent.com`'a yönlenir — `release-assets.` ya da `objects.` alt adına; Ağ
    Hizmeti Bilgi Notu'ndaki listededir).
  - *Gör:* GitHub'a erişim varsa **Kurulu sürüm** ve **Yayımlanan son sürüm**; ön sürüm
    döneminde en yeni ön sürüm gösterilir ("Uygulama güncel." ya da "Yeni sürüm hazır: …").
    Erişim yoksa "GitHub'a ulaşılamadı; okul ağında engellenmiş olabilir. Yeni sürümü
    indir.okulapp.org'dan elle denetleyebilirsiniz." ve altındaki
    `okulapp.org/kutuphane-defteri` bağlantısı bilgisayarın tarayıcısında açılır (sayfa site
    adımı yayına girene dek bulunamayabilir). Program açılışta internete çıkmamıştır.
  - *Sorun olursa:* "GitHub ile güvenli bağlantı doğrulanamadı…" iletisi ağ engeli DEĞİLDİR:
    önce bilgisayarın tarih ve saatini denetleyin; doğruysa okul ağı güvenli bağlantıları
    araya girerek denetliyordur (BTR'ye bildirin). "GitHub'a ulaşılamadı…" iletisinde erişim
    talebi Yardım Masası Modülü'nden; hedefler Ağ Hizmeti Bilgi Notu'nda.
  - *Kaynak:* F11 ekleri E-6, KR-1; kullanıcı kararı 1 (site ayrı adım) ve 3 (beta).
- [ ] **21.2 Doğrula ve indir (GitHub erişimi varsa)**
  - *Yap:* Yeni sürüm varsa **Doğrula ve indir**.
  - *Gör:* "Kurulum dosyası doğrulanarak indirildi."
  - *Sorun olursa:* Denetim çalışıp indirme düşüyorsa `*.githubusercontent.com` engellidir
    (21.1'deki üçüncü sınama); kurulum dosyasını `indir.okulapp.org`'dan elle indirip
    §1.3.2'deki gibi doğrulayın.
- [ ] **21.3 Güncelleme kurulumu (program tepsideyken)**
  - *Yap:* Portu 12.9'daki gibi yeniden 8766'ya çevirin (12.9'un sonunda 8765'e geri
    alınmıştı) ve BTR'ye kurala bir tahta bloğu ekletin (ya da Ağ Doktoru'ndan ekleyin). Program tepsideyken yeni sürümün (yoksa aynı sürümün) kurulum
    dosyasını masa hesabında `/LOG` ile çalıştırın; UAC'ye BTR kimliği. Bir kez de program
    **görevli kipindeyken** deneyin.
  - *Gör:* Program en çok 30 saniyede kendiliğinden düzenli kapanır ve kurulum sürer; kurulum
    günlüğünde "Kapatma olayı gönderildi." ve "Program düzenli kapandı."; güvenlik duvarı
    kuralı, port 8766 ve eklenen blok DEĞİŞMEDİ; `HKLM…\KatalogPortu` korundu; sürüm değiştiyse
    `backups` içinde `pre-migrate-<sürüm>-<tarih>.kdbak`; Uygulamalar listesinde tek bir
    "Kütüphane Defteri" kaydı (yan yana ikinci kurulum yok); program açılınca veriler yerinde.
  - *Sorun olursa:* 30 sn bekleyip "Kütüphane Defteri hâlâ çalışıyor…" diyorsa (Yeniden
    Dene/İptal) kapatma olayı ulaşmamıştır: günlükte "Kapatma olayı açılamadı" (W11, W12).
    Kurulum dosyası süreci zorla sonlandırmaz (beklenen).
  - *Kaynak:* W11, W12, W16; çek-listesi 9, 14 (güncelleme kipi); TB14; F12 satırı (kapatma
    olayı, iki mutex, güncelleme kipinde kural korunur, yeni GUID/AppId); risk 14;
    CLAUDE.md §7 F0 (açık programın kapatılması).
- [ ] **21.4 Eski program, yeni veri (isteğe bağlı; iki sürüm yayımlandıktan sonra)**
  - *Yap:* Yeni sürümle açılmış veriyi eski sürümün kurulum dosyasıyla açmayı deneyin.
  - *Gör:* "Program sürümü eski" iletisi, çıkış kodu 4; veri bozulmaz.
  - *Kaynak:* F11 ekleri B-3.

## 22. Kaldırma

- [ ] **22.1 Program açıkken kaldırma**
  - *Yap:* Program tepsideyken Ayarlar → Uygulamalar → Kütüphane Defteri → Kaldır (UAC'ye BTR
    kimliği). Sonra BTR:

    ```powershell
    Get-NetFirewallRule -DisplayName "Kutuphane Defteri Katalog"
    schtasks /Query /TN "Kutuphane Defteri"
    reg query HKLM\SOFTWARE\KutuphaneDefteri
    ```

  - *Gör:* Program kendiliğinden kapanır; kural, zamanlanmış görev ve kayıt defteri anahtarı
    BULUNAMAZ; Başlat menüsü kısayolları gider; veri klasörü (`%LOCALAPPDATA%\KutuphaneDefteri`)
    KALIR.
  - *Sorun olursa:* Görev kaldıysa "dosya bulunamadı" hatası verir (W17).
  - *Kaynak:* W11, W16, W17; çek-listesi 9 (kaldırma), 14 (kaldırma); CLAUDE.md §7 F0.
- [ ] **22.2 Deneme verisinin temizliği**
  - *Yap:* `%LOCALAPPDATA%\KutuphaneDefteri` klasörünü, USB'deki deneme yedeklerini ve
    `deneme-verisi` kopyalarını silin; deneme kurtarma anahtarı kâğıdını yırtın.

## 23. Taşınabilir sürüm ve WebView2'siz bilgisayar

- [ ] **23.1 Taşınabilir zip USB'den**
  - *Yap:* `…-win64-portable.zip`'i USB belleğe açıp `kutuphane-defteri.exe`'yi çalıştırın.
  - *Gör:* SmartScreen çıkmaz (FAT32/exFAT biçimli bellekteki dosya internetten indirildi
    işaretini taşımaz); Ağ Kataloğu sunulmaz: açılmak istenirse durum "Güvenlik duvarı izni
    yok" olur, Ağ Doktoru'nda 1. ya da 2. madde geçmez (kurulumun kuralı kurulu programın
    yoluna bağlıdır) ve katalog okul ağına açılmaz; otomatik başlatma yok. Bu adımda
    **"Kuralı ekle/güncelle"yi KULLANMAYIN**: kuralı taşınabilir sürümün yoluna yazar,
    katalog açılır ve aynı bilgisayardaki kurulu programın kuralının yerini alır (bilinen
    fark — tasarım §14.1 F12 ekleri KT-2; Windows'ta kesin kapı ayrı kullanıcı kararıdır).
    Pardus'un taşınabilir arşivinde katalog hiç açılmaz (24.11).
  - *Kaynak:* çek-listesi 6; §5.2 (GA-5).
- [ ] **23.2 WebView2 olmayan bilgisayar**
  - *Yap:* WebView2 kurulu olmayan bir Windows 10'da taşınabilir sürümü açın.
  - *Gör:* Türkçe yönlendirme penceresi, çıkış kodu 7; beyaz pencere DEĞİL.
  - *Kaynak:* çek-listesi 5; W5.

## 24. Pardus (kısaltılmış zincir)

**Pardus 21 (Debian 11 tabanı) ZORUNLUDUR**: en az 24.1, 24.2, 24.3 ve 24.5 Pardus 21'de
yapılır. PySide6'nın 6.8.3'te sabitlenmesinin (TB27) ve derleme tabanının (TB5) tek
gerekçesi Pardus 21'dir; CI'daki debian:11 kabı yalnız `--autotest`'i koşar, pencere ve Qt
WebEngine açmaz. Pardus 23 (Debian 12) isteğe bağlıdır (zincirin tamamı ya da bir kısmı).
Temiz Debian kaplarında kurulum provası paketleme hattında (`packaging/linux/test-kurulum.sh`)
her derlemede koşar; burada gerçek masaüstü sınanır.

- [ ] **24.1 `.deb` kurulumu, boyut ve lisans bildirimleri**
  - *Yap:* `sudo apt install ./kutuphane-defteri_<sürüm>_amd64.deb`;
    `du -sh /opt/kutuphane-defteri`; `ls /usr/share/doc/kutuphane-defteri/`.
  - *Gör:* Bağımlılıklar depodan kurulur; menüde "Kütüphane Defteri"; kurulu boyutu not
    edin; `/usr/share/doc/kutuphane-defteri/` altında `copyright` (Debian biçimi) ve
    `THIRD_PARTY_LICENSES` bağlantısı (`/opt/kutuphane-defteri/THIRD_PARTY_LICENSES`'a gider;
    içinde `BENIOKU.txt`, `paket-icerigi.txt`, `yerel-kutuphaneler/`); programın lisansı
    `/opt/kutuphane-defteri/LICENSE.txt`. `BENIOKU.txt`'deki yazılı teklif Qt ve PySide6'yı
    sürümüyle anar; `copyright`'ın ilk paragrafı teklife işaret eder.
  - *Kaynak:* F12 satırı (.deb); TB27 (boyut), TB28 (lisans); TB5 (hangi Pardus sürümü).
- [ ] **24.2 Tanılama**
  - *Yap:* `kutuphane-defteri --autotest; echo $?`, `kutuphane-defteri --bagimlilik-duman; echo $?`,
    `kutuphane-defteri --pdf-duman /tmp/deneme.pdf; echo $?`,
    `kutuphane-defteri --dagitim-duman kurulu; echo $?`.
  - *Gör:* Dördü `0`; PDF'te Türkçe harfler doğru; son komut "Dağıtım türü: kurulu" yazar
    (`.deb` ile kurulan program kendini kurulu sayar — Ağ Kataloğu buna bağlıdır, KB-2).
- [ ] **24.3 Qt tepsi ve pencere**
  - *Yap:* Programı menüden açın; çarpıya basın; tepsi simgesinden açın; tepsiden Çık.
    Tepsisi olmayan bir masaüstünde (GNOME) de deneyin.
  - *Gör:* Tepsili masaüstünde çarpı gizler, tepsi geri getirir, Çık süreci bitirir; tepsisiz
    masaüstünde çarpı pencereyi küçültür ve çıkış yolu üst çubuktaki **Çık**'tır.
  - *Kaynak:* CLAUDE.md §7 F0 (Pardus Qt tepsisi); risk 4.
- [ ] **24.4 Sihirbaz ve deneme verisi**
  - *Yap:* §3'ü kısaca yapın; §6.1-6.2, §7.1-7.3 ve §9.1-9.3'ü (üyelik, kart basımı, kart
    okutma) deneme dosyalarıyla tekrarlayın (daha kısa sürmesi için `--eser 300` ile ayrı bir
    klasöre üretim kullanılabilir).
  - *Gör:* Kullandığınız üretimin OZET'indeki sayılar (`--eser 300` ile üretildiyse o
    klasörün OZET'i — Windows'takinden farklıdır).
  - *Kaynak:* F12 kod kapısı ("Pardus'ta aynı zincir").
- [ ] **24.5 Etiket önizlemesi ve basım (CUPS)**
  - *Yap:* §8.1 ve §8.3'ü yapın.
  - *Gör:* PDF önizlemesi Qt WebEngine penceresinde görünür (görünmezse "PDF'i indir" tam
    işlevlidir); kalibrasyon çizgisi 100 mm.
  - *Kaynak:* F4 ekleri 9 (Qt WebEngine önizlemesi).
- [ ] **24.6 Dolaşım ve okuyucu**
  - *Yap:* §10.1 ve §10.3'ü okuyucuyla yapın: 24.4'te basılan üye kartını, sonra 24.5'te
    (8.3) etiketlenen bir kitabın etiketini okutun.
  - *Gör:* Okuyucu klavye gibi çalışır; hızlı okutmada kayıp yok.
- [ ] **24.7 Ağ Kataloğu ve güvenlik duvarı (ufw/firewalld)**
  - *Yap:* Ayarlar → Ağ Kataloğu → Ağ Doktoru'ndaki komutu BTR çalıştırır (Pardus'ta program
    kural açmaz); `sudo ufw status numbered` (ya da `sudo firewall-cmd --list-rich-rules`);
    Ağ Kataloğunu açın; ikinci bilgisayardan `curl -I http://<IP>:8765/` ve tarayıcıyla arama;
    bir tahtadan açma.
  - *Gör:* Komut **kaynak sınırlıdır**: her yerel ağ ve tahta bloğu ayrı satır, /16'dan geniş
    blok ve "her yer" yok; yanıt `200 OK` ve `Content-Security-Policy` başlığı; arama çalışır.
  - *Kaynak:* F12 satırı (.deb ufw/firewalld); F5 ekleri 27; §5.7 Pardus.
- [ ] **24.8 Uyku engeli (`systemd-inhibit`)**
  - *Yap:* Katalog açıkken `systemd-inhibit --list`; katalogu kapatıp yeniden bakın; katalog
    açıkken programı `pkill -9 -f kutuphane-defteri` ile öldürüp yeniden bakın.
  - *Gör:* Açıkken WHO "Kütüphane Defteri", WHY "Ağ Kataloğu açık", WHAT `idle`, MODE `block`;
    kapalıyken ve program öldürüldükten sonra satır YOK (engel yetim kalmaz).
  - *Kaynak:* §4.5 ("systemd-inhibit sahada doğrulanır"); F5 ekleri 16, 28.
- [ ] **24.9 Gün değişimi ve uyku**
  - *Yap:* §17.3'ü Pardus'ta yapın.
  - *Gör:* Uykudan uyanınca en geç bir saat içinde o günün yedeği.
  - *Kaynak:* F5 ekleri 28 (`CLOCK_BOOTTIME`).
- [ ] **24.10 Yedek ve geri yükleme**
  - *Yap:* Ayarlar → Güvenlik'ten şifreli yedek indirin; indirilen dosyayı
    `~/.local/share/kutuphane-defteri/backups/` klasörüne kopyalayın (geri yükleme aracı
    yalnız bu klasörü listeler); programdan Çık; uçbirimde `kutuphane-defteri --geri-yukle`.
  - *Gör:* İndirilen yedek listede; geri yükleme parolayla ve kurtarma anahtarıyla çalışır.
- [ ] **24.11 Taşınabilir arşiv: Ağ Kataloğu açılamaz**
  - *Yap:* Önce `.deb` programından **tepsiden Çık** (iki sürüm aynı veri klasörünü ve aynı tek
    kopya kilidini kullanır: `.deb` programı açıkken taşınabilir sürüm başlamaz, açık pencere
    öne gelir). `tar -xzf …-linux-x64.tar.gz`, `./kur.sh`; programı **tam yolla** açın:
    `~/.local/opt/kutuphane-defteri/kutuphane-defteri` (`.deb` kuruluyken menü ve
    `kutuphane-defteri` komutu artık taşınabilir sürümü açar). Uçbirimde
    `~/.local/opt/kutuphane-defteri/kutuphane-defteri --dagitim-duman tasinabilir; echo $?`.
    Ayarlar → Ağ Kataloğu ve Ağ Doktoru ekranlarına, tepsi menüsüne bakın; ikinci
    bilgisayardan `curl -I http://<IP>:8765/`. Sonra **Çık**, `./kaldir.sh`; programı
    **menüden** açın.
  - *Gör:* Menü kaydı eklenir; arşivin `BENIOKU.txt`'si Ağ Kataloğunun bu arşivde sunulmadığını
    ve `.deb`'den önce `./kaldir.sh` gerektiğini yazar, lisansları gösterir
    (`uygulama/LICENSE.txt`, `uygulama/THIRD_PARTY_LICENSES/BENIOKU.txt`). Duman komutu
    "Dağıtım türü: tasinabilir" ve `0`. **Ağ Kataloğu açılamaz:** iki ekranda "Bu taşınabilir
    sürümde…" ya da (`.deb` kurulu olduğu için beklenen) "Açık olan program taşınabilir
    sürümdür; bu bilgisayarda .deb paketi de kurulu…" bandı; **"Ağ Kataloğunu aç" düğmesi
    yoktur** (hata değildir); tepsi satırı "Ağ Kataloğu: taşınabilir sürümde sunulmaz",
    tepside "Ağ Kataloğunu aç" yok; Ağ Doktoru güvenlik duvarı komutu, sınama komutu ve
    belgeleri (afiş, yer imleri, PYS metni, bilgi notu) vermez. 24.7'den ayar açık kaldıysa
    (veri klasörü ortaktır) rozet **"Açılamadı"** ve son hata "Ağ Kataloğu açılmadı: açık olan
    program taşınabilir sürümdür, bu bilgisayarda ise .deb paketi de kurulu…" olur, "Ağ
    Kataloğunu kapat" durur — bu beklenen durumdur, ayarı KAPATMAYIN (son adımda `.deb`
    programı kullanır). Katalog hiçbir adreste dinlemez, ikinci bilgisayardan bağlantı
    kurulamaz; programın öbür işleri katalogsuz olağan çalışır. `./kaldir.sh`'ten sonra menüden
    açılan program `.deb`'inkidir: ayar açıksa **Ağ Kataloğu açılır** (ikinci bilgisayardan
    `curl -I` → `200 OK`); menü kaydı ve `kutuphane-defteri` komutu yeniden `.deb`'e döner.
  - *Sorun olursa:* Katalog taşınabilir sürümde açıldıysa, dinliyorsa, ekran nedeni
    söylemiyorsa ya da `./kaldir.sh`'ten sonra menüden açılan program katalogu açmıyorsa §27'ye
    yazın (`uygulama.log`, `logs/tanilama.log`).
  - *Kaynak:* F5 ekleri 27; KULLANICI KARARI 28.09.2026 (KB-2 — tasarım §5.2, F12 ekleri karar
    turu KT-2); KB-2 düzeltme turu (29.09.2026: `.deb`'e geçişte kısayol gölgelemesi, dağıtım
    duman testi).
- [ ] **24.12 Güncelleme ve kaldırma**
  - *Yap:* Önce **tepsiden Çık** (Pardus paketi açık programı kendiliğinden kapatmaz —
    `docs/kurulum.md` §4.1). Aynı (ya da yeni) `.deb`'i `sudo apt install ./…deb` ile yeniden
    kurun, programı açıp verilerin yerinde olduğunu görün, yeniden Çık. Gözlem (KB-4
    kararının koşuludur, atlamayın; gerçek veri bulunmayan deneme kurulumunda yapın): program AÇIKKEN
    yeniden kurmayı deneyip ne olduğunu §27'ye yazın — sorun görülürse `.deb`'in açık programı
    düzenli kapatması kararlı sürümden önce yapılır. Sonra BTR açtığı
    ufw/firewalld kurallarını kaldırır (`sudo ufw delete allow from <blok> to any app
    'Kutuphane Defteri'`); en son `sudo apt remove kutuphane-defteri`.
  - *Gör:* Yeniden kurulumdan sonra veriler yerinde; kaldırmada program menüden gider; veri
    `~/.local/share/kutuphane-defteri` altında KALIR (elle silinir).
  - *Kaynak:* F12 düzeltme turu D-13; KULLANICI KARARI 28.09.2026 (KB-4 — tasarım F12 ekleri
    karar turu KT-4, KT-5); TB40.

## 25. Deneme bittikten sonra: gerçek kullanıma geçiş

- [ ] **25.1 Deneme kurulumunu temizle** — Çık; veri, yedek ve günlük klasörlerini silin
  (`docs/kurulum.md` §6 tablosu); deneme USB yedeklerini ve `deneme-verisi` kopyalarını silin;
  deneme kurtarma anahtarı kâğıtlarını yırtın. Deneme sanal makinesini kapatın.
- [ ] **25.2 Gerçek kurulum** — `docs/kurulum.md` §3 (masa hesabı, BTR'nin UAC kimliği); gerçek
  yönetici parolası en az iki görevlendirilmiş kişide, kurtarma anahtarı müdürlükte kapalı
  zarfta (S11).
- [ ] **25.3 Duyuru ve görevlendirme** — Kütüphane aydınlatma metni e-Okul aktarımından ÖNCE
  duyurulur; görevli öğrenciler müdürlükçe yazılı görevlendirilir ve masa kartı verilir (S7).
- [ ] **25.4 Gerçek e-Okul listesinin biçim kanıtı** — okulun e-Okul'undan indirilen, HİÇ
  DEĞİŞTİRİLMEMİŞ `.XLS` raporu **Önizle**: "şube bloğu" notu, atlanan satır yok, I/İ
  şubeleri ayrı. Sonra **Aktar**; e-Okul dosyasını bilgisayardan silin (`docs/kurulum.md` §1.2).
  e-Okul raporunun yerleşimi değiştiyse bu adım onu ilk gösteren yerdir: bulgu, KİŞİ ADI ve
  NUMARASI OLMADAN (yalnız sütun başlıkları ve blok başlığının biçimi) bildirilir; blok
  başlığındaki il, ilçe ve okul adı `<il>`, `<ilçe>`, `<okul>` yer tutucularıyla değiştirilir
  (ör. "T.C. / <il> VALİLİĞİ / <ilçe> / <okul> Müdürlüğü").
- [ ] **25.5 Dönüşüm planı** — önce etiket yoluyla (§8.5) raf raf dönüşüm, doğrulama okutması;
  kim, hangi takvim, etiket stoğu (S9).

## 26. Eşleme tablosu: kaynak madde → protokol adımı

Her ertelenmiş saha kanıtı ve saha maddesi aşağıda bir adıma bağlıdır. "Kod" sütunu
kanıtın kod tarafının (test, paket hattı) nerede alındığını, "Adım" sütunu sahadaki
adımı gösterir.

### 26.1 Tasarım §14.1, F12 satırı

| Kaynak madde | Kod tarafı | Protokol adımı |
|---|---|---|
| Inno: yeni GUID (AppId değişmez) | paket hattı | 2.2, 21.3 (tek kayıt, yan yana kurulum yok) |
| Inno: WebView2 | paket hattı | 2.4, 23.2 |
| Inno: iki mutex | F0 spike | 4.2, 21.3 |
| Inno: kapatma olayı | F0 spike | 21.3, 22.1 |
| Inno: güncelleme kipinde kural korunur | F5 derlemesi | 21.3 |
| `.deb` (ufw/firewalld) | paket hattı, `test-kurulum.sh` | 24.1, 24.7, 24.12 |
| `veri_sizintisi` ×2 | paket hattı (Windows ve Linux) | — (kod kapısı; sahada adım gerekmez) |
| Belgeler: kurulum, ağ kurulumu, yeni bilgisayara taşıma, kılavuz, masa kartı | `docs/`, kılavuz testleri | 2-3 (kurulum), 12 (ağ), 18 (taşıma), 5.2 (masa kartı); kılavuz her adımda |
| okulapp.org alanı (§17) | kullanıcı kararı 1: ayrı adım (okulapp.org deposu) | 1.3.1, 21.1 (bağlantının açılması) |
| Kod kapısı: temiz Windows 11'de kurulum | — | 2.1-2.5 |
| Kod kapısı: sihirbaz | — | 3.1-3.5 |
| Kod kapısı: e-Okul | deneme verisi testi | 6.1-6.4 |
| Kod kapısı: Excel katalog | deneme verisi testi | 7.1-7.4 |
| Kod kapısı: etiket | — | 8.1-8.8 |
| Kod kapısı: dolaşım | — | 10.1-10.6 |
| Kod kapısı: ağdan arama | iki kaplı prova (F5 ekleri 18) | 12.4 |
| Kod kapısı: yedek/geri yükleme | geri yükleme provası (F11 B-2) | 17.1-17.2, 18.1-18.4 |
| Kod kapısı: Pardus'ta aynı zincir | `test-kurulum.sh` (Debian 11/12 kapları) | 24.1-24.12 |
| Kod kapısı: tahtadan arama (S2'ye bağlı) | — | 12.5 |
| Kod kapısı: gerçek okuyucu | — | 8.4, 8.6, 9.3, 10.3, 11.1, 13.2 |

### 26.2 "F<n> ekleri"ndeki ve tasarımın öbür bölümlerindeki saha maddeleri

| Kaynak madde | Protokol adımı |
|---|---|
| §4.2-3: Windows oturumu açılmadan program ve katalog kalkmaz | 4.6 |
| §4.5 Tepsi: pystray lisans metni ve kaynağı pakete girer (F12'de) | 2.2 (Windows: `_internal\pystray\` kaynak dosyaları ve `THIRD_PARTY_LICENSES\`), 24.1 (Pardus: Qt/PySide6 LGPL bildirimi) |
| §4.5 Uyku: "Linux'ta systemd-inhibit kullanılır; sahada doğrulanır" | 24.8 |
| §4.5 F0 spike'ı (Windows pystray, Linux Qt) gerçek pencerede | 4.1, 4.3, 24.3 |
| §5.7: "Denetimin yönetici olmayan hesapta çalıştığı sahada doğrulanır (F5 eki)" | 12.2 |
| §5.10-15: yönetici olmayan hesapta kural denetimi · Chrome ve ETAP Chromium HTTPS'e zorlamaz · tahtadan erişim | 12.2 · 12.4, 12.5 · 12.5 |
| §5.10-16: klavyesiz gezinme (sahada tahtada) | 12.5 |
| §14.1 kurallar: tahta erişimi S2'ye, gerçek okuyucu S4'e bağlı, F12'ye ertelenir | 12.5; 8.4, 10.3 |
| §14.1 F4 satırı: "gerçek okuyucu: F4 eki → F12" | 8.4, 8.6 |
| §14.1 F5 satırı: "tahta ve saha testleri (§5.10-15): F5 eki → F12" | 12.2, 12.4, 12.5 |
| F4 ekleri başlığı ve madde 9: gerçek yazıcıda basım | 8.3, 8.5 |
| F4 ekleri 9: kalibrasyon ölçümü | 8.1, 24.5 |
| F4 ekleri 9: gerçek okuyucuyla doğrulama okutması | 8.4, 8.7 |
| F4 ekleri 9: hızlı okutmada sıraya alma | 8.6 |
| F4 ekleri 9: PDF önizlemenin WebView2'de ve Pardus'taki Qt WebEngine'de görünmesi | 8.3, 24.5 |
| F4 ekleri 8: masaüstündeki dosya tabanlı WAL ve `busy_timeout` beklemesi ölçülmedi | 17.4 (gözlem) |
| F4 ekleri 11: doğrulama okutması görevli kipinde | 8.7 |
| F5 ekleri başlığı: tahta, gerçek okul ağı ve Windows'a özgü davranışlar | 12, 4, 2.3 |
| F5 ekleri 16: tahtadan erişim ve ekran klavyesiz gezinme | 12.5 |
| F5 ekleri 16: eski Chromium ve Firefox ESR görünümü | 12.5 |
| F5 ekleri 16: güvenlik duvarı denetimi yönetici olmayan masa hesabında | 12.2 |
| F5 ekleri 16: Windows'ta `SO_EXCLUSIVEADDRUSE` ile tüm arayüzde dinleme | 12.3 |
| F5 ekleri 16: `SetThreadExecutionState` | 12.10 |
| F5 ekleri 16: Linux'ta `systemd-inhibit` | 24.8 |
| F5 ekleri 16: pystray menü yenilemesi | 4.7 |
| F5 ekleri 16: UAC yardımcısı | 12.9 |
| F5 ekleri 16: kurulumun güvenlik duvarı görevi | 2.3, 12.8, 21.3, 22.1 |
| F5 ekleri 16: zamanlanmış görevin masa hesabına yazılması | 2.3, 4.6, 22.1 |
| F5 ekleri 18: gerçek okul ağı, tahta ve Windows paketiyle ikinci bilgisayar + yük provası | 12.4, 12.5, 12.11 |
| F5 ekleri 27: Pardus komutu kaynak sınırlı · karar (28.09.2026): Linux taşınabilir arşivde katalog açılamaz | 24.7 · 24.11 |
| F5 ekleri 28: uyku dahil açık kalma saati (Windows `GetTickCount64`, Linux `CLOCK_BOOTTIME`) | 17.3, 24.9 |
| F6 ekleri başlığı: gerçek okuyucuyla hızlı okutma | 10.3, 24.6 |
| F6 ekleri başlığı: katlanmış pusula | 10.6 |
| F7 ekleri başlığı: okuyucuyla toplu teslim | 11.1 |
| F7 ekleri başlığı: görevli kipinde geri alma okutması | 11.2 |
| F7 ekleri başlığı: F7 belgelerinin gerçek yazıcı çıktısı (E5, E6, E15) | 11.1-11.3, §16 |
| F8 ekleri başlığı: E7, E8, E9, E16'nın gerçek yazıcı çıktısı | 14.1-14.3, §16 |
| F9 ekleri başlığı: E10'un gerçek yazıcı çıktısı | 13.4, §16 |
| F9 ekleri başlığı: sayım gününün kendisi | 13.1-13.5, 15.5 |
| F10 ekleri başlığı: E11, E12, E17, E20 ve kişi dökümünün gerçek yazıcı çıktısı | 15.1-15.3, §16 |
| F11 ekleri E-6 ve KT-6: programın sayfası site adımıyla yayına girer (o güne dek 404) | 21.1 (kullanıcı kararı 1: site ayrı adım) |
| F11 ekleri B-1: dış yedek hatırlatması | 17.2 |
| F11 ekleri B-2, K-3, D-11: temiz makinede geri yükleme provası (okulun kendi denemesi) | 18.1-18.4 |
| F11 ekleri B-3: eski program yeni veriyi açmaz | 21.4 |
| F11 ekleri B-4: görev devri | 20.1-20.2 |
| F11 ekleri KB-2 (c): DEK döndürme — "F12 sonrasına", v1 dışı | kapsam dışı (protokolde adım yok; TB17) |
| §16 risk 1: tahta VLAN erişimi — saha kapısı F12'ye ertelenir | 12.5 |
| §16 risk 4: tepsi + pywebview uyumu (özellikle Qt) | 4.1, 24.3 |
| §16 risk 6: kalıntı kural ya da üçüncü parti güvenlik duvarı | 12.8 (ve `docs/kurulum.md` §8.2) |
| §16 risk 14: her güncelleme yönetici (BTR) ister | 21.3 |
| §16 risk 15: imzasız exe + dinleyen port | 2.1 |

### 26.3 `packaging/windows/NOTLAR.md` — doğrulanması gereken varsayımlar

| Madde | Protokol adımı |
|---|---|
| W1 MSYS2 `ntldd` paket adı | paket hattı (CI); sahada dolaylı: 2.5 (`--pdf-duman`) |
| W2 WeasyPrint DLL adları | 2.5 |
| W3 `WEASYPRINT_DLL_DIRECTORIES` | 2.5 |
| W4 fontconfig yolları ve önbelleği | 2.5 (PDF DejaVu ile) |
| W5 WebView2 Evergreen önyükleyicisi | 2.4, 23.2 |
| W6 Inno 6.3+ `x64compatible` | paket hattı; sahada 2.2 (kurulum açılıyor) |
| W7 `Turkish.isl` | 2.2 (kurulum penceresi Türkçe) |
| W8 yönetici kurulumu, kurulum dizinine yazılmaz | 2.2 |
| W9 pywebview `edgechromium` + pythonnet | 2.4, 3.1 |
| W10 "çalıştır" adımı masa hesabıyla | 2.2 |
| W11 kapatma olayı kurulumda ve kaldırmada | 21.3, 22.1 |
| W12 UAC'ye BTR kimliği girilince olay ve mutex'ler açılır | 21.3 |
| W13 pystray Çık sonrası süreç biter, simge görünür | 4.1, 4.3 |
| W14 oturum kapanışı engellenmez | 4.5 |
| W15 güvenlik duvarı denetimi yönetici olmayan hesapta; tüm arayüzde özel kullanım (TB12) | 12.2, 12.3 |
| W16 netsh kural denetimi, Türkçe yol, güncellemede kurala dokunulmaz, kaldırmada silinir, HKLM portu korunur | 2.3, 21.3, 22.1 |
| W17 otomatik başlatma görevi masa hesabında; kaldırmada silinir | 2.3, 4.6, 22.1 |
| W18 UAC yardımcısı | 12.9 |
| W19 uyku engeli | 12.10 |
| W20 pystray menü yenilemesi, görevli kipinde Çık | 4.7 |
| W21 lisans denetimi Windows derlemesinde (TOC, MSYS2 paket veritabanı) | paket hattı (CI); sahada 2.2 (lisans dizini kurulum klasöründe) |
| W22 pystray modüllerinin kaynak dosyadan yüklenmesi (Program Files salt okunur) | 2.5 (`--bagimlilik-duman`), 4.1 (tepsi çalışır) |
| W23 lisans sayfası UTF-8 metni Türkçe harfleri bozmadan gösterir; lisans dosyaları kurulur | 2.2 |
| W24 pip kısıt dosyası (lisans listesinin sürümleri) Windows'ta çözülür | paket hattı (CI); sahada dolaylı: 2.5 (`--bagimlilik-duman`) |
| W25 MSYS2 paketlerinin SPDX lisans denetimi ve DLL düzeyindeki izinler | paket hattı (CI); sahada 2.2 (lisans dizini) |
| W26 paketin statik DLL kapanışı; duman testleri Windows'un sistem PATH'iyle | paket hattı (CI); sahada dolaylı: 2.5 (`--pdf-duman`, `--bagimlilik-duman`) |

### 26.4 `packaging/windows/NOTLAR.md` — ilk Windows koşusu çek-listesi

| Madde | Protokol adımı |
|---|---|
| 1 `npm run build` | paket hattı (CI) |
| 2 `build.ps1` | paket hattı (CI) |
| 3 `pdf-duman.pdf` gözle | 2.5 |
| 4 yönetici olmayan hesapta kurulum, UAC, veri yeri | 2.2 |
| 5 WebView2'siz makinede çıkış kodu 7 | 23.2 |
| 6 taşınabilir zip USB'den, SmartScreen yok | 23.1 |
| 7 tepsi | 4.1, 4.3 |
| 8 ikinci açılış ve geri yükleme kısayolu | 4.2 |
| 9 kapatma olayı: kurulum ve kaldırmada, BTR kimliğiyle | 21.3, 22.1 |
| 10 temiz kapanış işareti | 4.3, 4.4 |
| 11 oturum kapanışı | 4.5 |
| 12 `--autotest` | 2.5 |
| 13 Defender/AV | 2.1 |
| 14 güvenlik duvarı: kural, beş madde, başka bilgisayardan sınama, devre dışı kural, güncelleme, kaldırma | 2.3, 12.2, 12.4, 12.8, 21.3, 22.1 |
| 15 otomatik başlatma | 2.3, 4.6 |
| 16 UAC yardımcısı (port) | 12.9 |
| 17 uyku ve tepsi (görevli kipinde Çık) | 12.10, 4.7 |

### 26.5 Tasarım §14.2 — saha hazırlık hattı (S1-S15)

| Madde | Kodla ilgisi | Protokol adımı |
|---|---|---|
| S1 ağ keşfi, Liderahenk yetkisi | Ağ Doktoru, yer imi politika dosyası | 1.1.3, 12.5, 12.6 |
| S2 PYS talebi | PYS talep metni | 1.1.3, 12.5 |
| S3 sabit adres ayırma (DHCP) | adres değişimi uyarısı | 1.1.3, 12.12 |
| S4 okuyucu ve etiket tabakası | etiket ve dolaşım | 1.1.2, 8.1-8.4, 9.3, 10.3 |
| S5 ilçe ve Bakanlığa sorular (Bakanlık sistemi, sınıflama) | "Bakanlık sistemi kullanımda" ayarı (varsayılan kapalı) | kod dışı; protokolde adım yok (ayar cevaba göre açılır) |
| S6 BTR bilgi notu | Ağ Hizmeti Bilgi Notu | 12.1 |
| S7 aydınlatma metni, görevlendirme | aydınlatma metni, masa kartı | 5.1, 5.2, 25.3 |
| S8 kitap sayısı, listeler (cevaplandı: hazır liste yok, 1.000-10.000) | Excel aktarımı ölçeği, önce etiket yolu | 7.1, 7.3, 7.6, 8.5 |
| S9 dönüşüm planı | önce etiket yolu, doğrulama okutması | 8.5, 25.5 |
| S10 masa hesabı, BitLocker | veri `%LOCALAPPDATA%`'da | 1.1.1, 2.2 |
| S11 parolanın iki kişide olması, anahtar zarfı | kurtarma anahtarı çıktısı ve doğrulaması | 3.2, 25.2 |
| S12 bilgisayarın demirbaş kaydı | sihirbazdaki demirbaş onayı | 3.3 |
| S13 UPS | temiz kapanış işareti, "Son Oturumu Kontrol Edin" | 4.4 |
| S14 Bakanlık kataloğu ucunun kullanım izni | künye getirme (varsayılan kapalı) | 7.7 |
| S15 künye kaynaklarına okul ağından erişim | künye getirme | 7.7 |

### 26.6 Teknik borç kütüğü (`docs/teknik-borc.md`)

| Kalem | Saha kısmı | Protokol adımı |
|---|---|---|
| TB2 NAT arkasındaki tahtalarda adres başına sınır | gözlem | 12.11 |
| TB3 `synchronous=FULL` maliyeti HDD'li Windows'ta | ölçüm | 17.4 |
| TB5 Pardus 21 desteği kararı | hangi Pardus sürümünde denendiği | 24.1 (kayıt çizelgesi 0.2) |
| TB6 imzasız exe | SmartScreen, SHA-256 | 1.3.2, 2.1 |
| TB12 tüm arayüzde özel kullanım (kalan saha kanıtı W15) | port paylaşımı denemesi | 12.3 |
| TB14 kapatma olayında dosyaların tutarlılığı | kurulum ve kaldırmada düzenli kapanış | 21.3, 22.1, 4.3 |
| TB27 PySide6 tavanı ve paket boyutu | kurulu boyut | 24.1 |
| TB28 üçüncü taraf lisans metinleri (kod tarafı kapandı — tasarım §14.1 F12 ekleri P-1…P-5; LGPL kaynağına yazılı teklif KB-1 (a), 28.09.2026; kararlı öncesi kalan: MSYS2 kaynak arşivleri, Qt bildirim metni — KT-5) | pakette ve `BENIOKU.txt`'de teklifle bulunması | 2.2, 24.1 |
| TB29 44'lü ve 40'lı tabakanın ölçüsü, gerçek basım | ölçüm | 8.1, 8.2 |
| TB30 UAC adımında yönetim isteğinin beklemesi | gözlem | 12.9 |
| TB36 büyük koleksiyonda E11 ve E17 PDF süresi | ölçüm | 15.2 |
| TB40 Pardus paketi açık programı kapatmaz (KB-4; kararlı öncesi iş yalnız sorun görülürse) | program açıkken yeniden kurma gözlemi | 24.12 |
| TB41 Windows'un taşınabilir sürümünde Ağ Kataloğu kesin kapıyla kapalı değil (DT-3; kararlı öncesi iş — KT-5 madde 5) | beta'da varsayılan kapalı olduğunun gözlemi; kararlı öncesi kesin kapının gerçek kurulum ve zip ile iki yönde sınanması | 23.1 |

### 26.7 CLAUDE.md §7 ve kullanıcı kararları (27.09.2026, 28.09.2026)

| Kaynak madde | Protokol adımı |
|---|---|
| F0 elle doğrulanacaklar: tepsi simgesi | 4.1 |
| F0 elle doğrulanacaklar: Çık | 4.3, 4.7 |
| F0 elle doğrulanacaklar: kurulumun açık programı kapatması | 21.3, 22.1 |
| F0 elle doğrulanacaklar: Pardus Qt tepsisi | 24.3 |
| F5 kullanıcı kararı (28.09.2026, KB-2): Pardus taşınabilir arşivinde Ağ Kataloğu açılamaz; düzeltme turu (29.09.2026): `.deb`'e geçişte `./kaldir.sh`, dağıtım duman testi | 24.11 (doğrulama), 24.2 (`--dagitim-duman kurulu`), 23.1 (Windows'ta varsayılan davranış; "Kuralı ekle/güncelle" ile açılması bilinen fark, KT-2) |
| F7: okuyucuyla toplu teslim, görevli kipinde geri alma, F7 belgelerinin yazıcı çıktısı | 11.1-11.3 |
| Karar 1: site ayrı adım | 1.3.1, 21.1 |
| Karar 2: saha kabulünü kullanıcı yapar; işaretlenebilir protokol ve uydurma deneme verisi | bu belge; 1.2 |
| Karar 3: beta etiketi, Release'te pre-release, kararlı kullanıcıya beta önerilmez | 1.3.1, 21.1 (kararlı sürüm yayımlandıktan sonra: kararlı sürüm kurulu bilgisayarda "Şimdi denetle" ön sürüm önermez) |
| KB-1 (28.09.2026): LGPL kaynağına yazılı teklif (beta) | 2.2, 24.1 |
| KB-3 (28.09.2026): beta'da Qt ve Chromium bildirimleri adresle (lisans dizinindeki Qt bildirim notu) | 24.1 |
| KB-4 (28.09.2026): beta için belge; kararlı öncesi iş sahadaki gözleme bağlı | 24.12 |

## 27. Bulgu kaydı

Her düşen adım için bir satır. Kişi adı, okul adı, IP adresi ve ekran görüntüsündeki gerçek
veri YAZILMAZ; günlük dosyasından alıntı yapmadan önce okuyun.

| Adım | Tarih | Ne görüldü (beklenenle fark) | Günlük / çıkış kodu | Önem (engelleyici / önemli / küçük) | İzleme (issue no) |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |

Protokolün sonucu: ☐ Kabul (engelleyici bulgu yok) ☐ Koşullu kabul (engelleyici yok, önemli
bulgular izleniyor) ☐ Ret (engelleyici bulgu var).
