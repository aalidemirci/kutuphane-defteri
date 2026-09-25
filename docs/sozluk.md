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
| Kart | **üye kartı**, **kart no** (8 hane) | okuyucu kartı, kütüphane kartı, kimlik kartı | Evrakta madde atfı gerekirse konum kalıbı: "Md. 20'de öngörülen kullanıcı kartının okulca düzenlenen yerel karşılığıdır; Bakanlık otomasyon sistemindeki kaydın yerine geçmez." Kalıp YALNIZ öğrenci ve öğretmen kartına basılır (Md. 20/1 kartı ikisine öngörür); diğer personelin kartında atıfsız not: "Okulca düzenlenen yerel üye kartıdır; diğer personele ödünç okul müdürlüğü kararıyla verilir." Kart no hiç kimseye yeniden verilmez; yedekten geri yükleme de bunu bozmaz (veri dizinindeki verilmiş kart defteri) |
| `CardRevocation` | **"Kartı yenile"** (düğme); eski kart için **"iptal edilmiş kart"** | kartı sil, kart iptal kaydı | İleti: "İptal edilmiş kart — kütüphane yöneticisine yönlendirin" |
| Üyelik yönetimi (F6) | sekme **Üyeler**; pencere **Üyelik**; durum rozeti **Aktif** · **Sonlandı · gg.aa.yyyy**; eylemler **"Kartı yenile"** (onay başlığı "Kart yenilensin mi?") · **"Üyeliği sonlandır"** · **"Üyeliği sil"** · **"Personele üyelik aç"**; bölüm **Ödünç Kaydı** | üyeyi sil (sonlandırma anlamında), dondur, askıya al | Sonlandırma nedeni kapalı listedir ve zorunludur: elle **Üyenin isteği** · **Yanlış kayıt**; program yazar: **Okuldan ayrıldı** · **Kişi kayıtları birleştirildi**. Açık ödüncü olan üyelik sonlandırılamaz. "Üyeliği sil" yalnız yanlış açılmış ve hiç ödünç kaydı olmayan üyeliktir; kartı iptal edilir, numarası bir daha verilmez |
| Üyelik istek listesi (Md. 17/1) | sekme **Üyelik İstek Listesi**; alan **"Üyelik isteği tarihi"**; düğme **"Seçilenleri üye yap"**; satır rozeti **Üye** | toplu kayıt, otomatik üyelik | Liste kimseyi kendiliğinden üye yapmaz; e-Okul aktarımı da üyelik açmaz. Seçimde bu arada üye olan ya da ayrılan varsa hiçbir üyelik açılmaz |
| Kart basımı (`card_printed_at`) | sekme **Kart Basımı**; listeler **Kart Basımı Bekleyen** · **Kartı Basılmış**; rozet **"Kart basımı bekliyor"**; eylemler **"Basıldı olarak işaretle"** · **"Basım işaretini geri al"**; seçenek **"Kesim çizgisi bas"** | kart yazdırma, kart listesi, kart üret | Etiketteki D10 kuralıyla aynı: **PDF'i almak kartı basılmış saymaz**. Yeni üyelik ve "Kartı yenile" kartı kuyruğa koyar. Kart 85 × 54 mm'dir, sayfaya 10 kart; kartta okul adı, ad, üye türü, barkodlu kart no ve konum kalıbı vardır, **sınıf yazmaz** (şube seçilirse sınıf yalnız sıralamadır). Kaydırma kart şablonunun **yazıcı kalibrasyonuyla** düzeltilir |
| İade hatırlatma (E4) | belge **İade hatırlatma pusulası** (tek kişilik; dış yüzde **"KİŞİYE ÖZELDİR"**; **kesme çizgisi**, **katlama çizgisi**); sayfa **Gecikmiş Ödünçler**; belge **Gecikmiş ödünç listesi** | ihtar, uyarı mektubu, borç listesi, kara liste | Pusulayı kütüphane yöneticisi ya da sınıf rehber öğretmeni dağıtır; sınıfta okunmaz, öğrenci görevliye dağıttırılmaz. Pusulada Md. 18'e yalnız süre cümlesinde atıf vardır ("Bir kitabı ödünç alma süresi on beş gündür"); kaydırılmış tarih "Md. 18 gereği" diye sunulmaz. Toplu listenin her sayfasında §5'teki dipnot durur |
| Üyelik belgeleri (E13, E19) | bölüm **Üyelik Belgeleri** (Kişiler → Üyeler); alanlar **"Başvuru adresi"** · **"E-posta ya da telefon"** (yalnız basıma yazılır, saklanmaz) | KVKK formu, gizlilik sözleşmesi | Kütüphane aydınlatma metni öğrenci ve personel listeleri programa aktarılmadan önce duyurulur. Masa kartı görevliye göreve başlamadan verilir |
| Beklenmedik kapanış (T15) | kart **Son Oturumu Kontrol Edin**; düğme **"Kontrol ettim"** | çökme, veri kaybı | Önceki oturum düzgün kapanmadıysa Genel Bakış'ta durur; diske yazılmış son ödünç ve iadeleri listeler. "Kontrol ettim" kartı bu oturum için kapatır |
| `Loan` | **ödünç** (ad), **ödünç ver** (eylem), **iade al** / **iade** | emanet, check-out, teslim (ödünç anlamında), "kitap çıkışı" | "Teslim" başka bir işlemdir (aşağıda) |
| `Loan.cardless` | **kartsız ödünç** | kartsız işlem, istisna | Yalnız yönetici kipinde, gerekçeli. Olağan yol kartın görevliye verilmesidir (Md. 23/1-a); kartsız ödünç bundan sapma olarak kayda işaretle geçer. Görevli kipinde yoktur: görevli kartı yanında olmayan üyeyi kütüphane yöneticisine yönlendirir |
| `Loan.override_reason` | **gerekçe** ("Gerekçeli istisna") | override, bypass | Yalnız gecikme engeline; yardım metni: "Sağlık ya da aile bilgisi yazmayın." |
| Ödünç sınırı (`loan_limit`, Md. 18/1) | **ödünç sınırı**; üye bağlamında **"Kalan ödünç hakkı: N"**; ret iletisi **"Ödünç sınırı dolu (en çok N kitap)."** | kota, limit, ödünç hakkı doldu (ileti olarak) | Üst değerler Yönetmelikten: öğrenciye 3, öğretmene 5 ("bir defasında"); okul daha düşük tutabilir, diğer personelin sınırı okulundur. Program üyenin elindeki (iade etmediği) kitapları sayar. **Hiçbir kipte istisna almaz**; Md. 16/1'de sayılan kaynaklar da öyle |
| Gecikme engeli (`block_loan_if_overdue`) | **gecikme engeli** (Kütüphane Politikası'nda **"Gecikmiş kitabı olana yeni ödünç verilmez"**); görevli iletisi **"Ödünç verilemiyor — kütüphane yöneticisine yönlendirin."**, yönetici iletisi **"Üyenin gecikmiş ödüncü var. Önce iade alın ya da gerekçeli istisnayla ödünç verin."** | ceza, yasak, kara liste, bloke, men | Okulun tercihidir, kapatılabilir; mevzuat hükmü diye sunulmaz. İstisnası yalnız yönetici kipinde ve gerekçeyle ("Gerekçeli istisna"). Gecikmenin karşılığı para ya da süre değişikliği değil, kişiye özel pusuladır |
| Yıl sonu (`last_loan_date`, `last_loan_date_graduating`) | **yıl sonu son ödünç tarihi**, **son sınıflar için son ödünç tarihi**; ret iletisi **"Yıl sonu son ödünç tarihi (gg.aa.yyyy) geçti — yeni ödünç verilmez. İade alınabilir."**; görevli kipinde tarihsiz: **"Yıl sonu son ödünç tarihi geçti — yeni ödünç verilmez. İade alınabilir."** | ödünç kapanışı, ödünç yasağı | Yalnız yeni ödüncü durdurur; iade sürer. Eski yılın tarihi yeni yılda uygulanmaz. Görevli iletisinde tarih yoktur: son sınıf tarihi kartın sahibinin son sınıfta olduğunu gösterirdi |
| Ödünç geçmişi | **ödünç kaydı**, **ödünç geçmişi** | **okuduğu kitaplar**, okuma karnesi, okuma puanı, okuma geçmişi | **Ödünç ≠ okuduğu kitap.** Öğrenci bazlı ödünç sayısı öğretmene ya da e-Okul'a aktarılmaz (tasarım §3) |
| İade tarihi | **iade tarihi**; gecikmişte **gecikme**, **"… gün gecikti"**; dönem sonu uyarısı **"İade tarihi (…) dönem sonundan (…) sonraya düşüyor. Süre kısaltılmaz."**; kapalı günler eksikse **"YYYY yılının resmî tatil ya da dini bayram günleri Kapalı Günler'de eksik; iade tarihi bir tatile rastlamış olabilir. Kütüphane yöneticisi Ayarlar → Kapalı Günler'den eklemelidir."** | son teslim tarihi, ceza, harç, uzatma | Programda uzatma, ceza ve harç yoktur. İade tarihi = verildiği gün + 15; kapalı güne rastlarsa izleyen ilk açık güne kayar. Kayma **iki ayrı kuraldır** ve Yönetmelikten gelmez: hafta sonu, resmî tatil ve dini bayram TBK 93'e kıyasen (idari izin programın kuralı, her zaman); ara tatil ve yarıyıl okulun tercihi (ayar). Kaydırılmış tarih "Md. 18 gereği" diye sunulmaz; Md. 18'e yalnız süre ve sayı cümlesinde atıf yapılır |
| `LibraryPolicy` | **Kütüphane Politikası** (Ayarlar sekmesi); bölümleri **Ödünç Sınırları** · **İade ve Yıl Sonu** · **Yönetici Kipi Süreleri** · **Vitrin ve Saklama** · **Künye Getirme** | ayarlar (tek başına), kurallar, ödünç ayarları | **Ödünç süresi burada AYAR DEĞİLDİR**: on beş gün sabittir (Md. 18/1) ve yalnız değiştirilemez bir bilgi satırıdır. Diğer personele ödünç açılırsa "Müdürlük kararı tarihi" ve "Müdürlük kararı sayısı" zorunludur. Yönetici kipi süreleri F7'den beri buradadır (aşağıda "Kip" satırı) |
| `Holiday.SCHOOL_BREAK` | **öğrenciye kapalı gün** (ara tatil, yarıyıl) | tatil (tek başına) | Kanunen tatil değildir; resmî ve dini tatil ayrı türdür |
| `Holiday` diğer türler | **resmî tatil**, **dini bayram**, **idari izin / diğer**; hepsinin üst adı **kapalı gün** (sayfa: "Kapalı Günler") | tatil günü (genel anlamda) | İdari izin kütüphanenin de kapalı olduğu gündür; iade tarihi hesabında resmî tatil gibi her zaman kapalı sayılır. Bu programın kuralıdır, TBK 93 kıyası altında anılmaz (`docs/mevzuat/BENIOKU.md` §4). Tahmini bayram tarihinde **"tahmini"** rozeti |
| `Delivery` (U11) | **teslim**: "sınıf kitaplığına teslim", "öğretmene teslim"; **teslim alan** (**Sınıf kitaplığı** · **Öğretmen**); **belge no**; **beklenen dönüş**; geri dönüşü **geri alma** (masada ve görevli ekranında düğme **"Teslimden geri al"**); belgeler **Teslim listesi** · **Geri alma dökümü** | ödünç, emanet, zimmet, zimmetli, "teslim alındı" (geri alma anlamında; Md. 19 adımı **"Bedel teslim alındı"** bunun dışındadır), iade (geri alma anlamında), gecikme (teslimde) | **Teslim ödünç değildir**: Md. 18 sayı sınırı ve on beş günlük süre uygulanmaz, üyelik gerekmez, teslim alanın ödünç hakkından düşmez ("kalan hak" dili yok). Yalnız etkin ders yılının şubesine ya da aktif öğretmene; diğer personele teslim yapılmaz. Toplu teslim tek işlemdir (bir kitap reddedilirse hiçbiri). Nüsha **Sınıf kitaplığında** görünür (öğretmene teslimde de); kime teslim edildiği Ağ Kataloğunda ve görevliye görünmez. Beklenen dönüşün geçmesi gecikme değildir (rozet **"beklenen dönüş geçti"**). Şube teslim listesi Dayanıklı Taşınırlar Listesi işlevini görür (TMY 23/6'ya **kıyasen**); sayımdaki yerini sayım kurulu seçer (32/5'e kıyasen). Teslim verme yönetici kipinde, geri alma görevli kipinde de |
| İlişik | **ilişik listesi**; **açık iş** ("kütüphaneyle açık işi olan kişi": iade edilmemiş ödünç, geri alınmamış teslim, çözülmemiş kayıp/hasar dosyası — **"Bedel teslim alındı"** dosyası hariç: o, kişinin değil **okulun açık işi**dir); **"Kütüphaneden ilişiği yoktur" belgesi** | borç, borçlu, ilişik kesme, ilişiği kesilmiştir, kara liste, yükümlülük (kullanıcı metninde; kod yorumunda serbest) | Karne ya da diplomanın ön koşulu diye SUNULMAZ; dayanağı yok (Md. 18 yalnız "iadesi sağlanır" der). Belgede ve ekranlarda "karne", "diploma" geçmez; kılavuz bunu tek bir olumsuz cümleyle söyler. Okuldan ayrılanlar listede kalır; sıra son sınıf → okuldan ayrılan → diğerleri. Ayrıntı §4.13 |
| `LossDamageCase` | **kayıp** (eylem **"Kayıp bildir"**), **hasar** (eylem **"Hasar dosyası aç"**), **kayıp dosyası** / **hasar dosyası**; **sorumlu** ("Sorumlu üye", "Sorumlu notu"); **tespit tarihi**; **bedel belirlendi**, **bedel teslim alındı**, **o günkü piyasa bedeli** (yalnız kayıt); **okulun açık işi**; **kayıttan düşme önerisi**; belge **Kayıp/hasar tutanağı** | zayi, telef, borç, ceza, tahsil edildi, ödendi, tazminat, "kayıp ödünç" | Bedel seçenekleri yalnız ortaöğretimde (Md. 19). Program tahsilat yapmaz ve disiplin sürecini başlatmaz (OKY 164/1-g okulun işidir). Bedel iki adımdır (25.09.2026 kullanıcı kararı): **"Bedel belirlendi"** kişinin açık işini sürdürür; **"Bedel teslim alındı"** bitirir (ilişik listesinden çıkar, "Kütüphaneden ilişiği yoktur" belgesi basılabilir), dosya ise **okulun açık işi** olarak "Bedelle aynısı alındı" ya da "Bedelle başka eser alındı" ile kapanana dek açık kalır. İki adım da yalnız kayıttır ve dosyayı kapatmaz; ikincisi geri alınmaz. Kayıp bildirimi ödüncü ya da teslimi **Kayba dönüştü** ile kapatır; "Bulundu" onları yeniden açmaz. Kayıttan düşme burada yalnız önerilir; asıl işlem TMY yoludur. Öneri geri alınabilir: "Kayıttan düşme önerildi" ile kapanan kayıp dosyasında kitap bulunursa "Bulundu" seçilir ("Bedelle başka eser alındı"da seçilemez). Açık hasar dosyalı kitap kaybolunca hasar dosyası **Kayba dönüştü** ile kapanır. Dosyanın kişisi önce üyeliktir, üyelik yoksa teslim alan. Çözüm adları §4.12 |
| Onarım (`CopyRepair`, `IN_REPAIR`) | **onarım**; eylemler **"Onarıma gönder"** · **"Onarımdan dön"**; nüsha durumu **Onarımda**; hasar dosyasının çözümü **Onarıldı** | tamir, bakım, servis | Hasar dosyası olmadan da onarıma gönderilir (Eser Ayrıntısı → **Kayıp, Hasar ve Onarım** bölümü). Onarımdaki nüsha ödünç ve teslim edilmez. Onarımdan dönüş hasar dosyasını kendiliğinden kapatmaz |
| Yıl akışları (§8.3) | **yıl sonu**, **yıl başı**, **kitap toplama**, **son sınıf**, **okuldan ayrılan** | yıl devri, yıl kapanışı, sınıf atlatma (program işi olarak), mezun listesi (belge adı olarak) | Son sınıf kademenin son sınıfıdır (4 · 8 · 12). Programda yeni yıla geçiş işlemi yoktur; sınıf atlama ve mezunların ayrılışı e-Okul aktarımı ve Ayrılış Havuzu'yla olur. Ekran ve adım adları §4.13 |
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
| Kip (U5) | **görevli kipi**, **yönetici kipi**, **kilitli**; eylemler **"Görevli kipine geç"**, **"Kilitle"**; süre alanları **"İşlem yapılmazsa kapanma süresi (dakika)"** · **"En uzun açık kalma süresi (dakika)"** (Kütüphane Politikası → **Yönetici Kipi Süreleri**) | öğrenci modu, admin modu, kiosk, oturum | Görevli kipinden çıkış yönetici parolası ister. Süreler: işlem yapılmazsa 1-15 dk (varsayılan 3), en uzun 5-120 dk (varsayılan 30); ilki ikincisini aşamaz, değişiklik bir sonraki işlemden geçerlidir |
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

*Aşağıdaki tablolar F7 sonundaki durumdur (25.09.2026); kaynak `AppShell.tsx`
(`NAV_ITEMS`, `PAGE_TITLES`), sayfaların h1'leri ve sekme tanımlarıdır.*

### 4.1 Sayfalar

| Gezinme etiketi | Sayfa başlığı (h1 = üst çubuk) | Adres | Not |
|---|---|---|---|
| Genel Bakış | Genel Bakış | `/` | Ana sayfanın tek adı |
| Dolaşım Masası | Dolaşım Masası | `/dolasim` | Ödünç, iade, nüsha durumu, kartsız ödünç ve gerekçeli istisna (F6). Görevli kipinde aynı masa **Görevli Kipi** sayfasında durur (§4.10) |
| — | Teslimler | `/dolasim/teslimler` | Menüde yoktur; Dolaşım Masası sayfasının sağ üstündeki **Teslimler** bağlantısıyla açılır. Sınıf kitaplığına ya da öğretmene toplu teslim, teslim kayıtları ve geri alma (F7, §4.12). Başlıkta "Dolaşım Masası / Teslimler". Yalnız yönetici kipinde; geri alma okutması görevli ekranında da vardır |
| — | Kayıp ve Hasar | `/dolasim/kayip-hasar` | Menüde yoktur; Dolaşım Masası sayfasının sağ üstündeki **Kayıp ve Hasar** bağlantısıyla açılır. Kayıp ve hasar dosyaları, çözüm adımları, onarım (F7, §4.12). `?dosya=<kimlik>` dosyayı doğrudan açar. Yalnız yönetici kipinde |
| Kişiler | Kişiler | `/kisiler` | |
| — | Gecikmiş Ödünçler | `/gecikmis-oduncler` | Menüde yoktur; Genel Bakış'taki **Gecikmiş Ödünçler** kartından açılır (kart yalnız gecikme varken görünür). İade hatırlatma pusulası ve gecikmiş ödünç listesi buradan basılır. Yalnız yönetici kipinde |
| — | İlişik Listesi | `/ilisik-listesi` | Menüde yoktur; Genel Bakış'taki **İlişik Listesi** kartından açılır. Kütüphaneyle açık işi olan kişiler, sınıf kitaplıkları, ilişik listesi ve "Kütüphaneden ilişiği yoktur" belgesi (F7, §4.13). Sağ üstte **Yıl Sonu** ve **Yıl Başı** bağlantıları. Yalnız yönetici kipinde |
| — | Yıl Sonu | `/yil-sonu` | Menüde yoktur; Genel Bakış'taki **Yıl Sonu** kartından (Mayıs-Haziran) ya da İlişik Listesi'nin sağ üstünden açılır. Adım adım ekran (§4.13). Yalnız yönetici kipinde |
| — | Yıl Başı | `/yil-basi` | Menüde yoktur; Genel Bakış'taki **Yıl Başı** kartından (yıl başı penceresinde) ya da İlişik Listesi'nin sağ üstünden açılır. Adım adım ekran; kayıt yazmaz, işin yapıldığı ekrana götürür (§4.13). Yalnız yönetici kipinde |
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

Ana gezinmenin sırası: Genel Bakış · Dolaşım Masası · Kişiler · Katalog · Ayarlar ·
Kılavuz. Görevli kipinde gezinme bağlantıları gösterilmez; her adreste görevli ekranı
durur. Görevli ekranının varsayılan işi **Dolaşım Masası**dır; oradan **Doğrulama
Okutması**, **Katalogda Ara** ve **Teslimden Geri Alma** (F7) açılır (bölüm
başlıkları; sayfanın h1'i ve üst çubuk "Görevli Kipi" kalır).

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
| Kişiler | **Öğrenciler** (`ogrenciler`) · **Öğretmenler ve Diğer Personel** (`personel`) · **Ayrılış Havuzu** (`havuz`) · **Üyeler** (`uyeler`) · **Üyelik İstek Listesi** (`uyelik-istekleri`) · **Kart Basımı** (`kart-basimi`) |
| Katalog | **Eserler** (`eserler`) · **Nüshalar** (`nushalar`) |
| Edinimler ve Bağışlar | **Edinim Partileri** (`partiler`) · **Bağış Ön Kayıtları** (`bagislar`) · **Komisyon Kararları** (`kararlar`) |
| Teslimler | **Teslim Kayıtları** (`kayitlar`) · **Yeni Teslim** (`yeni`) · **Geri Alma** (`geri-alma`) |
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
başındadır) · **Son Oturumu Kontrol Edin** (yalnız önceki oturum düzgün
kapanmadıysa; son ödünç ve iadeler, "Kontrol ettim") · **Gecikmiş Ödünçler**
(yalnız gecikme varken, yalnız sayı: "N ödüncün iade tarihi geçti." → Gecikmiş
Ödünçler) · **Ayrılış Havuzu** (yalnız havuz boş değilken: "N kişi ayrılış
kararı bekliyor" → Kişiler → Ayrılış Havuzu) · **Yıl Sonu** (yalnız yıl sonu
penceresinde — 1 Mayıs'tan 30 Haziran'a, ders yılı daha geç biterse bitişten iki
hafta sonrasına dek; yalnız sayı → Yıl Sonu) · **Yıl Başı** (yalnız yıl başı
penceresinde — 15 Ağustos-31 Ekim ya da ders yılı başlangıcının çevresi — ve adımları
bitmemişken → Yıl Başı) · **Kişiler** · **Ayarlar** · **İlişik Listesi** ·
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

### 4.10 Dolaşım Masası ve görevli ekranının adları

Kılavuz bu adları birebir kullanır; ekrandaki metin değişirse buradaki de değişir
(kaynak `frontend/src/modules/dolasim`, iletiler `services/circulation.py` ve
`services/masa.py`).

**Dolaşım Masası** (yönetici kipinde sayfa, görevli kipinde **Görevli Kipi**
sayfasının varsayılan işi). **Okutun** kartında tek okutma kutusu: **"Üye kartı ya
da kütüphane etiketi"**; düğmeler **"Kartsız ödünç"** (yalnız yönetici kipinde) ve
**"Okuma sesi açık"** / **"Okuma sesi kapalı"**; işaret kutusu **"Yalnız durum
sor"**. Kutunun altında gerektiğinde **"Sırada bekleyen okutma: N"** ve odak
uyarısı (**"Kutuya dön"**) durur. Üye bağlamı kartı: **Üye** (ad), **"Kalan ödünç
hakkı: N"**, düğme **"Bitti"**; yönetici kipinde ayrıca üye türü, sınıf ve **"Açık
ödünçler"** (her satırda **"Kayıp bildir"** kısayolu — F7, §4.12; kayıptan sonra
masada **"Kayıp bildirildi; ödünç kayba dönüştü ve kayıp dosyası açıldı."** yazar ve
kalan hak sunucudan yeniden okunur). Görevli kipinde bağlamda yalnız ad ve kalan hak
durur; kayıp bildirimi kısayolu yoktur. Sayfanın sağ üstünde **Teslimler** ve
**Kayıp ve Hasar** bağlantıları durur (yalnız yönetici kipinde).

