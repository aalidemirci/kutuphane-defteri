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

### 2.1 Kullanıcı kararları (21.09.2026; U13 23.09.2026)

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
| U13 *(23.09.2026)* | ISBN ile künye getirme | **İki kaynak + iki yol, varsayılan KAPALI, F3 ile** | Kaynak sırası: önce Kültür ve Turizm Bakanlığı halk kütüphaneleri kataloğu, bulunamazsa Open Library. Çalışma yeri: hem program içinde (ayarla açılır) hem de internetsiz masa için "ISBN listesini dışa aktar → internetli cihazda doldur → geri aktar" dosya yolu. Zamanlama: F3 (§8.5, §14.1) |

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
| T11 *(v3: 23.09.2026)* | **Dış istek yalnız kullanıcının başlattığı iki kapıdan çıkar:** (1) **güncelleme denetimi** — "Denetle" düğmesiyle, indir.okulapp.org manifestinden; (2) **ISBN ile künye sorgusu** (U13, §8.5) — ayarla açılır, **varsayılan kapalıdır**, her sorguyu kullanıcı başlatır. Başka hiçbir dış bağlantı yoktur: **açılışta ağ yok, telemetri yok, kişisel veri çıkmaz** | MEB ağında GitHub engelli (R6 §4). KS'nin UpdateBanner'ı her açılışta dış istek atıyor (EK-5). U13'ten önce tek kapı vardı; künye sorgusu ikinci kapıyı açar, ama ilkenin özü (kullanıcı başlatır, açılışta ağ yok, dışarı kişisel veri çıkmaz) korunur. Cümlenin bütün kopyaları eşitlenir: CLAUDE.md §3, `docs/kurulum.md`, `HakkindaPage.tsx`, `denetimOlayi.ts`, §5.9 E3 |
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
| 5/8, 6/7 | Öğretmen, öğrenci ve veliye ait kişisel bilgilerin üçüncü kişilerle paylaşılması yasaktır. **Kişisel veri paylaşımı yasağını kuran hükümler bunlardır; 11/8 değildir** (11/8 kişisel bilişim kaynaklarıyla ilgilidir). ISBN künye sorgusunda (§8.5) dışarı yalnız normalize ISBN çıkar; kural koruma testiyle kilitlenir |
| 11/12, 11/19, 11/22 | *(U13 eki, 23.09.2026)* Künye sorgusunun **operasyonel** engeli: kategorisi olmayan adrese erişim izni verilmez, talep Yardım Masası'ndan açılır (11/12) · MEBNET'te SSL denetimli proxy ve MEB kök sertifikası vardır, istemci sistem sertifika deposunu ve sistem proxy'sini kullanmak zorundadır (11/19) · port önceliği 21/80/443'tedir, Bakanlık ucu 210 portundadır (11/22). Sınama S15'tedir |
| 11/18 | Kurum bilgisayarına cep telefonu, mobil modem ya da kişisel erişim noktası bağlanarak MEBNET dışı bağlantı alınamaz. §8.5'teki çevrimdışı yol bu yüzden **ayrı cihaz** demektir, aynı cihaza ikinci hat değil |

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

**ISBN künye getirme (U13, §8.5) bu metne satır EKLEMEZ:** dışarı yalnız esere ait
ISBN çıkar, gerçek kişiye ilişkin bir bilgi çıkmaz (md. 3/1-d), bu yüzden md. 10
yükümlülüğü doğmaz. Özelliği anlatan satırlar E3 BTR bilgi notuna (§5.9), Hakkında
sayfasına ve `docs/kurulum.md`'ye girer.

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
- **Ağ Kataloğu hiçbir dış bağlantı açmaz** (U13 eki, 23.09.2026). Katalog uygulaması
  ve şablonları dış istemci içermez: kaynak import taramasında `urllib.request`,
  `http.client`, `socket` ile giden bağlantı ve ISBN künye modülü bulunmaz. Program
  tek süreç olduğu için bu bir **kod yolu değişmezidir**; künye sorgusu yalnız
  yönetim yüzeyinden, kullanıcının eylemiyle çıkar (§8.5). Katalogtan gelen hiçbir
  istek dış ağa çıkmaz.
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
| Görevli, kart numaralarını sırayla yazarak üye adlarını çıkarır (GA-7) | Kart no: 6 rastgele hane + sağlama hanesi · art arda 5 geçersiz kart → yönetici parolası · son 10 dakikada 5 tanınmayan ya da iptal edilmiş kart → yönetici parolası; geçerli kart okutması bu sayıyı sıfırlamaz (§14.1 F6 ekleri 19) | Yavaş numaralandırma: pencere başına 4 deneme kilitsiz geçer; 1.000 üyeli okulda bir isabet için sürekli okutmayla onlarca saat gerekir |
| **Dış servisin yanıtı programın içine girer** (U13, §8.5): künye sorgusuna dönen eser adı, yazar ve yayınevi metni katalog alanlarına, oradan TR arama anahtarlarına ve WeasyPrint evrakına basılır | Yanıt **güvenilmeyen girdidir**: boyut ve uzunluk tavanı, denetim karakteri temizliği, **NFC normalleştirmesi**, kısa zaman aşımı, yönlendirme izlenmez · hiçbir alan kullanıcı onaylamadan yazılmaz (ön izleme + kaynak ve tarih etiketi) · yerel önbellek aynı ISBN'i ikinci kez sormaz | Bakanlık ucunda TLS yoktur; yol üzerindeki bir aktör künyeyi değiştirebilir. Onay ekranı son katmandır ve kullanıcının dikkatine dayanır (TB20). Özellik varsayılan kapalıdır |
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
| Etiket doğrulama okutması (`library-label-verify` POST; yanıtta yalnız barkod ve eser adı — §14.1 F4 ekleri 11) | Etiket basımı, basım işareti ve geri alma, doğrulanmamışlar listesi, boş barkod aralığı, şablon ve kalibrasyon |
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
  - Bağlayıcı **PySide6**'dır (LGPLv3), PyQt5 değil — 23.09.2026 yayın denetimi:
    PyQt5/PyQtWebEngine GPLv3'tür, GPLv3 dağıtılan bütüne ek kısıtlama konmasını
    yasaklar, ürünün lisansı (PolyForm Noncommercial) ise ticari kullanımı
    kısıtlar; ikisi aynı pakette dağıtılamaz. LGPLv3 yükümlülüğü (dinamik
    bağlama + kütüphanenin değiştirilebilmesi) onedir yapısıyla karşılanır;
    lisans metinlerinin pakete girmesi F12'dedir (`packaging/README.md`).
  - pywebview bağlayıcıya `qtpy` üzerinden ulaşır; seçim `QT_API` ile ilk
    `import qtpy`'den önce, `desktop/tray.py::load_qt` içinde sabitlenir. `qtpy`
    pywebview'ın Linux bağımlılığı değildir, ayrıca pinlenir.
  - **Sürüm tavanı 6.8.x:** PySide6 6.9.1+ `libQt6WebEngineCore`'da
    `gbm_bo_get_fd_for_plane` ister; sembol Mesa 21.1 ile geldi ve Pardus 21'in
    tabanındaki (bullseye, Mesa 20.3.5) libgbm1'de YOKTUR. Yükseltmeden önce
    sembol denetlenir.
  - Qt5'ten Qt6'ya geçişte `.deb` bağımlılıklarına `libxkbfile1`
    (libQt6WebEngineCore) ve `libxcb-cursor0` (xcb platform eklentisi) eklendi;
    ikisi de Debian 11/12 ana deposundadır.
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
- **programın giden bağlantıları** (U13 eki, 23.09.2026): dış istek yalnız
  kullanıcının başlattığı iki kapıdan çıkar — güncelleme denetimi ve, ayarla
  açıksa, ISBN künye sorgusu (§8.5). Açılışta ağ yok, telemetri yok, dışarı
  kişisel veri çıkmaz. Not, künye sorgusu **açıksa** hedef adresleri ve dışarı
  yalnız ISBN'in çıktığını yazar; kapalıysa "giden bağlantı yalnız güncelleme
  denetimidir" satırı basılır. BTR'nin okul ağından sınaması için hazır komutlar
  verilir (S15);
- Yönerge atıfları: 5/11, 11/16, 11/22; 11/7'nin "aktif ağ cihazı" dediği notu;
  künye sorgusu açıksa 11/12 (kategorisiz adrese erişim izni Yardım Masası'ndan
  istenir) ve 11/19 (MEB kök sertifikası ve SSL denetimli proxy);
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
| 19 | **ISBN künye sorgusu** (§8.5): (a) açılışta ve toplu içe aktarımda hiç dış istek çıkmaz; (b) kaynak ayarı kapalıyken hiç istek çıkmaz; (c) giden isteğin sorgu dizesi, gövdesi ve **bütün başlıkları** dolaşılır — normalize ISBN dışında hiçbir değer (kimlik, anahtar, çerez, okul adı, demirbaş no, kart no, barkod) geçmez; (d) yanıt NFC'ye normalleştirilir ve denetim karakterleri elenir, boyut tavanı aşılırsa yanıt düşürülür; (e) kullanıcı onaylamadan hiçbir alan yazılmaz | F3 |
| 20 | Ağ Kataloğu kaynak import taramasında giden bağlantı çağrısı ve künye modülü bulunmaz (§4.1 değişmezi) | F3 · F5'te yeniden |

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
| `Copy` | **Tanımlayıcı tablosu** (SU-11, UY-22): `barcode` = 10 haneli kayıt no; `accession_no` aynı sayının tamsayı hâli, tek sayaçtan · `external_asset_ref` = TKYS sicil/kodu — **hiçbir akışta zorunlu değildir**, arayüzde geri plandadır ve Excel şablonunda da zorunlu değildir; yardım metni "Okulunuz Taşınır Kayıt ve Yönetim Sistemi'nde (TKYS) nüsha bazında kayıt tutmuyorsa bu alanı boş bırakın" der (S8 cevabı, 23.09.2026: sahada nüsha bazında TKYS kaydı fiilen tutulmuyor) · **`old_register_no`** = kitaptaki eski damga/defter no (isteğe bağlı) · `status` + `IN_REPAIR` giriş/çıkış yolu + **`DELIVERED`** (U11) · + `label_verified_at` · `shelf_location` → `Section` |
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
| "Bedel belirlendi" ya da "Bedel teslim alındı"da (`PRICE_DETERMINED` / `PRICE_RECEIVED`) bekleyen dosya | Yıllık hatırlatma listesine düşer, sessizce silinmez (F7 ekleri 26: bedel iki adımdır) | — |
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
  kapatılabilir. ISBN okutarak hızlı kayıt yönetici ekranında yapılır (SU-3) ve künye
  önerisi §8.5'ten gelir.
- **Elle yazılan ISBN-10 tam ayrılamaz (TB22).** Okutulan ISBN barkodu 13 hanedir ve
  978/979 ile kesin ayrılır; ama kullanıcı künye sayfasındaki 10 haneli eski ISBN'i
  ELLE yazarsa ayrım yalnız yıl ön ekiyle yapılabilir (`SCAN_YEAR_MIN`…`SCAN_YEAR_MAX`
  = 2000-2999). İlk dört hanesi bu aralığa düşen ISBN-10'lar nüsha barkodu sanılır;
  `SCAN_YEAR_MAX` üst duvarı da bir varsayımdır. Kabul edilmiş kalan risktir: kapatmanın
  tek yolu U7 ve T8'deki salt rakam barkod şemasını değiştirmektir.

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
  Doğrulanmamış nüshalar raporlanır. Okutma görevli kipinde de açıktır; rapor yönetici
  kipindedir (§14.1 F4 ekleri 11).

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
  odağı çalabilir);
- bir pencere açıkken kuyruk bekler; odak yazı alanında değilse okuyucunun kodu
  tampona alınır ve pencere kapanınca işlenir (§14.1 F6 ekleri 22). Kart okutma
  kilidi (GA-7) pencere değil, kutunun üstünde bir şerittir: iade kilitlenmez
  (§14.1 F6 ekleri 21).

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
| **B. Önce etiket** — **okulun ASIL yolu** (S8 cevabı, 23.09.2026) | Boş barkod aralığı ayrılır ve basılır → kitap elde, ISBN + etiket okutularak hızlı kayıt → sonradan künye tamamlanır (§8.5 künye getirme bu adımı hızlandırır) |

**Yöntem B neden asıl yol** (S8 cevabı, 23.09.2026). Okulda hazır bir Excel listesi
**yoktur**; bu yüzden "önce liste" varsayımıyla planlanan sıra sahada karşılığı olmayan
bir varsayımdır. Sonuçları: F3'te **hızlı kayıt akışı** (ISBN okut → künye doldur →
barkod bas) Excel içe aktarımıyla **eşit önceliktedir**; F4 etiket basımı **kritik
yoldadır**, çünkü yöntem B etiketsiz başlayamaz. Excel yolu bırakılmaz: dışa aktarım,
bağış listeleri ve başka okulların hazır listeleri için gereklidir.

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
- *U13 eki (23.09.2026):* künye eksiğini kapatmak için **§8.5'teki ISBN yolu daha
  güvenlidir** ve kılavuzda önce o anlatılır: AI köprüsünde okulun **kitap listesi**
  dış hizmete çıkar (Yönerge 11/23 ve 11/3-h/ı tartışması buradan doğar), ISBN
  yolunda dışarı yalnız kitabın arka kapağındaki numara çıkar.

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

### 8.5 ISBN ile künye getirme (U13, F3)

Kitabın arka kapağındaki ISBN barkodu okutulur ya da numara elle yazılır; program eser
ekleme formuna künye **önerisi** doldurur. Okutulan kodun ISBN olduğunu ayırt eden yol
F2'de hazırdır (`apps/kutuphane/isbn.py`, `barcode.py::classify_scan`); F3'ün işi yalnız
"numaradan künye getirme" halkasıdır. Yöntem B'nin (§8.1) hızlı kayıt adımını hızlandırır.

**Kaynaklar ve sıra.** Önce Bakanlık kataloğu, bulunamazsa Open Library (U13). Ölçümler
23.09.2026 tarihlidir.

