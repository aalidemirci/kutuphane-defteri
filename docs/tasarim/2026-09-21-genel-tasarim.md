# Kütüphane Defteri — Genel Tasarım ve Geliştirme Planı

*Tarih: 21.09.2026 · Durum: **TASLAK v2**. Denetimden geçti: 124 bulgu, işlenişi
§19'da. Kararlar: on iki kullanıcı kararı alındı (§2.1). Kalan kararlar varsayılanla
ilerler (§15). Kanıt dayanağı:
[keşif raporları](../kesif/2026-09-21-kesif-raporlari.md) (R1-R9) ·
[tasarım denetimi](../kesif/2026-09-21-tasarim-denetimi.md) (GA/KM/UY/SU/EK
bulguları)*

---

## 1. Altmış saniyede proje

Kütüphane Defteri, bir okul kütüphanesinin işlerini yürüten çevrimdışı bir masaüstü
programıdır (Windows 10/11 + Pardus). Kapsadığı işler:

- katalog ve etiket;
- üyelik, ödünç ve iade, sınıf kitaplığına teslim;
- sayım;
- komisyon ve ayıklama;
- Taşınır Mal Yönetmeliği (TMY) hazırlık çıktıları.

Kardeşlerinden tek farkı şudur: aynı okul ağındaki **bilgisayarlar ve etkileşimli
tahtalar kataloğu tarayıcıyla tarayabilir**. Bu tarama salt okurdur ve kişisel veri
içermez.

**Köken.**
- İş mantığı: OYS'nin (okulapp) `apps/kutuphane` modülü (ADR-0040, K1-K5 turları, ön
  yüzde KF1-KF6).
- Masaüstü, paketleme ve okul çekirdeği iskeleti: **kelebek-sinav (KS)**. KS,
  disiplin-defteri'nden (DD) türetildi ve masaüstü katmanında onu geride bıraktı
  (R7 §A1-A5).
- DD'den yalnız tatil takvimi ve iş günü aritmetiği alınır, o da uyarlanarak (§6.1).

| Katman | Teknoloji |
|---|---|
| Backend | Django 5.1 + DRF 3.15, **SQLite** (WAL, `synchronous=FULL`), Python 3.12 (KS sabitlemeleri) |
| Evrak | WeasyPrint 68 + openpyxl + pypdf (KS), tek kapı `shared/pdf.py`, gömülü DejaVu · QR: **segno** · 1D: bağımlılıksız **`shared/barcode128.py`** (Code128-C) |
| Yönetim arayüzü | React 18 + TS + Vite 6 + Tailwind (KS M3 kiti) |
| Ağ kataloğu | WSGI uygulaması. Django'nun istek zincirini, middleware'ini ve ORM'sini **kullanmaz**, yalnız `django.template` kullanır. Sunucu tarafında sade HTML üretir, JavaScript yoktur. SQLite'a salt okur bağlanır |
| Masaüstü | pywebview + **iki** waitress dinleyicisi. Yönetim: 127.0.0.1, rastgele port. Katalog: 8765 portu, varsayılan kapalı. Sistem tepsisi: Windows'ta pystray, Linux'ta Qt |
| Paket | Windows: PyInstaller onedir + Inno Setup (**yönetici kurulumu**) · Linux: `.deb` (KS hattı) |
| Güvenlik | **Zorunlu** yönetici parolası · Fernet alan şifrelemesi: adlar, okul no, kart no ve kişi metinleri · kimlik alanları için HMAC **kör indeks** · şifreli yedek · görevli/yönetici kipi |
| Sürüm | CalVer (`VERSION`) + `surum.json` damgası + GitHub Release + indir.okulapp.org manifesti |

Geliştirme ve test yalnız Docker'da yapılır, host'a Python ya da Node kurulmaz.
Kapı zinciri `scripts/gates.sh` KS'den gelir ve **F0'dan itibaren** CI'da koşar.

---

## 2. Verilmiş kararlar

### 2.1 Kullanıcı kararları (21.09.2026)

