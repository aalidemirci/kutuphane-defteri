# Kütüphane Defteri — Arayüz Sözlüğü ve Yazım Kuralları

*21.09.2026 · Tasarım §18. **Bağlayıcıdır.** Kullanıcıya görünen HER metin
(etiket, düğme, başlık, snackbar, hata, boş durum, kılavuz, evrak, ağ
kataloğu sayfaları) bu sözlüğe uyar. Kod tanımlayıcıları (İngilizce) ve kod
yorumları kapsam dışıdır.*

Hedef okur kütüphaneden sorumlu öğretmen ya da okul idarecisidir; yazılımcı
değildir. Masada ise öğrenci görevli oturur. Metin iki okura da onların
diliyle konuşur. Mevzuat terimleri mevzuattaki anlamıyla kullanılır, programın
iç kavramları (karar, faz, evrak kodları) yüzeye çıkmaz.

## 1. Kavram sözlüğü

| Kavram (kod) | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| Program kendisi | **Kütüphane Defteri**; konum: "okulun kütüphane işlerini yürüttüğü **yerel araç**" | "kütüphane otomasyon sistemi", "resmî sistem", "Bakanlık sistemi yerine" | "Otomasyon sistemi" Yönetmelikte Bakanlığın sistemidir (Md. 9/2, 16/2). Programa bu ad verilmez (tasarım §3) |
| Bakanlığın sistemi | **Bakanlık otomasyon sistemi**, kısa: "Bakanlık sistemi" | "e-Kütüphane", uydurma ürün adı | Resmî adı ve adresi doğrulanınca buraya yazılır |
| TMY çıktısı | **Taşınır Kütüphane Defteri dökümü** | tek başına "Kütüphane Defteri" | Programın adıyla karışmasın diye her zaman tam ad (U8) |
| `Work` | **eser** | kayıt, materyal, başlık (tek başına) | Künye bilgisi: başlık, yazar, yayınevi… Bir eserin birden çok nüshası olur |
| `Copy` | **nüsha** | kopya, demirbaş, materyal | Rafta duran fiziksel kitap. Masa iletilerinde gündelik "kitap" serbesttir: "Kitabın kütüphane etiketini okutun." |
| `Copy.barcode` | **barkod** (10 hane, basılı `2026-000123`) | etiket no, kod | Salt rakamdır |
| `Copy.accession_no` | **kayıt no** | demirbaş no, envanter no | Barkodun sayı hâlidir, tek sayaçtan gelir |
| `Copy.old_register_no` | **eski kayıt no** | eski barkod, defter sıra no | Kitaptaki eski damga ya da defter numarası; isteğe bağlı |
| `Copy.external_asset_ref` | **TKYS kodu** | demirbaş kodu, sicil (tek başına) | Taşınır kaydındaki karşılık |
| `SchoolConfig.demirbas_no` | **bilgisayarın demirbaş no'su** | — | "Demirbaş" yalnız bilgisayar için kullanılır (Yönerge 11/8) |
| Yer numarası (sırt etiketi satırları) | **yer numarası** | raf kodu, lokasyon, call number | Sınıflama / yazar kodu / cilt-nüsha |
| Sınıflama | **sınıflama kodu**; tahmini kod rozeti **"tahmini"**; ana sınıf: **"Dewey Onlu Sınıflama (DOS) ana sınıfı"** (ilk geçişte açık, sonra "DOS") | Dewey numarası, DDC, "Bakanlıkça belirlenen sınıflama" | Yönetmelik sistemi adlandırmıyor; DOS fiilî standarttır (tasarım §3) |
| `Section` | **bölüm** (kontrollü liste: ad, DOS aralığı, kısa tarif) | section, lokasyon, alan | Yönetmeliğin "alan"ı (Md. 4/1-a) ortaöğretimdeki konu bölümüdür; arayüzde "bölüm" denir. "Raf" yalnız fiziksel rafı anlatırken (etiket yapıştırma) |
| `is_reference` vb. | **danışma kaynağı**; durum **"Ödünç verilmez — kütüphanede okunur"** | referans, "ödünç dışı" | Tek türetim `is_loanable` (Md. 14/1-a, 16/1) |
| Nüsha durumları | **Rafta** · **Ödünçte** · **Ödünç verilmez — kütüphanede okunur** · **Geçici olarak kullanım dışı** · **Sınıf kitaplığında** · **Onarımda** · **Kayıp** | AVAILABLE gibi kodlar, "müsait" | Ağ kataloğu ve masa aynı sözcükleri kullanır |
| `Membership` | **üye**, **üyelik** | okuyucu, abone, kullanıcı (kişi anlamında) | Üyelik isteğe bağlıdır (Md. 17/1) |
| `member_kind` | **üye türü**: öğrenci / öğretmen / diğer personel | personel (öğretmen anlamında), çalışan | "Personel" yalnız e-Okul raporunun adında ("Personel Listesi"). Kişiler sekmesi: **"Öğretmenler ve Diğer Personel"** |
| Ayrılış (`left_at`, LEFT) | durum rozeti **"Ayrıldı · gg.aa.yyyy"**; eylem **"Ayrıldı olarak işaretle"** | pasif, pasifleştir, arşivle, mezun (genel ayrılış anlamında) | Hiç üye olmamış ve açık işlemi olmayan kişinin kaydı ayrılışta silinir; onay gövdesi bunu söyler |
| e-Okul mutabakatı | **"Bu dosya okulun tam listesidir"** (onay kutusu); **ayrılacak** (önizleme) / **ayrılan** (sonuç); personelde **"N kişi listede yok. Ayrıldı sayılsın mı?"** | silinecek, kaldırılacak | Varsayılan karşılaştırma yalnız dosyadaki şubelerledir |
| Personel birleştirme | **olası aynı kişi**; eylem **"Birleştir"** | mükerrer, duplicate, çift kayıt | Eski kaydın kütüphane bağları yeni kayda taşınır, eski kayıt silinir (ör. soyadı değişimi) |
| Kart | **üye kartı**, **kart no** (8 hane) | okuyucu kartı, kütüphane kartı, kimlik kartı | Evrakta madde atfı gerekirse konum kalıbı: "Md. 20'de öngörülen kullanıcı kartının okulca düzenlenen yerel karşılığıdır; Bakanlık otomasyon sistemindeki kaydın yerine geçmez." |
| `CardRevocation` | **"Kartı yenile"** (düğme); eski kart için **"iptal edilmiş kart"** | kartı sil, kart iptal kaydı | İleti: "İptal edilmiş kart — kütüphane yöneticisine yönlendirin" |
| `Loan` | **ödünç** (ad), **ödünç ver** (eylem), **iade al** / **iade** | emanet, check-out, teslim (ödünç anlamında), "kitap çıkışı" | "Teslim" başka bir işlemdir (aşağıda) |
| `Loan.cardless` | **kartsız ödünç** | kartsız işlem, istisna | Yalnız yönetici kipinde, gerekçeli |
| `Loan.override_reason` | **gerekçe** ("Gerekçeli istisna") | override, bypass | Yalnız gecikme engeline; yardım metni: "Sağlık ya da aile bilgisi yazmayın." |
| Ödünç geçmişi | **ödünç kaydı**, **ödünç geçmişi** | **okuduğu kitaplar**, okuma karnesi, okuma puanı, okuma geçmişi | **Ödünç ≠ okuduğu kitap.** Öğrenci bazlı ödünç sayısı öğretmene ya da e-Okul'a aktarılmaz (tasarım §3) |
| İade tarihi | **iade tarihi**; gecikmişte **gecikme**, **"… gün gecikti"** | son teslim tarihi, ceza, harç, uzatma | Programda uzatma, ceza ve harç yoktur. Kaydırılmış tarih "Md. 18 gereği" diye sunulmaz |
| `Holiday.SCHOOL_BREAK` | **öğrenciye kapalı gün** (ara tatil, yarıyıl) | tatil (tek başına) | Kanunen tatil değildir; resmî ve dini tatil ayrı türdür |
| `Holiday` diğer türler | **resmî tatil**, **dini bayram**, **idari izin / diğer**; hepsinin üst adı **kapalı gün** (sayfa: "Kapalı Günler") | tatil günü (genel anlamda) | İdari izin kütüphanenin de kapalı olduğu gündür; iade tarihi hesabında resmî tatil gibi her zaman kapalı sayılır. Bu programın kuralıdır, TBK 93 kıyası altında anılmaz (`docs/mevzuat/BENIOKU.md` §4). Tahmini bayram tarihinde **"tahmini"** rozeti |
| `Delivery` (U11) | **teslim**: "sınıf kitaplığına teslim", "öğretmene teslim"; geri dönüşü **geri alma** | ödünç, emanet, zimmet | **Teslim ödünç değildir**, Md. 18 sayı sınırı uygulanmaz |
| İlişik | **"Kütüphaneden ilişiği yoktur" belgesi**, **ilişik listesi** | borç, ilişik kesme | Karne ya da diplomanın ön koşulu diye SUNULMAZ; dayanağı yok |
| `LossDamageCase` | **kayıp**, **hasar**, **onarım**; belge "Kayıp/hasar tutanağı" | zayi, telef | Bedel seçenekleri yalnız ortaöğretimde (Md. 19). Program tahsilat yapmaz |
| `WeedingBatch` | **ayıklama** (Md. 12) | silme, temizleme, imha (genel anlamda) | Kütüphane kararıdır |
| TMY işlemi | **kayıttan düşme**; imha yalnız **"imha tutanağı"** (TMY 28/5) bağlamında; **devir** | silme | Ayıklama ≠ kayıttan düşme: biri komisyon kararı, öbürü taşınır işlemidir |
| `CommissionDecision` | **Seçim ve Ayıklama Komisyonu**, **komisyon kararı** | kurul (bu anlamda) | Yönetmelikteki adı aynen |
| `DonationIntake` | **bağış ön kaydı** | bağış listesi (tek başına), taslak | Komisyon kararına kadar nüsha açılmaz |
| `StockTake` | **sayım**; seçenekler **"TMY 32/3 durdurması"** ve **"sayım için hizmet arası"**; **sayım kurulu** | sayım kilidi, dondurma | İki seçenek ayrı adlarla ve tutanakta ayrı satırlarda geçer. **İade hiçbir durumda durmaz** |
| Ağ kataloğu | **Ağ Kataloğu** (özel ad, büyük harfle) | **OPAC**, web sitesi, sunucu, LAN, portal | Kişisel veri göstermez; bunu "Hakkında" sayfası söyler |
| Vitrin | **yeni gelenler**, **çok okunanlar** | popüler, en çok ödünç alınanlar | Çok okunanlarda sayı gösterilmez, yalnız sıra |
| Ağ Doktoru | **Ağ Doktoru** | ağ tanılama, diagnostik | Yalnız yönetici kipinde |
| BTR notu (E3) | belge adı **Ağ Hizmeti Bilgi Notu** | port izni, izin belgesi | "İzin" değil "bilgi" notudur (U10) |
| BTR | ilk geçişte **"bilişim teknolojileri rehber öğretmeni (BTR)"**, sonra "BTR" | BT sorumlusu, sistem yöneticisi | "Sistem yöneticisi" Yönergedeki (4/1-s) dar anlamıyla kalır, BTR için kullanılmaz |
| Kip (U5) | **görevli kipi**, **yönetici kipi**, **kilitli**; eylemler **"Görevli kipine geç"**, **"Kilitle"** | öğrenci modu, admin modu, kiosk, oturum | Görevli kipinden çıkış yönetici parolası ister |
| Görevli | **görevli** (masadaki öğrenci görevli ya da personel) | asistan, operatör | Md. 23/1-a "kütüphane görevlisi" |
| Sorumlu kişi | **kütüphane yöneticisi** (kütüphaneci ya da kütüphaneden sorumlu öğretmen) | admin, yetkili, sorumlu (tek başına) | Md. 20'nin terimi. Çoğu okulda kütüphaneci atanmaz (Md. 7/1) |
| Parola | **yönetici parolası**, **kurtarma anahtarı** | şifre, uygulama parolası, PIN | Parola zorunludur, sihirbazın ilk adımıdır |
| Görev devri | **görev devri**; belge **Görev devri notu** | devir teslim (tek başına) | "Devir" TMY'de başka anlama gelir |
| Masa hesabı | **kütüphane masası Windows hesabı** | kiosk hesabı, ortak hesap | Yönetici yetkisi olmayan ayrı hesap (U9) |
| Yedek | **yedek**, **şifreli yedek**; "güçlü şifrelemeyle korunur" | X25519, AES, `.kdbak` (kullanıcı metninde) | Teknik adlar yalnız Hakkında sayfasında |
| Sürüm | **"yayımlanan son sürüm"**, **"kurulum dosyası"** | GitHub sürümü, Release, kurucu | Güncelleme denetimi yalnız düğmeyle yapılır |