| Kavram | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| Üye bağlamı | **üye bağlamı**; kapanış iletileri **"Üye bağlamı kapandı."** ve **"Üye bağlamı kapandı: 60 saniye işlem yapılmadı."** | oturum, seans, aktif üye | 60 saniye işlem yoksa, "Bitti" ile ya da başka kart okutulunca kapanır |
| Masa iletileri | **"Ödünç verildi."** · **"İade alındı."** · **"Rafta — ödünç değil."** · **"Kayıp kaydında."** · **"Onarımda."** · **"Sınıf kitaplığında."** · **"Bu kitap başka bir üyede. Önce iade alınsın mı?"** (düğme **"İade al ve ödünç ver"**) · **"Bu kitap zaten bu üyede. İade alınsın mı?"** (düğme **"İade al"**) · üyeye bağlı retlerin (üyelik sonlanmış, ayrılmış, yıl sonu, gecikme, ödünç sınırı) altında **"Kitap iade için getirildiyse iadesi alınabilir."** (düğme **"İade al"**) · teslimdeki kitapta **"Sınıf kitaplığında."** altında **"Kitap sınıf kitaplığından ya da öğretmenden geri geldiyse teslimden geri alınabilir."** (düğme **"Teslimden geri al"**, görevli kipinde de; kime teslim edildiği yazmaz) | iade edildi (ileti olarak), teslim alındı | Görevli kipinde gecikmesi olan üyede TEK ileti: **"Ödünç verilemiyor — kütüphane yöneticisine yönlendirin."** Kişisel olmayan sebepler yazılır (ödünç sınırı, "Ödünç verilmez — kütüphanede okunur."). Görevli kipinde üyeye bağlı retler, kitabın kimde olduğundan ÖNCE verilir: gecikmeli ya da sınırı dolu üyede her kitap aynı iletiyi alır |
| Kart iletileri | **"İptal edilmiş kart — kütüphane yöneticisine yönlendirin."** · **"Bu kart tanınmadı — kütüphane yöneticisine yönlendirin."** · **"Kart numarası hatalı. Kartı yeniden okutun."** | geçersiz kart (ileti olarak), kayıtsız kart | "Tanınmadı": numara doğru biçimde ama programda yok; "hatalı": sağlama hanesi tutmuyor (okuma ya da yazım hatası) |
| Kart okutma kilidi | şerit (pencere değil) **"Kart okutma durduruldu"**, alan "Yönetici parolası", düğme **"Kart okutmayı aç"**; iletiler **"Art arda 5 geçersiz kart okutuldu. …"** · **"Son 10 dakikada 5 tanınmayan ya da iptal edilmiş kart okutuldu. …"**; şeritteki not **"İade almak kilitlenmez: üye kartı okutmadan kitabın kütüphane etiketini okuttuğunuzda iadesi alınır."** | hesap kilidi, bloke | Görevli kipinde art arda beş geçersiz kart ya da on dakikada beş tanınmayan/iptal edilmiş kart okutmasından sonra (araya geçerli kart girse de); yönetici parolası görevli kipinden çıkmadan girilir. Şerit dururken okutma kutusu açıktır: İade kilitlenmez |
| Gerekçeli istisna | pencere **"Gerekçeli istisna"** (en üstte **"Kitap: 2026-000123 — Eser adı"**), alanlar **"Gerekçe"** ve **"Açıklama"** (yardım **"Sağlık ya da aile bilgisi yazmayın."**), düğme **"Gerekçeyle ödünç ver"**; gerekçeler **"Ders ya da ödev için gerekli"** · **"Gecikmenin geçerli bir mazereti var"** · **"Gecikmiş kaynağın iadesi için görüşüldü"** · **"Diğer"** | override, bypass, muafiyet | Yalnız yönetici kipinde ve yalnız gecikme engeline |
| Kartsız ödünç | pencere **"Kartsız ödünç"**, alan **"Okul no ya da ad"**, düğmeler **"Ara"** ve **"Üyeyi aç"**; gerekçeler **"Kart yanında değil"** · **"Kart kayıp — yenilenecek"** · **"Kart henüz basılmadı"** · **"Kart okunmuyor"**; bağlamdaki şerit **"Kartsız ödünç — gerekçe: …"** | kartsız işlem | Yalnız yönetici kipinde |
| Nüsha durum sorgusu | **"Yalnız durum sor"**; iletiler **"Ödünçte."** · **"Rafta — ödünç verilebilir."**; üye kartı okutulunca **"“Yalnız durum sor” kapatıldı: üye kartı okutuldu."** | stok sorgusu | Yazma yapmaz; görevli kipinde kitabın kimde olduğu gösterilmez. Sesi ödünçten ayrıdır (iki kısa ses) |
| Ödünç retleri | **"Üyelik sonlanmış — ödünç verilemez."** · **"Üye okuldan ayrılmış — ödünç verilemez."** · **"Diğer personele ödünç verilmiyor (Kütüphane Politikası)."** · **"Ödünç sınırı dolu (en çok N kitap)."** · nüshanın gerekçesi (**"Ödünç verilmez — kütüphanede okunur."** vb.) · yıl sonu ve gecikme iletileri (§1) | ödünç reddedildi (tek başına), hata | Hepsi kişisel veri taşımaz ve görevli kipinde de yazılır; TEK istisna gecikmedir (görevliye yalnız "Ödünç verilemiyor — kütüphane yöneticisine yönlendirin.") |
| Masadaki bilgi iletileri | **"Kitabın kütüphane etiketini okutun."** (kart okundu, sıra kitapta) · **"Üye kartı okundu."** · **"Kart okutma yeniden açıldı."** · **"Gerekçeli istisnayla ödünç verildi."** · başka üyedeki kitap iade alınıp verilince **"Kitap başka bir üyenin ödüncündeydi; iadesi alındı. Durumu kütüphane yöneticisine bildirin."**; "İade al ve ödünç ver" sürerken bağlam değişince **"İade alındı; üye bağlamı bu arada değiştiği için kitap ödünç verilmedi."**; yönetici kipinde iade **"İade alındı. N gün gecikti."** | — | Masadaki son işlemler listesinin (**"Bu ekrandaki son işlemler"**) satırlarıdır; görevli kipinde satırlarda üye adı yazmaz |
| Etiket ve kod iletileri | **"Bu ISBN barkodu. Kitabın kütüphane etiketini okutun."** · **"Bu bir üye kartı. Kitabın kütüphane etiketini okutun."** · **"Bu kod tanınmadı. Kitabın kütüphane etiketini ya da üye kartını okutun."** · **"Bu barkodla kayıtlı nüsha yok. Kitabı ayırın ve kütüphane yöneticisine gösterin."** · bağlanmamış boş etiket ve numarası iptal edilmiş etiket için Doğrulama Okutması'ndaki iletiler; görevli kipinde sonları **"Kitabı ayırın ve kütüphane yöneticisine gösterin."** | geçersiz barkod, hatalı etiket | Görevli kipinde Hızlı Kayıt yönergesi verilmez (ekran görevliye kapalıdır), kitap yöneticiye yönlendirilir |
| Görevli ekranının işleri | bölüm başlıkları **Dolaşım Masası** · **Doğrulama Okutması** · **Katalogda Ara** · **Teslimden Geri Alma** (F7); düğmeler **"Doğrulama okutmasını aç"** / **"Okutmayı bitir"**, **"Katalogda ara"** / **"Dolaşım masasına dön"**, **"Teslimden geri al"** / **"Okutmayı bitir"**, **"Yönetici kipine geç"** | kiosk, öğrenci ekranı | Katalogda Ara'da alan **"Kaynak adı, yazar, konu ya da ISBN"**; künye ve nüsha durumu görünür, edinim ve kimde olduğu görünmez |

