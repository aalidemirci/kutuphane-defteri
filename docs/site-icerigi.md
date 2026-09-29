# Kütüphane Defteri — site içeriği (okulapp.org için hazırlık)

Bu belge okulapp.org'daki program sayfasının **metin içeriğidir**; sitenin kendisi değildir.
27.09.2026 kullanıcı kararıyla site işi AYRI bir adımdır: okulapp.org deposunda bir dal ve
PR açılır, kullanıcı birleştirir. Bu depo okulapp.org'a dokunmaz; site adımı metinleri
buradan alır.

## 0. Site adımı için kurallar

- **Ortak yayın alanı:** `../okulapp.org/CLAUDE.md` → "Ortak çalışma düzeni" bağlayıcıdır.
  Bu programın alanı: `src/data/kd-release.json`, `src/pages/kutuphane-defteri/**`,
  `src/layouts/KDLayout.astro`, `public/kutuphane-defteri.png`. İşe `git fetch` ve güncel
  `origin/main` ile başlanır; canlıya yalnız `main` push'u gider (Workers Builds "Version
  command" `npx wrangler versions upload` kalır, `deploy` yapılmaz). Commit başlığı
  "Kütüphane Defteri: …". İlk eklemenin ortak dosyaları (palet tipi, `global.css` palet
  blokları, sitenin alan tablosu) tasarım §17'dedir.
- **Sayfalar** (tasarım §17): `kutuphane-defteri/index` (tanıtım, özellikler, indirme),
  `kutuphane-defteri/kilavuz` (kurulum ve ilk adımlar), `kutuphane-defteri/gizlilik`.