## 2. İç kodlar yüzeye çıkmaz

Tasarımın karar, faz ve bulgu kodları kullanıcı metninde, hata mesajında ve
evrakta GEÇMEZ: `U1`-`U12`, `T1`-`T17`, `A1`-`A23`, `F0`-`F12`, `S1`-`S13`,
`D1`-`D21`, `E1`-`E20`, `GA-`, `KM-`, `UY-`, `SU-`, `EK-`, `AT-`, `V2-`. İç
kimlikler (`id=…`, `pk`) de geçmez. Evrak kodunun yerine belgenin adı yazılır:

| Kod | Ad |
|---|---|
| E1 | Sırt etiketi · Barkod etiketi · Kalibrasyon sayfası |
| E2 | Üye kartı |
| E3 | Katalog afişi · Ağ Hizmeti Bilgi Notu · PYS talep metni · Yer imi dosyaları |
| E4 | İade hatırlatma pusulası · Gecikmiş ödünç listesi |
| E5 | "Kütüphaneden ilişiği yoktur" belgesi · İlişik listesi |
| E6 | Kayıp/hasar tutanağı |
| E7 | Ayıklama belgeleri |
| E8 | El yazması ve nadir eserler listesi |
| E9 | Yıl sonu kütüphane raporu |
| E10 | Sayım tutanağı |
| E11 | Taşınır Kütüphane Defteri dökümü · Yönetim hesabı cetveli hazırlığı |
| E12 | Ayın Kitapları afişi |
| E13 | Kütüphane aydınlatma metni |
| E14 | Kurtarma anahtarı çıktısı |
| E15 | Teslim listesi · Geri alma dökümü |
| E16 | Bağış ön kayıt listesi |
| E17 | Alfabetik katalog dökümü |
| E18 | Görev devri notu |
| E19 | Masa kartı |
| E20 | Okuma ödülü iç çıktısı |