| # | Konu | Karar | Sonucu |
|---|---|---|---|
| U1 | Hukuki konum | **Tam kapsam, yerel araç** | Program bütün işlevleri kapsar. "Bakanlık sisteminin yerine geçer" iddiası taşımaz (§3). Açık ve belgelenmiş dışa aktarımla geçişe hazır durur. Bakanlık sistemi ödünçte kullanılmaya başlarsa bir çıkış planı vardır (§3) |
| U2 | Ağdan kim erişir | **Okul/kütüphane bilgisayarları + etkileşimli tahtalar** | Öğrenci telefonları v1 dışındadır. Tahtalar ayrı VLAN'da olduğu için ağ talebi gerekebilir. Bu, saha hattında erken başlar (§14.2) |
| U3 | Katalog ne zaman açık | **Program tepside çalışır** (okulzili deseni) | Çarpı düğmesi pencereyi gizler, programı kapatmaz. Oturum açılışında kendiliğinden başlar. Katalog açıkken **boşta kalma uykusu** engellenir; kullanıcının başlattığı uyku engellenmez (§4.5) |
| U4 | Kurulum yetkisi | **Kurucu her zaman yönetici ister** (okulzili deseni) | Program Files'a kurulur. Güvenlik duvarı kuralı kurulumda eklenir. Her güncelleme de yönetici (BTR) ister (§16) |
| U5 | Masayı kim kullanır | **Öğrenci görevliler de: iki kip** | Yönetici parolası **zorunludur**, sihirbazın ilk adımıdır. Görevli kipi yalnız dolaşım masasını ve katalog okumayı açar (§4.4) |
| U6 | İlk katalog girişi | **Excel (asıl yol) + isteğe bağlı AI köprüsü** | Doğrudan Excel içe aktarma yeniden yazılır. AI köprüsünde listeyi dış hizmete kullanıcı taşır, program kendisi bağlanmaz (§8) |
| U7 | Mevcut barkodlar | **Yok, yeniden etiketlenecek** | Barkod şemasını program belirler: salt rakam, Code128 (§7). Kitaptaki eski damga ya da defter no **isteğe bağlı** sütunla yakalanır |
| U8 | Ad | **Kütüphane Defteri** | Kısa ad `kutuphane-defteri`, önek **KD**. TMY'deki resmî defter çıktısı "Taşınır Kütüphane Defteri dökümü" diye adlandırılır |
| U9 | Masadan dosya erişimi riski | **Şifrele + ayrı masa hesabı** | Okul no ve kart no da şifrelenir, eşleştirme HMAC kör indeksle yapılır (T14; KS'den bilinçli sapma). Kurulum belgesi yönetici yetkisi olmayan bir **kütüphane masası Windows hesabı** ve BitLocker önerir (§4.3, §4.5) |
| U10 | Ağ kataloğu izni | **Okul BTR'sinin bilgisi yeterli** | Program, BTR ve müdür imzalı bir "Ağ Hizmeti Bilgi Notu" üretir, not okulda saklanır. Yönerge metni ve ilçe yolu kullanıcıya sunuldu; bu seçim bilinçli bir karardır (§3, §16) |
| U11 | Sınıf kitaplığı / öğretmene toplu teslim | **v1'e alınır** | "Teslim" ödünç değildir, Md. 18 sayı sınırı uygulanmaz. Teslim listesi basılır, geri alma toplu okutmayla yapılır. Sayımdaki yeri TMY 32/5'e **kıyasen** belirlenir, sayım kurulu seçer (§9-11) |
| U12 | Kartını unutan öğrenci | **Kartsız ödünç yalnız yönetici kipinde** | Görevli kipinde kart şarttır. Yönetici kipinde okul no ile ve gerekçeli ödünç verilebilir. "Kartı yenile" akışı eski numarayı iptal eder (§4.4) |

### 2.2 Teknik kararlar (bu belgenin önerisi — itiraz edilebilir)

| # | Karar | Gerekçe |
|---|---|---|
| T1 | **Temel KS'dir.** `desktop/`, `packaging/`, `shared/`, okul çekirdeği, FE `ui/` ve `lib/` KS'den alınır. Değişen her dosya §12'de UYARLA sınıfındadır | KS 149 commit ve saha kullanımıyla DD'nin masaüstü kusurlarını kapattı (R7) |
| T2 | Ön yüz kiti **KS'nin M3 kitidir**, Mürekkep taşınmaz | 12 ortak bileşenin prop'ları aynı (R3 §4) |
| T3 | **İki ayrı sunucu.** Yönetim sunucusu KS'deki gibi kalır. Katalog için ayrı bir waitress kullanılır; ayrı WSGI uygulaması Django'nun istek zinciri, ORM'si ve URLconf'u olmadan çalışır | Tek sunucu + izin listesi yönetim API'sini ağa açardı. waitress'in çoklu `listen` özelliğinde uygulama ve iş parçacığı havuzu ortaktır (R9 §2) |
| T4 | Ağ kataloğu **sunucu tarafında HTML** üretir, JavaScript yoktur | Eski tahta tarayıcılarında çalışır, CSP sıkı tutulabilir |
| T5 | **HTTP**, doğrudan IP, adres ve yer imi kullanılır. TLS ve mDNS yoktur | Kişisel veri yok. OYS'nin sertifika dağıtım yükü (R8 §2d). mDNS VLAN'lar arasında çalışmaz (R8 §2c) |
| T6 | **Katalog alanları asla şifrelenmez.** Kişi verisi taşıyan alanlar §6.3 listesine göre şifrelenir | Şifreli alanda DB araması yapılamaz. Katalog, program kilitliyken de çalışmalıdır |
| T7 | Türkçe arama için `search_key`, sıralama için `sort_key`, `author_sort_key` ve `subject_sort_key` alanları eklenir. Hepsi TR katlamalıdır | SQLite'ın LIKE'ı ve BINARY sıralaması Türkçe harflerde çalışmaz. Md. 8/1-a ve 11/1 yazar, eser adı ve konuya göre alfabetik katalog ister |
| T8 | Barkod **salt rakamdır**, Code128-C ile basılır. Üreteç bağımlılıksızdır: `shared/barcode128.py`, bilinen test vektörleriyle | TR-Q klavyede okuyucunun "-" karakteri "*" olur (R3 §2). Harfli kodlarda ı/i karışması da beklenir. Rakam bu sorunları ortadan kaldırır |
| T9 | Celery yoktur. Periyodik işler **"gün değişimi kapısından"** geçer: açılışta ve süreç içinde saatte bir, son çalışma tarihi bugünden eskiyse günlük yedek, rotasyon, saklama taraması ve IP denetimi koşar | Program tepside günlerce açık kalabilir. KS'nin "her gün yeniden açılır" varsayımı geçersizdir (SU-17, EK-17) |
| T10 | SMS, veli bildirimi ve bildirim modülü yoktur. Yerine **tek kişilik iade hatırlatma pusulası** gelir | Veli verisi toplanmaz |
| T11 | Güncelleme denetimi **yalnız kullanıcı "Denetle" düğmesine basınca** çalışır ve indir.okulapp.org manifestini okur. Açılışta denetim yapılmaz | MEB ağında GitHub engelli (R6 §4). KS'nin UpdateBanner'ı her açılışta dış istek atıyor (EK-5). Programın tek dış bağlantısı budur |
| T12 | Servis katmanı baştan alt modüllere bölünür | KS'de `services.py` 2.800 satıra şişti (TB12) |
| T13 | OpenAPI ve drf-spectacular yoktur. Tipler elle yazılır, serializer alan listesi anlık görüntüyle test edilir | KS/DD kalıbı |
| T14 | **Kör indeks.** Okul no ve kart no için `HMAC-SHA256(HKDF(DEK, "kd-kor-indeks"), normalize(değer))` hesaplanır. Tam eşleşme bu indeksle yapılır, sıralama Python'da yapılır | U9. KS'nin "BLIND INDEX YOKTUR" kararından (crypto.py:28) bilinçli sapmadır. Okuma geçmişi okul no ve kart no üzerinden kişiye bağlanıyordu (GA-1, KM-3) |
| T15 | `PRAGMA synchronous=FULL`. Temiz kapanış işareti yoksa pano "son işlemleri kontrol edin" kartını gösterir | WAL + NORMAL kipi elektrik kesintisinde son işlemleri geri alabilir. Dolaşımda bu sessiz kayıp demektir (SU-18) |
| T16 | **Kip durumu tek süreç içi nesnedir** (`KipDurumu`). Onu KipMiddleware, tepsi ve katalog kontrolü okur. Masaüstü ile backend arasında tek kanal vardır: `desktop/katalog_kontrol.py`, açılışta backend'e **kanca** olarak kaydedilir | Tepsi ve katalog sunucusu HTTP dışında kalır. Aksi hâlde iki durum kaynağı ve tanımsız kontrol kanalı doğar (GA-8, UY-17) |
| T17 | `SECRET_KEY` KS'deki gibi sabit kalır. Program imza, oturum ve CSRF kullanmaz; katalog imza ve çerez kullanmaz | Anahtarı "kurulumda üretmek" yönetici kurucuda uygulanamaz ve bugün bir etkisi yoktur (GA-14). İmza gerektiren bir özellik eklenirse ilk açılışta rastgele üretilir |

### 2.3 Kimlik sabitleri (F0'da toplu — KS/DD kalıntısına sıfır tolerans)

| Öğe | Değer |
|---|---|
| Ortam değişkeni öneki | `KD_*`. KS adları alınır. **`CATALOG_DIR` ve `COURSE_ALIAS_FILE` alınmaz**, çünkü ders çizelgeleri bu projede yok. **`UPDATE_REPOSITORY` de alınmaz**, çünkü güncelleme denetimi GitHub API'sinden değil indir.okulapp.org manifestinden yapılır (T11). `KD_KATALOG_PORT` ve `KD_KATALOG_HOST` yalnız geliştirme ve test içindir; gerçek kaynak `KatalogAyari`dır |
| Veri dizini | `%LOCALAPPDATA%\KutuphaneDefteri` · XDG `kutuphane-defteri` |
| Oturum | çerez `kd_oturum`, başlık `X-KD-Token` |
| Yedek | `.kdbak`, MAGIC `KDBAK\x02`, HKDF bilgisi `KutuphaneDefteri/backup/...` · kör indeks HKDF bilgisi `kd-kor-indeks` |
| Windows | yeni Inno AppId GUID · mutex **`KutuphaneDefteri` ve `Global\KutuphaneDefteri`**. Inno `AppMutex` **kullanılmaz**; kapatma yolu §4.2-5'tedir · adlı olaylar `KutuphaneDefteri.Goster` / `.Kapat` · AUMID `KutuphaneDefteri.Desktop` · exe `kutuphane-defteri.exe` |
| Paket | `kutuphane_defteri.spec`, `rthook_kd.py`, logger `kutuphane_defteri`, iş parçacıkları `kd-wsgi` / `kd-katalog` / `kd-tepsi` (yalnız Windows) / `kd-gunluk` |
| Güvenlik duvarı | `Kutuphane Defteri Katalog` (ASCII) · port kaynağı HKLM kayıt defteri değeri (§5.7) |
| Site / dağıtım | palet `kd`, `src/data/kd-release.json`, R2 `kutuphane-defteri/` + `manifest.json` |

**Kimlik kalıntısı taraması** (F0 kapısı): büyük/küçük harfe duyarsız ve TR
katlamalıdır. Kaynak kodu, basılı evrak şablonlarını ve ön yüz metinlerini kapsar.
- **Kalıplar:** `kelebek`, `ks[_:-]`, `x-ks-`, `ksbak`, `disiplin[ _-]?defteri`,
  `disiplindefteri`, `x-dd-`, `ddbak`.
- **Kullanılmayanlar:** yalın "disiplin" ve "sınav". Meşru metinde yanlış pozitif
  üretirler. Gerekirse dosya adıyla muafiyet verilir (EK-25).

---

## 3. Hukuki konum ve mevzuat çerçevesi

### Otomasyon şartı

Okul Kütüphaneleri Yönetmeliği (RG 23.11.2024/32731) iki ayrı şeyi "Bakanlıkça
belirlenen" diye niteler:
- **Md. 9/2:** otomasyon sistemini;
- **Md. 8/1-a ve 11/1:** kataloglama ve sınıflama sistemini.

Md. 11/2, 16/2, 16/3, 17, 18 ve 20-23 ise yalnız "(kütüphane) otomasyon sistemi" der
(KM-6, EK-14).

**Bakanlık sistemi.** İkincil basına göre MEB, 14.09.2026 öncesinde "Okul
Kütüphaneleri Otomasyon Sistemi"ni devreye aldı. Resmî duyuru, adres ya da aktarım
biçimi bulunamadı (R5 §5).

**Sınıflama.** 2024 metni sınıflama sistemini adlandırmıyor, yeni bir Bakanlık
belirlemesi de bulunamadı. Mülga 2001 yönetmeliğinde Dewey ve AAKK II yazıyordu.
Bu yüzden:
- sınıflama kodu **serbest alandır**;
- Dewey fiilî standart (DOS) olarak kullanılır;
- ağ kataloğundaki `/konular` gezinmesi "DOS" notuyla sunulur ve kapatılabilir;
- AI köprüsünde "Dewey" yerine "sınıflama kodu (tahmini)" denir.

### Program nasıl konumlanır

1. **Konum dili.** Program kendini "okulun kütüphane işlerini yürüttüğü yerel araç"
   diye tanıtır. Bu kural arayüzü, kılavuzu, siteyi **ve evrakı** kapsar. Kartta (E2)
   ya da ilişik belgesinde (E5) madde atfı basılacaksa şu kalıp kullanılır: "… Md.
   20'de öngörülen kullanıcı kartının okulca düzenlenen yerel karşılığıdır; Bakanlık
   otomasyon sistemindeki kaydın yerine geçmez." (KM-7)
2. **Dışa aktarım.** Birinci sınıf bir özelliktir. Şema tek ve sürümlüdür (§8.4).
3. **Çıkış planı (U1).**
   - S5 cevabı Bakanlık sisteminin kullanıldığını gösterirse "Bakanlık sistemi
     kullanımda" ayarı açılır (F10).
   - Ayar açıkken mutabakat, ilişik ve kart akışlarında "bu işlemi Bakanlık
     sisteminde de yapın" hatırlatması ve "yapıldı" işareti çıkar.
   - Bakanlık sistemi ödünçte fiilen kullanılıyorsa yerel **kişisel** ödünç kaydı
     durdurulur ve mevcut kayıtlar ilk saklama döngüsünde imha edilir. Bu kipin
     ayrıntısı **S5 cevabına kadar tasarlanmaz** (A22): dolaşım masasının o kipteki
     davranışı, ilişik, gecikme ve sayım etkileşimi Bakanlık sisteminin gerçek
     işleyişine göre yazılacak.
   - Katalog, etiket, sayım, komisyon ve ağ kataloğu sürer (KM-8).

### TMY

Resmî taşınır kaydı KBS/TKYS'dedir. Program yalnız hazırlık çıktısı üretir.

Ödünç ve iade TMY anlamında giriş ya da çıkış **değildir**:
- TMY 13/1'deki çıkış hâlleri arasında ödünç yok.
- TMY 23/4'e göre kütüphane materyali "Taşınır Teslim Belgesi düzenlenmeden idarelerin
  ödünç takip sistemleri ile takip edilir".

Bu tespit sayım (§9-10) ve teslim (U11) kurallarının dayanağıdır (KM-5, KM-16).

Süreli yayınlar için VİF düzenlenmez (TMY 10/1-a-4). Cilt birliği sağlananlar ancak
ciltletildikten sonra kayda alınır (15/4). Bu yüzden ciltsiz süreli yayın Taşınır
Kütüphane Defteri dökümüne girmez (§8.4).

### MEB Bilgi ve Sistem Güvenliği Yönergesi

| Madde | Metin ve uygulaması |
|---|---|
| 11/7 | Aynen: "Kurum ağına sistem yöneticisinin bilgisi dışında herhangi bir **aktif ağ cihazı** eklenemez." Programın dinlediği port bu hükme ancak ihtiyatlı yorumla girer |
| 4/1-s | "Sistem yöneticisi": Başkanlığın uygulama ve sistemden sorumlu bilişim personeli ya da İl/İlçe MEM'deki MEBBİS Yöneticisi veya onun sorumluluğundaki bilişim personeli. Okul BTR'si ve müdür bu tanıma girmez. **U10 bu tanım bilinerek BTR'nin bilgisiyle yetinir.** Belgede "sistem yöneticisi" geçtiği her yerde 4/1-s anlamındadır |
| 11/9 | Kurum içi sunucu ve bilgisayarlara uzaktan erişim, zorunlu hâllerde Başkanlık onayıyla yapılır. 11/22'deki örneklere (rdp, ssh, telnet) göre bu hüküm yönetim erişimini anlatır; HTTP katalog bu kapsamda görünmüyor, ama yoruma açık |
| 5/11, 11/22 | Port ve hizmet açmayı asıl bağlayan hükümler. MEBNET'teki erişim ve port yönetimi Başkanlıktadır, 80/443'e öncelik verilir |
| 11/16 | Erişim hakkı yetkisiz kişilere verilemez |
| U10 kararı | Okul BTR'sinin bilgisi yeterli sayıldı. BTR ve müdür imzalı bilgi notu (§5.9) okulda saklanır. İlçe bildirimi gerekirse aynı not üst yazının eki olarak kullanılır |
| 11/8, 11/23 | Program **yalnız kurum demirbaşı bilgisayara** kurulur. Sihirbazda "bu bilgisayar okul demirbaşıdır" onayı ve demirbaş no alanı bulunur (KM-18) |
| 11/25 | Ağ kataloğunda veri toplayan form yoktur. Arama bir GET sorgusudur ve kaydedilmez |
| 11/20-21 | Program erişim noktası kurmaz; DHCP, DNS, proxy ya da NAT sunmaz |
| 14/3 | İnternet sitesi bağlamındadır. Ağ içi katalog bu kapsamda görünmüyor, ama yoruma açık |
| 11/23 ve 11/3-h/ı | Program veriyi buluta aktarmaz. İsteğe bağlı AI köprüsünde ise kitap listesini dış bir hizmete **kullanıcı** taşır. Bu adım bu hükümlerle çatışabilir; sorumluluk kullanıcıdadır ve asıl yol Excel'dir (KM-26) |

### KVKK

**Dayanak.** 5/2-ç (hukuki yükümlülük). Yükümlülüğü kuran hükümler: Yönetmelik Md.
8/1-f, 16/2, 16/3, 18 ve 23 (ödünç kaydı, iade takibi, ayrılışta iadenin sağlanması).
Program, Bakanlık sistemine erişilene dek bu yükümlülüğün yerine getirildiği yerel
araçtır (KM-8).

**Profil yasağı.** Nedeni şudur: ödünç verisi md. 6'ya kayabilir, 6/3'te ise genel bir
hukuki yükümlülük bendi yoktur. Bu yüzden şu kurallar CLAUDE.md'ye ve testlere girer
(KM-14):
- üye bazında konu ya da sınıf dağılımı üretilmez;
- şube × konu kırılımı en az k farklı üye eşiği olmadan yapılmaz;
- not ya da başarı verisi alanı eklenmez;
- adlı okuma sıralaması ağa, panoya, E9'a ve velilerle paylaşılabilecek raporlara
  girmez;
- Kılavuz 7'deki ödül için iç çıktı yalnız yönetici kipinde, "iç kullanım" ibaresiyle
  basılır.

**Aydınlatma metni (E13).** md. 10/1'in asgari unsurlarını taşır:
- veri sorumlusu: Millî Eğitim Bakanlığı — okul müdürlüğü;
- amaçlar;
- hukuki sebep: 5/2-ç ve yukarıdaki maddeler;
- kaynaklar: e-Okul listesi ve masa;
- kimlerin gördüğü, **masadaki öğrenci görevliler dahil**;
- Bakanlık sistemine geçişte taşınabilirlik;
- saklama süreleri (§6.4);
- md. 11 hakları ve başvuru yolu.

Metin **e-Okul aktarımından önce** duyurulur (KM-13).

**Ödünç ≠ okuduğu kitap.** Öğrenci bazlı ödünç sayısı öğretmene ya da e-Okul'a
aktarılmaz; yalnız sınıf düzeyinde toplam verilir. Bu, amaç sınırlamasının gereğidir
(SU-24).

### Mevzuat metinleri depoya girer (F0)

- Okul Kütüphaneleri Yönetmeliği ve Uygulama Kılavuzu.
- evrakmotoru/mevzuat'taki **tam metinler:** Bilgi ve Sistem Güvenliği Yönergesi,
  6698 sayılı KVKK, Aydınlatma Yükümlülüğü Tebliği, TMY (5/8, 10/1, 13/1, 15/4, 23/4,
  24, 27, 28, 31, 32, 34 dahil).
- TBK md. 92-93 alıntısı: sürenin hesaplanması ve son günün tatile rastlaması. İade
  tarihi kaydırmasının kıyas dayanağıdır (§9-5).
- Kişisel Verilerin Silinmesi, Yok Edilmesi veya Anonim Hâle Getirilmesi Hakkında
  Yönetmelik: resmî kaynaktan birebir alınır.
- Ortaöğretim Kurumları Yönetmeliği'nin ilgili maddeleri.

Her atıf bu metinlerden doğrulanır (KS kuralı) (KM-22).

### Okul türü

- Md. 19'daki kayıp bedeli yalnız ortaöğretimde uygulanır. `SchoolConfig.kademe` ile
  açılır.
- İlkokulda sınıf kitaplığı zorunludur (Md. 4/1-i, 5/1). U11 teslim akışı bunu
  karşılar.

---

## 4. Mimari

### 4.1 Süreç modeli

```
kutuphane-defteri.exe (tek süreç, tek kopya kilidi, KipDurumu tek nesne)
├── ana iş parçacığı: pywebview penceresi (gizlenebilir)
│     Linux: Qt olay döngüsü + QSystemTrayIcon (webview.start'tan önce kurulur)
├── kd-wsgi      waitress 127.0.0.1:<rastgele> → Django (tam API + SPA)
│                  SessionToken · RestartRequired · AppLock(423) · KipMiddleware
├── kd-katalog   waitress <dinleme adresi>:8765 (ayarla açılır) → katalog WSGI
│                  yalnız GET/HEAD · sqlite3 mode=ro + query_only + authorizer
├── kd-tepsi     yalnız Windows: pystray (daemon olmayan; Çık'ta icon.stop())
└── kd-gunluk    saatlik "gün değişimi kapısı" + uyku engelleme sahibi
```

**Değişmezler** (testle kilitlenir, §5.10):

- Yönetim `BackgroundServer`'ı `DEFAULT_HOST` (127.0.0.1) dışında bir host kabul etmez.
  0.0.0.0 yalnız `desktop/katalog_server.py` içinde geçer.
- Katalog uygulaması Django URLconf'unu, ORM'yi ve `django.db`'yi **import etmez**.
  Şablonlarında `{% url` ve `{% load` geçmez.
- Katalog uygulaması `HTTP_COOKIE` okumaz ve çerez yazmaz.
- Katalog yalnız `prepare_django` tamamlandıktan sonra kalkar.
- Yönetim portu hiçbir ekranda ya da belgede ilan edilmez. Program içindeki katalog
  bağlantıları 127.0.0.1 üzerinden değil seçili LAN IP'siyle kurulur ve harici
  tarayıcıda açılır. Çerezler portlar arasında yalıtılmadığı için bu gereklidir
  (GA-16).

### 4.2 Açılış ve kapanış

KS sırası izlenir: kilit → belirteç → sürüm damgası → bütünlük → yedek → migrate →
yönetim sunucusu → sağlık denetimi → WebView2 → pencere. Farkları:

1. **İkinci açılış.**
   - `lock.acquire()` hata fırlatmaya devam eder.
   - Pencereyi gösterme sinyali ayrı bir yardımcıdadır (`lock.signal_running_instance`).
     Yalnız bayraksız normal açılışta gönderilir: çalışan kopyanın penceresi öne gelir
     ve ikinci süreç 0 koduyla çıkar.
   - `--geri-yukle`, `--autotest` ve `--pdf-duman` çalışan bir kopya bulursa **2**
     koduyla çıkar. `--geri-yukle` şu iletiyi gösterir: "Program tepside çalışıyor.
     Tepsideki simgeden Çık'ı seçip yeniden deneyin." (GA-11, UY-9)
2. **Katalog.** Ayar açıksa ve güvenlik duvarı denetimi geçerse (§5.7) kalkar. Önce
   kendini sınar:
   - `api/` altındaki bütün desenler katalog portunda 404 döner;
   - `/` yolu katalog şablonunun imzasını döndürür.

   Sınama geçmezse katalog kapanır ve Ağ Doktoru'na kayıt düşer. **F0-F4'te** katalog
   yalnız 127.0.0.1'de dinler; 0.0.0.0'da dinleme kural denetimiyle birlikte F5'te
   gelir (UY-19).
3. **Otomatik başlatma.**
   - Kütüphane masası hesabında oturum açılınca program **kilit ekranı görünür** olarak
     açılır.
   - `--tepside` ile gizli açılış isteğe bağlıdır.
   - Windows oturumu açılmadan ne program ne ağ kataloğu kalkar. Kurulum belgesi bunu
     yazar (SU-1).
4. **Pencere kapatma** pencereyi gizler. **Çık** akışı:

   | Durum | Çık |
   |---|---|
   | Yönetici kipi | Doğrudan çıkar |
   | Görevli kipi | Pencere öne gelir → SPA'da yönetici parolası → `POST /api/v1/app/quit/` → kanca üzerinden düzenli kapanış (`icon.stop()`, pencere, iki sunucu, WAL checkpoint) |
   | Kilitli ya da `restart_required` | Parolasız çıkar |

   Bu koruma **kaza önleyicidir, güvenlik sınırı değildir**: Görev Yöneticisi süreci
   kapatabilir (GA-8, UY-18).
5. **Kurucu ve kaldırıcıda kapatma yolu tektir: adlı olay** (GA-15).
   - Inno `AppMutex` kullanılmaz. Kullanılsaydı kaldırıcı, olayı gönderecek aşamaya
     gelmeden "programı kapatın" iletisinde beklerdi.
   - `[Code]` içindeki `InitializeSetup` ve `InitializeUninstall` aşamaları
     `KutuphaneDefteri.Kapat` olayını gönderir. Ardından iki mutex serbest kalana dek
     en çok 30 sn bekler. Program bu sürede düzenli kapanır (WAL checkpoint).
   - Program bu sürede kapanmazsa kurucu "tepsideki simgeden Çık'ı seçin" iletisini
     gösterir ve yeniden dener. Süreç zorla sonlandırılmaz.
   - okulzili'nin `CloseMainWindow` adımı bu programda işe yaramaz, çünkü pencereyi
     kapatmak programı tepsiye gizler.
   - Bu akış F0 spike'ında Inno'nun gerçek aşama sırasıyla doğrulanır.
6. **Temiz kapanış işareti** veri dizinine yazılır. Açılışta işaret yoksa panoya "son
   oturumdaki ödünç ve iadeleri kontrol edin" kartı ve son işlemler listesi düşer
   (T15).

### 4.3 Tehdit modeli

| Tehdit | Katman | Kalan risk |
|---|---|---|
| Aynı makinedeki başka bir süreç yönetim API'sine istek atar | KS oturum belirteci (fail-closed 403), yalnız loopback | — |
| **Masadaki öğrenci program üzerinden** okuma geçmişine, üye listesine ya da yedeğe ulaşmaya çalışır | Görevli kipi (sunucu tarafı, fail-closed izin listesi, §4.4) + yönetici parolası | Hatalı izin listesi: bunu URL desenlerini dolaşan test yakalar |
| **Masadaki öğrenci Windows oturumu üzerinden** veri dizinini kopyalar ya da tarayıcıda açık başka oturumlara erişir (GA-1, KM-2, EK-1) | U9: adlar, okul no, kart no ve kişi metinleri şifreli, eşleştirme kör indeksle · kurulum belgesi yönetici yetkisi olmayan ayrı bir **kütüphane masası Windows hesabı** önerir; bu hesapta e-Okul, MEBBİS, DYS ve e-posta açılmaz · BitLocker önerisi · görevlilerin müdürlükçe yazılı görevlendirilmesi ve gizlilik bilgilendirmesi (S7) | Düz metinde şube, üye türü ve ödünç zaman damgaları kalır. Küçük şubede kişi tahmin edilebilir. Personelin unvanı ve branşı **hiç alınmaz**, bu yüzden öğretmen branş üzerinden tanınmaz (V2-01). Aydınlatma metnine ve teknik borca yazılır |
| Kilitliyken `guvenlik.json` silinir ya da yeniden adlandırılır (GA-2) | DB'de parmak izi varken dosya yoksa durum **"güvenlik dosyası kayıp"** kilididir. Yalnız durum, kurtarma ve geri yükleme yolları açık kalır. `enable()` yalnız parmak izi boşken çalışır | Geri yükleme `guvenlik.json`'u yedekteki başlıktan yeniden yazar |
| Ağdaki bir cihaz yönetim işlevine ya da kişisel veriye ulaşmaya çalışır | Ayrı sunucu, ayrı uygulama, salt okur bağlantı, eylem kodlu authorizer, kişisel veri içermeyen görünümler (§5.3) | — |
| Kötü niyetli sayfa DNS rebinding yapar | Belirteç çerezi `SameSite=Strict` ve yalnız WebView2 profilinde. Paketli yapıda `ALLOWED_HOSTS` yalnız 127.0.0.1 ve localhost; `backend` adı yalnız `KD_SESSION_TOKEN` boşken (geliştirme ve test) eklenir (GA-13) | — |
| Disk, bilgisayar ya da yedek çalınır | Zorunlu parola + §6.3 şifreleme + X25519 şifreli yedek | Kopyalanan dosyada eser adları, şube, üye türü ve tarihler düzdür. Ad, okul no ve kart no olmadan kişiye doğrudan bağlanamazlar. Küçük gruplarda tahmin mümkündür (yukarıdaki satır). **Tam koruma için BitLocker** |
| Görevli, kart numaralarını sırayla yazarak üye adlarını çıkarır (GA-7) | Kart no: 6 rastgele hane + sağlama hanesi · art arda 5 geçersiz kart → yönetici parolası | — |
| Ağdan yük bindirilir ya da slowloris saldırısı yapılır (GA-12) | Kendi havuzu, `connection_limit`, kısa zaman aşımı, IP başına token-bucket · kabul anında IP başına eşzamanlı bağlantı sınırı (dispatcher alt sınıfı) | Kalan risk yalnız katalogun erişilemez olmasıdır, veri riski yoktur |

*F1 eki (22.09.2026):* bozuk güvenlik dosyası da kayıp kilidine düşer; kayıp ekranında
koşullu "Güvenlik dosyasını sıfırla ve kuruluma dön" yolu vardır (§14.1 F1 ekleri, 1).

### 4.4 İki kip: görevli ve yönetici (U5)

**Terim.** "Kütüphane yöneticisi" kütüphaneci ya da kütüphaneden sorumlu öğretmen
demektir. Çoğu okulda kütüphaneci atanmaz (Md. 7/1).

**Durumlar.** `KİLİTLİ` → (parola ya da kurtarma anahtarı) → `YÖNETİCİ` ⇄ `GÖREVLİ`.
Ayrıca `GÜVENLİK_DOSYASI_KAYIP` ve `YENİDEN_BAŞLAT_GEREK` durumları vardır.

- **Kilit açılışı.** DEK'i yalnız yönetici parolası ya da kurtarma anahtarı çözer.
  Açılış yönetici kipine götürür.
- **Görevli kipine geçiş** parolasızdır. Tepsiden ya da klavye kısayoluyla anında
  yapılabilir.
- **Görevli kipinden çıkış** yönetici parolası ister.
- **Kilitle** her kipte parolasızdır. DEK bellekten silinir ve durum `KİLİTLİ` olur.

**Boşta dönüş.** Süre **sunucuda tembel olarak** dolar: KipMiddleware her istekte önce
`son_etkinlik + N < şimdi` koşulunu denetler, doluysa kipi görevliye indirir.
- `son_etkinlik` yalnız kullanıcı eylemi taşıyan isteklerde güncellenir. Ön yüz
  etkileşimde `X-KD-Etkinlik` başlığını gönderir; durum ve pano sorguları göndermez.
- Ön yüzdeki geri sayım yalnız görseldir.
- Varsayılanlar: N = **3 dk**. Ayrıca etkinlikten bağımsız **mutlak süre 30 dk**; süre
  dolunca parola yeniden sorulur. İkisi de ayarlanabilir (GA-9, KM-2).
- *F1 eki (22.09.2026):* kurulum sihirbazı bitene kadar süreler kipi DÜŞÜRMEZ (anahtar
  ekrandayken ekrandan atmasın); elle geçiş ve Kilitle çalışır (§14.1 F1 ekleri, 8).

**KipMiddleware kuralları.**
- Yalnız kilit açıkken ve kip görevliyken devreye girer.
- `HEALTH_PATH`, `setup/status/` ve `security/status/` uçlarını **hiçbir durumda**
  kesmez.
- Reddi 403 ile ve `{"code":"kip_yetkisiz"}` gövdesiyle döner. Böylece belirteç
  403'ünden ayırt edilir (UY-16).

**Görevli kipinin izin listesi** uç **ve parametre** düzeyinde, fail-closed çalışır:

| Açık | Kapalı |
|---|---|
| Kartla üye çözme: yalnız **ad** ve **kalan ödünç hakkı**. Sınıf gösterilmez | Okul no ya da ad ile üye arama |
| Ödünç ver. `override_reason` taşıyan istek **403** alır | Gecikme istisnası |
| Barkodla iade | İade sonrası ödünç alanın kimliği, "son işlemler" listesi |
| Nüsha durum sorgusu | Üye listesi, okuma geçmişi, gecikme listesi |
| Katalog okuma: `works` ve `copies` GET, ağ kataloğunun alan listesine denk serializer ile | `acquisitions`, `commission-decisions`, bağışçı, fiyat, TKYS alanları |
| Teslimden geri alma okutması (U11) | Teslim verme |
| Kip ve güvenlik durum uçları · kip yükseltme (gövdede yönetici parolası) · `app/quit/` (gövdede yönetici parolası; parolasız istek 403) | Raporlar, ayarlar, yedek, içe aktarma, sayım onayı, ayıklama, kayıp dosyaları, ilişik |

**Görevlinin gördüğü iletiler.**
- Gecikmesi olan üyede eser adı ve gecikme günü gösterilmez. Yalnız "Ödünç
  verilemiyor — kütüphane yöneticisine yönlendirin" yazar.
- Kişisel olmayan sebepler gösterilebilir: "sınır dolu", "bu kaynak ödünç verilmez"
  (KM-9, SU-4).

**İstisnalar.**
- Gerekçeli istisna yalnız **politika kuralı** olan gecikme engeline
  (`block_loan_if_overdue`) tanınır ve yalnız yönetici kipinde yapılır.
- Md. 18 sayı sınırı ile Md. 16/1'de sayılan kaynaklar **hiçbir kipte** istisna almaz.
  Bunu validator ve test sağlar.

**Kartsız ödünç (U12).**
- Yalnız yönetici kipinde yapılır: okul no ile üye bulunur, kapalı listeden bir
  gerekçe seçilir.
- Ödünç kaydına "kartsız" işareti düşer. Md. 23/1-a'dan sapma olarak kayda geçer.

**Kartı yenile.** Yalnız yönetici kipindedir.
- Yeni kart no verilir, eski no `CardRevocation` tablosuna yazılır.
- Eski kart okutulursa "iptal edilmiş kart" uyarısı çıkar.
- Açık ödünçler üyelikte kalır.

**Onay adımları.** Ayıklama, sayım ve teslim onayları yönetici kipinde yapılır.
- "Onaylayan" her zaman **şifreli ad metnidir**. Personnel'den seçim yalnız bu metni
  doldurur, FK tutulmaz (KM-12). Yanına tarih düşülür.
- Islak imza basılı tutanakta kalır. OYS'deki "hazırlayan ≠ onaylayan" rol kuralı yerine
  iki adımlı durum makinesi ve onay damgası vardır (KS B12 emsali).

**Kütüphane yöneticisi yokken** (SU-1):
- Kurulum belgesi yönetici parolasının görevlendirilmiş **en az iki kişide**
  bulunmasını önerir: sorumlu öğretmen ve memur ya da sorumlu müdür yardımcısı.
- Kurtarma anahtarı müdürlükte kapalı zarfta saklanır.
- "Kilitliyken iade" ve ikinci parola yuvası v1'de yoktur (A17).

**Görev devri** (SU-25). Güvenlik ekranında yönetici kipinde çalışır:
- parola değişir;
- kurtarma sarmalı yeni anahtarla yeniden yazılır, eski anahtar bu kurulumun kilidini
  artık açmaz (*F1 eki (22.09.2026):* "Kurtarma anahtarını yenile" F1'e çekildi; DEK
  değişmediği için eski yedekler ve arşivlenen güvenlik dosyası eski anahtarla
  açılabilir kalır — §14.1 F1 ekleri, 8);
- yeni anahtar saklanır ve saklandığı doğrulanır (aynı damga);
- devir-teslim notu (E18) basılır.

Eski yedekler eski parola ve anahtarla açılabilir kalır; kılavuz bunu anlatır.

**Tepsi kip matrisi** (tepsi `KipDurumu`'nu okur, testle kilitlenir):

| Komut | Kilitli | Görevli | Yönetici |
|---|---|---|---|
| Pencereyi aç | ✓ | ✓ | ✓ |
| Ağ kataloğu durumu ve adresi | ✓ (bilgi) | ✓ (bilgi) | ✓ |
| Ağ kataloğunu aç/kapa | — | — | ✓ |
| Görevli kipine geç | — | — | ✓ |
| Kilitle | — | ✓ | ✓ |
| Çık | ✓ | parola (SPA) | ✓ |

### 4.5 Pencere, tepsi, otomatik başlatma, uyku, hesap

**Tepsi.**
- **Windows:** `pystray` (0.19.5) ve `six` `requirements-paketleme.txt`'e
  `sys_platform == "win32"` işaretiyle girer. Spec `collect_submodules("pystray")`,
  `six.moves` ve `PIL.ImageDraw` toplar.
  - `giris.py`'de ayrı bir `DESKTOP_RUNTIME_MODULES` listesi tutulur. Test bu listeyi
    platform işaretine göre `requirements-paketleme.txt` ile eşitler (UY-6).
  - LGPLv3 gereği okulzili'deki `THIRD_PARTY_LICENSES` yolu izlenir: lisans metni
    **ve pystray kaynağı** pakete girer.
  - `run_detached` daemon olmayan bir iş parçacığı açar. Bu yüzden Çık'ta `icon.stop()`
    şarttır.
- **Linux:** `QSystemTrayIcon`, `webview.start`'tan önce **ana iş parçacığında**, var
  olan `QApplication` örneğiyle kurulur. `isSystemTrayAvailable()` yanlışsa pencere
  küçültülür (okulzili yedeği) (UY-7).
- **F0 spike'ı** bu iki yolu gerçek pencerede sınar.

**Otomatik başlatma.**
- Inno görevi, okulzili'deki gibi Görev Zamanlayıcı'ya `runasoriginaluser` ile yazar.
- Kurucu **kütüphane masası hesabında** başlatılır, UAC penceresine BTR kimliği girilir.
  Kurucuyu BTR kendi oturumunda başlatırsa görev BTR'ye yazılır (GA-15).

**Uyku.**
- Ağ kataloğu açıkken `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`
  çağrılır. Çağrı **yalnız `kd-gunluk` iş parçacığından** yapılır, kapanışta
  temizlenir.
- Yalnız boşta kalma uykusunu engeller; kullanıcının başlattığı uyku ve kapak
  kapatma engellenmez (UY-17).
- Linux'ta `systemd-inhibit` kullanılır; sahada doğrulanır.

**Hesap ve bilgisayar.**
- Veri, programı çalıştıran hesabın `%LOCALAPPDATA%` dizinindedir.
- Önerilen hesap U9'daki ayrı **kütüphane masası hesabıdır**. Program ve kütüphane
  yöneticisinin günlük işi bu hesapta yürür. Kişisel oturumlar bu hesapta açılmaz.
- e-Okul listesi bu hesaba şifreli taşıyıcıyla getirilir ve içe aktarımdan sonra
  silinir.
- Veri `ProgramData`'ya **taşınmaz**, çünkü bütün hesaplara okuma hakkı verirdi.
- Bilgisayar okul demirbaşıdır (§3).
- Yeni bilgisayara taşıma kontrol listesi `docs/kurulum.md`'dedir: kurulum → `.kdbak`
  geri yükleme → güvenlik duvarı → DHCP rezervasyonunun yeni MAC adresine taşınması →
  afiş ve yer imleri.

---

## 5. Ağ kataloğu tasarımı

### 5.1 Kapsam

| Görünür | Asla görünmez |
|---|---|
| Künye: başlık, yazar, çevirmen, yayınevi, baskı, yıl, ISBN, konu, dil, tür | Üye listesi, üye adı, sınıfı, kart no |
| Sınıflama kodu + **ana sınıf adı** (DOS), yer numarası, **bölüm adı ve tarifi** (kontrollü liste, §6.2) | Kimin ödünç aldığı, okuma geçmişi, gecikenler, iade tarihi (A1) |
| Nüsha özeti: "3 nüsha · 2 rafta · 1 ödünçte" | Kayıp/hasar kayıtları, bedeller |
| Durumlar: Rafta / Ödünçte / **Ödünç verilmez — kütüphanede okunur** / Geçici olarak kullanım dışı / **Sınıf kitaplığında** (U11) | Bağışçı, fiyat, TKYS kodu, eski kayıt no |
| Vitrin: **yeni gelenler** (`Copy.created_at`) · **çok okunanlar** (eşikli, sayı gösterilmez, yalnız sıra — §5.3) | Komisyon ve sayım kurulu adları |
| Alfabetik dizinler: yazar, eser adı, konu (Md. 11/1) | Yedek, dışa aktarım, yönetim ekranları, PDF üretimi |
| Okul adı, kütüphane saatleri (`kd_katalog_okul` görünümü) | — |

**"Ödünç verilmez"** tek bir türetimdir: `is_reference OR is_out_of_print OR
resource_type = 'PERIODICAL'`. Python'daki `is_loanable` ile SQL karşılığının eşleştiği
parite testiyle sabitlenir (UY-12).

**Listelenmeyenler:**
- yumuşak silinmiş eser ve nüsha (`deleted_at IS NOT NULL`);
- `LOST`, `WITHDRAWN_*`, `TRANSFERRED` durumundaki nüshalar.

Sayaçlar da yalnız bu süzgeçten geçen nüshalardan türer (EK-7).

**Dijital kaynaklar** künye olarak listelenir, dosya dağıtılmaz.

### 5.2 Sunucu

- `desktop/katalog_server.py` kendi `BackgroundServer` örneğini kurar. Terimler şöyle
  ayrılır (GA-18):
  - **dinlemek (bind):** seçili adreste portu açmak;
  - **bağlanmak (connect):** istemci olarak bir adrese bağlantı kurmak. Windows'ta
    0.0.0.0'a bağlantı kurulamaz, bu yüzden hazırlık beklemesi ve öz sınama
    127.0.0.1 ya da seçili LAN IP'si üzerinden yapılır.
- **Soket kendimiz açılır.** Windows'ta `SO_EXCLUSIVEADDRUSE` ile dinlenir ve waitress'e
  `sockets=[...]` olarak verilir. waitress'in ardından denediği `SO_REUSEADDR` yutulur;
  bu F0 spike'ında sınanır. Port doluysa Türkçe "port kullanımda" iletisi çıkar
  (R9 §2).
- **Dinleme adresi.** Varsayılan 0.0.0.0'dır. İsteğe bağlı "yalnız seçili IP'de dinle"
  seçeneğinde IP değişirse dinleyici yeni IP'de yeniden açılır ve kullanıcı uyarılır. Ağ
  Doktoru, varsayılan rota dışındaki etkin arayüzleri "katalog bu ağlarda da
  erişilebilir" uyarısıyla listeler (EK-30).
- **Ayarlar:** `threads=4`, `connection_limit=300`, `channel_timeout=30`,
  `max_request_body_size=1024`, `max_request_header_size=8192`, `ident=None`.
  Kabul anında IP başına eşzamanlı bağlantı sınırı, ör. 20.
- **Port** varsayılanı 8765'tir. Değişikliği yalnız yönetici kipinde yapılır. UAC
  yardımcısı hem güvenlik duvarı kuralını hem **HKLM kayıt defteri değerini**
  günceller. Kurucu portu bu değerden okur (§5.7).
- **Ağ kataloğu varsayılan olarak kapalıdır.** İlk kez açılırken Ağ Doktoru adım adım
  yönlendirir.
- **Taşınabilir pakette** ağ kataloğu sunulmaz: kural program yoluna bağlıdır
  (GA-5).

### 5.3 Veri erişimi

**Bağlantı sırası.** Her istek kendi bağlantısını açar ve kapatır:

1. `sqlite3.connect(Path.as_uri() + "?mode=ro", uri=True)`
2. `PRAGMA query_only=ON`
3. `set_authorizer(...)`
4. `set_progress_handler(...)`: uzun sorguyu keser.

**Authorizer** eylem koduna göre çalışır. Görünüm üzerinden okumada SQLite alttaki
tablonun sütunu için `SQLITE_READ` çağırır ve görünüm adını **5. argümanda** verir
(GA-3, UY-11, EK-3):

| Eylem | Karar |
|---|---|
| `SQLITE_SELECT` | izin |
| `SQLITE_FUNCTION` | izin listesi: `like`, `lower`, `count`, `coalesce`, `substr`, `length` |
| `SQLITE_READ`, 5. argüman `kd_katalog_` ile başlıyor ve (tablo, sütun) sabit izin listesinde | izin |
| `SQLITE_READ`, 5. argüman `None` ve tablo `kd_katalog_*` (görünümün kendi sütunları; `count(*)` için boş sütun dahil) | izin |
| Geri kalan her şey | `SQLITE_DENY` |

**Görünümler.**
- `kd_katalog_eser`, `kd_katalog_nusha`, `kd_katalog_okul`.
- Yumuşak silme ve durum süzgeçleri görünüm tanımına yazılır.
- `Loan`, `Membership`, `Acquisition` ve kişi tabloları görünümlere **hiç girmez**.
  Bunu kaydedici bir authorizer ile "okunan (tablo, sütun) kümesi" anlık görüntü testi
  sabitler.

**Görünümlerin yaşam döngüsü.** Django'nun SQLite şema düzenleyicisi tabloyu yeniden
kurduğu için görünüm migration'da kalıcı durmaz (UY-10):
- `pre_migrate`: `DROP VIEW IF EXISTS`;
- `post_migrate`: idempotent `CREATE VIEW`;
- migrate sonrası her görünüm için `SELECT … LIMIT 0` testi.

**Çok okunanlar** Django tarafında hesaplanır:
- **gün değişimi kapısında** günde bir kez, `kd_katalog_populer` tablosuna yazılır:
  (eser, pencere, sıra);
- eşik: pencere içinde **en az k farklı üye** (`COUNT(DISTINCT membership_id)`,
  k = 5, ayarlanabilir 3-10);
- kapanmış pencerelerin satırları dondurulur; anonimleştirmeden sonra yeniden
  hesaplanmaz;
- ağ vitrininin penceresi dönem, E12 afişinin penceresi aydır;
- sayı gösterilmez (GA-10, KM-11, EK-23).

**Arama.**
- Sorgu `search_key` ile aynı katlamadan geçer. Kelimeler AND ile birleşir, sorgu
  `LIKE ? ESCAPE '\'` ile yazılır ve en fazla 100 karakterdir.
- Sayfa boyutu 20'dir. `sayfa` değeri `1..min(ceil(toplam/20), 500)` aralığına
  kırpılır.
- `id`, `tur` ve `konu` tam sayı ya da sabit küme olarak doğrulanır; geçersiz değer
  404 döner.
- FTS5 ancak ölçüm gerektirirse eklenir.

**Geri yükleme** (GA-4, UY-8):
1. Katalog **bakım kapısına** alınır: DB'ye dokunmadan 503 döner.
2. Uçuştaki istek sayacı sıfıra inene kadar beklenir.
3. Kanallar kapatılır: `wasyncore.close_all(map)` + `task_dispatcher.shutdown()`.
4. Çok okunanlar yazıcısı ve açılış görevleri ortak **bakım kilidiyle** durdurulur;
   bağlantılarını `finally` bloğunda kapatırlar.
5. Katalog, program yeniden açılana kadar kapalı kalır.

`restart_gate` iletisi şöyledir: "Tepsideki simgeden Çık'ı seçip programı yeniden
açın."

**Test ortamı.** Katalog testleri dosya tabanlı bir `TEST NAME` ve
`django_db(transaction=True)` ile koşar. Bellek içi test veritabanını ayrı bir `mode=ro`
bağlantısı göremez (UY-10).

### 5.4 Arayüz

**Sayfalar.**
- `/`: arama ve vitrin.
- `/ara?q=&tur=&konu=&sayfa=`
- `/eser/<id>`
- `/yazarlar/<harf>` ve `/eserler/<harf>`: A-Z dizin, sayfalı. **Klavyesiz
  gezinme** ve Md. 11/1'deki alfabetik düzen bu sayfalarla sağlanır (SU-15).
- `/konular`: DOS ana sınıfları.
- `/hakkinda`: saatler; ağ kataloğunun ne gösterip ne göstermediği.

**Şablonlar.** `django.template.Engine(dirs=[…], autoescape=True)` kullanılır. Kitap
adları Excel'den ve AI köprüsünden geldiği için otomatik kaçırma zorunludur.

**CSS.** Bellekte gömülüdür ve KS paletinden türer. Dış font ya da CDN yoktur,
JavaScript yoktur.

**Tahta kipi.**
- Dağıtılan yer imi `?tahta=1` parametresini taşır. Sunucu büyük düzeni seçer ve
  parametreyi bağlantılarda korur.
- Medya sorgusu olarak `any-pointer: coarse` de kullanılır.
- Dokunma hedefi 48 px'tir.
- F5 kod kapısı: "ekran klavyesi olmadan bir esere ulaşılır".

**Eski tarayıcı uyumu.** Düzen flex tabanlıdır. Eski Chromium ve Firefox ESR'de
sınanır.

**Hata sayfaları.** Türkçe ve sabit metinlidir. İç yol, sürüm ya da yığın bilgisi
göstermez.

### 5.5 Başlıklar, sınırlar, günlük

- **CSP:** `default-src 'none'; style-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`
- **Diğer başlıklar:** `nosniff`, `Referrer-Policy: no-referrer`, arama sayfalarında
  `Cache-Control: no-store`.
- **Yöntemler:** yalnız GET/HEAD kabul edilir, diğerleri 405 alır. Yol tablosu sabit
  bir kümedir.
- **Hız sınırı:** `REMOTE_ADDR` başına bellekte token-bucket. `X-Forwarded-For` okunmaz.
- **Günlük:** erişim günlüğü yoktur; IP ve arama terimi yazılmaz. Yalnız kişisiz günlük
  sayaçlar ve Ağ Doktoru'nun son hatası tutulur.

### 5.6 Erişim yolu

**Afiş.** Adres büyük puntoyla birincildir, QR küçük ve ikincildir. Kapsamdaki
bilgisayar ve tahtalar QR okumaz (SU-14).

**Yer imi dağıtımı.** Kullanıcı başına yazılan yer imi yetmez: ETAP her öğretmene ayrı
hesap açar (OYS ADR-0047 dersi). Ağ Doktoru şu dosyaları üretir:
- **ETAP/Pardus:** `/etc/chromium/policies/managed/` altında `ManagedBookmarks`
  politika dosyası ya da `/usr/share/applications/` altında `.desktop` başlatıcısı;
- **Windows:** `.url` kısayolu.

Liderahenk ile dağıtım yetkisi BTR'ye sorulur (S1).

**IP seçimi.** Varsayılan rotanın arayüzü seçilir. Aday listesi sunulur ve seçim
hatırlanır. 127/8 ve 169.254/16 atılır.

**IP değişimi.** Gün değişimi kapısı IP'yi denetler. IP değiştiyse "afişi yeniden
basın, **yer imlerini güncelleyin**" uyarısı çıkar. DHCP rezervasyonu MAC adresine
bağlıdır (S3).

**Kullanılmayanlar:** mDNS, NetBIOS adı, dış DNS.

### 5.7 Güvenlik duvarı

**Kurucu (Windows, yönetici).** "Yerel ağdan katalog taramasına izin ver" görevi
sunulur:
- **İlk kurulum:** önce `delete rule name=all dir=in program="{app}\kutuphane-defteri.exe"`
  çalışır, çünkü eski iletişim kutusunun bıraktığı engelleme kuralları izin
  kurallarından önce gelir. Sonra şu kural eklenir:

  ```
  netsh advfirewall firewall add rule name="Kutuphane Defteri Katalog" dir=in action=allow
    program="{app}\kutuphane-defteri.exe" protocol=TCP localport=<HKLM port, yoksa 8765>
    remoteip=LocalSubnet profile=domain,private,public enable=yes
  ```

- **Güncelleme kipi:** kural varsa silme ve ekleme adımları **atlanır**. Böylece
  değiştirilmiş port ve BTR'nin eklediği bloklar korunur (EK-29).
- **Kaldırma:** kural silinir.

**Kuralın kapsamı.**
- `remoteip` varsayılanı **LocalSubnet**'tir. Tahta VLAN'ının bloğu S1'de öğrenilir ve
  Ağ Doktoru'nun "Kuralı güncelle (UAC)" adımıyla eklenir; BTR'nin doğruladığı CIDR'ler
  girilir.
- RFC1918'in tamamı açılmaz. MEB WAN'ındaki başka kurum adresleri de özel aralıktadır
  (GA-6).
- Profiller Genel dahil açıktır, çünkü okul ağları çoğu zaman "Genel" görünür.

**Program içi denetim** yapılandırılmış veriyle yapılır:
`Get-NetFirewallRule -PolicyStore ActiveStore` | `Get-NetFirewallApplicationFilter` /
`PortFilter` / `AddressFilter`. Denetlenen beş şey:
1. kural etkin mi;
2. program yolu `sys.executable` ile aynı mı;
3. port ayarla aynı mı;
4. profil ve `remoteip` ne;
5. exe için bir gelen engelleme kuralı var mı.

Biri tutmazsa program **0.0.0.0'da dinlemez**, Ağ Doktoru düzeltme adımını gösterir.
netsh çıktısı yerelleştirilmiş gelir ve ayrıştırılamaz, bu yüzden kullanılmaz (GA-5).
Denetimin yönetici olmayan hesapta çalıştığı sahada doğrulanır (F5 eki).

Üçüncü parti antivirüs güvenlik duvarları bu kuralı yok sayabilir. Kurulum belgesi
bunu anlatır.

**Pardus.** Paket ufw uygulama profili ve firewalld servis tanımı bırakır, ama kuralı
açmaz. Ağ Doktoru çalıştırılacak komutu gösterir.

### 5.8 Okul ağı gerçekleri (R8 §1)

**Ağ yapısı.**
- İdari ağ ile tahta ağı ayrı VLAN'lardadır.
- Aktif cihazlar merkezden yönetilir; VLAN, ACL ve AP yalıtımı okulda değiştirilemez.
- Aynı VLAN içindeki trafik merkezi filtreye uğramaz.

**Tahtalardan erişim** iki bilinmeyene bağlıdır:
- VLAN'lar arasında yönlendirme var mı;
- tahta tarayıcısının proxy ayarı yerel IP isteğini proxy'ye gönderiyor mu.

Proxy istisnası BTR'nin yetkisindedir.

**Uygulama sırası.**
1. **S1 ağ keşfi** F0 ile aynı anda yapılır.
2. Erişim kapalıysa **S2 PYS talebi** OYS'nin dilekçe şablonundan elle, F0'da yazılır:
   "yerel ağ VLAN düzenlemesi — tek yön, TCP/8765". Portun gerekçesi yazılır.
3. **Yedek yollar yalnız sistem yöneticisinin uygun görüşüyle** kullanılır (KM-19):
   - **Tahta VLAN portuna bağlama.** Ağ Doktoru "bu bilgisayar öğrenci erişimli ağda"
     uyarısını gösterir.
   - **İkinci ağ kartı.** Ağ Doktoru IP yönlendirmenin kapalı olduğunu denetler
     (`Get-NetIPInterface` Forwarding / `IPEnableRouter`). Katalog yalnız seçilen
     arayüzlerde dinler.

**Öğrenci telefonları** v1 dışındadır (U2).

### 5.9 Ağ Doktoru ve BTR bilgi notu

Ağ Doktoru yalnız yönetici kipinde açılır.

**Gösterdikleri:**
- ağ kataloğu açık mı kapalı mı;
- port;
- aday IP'ler ve etkin arayüzler;
- güvenlik duvarı denetiminin beş maddesi;
- ağ profili;
- katalog URL'si ve QR kodu;
- son hata.

**"Dinleyici bu arayüzde ayakta" öz sınaması** yanında şu uyarıyla gösterilir:
"Güvenlik duvarını ya da VLAN'ı kanıtlamaz. Makinenin kendi IP'sine yapılan bağlantı
loopback'ten geçer. Başka bir bilgisayardan deneyin." Başka bilgisayar için hazır bir
`Test-NetConnection <IP> -Port 8765` komutu verilir (GA-5).

**Düğmeler:**
- Kuralı ekle/güncelle (UAC);
- Afişi bas;
- Yer imi dosyalarını üret;
- PYS talep metnini kopyala;
- **BTR bilgi notu** (E3).

**BTR bilgi notunun içeriği:**
- bilgisayarın demirbaş no'su;
- port ve portun gerekçesi;
- kuraldaki **gerçek** `remoteip` ve profil değerleri;
- neyin sunulduğu (salt okur katalog) ve neyin sunulmadığı;
- kişisel veri bulunmadığı;
- Yönerge atıfları: 5/11, 11/16, 11/22; 11/7'nin "aktif ağ cihazı" dediği notu;
- BTR ve müdür imza alanları.

Not okulda saklanır (U10). Yerel üretilen basılı bir belge olduğu için gerçek IP
bloklarını içerebilir.

### 5.10 Koruma testleri

| # | Test | Faz |
|---|---|---|
| 1 | Yönetim sunucusunu kuran çağrı `DEFAULT_HOST` dışında host kabul etmez. 0.0.0.0 yalnız `katalog_server.py`'de geçer | F0 |
| 2 | (a) `api/` altındaki her desen, converter'lar örnek değerle doldurularak katalog portunda 404 döner. (b) Katalog yol tablosu anlık görüntüyle karşılaştırılır. (c) `/` katalog şablonu imzasını döndürür, SPA catch-all bilinçli olarak test dışıdır | F0 |
| 3 | Katalog modülünün kaynak import taramasında `django.db`, ORM ve `apps.*.models` bulunmaz. Şablonlarda `{% url` ve `{% load` geçmez | F0 |
| 4 | Authorizer: görünüm üzerinden LIKE ve `count` geçer. `kutuphane_work`, `kutuphane_loan` ve `kutuphane_membership` doğrudan okunamaz. PRAGMA reddedilir. Görünümlerin okuduğu (tablo, sütun) kümesi anlık görüntüyle karşılaştırılır | F5 · **F6 ve F7'de yeniden koşar** |
| 5 | Katalog yanıtlarının alan listesi anlık görüntüyle karşılaştırılır. Sentetik bir üyenin adı, okul no'su ve kart no'su hiçbir katalog sayfasında geçmez | F5 · F6/F7'de yeniden |
| 6 | POST, PUT ve DELETE 405 döner. 1 KB'ı aşan gövde reddedilir. `sayfa` ve `id` doğrulanır | F5 |
| 7 | Eser adına `<script>` eklenir, çıktıda kaçırılmış olarak basılır | F5 |
| 8 | Görevli kipinde izin listesi dışındaki **bütün** `/api/` uçları 403 `kip_yetkisiz` döner (URL desenlerini dolaşan test). `override_reason` taşıyan ödünç 403 döner. Görevli yanıtlarının alan listesi anlık görüntüyle karşılaştırılır. `HEALTH_PATH` hiçbir durumda kesilmez | F1 iskelet, F6 dolu |
| 9 | Program kilitliyken (423) katalog 200 döner | F5 |
| 10 | Güvenlik duvarı kuralı yoksa ya da tutmuyorsa katalog 0.0.0.0'da dinlemez (denetim çıktısı taklit edilir) | F5 |
| 11 | Yumuşak silinmiş eser ya da nüsha aramada, dizinde ve sayaçlarda görünmez. `is_loanable` ile SQL türetimi eşleşir | F5 |
| 12 | Tek üyenin tekrarlanan ödünçleri bir eseri çok okunanlara sokmaz | F10 |
| 13 | Tepsi komutları `KipDurumu`'nu okur. Görevli kipinde ayar değiştiren komut reddedilir | F5 |
| 14 | Boşta dönüş: `X-KD-Etkinlik` başlığı olmayan periyodik istekler yönetici kipini canlı tutmaz. Mutlak süre dolunca parola istenir | F1 |
| 15 | Saha: yönetici olmayan hesapta kural denetimi çalışır · Chrome ve ETAP Chromium `http://<IP>:8765` adresini HTTPS'e zorlamadan açar · tahtadan erişim | F5 eki / F12 |
| 16 | Klavyesiz gezinme: yalnız bağlantılarla (A-Z dizin, konular) aramadan bir eserin sayfasına ulaşılır | F5 |
| 17 | Gün değişimi kapısı: program 3 gün kapanmadan açık kalır; her gün bir yedek alınır, IP denetlenir (saat taklidiyle) | F5 |
| 18 | Görevli kipinde parolasız `app/quit/` 403 döner, parolalı istek düzenli kapanışı başlatır | F5 |

---

## 6. Veri modeli

### 6.1 Okul çekirdeği (KS `apps/okul` — UYARLA)

| Model | Kütüphane için |
|---|---|
| `SchoolConfig` (pk=1) | + `kademe` · + `kisa_ad` · + `kutuphane_saatleri` · + `demirbas_no` + `demirbas_onayi` (§3) · + `bakanlik_sistemi_kullanimda` (§3) · zil, vardiya ve çizelge alanları alınmaz |
| `SchoolYear`, `SchoolTerm` | Aynen (KS'deki ad `SchoolTerm`) |
| `ClassSection` | Aynen |
| `Student` | Ad (şifreli) · **okul no (şifreli + kör indeks, U9)** · şube · durum ACTIVE/LEFT + **`left_at`**. `gender` alınmaz; `excel_ogrenci.py` ve `imports.py` buna göre uyarlanır (UY-2) |
| `Personnel` | Ad (şifreli), `is_active` (KS'de var) + **`left_at`** + **`member_kind`** (öğretmen / diğer personel). **Unvan ve branş alınmaz**: bir branşta çoğu zaman 1-3 öğretmen olduğundan düz branş, öğretmenin okuma geçmişini kişiye bağlar. `gender` ile aynı veri en aza indirme gerekçesi (V2-01). e-Okul personel aktarımı bu sütunları okumaz |
| `ImportRun` + e-Okul parser'ları | + öğrenci **ve personel** mutabakatı (§8.3) |
| `Holiday` (DD — UYARLA) | + tür **`SCHOOL_BREAK`**: ara tatil ve yarıyıl. DD bu günleri disiplin sürelerinde iş günü sayar; kütüphanede bunlar "öğrenciye kapalı gün"dür (UY-13, SU-6) · + `next_open_day()` · takvim ekranı · 2027 ve sonrası bayramlar için TAHMİNİ uyarısı |

*F1 eki (22.09.2026):* e-Okul personel aktarımı "Görevi" sütununu yalnız üye türü için
geçici okur, saklamaz; `Holiday.OTHER` ("İdari izin / diğer") dayanaksız program
kuralıyla her zaman kapalıdır; `Student` ve `Personnel` **ayrılış havuzu** alanlarını
(`leave_candidate_since`, `leave_candidate_run`) taşır ve ayrılış hiçbir kaydı silmez
(§14.1 F1 ekleri, 2, 3 ve 7).

**Unutma kancası** (KS'de öğrenci LEFT olunca hemen katı siler; burada uyarlanır):
- Açık ödünç, açık dosya ya da teslim varken kişi silinmez.
- Ayrılış yalnız üyeliği sonlandırır.
- ~~**Hiç üye olmamış** kişi ayrılınca ve açık yükümlülüğü yoksa hemen katı silinir.~~
  **F1 eki 7 (22.09.2026) ile kalktı: ayrılış hiçbir kaydı silmez** (ayrılanın iade
  etmediği kitap olabilir). Ayrılan kayıt saklama taramasına kalır; kullanıcının
  "Sil" eylemi eski kuralıyla sürer.
- Üyeler için §6.4'teki süreler geçerlidir (KM-4).
- **Ayrılış havuzu** (F1 eki 7): e-Okul aktarımı kimseyi ayırmaz; listede bulunmayan
  aktif kişi `leave_candidate_since` + `leave_candidate_run` ile havuzda bekler,
  durumu aktif kalır. Karar (ayrıldı / aktif kalsın / birleştir) yöneticinindir.

### 6.2 Kütüphane modelleri (OYS'den — UYARLA)

**Ortak değişiklikler:**
- `created_by` ve `by_user` düşer;
- `core.*` bağları `okul.*` olur;
- migration ağacı `0001`'den başlar.

| Model | Değişiklik |
|---|---|
| `LibraryPolicy` | **Ödünç süresi 15 gün ve sabittir**, ayar alanı yoktur (Md. 18: "on beş gündür", KM-17). OYS'nin 1-15 aralığı ve dönem sonu tavanı **alınmaz** · sayı sınırları: öğrenci 1-3, öğretmen 1-5, `max_loans_staff` 1-5 (varsayılan 3) · `staff_loans_enabled` açılırken **müdürlük kararının tarihi ve sayısı** zorunludur. Diğer personele ödünç Yönetmelikte ayrıca düzenlenmemiştir. 13/1 diğer personeli yalnız kullanıcı hizmetlerinden yararlananlar arasında sayar. Karar şartı ve sayı sınırı **programın ihtiyat kuralıdır** (AT-4) · `son_odunc_tarihi` (yıl sonu, §8.3) · `idle_minutes` (3) · `admin_max_minutes` (30) · `popular_min_members` (5) · saklama süreleri (§6.4) |
| `CommissionDecision` | Başkan ve katılımcılar **şifreli** · `DONATION_REVIEW` / `WEEDING` tür denetimi |
| `Acquisition` | `source_note` (bağışçı) **şifreli** · + **bağış ön kaydı** `DonationIntake`: nüsha açılmadan liste tutulur; karar girilince seçili kalemler tek işlemle kataloglanır, reddedilenler işaretlenir (SU-23) |
| `Work` | + `search_key`, `sort_key`, `author_sort_key`, `subject_sort_key` (T7) · + `isbn13` (normalize, ISBN-10 → 13, sağlama uyarısı) · + `section` → kontrollü **`Section`** listesi (ad, DOS aralığı, kısa tarif; Md. 4/1-a, 6/1) |
| `Copy` | **Tanımlayıcı tablosu** (SU-11, UY-22): `barcode` = 10 haneli kayıt no; `accession_no` aynı sayının tamsayı hâli, tek sayaçtan · `external_asset_ref` = TKYS sicil/kodu · **`old_register_no`** = kitaptaki eski damga/defter no (isteğe bağlı) · `status` + `IN_REPAIR` giriş/çıkış yolu + **`DELIVERED`** (U11) · + `label_verified_at` · `shelf_location` → `Section` |
| **Yeni** `Delivery` (U11) | Nüsha · alan (Personnel ya da ClassSection; teslim açıkken PROTECT, kapandıktan sonra saklama sonunda SET_NULL — §6.4) · teslim tarihi · beklenen dönüş · belge no · geri alma tarihi. Ödünç değildir, Md. 18 sayı sınırı uygulanmaz |
| `CopyCounter` | Yıl `localdate()` ile alınır (D6) |
| **Yeni** `IssuedCard` (V2-05) | Verilmiş **bütün** kart numaralarının kör indeksi. Kişisizdir ve kalıcıdır; üyelik katı silinse de kalır. Yeni kart numarası buna karşı çakışma denetiminden geçer. "Asla yeniden kullanılmaz" değişmezini bu tablo sağlar. `CardCounter` kalkar |
| `CatalogImportRun` | + `source` (excel / ai_json / disa_aktarim) · + `payload_sha256` |
| `LabelSheetTemplate` | + `kind` (sırt / barkod / kart) · kalibrasyon **şablon + yazıcı** çiftiyle saklanır |
| `Membership` | XOR `Student`/`Personnel` · **kart no şifreli + kör indeks** · + `requested_at` · + **`CardRevocation`** (iptal edilmiş kart kör indeksi) |
| `Loan` | + `override_reason`: **şifreli**, kapalı liste + açıklama, "sağlık/aile bilgisi yazılmaz" uyarısı · + `cardless` + gerekçe (U12) · `membership` SET_NULL |
| `LossDamageCase` | + DAMAGED akışı · bedel yalnız ortaöğretimde · `responsible_note` şifreli |
| `WeedingBatch`/`WeedingItem` | + kalem silme · + teklifi geri çekme · + **TMY yol eşlemesi** (§10-E7) · + 28/1 komisyon adları (şifreli) · + harcama yetkilisi onayı · `approved_by_name` şifreli |
| `AnnualLibraryReview` | E9 bölümleri (§10) |
| `RareWorksSubmission` | nadir nüsha denetimi + komisyon kararı bağı |
| `StockTake`/`StockTakeItem` | Başlangıçta **anlık görüntü** alınır · iki ayrı seçenek (§9-10): (1) **TMY 32/3 durdurması** (kurul talebi + harcama yetkilisi adı ve tarihi) yalnız edinim, kayıttan düşme, devir ve kayıp dosyası çözümünü kapsar; (2) **"sayım için hizmet arası"** yeni ödüncü durdurur ve okul kararıdır · seçilen kilitler APPROVED ya da iptale kadar sürer · onayda her MISSING kalem yeniden doğrulanır · iptal yolu · LOST nüsha uzlaştırma · ödünçteki nüsha için kurul seçimi (sayımdan önce toplansın mı, kayda göre mi alınsın) · `surplus_barcode` · kurul adları ve onaylayan şifreli |
| **Yeni** `KatalogAyari` (pk=1) | açık/kapalı, port, dinleme kipi, seçili IP, son afiş IP'si, uyku engelleme, vitrin, `/konular` açık mı. **Port ve IP'nin tek kaynağıdır** |
| **Yeni** `kd_katalog_populer` | (eser, pencere, sıra), eşikli, kapanmış pencereler dondurulmuş |
| **Yeni** `BelgeIzi` | Resmî belgenin kişisiz izi: tür, tarih/sayı, sha256. Anonimleştirmeden sonra yeniden basımda "Anonimleştirilmiş kopya — ıslak imzalı asıl nüsha okul arşivindedir" ibaresi (KM-12) |

### 6.3 Şifreleme kapsamı ve kuralları

**Şifreli alanlar (Fernet):**
- `Student` adı ve okul no'su (+ kör indeks);
- `Personnel` adı;
- `Membership.card_no` (+ kör indeks);
- `Loan.override_reason` ve kartsız ödünç gerekçesi;
- `LossDamageCase.responsible_note`;
- `CommissionDecision` başkan ve katılımcıları;
- `StockTake` kurul metni;
- ayıklama ve sayım onaylayan adları;
- 28/1 komisyon adları;
- `Acquisition.source_note`;
- `DonationIntake` bağışçı alanı.

**Açık kalanlar:**
- katalog alanları (T6);
- şube;
- üye türü (`member_kind`);
- barkod;
- tarihler.

Personelin unvanı ve branşı modelde yoktur (§6.1).

**Kör indeks** (T14):
- `HMAC-SHA256(HKDF(DEK, info="kd-kor-indeks"), normalize(değer))`.
- Kart okutma, e-Okul eşleştirmesi ve iptal kart denetimi tam eşleşmeyle bu indeksten
  yapılır.
- Okul no'ya göre sıralama Python'dadır.
- Anahtar DEK'ten türediği için parola değişimi indeksi bozmaz.

**Kurallar** (UY-1, UY-2, EK-2):
1. Sihirbazın **ilk adımı parola + kurtarma anahtarıdır**. Anahtar yazdırılır, USB'ye
   PDF olarak kaydedilir ya da elle yazılır; bir parçası geri yazdırılarak doğrulanır.
   Kural "basım zorunlu" değil, **"saklama zorunlu"**dur.
   *F1 eki (22.09.2026):* doğrulama sunucuya da işlenir (`guvenlik.json`'da damga) ve
   **kurulum damgasız tamamlanmaz**; anahtar ekranda değilken kâğıttaki anahtarı
   doğrulama ve anahtarı yenileme yolları vardır (§14.1 F1 ekleri, 8).
2. Parola kurulmadan kişi yazan bütün uçlar **409** döner: e-Okul aktarımı, kişi CRUD
   ve üyelik.
3. `EncryptedField.get_prep_value`, anahtar yokken boş olmayan değerde **hata
   yükseltir** (fail-closed). İstisna yalnız migrate ve test için açık bir bağlamdır.
4. `enable()` yalnız parmak izi boşken, kişi tabloları boşken çalışır.
5. `PRAGMA secure_delete=ON`.
6. **Parolasız dal sökülür** (F1 iş kalemi):
   - `disable`, `_run_decrypt_pass` ve `resume_pending`'in DECRYPTING dalı;
   - `plaintext_writes`;
   - `backup._write_plain`;
   - `backup_restore`'daki düz `SQLITE_MAGIC` dalı;
   - `restore.py` ve `live_restore`'daki düz dallar;
   - `security/disable/` ucu;
   - FE "Parolayı kaldır".

   İlk açılışta `yedekleme.json` yokken (kişi verisi de yokken) günlük yedek **atlanır**.
   Bu davranış testle sabitlenir.

### 6.4 Saklama ve anonimleştirme

| Veri | Kural | Varsayılan |
|---|---|---|
| Hiç üye olmamış ve ayrılmış kişi | **Ayrılışta SİLİNMEZ** (F1 eki 7): kayıt kalır; saklama taraması aday gösterir, yönetici onayıyla silinir | süre F11'de kararlaşır (TB16) |
| Sonlanmış üyeliğin ödünç ve dosya bağları | `terminated_at + N` sonunda `membership=NULL` + `anonymized_at`. `override_reason` ve gerekçe metinleri temizlenir | N = 2 yıl |
| Sonlanmış üyelik satırı + kişi kaydı | Açık yükümlülük yoksa aynı süre sonunda katı silinir | N = 2 yıl |
| **Aktif** üyenin iade edilmiş ödünçleri | Ders yılı sonu + M sonunda kişi bağı koparılır, `override_reason` temizlenir | M = 1 yıl (A3) |
| **Aktif** üyenin kapanmış kayıp/hasar dosyası | Kapanış + N sonunda kişi bağı ve `responsible_note` temizlenir | N = 2 yıl |
| `PRICE_RECORDED`'da bekleyen dosya | Yıllık hatırlatma listesine düşer, sessizce silinmez | — |
| Kapanmış teslim (U11) | Geri alma + N sonunda alan bağı koparılır (`Delivery.recipient` SET_NULL). E15 belgesi için `BelgeIzi` tutulur. Teslim açıkken alan kişi silinemez (PROTECT; açık yükümlülük sayılır) | N = 2 yıl |

**Çalışma biçimi.**
1. Gün değişimi kapısında aday tespiti yapılır ve pano kartı düşer.
2. Yönetici onayıyla geri dönüşsüz tetik çalışır.
3. Tetik öncesi `pre-anonim-<tarih>.kdbak` yedeği alınır. Bu yedek **rotasyona girer**
   (14 gün). Tetik öncesi yedek KS K14'te yok, bu projede eklendi (EK-18).
4. Onay beklemenin azami süresi **6 aydır**. Süre dolunca kapatılamayan bir uyarı çıkar.
   Süre, Silme Yönetmeliği'nin periyodik imha hükmü depoya alınınca ona göre ayarlanır.

**Yedeklerdeki kalıntı** (V2-02). Anonimleştirilen bağlar yedeklerde bir süre daha
bulunur:
- günlük ve `pre-anonim` yedeklerde en çok **14 gün**;
- `pre-migrate` yedeklerde **son 5 güncellemeye kadar**. KS bu yedekleri yaşa göre
  değil adede göre tutar. Onaylı anonimleştirme tetiği, tetik anından eski
  `pre-migrate` yedeklerini de siler;
- kullanıcının indirdiği şifreli yedekler ve dış kopyalar (USB) okulun elindedir. İmha
  kuralı kılavuzda yazılıdır.

Aydınlatma metni bu kapsamı aynen yazar.

---

## 7. Barkod, etiket, dolaşım masası

### 7.1 Barkod ve kart şeması

| | Biçim | Örnek |
|---|---|---|
| Nüsha | 10 hane: `YYYY` + 6 hane sıra | `2026000123` → basılı `2026-000123` |
| Üye kartı | 8 hane: `9` + 6 **rastgele** + 1 mod-10 sağlama | `94718263` |

- Uzunluk ve ön ek iki türü ayırır.
- Numaralar asla yeniden kullanılmaz.
- Okuyucu girdisi normalize edilir. Aynı yardımcı FE'de ve backend'de bulunur.
- **13 haneli 978/979 girdi**, yani kitabın ISBN barkodu, özel ileti verir: "Bu ISBN
  barkodu. Kitabın kütüphane etiketini okutun." Masadaki okuyucuda EAN/UPC sembolojisi
  kapatılabilir. ISBN okutarak hızlı kayıt yönetici ekranında yapılır (SU-3).

### 7.2 Etiketler

**Code128 hesabı** (düzeltildi; GA, UY-4, EK-27):
- 10 hane = başlangıç 11 + 5 × 11 + sağlama 11 + bitiş 13 = **90 modül**, sessiz
  bölgelerle 110.
- Modül genişliği yazıcı noktasına hizalanır: **X = 0,254 mm** (300 dpi'de 3 nokta,
  600 dpi'de 6). Bu da 22,9 mm, sessiz bölgelerle **27,9 mm** eder.
- Kart: 79 modül (sessiz bölgelerle 99).

**Etiket türleri.**

1. **Sırt etiketi.** Yer numarası alt alta 2-3 satır basılır: sınıflama / yazar kodu /
   cilt-nüsha. Kısa okul adı eklenir.
   - Tabaka S4'te sırt ölçümüne göre seçilir.
   - Sırtı dar kitaplarda etiket ön kapağa yapıştırılır. Koruyucu bant önerilir
     (SU-13).
2. **Barkod etiketi.** Code128-C, okunur metin, **yer numarası**, kısaltılmış eser adı,
   okul kısa adı.
   - **QR varsayılan olarak kapalıdır.** Varsayılan tabaka 38,1 × 21,2 mm (A4'te 65
     etiket, ör. Tanex TW-2065).
   - QR istenirse 48,5 × 25,4 ya da 52,5 × 29,7 mm şablonu kullanılır. S4'teki satın
     alma bu karardan **sonra** yapılır (SU-12).
   - QR içeriği URL değil, rakamdır.
3. **Üye kartı.** 85 × 54 mm, A4'e 10 kart.
   - Kartta: Code128 kart no, ad, üye türu, okul adı. **Sınıf yazmaz**: sınıf her yıl
     değişir ve gereksiz veridir (KM-24).
   - Şube bazında toplu basımda sınıf yalnız sıralama için kullanılır.

**Basım ve yapıştırma** (SU-9):
- **Basım sırası seçilebilir.** Varsayılan yer numarası sırasıdır; Excel satırı ya da
  barkod sırası da seçilebilir. Sırt ve barkod etiketleri **aynı sıra ve hücre
  düzeninde** basılır.
- Basım onayından sonra "basıldı" işaretlenir ve geri alınabilir (D10).
- **Etiket doğrulama okutması** yapıştırmadan sonra `label_verified_at` alanını yazar.
  Doğrulanmamış nüshalar raporlanır.

### 7.3 Dolaşım masası (durum tablosu)

| Durum | Girdi | Sonuç |
|---|---|---|
| Boş | kart | ÜYE bağlamı: ad + kalan hak (sınıf yok) |
| Boş | kitap | Açık ödünçteyse **iade**. Değilse durumuna göre ileti: "rafta — ödünç değil", "kayıp kaydında", "onarımda", "sınıf kitaplığında" |
| ÜYE | kitap | Ödünç verilebilirse ödünç. Değilse sebep (kişisel olmayan) |
| ÜYE | kitap başka üyede | "Bu kitap başka bir üyede. Önce iade alınsın mı?" (görevli: iade + uyarı) |
| ÜYE | 60 sn işlem yok · "Bitti" · başka kart | Bağlam kapanır |
| Her durum | iptal kart | "İptal edilmiş kart — kütüphane yöneticisine yönlendirin" |
| Her durum | tanınmayan / ISBN | Özel ileti (§7.1) |

**BarcodeInput** ortak bileşeni:
- kendiliğinden odaklanır;
- Enter ile gönderir;
- gönderim anında alanı temizler ve okumaları kuyruğa alır;
- sesli ve görsel geri bildirim verir;
- odak kaybında görünür uyarı verir (Windows bildirimi ya da güncelleme penceresi
  odağı çalabilir).

**Kamerayla okuma v1'de yoktur.**

---

## 8. İçe ve dışa aktarma

### 8.1 Excel ile katalog girişi (U6)

**Şablon ve sütun sözlüğü F1'de sabitlenir.** Sahadaki veri girişi programı beklemeden
Excel'le başlayabilir (SU-10).

**Sütunlar:**
- eser adı\*, yazar, çevirmen, yayınevi, baskı, yıl, ISBN, konu, sınıflama kodu, dil,
  tür;
- nüsha sayısı **ya da** "satır başına tek nüsha" kipi;
- bölüm/raf;
- **eski kayıt no** (isteğe bağlı);
- ciltli süreli yayın, danışma.

**Kurallar:**
- KS'nin TR sütun eşlemesiyle `.xlsx` ve `.xls` okunur.
- Önizleme, uygulamayla aynı kodu savepoint içinde koşturur (ADR-0034).
- Eşleşme kovaları: yeni / mevcut / şüpheli. Şüpheli satır tek tek karar ister.
- Aynı dosyanın ikinci kez uygulanması `payload_sha256` uyarısıyla engellenir. Satır
  başına en çok 50 nüsha açılır. `shelf_location` aktarılır (D5).
- Tür ya da konu **"ders kitabı"** ise danışma bayrağı varsayılan olarak açık gelir
  (Md. 14/1-a, 16/1-a). Önizlemede gösterilir (SU-24).
- Bölüm/raf değerleri kontrollü `Section` listesiyle eşleştirilir. Eşleşmeyen değer
  önizlemede sorulur.
- Uygulamadan sonra "bu partinin etiketlerini bas" kısayolu çıkar.

**Geriye dönük giriş yöntemleri** (kılavuzda iş sırasıyla anlatılır):

| Yöntem | Akış |
|---|---|
| **A. Önce liste** | Excel → içe aktar → yer numarası sırasında etiket bas → raf raf yapıştır → doğrulama okutması |
| **B. Önce etiket** (listesi olmayan okul) | Boş barkod aralığı ayrılır ve basılır → kitap elde, ISBN + etiket okutularak hızlı kayıt → sonradan künye tamamlanır |

**Geçiş dönemi kuralı.** Etiketsiz kitap masaya gelirse hızlı kayıt yapılır ve tek
etiket basılır ya da kitap kâğıt deftere geçer. Dönüşüm bitince kâğıt defter kapatılır.

**Bağış ön kaydı.** §6.2'deki `DonationIntake`: liste tutulur, komisyona sunulur,
karar gelince toplu kataloglanır.

### 8.2 AI köprüsü (isteğe bağlı)

- OYS JSON şeması (v1) ve komut korunur. Komuttaki "Dewey" ifadesi "sınıflama kodu
  (tahmini)" diye genelleştirilir.
- Arayüz notu şunu söyler:
  - liste kişisel veri içermemelidir;
  - listeyi dış hizmete kullanıcı taşır;
  - program hiçbir servise bağlanmaz;
  - bu adım Yönerge 11/23 ve 11/3-h/ı ile çatışabilir, asıl yol Excel'dir.
- Komuta **yalnız künye sütunları** girer. Demirbaş no, edinim ve bağışçı bilgisi
  girmez.
- ESTIMATED kodlar katalogda "tahmini" rozetiyle görünür.

### 8.3 Öğrenci ve personel; yıl akışları

**Kaynak.** e-Okul sınıf listesi (OOG01001R020) ve personel listesi (OOK01001R1). KS
hattı kullanılır, `gender` alınmaz.

**AKTARIM KİMSEYİ AYIRMAZ** (F1 eki 7, 22.09.2026): mutabakatta listede bulunmayan
aktif kişi **ayrılış havuzuna** girer, durumu aktif kalır; karar Kişiler → Ayrılış
Havuzu'nda verilir. Aşağıdaki kapsam kuralları "kimin havuza gireceğini" belirler.

**Öğrenci mutabakatı** (EK-21):
- Varsayılan olarak **yalnız dosyada bulunan şubelerle** karşılaştırılır.
- Bütün okulla karşılaştırma, ancak açık bir "bu dosya okulun tam listesidir"
  onayıyla yapılır; panel bütün şubeleri içeren tek dosyayı belirgin biçimde önerir.
- Önizleme şube bazında etkiyi ve "N öğrenci havuza eklenecek, M öğrenci havuzdan
  çıkacak" sayılarını gösterir.
- Tek şubelik dosya diğer şubeleri LEFT yapmaz — hiçbir dosya kimseyi LEFT yapmaz;
  bu testle sabitlenir.
- *F1 eki (22.09.2026):* havuza ekleme yalnız kanıtla; yeniden aktifleşme numara + ad
  eşleşmesiyle; şube şube yüklemenin bilinen sınırı, havuz sayesinde geri
  alınabilirdir (§14.1 F1 ekleri, 4 ve 7).

**Personel mutabakatı** (EK-20):
- Listede olmayan aktif personel havuza girer (eski "ayrıldı sayılsın mı?" seçimi
  ve `mark_left_ids` kalktı — F1 eki 7).
- Ada göre eşleşmeyen yeni satırda "olası aynı kişi" uyarısı çıkar. Birleştirme
  aracıyla üyelik ve ödünçler eski kayıttan taşınır (ör. soyadı değişimi);
  birleştirme ayrılış havuzundan da yapılır.

**Havuzda "ayrıldı" kararı verilenler:** durum LEFT olur, `left_at` yazılır, üyelik
sonlanır, açık ödünç ve teslimler ilişik listesine düşer; **kayıt silinmez**.

**Yıl sonu akışı (Mayıs-Haziran; SU-8, EK-22).** Mezunlar Haziran'da ayrılır; Eylül'de
kitap toplamak fiilen imkânsızdır.
1. `son_odunc_tarihi` politikası. Son sınıflar için daha erken bir tarih isteğe
   bağlıdır.
2. Son sınıflar önce gelecek biçimde "toplama" görünümü ve E4 pusulaları.
3. Son sınıflar ile nakil gidenler için açık ödünç ve teslim listesi.
4. Mezuniyetten önce ilişik listesi ve "İlişiği yoktur" belgeleri.

"İlişiği yoktur" belgesi karne ya da diplomanın ön koşulu diye sunulmaz; Yönetmelikte
buna dayanak yok, yalnız "iadesi sağlanır" hükmü var.

**Yıl başı akışı.** Yeni e-Okul listesi → mutabakat (nakil ve kaçırılanlar) → kapalı
günlerin (ara tatil, yarıyıl) girilmesi.

`year_rollover` **alınmaz**: sınıf atlama ve mezun pasifleştirme e-Okul aktarımı ve
mutabakatla karşılanır.

### 8.4 Dışa aktarım (U1)

- **Tek sürümlü şema** `docs/disa-aktarim.md`'de tanımlanır ve içe aktarımın üst
  kümesidir. Ek sütunlar: barkod, kayıt no, eski kayıt no, TKYS kodu, durum, edinim
  yöntemi ve tarihi, bütün bayraklar, çevirmen, baskı, bölüm.
- İçe aktarıcının **"dışa aktarım dosyası" kipi** barkodu ve kayıt no'yu korur,
  sayaçları ilerletir. **Gidiş-dönüş testi** bu kipte tanımlanır (EK-10).
- **Üye özeti = kişisiz sayılar:** türe ve şubeye göre üye sayısı.
- **Alfabetik katalog dökümü (E17):** yazar, eser adı ve konu eksenlerinde. Md. 11/1'in
  gereğidir ve denetimde kanıt olur.
- **Taşınır Kütüphane Defteri dökümü** (TMY 9/1-ç; ciltsiz süreli yayın girmez,
  10/1-a-4 ve 15/4) ve **Yönetim Hesabı Cetveli
  hazırlığı** (TMY 34/2-c, **34/3-a**).
- **Kişi dökümü** (KVKK md. 11): okul no ile üyelik, ödünç, dosya ve teslim kayıtları.
  Yalnız yönetici kipinde çalışır.

---

## 9. Dolaşım kuralları (testlerle sabitlenecek)

1. **Kim ödünç alabilir.**
   - Üye öğrenci ve öğretmen alabilir (Md. 16/1, 17/1).
   - Diğer personele ödünç Yönetmelikte ayrıca düzenlenmemiştir; 13/1 diğer personeli
     yalnız kullanıcı hizmetlerinden yararlananlar arasında sayar. Programda bu seçenek
     okul müdürlüğü kararıyla açılır; bu, programın kuralıdır. Sayı sınırı okulun
     takdiridir (`staff_loans_enabled`, `max_loans_staff`).
   - Veli alamaz.
2. **Üyelik isteğe bağlıdır** (Md. 17/1 "üye olmak isteyen"). Şube bazlı üyelik istek
   listesinden yapılır.
3. **Ödünç verilmeyenler** (Md. 16/1 a-c):
   - danışma kaynağı: ders kitabı, ansiklopedi, sözlük, atlas (Md. 14/1-a);
   - piyasada mevcudu olmayan eser;
   - süreli yayın.

   Tek türetim `is_loanable`'dır (§5.1).
4. **Süre ve sayı** (Md. 18):
   - "Bir kitabı ödünç alma süresi **on beş gündür**." Süre sabittir.
   - Bir defada öğrenciye en fazla 3, öğretmene en fazla 5 kitap verilir.
   - Sayı sınırları ve 3. maddedeki kaynaklar **hiçbir kipte** istisna almaz.
5. **İade tarihi.**
   - `bugün + 15` hesaplanır.
   - Kaydırma iki ayrı kuraldır, dayanakları farklıdır (AT-3):
     - **Hafta sonu, resmî ve dini tatil:** son gün bu günlere rastlarsa iade tarihi
       izleyen ilk iş gününe geçer. Yönetmelikte hüküm yoktur. TBK md. 93'teki genel
       ilkeye kıyasen, öğrencinin lehine bir uygulamadır; TBK md. 92-93 alıntısı
       docs/mevzuat'a alınır.
     - **Ara tatil ve yarıyıl:** bunlar kanunen tatil günü değildir; mesai sürer. Bu
       kaydırmanın **mevzuat dayanağı yoktur**. Okulun tercihidir: öğrenci okulda
       değilken sahte gecikme doğmasın diye iade tarihi dersin başladığı ilk güne kayar
       (UY-13, SU-6). Ayarla kapatılabilir.
   - Pusulada ve kılavuzda kaydırılmış tarih "Md. 18 gereği" diye sunulmaz.
   - İade tarihi dönem sonunu aşarsa ödünç anında **uyarı** verilir. Süre kısaltılmaz.
6. **Uzatma, ceza ve harç yoktur.** Gecikme engeli (`block_loan_if_overdue`) bir
   politika kuralıdır; istisnası yalnız yönetici kipinde ve gerekçeyle tanınır.
7. **Tek açık ödünç:** bir nüsha aynı anda yalnız bir açık ödünçte ya da teslimde
   olabilir.
8. **Ayrılış.**
   - Md. 16/3'ün amacına uygun olarak yerel kayıtta da üyelik sonlandırılır.
   - Açık ödünç ve teslim ilişik listesine düşer. Sonlanmış üye iade yapabilir.
   - "Bakanlık sistemi kullanımda" ayarı açıksa hatırlatma çıkar.
9. **Kayıp ve hasar** (Md. 19): bedel seçenekleri yalnız ortaöğretimde sunulur.
   Program tahsilat yapmaz. OKY 164/1-g bir disiplin konusudur; program disiplin
   sürecini başlatmaz.
10. **Sayım sırasında iki ayrı seçenek** (KM-5, SU-7, EK-11, AT-2). Sayım
    başlatılırken seçilir, tutanakta **ayrı satırlarda** görünür:
    - **TMY 32/3 durdurması (isteğe bağlı):** kurul talebi ile harcama yetkilisinin adı
      ve tarihi zorunludur. Kapsadığı işlemler: edinim ve yeni nüsha, kayıttan düşme,
      devir, kayıp dosyası çözümü. Bunlar TMY anlamında giriş ve çıkıştır.
    - **"Sayım için hizmet arası" (okul kararı):** yalnız yeni ödüncü durdurur. TMY'ye
      dayandırılmaz, çünkü ödünç ve iade TMY'de giriş-çıkış değildir (13/1, 23/4).
      32/3 durdurmayı ayrıca "hizmetin aksamaması kaydıyla" tanır. Dayanak olarak en
      fazla 32/3'ün ikinci cümlesi (kurulun önlem alma sorumluluğu) anılabilir.
    - **İade hiçbir zaman kilitlenmez** (Md. 23/1-c). Sayım sırasında iade edilen nüsha
      o turda "bulundu" sayılır.
    - Seçilen kilitler onaya ya da iptale kadar sürer. Onayda MISSING kalemler yeniden
      doğrulanır (D17).
11. **Toplu teslim (U11).**
    - Sınıf kitaplığına (şube) ya da öğretmene teslim **ödünç değildir**. Md. 18 sayı
      sınırı uygulanmaz.
    - Teslim listesi (E15) basılır. Geri alma toplu okutmayla yapılır.
    - Sayımdaki yeri (AT-1). Sayım kurulu teslimdeki nüshanın yerinde mi sayılacağını,
      kayda göre mi alınacağını seçer:
      - **Şube (sınıf kitaplığı) teslimi:** 32/5'in birinci cümlesine kıyasen ortak
        kullanım alanı gibi yerinde sayılır. Teslim listesi (E15) Dayanıklı Taşınırlar
        Listesi işlevini görür (23/6'ya kıyasen).
      - **Öğretmene teslim:** TKYS'de Taşınır Teslim Belgesi düzenlendiyse 32/5'in
        ikinci cümlesi uygulanır ("Kişilere Verilen Miktar"). Düzenlenmediyse 32/5'e
        kıyasen işlem yapılır (23/4).
    - Ağ kataloğu "Sınıf kitaplığında" gösterir.
12. **Kartsız ödünç (U12):** yalnız yönetici kipinde yapılır. Gerekçe zorunludur,
    kayıt işaretlidir.
13. **Pusula ve listeler.**
    - İade hatırlatma pusulası **tek kişiliktir**. Kesme çizgili sayfada her parça bir
      öğrenciye aittir ve katlanınca içerik görünmez.
    - Pusulayı kütüphane yöneticisi ya da sınıf rehber öğretmeni dağıtır. Sınıfta
      okunmaz, öğrenci görevliye dağıttırılmaz.
    - Toplu gecikme listesi yalnız yönetici kipinde açılır. Basılırsa "Kişisel veri
      içerir — asılmaz, çoğaltılmaz" dipnotu taşır (KM-10).
14. **Ödünç ≠ okuduğu kitap.** Öğrenci bazlı sayı öğretmene ya da e-Okul'a aktarılmaz.

---

## 10. Evrak kataloğu

Bütün PDF'ler KS'nin evrak şablon sistemi ve `shared/pdf.py` tek kapısı üzerinden
üretilir. KS'nin ölçülmüş tuzak listesine uyulur:
- `text-transform: uppercase` kullanılmaz;
- `{# #}` yorumu çok satırlı yazılmaz;
- sayfa bütçesi gerçek uzunlukta verilerle test edilir.

| # | Belge | Dayanak | Faz |
|---|---|---|---|
| E1 | Sırt etiketi · barkod etiketi · kalibrasyon sayfası | Md. 11 | F4 |
| E2 | Üye kartı (tekli + şube tabakası). Madde atfı basılırsa §3'teki konum kalıbı kullanılır | Md. 20 | F6 |
| E3 | Katalog afişi (dayanak yazılmaz) · **BTR bilgi notu** · PYS talep metni · yer imi dosyaları | Yönerge 5/11, 11/16, 11/22 (not ve talep için) | F5 |
| E4 | Tek kişilik iade pusulası · toplu gecikmiş listesi (dipnotlu) | Md. 18, 8/1-f | F6 |
| E5 | "Kütüphaneden ilişiği yoktur" belgesi (konum kalıbıyla) · ilişik listesi | Md. 16/3, 18 | F7 |
| E6 | Kayıp/hasar tutanağı | Md. 19 | F7 |
| E7 | Ayıklama: TMY yol eşlemesiyle belgeler (aşağıda) | Md. 12/1 · TMY 24/2, 27, 28, 31 | F8 |
| E8 | El yazması ve nadir eserler listesi (komisyon kararına bağlı) | Md. 12/2 | F8 |
| E9 | Yıl sonu kütüphane raporu, "Okul Müdürlüğüne", tarih/sayı, imza · bölümler: tespitler (+ onarım, hasar, kayıp sayıları), yıl içinde kazandırılanlar (yönteme göre), ayıklanan ve devredilen, koleksiyon özeti, kişisiz ödünç istatistiği · kişisel veri yok (test) | Md. 12/1, Kılavuz 2.4 | F8 |
| E10 | Sayım tutanağı + XLSX. **Ödünç alanın kimliği basılmaz**, çünkü fazla/noksan sayfaları VİF'e bağlanıp muhasebe birimine gider (10/1-g, 32/8) · TMY 32/3 durdurma kararı ve "hizmet arası" okul kararı **ayrı satırlarda** · noksan düşüm teklifi (**32/7**) · ödünçteki nüsha "32/5'e kıyasen; 23/4" · Taşınır Sayım ve Döküm Cetveli (32/9) kararı A8 | TMY 32 | F9 |
| E11 | Taşınır Kütüphane Defteri dökümü: **ciltsiz süreli yayın girmez** (TMY 10/1-a-4, 15/4; F10 testi) · Yönetim Hesabı Cetveli hazırlığı. Not: "Sayım kurulunca onaylanan Taşınır Sayım ve Döküm Cetveline dayanır; resmî cetveller TKYS'dedir" | TMY 9/1-ç, 10/1, 15/4, 34/2-c, 34/3-a | F10 |
| E12 | "Ayın Kitapları" afişi: eser bazlı, eşikli, sayısız | Md. 15/1-ğ; Kılavuz 6.2 | F10 |
| E13 | Kütüphane aydınlatma metni (§3 asgari içerik) | KVKK md. 10 | F6 (duyuru F1'den önce, S7) |
| E14 | Kurtarma anahtarı çıktısı (yazdır / PDF / elle; doğrulamalı) | — | F1 |
| E15 | **Teslim listesi** (şube ya da öğretmen) + geri alma dökümü. Şube tesliminde Dayanıklı Taşınırlar Listesi işlevini görür | U11; TMY 32/5 ve 23/6'ya kıyasen, 23/4 (§9-11) | F7 |
| E16 | Bağış ön kayıt listesi (komisyona sunulur) | Md. 10/3 | F8 |
| E17 | Alfabetik katalog dökümü (yazar / eser / konu) | Md. 8/1-a, 11/1 | F10 |
| E18 | Görev devri notu | — | F11 |
| E19 | **Masa kartı**: görevli öğrenci için tek sayfa kullanım ve gizlilik uyarısı | KVKK 12/1 | F6 |
| E20 | Okuma ödülü **iç çıktısı**: yalnız yönetici kipinde, "iç kullanım" ibareli, ağa, panoya ve E9'a girmez (profil yasağı testine bağlı) | Kılavuz 7 (öneri) | F10 |

**E7 — ayıklama gerekçesinden TMY yoluna** (KM-15):

| Gerekçe (Md. 12/1) | TMY yolu | Belgeler |
|---|---|---|
| Yıpranma (WORN, 12/1-a) | 27/1 ya da ekonomik ömrü bittiyse 28 | KDTOT (10/1-e: komisyon imzası + harcama yetkilisi onayı) + VİF · 27/3: harcama yetkilisinin kusur değerlendirmesi (olağan yıpranmada 5/8) |
| Bilimsel değer kaybı (OBSOLETE, 12/1-b) · 10. madde ölçütlerine aykırılık (CRITERIA_MISMATCH, 12/1-ç; **10/1-b hariç**, 10/1'in diğer bentleri ve 10/4) | 28 | Seçim ve Ayıklama Komisyonu bildirimi → 28/1 komisyonu değerlendirmesi → 28/3 tutanak → 28/4 onay → imha kararıysa **28/5 imha tutanağı** → 28/7 VİF eki. *Çıkarım:* 10/4'e aykırı kitap hiçbir kütüphanede bulundurulamaz, bu yüzden devredilmez |
| Düzeye uygunsuzluk (LEVEL_MISMATCH: 12/1-c ve **10/1-b** yaş/gelişim uyumsuzluğu) | **Devir zorunlu** (12/1): 24/2 (MEB okulları arası) ya da 31 (başka idare) | Devir listesi (PDF + XLSX) |

F8 kapısı bu eşlemeyi test eder: **10/1-b gerekçeli bir kalem 28 yoluna gidemez**.
Madde metinleri tam TMY'den doğrulanır (AT-5).

---

## 11. Bağımlılık kesim listesi

| # | Bağ | Karar | Karşılık |
|---|---|---|---|
| B1 | `permissions.py`, roller | KALDIR | Belirteç + iki kip (§4.4) |
| B2 | FE `useAuth`/`hasAnyRole` (11 sayfa), `RequireModule`, `module_flags` | KALDIR | `useKip()` + görevli gezinmesi |
| B3 | `core.*` string-FK + `get_model` | YERELLEŞTİR | `okul.*` doğrudan import |
| B4 | `denetim.log_audit` / `log_access` | KALDIR/UYARLA | `Loan.override_reason` (şifreli). Kip ve şifreleme hassas okumayı sınırlar |
| B5 | `bildirim` sinyalleri, SMS | KALDIR | Pano kartları + pusula |
| B6 | Celery beat | SADELEŞTİR | Gün değişimi kapısı (T9) + onaylı tetik |
| B7 | `student_status_changed` | UYARLA | İçe aktarım mutabakatı |
| B8 | Antet | UYARLA | KS `get_letterhead_identity` |
| B9 | `nobet` + `sosyal_etkinlikler` (kütüphane nöbeti) | ALMA | Görevli kipi |
| B10 | drf-spectacular | ALMA | T13 |
| B11 | Modül bayrağı | ALMA | Müstakil program |
| B12 | `StudentPhoto` | ALMA (A4) | — |
| B13 | `select_for_update` | SADELEŞTİR | Tek yazar + `IMMEDIATE` |
| B14 | OYS satır içi PDF'ler | UYARLA | KS evrak sistemi |

---

## 12. Çıkarım haritası

### AYNEN (yalnız kimlik sabitleri değişir)

- **KS desktop:** `session_guard`, `integrity`, `paths`, `logging_setup` (+ `cokme.log`),
  `backup_crypto`, `version`, `dialogs`, `django_bootstrap`, `errors` ve testleri.
- **KS packaging:** `dll_kapanisi`, linux hattı + `apt_dene`, `depo_sizintisi`,
  `veri_sizintisi` (+ `.kdbak`), fontconfig çift düzeltme, `build.ps1` · `scripts/gates.sh`
  · `.github/workflows/kapilar.yml` · `docker/`.
- **KS shared:** `pdf.py`, `exceptions.py`, `text.py`, `letterhead.py`, `models.py`.
- **KS okul:** `school_year`, `terms` (`SchoolTerm`), `sections`, `normalize.py`,
  `encrypted_backup`.
- **KS FE:** `ui/`, `lib/`, `hooks/`, `modules/guvenlik/SifreliYedekleme` · koruma
  testi `format.test.ts`.

### UYARLA (her satırda değişikliğin gerekçesi)

- **KS desktop:**
  - `main.py`: tepsi, katalog, gün değişimi, bayraklı açılışlar (§4.2)
  - `server.py`: yönetim örneğinde host sabiti
  - `katalog_server.py` + `katalog_kontrol.py`: yeni (§5)
  - `lock.py`: sinyal yardımcısı, Global mutex
  - `window.py`: gizli açılış, `closing` işleyicisi (§4.5)
  - `backup.py`: yalnız şifreli kip, `pre-anonim` rotasyonu, anonimleştirme tetiğinde
    eski `pre-migrate` silme (§6.3-6.4)
  - `restore.py`: tepsi iletisi, 2 kodu, düz dal sökümü (§6.3-6)
- **KS packaging:**
  - `.iss`: yönetici; güvenlik duvarı, otomatik başlatma ve kapatma olayı; güncelleme
    kipi
  - spec: segno, pystray, six
  - `giris.py`: `DESKTOP_RUNTIME_MODULES`
  - `paketleme.yml`: manifest
- **KS backend:**
  - `settings.py`: `ALLOWED_HOSTS` koşullu, `synchronous=FULL`, `secure_delete`,
    `KipMiddleware`, "ağ servisi sunmaz" docstring'inin ters çevrilmesi
  - `urls.py`
  - `crypto.py`: fail-closed yazma, kör indeks, `plaintext_writes` sökümü
  - `app_password`: `disable` sökümü, güvenlik dosyası kayıp kilidi, enable kapısı,
    görev devri
  - `lock_middleware`
  - `restart_gate`: ileti metni ("tepsiden Çık")
  - `backup_restore` ve `live_restore`: düz dal sökümü, katalog bakım kapısı
  - `okul/models.py`: okul no şifreli + kör indeks alanı; teklik kısıtı kör indekse,
    `ordering` Python'a taşınır; Holiday `SCHOOL_BREAK`; SchoolConfig ve Personnel
    alanları; `gender`, unvan ve branş düşer (V2-04)
  - `okul/selectors.py`: `find_student_by_number` ve okul no araması kör indeksle; okul
    no'ya göre sıralama Python'da
  - `okul/serializers.py`, `okul/views.py`: parola kurulmadan kişi yazan uçlarda 409
  - `persons.py`: unutma kancası
  - `imports.py`, `excel_ogrenci.py`, `eokul.py`: gender, mutabakat, personel
    birleştirme
  - `setup.py`: sihirbaz sırası, demirbaş
  - `updates.py`: manifest, izin listesi indir.okulapp.org
- **KS FE:**
  - `KurulumKapisi`, `GuvenlikKapisi`, `modules/kurulum`: parola ilk adım
  - `modules/guvenlik`: "Parolayı kaldır" ve `OgrenciFotograflari` çıkar, görev devri
    girer
  - `modules/okul`, `kisiler`, `ayarlar`
  - `modules/guncelleme` + `AppShell`: açılışta denetim yok
  - `modules/panel`: pano kartları
  - `modules/hakkinda`: konum notu
  - `modules/kilavuz`: kabuk KS, **içerik yeniden yazılır**
  - `App.test.tsx`: M3 token bütünlüğü kısmı korunur, KS gezinmesini sabitleyen kısım
    kütüphane gezinmesine göre yeniden yazılır
- **DD:** `working_days.py`, `calendar.py`: `SCHOOL_BREAK`, `next_open_day`.
- **OYS backend:**
  - `models.py` (§6.2)
  - `services.py` → alt modüller
  - `circulation.py`: kilit, gerekçe, teslim
  - `selectors.py`: TR katlama, `copy_count` annotate, `pending_clearances`, görevli
    serializer'ları
  - `serializers.py`, `views.py`, `urls.py`
  - `import_schema.py`: TR katlama, 50 nüsha sınırı, ciltli yayın, sınıflama ifadesi
  - `import_service.py` (§8.1)
  - `excel_template.py`: sütun sözlüğü
  - `label_service.py`: Code128, türler, sıra
  - `member_card.py`
  - `reports.py`: KS şablonlarına taşınır
  - `weeding.py`: D7, D15, TMY yolu, `approved_by_name`
  - `stocktake.py`: D1, D4, D16, D17, durdurma kararı, iptal, LOST uzlaştırma
  - `excel_exports.py`: SchoolYear kaynağı, D1
- **OYS FE:**
  - 13 sayfa: rol dalları düşer; sayfalama ve arama gecikmesi eklenir; `DataTable`
  - **dolaşım masası baştan** kurulur (§7.3)
  - `api.ts`

### ALMA

- **OYS:** `permissions.py`, `signals.py`, `tasks.py` (işlevleri gün değişimi kapısına
  taşınır), `admin.py`, `events.md`, migrations, `KutuphaneNobetPage` + nöbet ve kulüp
  bağımlılıkları, `@sentry/react`, JWT altyapısı.
- **KS:** `apps/dersler`, `apps/sinav`, `data/ders-cizelgeleri`, `StudentPhoto` +
  `OgrenciFotograflari`, `modules/bakim` (sınava özgü), zil/vardiya/zümre, `gender`,
  düz yedek dalı, `disable`.
- **DD:** disiplin app'i, imha aracı, veli alanları, `excel_veli.py`, `website/`,
  `pages.yml`, `year_rollover.py` (§8.3).

**F0 iş kalemi.** KS'den gelen "LAN/internet servisi sunmaz" ve "hiçbir port açılmaz"
ifadeleri ters çevrilir: `settings.py:3-7`, `server.py:8`, `docs/kurulum.md:83-84`,
`docker-compose.yml:4-5` (EK-4).

---

## 13. Devralınan kusurlar (taşırken düzeltilecek)

| # | Kusur | Düzeltme | Faz |
|---|---|---|---|
| D1 | TMY atıfları eski: 32/6 → **32/7**, 32/4 → 32/5, 10/1-m → **34/2-c + 34/3-a** | Tam metinden doğrulanır | F9, F10 |
| D2 | Türkçe arama ve eşleştirme bozuk | T7 | F2 |
| D3 | `IN_REPAIR` durumuna yol yok. `DAMAGED` açılamıyor | Akışlar yazılır | F7 |
| D4 | Sayım kilidi `report_lost` ve `resolve_case`'i kapsamıyor | Kilit seçildiyse bunlar da kapsanır | F9 |
| D5 | İçe aktarım: `shelf_location` kayboluyor, idempotency yok, önizleme uygulamayla eşleşmiyor | §8.1 | F3 |
| D6 | Yıl UTC'den alınıyor | `localdate()` | F2 |
| D7 | Karar türü denetlenmiyor | Tür denetimi | F2, F8 |
| D8 | Kartta okul adı boş, kartlar tekli basılıyor | §7.2 | F6 |
| D9 | Sayfalama yok, 26. ödünç iade edilemiyor | Sayfalama + barkodla iade | F2, F6 |
| D10 | "Basıldı" işareti PDF üretilince konuyor | Onaylı işaret | F4 |
| D11 | `.upper()` Türkçe değil, soyad sezgisi yanlış | `tr_upper` + yazar biçimi kuralı | F2 |
| D12 | İstisna gerekçesi boş kalabiliyor, sonlandırma nedeni doğrulanmıyor | Zorunlu alan + serializer | F6 |
| D13 | Anonimleştirme eksik (üyelik satırı, not metinleri) | §6.4 | F11 |
| D14 | Nadir eser denetimi ve komisyon bağı yok | §6.2 | F8 |
| D15 | Ayıklamada kalem silme ve teklif geri çekme yok | §6.2 | F8 |
| D16 | Sayım fazlası eski barkodu raf alanına yazıyor | `surplus_barcode` | F9 |
| D17 | Sayımda COMPLETED ile APPROVED arasında kilit boşluğu var (EK-12) | Kilit onaya kadar + onayda yeniden doğrulama | F9 |
| D18 | TMY 32/3 zorunlu bir kilit gibi okunmuş, iade de kilitleniyor | §9-10 | F9 |
| D19 | Ödünç süresi 1-15 arası ayarlanabilir; Md. 18 süreyi sabit koyuyor | 15 gün sabit | F6 |
| D20 | Etiket kuyruğu barkod sırasında | Seçilebilir sıra | F4 |
| D21 | Kart no sıralı, tahmin edilebilir | Rastgele + sağlama | F6 |

---

## 14. Faz planı

### 14.1 Geliştirme fazları ve kapıları

**Kurallar.**
- Faz, **kod kapısı** geçilmeden kapanmaz. Sapmalar "F<n> eki (tarih)" satırıyla
  işlenir.
- **Okulun denetiminde olmayan saha kanıtları fazı kilitlemez.** Tahta erişimi S2'ye,
  gerçek okuyucu S4'e bağlıdır. Bunlar "F<n> eki" ile F12 saha kabulüne ertelenir
  (UY-14, EK-9).
- Her fazda iki ek iş kalemi vardır: **FE testleri** (kapsam eşiği 82/78/55) ve
  **kılavuz bölümü**.
- `bash scripts/gates.sh` her faz sonunda yeşil olmalıdır.
- **Yayın işleri** (etiket, push, R2 yüklemesi, site commit'i) dışa açıktır, **kullanıcı
  onaylı adımlardır**.

| Faz | İş | Kod kapısı |
|---|---|---|
| **F0 İskelet** | `git init` + CLAUDE.md + AGENTS.md + `docs/mevzuat/` (tam metinler) · KS'den türetme + KD sabitleri + "ağ servisi sunmaz" ifadelerinin ters çevrilmesi · segno dört halka (requirements → eşleme → spec → RUNTIME) + `barcode128.py` · pystray/six masaüstü zinciri · Inno yönetici · `synchronous=FULL` + **temiz kapanış işareti** (pano kartı F6'da) · kapilar.yml · **iki sunucu iskeleti** (katalog yalnız 127.0.0.1'de dinler) · **spike'lar**: Windows pystray iş parçacığı, Linux Qt ana iş parçacığı, `SO_EXCLUSIVEADDRUSE` + waitress `sockets=`, Inno `InitializeSetup`/`InitializeUninstall` kapatma olayı | exe açılır, tepsiye iner, Çık ile kapanır · çıkış kodları · `--pdf-duman`, `--bagimlilik-duman` · §5.10-1/2/3 · temiz kapanış işareti yazılır, zorla sonlandırmada eksik kalır · kimlik kalıntı taraması sıfır · gates yeşil |
| **F1 Çekirdek + güvenlik** | Sihirbaz: 1) parola + kurtarma anahtarı 2) okul, kademe, kısa ad, demirbaş onayı 3) ders yılı, dönem, kapalı günler → panoda "başlangıç yol haritası" kartı · parolasız dal sökümü · fail-closed yazma · kör indeks · güvenlik dosyası kayıp kilidi · Student/Personnel · e-Okul aktarımı + öğrenci/personel mutabakatı · Holiday `SCHOOL_BREAK` · `KipDurumu` + KipMiddleware + boşta/mutlak süre · Excel şablon sözlüğü | Parola yokken kişi yazan uç 409 · kilitliyken `Student.save()` hata verir · guvenlik.json silinince fail-closed · tek şubelik dosya diğerlerini LEFT yapmaz · §5.10-8 iskelet, §5.10-14 · kör indeks eşleşmesi · şifreli kipte ad selector'ları |
| **F2 Katalog** | Work/Copy/Acquisition/Section/Commission/Policy/sayaçlar · TR anahtarları ve üç eksenli alfabetik sıralama · ISBN · barkod · tanımlayıcı tablosu · bağış ön kaydı · D2, D6, D7, D11 · FE Katalog (DataTable, sayfalama, gecikmeli arama), Eser detay, Edinimler | TR arama ("şiir"/"ŞİİR", "ılık"/"ILIK", "İnce"/"ince") · üç eksenli TR sıralama · ISBN-10/13 · nüsha kuralları · barkod yeniden kullanılmaz |
| **F3 İçe aktarma** | Excel (şablon, eşleme, önizleme = uygulama, kovalar, idempotency, ders kitabı → danışma, bölüm eşleştirme) · AI JSON köprüsü · D5 | Önizleme ile uygulama aynı · ikinci uygulama engellenir · 5.000 satırlık sentetik dosya ölçülür |
| **F4 Etiketler** | Sırt, barkod ve kalibrasyon · Code128-C (X = 0,254 mm) · QR isteğe bağlı · basım sırası · doğrulama okutması · yöntem B (önce etiket + hızlı kayıt) · D10, D20 | Code128 test vektörleri · PDF'te modül genişliği toleransı · basım durumu geri alınabilir · *gerçek okuyucu: F4 eki → F12* |
| **F5 Ağ kataloğu + tepsi** | Katalog WSGI (görünümler + yaşam döngüsü, authorizer, şablonlar, tahta kipi, A-Z dizinler, vitrin) · soket + IP başına bağlantı sınırı · hız sınırı · CSP · IP adayları · Ağ Doktoru (beş madde denetimi, yer imi dosyaları, BTR notu, PYS metni) · güvenlik duvarı (Inno görevi + UAC + HKLM port) · tepsi kip matrisi · otomatik başlatma · **`kd-gunluk` + gün değişimi kapısı iskeleti** (son çalışma damgası, saatlik denetim, günlük yedek, IP denetimi; sonraki fazlar kendi işlerini buraya ekler) · uyku · ikinci açılış · görevli kipinde Çık (`app/quit/`) · geri yükleme bakım kapısı | §5.10-4…11, 13, 16, 17, 18 · **ikinci bilgisayardan** arama · 50 istemcili yük provası · yönetim arayüzü yük altında akıcı · geri yüklemede katalog durur ve yeniden açılışta kalkar · *tahta ve saha testleri (§5.10-15): F5 eki → F12* |
| **F6 Üyelik + dolaşım** | Membership (istek listesi) · kart şeması + kartı yenile · **dolaşım masası** (§7.3) · görevli ekranı · kartsız ödünç (yönetici) · iade tarihi (kapalı gün) · gecikme kartı + pusula · E2, E4, E13, E19 · D8, D9, D12, D19, D21 | §9-1…8, 12, 13 testleri · görevli kipinde yalnız izinliler (§5.10-8 dolu) · hızlı okutmada okuma kaybı yok · §5.10-4/5 yeniden koşar |
| **F7 Teslim, kayıp, ilişik, yıl akışları** | Toplu teslim (U11) + E15 · kayıp/hasar/onarım (D3) · ilişik + E5, E6 · yıl sonu ve yıl başı akışları | Md. 19 kademe kapısı · teslimde sayı sınırı yok, ödünçte var · yıl sonu akışı sentetik veriyle uçtan uca · §5.10-4/5 yeniden koşar |
| **F8 Komisyon + ayıklama** | Komisyon · ayıklama (D7, D15, TMY yolu) · devir · nadir eser (D14) · bağış kararı → toplu katalog · E7, E8, E9, E16 · A8 kararı | Nadir eser ayıklanamaz · devir yalnız düzeye uygunsuzlukla · TMY yol eşlemesi testi · E9'da kişisel veri yok |
| **F9 Sayım** | Anlık görüntü · iki ayrı seçenek: TMY 32/3 durdurması ve "hizmet arası" · iade her zaman açık · kuyruk · iptal · LOST uzlaştırma · teslimdeki nüsha için kurul seçimi · D1, D4, D16, D17, D18 · E10 | 32/3 durdurması açıkken edinim, kayıttan düşme, devir ve dosya çözümü kapalı, ödünç açık · hizmet arası açıkken yalnız yeni ödünç kapalı · iki seçenek tutanakta ayrı satırda · iade hiçbir durumda kapanmaz · onayda durumu değişen kalem düşülmez · tutanakta ödünç alan kimliği yok · 32/7 |
| **F10 Raporlar + dışa aktarım** | İstatistik (kişisiz, eşikli kırılımlar) · 10.000 eşiği (Md. 7) · çok okunanlar (k farklı üye; gün değişimi kapısına eklenir) + E12 · E11 (ciltsiz süreli yayın hariç), E17, E20 · dışa aktarım şeması + gidiş-dönüş · kişi dökümü · "Bakanlık sistemi kullanımda" hatırlatma ayarı | Gidiş-dönüş aynı kataloğu verir · §5.10-12 · profil yasağı testleri (§3) · ciltsiz süreli yayın E11'e girmez |
| **F11 Bakım** | Dış yedek hatırlatması · saklama/anonimleştirme (gün değişimi kapısına eklenir; azami gecikme, `pre-anonim` rotasyonu, tetikte eski `pre-migrate` silme, BelgeIzi, kapanmış teslim) · görev devri (E18) · güncelleme (manifest, düğmeyle) | Eski exe yeni DB'yi açmaz · anonimleştirme sonrası yeniden basımda ibare var · açık yükümlülük varken kişi silinmez · temiz makinede geri yükleme provası |
| **F12 Paketleme + saha kabulü** | Inno (yeni GUID, WebView2, iki mutex, kapatma olayı, güncelleme kipinde kural korunur) · `.deb` (ufw/firewalld) · `veri_sizintisi` ×2 · belgeler (kurulum, ağ kurulumu, yeni bilgisayara taşıma, kılavuz, masa kartı) · okulapp.org alanı (§17) · **ertelenen saha kapıları** | Temiz Windows 11'de uçtan uca: kurulum → sihirbaz → e-Okul → Excel katalog → etiket → dolaşım → ağdan arama → yedek/geri yükleme · Pardus'ta aynı zincir · tahtadan arama (S2'ye bağlı) · gerçek okuyucu |

**Sıralama gerekçesi.** Ağ kataloğu (F5) dolaşımdan önce gelir. Katalog girildiği anda
ağdan taranabilir ve en büyük belirsizlik erken sahaya çıkar. Dolaşım gelene kadar
nüshalar "Rafta" görünür.

**F1 ekleri (22.09.2026).** F1'de tasarımdan bilinçli sapmalar ve tasarımda yazmayan
kararlar. İlgili bölümlerde bu listeye gönderme vardır.

1. **§4.3, §4.4 — kayıp kilidi ve kip geçişi.** Güvenlik dosyası yalnız silinince değil,
   var olup kullanılamadığında da (boş, bozuk JSON, bölümleri eksik) "güvenlik dosyası
   kayıp" kilidine düşer; bu hâl parmak izinden bağımsızdır. Kilit açık değilken kip
   geçişi isteği 409 `kip_gecisi_gecersiz` alır. Kayıp ekranına üçüncü çıkış yolu
   eklendi: **"Güvenlik dosyasını sıfırla ve kuruluma dön"**. Yalnız dört koşul
   birlikteyken açıktır: dosya var ama kullanılamıyor, DB'de parmak izi boş, şifreli
   alan taşıyan bütün tablolar boş, yedek klasöründe (parola kurulurken alınan geçiş
   yedeği dışında) yedek yok. Bozuk dosya silinmez, `guvenlik-arsiv-*` olarak kenara
   alınır. Koşul dışında uç 409 döner.
2. **§6.1 — personel görev sütunu.** e-Okul personel listesindeki "Görevi/Unvan" sütunu
   yalnız `member_kind`'i (öğretmen / diğer personel) belirlemek için geçici okunur;
   hiçbir yerde saklanmaz (kayıt, `ImportRun.report`, günlük). Tanınmayan görev
   öğretmen sayılır ve önizlemede satır no ile "üye türünü denetleyin" uyarısı çıkar.
   Branş sütunu hiç okunmaz. Saklanan veri §6.1'deki gibidir.
3. **§6.1 Holiday — `OTHER` türü "İdari izin / diğer".** Her zaman kapalıdır ve iade
   tarihini kaydırır. Dayanağı TBK 93 değildir (idari izin kanunen tatil sayılmaz),
   programın kuralıdır: `docs/mevzuat/BENIOKU.md` §4'e işlendi, kılavuzda ayrı madde.
4. **§8.3 — öğrenci mutabakatının ayrıntıları.** Ayrılış yalnız kanıtla yapılır:
   okul numarası dosyada geçen öğrenci satırı atlansa da (ad boş, sınıf çözülemedi)
   ayrılmaz; numarası boş öğrenci satırı o şubede (sınıfı da boşsa hiçbir yerde)
   ayrılışı durdurur; hiç satır işlenemeyen dosya kimseyi ayırmaz. Ayrılmış kayıt aynı
   okul no **ve aynı ad-soyadla** dönerse yeniden aktifleşir; numara adı farklı birine
   verilmişse eski kayıt dokunulmadan kalır, yeni kayıt açılır (okul no yeniden
   kullanılabilir). Bilinen sınır: şube şube yüklemede başka şubeye geçmiş öğrenci
   ayrılacaklar listesine düşer (yeni şubesi o dosyada yoktur). Önizleme, onay metni
   ve kılavuz bunu söyler ve yıl başında bütün şubeleri içeren tek dosyayı önerir.
5. **§14.1 F1 — yol haritası işaretleri.** "Başlangıç Yol Haritası"nın kullanıcı
   işaretleri tarayıcı deposunda değil `SchoolConfig.yol_haritasi` JSON alanında durur
   (kişisel veri yok; pencere profili silinse de kaybolmaz).
6. **§14.1 F1 — okul bilgileri.** Okul adı, kademe, kısa ad ve demirbaş onayı yalnız
   `setup/complete/` anında değil, sonradan her kayıtta da zorunludur: Okul Bilgileri
   ekranından ya da API'den boşaltılamaz (gönderilmeyen alana dokunulmaz).
7. **§6.1, §6.4, §8.3 — AYRILIŞ HAVUZU (kullanıcı kararı 22.09.2026).** Kullanıcının
   sözleri: "ayrılanları doğrudan silme, bir havuza ekle, orada karar verilsin; çünkü
   ayrılanın iade etmediği kitap olabilir; kaydı silmeyelim, yalnız aktif öğrencilik
   durumu değişsin."
   - **e-Okul aktarımı hiç kimseyi ayırmaz ve hiç kimseyi silmez.** Kapsamdaki
     (varsayılan: dosyadaki şubeler; `full_list` onayında bütün okul) aktif
     öğrencilerden ve listede olmayan aktif personelden dosyada bulunmayanlar
     **ayrılış havuzuna** eklenir; durumları AKTİF kalır. "Ayrılış yalnız kanıtla"
     kuralları (atlanan satırın numarası, numarası boş satır, hiç satırı işlenemeyen
     dosya) havuza ekleme için aynen geçerlidir — **personelde de**, kimlik anahtarı
     ad-soyad olduğu için kapsam şube değil "hiç kimse"dir: ad-soyadı boş bir satır
     (kaymış sütun) ya da hiç satırı işlenemeyen bir dosya hiç kimseyi havuza eklemez
     (F1 ekleri 10). Dosyada bulunan kişi havuzdan
     kendiliğinden çıkar (şube değişimi dahil: 9/A dosyası havuza atar, 9/B dosyası
     çıkarır). Personel aktarımındaki `mark_left_ids` seçimi KALKTI.
   - **Ayrılış kaydı silmez** (öğrenci ve personel, üyelik ve yükümlülükten bağımsız):
     durum LEFT / `is_active=False`, `left_at`, havuzdan çıkış, ayrılış kancaları (F6:
     üyelik sonlanır). `persons.py`'deki "hiç üye olmamış ve yükümlülüksüz → katı
     silme" dalı kalktı. Kişinin elle **silinmesi** ("Sil" düğmesi) mevcut kuralıyla
     kalır (açık yükümlülükte ret; üye olmuşsa ayrılış yoluna yönlendirme; aksi hâlde
     katı silme).
   - **Model:** `Student` ve `Personnel` → `leave_candidate_since` (DateField) +
     `leave_candidate_run` (FK ImportRun, SET_NULL); DB kısıtı havuzdaki kişinin aktif
     olmasını zorlar (göç `0005_ayrilis_havuzu`).
   - **Uçlar:** `GET leave-pool/` (havuz listesi; `?summary=true` yalnız sayılar) ve
     `POST leave-pool/resolve/` (`{students:{leave,keep},personnel:{leave,keep}}`, tek
     işlem; biri havuzda değilse hiçbir karar uygulanmaz). Karar ucu kişi yazar
     (`RequiresAdminPassword`, 409); ikisi de görevli kipinde kapalıdır.
   - **Arayüz:** Kişiler → "Ayrılış Havuzu" sekmesi (öğrenci ve personel ayrı listeler,
     TR sıralı, sınıf süzgeci, tek tek/toplu karar; personelde "olası aynı kişi" ve
     havuzdan birleştirme), Genel Bakış'ta "N kişi ayrılış kararı bekliyor" kartı,
     aktarım panelinde tek dosya önerisi ve "N … havuza eklenecek, M … havuzdan
     çıkacak" özeti. Yıl sonu mezunları bu yolla toplu ayrılır.
   - **KVKK sonucu:** ayrılmış kişi kayıtları artık ayrılışta silinmez (§6.4 ilk satır);
     saklama taraması (F11) aday gösterir, yönetici onayıyla silinir — süre F11'de
     kararlaştırılır (teknik borç TB16). Aydınlatma metni (E13, F6) bunu söyler.
8. **§4.4, §6.3 — KURTARMA ANAHTARI: ÜÇ ÖNLEM BİRLİKTE (kullanıcı kararı 22.09.2026).**
   Gerekçe: sihirbazın ilk adımında anahtar ekrandayken boşta süre dolup görevli kipine
   inmek kullanıcıyı anahtar saklanmadan ekrandan atıyordu; anahtarı hiç saklayamamış
   bir okulun da elinde bir yol olmalı.
   - **Kurulum bitene kadar süreler kipi düşürmez.** `SchoolConfig.setup_completed`
     yanlışken `KipDurumu`'nun boşta/mutlak tembel dolumu uygulanmaz. DB'ye iki yerden
     bakılır: süre dolacağı anda (sıcak yol) ve kip özetinde (geri sayım gösterilecek
     mi). Soru tükenir: OLUMLU yanıt önbelleğe alınır (kurulum tek yönlüdür), yani
     kurulumu bitmiş bir programda ne sıcak yol ne 15 saniyede bir gelen kip özeti
     DB'ye gider (F1 ekleri 10). Kurulum sürüyorsa iki sayaç yeniden başlar.
     DB okunamazsa kurulum tamamlanmış sayılır (fail-closed). Elle
     "Görevli kipine geç" ve "Kilitle" çalışmaya devam eder; kip özeti kurulum sürerken
     kalan süreleri boş verir (üst çubukta geri sayım görünmez). `setup/complete/`
     başarılı olunca sayaçlar sıfırdan başlar. §5.10-14 testleri kurulumu tamamlanmış
     ortamda koşar; kurulum sırasındaki davranışın kendi testleri vardır.
   - **Kurulum, kurtarma anahtarı doğrulanmadan tamamlanmaz.** Doğrulama damgası
     `guvenlik.json`'un kurtarma bölümündedir (`kurtarma.dogrulandi`, ISO zaman damgası);
     sarmalla birlikte yaşar, yenilemede damgasız yazılır — DB migration'ı GEREKMEZ.
     `POST security/recovery-key/confirm/ {recovery_key}`: sihirbaz iki grubu istemcide
     denetledikten sonra bellekteki TAM anahtarı gönderir, sunucu `verify_recovery_key`
     kuralıyla (sarmal + bellekteki DEK'in parmak izi) doğrulayıp damgayı atomik yazar;
     yanlışta kademeli gecikme. `security/status/` ve `setup/status/`
     `recovery_key_confirmed` taşır; `setup/complete/` damgasızsa 400 `kurulum_eksik`
     ("kurtarma anahtarı doğrulanmadı"). Bu karardan önce tamamlanmış (damgasız)
     kurulumlar KİLİTLENMEZ: yol haritası ve Güvenlik ekranı uyarır, sihirbazın 1. adımı
     kâğıttaki anahtarı doğrulama yolunu sunar.
   - **"Kurtarma anahtarını yenile"** (F11 görev devrinin bu parçası F1'e çekildi):
     `POST security/recovery-key/renew/ {password}` — yalnız kilit açık + yönetici
     kipinde (görevli izin listesine girmez; kilitliyken 423, `LOCKED_DENIED_PATHS`;
     `confirm` de aynı listededir). Parola bellekteki anahtara karşı doğrulanır, aynı DEK
     yeni anahtar ve yeni tuzla sarmalanır; önceki `guvenlik.json` `guvenlik-arsiv-<damga>.json`
     olarak KOPYALANIR (silinmez; dosya hiçbir an yok olmaz), yeni durum atomik yazılır,
     damga YOKTUR. Anahtar yanıtla bir kez döner (`Cache-Control: no-store`,
     `sensitive_variables`, günlüğe düşmez). DEK değişmediği için kayıtlar, kör indeks,
     yedek anahtarı ve kilit açılışı (kip) etkilenmez.
   - **Eski yedekler (koddan doğrulandı, `backup_restore._candidate_states`).** Her yedek
     alındığı anın `guvenlik.json`'unu başlığında taşır: yenilemeden önceki yedek bu
     bilgisayarda (güncel dosya yerindeyken) yeni anahtarla ya da güncel parolayla,
     güvenlik dosyası yokken (başka bilgisayar, kayıp dosya) yalnız ESKİ anahtarla ya da
     o dönemin parolasıyla açılır; eski anahtarla geri yükleme güvenlik dosyasını da
     yedeğin dönemine döndürür. Arayüz, kılavuz ve `docs/kurulum.md` bunu ve "yenileme
     ele geçmiş anahtara karşı koruma değildir" sınırını söyler (DEK değişmez; arşiv
     dosyası ve eski yedekler eski anahtarla açılır). §4.4'teki görev devri satırı
     ("eski anahtar geçersiz olur") bu ayrıntıyla okunur.
9. **§18 sözlük — başlık düzeni, durum ekranı başlıkları ve belgenin dürüstlüğü
   (dalga 3 denetiminin son rötuşları, 22.09.2026).**
   - **Başlık Düzeni'nin kapsamı sözlük §3'te netleşti:** kullanıcıya yol tarif
     edilirken adı geçebilen her başlık (sayfa h1, sekme, sayfa içi bölüm ve kart
     başlığı) Başlık Düzenindedir; bir bölümün ya da kartın içinde metni parçalayan
     **alt başlıklar** cümle düzeninde kalır. Üç istisna: §2'deki belge adları başlık
     yerinde de kendi yazımıyla kalır ("Kurtarma anahtarı çıktısı"), program durumu
     ekranlarının başlıkları §4.2'deki cümlenin kendisidir, onay diyaloğunun başlığı
     sorudur. Ayarlar, Güvenlik, sihirbaz, Kişiler, Kapalı Günler ve yol haritası
     ekranlarındaki kart/bölüm başlıkları bu kurala getirildi; Güvenlik'in ilk kartı
     **durumla değişen** bir başlık yerine sabit "Yönetici Parolası ve Şifreleme" adını
     aldı (durum cümlesi başlığın altına indi), sihirbazın adım rayı ve kart başlıkları
     Başlık Düzenine geçti (sözlük §4.4, §4.6).
   - **Durum ekranlarının üst çubuk başlığı.** Kilitli, güvenlik dosyası kayıp ve
     "yeniden başlatın" ekranları bir adrese bağlı olmadığı için `AppShell` başlığı yol
     adından türetemiyordu. Ekran kendi h1'ini `ui/DurumBasligi` yığınına yazar, kabuk
     onu gösterir (sözlük §4: "h1 = üst çubuk"). Örtüşen ekranlarda en son açılan
     kazanır.
   - **"Yeniden başlatın" ekranının metni düzeltildi:** pencerenin çarpısı programı
     KAPATMAZ, tepsiye gizler (`desktop/window.py::on_closing`); ekran artık tepsideki
     simgeden "Çık"ı seçmeyi tarif eder.
   - **Kılavuzun çapaları gerçekten kaydırır.** SPA rota değişiminde tarayıcı adresteki
     `#` parçasını uygulamaz; `KilavuzPage` çapayı kendisi uygular ve yol haritasındaki
     BTR maddesi `/kilavuz#ag-katalogu` adresine bağlanır.
   - **`docs/kurulum.md` bugünkü sürümü anlatır.** Gün değişimi kapısı yoktur (günlük
     yedek yalnız AÇILIŞTA alınır — `desktop/main.py`, T9 iskeleti F5'te), görevli
     kipindeki parolalı Çık (`app/quit/`) F5'te, kütüphane aydınlatma metni (E13) F6'da
     gelecek: üçü de "sonraki sürümde" diye işaretlendi. Kılavuzun yedek bölümü de
     "yedek açılışa bağlıdır" uyarısını taşır.
10. **§8.3, §14.1 F1, §4.4 — dalga 3 denetiminin düzeltmeleri (22.09.2026).** Dördü de
    var olan kararların EKSİK UYGULANMASIYDI; karar değişmedi.
    - **Personel aktarımında "havuza ekleme yalnız kanıtla" kapısı yoktu.** Öğrenci
      yolundaki iki kapının (`_reconcile_students`) personel karşılığı yazılmamıştı:
      sütunları kaymış bir dosya BÜTÜN aktif personeli, üstelik tek uyarı bile üretmeden
      ayrılış havuzuna atıyordu. `_reconcile_personnel` eklendi: hiç satırı işlenemeyen
      dosya kimseyi eklemez (başlık satırına `leave_pool` alanlı uyarı) ve ad-soyadı boş
      bir satır görülen dosya eklemeyi tümüyle durdurur (satır no ile uyarı). Personelde
      kimlik anahtarı ad-soyaddır; öğrencideki "yalnız o şube" dalının karşılığı yoktur.
      Zaten havuzda bekleyen kişi kapıdan etkilenmez (kararı silinmez).
    - **Yol haritası kartı gizlenince kurtarma anahtarı uyarısı da kayboluyordu.**
      "Kurtarma anahtarı doğrulanmadı" uyarısı kartın İÇİNDEDİR ve kartı geri getirecek
      arayüz yolu yoktur (işaret kutuları ve gizleme düğmesi de kartın içinde). Var olan
      "eksik madde varken kart gizli kalmaz" kuralı damgaya da uygulandı: damga yokken
      `roadmap_state` `hidden: false` döner ve `set_roadmap_hidden` 400 ile reddeder.
      SAKLANAN tercih silinmez (yazma yolları saklanan durumu okur): damga gelince kart
      yine gizli açılır.
    - **Kip özeti her yoklamada `SchoolConfig` sorguluyordu.** Ön yüz `security/mode/`'u
      15 saniyede bir yokladığı için, cevabı kalıcı olarak "evet" olan bir sorgu günde
      binlerce kez ve modül tekilinin kilidi altında koşuyordu; modül başlığı ile
      `gorevli_mi()` docstring'i de "yalnız süre dolarken / DB'ye bakmaz" diyerek
      gerçeği söylemiyordu. Olumlu yanıt artık `_kurulum_tamam_mi` içinde önbelleğe
      alınır (kurulum tek yönlüdür; geri yükleme zaten yeniden başlatma kapısından
      geçer) ve docstring'ler gerçeğe getirildi.
    - **Ayrılış havuzunda sınıf süzgeci karardan sonra bayat kalıyordu.** 12/A'yı toplu
      ayırınca seçenek listeden düşüyor, süzgeç "12/A"da kalıyor, tablo boş görünüyor ve
      seçici eşleşen seçenek bulamadığı için "Tümü" yazıyordu. Liste yenilendiğinde
      süzgeç de listeyle eşitlenir.
    - Kayda geçen kalan riskler: **TB18** ("olası aynı kişi" adayı ad benzerliğiyle
      bulunur, adaşı eleyemez — kural soyadı değişimi için böyle seçildi) ve **TB19**
      (kurulum bitene kadar yönetici kipinin süreyle kapanmaması).
11. **§8.3, §4.4, §6.3 — TB18 ve TB19'un daraltılması (kullanıcı kararı 22.09.2026).**
    İki kalemin de KURALI aynen kaldı; eklenen, kullanıcının doğru kararı verebilmesi
    için gereken bilgi ve bir adım daha.
    - **TB18 — "olası aynı kişi" dürüst ve iki adımlı.** `name_match.match_reason`
      eşleşmenin gerekçesini de döndürür (`MatchReason`: `ayni_ad_soyad`,
      `ad_ayni_soyad_farkli`, `yazim_farki`); `probably_same_person` bu kuralın boolean
      sarmalıdır (davranış değişmedi). Gerekçe `selectors.SimilarCandidate` ile taşınır,
      `LeavePoolPersonnelSerializer` her adayda `reason`, `member_kind` ve `created_on`
      (adayın sicile eklendiği yerel gün) döndürür; aktarım önizlemesinin `SimilarPair`
      kaydı da `reason` taşır (kalıcı `ImportRun.report`'a girmez — ad listeleriyle
      birlikte düşer). Ekranlar "Neden aday: …" satırını yazar. Birleştirme onayı ikinci
      bir doğrulama ister: diyalog başlığı "Bu iki kayıt aynı kişi mi?", gövdede iki
      kaydın ayırt edici bilgisi ve "geri alınamaz" cümlesi; "Birleştir" düğmesi
      `ConfirmProvider`'ın yeni `acknowledgeLabel` kutusu ("Bu iki kaydın aynı kişi
      olduğunu doğruladım") işaretlenmeden açılmaz, kutu her açılışta boşalır. Kalan
      risk TB18'de daraltılmış olarak durur (program hâlâ iki adaşı ayırt edemez).
    - **TB19 — gözetimsiz ekranda anahtar gizlenir.** Kip askısı (yukarıda, madde 8)
      AYNEN korunur ve anahtar bellekte kalır; `KurtarmaAnahtariPaneli` 5 dakika hiç
      etkileşim olmazsa anahtarı ekranda gizler ("Anahtar güvenlik için gizlendi" +
      "Anahtarı göster"; göster sayacı sıfırlar). Gizliyken anahtar DOM'da değildir, bu
      yüzden yazdırma alanı da onu taşımaz; PDF yolu ve doğrulama akışı değişmez. Sayaç
      YALNIZ GÖRSELDİR ve istemcide durur: kipi düşürmez, sunucuya sorulmaz. Ölçü
      `lib/api.ts`in kip için zaten tuttuğu etkileşim saatinden okunur (yeni küresel
      dinleyici yok, panele ait olan yalnız yoklama zamanlayıcısıdır).

**F2 ekleri (23.09.2026).** F2'de tasarımdan bilinçli sapmalar ve tasarımda yazmayan
kararlar. Kod kapısı (§14.1 F2 satırı) ve `bash scripts/gates.sh` yeşildir.

1. **§4.4, §6.2 — `kip_sureleri()` HÂLÂ SABİT; iki alan bağlanmadı.** `LibraryPolicy`
   `idle_minutes` (3) ve `admin_max_minutes` (30) alanlarını taşır ve `library/policy/`
   ucu ikisini yazar, ama `apps/okul/kip.py::kip_sureleri()` hâlâ A10 varsayılanlarını
   döndürür. Bağlama yapılmadı çünkü sağlayıcı HER kip değerlendirmesinde çağrılır ve
   DB'ye bağlamak F1 ekleri 8/10'da bilinçle azaltılmış sıcak yol sorgularını geri
   getirir. Kullanıcıya "ayar var, etkisi yok" görünmesin diye iki alan **Kütüphane
   Politikası ekranına konmadı**. Karar (önbellekli okuma mı, F6'ya erteleme mi) açıktır;
   o güne dek geçerli olan A10 varsayılanlarıdır ve `kip.py` docstring'i "F6'da
   bağlanacak" der.
2. **§6.2 — nüsha süzgeçlerinde "danışma" ayrı bir eksen DEĞİL.** Sunucudaki süzgeç
   `only_loanable`'dır ve `LOANABLE_Q`'nun dört koşulunu birden uygular (danışma,
   piyasada mevcudu yok, süreli yayın, durum ≠ Rafta); arayüzde **"Yalnız ödünç
   verilebilenler"** olarak sunulur. Yalnız danışma kaynaklarını süzen bir eksen
   istenirse `selectors.copies()`'e ayrı parametre eklenmelidir.
3. **§6.2, D2 — arama TEK kutudur.** OYS'nin eksen bazlı parametreleri (`title`,
   `author`, `subject`, `isbn`) ALINMADI: KD'de arama `search_key` üzerindedir (T7) ve
   ham sütunda Türkçe arama zaten çalışmaz. Sorgu sözcüklere bölünür, hepsi birden
   aranır; ISBN yazımı ('978-605-…') rakamlarına indirilir. Sıralama ekseni ayrı
   parametredir (`?order=title|author|subject|newest`).
4. **§6.2 — Bölüm listesi BOŞ başlar.** Varsayılan DOS bölümleri tohumlanmaz; bölümler
   Ayarlar → Bölümler'den elle açılır. İlk açılışta katalogdaki "Bölüm" seçicileri
   boştur. Bir tohum listesi gerekiyorsa kararı F3 içe aktarımıyla birlikte verilir.
5. **§8.1 — `library/copies/bulk/` yanıtı `{count, results}`.** Liste uçlarının
   `{count, next, previous, results}` biçiminden FARKLIDIR: sayfalama değil, işlem
   sonucudur. Her nüsha ayrı numara alır; `count > 1` iken eski kayıt no dolu olamaz.
6. **§6.2 — bağış kararının gövdesi.** `donation-intakes/<pk>/decision/` içinde
   `rejected`, kalem kimliğinden ret gerekçesine bir EŞLEMEDİR (liste değil): liste aynı
   kalemi iki gerekçeyle göndermeye izin verirdi. Reddedilen her kalemde gerekçe
   zorunludur ve karar geri alınamaz.
7. **§18 sözlük — Genel Bakış'a Katalog kartı eklenmedi.** Sözlük §4.5 kart listesini
   sabitler ve `PanelPage` testi kartları sayar; Katalog'a yalnız kenar çubuğundan
   girilir. Kart istenirse sözlük §4.5 ile kılavuzun o cümlesi birlikte güncellenir.
8. **§18 sözlük — "Geçici olarak kullanım dışı"nın model karşılığı yok.** Nüsha durumları
   satırında geçen bu ifade `CopyStatus` değerlerinden hiçbirine denk düşmez ("Onarımda"
   ayrıca listededir); en yakın hâl `Copy.is_out_of_print` bayrağıdır ve gerekçesi
   "Piyasada mevcudu yok — ödünç verilmez." metnidir. İfade ya bir hâle bağlanmalı ya da
   sözlükten düşürülmelidir (F5 Ağ Kataloğu metinlerinden önce).
9. **§14.1 F3 uyarısı — toplu yazım anahtarları atlar.** `Work`'ün TR anahtarları ve
   `isbn13` `save()`'de türer; `bulk_create` kullanan bir içe aktarım yolu onları ELLE
   doldurmak zorundadır. `tests/test_tr_anahtarlari.py::test_anahtar_alanlari_toplu_yazimla_atlanmaz`
   kaynak ağacını AST ile tarar ve böyle bir yol eklenirse kırmızıya döner. Ayrıca
   `import_schema`'daki `shelf_location` anahtarı Excel SÜTUN adıdır; modeldeki karşılığı
   `Copy.section` FK'sidir, eşleme F3'ün işidir.

### 14.2 Saha hazırlık hattı (kod dışı — F0 ile başlar)

| # | İş | Kim |
|---|---|---|
| S1 | **Ağ keşfi:** kütüphane bilgisayarının VLAN'ı, tahtada `ip route`, tahta proxy ayarı, ağ profili, **Liderahenk ile dosya ya da politika gönderme yetkisi** | BTR + kullanıcı |
| S2 | Gerekirse **PYS talebi**: OYS dilekçe şablonundan elle, F0'da; port gerekçesiyle | BTR → müdür → PYS |
| S3 | **DHCP rezervasyonu** (MAC değişiminde yenilenir) | BTR |
| S4 | **Okuyucu** (USB 2D önerilir) + **etiket tabakası** (QR kararından sonra; 38,1 × 21,2 varsayılan) + sırt etiketi tabakası (sırt ölçümüyle) | Kullanıcı |
| S5 | İlçe MEM / DHGM'ye sorular: Bakanlık otomasyon sisteminin adresi, geçiş takvimi, aktarım biçimi; **Bakanlıkça belirlenen sınıflama sistemi**; Z-Kütüphane ile ilişkisi. Önce **DYS'deki resmî yazılar** taranır. e-Okul "Okuduğu Kitaplar" durumu | Kullanıcı |
| S6 | **BTR bilgi notu** (U10): BTR ve müdür imzası, okulda saklanır | Kullanıcı + BTR |
| S7 | Aydınlatma metninin **e-Okul aktarımından önce** duyurulması · görevli öğrencilerin müdürlükçe **yazılı görevlendirilmesi ve gizlilik bilgilendirmesi** · komisyon ve yönetim bilgilendirmesi | Kullanıcı |
| S8 | Kitap sayısı, mevcut listeler (Excel var mı, sütunlar) · kitaplarda **eski kayıt/demirbaş no** var mı · TKYS nüsha bazında mı | Kullanıcı |
| S9 | **Geriye dönük dönüşüm planı:** kim, hangi takvim (yarıyıl ya da yaz), raf sırası, etiket stoğu, doğrulama okutması | Kullanıcı + komisyon |
| S10 | **Kütüphane masası Windows hesabı** (yönetici yetkisi olmayan) + BitLocker | BTR |
| S11 | Yönetici parolasının **en az iki görevlendirilmiş kişide** olması · kurtarma anahtarının müdürlükte zarfta saklanması | Kullanıcı + müdür |
| S12 | Kütüphane bilgisayarının demirbaş kaydı | Kullanıcı |
| S13 | UPS önerisi (elektrik kesintisi) | Okul yönetimi |

---

## 15. Açık kararlar (varsayılanla ilerlenir)

| # | Konu | Varsayılan |
|---|---|---|
| A1 | Ağda iade tarihi | Gösterilmez (katalog `Loan`'a dokunmaz) |
| A2 | Diğer personele ödünç | Kapalı. Açmak için müdürlük kararının tarih ve sayısı gerekir |
| A3 | Aktif üyenin iade edilmiş ödünçleri | Ders yılı sonu + 1 yıl sonra kişi bağı koparılır |
| A4 | Kartta fotoğraf | Yok |
| A5 | Katalog portu | 8765 (gerekçesi BTR notunda) |
| A6 | Pardus | KS gibi `.deb` (bullseye tabanı, KS TB13 riski) |
| A7 | Kütüphane nöbeti | Alınmaz |
| A8 | Taşınır Sayım ve Döküm Cetveli (32/9) · bağış kabul tutanağı | F9'dan önce tam metinden karar |
| A9 | Depo | GitHub `aalidemirci/kutuphane-defteri` (herkese açık, kardeşler gibi). Yerel klasör `apps/kutuphane`. Açmadan önce keşif ve denetim belgeleri yayın denetiminden geçer |
| A10 | Kip süreleri | Boşta 3 dk, mutlak 30 dk |
| A11 | Gecikme listesi | Yalnız yönetici kipinde, dipnotlu |
| A12 | Çok okunanlar eşiği | En az 5 farklı üye (3-10 arası ayarlanır) |
| A13 | OYS'den veri aktarımı | Yok; Excel'le sıfırdan (U6/U7) |
| A14 | Ağdan sayım okutması | v1'de yok |
| A15 | Katalog veri kaynağı | Canlı DB + görünüm + authorizer. Ayrı anlık dosya reddedildi: eşitleme kodu ve Windows dosya değişimi sorunu, görünüm + authorizer + test üçlüsü yeterli |
| A16 | Ayırtma, kendi ödüncünü görme | Kapsam dışı (kimlik doğrulama ve TLS gerektirir; R9 §7) |
| A17 | Kilitliyken iade · ikinci parola yuvası | v1'de yok (bütünlük ve kriptografi bedeli) |
| A18 | `synchronous=FULL` maliyeti | F0'da ölçülür, teknik borca yazılır |
| A19 | Sınıflama | DOS fiilî standart, kod serbest alan (S5 cevabına kadar) |
| A20 | Barkod etiketinde QR | Kapalı |
| A21 | "Bakanlık sistemi kullanımda" ayarı | Kapalı; S5 cevabına göre açılır |
| A22 | Yerel kişisel ödünç kaydının kapatıldığı kip (§3 çıkış planı) | S5 cevabına kadar tasarlanmaz |
| A23 | Ara tatil ve yarıyılda iade tarihi kaydırması (§9-5) | Açık (okulun tercihi, mevzuat dayanağı yok), ayarla kapatılabilir |

---

## 16. Riskler

| # | Risk | Etki | Azaltma |
|---|---|---|---|
| 1 | Tahta VLAN erişimi okulun kontrolünde değil | Tahtalar aylarca bekleyebilir | S1/S2 erken yapılır · okul bilgisayarlarından erişim bağımsız · saha kapısı F12'ye ertelenir |
| 2 | Bakanlık sistemi zorunlu hâle gelir | Yerel ödünç çift iş olur | Çıkış planı (§3) · dışa aktarım · katalog/etiket/sayım/komisyon çıktılarının bağımsız değeri |
| 3 | **U10:** ilçe ya da Bakanlık, port açmayı Yönerge 11/22 kapsamında izne bağlı sayar | Ağ kataloğu kapatılır | Program ağ kataloğu olmadan tam çalışır · BTR notu ilçe yazısına ek olarak hazır |
| 4 | Tepsi + pywebview uyumu (özellikle Qt) | Açılış ya da kapanış sorunu | F0 spike'ı · Linux'ta küçültme yedeği |
| 5 | hiddenimports körlüğü (segno, pystray) | Paket sahada çöker | Dört halka + masaüstü zinciri + `--bagimlilik-duman` |
| 6 | Güvenlik duvarında kalıntı kural ya da üçüncü parti güvenlik duvarı | Katalog erişilmez | Beş madde denetimi · kurulumda temizlik · belge |
| 7 | Kip atlatma (yeni uç izin listesine yanlışlıkla girer) | Görevli kişisel veri görür | Fail-closed + URL ve parametre testleri |
| 8 | Masadaki öğrencinin Windows oturumu üzerinden dosyaya erişmesi | Okuma verisi sızar | U9 şifreleme + masa hesabı + BitLocker · kalan sızıntı belgelenir |
| 9 | Parola unutulması ya da görevden ayrılan kişi | Veri kaybı ya da yetkisiz erişim | Saklanan kurtarma anahtarı · iki parola sahibi · görev devri akışı |
| 10 | Geriye dönük giriş iş yükü, yanlış kitaba yapışan etiket | Aylar süren iş, bozuk kayıt | Yöntem A/B · basım sırası · doğrulama okutması · S9 |
| 11 | Türkçe arama kalitesi | Katalog kullanılmaz | T7 + F2 test seti |
| 12 | **Elektrik kesintisi** | Son işlemler kaybolur | `synchronous=FULL` · temiz kapanış işareti · UPS önerisi |
| 13 | **Tek disk, bilgisayar değişimi, yeniden kurulum** | Veri kaybı | Dış yedek hatırlatması · taşıma kontrol listesi · temiz makinede geri yükleme provası |
| 14 | **Her güncelleme yönetici (BTR) ister** (U4) | Güncelleme gecikir | Kurulum belgesi · güncelleme kipinde kural korunur |
| 15 | İmzasız exe + dinleyen port | SmartScreen ve antivirüs uyarısı | SHA256 belgesi · imzalama v2 işi |

---

## 17. okulapp.org yayını (ortak alan — bağlayıcı kurallar)

**İlk ekleme** tek seferlik bir commit'le yapılır (KS öncülü `44de4d2`). Eklenenler:

- `src/content/projects/kutuphane-defteri.md`
- `src/data/kd-release.json`
- `src/layouts/KDLayout.astro`
- `src/pages/kutuphane-defteri/{index,kilavuz,gizlilik}.astro`
- `public/kutuphane-defteri.png`
- `BaseLayout.astro` palet tipine `'kd'`
- `global.css` içinde üç palet bloğu
- sitenin CLAUDE.md alan sahipliği tablosuna satır, kardeş depo listesi ve commit öneki
  "Kütüphane Defteri: …"

**Uygulamanın okuduğu manifest** sitede değil R2'dedir:
`indir.okulapp.org/kutuphane-defteri/manifest.json`. İçinde sürüm, yayın tarihi, dosya
adları, boyutlar ve sha256 bulunur. Manifesti `paketleme.yml`'in yayın adımı üretir.
Secret'lar tanımlı değilse elle yükleme adımı yazılıdır (EK-6).

**Sonraki sürümlerde:**
- yalnız kendi alana yazılır;
- işe `git fetch` ve güncel `origin/main` ile başlanır;
- canlıya yalnız `main` push'u gider (`wrangler versions upload`, `deploy` yok).

**Gizlilik sayfası** ağ kataloğunu dürüstçe anlatır (§5.1).

**Ekran görüntüleri** yalnız sentetik veriyle alınır. Unvan, kurum adı ve IP blokları
yazılmaz.

**Kullanıcıya öneri** (dosyasına dokunulmaz): genel `~/.claude/CLAUDE.md` içindeki
"siteye yazan projeler" listesine kelebek-sinav ve kutuphane-defteri eklenmeli.

---

## 18. Depoya girecek belgeler

| Dosya | İçerik |
|---|---|
| `CLAUDE.md` | Altın kurallar: iki yüzey değişmezleri (§4.1), katalog alanları şifrelenmez, kör indeks, kip fail-closed, profil yasağı kuralları (§3), Md. 18 süre sabit, sayım durdurma isteğe bağlı, TR arama, tarih ve büyük harf tuzakları, dört halka + masaüstü bağımlılık zinciri · "bulgu DEĞİL" tablosu |
| `AGENTS.md` | CLAUDE.md'ye işaret |
| `docs/tasarim/2026-09-21-genel-tasarim.md` | Bu belge |
| `docs/kesif/2026-09-21-kesif-raporlari.md` · `2026-09-21-tasarim-denetimi.md` | Kanıt ve denetim |
| `docs/mevzuat/` | Tam metinler (§3) + atıf haritası |
| `docs/sozluk.md` | Kullanıcı sözlüğü: eser/nüsha, kayıt no, yer numarası, bölüm, üye, ödünç/iade, **teslim**, ilişik, ayıklama, kayıttan düşme, **Ağ Kataloğu** ("OPAC" kullanıcı metninde geçmez), görevli/yönetici kipi, kütüphane yöneticisi, **ödünç ≠ okuduğu kitap** |
| `docs/ag-kurulumu.md` | BTR kılavuzu: güvenlik duvarı, DHCP, proxy istisnası, tahta keşfi, PYS metni, yer imi politikaları, Pardus ufw, yedek yollar (uygun görüşle) |
| `docs/disa-aktarim.md` | Sürümlü şema |
| `docs/kurulum.md` | Kurulum (masa hesabı, UAC'de BTR kimliği), yeni bilgisayara taşıma, güncelleme, kaldırma |
| `docs/teknik-borc.md` | Kalan riskler (şube ve zaman damgası sızıntısı, slowloris, `synchronous` maliyeti) |
| Uygulama içi kılavuz | Faz faz: geriye dönük giriş (F3/F4), masa ve görevli (F6), yıl akışları ve teslim (F7), ayıklama (F8), sayım günü (F9) |
| Masa kartı (E19) | Görevli öğrenci için tek sayfa |

---

## 19. Denetim kaydı (21.09.2026)

v1 taslağı beş mercekten bağımsız eleştirildi: güvenlik/ağ, KVKK/mevzuat,
uygulanabilirlik, saha/UX, eksiklik. Her bulgu ayrı bir doğrulayıcıyla kaynağa karşı
sınandı. Sonuç: **124 bulgu, hiçbiri çürütülmedi.** Ayrıntı:
`docs/kesif/2026-09-21-tasarim-denetimi.md`.

**v2'ye işlenen başlıca düzeltmeler:**

- **Mevzuat okuması.**
  - "Bakanlıkça belirlenen" ifadesinin iki ayrı konusu ayrıldı (9/2 ile 8/1-a ve 11/1).
  - Md. 18'deki süre sabit (15 gün) kabul edildi.
  - TMY 32/3 isteğe bağlı durdurma olarak yazıldı; iade hiçbir zaman kilitlenmiyor.
  - Ödünç TMY'de giriş-çıkış değil (13/1, 23/4).
  - Ayıklama gerekçeleri TMY yollarına bağlandı (27/28/24/31).
  - Yönerge 11/7'nin lafzı ("aktif ağ cihazı") düzeltildi; 5/11, 11/16, 11/22,
    11/8 ve 11/23 eklendi.
  - Kılavuz ve TMY atıf hataları düzeltildi.
- **Güvenlik.**
  - Windows oturumu üzerinden dosya erişimi tehdit modeline girdi (U9).
  - `guvenlik.json` silinerek kilidin aşılması kapatıldı.
  - Authorizer eylem koduyla ve 5. argümanla yeniden tanımlandı.
  - Kart no rastgele yapıldı.
  - Boşta dönüş sunucuda tembel ve etkinlik başlıklı oldu.
  - Tepsi ve kanal için `KipDurumu`/`katalog_kontrol` getirildi.
  - Geri yükleme için bakım kapısı eklendi.
  - Güvenlik duvarı `remoteip` kapsamı daraltıldı; kural denetimi yapılandırılmış
    veriyle yapılıyor.
  - Öz sınamanın loopback olduğu yazıldı.
- **KVKK.**
  - Şifreleme kapsamı genişletildi (U9, T14).
  - Saklama tablosu tamamlandı.
  - Aydınlatma metninin içeriği tanımlandı.
  - Çok okunanlar k farklı üye eşiğine bağlandı.
  - Pusula ve gecikme listesi kuralları yazıldı.
  - Profil yasağı teste bağlandı.
  - Kartta sınıf kaldırıldı.
- **Uygulanabilirlik.**
  - §12 haritası dosya dosya düzeltildi.
  - Parolasız dal sökümü F1 iş kalemi oldu.
  - Görünüm yaşam döngüsü ve test veritabanı ele alındı.
  - Qt tepsisi ana iş parçacığına alındı.
  - pystray için ayrı zincir kuruldu.
  - Code128 hesabı düzeltildi, üreteç bağımlılıksız.
  - Ortam değişkeni listesi temizlendi.
- **Saha.**
  - Dolaşım masası durum tablosu yazıldı.
  - Kartsız ödünç (U12) ve kartı yenile akışı eklendi.
  - Toplu teslim (U11) v1'e alındı.
  - Geriye dönük giriş yöntemleri, basım sırası ve doğrulama okutması tanımlandı.
  - Bağış ön kaydı, "öğrenciye kapalı gün" kavramı ve yıl sonu akışı eklendi.
  - Gün değişimi kapısı, `synchronous=FULL` ve dış yedek hatırlatması getirildi.
  - Görev devri akışı ve masa kartı eklendi.
  - Saha kapıları fazları kilitlemiyor.

**v2 kontrol turu** (aynı gün, 2 bağımsız ajan): işleniş ve tutarlılık kontrolünden
13, atıf doğrulamadan 8 bulgu çıktı. Hepsi bu sürüme işlendi:
- personelin unvanı ve branşı alınmıyor;
- yedeklerdeki kalıntı süresi doğru yazıldı;
- gün değişimi kapısı F5'e alındı;
- §12'ye `okul/models.py` ve `selectors.py` eklendi;
- verilmiş kartlar için kalıcı `IssuedCard` tablosu kuruldu;
- `app/quit/` izin listesine girdi;
- TMY 32/3 durdurması ile "hizmet arası" ayrıldı;
- teslimin sayımdaki yeri kıyas diliyle yazıldı;
- iade tarihi kaydırmasının iki ayrı dayanağı yazıldı (TBK 93'e kıyas / okul tercihi);
- Md. 13/1 ifadesi düzeltildi;
- E7 eşlemesi düzeltildi (10/1-e, 10/1-b devri);
- E10 atfı (10/1-g) ve E11 süreli yayın kuralı eklendi;
- Yönerge 4/1-s tanımı ve 11/9 notu yazıldı;
- Inno'da tek kapatma yolu seçildi;
- bind/connect terimleri tutarlı hâle getirildi.