### 4.11 Üyelik ekranlarının ve belgelerinin adları

Kılavuz bu adları birebir kullanır; ekrandaki metin değişirse buradaki de değişir
(kaynak `frontend/src/modules/uyelik`, belgeler `apps/kutuphane/dolasim_belgeleri.py`).

**Kişiler → Üyeler.** Kart başlığı **Kütüphane Üyeleri** ("N üyelik"), düğme
**"Personele üyelik aç"**; süzgeçler "Ara" (yer tutucu "Ad soyad, okul no ya da kart
no…", yardım "Okul no ve kart no tam yazılarak aranır."), "Durum", "Üye türü",
"Şube"; sütunlar Ad soyad · Sınıf / üye türü · Kart no · Durum · Açık ödünç · Üye
kartı. Satıra tıklanınca **Üyelik** penceresi: alanlar Ad soyad · Sınıf / üye türü ·
Kart no · Durum · Üyelik başlangıcı · Üye kartı · Açık ödünç / sınır · Kalan ödünç
hakkı · Gecikmiş ödünç; düğmeler **"Kartı yenile"** (onay "Kart yenilensin mi?") ·
**"Üyeliği sonlandır"** (pencere **Üyeliği sonlandır**, alan "Sonlandırma nedeni") ·
**"Üyeliği sil"** (onay "Üyelik silinsin mi?"); gecikme varsa iade hatırlatma
pusulasının basım kartı; bölüm **Ödünç Kaydı**. Personel penceresi **Personele
üyelik aç**: alan "Öğretmen ya da diğer personel", düğme **"Üyelik aç"**. Sekmenin
altında **Üyelik Belgeleri** bölümü: kütüphane aydınlatma metni ("Başvuru adresi",
"E-posta ya da telefon") ve masa kartı; her birinde "Önizle" · "PDF'i indir".

**Kişiler → Üyelik İstek Listesi.** "Şube", **"Üyelik isteği tarihi"** (yardım
"Öğrencilerin üyelik istediği gün."), düğme **"Seçilenleri üye yap"**; onay
başlığı "N öğrenciye üyelik açılsın mı?", düğmesi **"Üyelik aç"**. Tablo Okul no ·
Ad soyad · Sınıf · Üyelik (rozet **Üye**); başlıktaki kutu "Üye olmayanların tümünü
seç".

**Kişiler → Kart Basımı.** Listeler **Kart Basımı Bekleyen** · **Kartı Basılmış**;
süzgeçler "Ara", "Şube", "Üye türü"; tablo Ad soyad · Sınıf / üye türü · Kart no ·
Üyelik başlangıcı (basılmışta "Basıldı"). **Basım Ayarları** kartı: "Kart şablonu:
…", tabaka ızgarası, "Yazıcı (kalibrasyon)", "Başlangıç hücresi", **"Kesim çizgisi
bas"**; düğmeler "Önizle" · "PDF'i indir" · **"Basıldı olarak işaretle"** ya da
**"Basım işaretini geri al"**; altta **"Yazıcı kalibrasyonunu göster"** /
**"Yazıcı kalibrasyonunu gizle"**.

**Gecikmiş Ödünçler** (sayfa). Süzgeç "Şube" ("Bütün okul"); pusula için
"Önizle" · "PDF'i indir" (kişi seçilmezse süzgeçteki herkese); tablo Ad soyad ·
Sınıf / üye türü · Kaynak adı · Barkod · İade tarihi · Gecikme; altta gecikmiş ödünç
listesinin basım kartı (dipnot §5).

**Belge adları** §2'deki yazımla: **Üye kartı** · **İade hatırlatma pusulası** ·
**Gecikmiş ödünç listesi** · **Kütüphane aydınlatma metni** · **Masa kartı**. Kılavuz
belgeleri bu adlarla anar; §3'e göre başlık yerinde de bu yazım kullanılır.
Pusulanın dış yüzünde **"KİŞİYE ÖZELDİR"**, iç yüzünde **"İADE HATIRLATMASI"** ve
**"GECİKMİŞ KAYNAKLAR"** yazar; masa kartının bölümleri **"MASADA NASIL ÇALIŞILIR"**
ve **"GİZLİLİK"**tir.

### 4.12 Teslim ve Kayıp/Hasar ekranlarının adları

Kılavuz bu adları birebir kullanır; ekrandaki metin değişirse buradaki de değişir
(kaynak `frontend/src/modules/teslim` ve `frontend/src/modules/kayip`, iletiler
`services/deliveries.py` ve `services/loss_damage.py`). F7'de eklendi.

**Teslimler → Teslim Kayıtları.** Süzgeçler "Durum" (**Teslimde** · **Geri alındı** ·
**Kayba dönüştü**; varsayılan Teslimde), "Teslim alan" (**Sınıf kitaplığı** ·
**Öğretmen**), "Belge no" (düğmeler **"Ara"**, **"Temizle"**); tablo Belge no ·
Teslim alan · Barkod · Kaynak adı · Teslim tarihi · Beklenen dönüş · Durum. Beklenen
dönüşü geçmiş açık teslimde rozet **"beklenen dönüş geçti"** (gecikme DEĞİLDİR; ceza
ya da hatırlatma dili yok). Belge no'ya tıklanınca liste o belgeye süzülür ve
**"Teslim listesi — belge no …"** kartında "Önizle" · "PDF'i indir" durur; aynı kartın
**Geri alma dökümü** bölümü o belgenin bütün satırlarını durumlarıyla basar (görevli
kipinde, masada ya da başka oturumda geri alınanlar dahil). Açık teslimde **"Kayıp
bildir"**.

**Teslimler → Yeni Teslim.** Kart **Teslim Alan**: seçim **Sınıf kitaplığı** /
**Öğretmen**; alanlar "Şube" (yalnız etkin ders yılının şubeleri) ya da "Öğretmen"
(diğer personel listede görünür ama seçilemez: **"diğer personele teslim
yapılmaz"**), "Teslim tarihi", "Beklenen dönüş (isteğe bağlı)" (boşsa ders yılının son
günü), "Belge no (isteğe bağlı)" (boşsa program verir). Kart **Teslim Edilecek
Kitaplar**: okutma kutusu **"Kütüphane etiketi"**, **"Listede N kitap"**, satırda
**"Çıkar"**, **"Listeyi boşalt"** (onay "Liste boşaltılsın mı?"), **"Teslim et"**
(onay başlığı **"N kitap 9/A sınıf kitaplığına teslim edilsin mi?"** ya da **"N kitap
… adlı öğretmene teslim edilsin mi?"**). İletiler **"Bu kitap zaten listede."** ·
retlerde kitabın numarası, adı ve sunucunun gerekçesi ("2026-000123 — Kaynak adı:
**Ödünçte — teslim edilemez.**" vb.); reddedilenler sonraki okutmada silinmeyen
**Listeye girmeyen kitaplar** listesinde durur · okutma kutusu odakta değilse
BarcodeInput'un odak uyarısı ve **"Kutuya dön"** · toplu retlerde
**"Listedeki bazı kitaplar teslim edilemiyor; hiçbir teslim yapılmadı."** ve kitap
kitap liste · başarıda **"N kitap teslim edildi."** (sonuç kartında belge no, teslim
listesi basımı ve **"Yeni teslim"**). Sayı sınırı yoktur; "kalan hak" dili kullanılmaz.

**Teslimler → Geri Alma** (görevli kipinde **Teslimden Geri Alma**). Kart **Geri
Alınan Kitapları Okutun**, okutma kutusu **"Kütüphane etiketi"**, sayaç **"Bu ekranda
geri alınan: N"**, liste **"Son okutmalar"**. İletiler **"Geri alındı."** · **"Bu
kitap teslimde değil (…)."** · **"Bu kitap teslimde değil (Ödünçte). İade için dolaşım
masasını kullanın."**. Yönetici kipinde satırda teslim alan, belge no ve teslim
tarihi; altta **Geri alma dökümü** kartı ("Önizle" · "PDF'i indir"). Görevli kipinde
teslim alanın kimliği ve evrak yoktur.

**Kayıp ve Hasar** (sayfa). Sağ üstte **"Hasar dosyası aç"** ve **"Kayıp bildir"**;
süzgeçler "Görünüm" (**Çözülmemiş dosyalar** · **Bütün dosyalar**), "Tür" (**Kayıp** ·
**Hasar**), bütün dosyalarda "Çözüm" (bedel çözümleri yalnız ortaöğretimde); tablo Barkod · Kaynak adı · Tür · Sorumlu ·
Tespit tarihi · Çözüm · Nüsha durumu (bedeli teslim alınmış dosyanın Çözüm hücresinde alt satır
**"Okulun açık işi"**). Dosya açma pencereleri (başlık soru, gövde
sonuç): **"Kayıp bildirilsin mi?"** (düğme **"Kayıp bildir"**) · **"Hasar dosyası
açılsın mı?"** (düğme **"Hasar dosyası aç"**, kutu **"Nüshayı onarıma da gönder"**);
alanlar "Kütüphane etiketi" (nüsha önceden seçilmemişse), "Tespit tarihi", "Sorumlu
üye (isteğe bağlı)" (ödünçteki kitapta sorulmaz: **"Sorumlu, kitabı ödünç alan
üyedir; ödünç kaydından belirlenir."**), "Sorumlu notu (isteğe bağlı)" (yardım
**"Üye olmayan sorumlu ya da kısa açıklama. Sağlık ya da aile bilgisi yazmayın."**).
Başarı iletileri **"Kayıp bildirildi; kayıp dosyası açıldı."** · **"Hasar dosyası
açıldı."**. Dosya penceresi **Kayıp dosyası** / **Hasar dosyası**: alanlar Nüsha ·
Nüsha durumu · Dosya türü · Tespit tarihi · Sorumlu üye · Çözüm · Kaydedilen piyasa
bedeli · Bedel belirlendi · Bedel teslim alındı · Kapanış · Kayıttan düşme önerisi;
**"Notu kaydet"**; bölüm **Çözüm** (yalnız
sunucunun izin verdiği çözümlerin düğmeleri; ortaöğretim dışında **"Bedel seçenekleri
yalnız ortaöğretim okullarında sunulur (Yönetmelik Md. 19). …"**; bedeli teslim alınmış
dosyada **"Bedel teslim alındı: kişinin kütüphaneyle açık işi kalmadı; İlişik Listesi'nde
görünmez ve “Kütüphaneden ilişiği yoktur” belgesi basılabilir. Dosya okulun açık işi olarak
kalır; bedelle alınan kaynak kaydedilince kapanır."**; kayıttan düşme
önerisiyle kapanmış kayıp dosyasında yalnız **"Bulundu"** ve açıklama **"Kayıttan düşme
yalnız önerildi; nüsha hâlâ “Kayıp”. Kitap bulunduysa “Bulundu” seçin: öneri geri alınır ve
nüsha rafa döner."**); bölüm **Onarım**
(**"Onarıma gönder"** / **"Onarımdan dön"**); **Kayıp/hasar tutanağı** basımı. Çözüm
onayı pencerenin kendisidir: başlık **"“…” işlensin mi?"**, düğme **"İşle"**; yalnız
"Bedel belirlendi"de alan **"O günkü piyasa bedeli (TL)"** (yardım **"Yalnız kayıt içindir;
program tahsilat yapmaz."**; teslim alınan bedel sonradan değişmez). Onarım onayları **"Nüsha onarıma gönderilsin mi?"** ·
**"Nüsha onarımdan dönsün mü?"**.

| Kavram | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| Teslim durumu | **Teslimde** · **Geri alındı** · **Kayba dönüştü** | iade edildi, emanette, zimmette | `DeliveryStatus` ile birebir |
| Teslim alan | **Sınıf kitaplığı** · **Öğretmen** | sınıf (tek başına), zimmetli | Teslim yalnız etkin ders yılının şubesine ya da aktif öğretmene yapılır |
| Dosya türü | **Kayıp** · **Hasar** (pencere başlıkları "Kayıp dosyası" / "Hasar dosyası") | zayi, telef | `CaseType` ile birebir. Bir nüshanın aynı anda tek çözülmemiş dosyası olur |
| Çözüm durumları | **Çözüm bekliyor** · **Bedel belirlendi** · **Bedel teslim alındı** · **Bulundu** · **Aynısı temin edildi** · **Onarıldı** · **Bedelle aynısı alındı** · **Bedelle başka eser alındı** · **Kayıttan düşme önerildi** · **Kayba dönüştü** | borç, ceza, tahsil edildi, ödendi, zayi, kayıttan düşüldü, bedel kaydedildi (iki adım ayrıdır) | `CaseResolution` ile birebir. Bedel yolları yalnız ortaöğretimde ve sırayla: "Bedel belirlendi" → "Bedel teslim alındı" → "Bedelle aynısı / başka eser alındı". Açık dosyalar "Çözüm bekliyor", "Bedel belirlendi" ve "Bedel teslim alındı"dır; kişinin açık işi yalnız ilk ikisidir. Kayıttan düşme burada yalnız öneridir. "Kayba dönüştü" düğme değildir: yalnız hasar dosyasında, kayıp bildiriminin kapattığı dosyada görünür |
| Ödünç durumu (F7) | **Kayba dönüştü** (Üyelik → Ödünç Kaydı satırında "kayba dönüştü") | kayıp ödünç, iptal | Kayıp bildirimiyle kapanan ödünç; sayı sınırına ve gecikmeye sayılmaz |
| Teslim, dosya ve onarım iletileri | **"Teslim edilebilir."** (teslim listesine okutma ön denetimi) · **"Geri alındı."** · **"Bu kitap teslimde değil (…)."** · **"Bu kitap teslimde değil (Ödünçte). İade için dolaşım masasını kullanın."** · **"Teslim yalnız etkin ders yılının şubesine yapılır."** · **"Teslim yalnız sınıf kitaplığına ya da öğretmene yapılır; diğer personele teslim yapılmaz."** · **"Nüsha onarıma gönderildi."** · **"Nüsha onarımdan döndü; rafta."** · **"Onarıma yalnız raftaki nüsha gönderilir (…)."** · **"Onarımdaki nüsha için kayıp bildirilemez; önce onarımdan dönüşünü işleyin."** · **"Ödünçteki nüsha için önce iade alın; hasar dosyası iadeden sonra açılır."** · **"Teslimdeki nüsha için önce geri alın; hasar dosyası geri almadan sonra açılır."** · silme engelleri **"Bu şubede N açık teslim var; önce geri alın."**, **"Bu şubenin tesliminden doğan N çözülmemiş kayıp/hasar dosyası var; önce dosyayı çözün."** ve **"Bu kişiye kütüphaneden teslim yapılmış; kaydı silinemez. Okuldan ayrıldıysa “Ayrıldı olarak işaretle” eylemini kullanın."** · birleştirme engeli **"Birleştirilecek kaydın N açık teslimi var; teslim yalnız öğretmene yapılır. Kalacak kaydın üye türü “Öğretmen” olmalıdır ya da önce teslimleri geri alın."** | iade edildi (geri alma iletisi olarak), teslim alındı, tamir edildi | Kaynak `services/deliveries.py`, `services/loss_damage.py`, `views_teslim.py`; hiçbiri kişi adı taşımaz. Görevli kipindeki geri almada da aynı iletiler yazılır, teslim alanın kimliği yazılmaz |

**Eser Ayrıntısı → Nüshayı düzenle.** Bölüm **Kayıp, Hasar ve Onarım**: teslimdeki
nüshada **"Teslimde — Sınıf kitaplığı: 9/A · belge no … · teslim …"**, çözülmemiş
dosyada **"Çözülmemiş kayıp dosyası · tespit … · …"** (kayıp nüshada son dosya, kapanmış
da olsa: **"Kayıp dosyası · tespit … · …"**) ve bağlantı **"Dosyayı göster"**;
düğmeler durumuna göre **"Onarıma gönder"** · **"Onarımdan dön"** · **"Hasar dosyası
aç"** · **"Kayıp bildir"**. Pencerede ayrıca bilgi satırı **Durum**.

**Ayarlar → Kütüphane Politikası → Yönetici Kipi Süreleri.** Alanlar **"İşlem
yapılmazsa kapanma süresi (dakika)"** (1-15; en uzun süreyi aşamaz) ve **"En uzun açık
kalma süresi (dakika)"** (5-120). Değişiklik bir sonraki işlemden itibaren geçerlidir.

### 4.13 İlişik ve yıl akışı ekranlarının ve belgelerinin adları

Kılavuz bu adları birebir kullanır; ekrandaki metin değişirse buradaki de değişir
(kaynak `frontend/src/modules/yil`, belgeler `apps/kutuphane/ilisik_belgeleri.py` ve
`teslim_belgeleri.py`). F7'de eklendi.

**İlişik Listesi** (sayfa). Süzgeçler **"Kapsam"** (**Bütün kişiler** · **Son
sınıflar** · **Okuldan ayrılanlar** · **Son sınıflar ve okuldan ayrılanlar** ·
**Diğerleri**), "Şube" ("Bütün okul"), "Ara" (yer tutucu "Ad soyad ya da okul no…",
yardım "Okul no tam yazılarak aranır."); tablo Ad soyad · Sınıf / üye türü · Durum ·
Açık işler. Durum rozetleri **"Son sınıf"** · **"Ayrıldı · gg.aa.yyyy"** ·
**"Ayrılış kararı bekliyor"**. Açık işler özeti **"N ödünç (M gecikmiş) · N teslim ·
N kayıp/hasar dosyası"**, altında satır satır Ödünç / Teslim / Kayıp / Hasar. Boş
listede **"Bu seçimde kütüphaneyle açık işi olan kişi yok."** Kartlar **Sınıf
Kitaplıkları** (Şube · Ders yılı · Kitap · Belge no · Teslim listesi; şube teslimi
kişiye bağlı değildir, ayrı durur; **"önceki ders yılı"** notu) · **İlişik Listesi**
(toplu belgenin kartı; "Önizle" · "PDF'i indir") · **Kütüphaneden İlişiği Yoktur Belgesi**
(alan **"Kişi"**, düğme **"Ara"**; yalnız açık işi olmayan kişi seçilebilir). Kılavuz bu
iki kartı ekrandaki başlığıyla anar; belgelerin kendisini cümle içinde §2'deki adla
("İlişik listesi", "Kütüphaneden ilişiği yoktur" belgesi) anlatır.

**Yıl Sonu** (sayfa). Adım rayı: **Son Ödünç Tarihleri** · **Kitap Toplama** ·
**Son Sınıflar ve Ayrılanlar** · **İlişik ve Belgeler**; düğmeler **"Geri"**,
**"Devam"**. Adım 1'de alanlar **"Yıl sonu son ödünç tarihi"** ve **"Son sınıflar için
son ödünç tarihi"** (yardım "İsteğe bağlı; daha erken bir tarih."), düğme **"Kaydet"**,
ileti **"Son ödünç tarihleri kaydedildi."**; eski yılın tarihi için **"Kayıtlı … son
ödünç tarihi (gg.aa.yyyy) önceki ders yılına ait; bu yıl uygulanmaz."** Adım 2'de
görünür başlık ve tablo **Toplanacak kitaplar**, belge kartı **İade Hatırlatma Pusulası** (alan **"Son
getirme günü"**, yardım "Pusulaya yazılır; kaydedilmez.") ve **Sınıf Kitaplıkları**.
Adım 3'te son sınıfların ve okuldan ayrılanların ilişik listesi basımı ("Önizle" · "PDF'i
indir") ve yalnız son sınıf şubelerinin **Sınıf Kitaplıkları** kartı. Adım 4'te seçici
**"Son sınıf şubesi"** ("Bütün son sınıflar"), bağlantı **"İlişik Listesi'ni aç"** ve belge
basımı (tek seferde en çok 150 belge). Sağ üstte **İlişik Listesi** ve **Yıl Başı**
bağlantıları. Genel Bakış kartının bağlantısı **"Yıl Sonu'nu aç"**.

**Yıl Başı** (sayfa). Adım rayı: **Ders Yılı** · **e-Okul Listeleri** · **Ayrılış
Havuzu** · **Kapalı Günler**; her adımda işin yapıldığı ekrana bağlantı
(**"Ders Yılları'nı aç"** · **"Öğrencileri aç"** · **"Öğretmenler ve Diğer Personel'i
aç"** · **"Ayrılış Havuzu'nu aç"** · **"Kapalı Günler'i aç"**). Programda "yıl devri"
işlemi yoktur; ekran bunu söyler (kılavuz "yeni yıla geçiş için ayrı bir işlem yoktur"
der ve bu sözcüğü kullanmaz). Sağ üstte **İlişik Listesi** ve **Yıl Sonu** bağlantıları.
Genel Bakış kartının bağlantısı **"Yıl Başı'nı aç"**.

| Kavram | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| Yıl akışları | **yıl sonu**, **yıl başı**, **kitap toplama**, **son sınıflar**, **okuldan ayrılanlar** | yıl devri, yıl kapanışı, mezun listesi (belge adı olarak), sınıf atlatma (program işi olarak) | "Son sınıf" kademenin son sınıfıdır (4 · 8 · 12); kademe seçilmemişse son sınıf yoktur |
| E5 belgesi | başlık **"KÜTÜPHANEDEN İLİŞİĞİ YOKTUR BELGESİ"**; hüküm **"… iade edilmemiş ödünç kaynağı ve kayıp ya da hasar nedeniyle kendisinden beklenen bir işlem bulunmamaktadır. Kütüphaneden ilişiği yoktur."** (personelde "geri alınmamış teslimi" de; "çözülmemiş kayıt" denmez: bedeli teslim alınmış dosya okul için açık kalır ama kişinin işi değildir); konum kalıbı **"Bu belge, okulun kütüphane işlerini yürüttüğü yerel araçtaki kayıtlara göre düzenlenmiştir. Okul Kütüphaneleri Yönetmeliği Md. 18'deki “… alınan ödünç kitabın kütüphaneye iadesi sağlanır.” hükmünün uygulanmasına yöneliktir; Bakanlık otomasyon sistemindeki kaydın yerine geçmez."** | karne, diploma, borç, ilişik kesme | Yalnız açık işi olmayan kişiye; kişi başına bir sayfa. Açık işi olan seçilince **"Seçilenlerden N kişinin iade edilmemiş kaynağı, geri alınmamış teslimi ya da çözülmemiş kayıp/hasar dosyası var; belge basılmadı. İlişik listesine bakın."** (ad yazmaz) |
| İlişik listesi (belge) | başlık **"İLİŞİK LİSTESİ"**, sütunlar Sıra · Ad soyad · Sınıf / üye türü · Durum · Ödünç · Teslim · Dosya · Açık işler; ikinci tablo **"SINIF KİTAPLIKLARINDAKİ AÇIK TESLİMLER"**; her sayfada §5 dipnotu | borç listesi, kara liste | Kaynak adı ve okul no BASILMAZ (yalnız barkod, iade tarihi, belge no) |
| Yıl sonu pusulası | belge adı **İade hatırlatma pusulası** (E4 biçimi); iç başlık **"İADE HATIRLATMASI"**, kaynak başlığı **"İADE EDİLECEK KAYNAKLAR"**; metin **"Ders yılı sona eriyor. Kütüphaneden ödünç aldığınız, sağda yazılı kaynakları ders yılı bitmeden (ya da: en geç gg.aa.yyyy tarihine kadar) kütüphaneye getirin."** | ihtar, son uyarı | Kişinin BÜTÜN açık ödünçleri (gecikmemişler dahil); dış yüz E4'le aynıdır |
| E15 belgeleri | **"TESLİM LİSTESİ"** (şubede not: "… Dayanıklı Taşınırlar Listesinin işlevini görür (Taşınır Mal Yönetmeliği md. 23/6'ya kıyasen). Teslim ödünç değildir."; imza **"Teslim eden — Kütüphane yöneticisi"** / **"Teslim alan — Sınıf kitaplığı sorumlusu"** ya da **"— Öğretmen"**) · **"GERİ ALMA DÖKÜMÜ"** (durumlar **"Geri alındı · gg.aa.yyyy"** · **"Teslimde"** · **"Kayba dönüştü · gg.aa.yyyy"**; özet **"N kitap geri alındı · N kitap teslimde · N kitap kayba dönüştü"**) | zimmet, emanet | Şubenin güncel teslim listesi de basılabilir (Sınıf Kitaplıkları kartı) |
| E6 belgesi | başlık **"KAYIP/HASAR TUTANAĞI"**; bölümler **KAYNAK** · **İLGİLİ KİŞİ** · **ÇÖZÜM**; imza **Kütüphane yöneticisi** · **İlgili kişi** · **Okul müdürü**; bedel **"… TL (kayıt); gg.aa.yyyy tarihinde belirlendi, gg.aa.yyyy tarihinde teslim alındı"** (iki adımın tarihleri; teslim alınmamışsa yalnız ilki) | zayi, telef, borç, ceza, tahsil edildi | Md. 19 alıntısı ve **"Bu tutanak bir ödeme ya da tahsilat belgesi değildir."** YALNIZ ortaöğretimde |

## 5. Kişisel veri ve metin

- **Görevli kipindeki iletilerde okuma bilgisi yoktur.** Gecikmesi olan üyede
  eser adı ve gecikme günü gösterilmez: "Ödünç verilemiyor — kütüphane
  yöneticisine yönlendirin." Kişisel olmayan sebepler yazılabilir: "sınır
  dolu", "bu kaynak ödünç verilmez".
- Kartla üye çözümlemesinde görevli yalnız **ad** ve **kalan ödünç hakkını**
  görür; sınıf yazılmaz.
- Görevli kipinde iade iletisinde ödünç alanın kimliği ve gecikme günü, durum
  sorgusunda kitabın kimde olduğu, masadaki son işlemler listesinde üye adı
  yazılmaz. Başka üyedeki kitapta önceki üyenin adı görevliye gösterilmez.
- İade hatırlatma pusulası tek kişiliktir; katlanınca dışta "KİŞİYE ÖZELDİR",
  kişinin adı ve sınıfı (personelde üye türü), katlama yönergesi ve "Kişinin
  kendisine elden verilir; sınıfta okunmaz." notu (personelde "Kişinin kendisine
  elden verilir.") kalır. Dış yüz kütüphaneyi ANMAZ: kâğıdın kütüphaneden, yani
  iade edilmemiş bir kitaptan geldiği dıştan anlaşılmamalıdır. Pusula sınıfta
  okunmaz, öğrenci görevliye dağıttırılmaz.
- Görevli kipinde üyeye bağlı ödünç retleri (gecikme, ödünç sınırı, yıl sonu)
  kitabın kimde olduğundan önce verilir; yıl sonu iletisi görevliye tarih
  göstermez. Kartı okutulan üyenin kendi kitabı okutulursa "Bu kitap zaten bu
  üyede" sorusu çıkabilir: masadaki kitabın o üyede olduğu bu kadarıyla görünür
  (aydınlatma metni bunu söyler).
- Kütüphane aydınlatma metni e-Okul listelerinin aktarımından **önce** duyurulur
  (KVKK md. 10/1 "elde edilmesi sırasında"); kılavuzun üyelik bölümü bu adımla
  açılır.
- Hata ve uyarı metnine, günlüğe ve uç yoluna öğrenci adı yazılmaz.
- Basılı toplu gecikme listesi şu dipnotu taşır: "Kişisel veri içerir —
  asılmaz, çoğaltılmaz."
- İlişik listesinin basılı hâli de aynı dipnotu taşır ve kaynak adı ile okul no
  basmaz (yalnız barkod, tarih, belge no). "Kütüphaneden ilişiği yoktur" belgesinin
  ret iletisi kişi adı yazmaz, yalnız sayı verir.
- Görevli kipinde teslimden geri almada teslim alanın kimliği (şube ya da öğretmen)
  ve belge no gösterilmez; masadaki "Teslimden geri al" önerisi kime teslim
  edildiğini söylemez. Ağ Kataloğu teslimdeki kitabı yalnız "Sınıf kitaplığında"
  diye gösterir.
- Kayıp/hasar dosyası, tutanağı ve öğretmene teslim listesi kişi adı taşır:
  yalnız yönetici kipinde açılır, kişisel veri içeren belge gibi saklanır. Sorumlu
  notuna sağlık ya da aile bilgisi yazılmaz.
- Ağ kataloğunun hiçbir sayfasında üye, ödünç, iade tarihi ya da kişi adı
  geçmez. "Hakkında" sayfası bunu açıkça söyler.