| Kaynak | Uç | Dönen alanlar | Ölçülen durum |
|---|---|---|---|
| **1. Kültür ve Turizm Bakanlığı halk kütüphaneleri kataloğu** (KYGM, Koha/Zebra) | SRU 1.1, düz HTTP, port 210: `koha.ekutuphane.gov.tr:210/biblios?version=1.1&operation=searchRetrieve&query=bath.isbn=<isbn13>&maximumRecords=5&recordSchema=marcxml` · kimlik ve anahtar **gerekmez** | MARCXML: 020 ISBN · 100 yazar · 245 eser adı, alt başlık ve sorumluluk (çevirmen/editör dâhil) · 260/264 yayın yeri, yayınevi, yıl · 300 sayfa ve boyut · 650 konu başlığı · 041 dil · 040 kataloglayan kurum · **082 Dewey** ve **090 yer numarası** | Türkçe karakterler **tam doğru** (UTF-8). 5 örnek ISBN'in 4'ü bulundu. Yanıt ~0,3 sn. **TLS yok.** **Mükerrer kayıt:** tek ISBN için 123 kayıt döndü. Yayımlanmış kullanım şartı, lisans ve atıf kuralı **yok** (TB20, S14) |
| **2. Open Library** (yedek) | HTTPS + JSON: `openlibrary.org/isbn/<isbn>.json` (302 ile `/books/OL…M.json`'a gider) · `openlibrary.org/search.json?q=isbn:<isbn>` · `openlibrary.org/api/volumes/brief/isbn/<isbn>.json` · **eski `/api/books` ucu ölü** (404) | title, publishers, number_of_pages, publish_date, isbn_10/13, language, author_name (search ucunda) · **Dewey/sınıflama yok** | Türkçe verisi **kusurlu ve ölçülmüştür:** harf düşmesi ("Yap Kredi Yaynlar", "Destek Yaynlar") · ham HTML varlığı (`Do&#x11F;an Kitap`) · **ayrışık (NFD) kod noktaları** ("İletişim") · **çevirmen yazar sayılmış** (Orhan Pamuk kitaplarına Kazak ve İspanyol çevirmenler yazar olarak eklenmiş) · Amazon kaynaklı **uydurma tarihler** ("13 Nisan", "28 Ekim") — kalemin kütükteki yeri **TB21**. Belgeli hız sınırı: tanıtılmamış istemci 1 istek/sn |

**Sert kurallar** (hepsi §5.10-19 ve §5.10-20 ile kilitlenir):

1. **Varsayılan KAPALI.** Ayarla açılır, yalnız yönetici kipinde. Kapalıyken hiç istek
   çıkmaz.
2. **Yalnız kullanıcının başlattığı tek istek.** Açılışta, arka planda ve **toplu içe
   aktarımda ASLA** istek atılmaz (Open Library'nin açıkça yasakladığı "yüzlerce tekil
   kitap isteği" tam olarak budur). Saniyede en çok bir istek.
3. **Dışarı yalnız normalize ISBN gider.** İstekte kimlik, anahtar, çerez, okul adı,
   demirbaş no, kart no, barkod, kitap listesi ve kullanıcı adı **bulunmaz**; sorgu
   dizesi, gövde ve başlıklar testle dolaşılır. Open Library'nin şartı gereği
   `User-Agent` yalnız program adını ve sürümü taşır.
4. **Yanıt güvenilmeyen girdidir** (§4.3): boyut ve alan uzunluğu tavanı, denetim
   karakteri temizliği, **NFC normalleştirmesi zorunludur** (ayrışık girdide
   `apps/okul/normalize.py` katlaması eşleşmiyor — ölçüldü; NFC olmadan kullanıcı kendi
   kataloğundaki kitabı bulamaz ve bu **sessizce** olur), HTML varlıklarının çözülmesi,
   kısa zaman aşımı. **Yönlendirme kendiliğinden izlenmez;** Open Library'nin `/isbn/`
   ucundaki 302 aynı host içinde ve en çok bir kez izlenir, başka hosta giden
   yönlendirme düşürülür.
5. **Kullanıcı onaylamadan hiçbir alana yazılmaz.** Alanlar ön izleme olarak dolar, her
   alanın yanında **kaynak ve tarih etiketi** durur ("Bakanlık kataloğu, 23.09.2026"),
   dolu alan sessizce üzerine yazılmaz. **Çevirmen alanı dışarıdan doldurulmaz**
   (kaynaklar çevirmeni yazardan ayırmıyor), kullanıcıya sorulur.
6. **Yerel önbellek:** aynı ISBN ikinci kez sorulmaz.
7. **TLS sistem sertifika deposundan doğrulanır ve sistem proxy'si kullanılır.** MEBNET'te
   SSL denetimli proxy vardır ve istemcilere MEB kök sertifikası kurulur (Yönerge 11/19,
   R8 §4); `certifi` ile çalışan bir istemci tam da hedeflenen ağda sessizce patlar.
8. **Ağ Kataloğu süreci hiçbir dış bağlantı açmaz** (§4.1 değişmezi).
9. **Fail-open.** Uç ölürse, yavaşsa, engelliyse ya da ağ kapalıysa program aksamaz:
   sessiz başarısızlık ve "İnternetten getirilemedi, elle girebilirsiniz" iletisi. Elle
   giriş ve Excel içe aktarımı her koşulda tam işlevlidir.
10. **Konum dili** (§3): arayüz "resmî künye" ya da "Bakanlık sisteminden geliyor"
    izlenimi vermez; künye "dış kaynaktan alındı, doğrulayın" rozetiyle gösterilir.

**Mükerrer kayıt kuralı.** Tek ISBN için yüzlerce kayıt dönebilir (ülkedeki her halk
kütüphanesi aynı kitabı ayrı kataloglamıştır; ölçülen en yüksek değer 123). Program
sessizce ilk kaydı almaz: **en zengin kayıt** seçilir (082 ve 090 taşıyan, 300 ve 650
dolu olan tercih edilir), kullanıcıya **kaç kayıt bulunduğu** söylenir ve gerekirse ilk
birkaç aday listelenip seçtirilir.

**Çevrimdışı yol** (kütüphane masasında internet yoksa; U13'ün ikinci yarısı). Künyesi
eksik eserlerin **ISBN listesi dışa aktarılır** → internetli **başka bir cihazda**
doldurulur → dosya geri aktarılır. Geri aktarım **ayrı bir künye tamamlama hattı**
kullanır (eşleşme ISBN üzerindendir; ön izleme + alan alan onay akışı ve dili katalog
içe aktarımıyla aynıdır). Dosya kişisel veri taşımaz.

*F3 eki (23.09.2026):* bu paragraf önce "F3'ün içe aktarma hattını kullanır" diyordu;
uygulama bilinçli olarak ayrıldı ve metin koda göre düzeltildi. Gerekçe: içe aktarma
hattı her satır için **nüsha açar**, oysa çevrimdışı dosya var olan eserlerin
künyesini tamamlar — aynı hattan geçseydi 500 satırlık bir künye dosyası 500 yeni
nüsha açardı. Dosyanın sayfa adı da bu yüzden "Katalog" değil "Künye"dir
(`import_schema.CATALOG_SHEET` yalnız "Katalog" sayfasını okur; ayrı ad kazayı baştan
keser). Kod: `apps/kutuphane/kunye/offline.py`, uçlar
`library/metadata/offline-export|offline-preview/`, ekran `CevrimdisiKunyePaneli`.
Kullanıcıya görünen iki ekranın dili ve onay akışı aynı kalır (sözlük). **Kurum bilgisayarına telefon, mobil modem ya da kişisel erişim noktası
bağlanarak internet alınamaz** (Yönerge 11/18): bu yol *ayrı cihaz* demektir, aynı
cihaza ikinci hat değil. Taşımada Yönerge 10/4-10/5'teki taşınabilir bellek kuralları
geçerlidir.

**Mevzuat durumu** (depodaki metinlerden doğrulandı).
- Yönerge **11/23** ("Bakanlığa ait … veri" dışarı aktarılmaz) ile **çatışmaz**: ISBN
  sorgusu dışarı veri çıkarmaz, veri getirir. §8.2 AI köprüsünden temel farkı budur.
- Yönerge **11/3-h** ("resmî işlemler dışındaki interaktif uygulamalara erişmek") ile
  **çatışmaz**: kataloglama, Yönetmelik md. 8/1-a ile kurulmuş resmî bir iştir.
- Yönerge **5/8** ve **6/7** kişisel veri paylaşımını yasaklar; "dışarı yalnız ISBN
  gider" kuralı testle kilitlendiği sürece devreye girmez. *(Bu yasak **11/8'de
  değildir**; 11/8 kişisel bilişim kaynaklarıyla ilgilidir ve bu belgede demirbaş
  bilgisayar bağlamında kullanılır.)*
- **KVKK:** dışarı çıkan ISBN esere aittir, gerçek kişiye değil (md. 3/1-d), bu yüzden
  kişisel veri işlenmez; md. 9 (yurt dışına aktarım) tetiklenmez ve md. 10 aydınlatma
  yükümlülüğü **doğmaz** — yükümlülük kişisel verinin elde edilmesine bağlıdır.
  **Bu yüzden aydınlatma metnine (E13) satır EKLENMEZ.** Gereken satırlar E3 BTR bilgi
  notuna (§5.9), Hakkında sayfasına ve `docs/kurulum.md`'ye girer.
- **Operasyonel engel hukuki değildir:** Yönerge **11/12** kategorisi olmayan adrese
  erişim izni verilmediğini söyler ve talebi `yardimmasasi.meb.gov.tr`'ye bağlar; karar
  okulun elinde değildir. Bakanlık ucu ayrıca standart dışı **210 portunda ve düz
  HTTP'de** çalışır; Yönerge 11/22 önceliği 21/80/443'e verir. İki adresin okul ağından
  erişilebilirliği **doğrulanmamıştır** ve BTR ile sınanır (S15).

**Lisans ve izin durumu — açık kalan risk.** Bakanlık ucunun yayımlanmış bir kullanım
şartı, API belgesi, lisansı ya da atıf kuralı **yoktur** (arandı, bulunamadı); aynı
sunucunun web yüzeyi WAF ile korunmakta, OAI-PMH ve OPAC kazımasına kapalıdır. Yani
açık port bilinçli bir hizmet olmayabilir ve her an kapanabilir. Buradan çıkan kural:
**tek tek sorgu ile okulun kendi kataloğunu doldurmak** ile **kayıtları toplu indirip
programla birlikte dağıtmak** hukuken aynı şey değildir; **ikincisi yapılmaz.** Yazılı
izin ve atıf koşulu kuruma sorulur (S14). Ayrıca kullanılmayacak kaynaklar: TO-KAT
(`robots.txt` = `Disallow: /`, tam yasak), Milli Kütüphane KAŞİF (yalnız POST +
`__VIEWSTATE`, kazımadan başka yol yok), Bakanlığın ISBN başvuru sistemi (e-Devlet T.C.
kimlik no + şifre ister; program kimlik bilgisi ne isteyebilir ne saklayabilir),
kitap perakendecileri (API yok, kullanım koşulları doğrulanamadı).

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
| D3 | `IN_REPAIR` durumuna yol yok. `DAMAGED` açılamıyor | Akışlar yazılır | F7 — kapandı (§14.1 F7 ekleri 3) |
| D4 | Sayım kilidi `report_lost` ve `resolve_case`'i kapsamıyor | Kilit seçildiyse bunlar da kapsanır | F9 |
| D5 | İçe aktarım: `shelf_location` kayboluyor, idempotency yok, önizleme uygulamayla eşleşmiyor | §8.1 | F3 |
| D6 | Yıl UTC'den alınıyor | `localdate()` | F2 |
| D7 | Karar türü denetlenmiyor | Tür denetimi | F2, F8 |
| D8 | Kartta okul adı boş, kartlar tekli basılıyor | §7.2 | F6 — kapandı (§14.1 F6 ekleri 12) |
| D9 | Sayfalama yok, 26. ödünç iade edilemiyor | Sayfalama + barkodla iade | F2, F6 — kapandı (§14.1 F6 ekleri 12) |
| D10 | "Basıldı" işareti PDF üretilince konuyor | Onaylı işaret | F4 |
| D11 | `.upper()` Türkçe değil, soyad sezgisi yanlış | `tr_upper` + yazar biçimi kuralı | F2 |
| D12 | İstisna gerekçesi boş kalabiliyor, sonlandırma nedeni doğrulanmıyor | Zorunlu alan + serializer | F6 — kapandı (§14.1 F6 ekleri 12) |
| D13 | Anonimleştirme eksik (üyelik satırı, not metinleri) | §6.4 | F11 |
| D14 | Nadir eser denetimi ve komisyon bağı yok | §6.2 | F8 |
| D15 | Ayıklamada kalem silme ve teklif geri çekme yok | §6.2 | F8 |
| D16 | Sayım fazlası eski barkodu raf alanına yazıyor | `surplus_barcode` | F9 |
| D17 | Sayımda COMPLETED ile APPROVED arasında kilit boşluğu var (EK-12) | Kilit onaya kadar + onayda yeniden doğrulama | F9 |
| D18 | TMY 32/3 zorunlu bir kilit gibi okunmuş, iade de kilitleniyor | §9-10 | F9 |
| D19 | Ödünç süresi 1-15 arası ayarlanabilir; Md. 18 süreyi sabit koyuyor | 15 gün sabit | F6 — kapandı (§14.1 F6 ekleri 12) |
| D20 | Etiket kuyruğu barkod sırasında | Seçilebilir sıra | F4 |
| D21 | Kart no sıralı, tahmin edilebilir | Rastgele + sağlama | F6 — kapandı (§14.1 F6 ekleri 12) |

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
| **F3 İçe aktarma** | Excel (şablon, eşleme, önizleme = uygulama, kovalar, idempotency, ders kitabı → danışma, bölüm eşleştirme) · **hızlı kayıt akışı (ISBN okut → künye doldur → barkod bas) — Excel ile EŞİT öncelikte** (S8) · **ISBN ile künye getirme (U13, §8.5): iki kaynak, varsayılan kapalı ayar, ön izleme + onay, kaynak/tarih etiketi, yerel önbellek, çevrimdışı dosya yolu (ISBN listesi dışa aktar → doldur → geri aktar)** · AI JSON köprüsü · D5 | Önizleme ile uygulama aynı · ikinci uygulama engellenir · **10.000 satırlık** sentetik dosya ölçülür · **katalog listesi, arama ve sayfalama 10.000 nüshada akıcı** · **açılışta ve toplu içe aktarımda dış istek YOK** (koruma testi) · **dışarı yalnız ISBN gider** (istek başlıklarını, sorgu dizesini ve gövdeyi dolaşan test) · **NFC koruma testi** · kaynak ayarı kapalıyken hiç istek çıkmaz · §5.10-19, §5.10-20 |
| **F4 Etiketler** | Sırt, barkod ve kalibrasyon · Code128-C (X = 0,254 mm) · QR isteğe bağlı · basım sırası · doğrulama okutması · **yöntem B (önce etiket + hızlı kayıt) — okulun ASIL yolu olduğu için F4 KRİTİK YOLDADIR** (S8): okulda hazır liste yok, dönüşüm etiketsiz başlayamaz · D10, D20 | Code128 test vektörleri · PDF'te modül genişliği toleransı · basım durumu geri alınabilir · boş barkod aralığı ayırma ve basma uçtan uca · *gerçek okuyucu: F4 eki → F12* |
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
   bağlanacak" der. *(F7'de bağlandı: önbellekli okuma; iki alan Kütüphane Politikası
   → Yönetici Kipi Süreleri'nde — F7 ekleri 10.)*
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
10. **§7.1 — F2 düzelticisinden devreden iki kalem kütüğe alındı (TB22).** Elle yazılan
    10 haneli ISBN-10'un (ilk dört hanesi 2000-2999'a düşenler) nüsha barkodundan
    ayrılamaması ve `SCAN_YEAR_MAX = 2999` üst duvarının varsayım oluşu **kapatılmadı**;
    ikisi de salt rakam barkod şemasının (U7, T8) doğrudan sonucudur ve kabul edilmiş
    kalan risktir. Kalem `docs/teknik-borc.md` TB22'dedir, `barcode.py::classify_scan`
    docstring'i oraya gönderme yapar.

**F3 ekleri (23.09.2026).** F3'te tasarımdan bilinçli sapmalar ve tasarımda yazmayan
kararlar.

1. **§8.5 — çevrimdışı künye yolu, F3'ün içe aktarma hattını KULLANMAZ.** §8.5'teki
   paragraf düzeltildi (gerekçe orada): içe aktarma hattı her satır için nüsha açar,
   çevrimdışı dosya ise var olan eserlerin künyesini tamamlar. Ayrı hat, ayrı uçlar
   (`library/metadata/offline-export|offline-preview/`), ayrı sayfa adı ("Künye"), ayrı
   ekran (`CevrimdisiKunyePaneli`) — ama kullanıcıya görünen dil ve onay akışı aynıdır.
2. **§8.1 — fikirdeşlik anahtarı BAYT değil İÇERİK özetidir.** `payload_sha256`,
   ayrıştırılmış satırların kanonik dökümünden hesaplanır
   (`import_service.content_hash`). Ham bayt özeti "aynı dosya" sorusuna değil "aynı
   dosya, aynı baytlarla" sorusuna cevap veriyordu: sahadaki olağan akış (önizle →
   Excel'de birkaç satırı düzelt → kaydet → yeniden uygula) ve tek boşluk farkı olan
   bir kopya engeli deliyordu.
3. **§14.1 F3 ölçüm kapısı artık otomatik koşabiliyor.** Ölçüm testi süreye ek olarak
   **tepe belleği** de raporlar ve kaba bir tavan uygular. `scripts/gates.sh`
   `KD_YAVAS=1` verildiğinde ölçüm kapısını da koşar; `.github/workflows/kapilar.yml`
   bu değişkeni gecelik koşuda (ve elle tetiklemede) verir. Varsayılan kapı koşusu
   değişmedi — her PR'da 10.000 kayıt yazmak zinciri gereksiz uzatırdı.
4. **§8.1 — aktarım kütüğüne (`CatalogImportRun.report`) ham hücre metni yazılmaz.**
   Kütük kalıcıdır ve koşu satırının silme ucu yoktur; sütunu kaymış bir okul
   listesinde ham "Eser Adı" hücresi bir kişi adı olabilir. Kütüğe satır numarası,
   kova ve sayılar girer; ham metin API yanıtında (geçici, ekranda) kalır.

**F4 ekleri (24.09.2026).** F4'te tasarımdan bilinçli sapmalar ve tasarımda yazmayan
kararlar. Kod kapısı (§14.1 F4 satırı) ve `bash scripts/gates.sh` yeşildir; gerçek
yazıcı ve gerçek okuyucu kanıtı F12'ye ertelendi (madde 9).

1. **§7.2, D10 — iki basım işareti.** `Copy.label_printed_at` yalnız **barkod
   etiketinin**, yeni `Copy.spine_label_printed_at` **sırt etiketinin** işaretidir.
   Kuyruk iki sayaçla çalışır ("Sırt etiketi bekleyen", "Barkod etiketi bekleyen").
   Tek işaret, "sırt ve barkod etiketi" ayrı ayrı basılabildiği için eksik kalan
   etiketi gizlerdi. Basım kaydı `LabelPrintBatch` + `LabelPrintBatchItem`'dır; kalem
   her nüshanın **basımdan önceki** damgalarını saklar. Kurallar:
   - Barkod etiketi içeren partinin onayı o nüshaların doğrulamasını sıfırlar (yeni
     etiket henüz okutulmamıştır).
   - Geri alma işareti silmez, basımdan önceki hâline döndürür. Barkodu okutularak
     doğrulanmış nüshanın işaretleri korunur (sırt ve barkod partisinde İKİSİ de —
     madde 11) ve sayısı yanıtta bildirilir. Yanıt kuyruğa DÖNEN nüshayı (`requeued`)
     işareti önceki basıma dönen nüshadan (`restored`) ayırır: yeniden basım partisi
     geri alınınca nüshalar kuyruğa girmez.
   - Nüshası sonradan başka partiyle yeniden basılmış bir parti, o parti hâlâ onaylıysa
     önce o parti geri alınmadan geri alınamaz. Sonraki parti geri alınmışsa engel
     kalkar; doğrulandığı için işareti o partide korunan nüshaya dokunulmaz (denetim,
     24.09.2026: önceden iki parti de bir daha geri alınamıyordu).
   - Parti açıldıktan sonra silinen ya da elden çıkan nüsha (`Copy.is_labelable`)
     partiden düşmez: partinin PDF'inde hücresi BOŞ kalır (sonraki etiketler kaymaz),
     onay onun işaretine dokunmaz, yeniden basım onu almaz (kalanların sırası korunur).
   - Yeniden basım aynı nüshaları aynı sırayla yeni bir partide basar
     (`reprint_of`). Şablon değişirse eski kalibrasyon taşınmaz. Gövdede
     `calibration: null` açıkça "kalibrasyonsuz" demektir; alan hiç gönderilmezse
     aynı şablonun kalibrasyonu taşınır.
   - Doğrulanmış nüshada sırt işaretinin korunup korunmayacağı açık karardı;
     kullanıcı 24.09.2026'da karar verdi: ikisi de korunur (madde 11).
2. **§7.2 — uçların yeri ve ekran.** Şablon ve kalibrasyon uçları motor
   paketindedir (`apps/kutuphane/labels/urls.py`): `library/label-templates/`,
   `library/label-calibrations/`, kalibrasyon sayfası `library/labels/calibration/`
   ve **hiçbir kayıt yazmayan** önizleme `library/labels/preview/`. Önizlemenin boş
   barkod içeriği yalnız AÇIK ayrılmış numaraya basar (iptal edilmiş, bağlı ve sayacın
   henüz vermediği numara reddedilir — aralığın PDF'iyle aynı kural). Kuyruk, basım
   partisi, doğrulama ve boş barkod aralığı uçları `views_kuyruk.py`'dedir. Şablon ve
   kalibrasyon ekranı Ayarlar'da değil, **Etiketler → Şablonlar ve Kalibrasyon**
   sekmesindedir (Ayarlar'da DEĞİL: şablon ve kalibrasyon basımla birlikte kullanılır,
   kalibrasyon sayfası da oradan basılır); parti ve aralık ayrıntısı pencere değil
   sayfa içi karttır. Yeni uçlardan görevli kipi izin listesine YALNIZ
   `library-label-verify` POST girdi (madde 11); gerisi kapalıdır.
3. **§7.2 — Code128 yazıcı noktasına hizalıdır.** Modül X = 0,254 mm'dir. Barkodun
   sayfadaki sol kenarı da kalibrasyon kaymasından SONRA X'in katına çekilir. Böylece
   modül kenarları 300 ve 600 dpi yazıcının nokta sınırına düşer. Modül genişliği
   PDF'in çizim komutlarından okunarak sınanır.
4. **§7.2 — sırt etiketinde taşma yok.** Yer numarası boşlukla ayrılmış parçalarından
   alt alta en çok üç satır basılır. Sığmayan satırda **yalnız o satırın** yazısı
   küçülür, diğer satırlar okunur boyda kalır. Ölçüm gömülü DejaVu'nun genişlik
   tablosuyla yapılır. Kısaltılmış kaynak adı tek satırdır ve Türkçe güvenli kırpılır.
   Sayfa bütçesi testleri en uzun kaynak adı, yer numarası ve okul kısa adıyla koşar.
5. **§7.2 — tek belgede en çok 1.300 etiket** (20 tam tabaka 65'li). Daha büyük iş
   Türkçe iletiyle ("listeyi parçalara bölün") reddedilir; bölmeyi kullanıcı yapar.
   Sözleşmede bir üst sınır yoktu.
6. **§7.2 — hazır şablonlar kod içi tohumdur** (`labels/seed.py`,
   `ensure_default_templates()`, göç yok). 38,1 × 21,2 mm 65'li tabaka varsayılan
   barkod **ve** sırt tabakasıdır; iki şablonun ızgarası aynı olduğu için "sırt ve
   barkod etiketi" aynı satır × sütun düzeninde basılır. Farklı ızgaralı bir sırt
   tabakası bu içerikte reddedilir. 44'lü ve 40'lı tabakanın ölçü belirsizliği
   TB29'dadır. Şablon adlarında kâğıt boyunun kısa adı geçmez; sayfa her şablonda
   210 × 297 mm'dir (sözlük §1). **Yazıcının basamadığı kenar payı:** bar, QR modülü
   ve yazı sayfa kenarından en az 5 mm içeride basılır (`PRINT_SAFE_MARGIN_MM`; sessiz
   bölge paya taşabilir); kenarsız 40'lı tabakanın dış hücrelerinde içerik içeri kayar.
   Kalibrasyon sayfası cetveli dış kenarı basılamıyorsa etiketin iç kenarına koyar.
7. **§8.1 yöntem B — boş barkod aralığı.** Modeller `BarcodeReservation` (aralık) ve
   `ReservedBarcode` (numara başına durum). Numaralar tek sayaçtan alınır; iptal
   geri alınmaz ve numara sayaca dönmez. Hızlı Kayıt'ta sıra şöyledir:
   1. `GET library/barcode-reservations/check/?code=` ile ön denetim yapılır;
   2. eser açılır;
   3. `POST library/copies/from-label/` (gövdede `label_code`) ile nüsha bağlanır.
   Ön denetim olmasaydı reddedilen etiket nüshasız bir eser bırakabilirdi. Ekran,
   açık (bağlanmamış) boş etiket aralığı varken **etiket yoluyla** açılır; etiket
   kutusunun Enter'ı kaydı başlatır ("Kaydet"e basmakla aynıdır — okuyucu kodun
   sonuna Enter gönderir, ayrıca düğmeye gitmek gerekmez). Etiketsiz kitabın "tek
   etiket basma kısayolu" PDF'i doğrudan üretmez, tek nüshalı bir basım partisi açar;
   onay ve geri alma kuralları aynıdır (D10: PDF basıldı değildir). `classify_scan` ayrılmış ama
   bağlanmamış numarayı ayrı durum (`RESERVED`) olarak döndürür; İPTAL EDİLMİŞ numara
   ayrı bir durumdur (`CANCELLED`, denetim 24.09.2026): F6 masasının `RESERVED`'a
   diyeceği "bu etiket henüz bir kitaba bağlanmadı" iletisi iptal edilmiş etikete
   yanlış olurdu. Modül saf kalır: veritabanına bakan sorgu işlevini çağıran verir.
   F6 dolaşım masası bunu kullanır. Numara başka bir canlı nüshaya bağlıysa Hızlı
   Kayıt "kitap zaten kayıtlı olabilir" der ve "yeni numara ver" önermez.
8. **§14.1 F4 kapısı — sayaç yarışı.** Yarış testi paylaşımlı bellek içi SQLite
   üzerinde, kilit hatasında yeniden deneyerek koşar. İki numaranın çakışmadığını
   kanıtlar. Masaüstündeki dosya tabanlı WAL ve `busy_timeout` beklemesi ayrıca
   ölçülmedi.
9. **F4 eki → F12 (saha).** Gerçek yazıcıda basım ve kalibrasyon ölçümü, gerçek
   okuyucuyla doğrulama okutması, hızlı okutmada sıraya alma ve PDF önizlemenin
   WebView2 ile Pardus'taki Qt WebEngine'de görünmesi. Önizleme görünmezse
   "PDF'i indir" yolu tam işlevlidir.
10. **Açık kalan.** Tek nüshanın barkod etiketini yeniden basmanın yolu henüz
    yoktur. "Yeniden bas" bütün partiyi basar ve onayı partideki bütün nüshaların
    doğrulamasını sıfırlar. Etiket yoluyla bağlanmış nüshanın hiç basım partisi de
    yoktur. Arka uç `create_batch(copy_ids=[…])` ile tek nüshalı partiyi zaten
    kabul eder. Eksik olan, Doğrulanmamış Etiketler ya da Eser Ayrıntısı satırındaki
    "Etiketini yeniden bas" düğmesidir.
11. **§4.4, §7.2, D10 — İKİ KULLANICI KARARI (24.09.2026).**
    - **Doğrulama okutması görevli kipine açılır.** İzin listesine
      (`apps/okul/kip_izinleri.py`) YALNIZ `library-label-verify` POST girdi; öbür
      etiket uçları (kuyruk, basım partisi, onay, geri alma, doğrulanmamışlar listesi,
      boş barkod aralığı, şablon, kalibrasyon, önizleme) ve aynı ucun GET'i görevli
      kipinde 403 `kip_yetkisiz` döner. Yanıt zaten kişisel veri taşımıyordu; görevli
      kipinde yine de daralır: nüsha özeti yalnız `barcode`, `barcode_display`,
      `work_title` (`label_queue.STAFF_COPY_FIELDS`, anlık görüntüyle sınanır). Yönetici
      işine yönelten üç ileti (basıldı olarak işaretlenmemiş nüsha, bağlanmamış ve iptal
      edilmiş boş etiket) görevliye "Kitabı ayırın ve kütüphane yöneticisine gösterin."
      der: basım onayı ve Hızlı Kayıt ona kapalıdır. Kip, görünümde ara katmanla aynı
      süreç içi `KIP` nesnesinden okunur. Ön yüzde okutma görevli ekranından açılır
      ("Doğrulama okutmasını aç" / "Okutmayı bitir"; h1 "Görevli Kipi" kalır, iş bölüm
      başlığıdır); "Doğrulanmamış Etiketler" listesi görevli kipinde istenmez ve
      gösterilmez. Etiketler sayfasının kendisi görevliye kapalı kalır (kip kapısı
      rotanın yerine görevli ekranını koyar). Testler: `test_kip_koruma.py` anlık
      görüntüsü, `test_etiket_kuyrugu_uclari.py::TestKapilar` (verify POST 200 +
      daraltılmış gövde, diğer her etiket ucu her yöntemde 403),
      `test_uc_kapilari.py` (katalog yüzeyinde tek istisna bu çifttir).
    - **Sırt ve barkod partisi geri alınınca doğrulanmış nüshanın İKİ işareti de
      korunur.** Barkod etiketi içeren partide barkodu okutularak doğrulanmış nüshaya
      geri almada hiç dokunulmaz: barkod ve sırt işareti kalır, nüsha ne barkod ne
      sırt kuyruğuna döner (`label_queue.revert_batch`, `_kept_verified`). Yalnız sırt
      basan partide doğrulama yoktur, bütün sırt işaretleri geri alınır. Sayaçlar
      ayrıktır: korunan nüsha yalnız `kept_verified`'a girer, `restored`'a ve
      `requeued`'a girmez (`requeued ≤ restored`, `restored + kept_verified ≤ nüsha
      sayısı`). Dokunulmadığı için doğrulanmış nüshanın sonraki bir partideki işareti
      "önce o partiyi geri alın" reddini de tetiklemez; doğrulanmamış nüshada kural
      aynıdır. Geri alma onayı ve iletisi partinin içeriğine göre konuşur ("sırt ve
      barkod işareti" / "barkod işareti"; sırt partisinde doğrulamadan söz edilmez).
12. **§18 sözlük §3 — indirme adlarında iç kimlik yok.** Basım partisinin PDF'i belge
    adı + yerel tarih (`Sırt-ve-Barkod-Etiketi_24.09.2026.pdf`), boş barkod
    etiketleri belge adı + numara aralığı + tarih
    (`Boş-Barkod-Etiketi_2026-000101_2026-000165_24.09.2026.pdf`) taşır; parti ve
    aralık numarası dosya adına girmez. Önizleme ucu da aynı biçimi kullanır (boş
    barkod içeriğinde basılan numaraların aralığıyla). Biçim ön yüzün
    `lib/download.ts::dosyaAdi` çıktısıyla aynıdır.

**F5 ekleri (24.09.2026).** F5'te tasarımdan bilinçli sapmalar ve tasarımda yazmayan
kararlar. Üç iş kolunda (katalog uygulaması, masaüstü ve ağ, Ağ Doktoru ve belgeler)
yapıldı. Kod kapısı (§14.1 F5 satırı) ve `KD_YAVAS=1 bash scripts/gates.sh` yeşildir
(bütünleştirme, 24.09.2026; ağ kanıtları madde 18).
Tahta, gerçek okul ağı ve Windows'a özgü davranışların saha kanıtı F12'ye ertelendi
(madde 16).

1. **§4.1, §5.10-3 — şablon motoru TEMBEL yüklenir.** `django.template` paketinin
   kendi başlangıç zinciri (`template.autoreload` → `backends.django` →
   `core.checks` → `checks.database`) `django.db` ve `django.db.utils` modüllerini
   yükler. Motor modül düzeyinde kurulsaydı §5.10-3 düşerdi; ilk sayfa üretiminde
   kurulur ve `katalog.app` importu temiz kalır. Gerçek sayfalar üreten bir alt süreç
   testi yalnız bu iki modüle izin verir: `django.db.models`, `django.db.backends`,
   `django.urls`, `django.http`, `apps`, `config` ve `rest_framework` yüklenmez;
   bağlantı ve ORM kullanılmaz. Değişmezin anlamı "Django'nun veri katmanı
   KULLANILMAZ"dır.
2. **§5.3 — tek örnek ve katlama.** `katalog.app.application` süreç içi tek örnektir;
   `KutuphaneConfig.ready()` onu veriye bağlar (`ag_katalogu.varsayilan_katalogu_kur`),
   DB yolu her istekte ayardan okunur. Katalog `apps.*`'ı içe aktaramadığı için TR
   arama katlaması ve sıralama anahtarı `KatalogKurulumu` ile dışarıdan verilir; tek
   katlama kaynağı (`apps/kutuphane/keys.py`) korunur. Test veritabanı BÜTÜN backend
   testleri için dosya tabanlıdır (`TEST.NAME` küresel bir ayardır).
3. **§5.1 — görünürlük kuralları.** Nüsha durumunda BEYAZ LİSTE vardır (Rafta,
   Ödünçte, Sınıf kitaplığında, Onarımda); ileride eklenecek durum kendiliğinden
   görünmez. "Ödünç verilmez" türetimi `is_reference OR is_out_of_print OR tür ∈
   {PERIODICAL, EBOOK, EDATABASE}`'tir (`is_loanable` ve `LOANABLE_Q` ile parite
   testli). Eser en az bir görünür nüshası varsa görünür; nüshasız eserlerden yalnız
   dijital kaynaklar ve süreli yayınlar listelenir (bütün nüshası elden çıkmış kitap
   "0 nüsha" diye durmaz). `IN_REPAIR` sözlüğe göre **Onarımda** yazılır; §5.1'deki
   "Geçici olarak kullanım dışı" sözlükte "kullanılmaz"dır.
4. **§5.4 — yol tablosu ve doğrulama.** §5.4'e ek yollar: `/katalog.css` (CSP
   `style-src 'self'` gömülü stili ayrı yoldan ister), `/saglik` (F0), `/eserler`
   ve `/yazarlar` (harf seçimi), `/konular/<harf>` (Md. 11/1'in konu dizini;
   `/konular` DOS ana sınıflarıdır). Arama metni 100 karakteri aşarsa reddedilmez,
   kırpılır ve sayfada not çıkar; `sayfa` rakam değilse 404, rakamsa kırpılır. Bakım
   503'ü `/saglik` ve `/katalog.css` dahil bütün yollara `Retry-After: 60` ile uygulanır.
5. **§5.3 — `kd_katalog_populer`.** (eser, pencere, sıra) dışında `pencere_turu`
   (DONEM/AY), `hesaplanma` ve `dondu` alanları vardır: kapanmış pencere dondurulur,
   E12 afişinin penceresi aydır. Sayı alanı yoktur. Yazıcı gün değişimi kapısına
   `KutuphaneConfig.ready()`'de "cok-okunanlar" adıyla kaydolur (bakımda ya da hatada
   bir saat sonra yeniden denenir); gerçek hesap ve §5.10-12 F10'dadır.
6. **§5.2, §6.2 — `KatalogAyari`.** Alanlar: `acik`, `port`, `dinleme_kipi`
   (`ALL`/`SELECTED`), `secili_ip`, `son_afis_ip`, `uyku_engelleme`, `vitrin_acik`,
   `konular_acik`, `tahta_cidrleri`; kütüphane saatleri `SchoolConfig`'tedir ama aynı
   servisten yazılır. Servis `update_katalog_ayari(*, sistem_yazimi=False, **alanlar)`
   yalnız yönetici kipinde yazar; `ayar_degisince(dinleyici)` kalıcılaşan ayarı
   masaüstü denetçisine iletir. Tahta ağı blokları özel ve en geniş `/16`'dır.
7. **§5.7 — denetim geçmezse hiç dinlemez.** Beş madde tutmazsa ya da denetim
   okunamazsa katalog okul ağında dinlemediği gibi `127.0.0.1`'e de düşmez (durum
   "Güvenlik duvarı izni yok"). Loopback'e düşmek TB12 açığını yeniden açardı ve
   program içi bağlantılar LAN adresiyle kurulduğu için değeri yoktu. 4. madde:
   kural profili etkin ağ profilini kapsamazsa KALDI; uzak adres "her yer" ise UYARI
   (dinlemeyi engellemez). `--autotest` ayardan ve duvardan bağımsız olarak katalogu
   yalnız loopback'te kaldırıp öz sınar.
8. **§5.2 — seçili IP kaybolursa dar yorum.** Bilgisayarın TEK aday adresi varsa
   katalog o adreste açılır ve uyarır; birden çok aday varsa açılmaz, Ağ Doktoru
   seçim ister. Arayüz kimliği tutulmadığı için katalog sessizce yanlış ağa (ör.
   öğrenci erişimli ağa) açılabilirdi. Port doluysa denetçi 5 dakika boyunca 10 sn
   arayla kendiliğinden yeniden dener ("Port bekleniyor").
9. **§4.2-4, §5.10-18 — `app/quit/`.** Parolasız görevli isteği 403
   `cikis_parolasi_gerekli` (403 `kip_yetkisiz` değil: ön yüz o kodu "kip değişti"
   diye okur), yanlış parola 400, masaüstü kancası yoksa 503 `cikis_kullanilamiyor`,
   başarı 202. Kilit ve yeniden başlat kapıları bu tek yolu tam eşleşmeyle geçirir.
   Arayüzde her durumda üst çubukta "Çık" vardır; onay diyaloğunun başlığı "Programdan
   çıkılsın mı?", görevli kipinde "Programdan çık" (parola formu). "Programı kapatıp
   yeniden açın" ekranında "Programdan çık" düğmesi vardır. Tepsideki görevli kipi
   Çık'ı pencereyi öne getirip arayüze `kd:cik-iste` olayını gönderir.
10. **T16 — kayıt noktası `apps/okul/masaustu_kanca.py`.** Katalog denetçisi, çıkış
    kancası ve backend'in gün değişimi işleri buraya kaydolur. `live_restore`
    takastan önce katalogu bakım kapısına alır, takas başarısızsa geri açar. Yeni iş
    parçacığı adları: `kd-tepsi`, `kd-cikis`, `kd-katalog-dene`, `kd-katalog-ayar`,
    `kd-katalog-ac`, `kd-katalog-kapat`. Yeni kimlik adları: zamanlanmış görev
    "Kutuphane Defteri", HKLM değeri `SOFTWARE\KutuphaneDefteri\KatalogPortu` (DWORD).
11. **Teknik borç.** TB10 kararı: Linux'ta katalog soketine `SO_REUSEADDR` konur
    (Linux'ta port paylaşımı değildir). TB11, TB12, TB13, TB14 kapandı; TB2
    uygulandı (kabul anında adres başına 20 eşzamanlı bağlantı), kalan riski
    kütüktedir.
12. **§5.9 — Ağ Doktoru uçları** (`library/network-catalog/…`, hepsi yalnız yönetici
    kipinde, izin listesinde değil): `status/` (durum, adres ve QR modülleri, kişisiz
    günlük sayılar, son hata), `control/` (aç/kapat/yeniden başlat), `firewall/`,
    `firewall-rule/` (UAC), `interfaces/`, `listener-test/`, `port/`, `poster/`,
    `info-note/`, `bookmarks/`, `pys-text/`. Denetçi yokken (geliştirme sunucusu)
    durum okunur, eylemler 503 `masaustu_yok` döner. Ağ Doktoru menüde yoktur;
    **Ayarlar → Ağ Kataloğu** sekmesinden (dokuzuncu sekme) açılır.
13. **§5.2, §5.7 — port değişikliği sırası.** Windows'ta ÖNCE UAC yardımcısı kuralı
    ve HKLM değerini yeni portla yazar, ancak başarırsa port ayarı kaydedilir; UAC
    reddedilirse port değişmez (409 `kural_yazilamadi`). Bu yüzden Windows'ta ayar
    ucu (`settings/` PUT) portu değiştirmez (400). Pardus'ta port doğrudan yazılır,
    Ağ Doktoru yeni komutu gösterir.
14. **§5.6, §5.9 — belgeler.** Afiş POST'tur, basılınca adres `son_afis_ip` olarak
    kaydedilir (IP değişimi uyarısının karşılaştırma değeri). Adresin punto boyu
    DejaVu ölçüleriyle en uzun adresi de tek satıra sığdırır; afiş tek sayfadır.
    Bilgi notu en uzun gerçekçi veride en çok iki sayfadır, adres bulunamazsa da
    basılır (adres satırı elle doldurulur), kuraldaki değerleri denetimin GÜNCEL
    okumasından alır; Yönerge alıntıları depodaki metinle birebir testlidir ve
    §5.9 listesine 11/20, 11/21, 11/25 satırı eklendi (atıf haritası §3.3'teki
    satır). Yer imi dosyaları tek arşivdir (Chromium `ManagedBookmarks` politikası
    ve `.desktop` başlatıcı tahta kipiyle, Windows `.url` iki biçimde, BENIOKU).
    PYS talep metni kanalı **FATİH PYS** diye anar; açılımı yazılmaz. Belgelerde
    ve ekranlarda "okul bilişim sorumlusu" yerine sözlüğün **BTR**'si kullanılır.
15. **Açık karar — güncelleme denetiminin hedefi.** T11 ve CLAUDE.md §3 güncelleme
    denetimini `indir.okulapp.org` manifestine bağlar; kod bugün GitHub'a
    (`api.github.com`, indirme `github.com`) gider (`apps/okul/services/updates.py`).
    Bilgi notu hedefleri kaynak koddaki adresten türetir, yani notta yazan her zaman
    programın gerçekten gittiği adrestir. Denetimin manifeste taşınması ya da T11
    metninin düzeltilmesi kullanıcı kararıdır.
16. **F5 eki → F12 (saha).** Tahtadan erişim ve ekran klavyesiz gezinme (§5.10-15),
    eski Chromium ve Firefox ESR görünümü, güvenlik duvarı denetiminin yönetici
    olmayan masa hesabında çalışması, Windows'ta `SO_EXCLUSIVEADDRUSE` ile tüm
    arayüzde dinleme, `SetThreadExecutionState` ve Linux'ta `systemd-inhibit`,
    pystray menü yenilemesi, UAC yardımcısı, kurucunun güvenlik duvarı görevi ve
    zamanlanmış görevin masa hesabına yazılması (`packaging/windows/NOTLAR.md`
    W15-W20).
17. **Kılavuz, sözlük ve kurulum belgesi.** Kılavuzun "Ağ Kataloğu" bölümü
    kullanıcının soru sırasıyla yazıldı: ne olduğu → neyi gösterip neyi asla
    göstermediği (§5.1 tablosu; "Ödünçte" görünür, kimde olduğu görünmez) → BTR'yle
    yapılacak beş iş (ağ keşfi, sabit adres, gerekirse PYS talebi, bilgi notu, okul
    ağından erişim sınaması — S1, S2, S3, S6, S15) → "Ağ Kataloğunu Açmadan Önce"
    kartının adımları → Ağ Doktoru'nun beş kartı ve durum rozetleri → afiş ve yer
    imleri (ETAP'ın öğretmen başına hesabı, politika dosyası) → tahta kipi → adres
    değişirse → port → Pardus. "Tepsi, Çıkış ve Gün Değişimi" bölümü tepsiden
    seçilen Çık'ın yönetici kipinde ve kilitliyken ONAY SORMADAN kapattığını
    (üst çubuktaki sorar), kurucunun programı kendisi kapattığını, kurucu
    görevlerinin gerçek adlarını ve yedeğin kilitliyken de alındığını yazar. Çok
    okunanlar listesinin bu sürümde boş olduğu (ödünç verisi yok, madde 5)
    kılavuzda açıkça söylenir. Yeni mevzuat atfı: **Yönerge 11/6** (IP ve MAC
    adresini yalnız yetkilendirilmiş kişiler değiştirir — kütüphane yöneticisi
    adresi elle değiştirmez; atıf haritasına satır eklendi), kılavuza 11/12 ve
    11/22 (ilk cümle) alıntıları; hepsi `docs/mevzuat/`'taki metinle birebir
    testlidir. F1 ekleri 9'un `docs/kurulum.md`'deki "sonraki sürümde"
    işaretlerinden gün değişimi kapısı ve parolalı Çık kalktı; kütüphane
    aydınlatma metni (E13) F6'da kalır. Sözlük §4.9'a çıkış, tepsi ve kurucu
    adları ile Ağ Kataloğunun kendi sayfalarının adları işlendi.
18. **Kod kapısının ağ kanıtları (bütünleştirme).** İki Docker kabı aynı compose
    ağında iki ayrı bilgisayar yerine geçer (`scripts/ag_katalogu_provasi.sh`). Kap A
    gerçek masaüstü yolunu koşar: göç, yönetici parolası, 10.000 eser ve 20.000
    nüshalık sentetik katalog, oturum belirteçli yönetim sunucusu `127.0.0.1`'de,
    "Aç" ayarı ve `KatalogKontrol` ile Ağ Kataloğu tüm arayüzlerde (`KD_DEBUG=0`).
    **İkinci bilgisayardan arama:** kap B'nin "ŞİİR" araması 200 döner; yanıt
    imzalı, CSP'li ve çerezsizdir, TR katlamayla "şiir" konulu eseri bulur. Katalog
    portunda yönetim yolu 404'tür, A'nın yönetim portuna ağdan bağlantı reddedilir,
    A isteği B'nin adresinden görür. **50 istemcili yük:** B'de 50 eşzamanlı
    istemci, her biri ayrı kaynak IP'den gelir (okul ağında her tahta ayrı adrestir;
    hız sınırı ve bağlantı sınırı gerçek dağılımla sınanır). İstemciler her istekte
    yeni bağlantıyla karışık katalog sayfaları çeker (arama, sonuç sayfaları, eser,
    harf dizinleri, konular). Aynı anda A'da ayrı bir süreç yönetim API'sini yoklar:
    durum, kip, eser araması ve 10.000 eserde TR sıralı sayfalı liste. Ölçüm
    (24.09.2026, geliştirme makinesi; istemci ve sunucu aynı Docker sanal
    makinesinde; 30 sn):

    | Senaryo | Ağ Kataloğu | Yönetim API'si |
    |---|---|---|
    | Yüksüz taban | — | medyan 11 ms, p95 72 ms, hata 0 |
    | 50 istemci, düşünme süresiz (en kötü durum) | 4.462 istek (147/sn), hepsi 200; medyan 334 ms, p95 416 ms, en uzun 515 ms; hata 0, hız sınırı 0, reddedilen bağlantı 0 | medyan 56 ms, p95 158 ms, hata 0 |
    | 50 istemci, sayfa başına ortalama 2 sn düşünme | 770 istek (23/sn), hepsi 200; medyan 14 ms, p95 125 ms | medyan 18 ms, p95 76 ms, hata 0 |

    Düşünme süresiz yükte katalog gecikmesinin çoğu 4 iş parçacıklı havuzun
    kuyruğudur (50 istemci / 147 istek/sn ≈ 0,34 sn). Yönetim sunucusu ayrı havuzda
    olduğu için (T3) en ağır yönetim isteği yük altında yaklaşık iki kat yavaşlar ama
    200 ms'nin altında kalır. Betikteki eşikler: katalogda hata ve 429 sıfır, katalog
    p95 < 2 sn, yönetim p95 < 500 ms. Prova gecelik kapıda koşar (`KD_YAVAS=1
    bash scripts/gates.sh`); aynı değişken artık `yavas` işaretli BÜTÜN ölçüm
    testlerini seçer. Bu değişiklikten önce F5'in katalog ölçümü
    (`katalog/tests/test_olcum.py`) gecelik kapıya girmiyordu. Gerçek okul ağı,
    tahta ve Windows paketiyle aynı prova F12'dedir. Kalan risk TB2'dedir: tahtalar
    kütüphane bilgisayarına tek bir NAT adresinden ulaşırsa adres başına hız sınırı
    (40 istek sıçraması, saniyede 4) ve 20 bağlantı sınırı bütün sınıfı birlikte
    sınırlar.

*Düzeltme turu (24.09.2026).* Bütünleştirme sonrası denetimin bulguları yeniden
doğrulandı; gerçek olanlar kök nedeninden düzeltildi ve her biri bir testle
kilitlendi (madde 19-30). Kapı yeniden yeşildir.

19. **§5.7 — 4. madde bütün izin kurallarının BİRLEŞİMİDİR.** Denetim yalnız ilk
    eşleşen kurala bakıyordu; PowerShell kuralları hashtable'dan topladığı için sıra
    belirsizdi ve dar kural önce gelirse aynı exe'ye yazılmış geniş (Any) ikinci
    kural görünmüyordu. Kurallar önce sabit sıraya dizilir (programın kendi adlı
    kuralı önde). Kapsam: portu kapsayan kuralların profil birleşimi etkin profili
    kapsamalı; etkin profile uyan kuralların uzak adresleri birleştirilir, biri
    "her yer" ise UYARI ve kuralın adı yazılır. Geniş kural programın kendi kuralı
    değilse açıklama "“Kuralı ekle/güncelle” yalnız programın kendi kuralını yazar;
    bu kuralı BTR … daraltır ya da kaldırır" der. Denetim `kurallar` listesini de
    döndürür; Ağ Doktoru her kuralı ayrı gösterir, bilgi notu ilk kuralı tam
    tabloyla, öbürlerini kısa satırla basar (sayfa bütçesi iki sayfa, iki kuralla
    testli). UAC yardımcısı öbür izin kurallarını SİLMEZ: BTR'nin ya da grup
    ilkesinin kuralı olabilir, karar BTR'nindir.
20. **§5.3 — authorizer önekle değil TAM ad kümesiyle karar verir.** Görünüm içi
    okumada 5. argüman `{kd_katalog_eser, kd_katalog_nusha, kd_katalog_okul}`
    kümesinde, üst düzey okumada ad bu küme + `kd_katalog_populer` içinde
    olmalıdır (`katalog/veri.py::GORUNUMLER`, `UST_DUZEY_OKUNABILIR`; küme görünüm
    tanımlarıyla eşitlik testli). İleride `kd_katalog_` önekiyle eklenecek bir tablo
    kendiliğinden ağa açılmaz; `WITH kd_katalog_x AS (…)` gibi önekli CTE reddedilir.
    **Bilinen sınır:** SQLite 5. argümanda görünümü aynı adlı CTE'den ayırmaz;
    görünümle aynı adı taşıyan bir CTE izin listesindeki çiftleri görünüm
    süzgeçleri olmadan okuyabilir (barkod, kişi ve ödünç yine reddedilir). Katalogda
    keyfi SQL çalışmadığı için sömürülemez: güvencenin dayanağı katalog SQL'inin
    SABİT olmasıdır; kaynak taraması testi katalog paketinde `WITH` olmadığını ve
    okunan adların kümede olduğunu sınar (TB31). §5.3 tablosunun "`kd_katalog_` ile
    başlıyor" satırları bu dar anlamda okunur.
21. **T9, §5.2 — saatlik damgasız işler.** Gün değişimi kapısına damga yazmayan,
    her tikte koşan işler eklendi (`saatlik_kaydet`). `KatalogKontrol.saatlik_denetle`
    (1) seçili IP kipinde dinlenen adres bu bilgisayardan kalktıysa dinleyiciyi
    yeniden kurar (DHCP gün içinde adres değiştirirse katalog ertesi güne dek
    kaybolan adreste "açık" görünmez), (2) geçici hatayla kapalı kalan katalogu
    yeniden dener (madde 23). Arayüz listesi okunamadıysa çalışan dinleyiciye
    dokunulmaz. Afiş/yer imi uyarısı günlük kalır.
22. **§5.2 — F5 ekleri 8'e ek: liste okunamazsa tek aday kuralı yok.** Arayüz
    listesi okunamadığında (yedek yol yalnız varsayılan adresi bilir) seçili IP
    belki hâlâ bu bilgisayardadır ve "tek aday" başka bir ağdır; katalog açılmaz
    (`KatalogArayuzOkunamadiError`, geçici hata), ileti "ağ bağlantıları okunamadı"
    der.
23. **§5.7 — okunamayan denetim kendiliğinden yeniden denenir.** Fail-closed
    değişmedi: güvenlik duvarı denetimi okunamazsa (oturum açılışının yükünde
    PowerShell zaman aşımı) katalog dinlemez. Ama 60 sn arayla 5 kez, sonra saatlik
    tikte birer kez yeniden denenir; kullanıcı eylemi sayacı sıfırlar. Kuralın
    gerçekten tutmadığı (KALDI) durum yeniden denenmez.
24. **Kapatılabilirlik ve ilk açılış kartı.** Ayar açık ama katalog açılamamışsa
    (güvenlik duvarı izni yok, açılamadı, port bekleniyor) Ayarlar → Ağ Kataloğu,
    Ağ Doktoru ve tepsi "Ağ Kataloğunu kapat" (+ "Yeniden başlat") sunar
    (`KatalogKontrol.kapatilabilir_mi`, tepside `katalog_kapatilabilir`); ayar açık
    kaldıkça program her açılışta yeniden dener, kullanıcı vazgeçebilmelidir. "Ağ
    Kataloğunu Açmadan Önce" kartı yalnız afiş hiç basılmamışken görünür, katalog
    açıldıktan sonra da afiş basılana dek kalır: 4. adım açıkken "tamam", açılamadıysa
    nedenin nerede yazdığını söyler; 5. adım (afiş, yer imleri) ekranda kalır.
25. **§5.8 — "bu bilgisayar öğrenci erişimli ağda".** Aday adreslerden biri
    Ayarlar'daki tahta ağı bloklarının içindeyse Ağ Doktoru'nun uyarılarına ve
    durum uyarılarına "Bu bilgisayar öğrenci erişimli ağda…" satırı, arayüz
    tablosuna "Tahta ağı (öğrenci erişimli)" notu girer (KM-19). Tahta blokları
    girilmemişse uyarı çıkamaz; bu bilinçlidir (ağın niteliğini BTR söyler).
26. **§5.2 — varsayılan rota RouteMetric + InterfaceMetric toplamıyla seçilir.**
    Windows'un kendi kuralıdır; DHCP rotalarında RouteMetric çoğu zaman 0'dır ve
    kablolu/kablosuz tercihi arayüz metriğindedir. Eşitlikte küçük arayüz indeksi.
27. **§5.7 Pardus — komut KAYNAK SINIRLIDIR.** `ufw allow <profil>` ve kaynaksız
    `--add-service` katalogu MEB WAN'ındaki başka kurumlara da açardı (GA-6). Komut
    bu bilgisayarın yerel alt ağlarından (`ip -j`) ve tahta ağı bloklarından
    üretilir, her blok ayrı satırdır: ufw'de `allow from <blok> to any app 'Kutuphane
    Defteri'`, firewalld'de zengin kural (rich rule). Blok bilinmiyorsa
    `<okul-agi-blogu>` yer tutucusu yazılır; /16'dan geniş blok komuta girmez.
    Tanım dosyası yoksa (taşınabilir arşiv) ya da port değiştiyse port temelli
    komut verilir. Paketteki ufw profil açıklaması, `docs/kurulum.md` §8.5 ve
    `docs/ag-kurulumu.md` §3 aynı biçime getirildi. **Açık karar:** Pardus'un
    taşınabilir arşivinde katalog açılır; §5.2'deki "taşınabilir pakette sunulmaz"
    gerekçesi (kural program yoluna bağlı, GA-5) Windows'a özgüdür. Belgeler
    "Windows'un taşınabilir paketinde sunulmaz" diye daraltıldı; Linux taşınabilir
    arşivde de kapatılması kullanıcı kararıdır.
28. **Sağlamlık.** `powershell.ps_dizesi` PowerShell'in tek tırnak saydığı beş
    karakterin hepsini ikiler (`'`, U+2018, U+2019, U+201A, U+201B; kural
    `EscapeSingleQuotedStringContent` ile aynı, Windows PowerShell 5.1'de
    denendi): "Okul’un" gibi bir yol yükseltilmiş kural betiğinde komut olarak
    çalışamaz. PyInstaller kancası (`rthook_kd.py`) yükseltilmiş yardımcı kipte
    fontconfig önbelleği yazmaz (BTR'nin profiline dokunulmaz). Linux uyku engeli
    `systemd-inhibit … cat` ile programa ait borudan okur: program düzensiz biterse
    boru kapanır ve engel kalkar (`sleep infinity` yetim kalırdı). Oturum içi yedek
    rotasyonu saat sıçramasına karşı çapalıdır: rotasyon tarihi `min(bugün, çapa +
    uyku dahil açık kalma saatiyle geçen gün + 1)`; saat 14 günden fazla ileri
    sıçrarsa geçmiş yedekler silinmez. Bulgunun önerdiği "en yeni N yedeği her
    durumda tut" alınmadı: TB8 ve §6.4'ün "günlük yedeklerde en çok 14 gün" sözünü
    (aydınlatma metni) bozardı. Uyku dahil açık kalma saati Windows'ta
    `GetTickCount64`, Linux'ta `CLOCK_BOOTTIME`'dır; ikisi de F12'de sahada
    doğrulanır.
29. **Inno — `[Registry]` yerleşimi.** `[Registry]` bölümü WebView2 `Source:`
    satırının önüne girmişti; sürüm derlemesi WebView2 kurucusunu indirdiğinde
    ISCC "Unrecognized parameter name Source" ile kırılıyordu (yerel derleme
    yalnız `#else` dalını görmüştü). WebView2 bloğu `[Files]`'ın sonuna,
    `[Registry]` ondan sonraya alındı; iki dal da yerel ISCC 6 ile `/O-`
    derlendi. Bölüm yerleşimini paket testi sınar.
30. **Belgeler ve sözlük.** Bilgi notu: künye bayrağı açık ama iki kaynak da
    kapalıysa program dışarı künye isteği atmaz, not da "kapalı" gibi yazar
    (hedef satırı ve 11/12-11/19 atıfları basılmaz); güncelleme hedeflerine
    indirmenin yönlendiği `*.githubusercontent.com` ve `Test-NetConnection
    github.com -Port 443` eklendi (F5 ekleri 15'in açık kararı sürüyor); port
    gerekçesinin son cümlesi platforma göredir (Pardus'ta "kuralı da günceller"
    yazılmaz). PYS talep metninde BTR ilk geçişte açılır. Yer imi BENIOKU'su
    Chromium'un yer imi çubuğunu varsayılan olarak yalnız yeni sekmede gösterdiğini
    söyler; `BookmarkBarEnabled` okulun kararına bırakıldı, başka bir
    `ManagedBookmarks` dosyasıyla birleştirme notu eklendi. Sözlük: güvenlik duvarı
    madde açıklamalarında "okul bilişim sorumlusu" yerine BTR, düğme adı birebir
    "Kuralı ekle/güncelle"; katalog "Son hata" iletilerinde "sunucu" yerine
    "dinleyici"; Ağ Doktoru'ndaki kural profili Türkçe ("Etki alanı, Özel,
    Genel"). Masaüstü modüllerinin kullanıcı metinleri bir sözlük taramasıyla
    korunur (`desktop/tests/test_sozluk_metinleri.py`). Kılavuz: geri yüklemeden
    sonra katalogun kalkması yedekteki ayara bağlıdır.

**F6 ekleri (24.09.2026).** F6'da tasarımdan bilinçli sapmalar ve tasarımda yazmayan
kararlar. Üç iş kolunda (üyelik, kart ve ödünç çekirdeği; dolaşım masası ve görevli
kipi; evrak, üyelik yönetimi ve pano) yapıldı; ardından bütünleştirme denetiminin
bulguları düzeltildi (madde 13-26). Kod kapısı (§14.1 F6 satırı) ve `bash
scripts/gates.sh` yeşildir. **D8, D9, D12, D19 ve D21 kapandı** (§13; madde 12).
Gerçek okuyucuyla hızlı okutma ve katlanmış pusulanın saha denemesi F12'dedir.

1. **§6.2 — modeller ve tek göç.** `Membership` (öğrenci XOR personel, kişi başına tek
   aktif üyelik — kısmi teklik; üye türü saklanmaz, kişiden türer; `card_no` şifreli
   + `card_no_index` kör indeks, teklik indekste; `requested_at`, `started_at`,
   `terminated_at`, `termination_reason` — sonlanan üyelikte zorunlu, DB kısıtı;
   `card_printed_at`), `IssuedCard` (yalnız indeks ve tarih, `BaseModel` değil),
   `CardRevocation` (nedeni `RENEWED`/`MERGED`/`DELETED`), `Loan` (bir nüshada tek açık
   ödünç — kısmi teklik; `override_reason` + `override_note` ikisi birlikte ve şifreli;
   `cardless` + `cardless_reason` ikisi birlikte ve gerekçe şifreli). Tek göç
   `0005_uyelik_ve_odunc`. **Dönen kişiye YENİ üyelik ve yeni kart açılır**, eski satır
   yeniden aktifleşmez (OYS kararı); sayılar (açık ödünç, gecikme, kalan hak) kişinin
   BÜTÜN üyelikleri üzerinden sayılır: eski üyelikte iade edilmemiş kitap sınırı ve
   gecikme engelini sıfırlamaz.
2. **§4.4, D12 — kapalı listeler.** Gecikme istisnası gerekçesi: "Ders ya da ödev için
   gerekli" · "Gecikmenin geçerli bir mazereti var" · "Gecikmiş kaynağın iadesi için
   görüşüldü" · "Diğer" + zorunlu açıklama (en çok 500 karakter, "Sağlık ya da aile
   bilgisi yazmayın."). Kartsız ödünç gerekçesi: "Kart yanında değil" · "Kart kayıp —
   yenilenecek" · "Kart henüz basılmadı" · "Kart okunmuyor". Sonlandırma nedeni:
   elle yalnız "Üyenin isteği" ve "Yanlış kayıt"; "Okuldan ayrıldı" ayrılış kancasının,
   "Kişi kayıtları birleştirildi" birleştirmenin işidir. Açık ödüncü olan üyelik elle
   sonlandırılamaz; ödünç kaydı olan üyelik silinmez (sonlandırılır). Gecikme engeli
   yokken gönderilen gerekçe kayda GEÇMEZ (gereksiz gerekçe yanıltıcı olurdu).
3. **§9-5 — dönem sonu uyarısı ve kaydırma işareti.** Uyarı etkin ders yılının ödünç
   gününü kapsayan döneminden hesaplanır; ders yılı ya da dönem tanımlı değilse
   üretilmez. Yönetici yanıtı `due_date_shifted` taşır; kaydırma "Md. 18 gereği" diye
   sunulmaz (kaynak taramasıyla testli).
4. **§8.3 — yıl sonu tarihi.** Son sınıf, `SchoolConfig.kademe`'nin son sınıfıdır (4 ·
   8 · 12); `last_loan_date_graduating` tanımlıysa ona daha erken tarih uygulanır.
   **Eski yılın tarihi uygulanmaz:** etkin ders yılı tarihten sonra başlamışsa kural
   düşer (geçen Haziran'ın tarihi Eylül'de bütün ödünçleri kilitlemesin).
5. **§4.4 — görevli yüzeyi.** İzin listesine beş masa ucu (`library-desk-member`,
   `library-checkout`, `library-return`, `library-desk-copy-status`,
   `library-desk-card-unlock`) ve katalog okumanın üç GET ucu (sorgu parametresi
   sınırlı) girdi. `library-checkout` gövdesinde `override_*`, `cardless*`,
   `membership_id`; `library-desk-member` gövdesinde `membership_id` bulunursa (değeri
   boş olsa da) 403. Masa uçları yalnız JSON gövde kabul eder, kart no URL'ye yazılmaz
   (POST). Görevli yanıtlarının alan listeleri `serializers_masa` sabitleridir ve
   anlık görüntüyle sınanır (§5.10-8 dolu). Servis katmanı aynı kuralı bir kez daha
   uygular (`yonetici_kipi.require_admin_mode`).
6. **§7.3 — masa iletileri.** Tasarımın tablosuna "Bu kitap zaten bu üyede. İade
   alınsın mı?" (düğme "İade al") eklendi: üyenin kendi kitabını "başka üyede" diye
   okumak yanlış olurdu. Okutma bir olaydır (iade ve durum sorgusu 200 gövde döner),
   ödünç bir eylemdir (ret 400 + kararlı kod). Nüsha durum sorgusu ("Yalnız durum
   sor") yazma yapmaz; görevli kipinde kitabın kimde olduğu gösterilmez.
7. **GA-7 — sayaç süreç içidir** ve anahtar dönemine bağlıdır (kilitleyip parolayla
   açmak sıfırlar); yönetici kipinde sayılmaz, yönetici kipindeki bir okutma sıfırlar.
   Sağlaması tutmayan numara veritabanına hiç sorulmaz. Kilit görevli kipinden
   çıkmadan `card-unlock/` ile (gövdede yönetici parolası) açılır. İkinci kural madde
   19'dadır.
8. **§7.2, E2 — üye kartı.** Kart şablonu kod içi tohumdur (85 × 54 mm, A4'e 2 × 5,
   simetrik kenar; göç yok, etiket şablonları ekranında görünmez), kesim çizgisi
   seçmelidir, kaydırma yazıcı kalibrasyonuyla düzeltilir. Barkod modülü kartta 4/300
   inçtir (≈ 0,339 mm; nokta ızgarasına hizalı, 99 modülle 33,5 mm). Basım işareti
   üyelik satırındadır (`card_printed_at`); kart için basım partisi tutulmaz, geri
   alma işareti boşaltır.
9. **E4 — pusula geometrisi.** A4'te üç pusula (210 × 99 mm), sol 45 mm ad şeridi,
   katlama çizgisi 127,5 mm'de (sağ 82,5 mm'lik bölüm orta bölümü tam örter), kesme
   çizgileri yalnız pusulalar arasında. Pusulada en çok beş kaynak, fazlası "ve N
   kaynak daha — kütüphane yöneticisine sorun." satırıdır. Kişinin eski üyeliğindeki
   gecikmeler de aynı pusulaya girer (kişi bazında).
10. **E13, E19 — aydınlatma metni ve masa kartı.** Başvuru adresi ve iletişim bilgisi
    yalnız basıma yazılır, programda saklanmaz. Metin en uzun veride en çok iki
    sayfadır; Kanun alıntıları `docs/mevzuat/6698-kvkk.md` ile birebir testlidir.
    Masa kartı tek sayfadır ve masadaki iletileri ekranla aynı yazar.
11. **T15 — beklenmedik kapanış kartı.** "Son Oturumu Kontrol Edin" kartı yalnız
    yönetici kipinde görünür ve bu süreçten ÖNCEKİ son 30 ödünç/iadeyi listeler;
    "Kontrol ettim" onayı süreç içidir (dosyaya yazılmaz).
12. **D kalemleri.** D8: kartta okul adı `SchoolConfig`'ten gelir, kartlar tabakaya
    basılır. D9: ödünç ve üyelik listeleri sayfalıdır, 26. ödünç barkodla iade edilir
    (testli). D12: istisna gerekçesi ve sonlandırma nedeni kapalı listeden ve zorunlu
    (servis + DB kısıtı + serializer). D19: süre ayar değildir (`LibraryPolicy`'de süre
    alanı yok, testli). D21: kart no `9` + 6 rastgele hane + Luhn; `CardCounter` yok.

*Düzeltme turu (24.09.2026).* Bütünleştirme sonrası denetimin bulguları yeniden
doğrulandı; gerçek olanlar kök nedeninden düzeltildi ve her biri bir testle
kilitlendi (madde 13-26). Tasarım kararını değiştirecek bir kalem uygulanmadı,
açık karar olarak yazıldı; kullanıcı 25.09.2026'da §7.3'ün aynen kalmasına karar verdi
(madde 26, TB34).

13. **§9-5 — tatilsiz takvim yılı.** İade tarihi kaydırması yalnız Kapalı Günler'e
    bakar; tatilleri yalnız kurulum sihirbazı tohumluyordu. İkinci yılda Ayarlar'dan
    açılan ders yılının ikinci takvim yılı tatilsiz kalıyor, 1 Ocak'a ya da bayrama
    düşen iade tarihi kaymıyordu (ertesi gün sahte gecikme ve gecikme engeli). İki
    önlem: Ayarlar → Ders Yılları'nda aktifleştirme de iki takvim yılını tohumlar
    (sihirbazla ortak `modules/takvim/tatilTohumu.ts`); iade tarihinin düştüğü yılda
    resmî tatil ya da dini bayram kaydı yoksa ödünç uyarı döndürür
    (`circulation.holidays_missing_warning`).
14. **§4.4, §7.3 — görevli kipinde ret sırası.** Görevli, gecikmesi olan ya da sınırı
    dolu bir üyenin kartıyla barkodları deneyip "bu üyede / başka üyede" retlerinden
    üyenin elindeki (gecikmiş) kitapları çıkarabiliyordu (§4.4: gecikmeli üyede eser
    adı gösterilmez). Görevli kipinde üyeye bağlı engeller (üyelik, yıl sonu, gecikme,
    sayı sınırı) nüshanın kimde olduğundan ÖNCE koşar; yönetici kipinde sıra
    korunur. Kalan ayrım madde 26'dadır.
15. **§8.3 — görevliye tarihsiz yıl sonu iletisi.** Son sınıf tarihi görevliye kartın
    sahibinin son sınıfta olduğunu gösteriyordu; görevli iletisi tarihsizdir. Ret
    zamanlamasından çıkarım kalan risktir (TB32).
16. **§9-8, §7.3 — üyeye bağlı retlerde iade önerisi.** Sonlanmış üyenin kartından sonra
    okutulan kendi kitabı "Üyelik sonlanmış" retiyle kalıyordu. Masa, üyeye bağlı
    retlerin (üyelik, ayrılış, yıl sonu, gecikme, sınır) altında "Kitap iade için
    getirildiyse iadesi alınabilir." der ve "İade al" sunar. Sunucu sırası
    değişmedi: iade önerisi kitabın kimde olduğunu söylemez.
17. **§4.4 — birleştirmede iptal edilen kart.** Kaynak üyelik numarasını korur ama kartı
    iptaldir; masa onu "Üyelik sonlanmış" diye okuyordu. Kart çözümünde iptal kaydına
    ÖNCE bakılır.
18. **§7.1, D21 — geri yükleme ve kart numarası.** Geri yükleme `IssuedCard`'ı da geri
    sarıyordu; yedekten sonra basılıp dağıtılmış bir kartın numarası sonraki bir
    üyeliğe yeniden çekilebilirdi. Verilen her numaranın kör indeksi veri dizinindeki
    yalnız-eklenen `verilmis-kartlar.txt` defterine de yazılır (`card_ledger`; geri
    yükleme dokunmaz, kişisiz); yeni numara iki kaynağa karşı denetlenir. Defter
    okunamazsa kart yine verilir (asıl güvence veritabanıdır). Kalan risk TB33.
19. **GA-7 — ikinci kural.** Geçerli bir kart "art arda" diziyi bozduğu için görevli
    dört numaradan sonra kendi kartını okutup sınırsız deneyebiliyordu (§4.3'teki
    "kalan risk —" yanlıştı). Ek kural: son 10 dakikada 5 tanınmayan ya da iptal
    edilmiş kart okutması (sağlaması tutan, veritabanına sorulan) kart okutmayı
    durdurur; geçerli kart bu sayıyı sıfırlamaz, kilit kendiliğinden kalkmaz, yalnız
    yönetici parolası kaldırır. Sağlaması tutmayan okutma bu kurala sayılmaz (kimseyi
    ele vermez); yıpranmış kartın yanlış okunması kilitlemesin diye "art arda" kuralı
    aynen durur. §4.3 satırı güncellendi.
20. **§4.4 — parametre denetçisi yalnız UTF-8.** Denetçi gövdeyi `json.loads` ile,
    DRF ise `charset` ile çözüyordu; `charset=utf-7` ile `override+AF8-reason`
    denetçiden geçip görünümde `override_reason` oluyordu (servis kapısı yine
    kesiyordu, sömürülemezdi). `charset` UTF-8 dışındaysa ara katman 403 verir, masa
    görünümleri 415 verir (`Utf8JSONParser`).
21. **§7.3 — kart okutma kilidi pencere değil şerittir.** Kipsel pencere bütün
    okutmaları yutuyordu ("iade kilitlenmez" sözü masada tutmuyordu). Kilit okutma
    kutusunun üstünde bir şerittir; kutu açık kalır, kilitliyken okutulan kitabın
    iadesi alınır, kart okutması 429 alır.
22. **§7.3 — gerekçeli istisna penceresi ve kuyruk.** Pencere açıldıktan sonra okutulan
    kitaplar kayboluyor, kuyrukta bekleyen retler açık pencereyi eziyordu (yalnız son
    kitap istisnayla verilir, öbürleri raftan kayıtsız çıkabilirdi). Pencere açıkken
    kuyruk bekler; odak yazı alanında değilse okuyucunun kodu kutunun tamponuna alınır
    (okutmanın ortasında açılan pencere kodu ikiye bölmez) ve pencere kapanınca
    sırayla işlenir; her kitap kendi penceresini alır. Pencere kitabı yazar ("Kitap:
    …"). Pencere açıkken 60 sn bağlam süresi işlemez.
23. **§7.3 — istem yarışı, durum sorgusu sesi, ilk odak.** "İade al ve ödünç ver"
    bağlamı düğmeye basıldığı an yakalar; iade sürerken bağlam değiştiyse ödünç
    verilmez ve söylenir. Durum sorgusu ödünçten ayrı bir sesle (iki kısa ton) biter;
    üye kartı okutulunca "Yalnız durum sor" kendiliğinden kapanır. Ortak `ui/Dialog`
    açılışta odağı panele aldığı için çocuktaki `autoFocus` etkisizdi (kartsız ödünç,
    yönetici kipine geçiş ve Çık pencereleri); React `autoFocus`'u Dialog'un açılış
    efektinden ÖNCE uyguladığı için Dialog açan öğe yerine alanın kendisini kaydediyor,
    kapanışta odak geri verilemiyordu. *(25.09.2026)* `ui/Dialog`'a geriye uyumlu
    `initialFocusRef` özelliği eklendi (KS kitinden bilinçli ve yalnız ekleyici sapma;
    F1'de `ConfirmProvider`'a ve F3'te `TextField`'a yapılan eklerin kalıbı): açan öğe
    önce kaydedilir, sonra verilen alan, o yoksa panel odaklanır; özellik verilmezse
    davranış KS'dekiyle aynıdır. Yönetici kipine geçiş, Çık, Parolayı değiştir,
    kurtarma anahtarı yenileme ve kartsız ödünç pencerelerinde açılışta alan odaktadır
    (testli); kartsız ödüncün `setTimeout`'lu yerel kancası kalktı. `ui/Dialog`
    kullanan dosyada `autoFocus` kaynak taramasıyla yasaktır (`ui/Dialog.test.tsx`).
24. **§3, E13 — aydınlatma metni.** Saklama maddesi TB16'nın bugünkü kapsamını söyler:
    okuldan ayrılan kişilerin kayıtları üye olsunlar olmasınlar süresiz kalır;
    geri yüklemede kenara alınan önceki veritabanı da anılır. "Veriler şifreli durur"
    cümlesi TB1'e göre düzeltildi (ad, okul no, kart no ve gerekçeler şifreli; sınıf,
    üye türü ve ödünç tarihleri düz). Görevlinin, okuttuğu kitabın o üyede olup
    olmadığını gördüğü yazıldı (madde 26).
25. **Md. 20, §9-1 — kart notu ve pusula dış yüzü.** Md. 20 konum kalıbı yalnız öğrenci
    ve öğretmen kartına basılır (Md. 20/1 kartı ikisine öngörür); diğer personelin
    kartında atıfsız not vardır. Pusulanın katlanınca dışta kalan teslim notu
    kütüphaneyi anmaz ("Kişinin kendisine elden verilir; sınıfta okunmaz."); şeridin
    tam metni testle sabittir, kılavuz ve sözlük dış yüzü gerçeğe göre yazar.
26. **Görevli kipinde "bu üyede / başka üyede" ayrımı KORUNUR (kullanıcı kararı,
    25.09.2026).** Madde 14'ten sonra ayrım yalnız engeli olmayan üyede kalır:
    görevli, kartını bildiği bir üyenin elindeki kitapları barkod deneyerek yine
    öğrenebilir (kitap adları durum sorgusundan zaten açıktır, kimde olduğu değil;
    gecikme bilgisi bu yoldan açılmaz). Tam kapanış görevli kipinde TEK ret kodu olurdu ("Bu kitap ödünçte.
    Önce iade alınsın mı?" + yalnız "İade al"); bu, §7.3 tablosunun görevliye verdiği
    "başka üyede → iade + uyarı" akışını değiştireceği için uygulanmadı. Kullanıcı
    §7.3'ün aynen kalmasına karar verdi; kalan risk TB34'tür (azaltmalar: engelli
    üyede ayrım görünmez, GA-7 kart denetimi, görevlilerin yazılı görevlendirilmesi,
    masa kartındaki gizlilik uyarısı). Aydınlatma metni bugünkü davranışı söyler.
    Ayrıca `kip_sureleri()` hâlâ A10 sabitlerindedir (F2 ekleri 1'in "F6'da
    bağlanacak" notu F7'ye devredildi). *(F7'de bağlandı — F7 ekleri 10.)*

**F7 ekleri (25.09.2026).** F7'de tasarımdan bilinçli sapmalar ve tasarımda yazmayan
kararlar. Dört iş kolunda (teslim ve kayıp/hasar çekirdeği; ilişik, yıl akışları ve
F7 evrakı; teslim ve kayıp/hasar ekranları; kılavuz) yapıldı, ardından
bütünleştirildi; bütünleştirme sonrası denetimin düzeltme turu madde 14-25'tedir, düzeltme
turunda kullanıcıya bırakılan kararın sonucu madde 26'dadır. Kod kapısı (§14.1 F7 satırı) ve `bash scripts/gates.sh` yeşildir;
yıl sonu akışı sentetik veriyle uçtan uca sınanır
(`apps/kutuphane/tests/test_yil_sonu_uctan_uca.py`). **D3 kapandı** (§13; madde 3).
Okuyucuyla toplu teslim, görevli kipinde geri alma okutması ve F7 belgelerinin gerçek
yazıcıdan çıktısı saha denemesidir (F12).

1. **§6.2 — modeller ve tek göç** (`0006_teslim_kayip_onarim`). `Delivery`: şube XOR
   öğretmen (`recipient_kind` kişisizdir ve bağ koparıldıktan sonra da kalır; sayımda
   iki tür ayrı işlem görür — AT-1); açık teslimde alan boş olamaz ve PROTECT'tir,
   kapanmış teslimde kısıt boş alana izin verir (F11 bağı açık güncellemeyle koparır,
   `on_delete`'e güvenilmez); bir nüshada tek açık teslim (kısmi teklik); kapanış
   zamanları durumla DB kısıtında; belge no zorunlu. `LossDamageCase`: nüsha PROTECT,
   üyelik/ödünç/teslim SET_NULL; `responsible_note` şifreli; `market_price` yalnız
   kayıt; nüsha başına tek açık dosya; `write_off_proposed_at` yalnız öneri taşıyan
   çözümlerde (DB kısıtı). **Yeni** `CopyRepair`: kişisiz, serbest metin alanı yok,
   nüsha başına tek açık onarım; E9 onarım sayısının kaynağı. `Loan`'a
   `LOST_CONVERTED` ("Kayba dönüştü") ve `lost_at`. **Ödünç ile teslim arasındaki tek
   açık kayıt** (§9-7) iki tabloya yayıldığı için tek DB kısıtıyla yazılamaz; güvence
   nüsha durumunun koşullu güncellenmesidir ("Rafta"dan çıkışı yalnız biri kazanır —
   `services.nusha_durumu`; eşzamanlı yarış testi dahil).
2. **§9-9 — çözüm durumları** (OYS `CaseResolution` UYARLA). Başlangıç durumu "Çözüm
   bekliyor" ve sekiz seçilebilir çözüm: Bedel belirlendi · Bedel teslim alındı · Bulundu ·
   Aynısı temin edildi · Onarıldı · Bedelle aynısı alındı · Bedelle başka eser alındı ·
   Kayıttan düşme önerildi; onuncu durum "Kayba dönüştü" düğme değildir (madde 15). OYS'nin
   `WRITTEN_OFF`'u **alınmadı**: kayıttan düşme TMY işlemidir (F8/F9); burada
   "Kayıttan düşme önerildi" ve "Bedelle başka eser alındı" yalnız öneri işareti
   koyar, nüshanın durumu değişmez. "Onarıldı" OYS'de yoktu (D3). Açık sayılanlar
   "Çözüm bekliyor", "Bedel belirlendi" ve "Bedel teslim alındı"dır: **bedel adımları
   dosyayı kapatmaz** (Md. 19: önce temin; olmazsa bedelle aynısı ya da başka eser).
   Kişinin açık işi yalnız ilk ikisidir: "Bedel teslim alındı"da kişi İlişik
   Listesi'nden çıkar, dosya okulun açık işi olarak kalır (madde 26; madde 18'deki
   açık karar bununla kapandı). Bedel yolları yalnız
   ortaöğretimde; kademe seçilmemişse kapalıdır (fail-closed), kademe sonradan
   değişirse açık dosyada bedel yolu kapanır — bedeli teslim alınmış dosyanın iki
   kapanış yolu hariç (madde 26). Kapı servistedir; yanıttaki
   `allowed_resolutions` ve `price_options_available` yalnız ekrana hangi düğmelerin
   konacağını söyler.
3. **D3 — onarım ve hasar.** "Onarıma gönder" / "Onarımdan dön": Rafta ⇄ Onarımda, her
   gidiş bir `CopyRepair` kaydıdır. Hasar dosyası yalnız kütüphanedeki nüshaya açılır
   (ödünçteki önce iade alınır, teslimdeki önce geri alınır; sorumlu, iadesi alınmış
   ödünç ya da geri alınmış teslimle gösterilir). **Dosya açılışı nüshayı dolaşımdan
   çıkarmaz** (kitap okunabilir olabilir; "Nüshayı onarıma da gönder" isteğe bağlıdır);
   onarımdan dönüş dosyayı kendiliğinden kapatmaz. Kayıp bildirimi ödünçteki nüshanın
   ödüncünü, teslimdeki nüshanın teslimini "Kayba dönüştü" ile kapatır (kapanan ödünç
   sayı sınırına ve gecikmeye sayılmaz; yükümlülük dosyadır); "Bulundu" nüshayı rafa
   döndürür, ödünç ya da teslim yeniden açılmaz. Onarımdaki nüshaya kayıp bildirilmez
   (önce onarımdan dönüş işlenir). Açık hasar dosyalı nüsha kaybolursa madde 15;
   öneriyle kapanan kayıp dosyasında kitap bulunursa madde 14.
4. **§9-10, D4 — TMY 32/3 kapı noktası.** Kayıp bildirimi ve dosya çözümü
   `services.tmy_kapisi.ensure_open`'dan geçer; kapı F7'de boştur, F9 doldurur (iki
   yolun kapıyı sorduğu testlidir). Dosya çözümünde kapsam madde 17'dedir.
5. **§9-11, U11 — toplu teslim.** Alan etkin ders yılının şubesi ya da aktif öğretmendir;
   diğer personele teslim yapılmaz (fail-closed). Toplu teslim TEK işlemdir (bir kitap
   reddedilirse hiçbiri; gerekçeler kitap kitap döner), bir listede en çok 500 nüsha.
   Belge no verilmezse program `<yıl>/<sıra>` biçiminde verir, kullanılmış numara
   tekrar verilmez; beklenen dönüş boşsa ders yılının son günüdür. Beklenen dönüşün
   geçmesi gecikme değildir (yalnız rozet). Teslim alanın ödünç hakkı düşmez, Md. 18
   sayı sınırı uygulanmaz (testli). Geri alma okutmayladır: tek okutma `{barcode}`,
   okuyucu kuyruğu `{barcodes}` (en çok 200); geri alma hiçbir durumda kilitlenmez.
6. **§4.4 — görevli yüzeyi.** İzin listesine yalnız `library-delivery-take-back` POST
   girdi; görevli yanıtı sonuç, ileti, barkod ve eser adından ibarettir (teslim alanın
   kimliği, belge no ve tarih yok; alan listeleri anlık görüntüyle sınanır). Teslim
   verme, teslim listesi, kayıp/hasar dosyaları, onarım, ilişik ve yıl akışları uçları
   görevliye kapalıdır. Masada teslimdeki kitap okutulunca "Sınıf kitaplığında."
   altında "Teslimden geri al" önerisi çıkar (görevli kipinde de; kime teslim
   edildiği yazmaz).
7. **§8.3 — ilişik listesi.** Açık iş: iade edilmemiş ödünç, geri alınmamış teslim
   (yalnız öğretmende; şube teslimi kişiye bağlı değildir ve listede ayrı "Sınıf
   Kitaplıkları" tablosunda durur) ve çözülmemiş kayıp/hasar dosyası. Sıra: son sınıf
   (kademenin son sınıfı 4 · 8 · 12; kademe seçilmemişse kimse) → okuldan ayrılan →
   diğerleri. **"Nakil gidenler" programda "okuldan ayrılan" grubudur**: ayrılmış ya da
   Ayrılış Havuzunda karar bekleyen kişi; nakil ile başka ayrılış ayrı tutulmaz.
   Toplama görünümü yalnız toplanacak kitabı olanları gösterir (yalnız dosyası olan kişi
   ilişikte vardır, toplamada yoktur). Okul no araması kör indeksle tam eşleşmedir.
   Basılı ilişik listesi kaynak adı ve okul no basmaz.
8. **E5 — "Kütüphaneden ilişiği yoktur" belgesi** yalnız açık işi olmayan kişiye, kişi
   başına bir sayfa, tek seferde en çok 150; açık işi olan seçilirse ad yazmayan, sayılı
   ret (400). Metin konum kalıbını ve Md. 18 alıntısını taşır; "karne", "diploma",
   "borç" belgede, ekranda ve kılavuzda geçmez (testli). §3'teki "Bakanlık sistemi
   kullanımda" hatırlatması F10 ayarına bağlıdır, bu fazda yoktur.
9. **§8.3 — yıl akışları.** Yıl Sonu ve Yıl Başı ekranları kayıt yazmaz; işin yapıldığı
   uçları ve ekranları kullanır, durumları kişisiz `library/year-flows/` özetinden
   okur. Yıl sonu penceresi 1 Mayıs - 30 Haziran (ders yılı daha geç biterse bitişten
   14 gün sonrasına dek); yıl başı penceresi 15 Ağustos - 31 Ekim ya da ders yılı
   başlangıcından 21 gün önce ile 42 gün sonrası. Yıl başının "e-Okul listesi bu yıl
   aktarıldı" ölçütü: son tamamlanmış aktarım ders yılı başlangıcından en çok 45 gün
   önce yapılmış olmalı. Yıl sonu pusulası kişinin BÜTÜN açık ödünçlerini taşır (E4
   biçimi), tek seferde en çok 150 kişi ("şube şube basın"); "son getirme günü"
   pusulaya yazılır, kaydedilmez. Yıl başına üyelik istek listesi ve kart basımı adımı
   konmadı (üyelik isteğe bağlıdır; istenirse beşinci, isteğe bağlı adım olur).
10. **F2 ekleri 1 — kip süreleri bağlandı.** `kip_sureleri()` kütüphanenin
    `AppConfig.ready` içinde kaydettiği sağlayıcıdan okur (bağımlılık yönü kütüphane →
    okul; `persons` kayıt defterleriyle aynı kalıp). Değer süreç içinde önbelleğe
    alınır, ayar yazılınca boşaltılır: sıcak yolda sorgu yoktur. Sınırlar 1-15 ve
    5-120 dakikadır (tek kaynak model sabitleri), boşta süresi mutlak süreyi aşamaz (DB
    kısıtı); anlamsız değer ya da okunamayan veritabanı varsayılana (3 / 30 dk) düşer.
    Alanlar Kütüphane Politikası → Yönetici Kipi Süreleri'ndedir; değişiklik bir sonraki
    işlemden geçerlidir.
11. **E6, E15 — evrak.** Teslim listesi (şubede Dayanıklı Taşınırlar Listesi işlevi —
    TMY 23/6'ya kıyasen) ve geri alma dökümü; belge no ve teslim tarihi `Delivery`'de
    tutulur, `BelgeIzi` F11'dedir. Kayıp/hasar tutanağında sorumlunun adı şifreli
    alandan çözülür; Md. 19 alıntısı ve "Bu tutanak bir ödeme ya da tahsilat belgesi
    değildir." satırı yalnız ortaöğretimde basılır.
12. **§5.10-4/5 yeniden koştu.** `kutuphane_delivery`, `kutuphane_lossdamagecase` ve
    `kutuphane_copyrepair` katalog authorizer'ında reddedilir (görünümden bile); teslim
    alan, belge no, sorumlu notu ve bedel hiçbir katalog sayfasında geçmez. Katalog
    teslimdeki nüshayı (öğretmene teslim dahil) "Sınıf kitaplığında" sayar; kayıp nüsha
    görünmez, onarımdaki "onarımda" sayılır.
13. **Açık yükümlülük ve silme.** Açık teslim ve çözülmemiş dosya kişi kayıt
    defterlerine (`apps/okul/services/persons.py`) açık yükümlülük olarak bağlandı:
    kişi silinemez, ilişik listesine girer; çözülmüş dosya yükümlülük değildir.
    **Kendisine (kapanmış da olsa) teslim yapılmış personel silinmez** — teslim satırı
    alanı PROTECT ile tutar; kapanmış teslimin bağını kullanıcının "Sil"i değil F11
    saklama taraması koparır (ileti "Okuldan ayrıldıysa “Ayrıldı olarak işaretle”
    eylemini kullanın."). Personel birleştirmede kaynağın bütün teslimleri hedefe
    taşınır (açık teslim yalnız öğretmene — madde 20). Açık teslimi olan şube silinemez
    (şube tesliminden doğan çözülmemiş dosya da — madde 19).

**Düzeltme turu (25.09.2026).** Bütünleştirme sonrası denetimin bulguları (mevzuat, veri
bütünlüğü, evrak ve arayüz mercekleri) Docker sondalarıyla yeniden doğrulandı; hepsi
gerçekti. Kök nedenden düzeltildi ve testle kilitlendi; biri (madde 18) karar olarak
korunup kullanıcıya bırakıldı, kullanıcı 25.09.2026'da karar verdi (madde 26). Düzeltme
turunun tasarımdan iki sapması — dokuzuncu çözüm durumu "Kayba dönüştü" (madde 15) ve TMY
32/3 kapısının dosya çözümündeki daraltılmış kapsamı (madde 17) — ana oturumca
**onaylandı** (25.09.2026).

14. **Öneri geri alınabilir** (bulgu: öneri fiilen geri alınamaz bir karar gibi
    işliyordu). "Kayıttan düşme önerildi" ile kapanmış KAYIP dosyasında nüsha hâlâ
    "Kayıp"sa `allowed_resolutions` yalnız "Bulundu"yu verir: öneri kalkar
    (`write_off_proposed_at` boşalır, F8/F9 kuyruğundan düşer), nüsha rafa döner, ödünç
    ya da teslim yeniden açılmaz (`loss_damage.oneri_geri_alinabilir`). "Bedelle başka
    eser alındı"da bu yol YOKTUR (Md. 19: "kaybedilenin kaydı silinerek başka eser satın
    alınır"); onay metni ve kılavuz bunu söyler, bilinen sınır (h). Nüsha asıl kayıttan
    düşülmüşse yol kapanır.
15. **Açık hasar dosyalı nüsha kaybolursa** (bulgu: kayıp bildirilemiyor, ödünç açık
    kalıp sayı sınırına ve gecikmeye sayılıyordu; tek çıkış dosyayı gerçeğe aykırı bir
    çözümle kapatmaktı). Hasar dosyası nüshayı dolaşımdan çıkarmadığı için (madde 3)
    kayıp bildirimi açık HASAR dosyasını aynı işlemde **"Kayba dönüştü"**
    (`CONVERTED_TO_LOSS`) ile kapatır ve kayıp dosyası açar; ödünç ya da teslim her
    zamanki gibi kayba dönüşür. Hasar dosyasının sorumlusu, notu ve kaydedilmiş bedeli
    kendi kaydında kalır; kaybın sorumlusu ödünçten ya da bildirimden gelir. Yeni durum
    kullanıcı seçimi değildir (servis reddeder) ve DB kısıtıyla yalnız hasarda durur;
    yayınlanmamış tek göç `0006_teslim_kayip_onarim`'a işlendi. "Açık hasar dosyalı nüsha
    ödünç ya da teslim edilmez" seçeneği madde 3'le çeliştiği için alınmadı. *(Tasarımdan
    sapma olarak ONAYLANDI — ana oturum, 25.09.2026. Madde 26'yla durum sayısı ona çıktı;
    "Kayba dönüştü" yine düğme değildir. Bedeli teslim alınmış hasar dosyası da kayba
    dönüşebilir: iki adımın kaydı o dosyada kalır.)*
16. **Kişi bağı tek kural** (bulgu: öğretmene teslimde üye seçilen dosya kayıt defterinde
    öğretmende, ilişik listesinde öğrencide görünüyordu; öğretmene E5 basılabiliyordu).
    Kural: önce üyelik, üyelik yoksa teslim alan öğretmen
    (`selectors_teslim.case_person`). `open_cases_for_person` ve
    `persons_with_open_cases` aynı kurala çekildi; kayıt defteri, ilişik listesi, E5 ve
    E6 aynı sonucu verir (tutarlılık testi `TestKisiBagiTutarliligi`). Kayıp penceresi
    teslimdeki kitapta üye seçilirse dosyanın o üyeye bağlanacağını söyler.
17. **TMY 32/3 kapsamı çözüm türüne göre** (bulgu: kapı "Onarıldı"yı ve bedel kaydını da
    kapsıyor, kapının kendi "onarım kapsam dışı" kuralıyla çelişiyordu).
    `tmy_kapisi.dosya_cozumu_kapsamda_mi(tür, çözüm)`: kayıp dosyasında iki bedel adımı
    ("Bedel belirlendi", "Bedel teslim alındı" — madde 26) dışındaki bütün çözümler, hasar
    dosyasında yalnız kayıttan düşme önerisi yazanlar kapsamdadır; `resolve_case` kapıyı
    yalnız bunlarda sorar. `ensure_open` imzası değişmedi. §14.1 F9 satırındaki "dosya
    çözümü" bu kapsamla okunur (F9 sözleşmesi sabitler). *(Daraltılmış kapsam tasarımdan
    sapma olarak ONAYLANDI — ana oturum, 25.09.2026; kapsamın son biçimi F9 sözleşmesine
    devredildi.)*
18. **"Bedel kaydedildi" açık iştir; karar korundu** (bulgu: kişinin ilişiği okulun satın
    almasına bağlanıyor). Madde 2'nin kararı değişmedi; sonucu madde 2'ye ve kılavuza
    açıkça yazıldı. Md. 19/1'in ikinci cümlesini okulun işi sayıp dosyayı açık tutarken
    kişiyi ilişikten ayırmak bir kullanıcı kararıdır. *(Karar verildi — 25.09.2026:
    bedel iki adıma ayrıldı; "Bedel teslim alındı"da kişi ilişikten ayrılır, dosya okul
    için açık kalır. Ayrıntı madde 26.)*
19. **Şube silme engeli dosyayı da sayar** (bulgu: şube tesliminden doğan çözülmemiş
    dosya varken şube silinebiliyor, ilişik listesi silinmiş şubeyi gösteriyordu).
    `section_delete_obstacles` üyeliksiz ve şube tesliminden doğan çözülmemiş dosyaları
    da sayar ("Bu şubenin tesliminden doğan N çözülmemiş kayıp/hasar dosyası var; önce
    dosyayı çözün."); süzgeç tek kaynaktan (`selectors_teslim.section_case_q`).
20. **Birleştirmede açık teslim yalnız öğretmene** (bulgu: açık teslim "diğer personel"e
    taşınıyor, E15 onu "Öğretmen" diye basıyordu). Kaynağın açık teslimi varsa ve hedef
    öğretmen değilse birleştirme gerekçeyle reddedilir; tek işlem olduğu için hiçbir bağ
    taşınmaz. Kapanmış teslimler türüne bakılmadan taşınır.
21. **E6 sayfa bütçesi** (bulgu: gerçek uzunluktaki veride imzalar tek başına ikinci
    sayfaya düşüyordu; test kısa yazar ve tek satırlık notla yanlış yeşil veriyordu).
    Sorumlu notunun satır sonları tutanakta boşluğa iner; ÇÖZÜM bölümü, Md. 19 alıntısı ve
    imzalar tek bölünmez kutudadır; aralıklar daraltıldı. Sayfa bütçesi testi en uzun okul
    ve kişi adı, çeviri künyeli yazar, 64 karakterlik TKYS kodu, 40 karakterlik belge no ve
    satır satır 500 karakterlik notla, ödünç ve öğretmen teslimi yolunda, ortaöğretim ve
    ilkokulda tek sayfa ister. Alan sınırındaki veride bilinen sınır (i).
22. **Geri alma dökümü belge no ile** (bulgu: döküm yalnız o anki okutma oturumundan
    basılabiliyordu; görevli kipinde ya da masada geri alınanların dökümü alınamıyordu).
    Teslim Kayıtları'nda belge no'ya tıklayınca çıkan kartta "Geri alma dökümü" bölümü
    `{document_no}` ile belgenin bütün satırlarını durumlarıyla basar (sunucu yolu F7'de
    vardı, ekrana bağlandı).
23. **Yeni Teslim okutması** (iki bulgu). Ret iletisi kitabın numarasını ve adını taşır;
    reddedilen kitaplar sonraki başarılı okutmada silinmeyen "Listeye girmeyen kitaplar"
    listesinde durur (aynı kitap listeye girince çıkar). Okutma kutusunun odak uyarısı
    açıldı (odak "Şube" seçicisindeyken okutulan kod kaybolur ve şube seçimini
    değiştirebilir); öğretmen seçilince odak kutuya döner. "Şube" seçicisinde odak
    kendiliğinden geri alınmaz: ok tuşlarıyla seçim yapan kullanıcının seçimini keserdi.
24. **Kayıp ve Hasar sayfası** (iki bulgu). Sayfa açıklaması sözlükteki "açık iş"
    terimini kullanır ("yükümlülük" F7 ekranlarında ve kılavuzda kullanıcı metnine
    girmez; test). "Çözüm" süzgeci bedel yollarını yalnız ortaöğretimde listeler; kademe
    kapısının yansıması liste yanıtının `price_options_available` alanıdır (liste boşken
    de gelir), ekran kademeyi kendisi yorumlamaz.
25. **Kitap Toplama başlığı görünür** (bulgu: kılavuz ve sözlük ekranda görünmeyen tablo
    adını kullanıyordu). "Toplanacak kitaplar" artık adımın görünür alt başlığıdır.

**Kullanıcı kararı (25.09.2026).**

26. **Md. 19 bedel adımı ikiye ayrıldı** (madde 18'in açık kararı). Ortaöğretimde kayıp ya
    da hasar dosyasının bedel yolu iki kayıttır; program tahsilat YAPMAZ, yalnız kaydeder
    (dil "bedel belirlendi", "bedel teslim alındı" — borç, ceza, tahsilat yok):
    - **"Bedel belirlendi"** (`PRICE_DETERMINED`; eski "Bedel kaydedildi"): o günkü piyasa
      bedeli ve adımın zamanı (`price_determined_at`) kaydedilir. Kişinin açık işi SÜRER:
      İlişik Listesi'nde kalır, E5 basılmaz, kişi silinemez. Bedel bu adımda yeniden
      belirlenerek düzeltilebilir; bulunma, temin ve öneri yolları açık kalır.
    - **"Bedel teslim alındı"** (`PRICE_RECEIVED`): yalnız "Bedel belirlendi"den gelinir;
      adımın zamanı (`price_received_at`) kaydedilir. Kişinin açık işi BİTER: İlişik
      Listesi'nden çıkar, "Kütüphaneden ilişiği yoktur" belgesi basılabilir, kayıt
      defterinde yükümlülük sayılmaz (şube tesliminden doğan dosyada şubenin açık işi de
      biter). Dosya **okul için AÇIK kalır** (nüsha başına tek açık dosya; Kayıp ve Hasar
      ekranının "Çözülmemiş dosyalar"ında satırın altında "Okulun açık işi") ve yalnız
      "Bedelle aynısı alındı" ya da "Bedelle başka eser alındı" ile kapanır; bu ikisi
      artık yalnız bu adımdan sonra seçilir. Adım geri alınmaz, teslim alınan bedel
      değiştirilmez. Kademe sonradan ortaöğretimden çıksa da bu iki kapanış yolu açık kalır
      (alınmış bedelin kullanımı kaydedilmeli; dosya kilitlenmez).
    - Kodda iki küme ayrıldı: `OPEN_CASE_RESOLUTIONS` (dosya açık — okulun işi) ve
      `PERSON_OPEN_RESOLUTIONS` (kişinin açık işi: "Çözüm bekliyor", "Bedel belirlendi").
      Kayıt defteri (`open_case_obligations`), `open_cases_for_person` /
      `persons_with_open_cases`, şube engeli (`open_cases_for_section`), ilişik listesi,
      E5 basılabilirliği ve yıl akışı sayıları ikinciye bakar. Serileştirici
      `is_person_open_work`, `price_determined_at` ve `price_received_at` taşır. DB
      kısıtları: bedel ile belirlendiği zaman birlikte; teslim zamanı yalnız teslim alınmış
      bedel yolunda (ve orada zorunlu; "Kayba dönüştü" hasar dosyası önceki kaydını
      taşıyabilir). Yayınlanmamış tek göç `0006_teslim_kayip_onarim`'a işlendi.
    - **TMY 32/3**: iki bedel adımı da kapıdan geçmez (bedelin belirlenmesi ve teslim
      alınması TMY'de giriş-çıkış değildir; madde 17 ile tutarlı).
    - **E6**: piyasa bedeli satırı iki adımın tarihlerini taşır ("… TL (kayıt);
      gg.aa.yyyy tarihinde belirlendi, gg.aa.yyyy tarihinde teslim alındı"; tek satır —
      sayfa bütçesi testi en uzun yolda iki adımla koşar). **E5** hükmü "çözülmemiş kayıp ya
      da hasar kaydı" yerine "kayıp ya da hasar nedeniyle kendisinden beklenen bir işlem"
      der: bedeli teslim alınmış dosya okul için açıktır ama kişinin işi değildir.
    - Testler: `TestBedelIkiAdim` (ilişik, kayıt defteri, toplu soru ve E5 tutarlılığı;
      öğretmen ve şube teslimi; kademe kapısı — ilkokul ve ortaokulda iki adım da yok; DB
      kısıtları), uç, E5 ucu, E6 ve yıl sonu uçtan uca testleri; kılavuz ve sözlük §4.12.

*Bilinen sınırlar (F7 sonunda açık).* (a) Rafta duran hasarlı nüsha için "Kayıttan
düşme önerildi" seçilse de nüsha ödünç verilebilir kalır (öneri ≠ onay, OYS'de de
böyle); ekran raftan ayırmayı önerir, asıl işlem F8 ayıklamasıdır. (b) Eski veriden
gelen, kaydı olmayan "Onarımda" nüsha "Onarımdan dön" ile rafa döner ama `CopyRepair`
kaydı oluşmaz (E9 onarım sayısına girmez). (c) Onarımcıda kaybolan kitap için ayrı yol
yoktur (önce onarımdan dönüş işlenir). (d) Görevli kipinde masa teslimdeki kitabı
sunucunun "Sınıf kitaplığında." iletisinden tanır; ileti değişirse öneri kaybolur
(daha sağlam yol: görevli yanıt alanlarına kişisiz bir teslim bayrağı). (e) Üye
bağlamı açıkken okutulan teslimdeki kitaba "Teslimden geri al" önerisi çıkmaz. (f)
"Aynısı temin edildi"den sonra gelen kitabın etiketini tek nüsha olarak yeniden basmanın
yolu yoktur (Basım Geçmişi'ndeki "Yeniden bas" bütün partiyi basar). (g) 60'tan uzun
teslim listesinde son sayfaya yalnız not ve imza düşebilir. (h) "Bedelle başka eser
alındı" ile kapanan kayıp dosyasında kitap sonradan bulunursa rafa dönüş yolu yoktur (Md.
19 bu yolda kaybedilenin kaydının silinmesini ister); nüsha F8 ayıklamasında ele alınır.
(i) Kayıp/hasar tutanağı alan sınırındaki veride (500 karakterlik kaynak adı ve yazar)
iki sayfa olur; ÇÖZÜM, Md. 19 alıntısı ve imzalar birlikte ikinci sayfaya geçer.

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
| S8 | Kitap sayısı, mevcut listeler (Excel var mı, sütunlar) · kitaplarda **eski kayıt/demirbaş no** var mı · TKYS nüsha bazında mı — **CEVAPLANDI (23.09.2026):** TKYS'de nüsha bazında kayıt fiilen tutulmuyor (alan isteğe bağlı kalır, §6.2) · okulda **hazır Excel listesi yok** (yöntem B asıl yol olur, §8.1) · ölçek **1.000-10.000 kitap**, fazlası nadir (F3 ölçüm kapısı 10.000 satır) | Kullanıcı |
| S9 | **Geriye dönük dönüşüm planı:** kim, hangi takvim (yarıyıl ya da yaz), raf sırası, etiket stoğu, doğrulama okutması | Kullanıcı + komisyon |
| S10 | **Kütüphane masası Windows hesabı** (yönetici yetkisi olmayan) + BitLocker | BTR |
| S11 | Yönetici parolasının **en az iki görevlendirilmiş kişide** olması · kurtarma anahtarının müdürlükte zarfta saklanması | Kullanıcı + müdür |
| S12 | Kütüphane bilgisayarının demirbaş kaydı | Kullanıcı |
| S13 | UPS önerisi (elektrik kesintisi) | Okul yönetimi |
| S14 *(23.09.2026)* | **Bakanlık kataloğu ucunun kullanım izni ve atıf kuralı** için Kültür ve Turizm Bakanlığı Kütüphaneler ve Yayımlar Genel Müdürlüğü'ne yazılı soru: (a) 210 portundaki SRU ucu okul kütüphanelerince kullanılabilir mi, (b) belgeli ve kalıcı bir uç ile atıf/lisans koşulu var mı. Uç bugün belgesizdir (§8.5, TB20); yanıt gelene kadar yalnız tek tek sorgu yapılır, toplu indirme ve yeniden dağıtım yapılmaz | Kullanıcı |
| S15 *(23.09.2026)* | **İki adresin okul ağından erişilebilirliğini BTR ile sınama** (§8.5 künye getirme buna bağlıdır): `Test-NetConnection koha.ekutuphane.gov.tr -Port 210` ve `Test-NetConnection openlibrary.org -Port 443`. Geçmezse erişim talebi Yardım Masası'ndan açılır (Yönerge 11/12); hiç açılmazsa yalnız çevrimdışı dosya yolu kalır. Komutlar BTR bilgi notunda ve kurulum kılavuzunda verilir | Kullanıcı + BTR |

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