Açıklanmamış kısaltma kullanılmaz: "KD" hiç yazılmaz; DOS, BTR ve TKYS ilk
geçişte açılır ("Taşınır Kayıt ve Yönetim Sistemi (TKYS)"). Kod yorumlarında ve
testlerde kodlar serbesttir.

## 3. Yazım kuralları

- **Düğmeler cümle düzenindedir:** "Ödünç ver", "İade al", "Kartı yenile",
  "Görevli kipine geç". Sayfa, sekme ve bölüm **başlıkları** Başlık
  Düzenindedir: "Dolaşım Masası".
- **Devam düğmesi** tek biçim: "Kaydet ve devam et" (kayıt yoksa "Devam").
  Vazgeçme: "Vazgeç"; salt bilgi diyaloğunda "Kapat".
- **Seçici yer tutucusu** tek biçim: "Seçin". Boş seçenek: "— yok —".
- **Tırnak:** JSX metninde “ ” (kıvrık). Kesme işareti düz `'`.
- **"resmî"** düzeltme işaretiyle yazılır ("resmi" değil).
- **Simgeler** `Icon` bileşeniyle verilir; metne ham "✓" / "⚠" yazılmaz.
- **Tarih/saat** yalnız `lib/format.ts` yardımcılarıyla (`formatDate`
  gg.aa.yyyy, `formatDateTime`); `toLocaleString`/`toISOString` ile yerel
  kopya yazılmaz.