- **Metin kuralları** (bu belgedeki bütün metinler bunlara uyar):
  - **Unvan ve kurum adı yazılmaz**; programı yazandan söz etmek gerekirse "bir ortaöğretim
    kurumunda çalışıyor" düzeyinde kalınır. Geliştiricinin **adı ve e-postası** kardeş
    programların sayfalarındaki gibi kullanılabilir (29.09.2026 kullanıcı kararı; 27.09'daki
    "kişi adı yazılmaz" kuralı bu kararla değişti): iletişim e-posta düğmesiyle verilir, adı ve
    iletişim bilgileri sitenin Hakkımda sayfasındadır (§6 "Soru, öneri ya da hata nereye
    bildirilir?"). Öğrenci, veli ya da personel adı ve okulun adı hiçbir metinde yer almaz.
    Site alt bilgisi olduğu gibi kalır.
  - Okul ağının gerçek IP blokları, adresleri ve sunucu adları yazılmaz.
  - Konum dili: program "okulun kütüphane işlerini yürüttüğü **yerel araç**"tır. Bakanlık
    otomasyon sisteminin yerine geçtiği, onunla eşitlendiği ya da ona veri gönderdiği
    söylenmez (öyle bir iddia yoktur).
  - "Otomasyon sistemi" programın adı olarak kullanılmaz; "OPAC" yerine **Ağ Kataloğu**;
    "kurucu" yerine **kurulum dosyası** (`docs/sozluk.md`).
  - İç kodlar (faz, karar ve belge kodları) yazılmaz.
  - Ekran görüntüleri yalnız uydurma veriyle alınır (§8).

## 1. Kısa tanıtım

**Tek cümle (başlık altı):**

> Kütüphane Defteri, okulun kütüphane işlerini yürüttüğü çevrimdışı, yerel bir masaüstü aracıdır.

**Tanıtım paragrafı:**

> Katalog ve etiketten ödünç masasına, sınıf kitaplığına teslimden sayım ve ayıklamaya kadar
> okul kütüphanesinin günlük işleri tek bilgisayarda yürür. Program internete bağlı kalmadan
> çalışır; veriler okulun kendi bilgisayarında, şifreli durur. Kurallar Okul Kütüphaneleri
> Yönetmeliği'ne göre yazılmıştır: on beş günlük ödünç süresi, öğrenciye üç, öğretmene beş
> kitap sınırı, ödünç verilmeyen kaynaklar. İstenirse okul ağındaki bilgisayarlar ve
> etkileşimli tahtalar kataloğu tarayıcıyla, salt okur olarak tarayabilir.

**Platformlar:** Windows 10 ve 11 (64 bit) · Pardus 21 ve 23 (ve dayandıkları Debian 11 ve 12).

## 2. Özellikler

- **Katalog:** Excel şablonuyla toplu aktarım (önizleme kaydı yazmadan sonucu gösterir, aynı
  dosya iki kez uygulanamaz); hazır liste yoksa önce barkod etiketini yapıştırıp kitabı elde
  okutarak kayıt; Türkçe harflere duyarlı arama; kaynak adına, yazara ve konuya göre Türkçe
  sıralama; ISBN denetimi; isteğe bağlı ISBN ile künye getirme (varsayılan kapalı).
- **Etiketler:** sırt ve barkod etiketi, boş barkod etiketi; yazıcıya göre kalibrasyon;
  basım kaydı geri alınabilir; yapıştırılan etiketin okutularak doğrulanması.
- **Dolaşım masası:** üye kartı ve barkod okuyucuyla ödünç ve iade; öğrenci görevliler için
  yalnız masa işlerini açan **görevli kipi**; iade hatırlatma pusulası; beklenmedik
  kapanıştan sonra son işlemleri gözden geçirme.
- **Sınıf kitaplığı ve öğretmene teslim:** toplu teslim, okutarak geri alma, teslim listesi.
- **Kayıp, hasar ve ilişik:** kayıp/hasar tutanağı, "Kütüphaneden ilişiği yoktur" belgesi, yıl
  sonu ve yıl başı adımları.
- **Sayım, komisyon ve ayıklama:** sayım tutanağı ve Taşınır Mal Yönetmeliği'ne hazırlık
  dökümleri, ayıklama belgeleri, nadir eserler listesi, bağış değerlendirmesi, yıl sonu
  kütüphane raporu. Resmî taşınır kayıtları Taşınır Kayıt ve Yönetim Sistemi'nde (TKYS) kalır;
  program onların yerine geçmez, hazırlık çıktısı verir.
- **Raporlar:** kişisiz istatistik, çok okunanlar (sayı göstermeden), alfabetik katalog
  dökümü; verinin açık, belgelenmiş biçimde dışa aktarımı.
- **Ağ Kataloğu:** okul ağındaki bilgisayarlar ve etkileşimli tahtalar için salt okur katalog
  sayfaları; tahtalar için büyük dokunma düzeni; varsayılan olarak kapalı.
- **Güvenlik ve yedek:** zorunlu yönetici parolası ve kurtarma anahtarı; kişi adları, okul
  numaraları ve kart numaraları şifreli; her gün şifreli otomatik yedek; USB belleğe yedek
  hatırlatması; yedekten başka bilgisayara geri yükleme; görev devri.

## 3. Gizlilik özeti (gizlilik sayfası)

**Veri okulda kalır.** Program okulun bilgisayarındaki tek bir yerel veritabanıyla çalışır.
Bulut, hesap ve telemetri yoktur; program açılışta internete çıkmaz.

**Toplanmayan veriler.** T.C. kimlik numarası, veli bilgisi, cinsiyet, personelin unvanı ve
branşı programa alınmaz. e-Okul listesindeki bu sütunlar okunmaz.

**Şifreleme.** Kişi adları, okul numaraları, kart numaraları ve kişiyle ilgili açıklamalar
yönetici parolasına bağlı bir anahtarla şifrelenir; yedekler de şifrelidir. Eser adları,
şube ve ödünç tarihleri aramada ve sayımda kullanıldığı için şifrelenmez; bilgisayarın
diskinin şifrelenmesi (BitLocker) önerilir.

**Masadaki öğrenci görevli.** Görevli kipinde yalnız masa işleri açıktır: üyenin adı ve kalan
ödünç hakkı görünür, gecikme gerekçesi ve kişi listeleri görünmez. Yönetici işleri parolayla
açılır.

**Okuma ödülü.** Ödünç kayıtlarından adlı bir sıralama yalnız bir yerde çıkar: okul isterse,
yalnız yönetici kipinde bir **okuma ödülü aday listesi** (programdaki adıyla okuma ödülü iç
çıktısı) basılabilir. Amacı, Okul Kütüphaneleri Yönetmeliği Uygulama Kılavuzu'nun 7.
bölümündeki okuma ödülü önerisi için adayların belirlenmesidir; öneri bağlayıcı değildir,
ödül verilip verilmeyeceğine okul karar verir. Hukuki sebebi programdaki öbür kütüphane
kayıtlarınınkiyle aynıdır: 6698 sayılı Kanun md. 5/2-ç ("Veri sorumlusunun hukuki
yükümlülüğünü yerine getirebilmesi için zorunlu olması"); yükümlülük burada Okul
Kütüphaneleri Yönetmeliği md. 8/1-c'deki okuma kültürünü oluşturmaya yönelik
etkinliklerden doğar. Liste yalnız öğrencileri, seçilen dönemde ödünç alıp iade ettikleri
farklı eserlerin sayısına göre sıralar ve yalnız sırayı, adı soyadı ve sınıfı/şubeyi basar;
ödünç ya da eser sayısı, okul numarası ve kitap adları basılmaz. Çıktı "İç kullanım"
ibarelidir ve okul içinde ödül kararı için kullanılır: asılmaz, çoğaltılmaz; Ağ Kataloğuna,
panoya, yıl sonu raporuna ve velilerle paylaşılan çıktılara girmez. Kütüphane aydınlatma
metni bunu da yazar.

*Site adımı notu (sayfaya yazılmaz):* gizlilik sayfasının `#okuma-odulu` paragrafı yukarıdaki
metnin son cümlesi dışında aynısıdır (29.09.2026; aydınlatma metni sayfada kendi bölümünde
anlatılır). Hukuki sebep ve yöntem kullanıcı kararıyla onaylıdır (tasarım
§14.1 F12 ekleri İA-3); metin değişirse aydınlatma metni, bu paragraf ve gizlilik sayfası
birlikte değişir.

**İnternete giden istekler.** Yalnız kullanıcının başlattığı iki durumda:

1. "Şimdi denetle" düğmesiyle yayımlanan son sürümün sorulması (programın GitHub sayfasına);
   istek kişisel veri taşımaz.
2. Varsayılan olarak kapalı olan "ISBN ile künye getirme" açılırsa ve kullanıcı bir kitap
   için isterse: dışarı yalnız kitabın ISBN numarası gider.

**Ağ Kataloğu neyi gösterir, neyi göstermez.** Varsayılan olarak kapalıdır; okulun kararıyla
ve okulun bilişim teknolojileri rehber öğretmeninin (BTR) bilgisiyle açılır.

| Gösterir | Göstermez |
|---|---|
| Kaynak adı, yazar, yayınevi, yıl, konu, ISBN | Üye listesi, üye adı, sınıfı, kart numarası |
| Yer numarası ve bölüm | Kimin ödünç aldığı, iade tarihi, ödünç geçmişi |
| Nüsha özeti ("3 nüsha · 2 rafta · 1 ödünçte") | Kayıp ve hasar kayıtları, bedeller, bağışçı |
| Yeni gelenler, çok okunanlar (sayı göstermeden) | Yönetim ekranları, yedek, dışa aktarım |

Dürüst sınırlar: Ağ Kataloğu yalnız okul ağında, düz HTTP ile çalışır (kişisel veri
taşımadığı için şifreli bağlantı kullanılmaz). Arama terimleri ve ziyaretçilerin adresleri
kaydedilmez; erişim günlüğü tutulmaz, yalnız kişisiz günlük sayılar bellekte durur. Katalog
kişisel veri tablolarına hiç erişemeyen, salt okur bir bağlantıyla çalışır ve internete
çıkmaz.

**Saklama ve silme.** Süresi dolan kişisel veriler her gün taranır ama program kişi
kayıtlarını kendiliğinden silmez: silme ve kişiyle bağın koparılması kütüphane yöneticisinin
onayıyla yapılır; süreler okulun ayarıdır. Bu bilgisayardaki günlük şifreli yedekler 14 gün
sonra, güncelleme öncesi yedekler son beş güncellemeden eskiyse kendiliğinden silinir. USB
belleğe alınan yedeklerin düzeni okulun sorumluluğundadır.

**Veri sorumlusu okuldur.** Program, okulun duyurması için bir kütüphane aydınlatma metni
basar; metin e-Okul listeleri aktarılmadan önce duyurulur.

## 4. Kurulum ve ilk adımlar (kılavuz sayfası)

Kısa metin; ayrıntı programın içindeki **Kullanım Kılavuzu**'nda ve depodaki
`docs/kurulum.md`'dedir.

1. **Hazırlık:** kütüphane için yönetici yetkisi olmayan ayrı bir Windows hesabı; bilgisayar
   okul demirbaşı olmalı; disk şifrelemesi önerilir.
2. **Kurulum (Windows):** kurulum dosyası kütüphane masası hesabında başlatılır; Windows'un
   yönetici onayına okulun bilişim teknolojileri rehber öğretmeni (BTR) kimliğini girer.
   Kurulum, Ağ Kataloğu için güvenlik duvarı kuralını ve oturum açılınca başlatmayı
   seçenek olarak sunar. Pardus'ta `.deb` paketi `apt` ile kurulur.
3. **İlk açılış:** yönetici parolası ve kurtarma anahtarı (anahtar saklanıp doğrulanmadan
   kurulum tamamlanmaz), okul bilgileri, ders yılı ve kapalı günler.
4. **Kişiler:** e-Okul'un öğrenci ve personel Excel raporları değiştirilmeden yüklenir;
   önizleme hiçbir şey yazmadan sonucu gösterir. Aktarım kimseyi silmez: listede
   bulunmayanlar kararınızı bekler.
5. **Katalog:** Excel şablonuyla ya da önce etiket yoluyla (etiketi yapıştır, kitabı okut).
6. **Masa:** üye kartları basılır, ödünç ve iade barkod okuyucuyla yapılır.
7. **Yedek:** program her gün yedek alır; ayda bir şifreli yedeği USB belleğe alın.
8. **Ağ Kataloğu (isteğe bağlı):** okulun BTR'siyle birlikte açılır; program BTR ve müdürün
   imzalayacağı bir Ağ Hizmeti Bilgi Notu basar.

## 5. İndirme ve doğrulama (indirme bölümü)

| Dosya | Kimin için |
|---|---|
| `kutuphane-defteri-<sürüm>-win64-setup.exe` | Windows 10/11 — önerilen kurulum (yönetici onayı ister) |
| `kutuphane-defteri-<sürüm>-win64-portable.zip` | Windows — kurulumsuz; Ağ Kataloğu sunulmaz, otomatik başlatma yok |
| `kutuphane-defteri_<sürüm>_amd64.deb` | Pardus ve Debian tabanlılar — önerilen |
| `kutuphane-defteri-<sürüm>-linux-x64.tar.gz` | Linux — kurulum için sistem yöneticisi (sudo) yetkisi gerekmez; Ağ Kataloğu yok (sonradan `.deb` kurulacaksa önce arşivdeki `./kaldir.sh`) |
| `SHA256SUMS-<sürüm>.txt` | İndirilen dosyayı doğrulamak için |

**Açık kaynak bileşenlerin kaynağı** (paket bağlantılarının hemen altında durur; program
ağdan dağıtıldığı için LGPL bileşenlerinin kaynağına yönlendirme indirmenin yanında
verilir): "Programla gelen LGPL lisanslı bileşenlerin kaynak adresleri ve kaynak kodu için
yazılı teklif her paketteki `THIRD_PARTY_LICENSES/BENIOKU.txt` dosyasındadır. Linux
paketindeki Qt ve PySide6'nın kaynak arşivleri download.qt.io'dadır." (Sürüm numarası
`kd-release.json`'daki sürümün lisans listesinden alınır; bugün Qt ve PySide6 6.8.3.)

Dosyalar `indir.okulapp.org/kutuphane-defteri/` altından iner; aynı dosyalar GitHub
Releases sayfasında da bulunur. Paketler imzasızdır: Windows "tanınmayan uygulama" uyarısı
verebilir ("Ek bilgi" → "Yine de çalıştır"). Kurmadan önce dosyanın SHA-256 özetini
`SHA256SUMS-<sürüm>.txt` dosyasındaki satırla karşılaştırın (Windows: `Get-FileHash <dosya>
-Algorithm SHA256`; Linux: `sha256sum -c SHA256SUMS-<sürüm>.txt --ignore-missing` — indirmediğiniz
paketlerin satırları atlanır; GitHub'dan indirilen özet dosyasının adı `SHA256SUMS.txt`'dir).

**Sürüm durumu metni (ön sürüm dönemi):**

> İlk sürüm bir ön sürümdür (beta). Gerçek okul verisiyle kullanmadan önce okulda bir deneme
> kurulumu yapmanızı ve şifreli yedek almanızı öneririz. Güncelleme, programın Ayarlar →
> Güncelleme ekranındaki "Şimdi denetle" düğmesiyle denetlenir; okul ağında GitHub'a
> erişim yoksa yeni sürüm bu sayfadan elle indirilir.

**`src/data/kd-release.json` için gereken bilgiler** (değerler her yayında sürümden alınır;
biçim sitenin kendi dosyasındaki gibidir): sürüm (ör. `2026.10.0-beta.1`), yayım tarihi
(gg.aa.yyyy), ön sürüm mü, her dosyanın adı ve boyutu, SHA256SUMS dosyasının adı. Beta
sürümde `.deb` dosyasının adında `~` yerine `.` bulunur (`kutuphane-defteri_2026.10.0.beta.1_amd64.deb`).

## 6. Sık sorulanlar

**Bakanlık otomasyon sisteminin yerine mi geçer?**
Hayır. Kütüphane Defteri okulun kütüphane işlerini yürüttüğü yerel bir araçtır; Bakanlık
otomasyon sistemine bağlanmaz ve ona veri göndermez. Kataloğunu açık, belgelenmiş bir
biçimde dışa aktarabilir.

**İnternet gerekir mi?**
Hayır. Program çevrimdışı çalışır. İnternet yalnız güncellemeyi denetlemek ve (açıksa) ISBN
ile künye getirmek için kullanılır; ikisini de kullanıcı başlatır.

**Öğrenci verisi nereye gider?**
Hiçbir yere. Veriler okulun bilgisayarındadır; yedekler şifrelidir; program dışarıya kişisel
veri göndermez.

**Ağ Kataloğunu açmak zorunlu mu?**
Hayır. Varsayılan olarak kapalıdır; program onsuz tam çalışır.

**Hangi donanım gerekir?**
Programın çalıştığı bir Windows 10/11 ya da Pardus bilgisayar. Ödünç masası için USB barkod
okuyucu (2D önerilir) ve etiket basımı için lazer yazıcı ile etiket tabakası (varsayılan
38,1 × 21,2 mm 65'li) önerilir.

**Ücretli mi?**
Program PolyForm Noncommercial lisansıyla dağıtılır: ticari olmayan kullanım serbesttir;
ticari satış, ücretli dağıtım ya da barındırılan hizmet olarak sunum için ayrı yazılı izin
gerekir. Pakete giren üçüncü taraf bileşenlerin lisans metinleri paketle birlikte gelir;
LGPL lisanslı bileşenlerin kaynak kodu için yazılı teklif de oradadır (`BENIOKU.txt`; istek
yolu programın GitHub deposundaki Issues sayfası ya da geliştiricinin e-posta adresi).

**Bilgisayar değişirse?**
Eski bilgisayardan şifreli yedek alınır, yeni bilgisayara program kurulur ve yedek geri
yüklenir; adımlar kılavuzda bir kontrol listesi olarak yazılıdır.

**Soru, öneri ya da hata nereye bildirilir?**
Teknik destek, öneri ve hata bildirimleri için e-posta gönderebilirsiniz
(`mailto:aalidemirci@gmail.com?subject=Kütüphane Defteri hakkında` — kardeş programların
sayfalarındaki "E-posta gönder" düğmesiyle aynı biçim) ya da programın GitHub deposunda
Issues kaydı açabilirsiniz. İletiye ve kayda öğrenci, veli ya da personel verisi, okulun adı,
gerçek veri içeren ekran görüntüsü, yedek ya da veritabanı dosyası eklemeyin; Issues
kayıtları herkese açıktır. Programdaki kişisel verilere ilişkin başvurular okul müdürlüğüne
yapılır.

## 7. Proje görseli

`public/kutuphane-defteri.png` programın logosundan türetilir. Logo 29.09.2026 kullanıcı
kararıyla kesinleşti: "Raf ve etiket" — lacivert karo, safran raf üzerinde kitap sırtları,
barkodlu safran sırt etiketi, yaslanan kitap (tasarım §14.1 F12 ekleri L-1; teknik borç TB4
kapandı). Kaynak dosya `packaging/ikonlar/kutuphane-defteri-logo.png`'dir (1024×1024, saydam
kenar boşluğu 32 px); logo yeniden çizilmez ya da renkleri değiştirilmez.

Site görseli bu kaynaktan **ikon üreticisiyle** türetilir, taslak dosyasından ya da elle
kırpılarak değil. Ölçüsü kardeş Kelebek Sınav'ın görseliyle aynıdır: 256×256 RGBA, 15 px
saydam pay (görünür kutu 15..241); karo saydam paydan kırpılır, 226 px'e LANCZOS ile
küçültülür ve 15 px payla ortalanır. Hazır `-256.png` kesimi bu ölçüde DEĞİLDİR (8 px pay,
program simgesinin kuralı). Komut (Docker'da; betik varsayılan koşusunda siteye yazmaz):

    docker compose run --rm -w /repo -v "<okulapp.org>/public:/site" backend \
        python packaging/ikonlar/ikon_uret.py --site /site/kutuphane-defteri.png

Ölçüyü `packaging/tests/test_ikonlar.py` sınar. Logo değişirse site görseli bu komutla
yeniden üretilir.

## 8. Ekran görüntüleri

Yalnız uydurma veriyle alınır: `scripts/deneme_verisi.py` ile üretilen deneme verisi ve okul
adı "Örnek Anadolu Lisesi" (`docs/saha-kabulu.md` §1.2). Önerilen kareler: Genel Bakış ·
Katalog (Türkçe arama) · Dolaşım Masası (görevli kipi) · Etiketler (basım kuyruğu) · Ağ
Kataloğu sayfası (tahta kipi) · Sayım. Adres çubuğunda okul ağının gerçek adresi görünmez
(görüntü `127.0.0.1` ile alınır ya da adres örtülür); kişi adı, okul adı, IP ve bilgisayar
adı taşıyan hiçbir kare yayımlanmaz.
