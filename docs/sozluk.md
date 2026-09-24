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
| `Work.title` | **kaynak adı** | kitap adı, eser adı (form etiketi olarak) | Yönetmeliğin terimi (Md. 11/1 "kaynak adı"). Excel şablonundaki sütun adı **Eser Adı**'dır, orada korunur |
| `Work.resource_type` | **kaynak türü**: Kitap · Süreli yayın · Görsel-işitsel materyal · E-kitap · E-veri tabanı | tür (tek başına), format, materyal türü | E-kitap ve e-veri tabanında **nüsha açılmaz**; süreli yayın ödünç verilmez (Md. 16/1-c) |
| `Work.isbn`, `isbn13` | **ISBN** | barkod (ISBN anlamında), kitap numarası | Sağlama hatası kaydı ENGELLEMEZ: numara olduğu gibi saklanır, ekranda **"ISBN uyarısı"** bandı durur. Kitabın arkasındaki 13 haneli 978/979 kodu **ISBN barkodu**dur, kütüphane etiketi değildir |
| ISBN'den künye doldurma (U13, F3) | ayarın adı **"ISBN ile künye getirme"** (Kütüphane Politikası → **Künye Getirme** bölümü, anahtar **"ISBN ile künye getirme açık"**); düğme **"Künyeyi getir"**; sonuç **künye önerisi**dir, rozeti **"Dış kaynaktan alındı, doğrulayın"** · yanında kaynak adı ve tarih yazılır ("Bakanlık kataloğu, 23.09.2026"); forma yazan düğme **"Seçilenleri forma yaz"** | "otomatik künye", "resmî künye", "Bakanlık sisteminden çekildi", "sorgula", "API" | Özellik varsayılan KAPALI'dır; kullanıcı onaylamadan hiçbir alan dolmaz, dolu alanın üzerine sessizce yazılmaz ve **çevirmen alanı dışarıdan doldurulmaz** (tasarım §8.5). Fail-open iletisi: "İnternetten getirilemedi, elle girebilirsiniz." Konum dili §3'e bağlıdır: program Bakanlık sisteminin yerine geçtiğini ima etmez |
| Künye kaynakları (§8.5) | **Bakanlık kataloğu** (ilk geçişte tam adıyla: "Kültür ve Turizm Bakanlığı halk kütüphaneleri kataloğu") · **Open Library** | "MEB kataloğu", "resmî katalog", "veri tabanı" (tek başına) | Kısa ad tek başına MEB'i çağrıştırabildiği için kılavuzda ve ayarda kurumun adı açık yazılır. Kullanıcıya söylenen: bu kayıtlar başka kurumların kataloğudur, okulun kaydı değildir ve **doğrulanır** |
| Geçiş yolları (tasarım §8.1) | **önce liste** · **önce etiket** ("okulun asıl yolu"); geçiş dönemindeki kâğıt kayıt **kâğıt defter** | yöntem A / yöntem B, retrospektif dönüşüm, geriye dönük katalog girişi (kullanıcı metninde) | Önce liste: Excel → İçe Aktarma → etiket basımı → raf raf yapıştırma → doğrulama okutması. Önce etiket: boş barkod aralığı ayır → boş etiketleri bas → kitaplara yapıştır → Hızlı Kayıt'ta künye + etiket okut → sırt etiketlerini bas → kullanılmayan numaraları iptal et. Etiketsiz kitap masaya gelirse Hızlı Kayıt + tek etiket; dönüşüm bitince kâğıt defter kapatılır |
| Toplu katalog aktarımı (`CatalogImportRun`) | **içe aktarma** (ekran: **İçe Aktarma**), tek çalıştırma **aktarım**; adımlar **"Önizle"** → **"Yeniden önizle"** → **"Uygula"**; geçmişte **"Önizlemeyi iptal et"** | import, yükleme (bu anlamda), senkronizasyon, "toplu kayıt" | Önizleme uygulamanın birebir provasıdır ve hiçbir kayıt yazmaz ("Önizleme — hiçbir kayıt yazılmadı"). **Aynı dosya ikinci kez uygulanamaz** — uyarı değil ENGELdir: "Bu dosya … tarihinde zaten aktarıldı." Toplu aktarımda dış istek yoktur |
| Eşleşme kovası (`bucket`) | satır durumları **Yeni eser** · **Mevcut esere nüsha** · **Şüpheli** · **Aktarılmadı**; şüpheli satırların listesi **"Karar bekleyen satırlar"**, seçenekler **"Yeni eser aç"** ve **"… eserine nüsha ekle"**; bilinmeyen bölümler **"Bölüm listesinde bulunmayan değerler"**, seçenek **"Yeni bölüm aç"** | çakışma, çift kayıt, hatalı satır (şüpheli anlamında), "eşleştirme skoru" | **Şüpheli satır** katalogdaki bir esere benziyor ama tam eşleşmiyor; kullanıcı karar vermeden aktarım yazmaz. Bölüm değeri karşılıksızken de yazmaz (değer kaybolmasın) |
| Yapay zekâ köprüsü (§8.2) | **Yapay Zekâ Köprüsü** (sekme); **komut metni**, düğme **"Komutu kopyala"**; girdi kutusu **"Yapay zekâ aracının verdiği JSON"** | AI, "yapay zeka" (düzeltme işareti düşürülmez), "yapay zekâyla kataloglama", asistan | İsteğe bağlıdır ve asıl yol Excel'dir. **Program hiçbir yapay zekâ servisine bağlanmaz**, metni kullanıcı taşır; **listeye kişisel veri yazılmaz**. Ekrandaki dört uyarı maddesi sunucudan gelir |
| Çevrimdışı künye (U13) | **Çevrimdışı Künye** (sekme); belge **ISBN Künye Listesi**; düğmeler **"ISBN listesini indir"** ve **"Seçilenleri kaydet"** | dışa aktarım (tek başına), "çevrimdışı kip", "offline" | İnternetsiz masanın yolu: liste **başka bir cihazda** doldurulur. Kurum bilgisayarına telefon, mobil modem ya da kişisel erişim noktası bağlanamaz (Yönerge 11/18); taşımada 10/4-10/5 geçerlidir. Dolu alan işaretsiz gelir, işaretlenmeyen alan yazılmaz |
| Katalog sıralaması (`WorkOrder`) | **"Sırala"** seçicisi: Kaynak adına göre · Yazar adına göre · Konuya göre · En yeni eklenen | alfabetik sıra (tek başına), A-Z | İlk üçü Md. 11/1'in katalog eksenleridir; sıralama Türkçe alfabeyedir |
| `Copy` | **nüsha** | kopya, demirbaş, materyal | Rafta duran fiziksel kitap. Masa iletilerinde gündelik "kitap" serbesttir: "Kitabın kütüphane etiketini okutun." |
| `Copy.barcode` | **barkod** (10 hane, basılı `2026-000123`) | etiket no, kod | Salt rakamdır |
| `Copy.accession_no` | **kayıt no** | demirbaş no, envanter no | Barkodun sayı hâlidir, tek sayaçtan gelir |
| `Copy.old_register_no` | **eski kayıt no** | eski barkod, defter sıra no | Kitaptaki eski damga ya da defter numarası; isteğe bağlı |
| `Copy.external_asset_ref` | **TKYS kodu** | demirbaş kodu, sicil (tek başına) | Taşınır kaydındaki karşılık |
| `SchoolConfig.demirbas_no` | **bilgisayarın demirbaş no'su** | — | "Demirbaş" yalnız bilgisayar için kullanılır (Yönerge 11/8) |
| Yer numarası (sırt etiketi satırları) | **yer numarası** | raf kodu, lokasyon, call number | Sınıflama / yazar kodu / cilt-nüsha |
| Kitaptaki barkod etiketi (okutma) | **kütüphane etiketi**; okutma kutularının adı **"Kütüphane etiketi"** (Hızlı Kayıt, Doğrulama Okutması) | kitap barkodu (ISBN barkoduyla karışır), demirbaş etiketi, etiket no | Kitaba yapıştırılan barkod etiketinin gündelik adıdır (basılı barkod etiketi ya da önce etiket yolunda boş barkod etiketi). Masa ve okutma iletileri onu **ISBN barkodu**ndan ve **üye kartı**ndan bu adla ayırır: "Kitabın kütüphane etiketini okutun." |
| Etiket türleri (`LabelPrintKind`) | **sırt etiketi** (yer numarası + okulun kısa adı) · **barkod etiketi** (barkod, okunur numara, yer numarası, kısaltılmış kaynak adı, okulun kısa adı) · ikisi birlikte **sırt ve barkod etiketi** · önce etiket yolunda **boş barkod etiketi** (yalnız barkod, okunur numara, kısa okul adı); seçicinin adı **"Etiket içeriği"** | künye etiketi, raf etiketi (sırt etiketi anlamında), sticker | Yer numarasının boşlukla ayrılmış parçaları sırtta alt alta basılır (en çok üç satır; yer numarası çıkarılamazsa "—"). "İkisi birden" basımda iki etiket **aynı sıra ve hücre düzeninde** çıkar; PDF'te önce sırt, sonra barkod tabakaları gelir. Sırtı dar kitapta sırt etiketi **ön kapağa, sırta yakın köşeye** yapıştırılır ve bütün ince kitaplarda aynı köşe kullanılır (tasarım §7.2 yalnız "ön kapağa" der; köşe dayatılmaz); **şeffaf koruyucu bant** önerilir. Barkod etiketi ISBN barkodunu örtmez. QR varsayılan kapalıdır ve yalnız barkod numarasını taşır |
| Etiket şablonu (`LabelSheetTemplate`) | **etiket şablonu** (tabakanın ölçüsü: etiket boyu, kenar boşlukları, sütun ve satır aralığı, satır × sütun); **etiket tabakası** ("65'li tabaka"); rozetler **Varsayılan** · **QR'a uygun** · **Barkod bu etikete sığmaz**; düğme **"Yeni şablon"** | sticker, etiket formu, kâğıt boyunun kısa adı (kullanıcı metninde), etiket sayfası (tabaka anlamında) | Hazır şablonlar: 38,1 × 21,2 mm 65'li (varsayılan barkod ve sırt tabakası), 48,5 × 25,4 mm 44'lü (adında "yaklaşık ölçü"), 52,5 × 29,7 mm 40'lı ("kenarsız"). Sayfa her şablonda 210 × 297 mm'dir. **QR kararı tabakayı belirler**: QR 65'li tabakaya sığmaz, satın alma bu karardan sonra yapılır (tasarım §7.2, S4). Ölçüler milimetreyle yazılır; kâğıt boyunun kısa adı iç kod taramasına takılır |
| Kalibrasyon (`LabelCalibration`) | **kalibrasyon** / **yazıcı kalibrasyonu** (şablon + yazıcı çifti); **kayma**: **"Yatay kayma (mm)"** (artı sağa) ve **"Dikey kayma (mm)"** (artı aşağı); belge **kalibrasyon sayfası** (§2 E1); ölçüm alanları **"Okunan yatay değer"** · **"Okunan dikey değer"**, düğme **"Kaymaya ekle"**; seçiciler **"Yazıcı (kalibrasyon)"** (basımda) ve **"Sayfaya uygulanacak kayma"** (kalibrasyon sayfasında) | ofset, offset, hizalama ayarı, yazıcı profili, yazıcı ayarı | Yazıcının kaydırması şablona değil kalibrasyona yazılır; her yazıcı ayrı kalibre edilir. Sayfa **gerçek boyutta (%100)** basılır (ortadaki çizgi 100 mm); köşe cetvelinde okunan değer (sağ ve alt taraf artı) kaymaya eklenir; kâğıt kenarına yakın cetvel, yazıcının basamadığı kenar payı yüzünden etiketin iç kenarına (yan etiketle arasındaki kesime) konur. Sayfadaki kayma satırı "yatay kayma" ve "dikey kayma" der. Kayma en çok ±10 mm'dir. Dört köşede farklı değer ölçek sorunudur, kayma değil |
| Başlangıç hücresi (`start_cell`) | **başlangıç hücresi** (alan **"Başlangıç hücresi"**); **tabaka ızgarası** (tabakanın küçük resmi; hücre adı **"12. hücre"**) | pozisyon, offset, konum no, ilk etiket no | 1'den başlar, **satır satır, soldan sağa** sayılır. Kısmen kullanılmış tabakada ilk boş hücre seçilir, öncekiler boş bırakılır. "Sırt ve barkod etiketi"nde iki tabakanın aynı hücresi aynı kitabındır |
| Basım kuyruğu | **Basım Kuyruğu** (sekme); satır durumu **Kuyrukta** · rozet **"Onay bekleyen partide"**; sayaçlar **"Sırt etiketi bekleyen"** · **"Barkod etiketi bekleyen"** | yazdırma kuyruğu (Windows'un yazıcı kuyruğuyla karışır), baskı kuyruğu, iş listesi | Etiketi basılmamış nüshalar. Nüsha açılınca kendiliğinden girer, "Basıldı olarak işaretle" ile çıkar, işaret geri alınınca döner. Onay bekleyen partideki nüsha kuyrukta kalır |
| Basım kaydı (`LabelPrintBatch`) | **basım partisi**; durumlar **Basım onayı bekliyor** · **Basıldı** · **Basım işareti geri alındı** · **Vazgeçildi**; eylemler **"Basım partisini hazırla"** · **"Basıldı olarak işaretle"** · **"Partiden vazgeç"** · **"Basım işaretini geri al"** · **"Yeniden bas"** · **"Önizle"** · **"PDF'i indir"** | yazdırıldı, etiketlendi (işaret anlamında), print, iş emri | **PDF'i almak "basıldı" saymaz**: "Önizle" ve "PDF'i indir" hiçbir işarete dokunmaz; işaret yalnız onay diyaloğundan geçen "Basıldı olarak işaretle" ile yazılır ve geri alınabilir. Geri alma işareti silmez, **bu basımdan önceki hâline** döndürür; barkodu okutularak doğrulanmış nüshanın işaretine dokunulmaz (sırt ve barkod etiketi partisinde sırt işareti de korunur, nüsha kuyruğa dönmez); nüshası sonradan başka partiyle yeniden basılmış parti, o parti hâlâ basılmış görünüyorsa önce o geri alınmadan geri alınamaz. Geri almanın iletisi kuyruğa dönen nüshayı, işareti önceki basıma dönen nüshadan ayırır. Partideki nüsha sonradan silinir ya da kayıttan düşülürse PDF'te **hücresi boş kalır** (sonrakiler kaymaz), onay ona dokunmaz, yeniden basım onu almaz. Barkod etiketi içeren partinin onayı o nüshaların doğrulamasını sıfırlar (yeni etiket okutulmamıştır). İç kimlik (parti numarası) ekrana yazılmaz; parti tarih, içerik ve nüsha sayısıyla tanınır |
| Basım sırası (`LabelOrder`) | **"Basım sırası"**: **Yer numarası** · **İçe aktarma sırası** · **Barkod** | pozisyon, konum no, Excel sırası (seçenek adı olarak) | Yer numarası (varsayılan) raf raf yapıştırma içindir; yer numarası olmayan nüsha sona düşer. İçe aktarma sırası nüshaların **kayda girdiği** sıradır: Excel aktarımında satır sırası, Hızlı Kayıt'ta kitapların masadan geçiş sırası |
| Boş barkod aralığı (`BarcodeReservation`, `ReservedBarcode`) | **boş barkod aralığı** (sekme **Boş Barkod Aralığı**, özel ad); eylem **"Numara ayır"**; numara durumları **Bağlanmadı** · **Nüshaya bağlandı** · **İptal edildi**; **"Seçilenleri iptal et"** · **"Bağlanmamış bütün numaraları iptal et"**, alan "İptal gerekçesi"; sayaç **"Bağlanmamış boş etiket"**; Hızlı Kayıt'ta seçenekler **"Kitaptaki etiketi okutun"** ve **"Etiket yok — yeni numara ver"** | rezervasyon, barkod stoğu, boş etiket havuzu, numara serbest bırakma | Önce etiket yolunun (okulun asıl yolu) ilk adımıdır. Numara tek sayaçtan alınır ve **asla yeniden verilmez**: kullanılmayan numara iptal edilir, iptal **geri alınmaz** ve sayaca dönmez. Bozulan etiket eldeyse **aynı numaranın yenisi** basılır (bozuğu atılır); kaybolan etiketin numarası **iptal edilir**. Toplu iptal ancak aralığın bütün kitapları kaydedilince: bağlanmamış numaranın etiketi rafta kayıt bekleyen bir kitapta olabilir |
| Doğrulama okutması (`label_verified_at`) | **Doğrulama Okutması** (sekme); **doğrulanmış** / **doğrulanmamış etiket**; liste **"Doğrulanmamış Etiketler"**; sayaç **"Doğrulanmamış etiket"**; uyarı düğmesi **"Kutuya dön"** | kontrol taraması, tarama testi, verify | Yapıştırılan etiket okutulur; okutma bir olaydır, hata değildir. Yalnız barkod etiketinde vardır (sırt etiketi barkod taşımaz). Önce etiket yolunda kayıtta okutulan etiket doğrulanmış sayılır. Görevli kipinde de açıktır: görevli ekranındaki **"Doğrulama okutmasını aç"** ile açılır, **"Okutmayı bitir"** ile kapanır; görevli okutulan etiketin yalnız numarasını ve kaynak adını görür, "Doğrulanmamış Etiketler" listesi yönetici kipindedir |
| Sınıflama | **sınıflama kodu**; tahmini kod rozeti **"tahmini"**; ana sınıf: **"Dewey Onlu Sınıflama (DOS) ana sınıfı"** (ilk geçişte açık, sonra "DOS") | Dewey numarası, DDC, "Bakanlıkça belirlenen sınıflama" | Yönetmelik sistemi adlandırmıyor; DOS fiilî standarttır (tasarım §3) |
| `Work.classification_source` | **sınıflama kaynağı**: Katalogdan bulundu · Tahmini · Elle girildi | otomatik, AI, tahmin (tek başına) | Kodun nereden geldiğini söyler; "Tahmini" değeri yukarıdaki rozetin karşılığıdır |
| `Section` | **bölüm** (kontrollü liste: ad, DOS aralığı, kısa tarif) | section, lokasyon, alan | Yönetmeliğin "alan"ı (Md. 4/1-a) ortaöğretimdeki konu bölümüdür; arayüzde "bölüm" denir. "Raf" yalnız fiziksel rafı anlatırken (etiket yapıştırma) |
| `is_reference` vb. | **danışma kaynağı**; durum **"Ödünç verilmez — kütüphanede okunur"** | referans, "ödünç dışı" | Tek türetim `is_loanable` (Md. 14/1-a, 16/1) |
| Nüsha durumları (`Copy.status`) | **Rafta** · **Ödünçte** · **Sınıf kitaplığında** · **Onarımda** · **Kayıp** · **Ayıklandı (kayıttan düşüldü)** · **Sayım noksanı (kayıttan düşüldü)** · **Kayıp (kayıttan düşüldü)** · **Devredildi** | AVAILABLE gibi kodlar, "müsait" | Liste `CopyStatus.choices` ile BİREBİRDİR (koruma testi `test_sozluk_belgesi.py`). Ağ kataloğu ve masa aynı sözcükleri kullanır. **"Ödünç verilmez — kütüphanede okunur" durum DEĞİLDİR**, `is_reference`'tan türetilir (yukarıdaki satır); **"Geçici olarak kullanım dışı"** bir hâle bağlı değildir ve kullanılmaz |
| `Membership` | **üye**, **üyelik** | okuyucu, abone, kullanıcı (kişi anlamında) | Üyelik isteğe bağlıdır (Md. 17/1) |
| `member_kind` | **üye türü**: öğrenci / öğretmen / diğer personel | personel (öğretmen anlamında), çalışan | "Personel" yalnız e-Okul raporunun adında ("Personel Listesi"). Kişiler sekmesi: **"Öğretmenler ve Diğer Personel"** |
| Ayrılış (`left_at`, LEFT) | durum rozeti **"Ayrıldı · gg.aa.yyyy"**; eylem **"Ayrıldı olarak işaretle"** | pasif, pasifleştir, arşivle, mezun (genel ayrılış anlamında) | Ayrılış kaydı SİLMEZ: kişi seçicilerden düşer, kayıt rozetle kalır; onay gövdesi bunu söyler |
| Ayrılış havuzu (`leave_candidate_since`) | **Ayrılış Havuzu** (sekme ve kart adı, özel ad); aktif kişide rozet **"Ayrılış kararı bekliyor"**; eylemler **"Ayrıldı olarak işaretle"** ve **"Aktif kalsın"** | bekleyenler, karantina, ayrılacaklar listesi, silinecekler | Aktarımda listede bulunmayan kişiler burada karar bekler; durumları aktif kalır. Karar ekranı: Kişiler → Ayrılış Havuzu |
| e-Okul mutabakatı | **"Bu dosya okulun tam listesidir"** (onay kutusu); **"N öğrenci ayrılış havuzuna eklenecek / eklendi"**, **"M öğrenci havuzdan çıkacak / çıktı"** | ayrılacak, silinecek, kaldırılacak | Varsayılan karşılaştırma yalnız dosyadaki şubelerledir. **Aktarım kimseyi ayırmaz ve kimsenin kaydını silmez** |
| Personel birleştirme | **olası aynı kişi**; eylem **"Birleştir"** | mükerrer, duplicate, çift kayıt | Eski kaydın kütüphane bağları yeni kayda taşınır, eski kayıt silinir (ör. soyadı değişimi). Aktarım sonucundan ya da Ayrılış Havuzu'ndan yapılır |
| Kart | **üye kartı**, **kart no** (8 hane) | okuyucu kartı, kütüphane kartı, kimlik kartı | Evrakta madde atfı gerekirse konum kalıbı: "Md. 20'de öngörülen kullanıcı kartının okulca düzenlenen yerel karşılığıdır; Bakanlık otomasyon sistemindeki kaydın yerine geçmez." |
| `CardRevocation` | **"Kartı yenile"** (düğme); eski kart için **"iptal edilmiş kart"** | kartı sil, kart iptal kaydı | İleti: "İptal edilmiş kart — kütüphane yöneticisine yönlendirin" |
| `Loan` | **ödünç** (ad), **ödünç ver** (eylem), **iade al** / **iade** | emanet, check-out, teslim (ödünç anlamında), "kitap çıkışı" | "Teslim" başka bir işlemdir (aşağıda) |
| `Loan.cardless` | **kartsız ödünç** | kartsız işlem, istisna | Yalnız yönetici kipinde, gerekçeli |
| `Loan.override_reason` | **gerekçe** ("Gerekçeli istisna") | override, bypass | Yalnız gecikme engeline; yardım metni: "Sağlık ya da aile bilgisi yazmayın." |
| Ödünç geçmişi | **ödünç kaydı**, **ödünç geçmişi** | **okuduğu kitaplar**, okuma karnesi, okuma puanı, okuma geçmişi | **Ödünç ≠ okuduğu kitap.** Öğrenci bazlı ödünç sayısı öğretmene ya da e-Okul'a aktarılmaz (tasarım §3) |
| İade tarihi | **iade tarihi**; gecikmişte **gecikme**, **"… gün gecikti"** | son teslim tarihi, ceza, harç, uzatma | Programda uzatma, ceza ve harç yoktur. Kaydırılmış tarih "Md. 18 gereği" diye sunulmaz |
| `LibraryPolicy` | **Kütüphane Politikası** (Ayarlar sekmesi); bölümleri **Ödünç Sınırları** · **İade ve Yıl Sonu** · **Vitrin ve Saklama** · **Künye Getirme** | ayarlar (tek başına), kurallar, ödünç ayarları | **Ödünç süresi burada AYAR DEĞİLDİR**: on beş gün sabittir (Md. 18/1) ve yalnız değiştirilemez bir bilgi satırıdır. Diğer personele ödünç açılırsa "Müdürlük kararı tarihi" ve "Müdürlük kararı sayısı" zorunludur |
| `Holiday.SCHOOL_BREAK` | **öğrenciye kapalı gün** (ara tatil, yarıyıl) | tatil (tek başına) | Kanunen tatil değildir; resmî ve dini tatil ayrı türdür |
| `Holiday` diğer türler | **resmî tatil**, **dini bayram**, **idari izin / diğer**; hepsinin üst adı **kapalı gün** (sayfa: "Kapalı Günler") | tatil günü (genel anlamda) | İdari izin kütüphanenin de kapalı olduğu gündür; iade tarihi hesabında resmî tatil gibi her zaman kapalı sayılır. Bu programın kuralıdır, TBK 93 kıyası altında anılmaz (`docs/mevzuat/BENIOKU.md` §4). Tahmini bayram tarihinde **"tahmini"** rozeti |
| `Delivery` (U11) | **teslim**: "sınıf kitaplığına teslim", "öğretmene teslim"; geri dönüşü **geri alma** | ödünç, emanet, zimmet | **Teslim ödünç değildir**, Md. 18 sayı sınırı uygulanmaz |
| İlişik | **"Kütüphaneden ilişiği yoktur" belgesi**, **ilişik listesi** | borç, ilişik kesme | Karne ya da diplomanın ön koşulu diye SUNULMAZ; dayanağı yok |
| `LossDamageCase` | **kayıp**, **hasar**, **onarım**; belge "Kayıp/hasar tutanağı" | zayi, telef | Bedel seçenekleri yalnız ortaöğretimde (Md. 19). Program tahsilat yapmaz |
| `WeedingBatch` | **ayıklama** (Md. 12) | silme, temizleme, imha (genel anlamda) | Kütüphane kararıdır |
| TMY işlemi | **kayıttan düşme**; imha yalnız **"imha tutanağı"** (TMY 28/5) bağlamında; **devir** | silme | Ayıklama ≠ kayıttan düşme: biri komisyon kararı, öbürü taşınır işlemidir |
| `Acquisition` | **edinim**, **edinim partisi**; **edinim yolu**: Bakanlık gönderimi · Satın alma · Bağış · Değişim · Sayım fazlası (kayda giriş) · Mevcut koleksiyon (programa aktarım) | alım, temin, kaynak girişi, sağlama (tek başına) | İlk dördü Md. 10/5'in saydığı yollardır; son ikisi kayıt içi girişlerdir ve öyle adlandırılır. Bağışçı/satıcı adı **"kaynak notu"**dur ve şifreli saklanır |
| `CommissionDecision` | **Seçim ve Ayıklama Komisyonu**, **komisyon kararı** | kurul (bu anlamda) | Yönetmelikteki adı aynen |
| `decision_type` | **karar türü**: Kaynak seçimi · Bağış değerlendirme · Ayıklama; kullanılmış kararda rozet **"Kullanımda"** | karar tipi, kategori | Tür bağlayıcıdır: bağış yalnız bağış değerlendirme kararıyla kataloglanır. Kullanılmış kararın türü değişmez, kaydı silinmez |
| `DonationIntake` | **bağış ön kaydı** | bağış listesi (tek başına), taslak | Komisyon kararına kadar nüsha açılmaz |
| Bağış durumları | ön kayıt: **Karar bekliyor** · **Karar işlendi** · **İptal edildi**; kalem: **Kabul edildi** · **Reddedildi**; eylemler **"Komisyon kararını uygula"**, **"Kararı uygula"**, **"İptal et"** | onaylandı, kapandı, silindi | Karar geri alınamaz; onay diyaloğu kaç kalemin kabul, kaç kalemin ret edileceğini yazar. Reddedilen her kalemde **"ret gerekçesi"** zorunludur |
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
| Kurtarma anahtarı işlemleri | kart adları **Kurtarma Anahtarını Doğrula** ve **Kurtarma Anahtarını Yenile**; eylem **"yenileme"** | anahtarı sıfırla, anahtar değiştir, yeni anahtar üret (tek başına) | Yenileme kayıtların anahtarını değiştirmez, yalnız kurtarma kilidini yeniler; yenilemeden önce alınmış yedekler için eski kâğıt gerekebilir ve metin bunu söyler |
| Görev devri | **görev devri**; belge **Görev devri notu** | devir teslim (tek başına) | "Devir" TMY'de başka anlama gelir |
| Masa hesabı | **kütüphane masası Windows hesabı** | kiosk hesabı, ortak hesap | Yönetici yetkisi olmayan ayrı hesap (U9) |
| Yedek | **yedek**, **şifreli yedek**; "güçlü şifrelemeyle korunur" | X25519, AES, `.kdbak` (kullanıcı metninde) | Teknik adlar yalnız Hakkında sayfasında |
| Lisans | **LGPLv3** (yalnız Pardus sürümünün lisans bildiriminde), **PolyForm Noncommercial** | — | Lisans adı teknik ad sayılmaz: bildirim yükümlülüğü gereği açıkça yazılır (`docs/kurulum.md` §4.1, `packaging/linux/BENIOKU.txt`) |
| Sürüm | **"yayımlanan son sürüm"**, **"kurulum dosyası"** | GitHub sürümü, Release, kurucu | Güncelleme denetimi yalnız düğmeyle yapılır |

## 2. İç kodlar yüzeye çıkmaz

Tasarımın karar, faz ve bulgu kodları kullanıcı metninde, hata mesajında ve
evrakta GEÇMEZ: `U1`-`U13`, `T1`-`T17`, `A1`-`A23`, `F0`-`F12`, `S1`-`S15`,
`D1`-`D21`, `E1`-`E20`, `GA-`, `KM-`, `UY-`, `SU-`, `EK-`, `AT-`, `V2-`. İç
kimlikler (`id=…`, `pk`) de geçmez. Evrak kodunun yerine belgenin adı yazılır:

| Kod | Ad |
|---|---|
| E1 | Sırt etiketi · Barkod etiketi · Sırt ve barkod etiketi · Boş barkod etiketi · Kalibrasyon sayfası |
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

## 2.1 Belgelerde örnek ve yer tutucu yazımı

Depo herkese açıktır; belgelerde ve testlerde **gerçek kurum, kişi ve ağ bilgisi
kullanılmaz** (teknik borç TB25):

- **Yer tutucular:** okul ağı için `<idari-ağ>`, `<tahta-ağı>`, `<ek-alt-ağ>`;
  bilgisayar adı için `<bilgisayar-adı>`; port için `<port>`. Gerçek IP blokları, alt
  ağ maskeleri (`/24`), host numaraları (`.40`), VLAN, SSID, proxy ve sunucu adları
  yazılmaz.
- **Örnek veri** uydurmadır ve `Örnek` ön ekiyle kurulur: "Örnek Anadolu Lisesi",
  "Örnek İlçe". Uzun ad gereken testte ad uzatılır, gerçek kurum adı kullanılmaz.
  Örnek kişi adları da uydurmadır; rol ve branş birleşimi gerçek bir kişiyi
  düşündürmeyecek biçimde seçilir.
- **Yollar:** kardeş depolara atıf `../<depo>/…` biçimindedir; mutlak yerel yol
  (`C:\Users\…`) hiçbir belgeye yazılmaz.

## 3. Yazım kuralları

- **Düğmeler cümle düzenindedir:** "Ödünç ver", "İade al", "Kartı yenile",
  "Görevli kipine geç". Sayfa, sekme ve bölüm **başlıkları** Başlık
  Düzenindedir: "Dolaşım Masası".
- **Başlık Düzeni nereye uygulanır:** kullanıcıya yol tarif edilirken adı
  geçebilen her başlık — sayfa başlığı (h1), sekme, sayfa içi bölüm ve kart
  başlıkları — Başlık Düzenindedir ("Ayarlar → Güvenlik", "Kişiler → Ayrılış
  Havuzu", "Şifreli Veritabanı Yedeği"); bir bölümün ya da kartın içinde metni
  parçalayan **alt başlıklar** (kılavuzun ara başlıkları, kart içi adımlar)
  cümle düzeninde kalır ("Sakladığınızı doğrulayın", "Parolayı unutursanız").
  Üç istisna: §2'deki **belge adları** başlık yerinde de oradaki yazımıyla
  yazılır ("Kurtarma anahtarı çıktısı"), program durumu ekranlarının başlıkları
  §4.2'deki cümlenin kendisidir ("Kayıtlar kilitli"), onay diyaloğunun başlığı
  sorudur.
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

*Aşağıdaki tablolar F5 sonundaki durumdur (24.09.2026); kaynak `AppShell.tsx`
(`NAV_ITEMS`, `PAGE_TITLES`), sayfaların h1'leri ve sekme tanımlarıdır.*

### 4.1 Sayfalar

| Gezinme etiketi | Sayfa başlığı (h1 = üst çubuk) | Adres | Not |
|---|---|---|---|
| Genel Bakış | Genel Bakış | `/` | Ana sayfanın tek adı |
| Kişiler | Kişiler | `/kisiler` | |
| Katalog | Katalog | `/katalog` | Eser ve nüsha listelerinin tek ekranı |
| — | Eser Ayrıntısı | `/katalog/eser/:id` | Menüde yoktur; katalog listesindeki satıra tıklanarak açılır. Başlıkta modül adı geri bağlantısıdır ("Katalog / Eser Ayrıntısı") |
| — | Edinimler ve Bağışlar | `/katalog/edinimler` | Menüde yoktur; Katalog sayfasının sağ üstündeki **Edinimler ve Bağışlar** bağlantısıyla açılır |
| — | Hızlı Kayıt | `/katalog/hizli-kayit` | Menüde yoktur; Katalog sayfasının sağ üstündeki **Hızlı Kayıt** bağlantısıyla açılır. Kitap elde, ISBN okutarak tek tek giriş |
| — | Etiketler | `/katalog/etiketler` | Menüde yoktur; Katalog sayfasının sağ üstündeki **Etiketler** bağlantısıyla açılır. Sırt ve barkod etiketi basımı, basım kaydı, boş barkod aralığı, doğrulama okutması, şablon ve kalibrasyon. İçe aktarmanın **"Bu partinin etiketlerini bas"** kısayolu buraya gelir |
| — | İçe Aktarma | `/katalog/ice-aktarma` | Menüde yoktur; Katalog sayfasının sağ üstündeki **İçe Aktarma** bağlantısıyla açılır. Toplu giriş, yapay zekâ köprüsü, çevrimdışı künye ve aktarım geçmişi |
| Ayarlar | Ayarlar | `/ayarlar` | |
| — | Ağ Doktoru | `/ag-doktoru` | Menüde yoktur; **Ayarlar → Ağ Kataloğu** sekmesindeki **Ağ Doktoru** bağlantısıyla açılır. Yalnız yönetici kipinde (görevli kipinde her adreste görevli ekranı durur) |
| Kılavuz | Kullanım Kılavuzu | `/kilavuz` | |
| Hakkında ve Lisans | Hakkında ve Lisans | `/hakkinda` | Kenar çubuğunun altında, ana gezinmenin dışında |
| — | Kurulum Sihirbazı | `/kurulum` | Menüde yoktur. İlk açılışta kurulum kapısı buraya getirir; kurulumdan sonra Ayarlar'ın altındaki "Diğer Ayarlar" bölümünde **Kurulum Sihirbazı** kartıyla açılır |

Ana gezinmenin sırası: Genel Bakış · Kişiler · Katalog · Ayarlar · Kılavuz.
Görevli kipinde gezinme bağlantıları gösterilmez; her adreste görevli ekranı
durur. Görevli ekranından açılan tek iş **Doğrulama Okutması**dır (bölüm
başlığı; sayfanın h1'i ve üst çubuk "Görevli Kipi" kalır).

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
| Kişiler | **Öğrenciler** (`ogrenciler`) · **Öğretmenler ve Diğer Personel** (`personel`) · **Ayrılış Havuzu** (`havuz`) |
| Katalog | **Eserler** (`eserler`) · **Nüshalar** (`nushalar`) |
| Edinimler ve Bağışlar | **Edinim Partileri** (`partiler`) · **Bağış Ön Kayıtları** (`bagislar`) · **Komisyon Kararları** (`kararlar`) |
| Etiketler | **Basım Kuyruğu** (`kuyruk`) · **Basım Geçmişi** (`gecmis`) · **Boş Barkod Aralığı** (`bos-barkod`) · **Doğrulama Okutması** (`dogrulama`) · **Şablonlar ve Kalibrasyon** (`sablonlar`) |
| İçe Aktarma | **Excel Aktarımı** (`excel`) · **Yapay Zekâ Köprüsü** (`kopru`) · **Çevrimdışı Künye** (`cevrimdisi`) · **Aktarım Geçmişi** (`gecmis`) |
| Ayarlar | **Ders Yılları** (`ders-yillari`) · **Kapalı Günler** (`kapali-gunler`) · **Şubeler** (`subeler`) · **Kütüphane Politikası** (`politika`) · **Bölümler** (`bolumler`) · **Okul Bilgileri** (`okul`) · **Güvenlik** (`guvenlik`) · **Güncelleme** (`guncelleme`) · **Ağ Kataloğu** (`ag-katalogu`) |

Katalog ekranlarının pencere başlıkları (Dialog): **Yeni eser** /
**Künyeyi düzenle** · **Nüsha ekle** / **Nüshayı düzenle** · **Yeni edinim** /
**Edinimi düzenle** · **Yeni bağış ön kaydı** · **Bağış ön kaydı** ·
**Komisyon kararını uygula** · **Bağış ön kaydını iptal et** · **Yeni komisyon
kararı** / **Kararı düzenle** · **Yeni bölüm** / **Bölümü düzenle** · **Yeni etiket
şablonu** / **Şablonu düzenle** · **Yeni yazıcı kalibrasyonu** / **Kalibrasyonu düzenle**.

Ağ Kataloğu ve Çık pencereleri: **Portu değiştir** · **Güvenlik duvarı kuralı güncellensin mi?** (onay) · **Programdan çıkılsın mı?** (yönetici kipi ve kilitliyken onay) / **Programdan çık** (görevli kipinde, yönetici parolasıyla) · **Program kapanıyor**.

### 4.4 Kurulum Sihirbazı adımları

Adım rayındaki adlar, sırasıyla: **Yönetici Parolası** · **Okul Bilgileri** ·
**Ders Yılı ve Kapalı Günler**. İlk adım atlanamaz. Adımlar arası düğmeler:
**Geri**, **Devam** (1. adım), **Kaydet ve devam et** (2. adım), **Kurulumu
tamamla** (son adım).

### 4.5 Genel Bakış kartları

**Başlangıç Yol Haritası** (kurulumdan sonra; bütün maddeler bitince
gizlenebilir — kurtarma anahtarı doğrulanmamışken gizlenemez, uyarı kartın
başındadır) · **Ayrılış Havuzu** (yalnız havuz boş değilken: "N kişi ayrılış
kararı bekliyor" → Kişiler → Ayrılış Havuzu) · **Kişiler** · **Ayarlar** ·
**Katalog Excel Şablonu** (bir sayfaya gitmez, şablonu indirir).

### 4.6 Ayarlar → Güvenlik kartları

Sırasıyla: **Yönetici Parolası ve Şifreleme** (durumu, şifrelenen alanları,
"Parolayı değiştir" ve "Kilitle" düğmelerini taşır) · **Kurtarma Anahtarınız**
(yalnız yeni üretilmiş anahtar beklerken) · **Kurtarma Anahtarını Doğrula**
(yalnız anahtar doğrulanmamışken) · **Kurtarma Anahtarını Yenile** ·
**Kurtarma anahtarı çıktısı** (belge adı, §2 E14) · **Şifreli Veritabanı
Yedeği** · **Yedekten Geri Yükleme**.

### 4.7 Hızlı Kayıt ve İçe Aktarma ekranlarının adları

Kılavuz bu adları birebir kullanır; ekrandaki metin değişirse buradaki de
değişir.

**Hızlı Kayıt.** Kartlar: **Kitabın ISBN'ini okutun** · **Künye** (ya da eser
seçildiyse **Seçilen eser**) · **Kitabın etiketi** (seçenekler **"Kitaptaki etiketi
okutun"** ve **"Etiket yok — yeni numara ver"**; ilkinde "Kütüphane etiketi" alanı,
okutunca nüsha o numarayla açılır; bağlanmamış boş etiket varken ekran bu seçenekle
açılır) · **Nüsha** ("Nüsha sayısı" yalnız yeni numara yolunda sorulur). Kayıttan
sonra sonuç kartında **"Etiketini bas"** (etiket yolunda **"Sırt etiketini bas"**)
düğmesi **Etiket Basımı** kartını açar ("Etiket içeriği", Basım Ayarları'nın alanları,
**"Basım partisini hazırla"**, ardından §4.8'deki **Hazırlanan Basım Partisi** kartı).
Etiket yolunda kutuya okutulan etiketin Enter'ı kaydı bitirir; etiket reddedilirse
alanın altında gerekçe ve **"Kitapta etiket yoksa “Etiket yok — yeni numara ver”
seçeneğini kullanın."** ipucu çıkar. Etiket zaten kayıtlı bir nüshanınsa ipucu
çıkmaz, gerekçe önce **"Elinizdeki kitap buysa kitap zaten kayıtlıdır; yeniden
kaydetmeyin."** der (aynı kitap ikinci kez kaydedilmesin). Etiket kutusu odak alınca
kod seçilir: yeniden okutulan etiket eski kodu siler. Alanlar: "ISBN barkodu", "Kaynak
adı", "Yazar(lar)", "Çevirmen", "Yayınevi", "Yayın yılı", "ISBN", "Konu(lar)",
"Kaynak türü", "Dil", "Sınıflama kodu", "Sınıflama kaynağı", "Yer numarası",
"Edinim", "Nüsha sayısı", "Bölüm", "Eski kayıt no", "Danışma kaynağı (ödünç
verilmez)". Düğmeler: **"Künyeyi getir"** · **"Formu temizle"** ·
**"Yeniden getir"** (künye önerisini önbelleği atlayarak yeniden ister) ·
**"Seçilenleri forma yaz"** · **"Bu esere nüsha ekle"** · **"Seçimi bırak"** ·
**"Nüshayı aç"** · **"Künyeyi aç"**. Nüsha açıldıktan sonra künye ve nüsha
alanları boşalır (edinim ve bölüm seçimi korunur), imleç okutma kutusuna döner.

**İçe Aktarma.** Sağ üstte **"Katalog Excel şablonu"** düğmesi. Excel Aktarımı
ve Yapay Zekâ Köprüsü sekmeleri aynı paneli kullanır: **"Önizle"** /
**"Yeniden önizle"** → rapor → **Açılacak Edinim Partisi** → **"Uygula"**.
Rapor başlığı önizlemede **"Önizleme — hiçbir kayıt yazılmadı"**, uygulamadan
sonra **"Aktarım sonucu"**; bölümleri **"Bölüm listesinde bulunmayan
değerler"** ("Karşılığı" seçicisi, **"Yeni bölüm aç"**), **"Karar bekleyen
satırlar"** ("Kararınız" seçicisi, **"Yeni eser aç"**) ve **"Satır listesi"**
("Durum" sütununda **Yeni eser** · **Mevcut esere nüsha** · **Şüpheli** ·
**Aktarılmadı**). Çevrimdışı Künye sekmesi: **ISBN Künye Listesi** kartı,
**"ISBN listesini indir"**, "Doldurulmuş dosya" kutusu, **Önizleme** ve
**"Seçilenleri kaydet"**. Aktarım Geçmişi sekmesi: sütunlar Tarih · Dosya ·
Kaynak · Durum · Satır · Nüsha, eylem **"Önizlemeyi iptal et"**.

### 4.8 Etiketler ekranının adları

Kılavuz bu adları birebir kullanır; ekrandaki metin değişirse buradaki de değişir.

**Sayfanın üstü.** Başlık "Katalog / Etiketler". Sayaç şeridi (her sayaç ilgili
sekmeyi açar): **"Sırt etiketi bekleyen"** · **"Barkod etiketi bekleyen"** ·
**"Doğrulanmamış etiket"** · **"Bağlanmamış boş etiket"**. Onay bekleyen parti
varsa üstte uyarı: "N basım partisi onay bekliyor. …" ve **"Basım Geçmişi'ni
aç"**.

**Basım Kuyruğu.** Kartlar **Ne Basılacak** ("Etiket içeriği", "Basım sırası",
"Bölüm", "Edinim partisi", "Boş barkod aralığı", "Kayıt tarihi (ilk)", "Kayıt
tarihi (son)") ve **Basım Ayarları** ("Etiket şablonu", "Yazıcı (kalibrasyon)",
yalnız ikisi birden basımda "Sırt etiketi tabakası" ve "Sırt tabakasının
yazıcısı", "Barkodun yanına QR ekle", tabaka ızgarası ve "Başlangıç hücresi");
düğme **"Basım partisini hazırla"**. Kuyruk tablosu: Barkod · Kaynak adı · Yer
numarası · Bölüm · Kayıt · Durum (**Kuyrukta** ya da **"Onay bekleyen
partide"** rozeti); seçim varken **"Seçimi bırak"**. Hazırlanan parti
**Hazırlanan Basım Partisi** kartında durur: **"Önizle"** · **"PDF'i indir"** ·
**"Basıldı olarak işaretle"** · **"Partiden vazgeç"**.

**Önizleme penceresi.** Başlığı içeriğin adıdır ("Sırt ve barkod etiketi", "Boş
Barkod Etiketi", "Kalibrasyon Sayfası"); pencerede **"PDF'i indir"** ve
**"Kapat"**, üstte "Yazdırırken ölçeklemeyi kapatın (“Gerçek boyut” ya da
%100)…" notu. Önizleme ve indirme hiçbir işarete dokunmaz.

**Basım Geçmişi.** "Durum" süzgeci; tablo Hazırlandı · İçerik · Nüsha · Şablon ·
Yazıcı · Durum. Satıra tıklanınca tablonun üstünde **Seçilen Basım Partisi**
kartı ("Nüshaları göster" / "Nüshaları gizle", **"Basım işaretini geri al"**,
**"Yeniden bas"**, "Kapat"); parti onay bekliyorsa altında **Onay Bekleyen
Parti** kartı (Hazırlanan Basım Partisi kartıyla aynı düğmeler). "Yeniden bas"
**Yeniden Basım** kartını açar ("Etiket içeriği", Basım Ayarları'nın alanları,
**"Yeniden basım partisini hazırla"**; QR ve ayrı sırt tabakası önceki partiden
alınır).

**Boş Barkod Aralığı.** **Numara Ayır** kartı ("Adet", "Açıklama", **"Numara
ayır"**); aralık tablosu Numaralar · Adet · Açıklama · Ayrıldı · Basım ·
Bağlanan · İptal · Bağlanmamış. Satıra tıklanınca (ayırmadan sonra
kendiliğinden) **Seçilen Aralık** kartı: "Boş etiketleri basın" (Basım
Ayarları'nın alanları, "Önizle", "PDF'i indir", **"Basıldı olarak işaretle"** ya
da "Basıldı · gg.aa.yyyy ss:dd" rozeti ve **"Basım işaretini geri al"** — aralıktan
kitaba bağlanmış etiket varsa kapalı), **"Sırt etiketlerini bas"** bağlantısı,
"Numaralar" tablosu (Barkod · Durum · Kitap ya da gerekçe), "Kullanılmayan
numaralar" ("İptal gerekçesi", **"Seçilenleri iptal et"**, **"Bağlanmamış bütün
numaraları iptal et"**). İptal onayının düğmesi **"Numaraları iptal et"**dir ve
kullanıcı "Bu numaraların etiketlerinin kitaplara yapıştırılmadığını
denetledim." kutusunu işaretlemeden açılmaz.

**Doğrulama Okutması.** **Yapıştırılan Etiketi Okutun** kartı ("Kütüphane
etiketi" kutusu, odak uyarısı ve **"Kutuya dön"**, "Bu ekranda doğrulanan: N",
son okutmalar), **Doğrulanmamış Etiketler** listesi (Barkod · Kaynak adı · Yer
numarası · Bölüm · Basıldı).

**Şablonlar ve Kalibrasyon.** **"Yeni şablon"**; şablon kartında
**"Kalibrasyon"** · **"Düzenle"** · **"Sil"**, rozetler **Varsayılan** · **QR'a
uygun** · **Barkod bu etikete sığmaz**. Şablon penceresi (**Yeni etiket
şablonu** / **Şablonu düzenle**): "Şablon adı", "Tür", "Bu türün varsayılan
şablonu", "Satır sayısı", "Sütun sayısı", "Etiket genişliği (mm)", "Etiket
yüksekliği (mm)", "Üst kenar boşluğu (mm)", "Sol kenar boşluğu (mm)", "Sütun
aralığı (mm)", "Satır aralığı (mm)". **Yazıcı Kalibrasyonu: (şablonun adı)**
kartında adım listesi, "Sayfaya uygulanacak kayma", "Önizle" · "PDF'i indir",
"Kayıtlı yazıcılar" listesi ("Düzenle", "Sil") ve **"Yeni yazıcı
kalibrasyonu"**. Kalibrasyon penceresi (**Yeni yazıcı kalibrasyonu** /
**Kalibrasyonu düzenle**): "Yazıcı adı", "Yatay kayma (mm)", "Dikey kayma (mm)",
"Cetvelde okuduğunuz değeri ekleyin" bölümünde "Okunan yatay değer", "Okunan
dikey değer" ve **"Kaymaya ekle"**; "Kaydet".

### 4.9 Ağ Kataloğu ve Ağ Doktoru ekranlarının adları

**Ayarlar → Ağ Kataloğu.** İlk açılışta (katalog kapalı ve afiş hiç basılmamış)
başta **Ağ Kataloğunu Açmadan Önce** kartı durur; adımları sırasıyla: **BTR'yle
görüşün** (düğme **"Ağ Hizmeti Bilgi Notu'nu bas"**) · **Güvenlik duvarını
hazırlayın** (bağlantı **"Ağ Doktoru'nu aç"**) · **Adresi seçin** · **Ağ Kataloğunu
açın** · **Afişi basın, yer imlerini dağıtın**. Kartlar: **Ağ Kataloğu** (durum
rozeti, adres, **"Ağ Kataloğunu aç"** / **"Ağ Kataloğunu kapat"**, **Ağ Doktoru**
bağlantısı) · **Dinleme** (port ve **"Portu değiştir"**; "Katalog hangi ağ
bağlantısında açılsın?" seçenekleri **"Bu bilgisayarın bütün ağ bağlantılarında"** ve
**"Yalnız seçili IP adresinde"**; "IP adresi"; "Tahta ağı blokları") · **Katalog
Sayfaları** ("Vitrin (yeni gelenler ve çok okunanlar) ana sayfada gösterilir",
"Konu dizini gösterilir", "Kütüphane saatleri") · **Uyku** ("Ağ Kataloğu açıkken
bilgisayar boşta uykuya geçmesin"). Kaydetme düğmesi **"Kaydet"**. Port penceresi
(**Portu değiştir**): alan "Yeni port", düğmeler "Vazgeç" · "Portu değiştir".

**Ağ Doktoru.** Kartlar sırasıyla: **Katalog Durumu** · **Güvenlik Duvarı** ·
**Ağ Bağlantıları** (yalnız masaüstü programında) · **Dinleyici Sınaması** ·
**Belgeler**. Düğmeler: **"Ağ Kataloğunu aç"** / **"Ağ Kataloğunu kapat"** ·
**"Yeniden başlat"** · **"Yenile"** · **"Kuralı ekle/güncelle"** · **"Yeniden
denetle"** · **"Dinleyiciyi sına"** · **"Afişi bas"** · **"Yer imi dosyalarını
üret"** · **"PYS talep metnini kopyala"** · **"Ağ Hizmeti Bilgi Notu'nu bas"** ·
**"Kopyala"** (komut kutuları). Seçici: **"Belgelerde kullanılacak adres"**.

| Kavram | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| Katalog durumu | **Açık** · **Kapalı** · **Güvenlik duvarı izni yok** · **Açılamadı** · **Port bekleniyor** · **Geri yükleme nedeniyle kapalı** | aktif/pasif, online, çalışıyor | Tepsi satırı "Ağ Kataloğu: açık — http://…" biçimindedir |
| Güvenlik duvarı denetimi | **beş madde**; madde sonuçları **Geçti** · **Geçmedi** · **Uyarı** · **Denetlenemedi** | firewall, kontrol listesi | Windows'ta biri geçmezse katalog okul ağına hiç açılmaz |
| Öz sınama | **"dinleyici bu arayüzde ayakta"**; yanında her zaman: "Güvenlik duvarını ya da VLAN'ı kanıtlamaz…" | bağlantı testi, ping | Asıl kanıt başka bilgisayardan `Test-NetConnection` |
| Ağ profili | **Genel** · **Özel** · **Etki alanı** | Public/Private/Domain (kullanıcı metninde) | |
| DHCP'de sabit adres | **sabit adres**, "DHCP'de sabit adres ayırma" | rezervasyon (kılavuzda; sözcük barkod bağlamında yasaktır) | BTR belgelerinde (`docs/kurulum.md`, `docs/ag-kurulumu.md`) teknik adı yazılabilir. Adresi kütüphane yöneticisi elle değiştirmez (Yönerge 11/6) |
| Adres uyarısı | **"Bu bilgisayarın IP adresi değişti (… → …). Afişi yeniden basın, yer imlerini güncelleyin."** | "IP çakışması", "ağ hatası" | Gün değişimi denetiminden gelir, Ağ Doktoru'nun **Katalog Durumu** kartında görünür; afiş yeni adresle basılınca kalkar |
| PYS | **PYS talep metni**, talebin konusu **"yerel ağ VLAN düzenlemesi — tek yön"**; kanal **FATİH PYS** | "internet açma", "site açma" | Açılımı yazılmaz: ad kanalın kendi adıdır |
| Tahta kipi | **tahta kipi** ("büyük düzen"; yer imi adresinde `?tahta=1`) | kiosk, tahta modu, dokunmatik mod | Tahtalar için üretilen yer imleri bu kiple açar; dokunmatik ekranda büyük düzen kendiliğinden de açılır. Klavyesiz gezinme **Kaynak Adları** · **Yazarlar** · **Konular** dizinleriyledir |
| Yer imi dağıtımı | belge **Yer imi dosyaları** (§2); ETAP/Pardus için **yer imi politika dosyası**, Windows için **internet kısayolu** | bookmark, favori | ETAP her öğretmene ayrı hesap açar: kullanıcı başına yer imi yetmez, politika dosyası bütün hesaplarda görünür. Dağıtımı BTR yapar |
| Gün değişimi | **gün değişimi** (denetim açılışta ve program açıkken saatte bir) | zamanlanmış görev, cron, gece işi | Günlük yedek, 14 günden eski yedeklerin silinmesi ve adres denetimi buna bağlıdır; program tepside günlerce açık kalabilir |
| Programdan çıkış | **Çık** (üst çubuk ve tepsi), onay **"Programdan çıkılsın mı?"**, görevli kipinde **"Programdan çık"** (yönetici parolasıyla) | "Kapat" (programdan çıkmak anlamında), sonlandır, oturumu kapat | "Kapat" salt bilgi diyaloğunu kapatır (§3); pencerenin çarpısı programı kapatmaz, tepsiye gizler. Görevli kipindeki parola kaza önleyicidir, güvenlik sınırı diye sunulmaz |

**Çık, tepsi ve kurucu.** Üst çubukta her durumda **Çık** düğmesi (dar pencerede
yalnız simge; ipucu "Programdan çık"). Onay penceresi **Programdan çıkılsın mı?**
("Vazgeç" · "Çık"); görevli kipinde **Programdan çık** ("Yönetici parolası",
"Vazgeç" · "Çık"); kapanırken **Program kapanıyor** ("Kütüphane Defteri
kapanıyor…"). **Programı kapatıp yeniden açın** ekranında **"Programdan çık"**
düğmesi (onay ve parola sormaz). Tepsi menüsü sırasıyla: **Pencereyi aç** · durum
satırı ("Ağ Kataloğu: açık — http://…", "Ağ Kataloğu: kapalı", "Ağ Kataloğu:
güvenlik duvarı izni yok", "Ağ Kataloğu: açılamadı", "Ağ Kataloğu: port
bekleniyor", "Ağ Kataloğu: geri yükleme nedeniyle kapalı") · **Ağ Kataloğunu
aç** / **Ağ Kataloğunu kapat** · **Görevli kipine geç** · **Kilitle** · **Çık**.
Windows kurucusunun görevleri: **Yerel ağdan katalog taramasına izin ver
(güvenlik duvarı kuralı)** · **Oturum açılınca Kütüphane Defteri'ni başlat** ·
**Pencereyi açmadan tepside başlat** · **Masaüstü kısayolu oluştur**; Başlat
menüsünde **Kütüphane Defteri — Yedekten Geri Yükle**.

**Ağ Kataloğunun kendi sayfaları** (okul ağından açılan tarayıcı sayfaları;
pencere başlığı "… — Ağ Kataloğu"). Üst menü: **Ara** · **Kaynak Adları** ·
**Yazarlar** · **Konular** (konu dizini açıksa) · **Hakkında**. Ana sayfa
**Kütüphane Kataloğu**: arama kutusu "Katalogda ara" (yer tutucu "Kaynak adı,
yazar, konu ya da ISBN"), seçici "Kaynak türü" ("Bütün kaynak türleri"), düğme
"Ara"; **Dizinler** bölümünde **Kaynak Adına Göre** · **Yazar Adına Göre** ·
**Konuya Göre** · **Bütün Kaynaklar**; vitrinde **Yeni Gelenler** · **Çok
Okunanlar**. Dizin sayfaları **Kaynak Adı Dizini** · **Yazar Dizini** · **Konu
Dizini** (harf seçilince "…: A"; harfle başlamayan adlar — rakam, noktalama —
**Diğer**). Arama
sayfası **Arama Sonuçları** (arama yoksa **Bütün Kaynaklar**). Konular sayfasında
**Dewey Onlu Sınıflama (DOS) Ana Sınıfları** ve **Konu Dizini**. Eser sayfasında
**Künye** ve **Nüshalar** (sütunlar Bölüm · Durum), düğme "Kataloğa dön". Hakkında
sayfasında **Kütüphane Saatleri** · **Ağ Kataloğu Neyi Gösterir** · **Ağ Kataloğu
Neyi Göstermez** · **Kütüphane Defteri**. Katalog afişinin başlığı **KÜTÜPHANE
KATALOĞU** (afiş belge adı §2'de: Katalog afişi).

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