- **Büyük harf:** evrakta `text-transform: uppercase` yok; büyük harfli metin
  doğrudan büyük yazılır ya da `tr_upper` ile üretilir ("İ", "I" ayrımı).
- **Snackbar** tam cümledir ve noktayla biter ("Ödünç verildi.", "İade
  alındı.").
- **Geri dönüşü olmayan ya da damga düşüren her işlem** onay diyaloğundan
  geçer; başlık soru, gövde sonuçtur (ikisi aynı cümle olmaz).
- **İndirilen dosya adı** belge adı + tarih taşır (`lib/download.ts`).

## 4. Sayfa ve gezinme adları

Ekranlar fazlarla geldikçe buraya işlenir. Kural: gezinme etiketi kısa, sayfa
başlığı (h1) tam addır ve üst çubuktaki başlıkla AYNIDIR. Gezinme kartının
(Genel Bakış) başlığı gittiği sayfanın h1'idir. Sekme adları Başlık
Düzenindedir; sekme adreste `?tab=` ile tutulur, böylece başka ekranlar ve
kılavuz doğrudan sekmeye bağlanır. Kılavuzda ekran, sekme ve düğme adları
buradaki ve ekrandaki metinle birebir yazılır ("Ayarlar → Güvenlik").

*Aşağıdaki tablolar F1 sonundaki durumdur (22.09.2026); kaynak `AppShell.tsx`
(`NAV_ITEMS`, `PAGE_TITLES`), sayfaların h1'leri ve sekme tanımlarıdır.*

### 4.1 Sayfalar

| Gezinme etiketi | Sayfa başlığı (h1 = üst çubuk) | Adres | Not |
|---|---|---|---|
| Genel Bakış | Genel Bakış | `/` | Ana sayfanın tek adı |
| Kişiler | Kişiler | `/kisiler` | |
| Ayarlar | Ayarlar | `/ayarlar` | |
| Kılavuz | Kullanım Kılavuzu | `/kilavuz` | |
| Hakkında ve Lisans | Hakkında ve Lisans | `/hakkinda` | Kenar çubuğunun altında, ana gezinmenin dışında |
| — | Kurulum Sihirbazı | `/kurulum` | Menüde yoktur. İlk açılışta kurulum kapısı buraya getirir; kurulumdan sonra Ayarlar'ın altındaki "Diğer ayarlar" bölümünde **Kurulum Sihirbazı** kartıyla açılır |

Ana gezinmenin sırası: Genel Bakış · Kişiler · Ayarlar · Kılavuz. Görevli
kipinde gezinme bağlantıları gösterilmez; her adreste görevli ekranı durur.

### 4.2 Program durumu ekranları

Bunlar adres değildir; program durumuna göre sayfanın yerine gelir.

| Durum | Başlık |
|---|---|
| Kilitli | **Kayıtlar kilitli** |
| Görevli kipi | **Görevli Kipi** (üst çubukta da bu ad yazar) |
| Güvenlik dosyası yok ya da bozuk | **Güvenlik dosyası bulunamadı ya da okunamıyor** |
| Yedekten geri yüklendi | **Programı kapatıp yeniden açın** |

Üst çubuktaki kip göstergesinin adları: kip adı **Yönetici kipi** / **Görevli
kipi**; düğmeler **Görevli kipine geç** (kısayol Ctrl+Shift+G), **Yönetici
kipine geç**, **Kilitle**.

### 4.3 Sekmeler

İlk sekme varsayılandır.

| Sayfa | Sekmeler, sırasıyla (`?tab=` değeri) |
|---|---|
| Kişiler | **Öğrenciler** (`ogrenciler`) · **Öğretmenler ve Diğer Personel** (`personel`) |
| Ayarlar | **Ders Yılları** (`ders-yillari`) · **Kapalı Günler** (`kapali-gunler`) · **Şubeler** (`subeler`) · **Okul Bilgileri** (`okul`) · **Güvenlik** (`guvenlik`) · **Güncelleme** (`guncelleme`) |

### 4.4 Kurulum Sihirbazı adımları

Adım rayındaki adlar, sırasıyla: **Yönetici parolası** · **Okul bilgileri** ·
**Ders yılı ve kapalı günler**. İlk adım atlanamaz. Adımlar arası düğmeler:
**Geri**, **Devam** (1. adım), **Kaydet ve devam et** (2. adım), **Kurulumu
tamamla** (son adım).

### 4.5 Genel Bakış kartları

**Başlangıç Yol Haritası** (kurulumdan sonra; bütün maddeler bitince
gizlenebilir) · **Kişiler** · **Ayarlar** · **Katalog Excel Şablonu** (bir
sayfaya gitmez, şablonu indirir).

## 5. Kişisel veri ve metin

- **Görevli kipindeki iletilerde okuma bilgisi yoktur.** Gecikmesi olan üyede
  eser adı ve gecikme günü gösterilmez: "Ödünç verilemiyor — kütüphane
  yöneticisine yönlendirin." Kişisel olmayan sebepler yazılabilir: "sınır
  dolu", "bu kaynak ödünç verilmez".
- Kartla üye çözümlemesinde görevli yalnız **ad** ve **kalan ödünç hakkını**
  görür; sınıf yazılmaz.
- Hata ve uyarı metnine, günlüğe ve uç yoluna öğrenci adı yazılmaz.
- Basılı toplu gecikme listesi şu dipnotu taşır: "Kişisel veri içerir —
  asılmaz, çoğaltılmaz."
- Ağ kataloğunun hiçbir sayfasında üye, ödünç, iade tarihi ya da kişi adı
  geçmez. "Hakkında" sayfası bunu açıkça söyler.
