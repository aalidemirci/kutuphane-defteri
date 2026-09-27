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
| Bakanlığın sistemi | **Bakanlık otomasyon sistemi**, kısa: "Bakanlık sistemi"; ayar **"Bakanlık sistemi kullanımda"** (F10) | "e-Kütüphane", uydurma ürün adı, "Bakanlık sistemine gönder", "eşitle", "entegrasyon" | Resmî adı ve adresi doğrulanınca buraya yazılır. Program o sisteme bağlanmaz, veri göndermez ve yerine geçmez; ayar varsayılan kapalıdır ve yalnız hatırlatma açar (§4.17). Kılavuz kısa adı yalnız "Dökümler ve Dışa Aktarım" bölümünde kullanır, öbür bölümlerde yalnız ayarın adı geçer: künye getirmede Bakanlığın sistemi anılmaz |
| TMY çıktısı | **Taşınır Kütüphane Defteri dökümü**; F10'dan beri **Yönetim hesabı cetveli hazırlığı** | tek başına "Kütüphane Defteri"; "Kütüphane Yönetim Hesabı Cetveli" (hazırlık için) | Programın adıyla karışmasın diye her zaman tam ad (U8). Resmî defter ve cetveller TKYS'dedir; dökümler onların yerine geçmez. Ciltletilmemiş süreli yayın deftere girmez (TMY 10/1-a-4, 15/4) |
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
| Nüsha durumları (`Copy.status`) | **Rafta** · **Ödünçte** · **Sınıf kitaplığında** · **Onarımda** · **Kayıp** · **Ayıklandı (kayıttan düşüldü)** · **Sayım noksanı (kayıttan düşüldü)** · **Kayıp (kayıttan düşüldü)** · **Hasar (kayıttan düşüldü)** · **Devredildi** | AVAILABLE gibi kodlar, "müsait" | Liste `CopyStatus.choices` ile BİREBİRDİR (koruma testi `test_sozluk_belgesi.py`). Ağ kataloğu ve masa aynı sözcükleri kullanır. **"Ödünç verilmez — kütüphanede okunur" durum DEĞİLDİR**, `is_reference`'tan türetilir (yukarıdaki satır); **"Geçici olarak kullanım dışı"** bir hâle bağlı değildir ve kullanılmaz |
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
| Ödünç geçmişi | **ödünç kaydı**, **ödünç geçmişi** | **okuduğu kitaplar**, **okuma karnesi**, **okuma puanı**, okuma geçmişi | **Ödünç ≠ okuduğu kitap.** Öğrenci bazlı ödünç sayısı öğretmene ya da e-Okul'a aktarılmaz (tasarım §3). F10'dan beri istatistik, çok okunanlar, okuma ödülü iç çıktısı ve kişi dökümü de ödünç kaydından okuma bilgisi üretmez; ekranda ve belgede kalıp cümle **"Ödünç kaydı okunan kitabı göstermez."** |
| İade tarihi | **iade tarihi**; gecikmişte **gecikme**, **"… gün gecikti"**; dönem sonu uyarısı **"İade tarihi (…) dönem sonundan (…) sonraya düşüyor. Süre kısaltılmaz."**; kapalı günler eksikse **"YYYY yılının resmî tatil ya da dini bayram günleri Kapalı Günler'de eksik; iade tarihi bir tatile rastlamış olabilir. Kütüphane yöneticisi Ayarlar → Kapalı Günler'den eklemelidir."** | son teslim tarihi, ceza, harç, uzatma | Programda uzatma, ceza ve harç yoktur. İade tarihi = verildiği gün + 15; kapalı güne rastlarsa izleyen ilk açık güne kayar. Kayma **iki ayrı kuraldır** ve Yönetmelikten gelmez: hafta sonu, resmî tatil ve dini bayram TBK 93'e kıyasen (idari izin programın kuralı, her zaman); ara tatil ve yarıyıl okulun tercihi (ayar). Kaydırılmış tarih "Md. 18 gereği" diye sunulmaz; Md. 18'e yalnız süre ve sayı cümlesinde atıf yapılır |
| `LibraryPolicy` | **Kütüphane Politikası** (Ayarlar sekmesi); bölümleri **Ödünç Sınırları** · **İade ve Yıl Sonu** · **Yönetici Kipi Süreleri** · **Vitrin ve Saklama** · **Künye Getirme** · **Bakanlık Sistemi** (F10: ayar **"Bakanlık sistemi kullanımda"**, varsayılan kapalı) | ayarlar (tek başına), kurallar, ödünç ayarları | **Ödünç süresi burada AYAR DEĞİLDİR**: on beş gün sabittir (Md. 18/1) ve yalnız değiştirilemez bir bilgi satırıdır. Diğer personele ödünç açılırsa "Müdürlük kararı tarihi" ve "Müdürlük kararı sayısı" zorunludur. Yönetici kipi süreleri F7'den beri buradadır (aşağıda "Kip" satırı) |
| `Holiday.SCHOOL_BREAK` | **öğrenciye kapalı gün** (ara tatil, yarıyıl) | tatil (tek başına) | Kanunen tatil değildir; resmî ve dini tatil ayrı türdür |
| `Holiday` diğer türler | **resmî tatil**, **dini bayram**, **idari izin / diğer**; hepsinin üst adı **kapalı gün** (sayfa: "Kapalı Günler") | tatil günü (genel anlamda) | İdari izin kütüphanenin de kapalı olduğu gündür; iade tarihi hesabında resmî tatil gibi her zaman kapalı sayılır. Bu programın kuralıdır, TBK 93 kıyası altında anılmaz (`docs/mevzuat/BENIOKU.md` §4). Tahmini bayram tarihinde **"tahmini"** rozeti |
| `Delivery` (U11) | **teslim**: "sınıf kitaplığına teslim", "öğretmene teslim"; **teslim alan** (**Sınıf kitaplığı** · **Öğretmen**); **belge no**; **beklenen dönüş**; geri dönüşü **geri alma** (masada ve görevli ekranında düğme **"Teslimden geri al"**); belgeler **Teslim listesi** · **Geri alma dökümü** | ödünç, emanet, zimmet, zimmetli, "teslim alındı" (geri alma anlamında; Md. 19 adımı **"Bedel teslim alındı"** bunun dışındadır), iade (geri alma anlamında), gecikme (teslimde) | **Teslim ödünç değildir**: Md. 18 sayı sınırı ve on beş günlük süre uygulanmaz, üyelik gerekmez, teslim alanın ödünç hakkından düşmez ("kalan hak" dili yok). Yalnız etkin ders yılının şubesine ya da aktif öğretmene; diğer personele teslim yapılmaz. Toplu teslim tek işlemdir (bir kitap reddedilirse hiçbiri). Nüsha **Sınıf kitaplığında** görünür (öğretmene teslimde de); kime teslim edildiği Ağ Kataloğunda ve görevliye görünmez. Beklenen dönüşün geçmesi gecikme değildir (rozet **"beklenen dönüş geçti"**). Şube teslim listesi Dayanıklı Taşınırlar Listesi işlevini görür (TMY 23/6'ya **kıyasen**); sayımdaki yerini sayım kurulu seçer (32/5'e kıyasen). Teslim verme yönetici kipinde, geri alma görevli kipinde de |
| İlişik | **ilişik listesi**; **açık iş** ("kütüphaneyle açık işi olan kişi": iade edilmemiş ödünç, geri alınmamış teslim, çözülmemiş kayıp/hasar dosyası — **"Bedel teslim alındı"** dosyası hariç: o, kişinin değil **okulun açık işi**dir); **"Kütüphaneden ilişiği yoktur" belgesi** | borç, borçlu, ilişik kesme, ilişiği kesilmiştir, kara liste, yükümlülük (kullanıcı metninde; kod yorumunda serbest) | Karne ya da diplomanın ön koşulu diye SUNULMAZ; dayanağı yok (Md. 18 yalnız "iadesi sağlanır" der). Belgede ve ekranlarda "karne", "diploma" geçmez; kılavuz bunu tek bir olumsuz cümleyle söyler. Okuldan ayrılanlar listede kalır; sıra son sınıf → okuldan ayrılan → diğerleri. Ayrıntı §4.13 |
| `LossDamageCase` | **kayıp** (eylem **"Kayıp bildir"**), **hasar** (eylem **"Hasar dosyası aç"**), **kayıp dosyası** / **hasar dosyası**; **sorumlu** ("Sorumlu üye", "Sorumlu notu"); **tespit tarihi**; **bedel belirlendi**, **bedel teslim alındı**, **o günkü piyasa bedeli** (yalnız kayıt); **okulun açık işi**; **kayıttan düşme önerisi**; belge **Kayıp/hasar tutanağı** | zayi, telef, borç, ceza, tahsil edildi, ödendi, tazminat, "kayıp ödünç" | Bedel seçenekleri yalnız ortaöğretimde (Md. 19). Program tahsilat yapmaz ve disiplin sürecini başlatmaz (OKY 164/1-g okulun işidir). Bedel iki adımdır (25.09.2026 kullanıcı kararı): **"Bedel belirlendi"** kişinin açık işini sürdürür; **"Bedel teslim alındı"** bitirir (ilişik listesinden çıkar, "Kütüphaneden ilişiği yoktur" belgesi basılabilir), dosya ise **okulun açık işi** olarak "Bedelle aynısı alındı", "Bedelle başka eser alındı" ya da (kayıpta) "Bulundu (bedel teslim alınmıştı)" ile kapanana dek açık kalır. İki adım da yalnız kayıttır ve dosyayı kapatmaz; ikincisi geri alınmaz. Kayıp bildirimi ödüncü ya da teslimi **Kayba dönüştü** ile kapatır; "Bulundu" onları yeniden açmaz. Kayıttan düşme burada yalnız önerilir; asıl işlem TMY yoludur. Öneri geri alınabilir: öneriyle kapanan kayıp dosyasında nüsha henüz kayıttan düşülmemişse kitap bulununca "Bulundu" ("Bedelle başka eser alındı"da **"Bulundu (bedel teslim alınmıştı)"**) seçilir; kayıttan düşülmüşse kitap "Sayım fazlası (kayda giriş)" edinimiyle yeni nüsha olarak alınır. Bedel teslim alındıktan sonra bulunan kitapta teslim alınan bedelin iadesi okul yönetiminin kararıdır; program para tutmaz (25.09.2026 kullanıcı kararı). Kayıp ve hasar dosyasının kayıttan düşme önerisi ayıklamaya konmaz, sayımda düşülür: hasar önerili kitap sayımda bulunursa **Hasar (kayıttan düşüldü)**, kayıptaki kitap bulunamazsa **Kayıp (kayıttan düşüldü)** olur; kayıpta görünen kitap sayımda okutulursa onayda dosyası "Bulundu" ile kapanır (onay sonucu **"Kayıp kaydı kapandı"**). TMY 32/3 durdurması sürerken kayıp bildirilemez; kayıp dosyası yalnız bulunma ("Bulundu", "Bulundu (bedel teslim alınmıştı)" — kayıptaki kitabın rafa dönüşü taşınır giriş-çıkışı değildir; F9 ekleri K1, 25.09.2026) ve bedel adımlarıyla, hasar dosyası yalnız öneri yazmayan çözümlerle ilerler. Açık hasar dosyalı kitap kaybolunca hasar dosyası **Kayba dönüştü** ile kapanır. Dosyanın kişisi önce üyeliktir, üyelik yoksa teslim alan. Çözüm adları §4.12 |
| Onarım (`CopyRepair`, `IN_REPAIR`) | **onarım**; eylemler **"Onarıma gönder"** · **"Onarımdan dön"**; nüsha durumu **Onarımda**; hasar dosyasının çözümü **Onarıldı** | tamir, bakım, servis | Hasar dosyası olmadan da onarıma gönderilir (Eser Ayrıntısı → **Kayıp, Hasar ve Onarım** bölümü). Onarımdaki nüsha ödünç ve teslim edilmez. Onarımdan dönüş hasar dosyasını kendiliğinden kapatmaz |
| Yıl akışları (§8.3) | **yıl sonu**, **yıl başı**, **kitap toplama**, **son sınıf**, **okuldan ayrılan** | yıl devri, yıl kapanışı, sınıf atlatma (program işi olarak), mezun listesi (belge adı olarak) | Son sınıf kademenin son sınıfıdır (4 · 8 · 12). Programda yeni yıla geçiş işlemi yoktur; sınıf atlama ve mezunların ayrılışı e-Okul aktarımı ve Ayrılış Havuzu'yla olur. Ekran ve adım adları §4.13 |
| `WeedingBatch` | **ayıklama** (Md. 12); kayıt **ayıklama teklifi**; ekran ve belge adları §4.14 | silme, temizleme, imha (genel anlamda), hurdaya çıkarma, ayıklama partisi | Seçim ve Ayıklama Komisyonunun kararıdır (Md. 12/1); kayıttan düşme ve devir harcama yetkilisinin onayıyla yapılan taşınır işlemidir. Nüsha durumu yalnız teklif uygulanınca değişir |
| TMY işlemi | **kayıttan düşme**; **hurdaya ayırma** (TMY 28); imha yalnız **"imha tutanağı"** ve onaydaki **"İmha kararı verildi"** kutusu (TMY 28/5) bağlamında; **devir** (TMY 24/2, 31), devralan **"devralacak okul ya da kurum"** | silme | Ayıklama ≠ kayıttan düşme: biri komisyon kararı, öbürü taşınır işlemidir. Resmî Kayıttan Düşme Teklif ve Onay Tutanağı ve Varlık İşlem Fişi TKYS'dedir; programın çıktıları onların hazırlığıdır. Kılavuz yolları sade dille ve fıkra atfıyla anlatır: yıpranma 27/1 (olağan yıpranmada sorumluluk aranmaz, 5/8; kusuru harcama yetkilisi değerlendirir, 27/3), hurdaya ayırma 28/1-28/4 (ekonomik değeri olan hurdada 28/8), devir 24/2 ve 31. Ayıklanan kitap kendiliğinden imha edilmez; imha kararı kalem kalem verilir. Sayımda iki yol daha vardır: sayım noksanı 32/7 (ve 27/1), hasar dosyasının önerisi 27/1 + 10/1-e (kayıp/hasar tutanağıyla, komisyonsuz — tasarım F8 ekleri 34); ikisi de sayımın onayıyla işlenir, ayıklamaya konmaz |
| Harcama yetkilisi ve TMY komisyonu (`approved_by_name`, `tmy_commission_members`) | **harcama yetkilisi**, **harcama yetkilisinin onayı** (adım **Harcama yetkilisi onayı**; alanlar **"Harcama yetkilisinin adı"**, **"Onay tarihi"**); kayıttan düşmeyi değerlendiren komisyon için alan **"Komisyon üyeleri"**; belgede onay bloğu **"OLUR"** | müdür onayı (harcama yetkilisinin onayı anlamında), amir onayı, Seçim ve Ayıklama Komisyonu (TMY komisyonu anlamında), sayım kurulu (bu anlamda) | Taşınır Mal Yönetmeliğindeki adı aynen (10/1-e, 28/4). İki ayrı komisyon vardır: ayıklamaya **Seçim ve Ayıklama Komisyonu** karar verir (Md. 12/1); hurdaya ayırmayı harcama yetkilisinin belirlediği, biri işin uzmanı **en az üç kişilik** komisyon değerlendirir (28/1); işin uzmanı "Komisyon üyeleri"nin ilk satırına yazılır ve belgede **"Komisyon üyesi (işin uzmanı)"** diye basılır. Yalnız 27/1 yolunda bu komisyon isteğe bağlıdır: durumu belgeleyen tutanak varsa harcama yetkilisi komisyon kurulmadan onaylayabilir (10/1-e); ayıklama tutanağının bu tutanak sayılmasını harcama yetkilisi değerlendirir — metinler bunu kesin hüküm gibi yazmaz ("onaylanabilir"). Ad ve üyeler kişi adıdır, şifreli saklanır. Onay tarihi imzalı belgenin tarihidir; komisyon kararından önce ve bugünden sonra olamaz. **Sayımda** harcama yetkilisi iki yerde geçer: TMY 32/3 durdurmasını yapan (durdurma kutusundaki "Harcama yetkilisinin adı") ve sayımı onaylayan (pencere **"Sayım onaylansın mı?"**, belgede "OLUR"; onay tarihi sayımın tamamlandığı günden önce ve bugünden sonra olamaz). Sayımda "Komisyon üyeleri" alanı yoktur: noksanın ve hasar önerisinin Kayıttan Düşme Teklif ve Onay Tutanağı durumu belgeleyen tutanakla komisyon kurulmadan onaylanabilir (10/1-e) — aynı takdir diliyle |
| El yazması ve nadir eser (`Copy.is_rare_or_manuscript`, `RareWorksSubmission`) | kutu **"El yazması / nadir eser"**; **el yazması ve nadir eser**; belge **El yazması ve nadir eserler listesi**; **Genel Müdürlük** (Destek Hizmetleri Genel Müdürlüğü, Md. 4/1-c); rozetler **Bildirildi** · **Bildirilmedi** | antika, değerli kitap, özel koleksiyon, arşiv (bu anlamda), nadir kitap envanteri | Md. 12/2: liste Seçim ve Ayıklama Komisyonunca tespit edilir ve Genel Müdürlüğe gönderilir. Nadir eser **ayıklanmaz**; işaret ödünç verilebilirliği değiştirmez. Liste "Ayıklama" türündeki karara bağlanır; gönderilmiş liste değişmez. Gönderilmiş ya da kararı bağlanmış (komisyonun tespit ettiği) listedeki nüshanın işareti kaldırılamaz; hiçbir listede ya da kararı bağlanmamış listede olan işaret veri giriş hatası olarak kaldırılabilir. Listedeki nüsha silinemez. Ekran adları §4.14 |
| Yıl sonu kütüphane raporu (`AnnualLibraryReview`) | belge **yıl sonu kütüphane raporu**; ekran **Yıl Sonu Raporu**; alan **"Tespit edilen hususlar"**; eylemler **"Raporu hazırla"** · **"Raporu sonlandır"** · **"Sonlandırmayı geri al"** | faaliyet raporu (bu belge için), okuma raporu, istatistik raporu, öğrenci listesi | Md. 12/1 ve Uygulama Kılavuzu 2.4 (bağlayıcı değildir). Ders yılı başına tek rapordur; sonlandırma sayıları dondurur ve geri alınabilir. **Kişisel veri içermez** (kod kapısı): üye bazında bilgi, adlı sıralama ve şube × konu kırılımı yoktur; üye türü ve sınıf düzeyi kırılımında eşiğin ("Çok okunanlar için en az üye sayısı") altındaki grup "—" yazılır; imzada ad basılmaz. Tespit alanının yardımı: "Kaynakların durumu ve öneriler. Kişi adı yazmayın." Ekran ve belge adları §4.14 |
| Raporlar ve istatistik (F10, `selectors_istatistik`) | sayfa **Raporlar**; **istatistik**, **kişisiz**; eşiğin altındaki hücre **"—"** | okuma istatistiği, öğrenci istatistiği, okuma oranı, başarı, performans | Üye bazında bilgi, adlı sıralama, şube × konu ve konuya göre ödünç kırılımı YOKTUR (profil yasağı, CLAUDE.md §2-5). Üye türü ve sınıf düzeyi kırılımında "Çok okunanlar için en az üye sayısı"ndan az farklı üyenin ödünç aldığı grup "—" yazılır; gizlenen sayı toplamdan bulunamasın diye tamamlayıcı gizleme yapılır. Kılavuz nedenini sade dille söyler: küçük grubun sayısı kişileri ele verir, kimin hangi kitabı aldığı düşünce, inanç ya da sağlık hakkında fikir verebilir (KVKK md. 6). İstatistik bilgi ekranıdır; okul müdürlüğüne giden rapor **yıl sonu kütüphane raporu**dur. Ekran adları §4.16 |
| Çok okunanların sırası (F10, tasarım §5.3) | **çok okunanlar**; listeler **Dönemin Çok Okunanları** (Ağ Kataloğu vitrini) · **Ayın Kitapları** (afiş); **sıra**; rozetler **Sürüyor** · **Kapandı** | popüler, en çok ödünç alınanlar, okunma sayısı, "N kez okundu", en çok okuyanlar, dondurulmuş liste | Eşik en az k FARKLI üyedir (k = "Çok okunanlar için en az üye sayısı", 3-10, varsayılan 5): tek üyenin aynı kitabı tekrar tekrar alması eseri listeye sokmaz. **Sayı hiçbir yerde gösterilmez**, yalnız sıra; pencere başına en çok on eser. Kapanan dönem ve ay son hâliyle kalır ("bir daha değişmez"). Afiş (**Ayın Kitapları afişi**) sayısız ve kişisizdir, asılabilir. Ekran adları §4.16 |
| Okuma ödülü (Uygulama Kılavuzu 7, F10) | belge **okuma ödülü iç çıktısı**; ibare **"İç kullanım"**; Kılavuz 7 için **öneri** ("Öneridir, bağlayıcı değildir") | **okuduğu kitaplar**, **okuma karnesi**, **okuma puanı**, okuma şampiyonu, en çok (kitap) okuyan öğrenciler listesi (asılan; programın kendi metninde de — Kılavuz 7 cümlesi yalnız alıntıdır), başarı listesi | Programda adlı sıralamanın geçtiği TEK yer; yalnız yönetici kipinde. Ölçüt dönem içinde iade edilmiş FARKLI eser; sayı ve okul no basılmaz; eşitler aynı sırada. Asılmaz, çoğaltılmaz; ağa, panoya, Ayın Kitapları afişine, yıl sonu raporuna ve velilerle paylaşılabilecek çıktılara girmez. Not ya da başarı verisiyle ilişkilendirilmez (Kılavuz 7'nin bu önerisini program yapmaz) |
| Kitap sayısı eşiği (Yönetmelik Md. 7/1, F10) | kart **Kitap Sayısı 10.000'i Aştı**; **elde bulunan kitap** | "kütüphaneci atanmalıdır", zorunlu, eksiklik, uyarı (hüküm anlamında) | Yalnız bilgi verir, bağlantısı ve düğmesi yoktur; program maddenin nasıl uygulanacağını yorumlamaz. Sayılan: kaynak türü "Kitap" olan, kayıttan düşülmemiş ve devredilmemiş nüsha ("aşan" = 10.000'den büyük) |
| Dışa aktarım (tasarım §8.4, F10) | **dışa aktarım**, **dışa aktarım dosyası** (belge adı **Katalog dışa aktarımı**); boş kuruluma **geri yükleme** ("Dışa aktarım dosyası" seçimiyle) | yedek ya da yedekleme (bu anlamda), senkronizasyon, eşitleme, "Bakanlığa aktarım", "Bakanlık sistemine yükle" | Yalnız kataloğu taşır, kişisel veri içermez; programın bütün kayıtlarını **şifreli yedek** taşır (yeni bilgisayara taşıma). Barkod ve kayıt no korunur, **hiçbir numara yeniden kullanılmaz**. Bakanlık sistemine ya da başka bir araca geçişte taşınabilirlik içindir; o sisteme doğrudan yüklenecek biçim diye sunulmaz. Şema `docs/disa-aktarim.md`, ekran adları §4.17 |
| İlgili kişinin başvurusu (KVKK md. 11, F10) | belge **Kişi dökümü**; **başvuru**, **cevap hazırlığı** | okuma geçmişi, kişi raporu, kişi dosyası, profil | Yalnız yönetici kipinde; döküm SEÇİLEN kişinin üyelik, ödünç, kayıp/hasar ve (öğretmende) teslim kayıtlarıdır, başka kişinin kaydı girmez. Cevabı okul müdürlüğü verir (md. 13/2: en geç otuz gün). İndirilen dosyanın adında kişi adı yoktur. Ekran adları §4.17 |
| Sayımın türü (`StockTake.is_year_end`, F10) | **yıl sonu sayımı** (kutu **"Yıl sonu sayımı"**) · **ara sayım** | dönem sonu sayımı, kesin sayım, ara dönem sayımı | TMY 32/1'in iki sayımı: yıl sonu ve harcama yetkilisinin gerekli gördüğü sayım. Ekin cetvele aktarılacak sayıları ve yönetim hesabı cetveli hazırlığı yalnız yıl sonu sayımındandır; işaretsiz sayımın eki **"Ara sayım — sayılar cetvele aktarılmaz"** başlığını alır. İşaret onaya dek değiştirilebilir |
| `Acquisition` | **edinim**, **edinim partisi**; **edinim yolu**: Bakanlık gönderimi · Satın alma · Bağış · Değişim · Sayım fazlası (kayda giriş) · Mevcut koleksiyon (programa aktarım) | alım, temin, kaynak girişi, sağlama (tek başına) | İlk dördü Md. 10/5'in saydığı yollardır; son ikisi kayıt içi girişlerdir ve öyle adlandırılır. Bağışçı/satıcı adı **"kaynak notu"**dur ve şifreli saklanır |
| `CommissionDecision` | **Seçim ve Ayıklama Komisyonu**, **komisyon kararı**; alanlar **"Karar türü"** · **"Karar tarihi"** · **"Karar sayısı"** · **"Başkan adı"** · **"Katılımcılar"**; eylem **"Karar ekle"** | kurul (bu anlamda), ayıklama komisyonu (tek başına), seçim komisyonu (tek başına) | Yönetmelikteki adı aynen. Başkanı ilçe millî eğitim şube müdürüdür, katılamadığı durumlarda okul müdürü başkanlık eder (Md. 10/1); bileşimi Md. 4/1-ı'dadır (kılavuz üyeleri saymaz, bende gönderir). Program komisyonu kurmaz, kararını kaydeder; başkan ve katılımcı adları şifreli saklanır. TMY 28/1 komisyonu ayrı bir komisyondur (yukarıda "Harcama yetkilisi ve TMY komisyonu") |
| `decision_type` | **karar türü**: Kaynak seçimi · Bağış değerlendirme · Ayıklama; kullanılmış kararda rozet **"Kullanımda"** ve altında kullanan kayıtların sayısı ("2 ayıklama teklifi · 1 nadir eserler listesi") | karar tipi, kategori | Tür bağlayıcıdır: bağış yalnız bağış değerlendirme kararıyla kataloglanır; ayıklama teklifi ve el yazması ve nadir eserler listesi yalnız "Ayıklama" kararına bağlanır. Kullanılmış kararın türü değişmez, kaydı silinmez |
| `DonationIntake` | **bağış ön kaydı** | bağış listesi (tek başına), taslak | Komisyon kararına kadar nüsha açılmaz |
| Bağış durumları | ön kayıt: **Karar bekliyor** · **Karar işlendi** · **İptal edildi**; kalem: **Kabul edildi** · **Reddedildi**; eylemler **"Komisyon kararını uygula"**, **"Kararı uygula"**, **"İptal et"**; kabul edilen kalemde seçici **"Katalogdaki karşılığı"** (**"… eserine nüsha ekle"** · **"Yeni eser aç"**) | onaylandı, kapandı, silindi, bağış kabul tutanağı | Karar geri alınamaz; onay diyaloğu kaç kalemin kabul, kaç kalemin ret edileceğini yazar. Reddedilen her kalemde **"ret gerekçesi"** zorunludur. Edinim tarihi boşsa komisyon kararının tarihi ile geliş tarihinin geç olanıdır. Bağışta "Birim fiyat" bağışçının belgesindeki değer ya da değer tespit komisyonunun belirlediği değerdir (TMY 13/2-c). Karar uygulanınca ön kaydın penceresinden **Bağış değerlendirme sonucu** basılır (25.09.2026 kullanıcı kararı). "Bağış kabul tutanağı" TMY'de bir belge değildir, kullanılmaz (tasarım F8 ekleri 13) |
| `StockTake` | **sayım**; seçenekler **"TMY 32/3 durdurması"** ve **"sayım için hizmet arası"**; **sayım kurulu** (alanlar **"Kurul başkanı"** · **"Taşınır kayıt yetkilisi"** · **"Kurul üyeleri"**); **anlık görüntü**; **ikinci sayım**; **sayım fazlası**, **noksan**; **"Kayda alınmayacak"**; belge **Sayım tutanağı** | sayım kilidi, dondurma, kilit (seçenek anlamında), envanter sayımı, noksanlık, fazlalık (sonuç adı olarak) | İki seçenek ayrı adlarla ve tutanakta ayrı satırlarda geçer ve birbirinden bağımsızdır: TMY 32/3 durdurması isteğe bağlıdır (kurulun talebi + harcama yetkilisinin adı ve tarihi; edinim ve yeni nüsha kaydı, kayıttan düşme, devir, kayıp bildirimi, kayıp dosyasının bulunma ve bedel adımları dışındaki çözümü ve hasar dosyasında kayıttan düşme önerisi durur; programa aktarım da durur ama TMY'ye dayandırılmaz), sayım için hizmet arası okul kararıdır ve yeni ödüncü ve yeni teslimi durdurur — TMY'ye dayandırılmaz. **İade ve teslimden geri alma hiçbir durumda durmaz** (Md. 23/1-c). Seçenekler onaya ya da iptale dek sürer. Sayım kurulu TMY 32/2'nin adıdır (en az üç kişi; adlar şifreli); Seçim ve Ayıklama Komisyonu ve TMY 28/1 komisyonu değildir. Ödünç alanın ve teslim alanın kimliği sayım verisine ve tutanağa girmez. Program sayımı bir **mali yıla** bağlar (1 Ocak-31 Aralık); ders yılı sonundaki Yıl Sonu ekranı sayım değildir. Ayrıntı aşağıdaki üç satırda ve §4.15 |
| Sayım kurulu (`committee_chair`, `committee_property_officer`, `committee_members`) | **sayım kurulu** (TMY 32/2); kart **Sayım Kurulu**, alanlar **"Kurul başkanı"** · **"Taşınır kayıt yetkilisi"** · **"Kurul üyeleri"** (satır başına bir kişi); belgede imza bloğu **"SAYIM KURULU"** (Sayım kurulu başkanı · Taşınır kayıt yetkilisi · Üye) | sayım komisyonu, komisyon (sayım kurulu anlamında), sayım ekibi, Seçim ve Ayıklama Komisyonu (bu anlamda) | Başkan harcama yetkilisi ya da görevlendirdiği kişidir; taşınır kayıt yetkilisi kurulda bulunur; kurul en az üç FARKLI kişidir (32/2). Adlar kişi adıdır: şifreli saklanır ve yalnız Sayım tutanağına basılır; sayım listesi, Genel Bakış kartı ve iletiler ad yazmaz. Sayım kurulu ne Seçim ve Ayıklama Komisyonu ne de TMY 28/1'in hurdaya ayırmayı değerlendiren komisyonudur; Taşınır Sayım ve Döküm Cetvelini düzenleyen ve imzalayan da odur (32/9 — cetvel TKYS'dedir) |
| Sayım sırasındaki seçenekler (`tmy_stop`, `service_pause`) | kart **Sayım Sırasındaki Seçenekler**; **TMY 32/3 durdurması** (alanlar **"Kurulun talep tarihi"** · **"Harcama yetkilisinin adı"** · **"Durdurma tarihi"**; ret iletisi **"TMY 32/3 durdurması süresince … yapılamaz. Durdurma, sayım onaylanınca ya da iptal edilince kalkar. Durdurma ödüncü ve iadeyi kapsamaz."**); **Sayım için hizmet arası** (alan **"Okul kararı (isteğe bağlı)"**; sayım listesinin Seçenekler sütununda kısaca **"Hizmet arası"**); süren seçenekte rozet **"Sürüyor"**; durdurmanın kapsadığı işlemlerin ekranında bant **"TMY 32/3 durdurması sürüyor"**; programa aktarımın ekranında (İçe Aktarma; Hızlı Kayıt'ta "Mevcut koleksiyon (programa aktarım)" edinimiyle) bant **"Sayım sürüyor"** ve ret iletisi **"Sayım sürerken programa aktarım yapılamaz; sayım bitince aktarın."**; masada ve Yeni Teslim'de şerit **"Sayım için hizmet arası — yeni ödünç ve teslim yapılamıyor. İade ve teslimden geri alma açık."** | sayım kilidi, dondurma, kilit ve kilitli (seçenek anlamında — "kilitli" programın kip durumudur), ödünç yasağı, dolaşım kapalı, sayım modu | İkisi bağımsızdır ve tutanakta ayrı satırlardadır; iade üçüncü satırdır. **TMY 32/3 durdurması** isteğe bağlıdır (32/3 "durdurulabilir" der): kurulun talebiyle harcama yetkilisi yapar, üç alan zorunludur. Durur: edinim ve yeni nüsha kaydı (Hızlı Kayıt, içe aktarma, bağış kataloglaması, boş etiket bağlama), kayıttan düşme, devir, kayıp bildirimi, kayıp/hasar dosyası çözümü. Programa aktarım (mevcut koleksiyonun kaydı) taşınır girişi değildir ama durdurma süresince o da durur; iletisi TMY'ye dayandırılmaz, kodu `sayim_programa_aktarim`'dır (F9 ekleri K4). Durmaz: kayıp dosyasında kitabın bulunması ("Bulundu", "Bulundu (bedel teslim alınmıştı)" — F9 ekleri K1) ve bedelin iki adımı ("Bedel belirlendi", "Bedel teslim alındı"), hasar dosyasında kayıttan düşme önerisi yazmayan çözümler ("Onarıldı", "Aynısı temin edildi", "Bedelle aynısı alındı"), onarım, teslim ve geri alma, ödünç ve iade (tasarım F7 ekleri 17). **Sayım için hizmet arası** okul kararıdır ve yeni ödüncü ve yeni teslimi durdurur (madde 27, 25.09.2026 kullanıcı kararı; ödünç ve teslim aynı kodla reddedilir — `sayim_hizmet_arasi`); TMY'ye dayandırılmaz (ödünç TMY 13/1'in saydığı giriş ve çıkış hâllerinden değildir; okuyucuya verilen materyal ödünç takip sistemiyle izlenir, 23/4): tutanağın "Dayanak" sütunu "Okul kararı" der ve en fazla 32/3'ün ikinci cümlesini (önlem almak kurulun görevidir) anar; seçenek satırı "sayım süresince yeni ödünç ve teslim durdurulur; iade ve teslimden geri alma açıktır." der. Teslimden geri almayı durdurmaz. Masa hizmet arasını açılışta kişisiz masa durumundan öğrenir — görevli kipinde de (madde 26). **İade hiçbir durumda durmaz** (Md. 23/1-c). Seçenekler başlatınca başlar, "Tamamlandı"da da sürer, onaya ya da iptale dek |
| Noksan ve sayım fazlası (`StockTakeResult`) | **noksan** (kalem sonucu **"Noksan"**; TMY 32/6'nın sütun adı); **sayım fazlası** (kalem sonucu **"Fazla"**, kart **Sayım Fazlası**, edinim yolu **Sayım fazlası (kayda giriş)**); ikinci sayımın listesi **"İkinci Sayım: Bulunamayan Nüshalar"**; **kayda göre alındı** (ödünçteki ve teslimdeki nüsha) | eksik (sonuç adı olarak), kayıp (sayım sonucu anlamında), noksanlık, fazlalık, açık (sayım farkı anlamında) | **Noksan ≠ kayıp**: "Kayıp" nüsha durumu ve dosyadır (Md. 19); noksan sayımın sonucudur ve ikinci sayımdan (32/6) sonra yazılır. Onayda noksan **Sayım noksanı (kayıttan düşüldü)**, kayıtta kayıp görünen noksan **Kayıp (kayıttan düşüldü)** olur (32/7); hasar dosyasında öneri yazılmış ve sayımda bulunan nüsha **Hasar (kayıttan düşüldü)** olur (27/1, 10/1-e). Ödünçteki ve teslimdeki nüsha noksan sayılmaz; tek istisna yerinde sayılan sınıf kitaplığıdır. Sayım fazlası kayda **yeni numarayla** girer (hiçbir kitaba bağlanmamış boş etiketse o numarayla — numara asla yeniden kullanılmaz); kayda esas değeri program yazmaz (TMY 17/1) |
| Ağ kataloğu | **Ağ Kataloğu** (özel ad, büyük harfle) | **OPAC**, web sitesi, sunucu, LAN, portal | Kişisel veri göstermez; bunu "Hakkında" sayfası söyler |
| Vitrin | **yeni gelenler**, **çok okunanlar** | popüler, en çok ödünç alınanlar | Çok okunanlarda sayı gösterilmez, yalnız sıra. Vitrindeki liste **Dönemin Çok Okunanları**dır (F10; eşik ve adlar bu tablonun "Çok okunanların sırası" satırında ve §4.16'da) |
| Ağ Doktoru | **Ağ Doktoru** | ağ tanılama, diagnostik | Yalnız yönetici kipinde |
| BTR notu (E3) | belge adı **Ağ Hizmeti Bilgi Notu** | port izni, izin belgesi | "İzin" değil "bilgi" notudur (U10) |
| BTR | ilk geçişte **"bilişim teknolojileri rehber öğretmeni (BTR)"**, sonra "BTR" | BT sorumlusu, sistem yöneticisi | "Sistem yöneticisi" Yönergedeki (4/1-s) dar anlamıyla kalır, BTR için kullanılmaz |
| Kip (U5) | **görevli kipi**, **yönetici kipi**, **kilitli**; eylemler **"Görevli kipine geç"**, **"Kilitle"**; süre alanları **"İşlem yapılmazsa kapanma süresi (dakika)"** · **"En uzun açık kalma süresi (dakika)"** (Kütüphane Politikası → **Yönetici Kipi Süreleri**) | öğrenci modu, admin modu, kiosk, oturum | Görevli kipinden çıkış yönetici parolası ister. Süreler: işlem yapılmazsa 1-15 dk (varsayılan 3), en uzun 5-120 dk (varsayılan 30); ilki ikincisini aşamaz, değişiklik bir sonraki işlemden geçerlidir |
| Görevli | **görevli** (masadaki öğrenci görevli ya da personel) | asistan, operatör | Md. 23/1-a "kütüphane görevlisi" |
| Sorumlu kişi | **kütüphane yöneticisi** (kütüphaneci ya da kütüphaneden sorumlu öğretmen) | admin, yetkili, sorumlu (tek başına) | Md. 20'nin terimi. Çoğu okulda kütüphaneci atanmaz (Md. 7/1) |
| Parola | **yönetici parolası**, **kurtarma anahtarı** | şifre, uygulama parolası, PIN | Parola zorunludur, sihirbazın ilk adımıdır |
| Kurtarma anahtarı işlemleri | kart adları **Kurtarma Anahtarını Doğrula** ve **Kurtarma Anahtarını Yenile**; eylem **"yenileme"** | anahtarı sıfırla, anahtar değiştir, yeni anahtar üret (tek başına) | Yenileme kayıtların anahtarını değiştirmez, yalnız kurtarma kilidini yeniler; yenilemeden önce alınmış yedekler için eski kâğıt gerekebilir ve metin bunu söyler |
| Görev devri | **görev devri**; belge **Görev devri notu**; kişiler **"görevi devreden"** / **"görevi devralan"** | devir teslim (tek başına); görev devrinde tek başına "devreden" / "devralan" (bu iki sözcük TMY devrinin — E7 — imza adlarıdır) | "Devir" TMY'de başka anlama gelir: kişiler hep "görevi …" diye anılır. Görev devri parola ve kurtarma anahtarını birlikte yeniler; kayıtların şifreleme anahtarı değişmez ve metin bunu söyler: devirden önceki yedekler eski parola/anahtarla açılır ve eski parola ya da eski anahtar böyle bir yedekle (ya da arşiv dosyasıyla) devirden SONRAKİ yedekleri de açar — **"eski parola kilidi artık açmaz" denmez**; metin masa hesabının parolasının değiştirilmesini ister (F11 düzeltme turu D-5). Açık işler **"notun düzenlendiği gün"**ün sayılarıdır ("devir günü" denmez — D-6). Eski kâğıt "yırtılarak yok edilir" — "imha" denmez |
| Masa hesabı | **kütüphane masası Windows hesabı** | kiosk hesabı, ortak hesap | Yönetici yetkisi olmayan ayrı hesap (U9) |
| Yedek | **yedek**, **şifreli yedek**; "güçlü şifrelemeyle korunur"; türleri **günlük yedek** · **güncelleme öncesi yedek** · **işlemden hemen önce alınan yedek** (saklama işlemi, F11); indirileni **"USB bellekteki yedek"** (ya da okulun ağ diskindeki); hatırlatma kartı **Şifreli Yedeği USB Belleğe Alın** (F11) | X25519, AES, `.kdbak` (kullanıcı metninde); "dış yedek" (ekranda ve kılavuzda — kod yorumunda serbest); "harici yedek", "bulut yedeği" | Teknik adlar yalnız Hakkında sayfasında (kurulum belgesi BTR için dosya adlarını yazar). **USB bellekteki yedek programın dışındadır**: program ona ulaşamaz, onu silemez, saklama işlemi ona dokunmaz; saklanması ve silinmesi okulun sorumluluğundadır, düzeni okul müdürlüğü belirler; bellekteki yedeğin güvenliğini onu kullanan personel sağlar (Yönerge 10/5'in öznesi personeldir — metin "yükümlüdür" der, kullanıcı metni "sağlar" der; F11 düzeltme turu D-19). Kılavuzun "Önerilen düzen"i (son iki yedek — 27.09.2026 kullanıcı kararıyla onaylandı; saklama işleminden ve görev devrinden sonra yeni yedek, eskilerin silinmesi) programın önerisidir, mevzuat hükmü diye sunulmaz. Program elle konan dosyaya dokunmaz; geri yüklemeden kalan **önceki veritabanı** (`db-onceki`) dosyalarından 14 günden eski olanları saklama işlemi siler, daha yenilerine dokunmaz (27.09.2026 kullanıcı kararı) — metin bunu söyler ve elle silme önerisini yalnız onlar için yapar (§4.18) |
| Saklama ve anonimleştirme (`services.saklama`, tasarım §6.4; F11) | **saklama süresi**, **süresi dolan kayıtlar**, **silme** (kaydın kendisi kalkar: kişi kaydı, sona ermiş üyelik kaydı), **anonimleştirme** / **"kişiyle bağı koparılır"** (kayıt kalır, gerekçe ve açıklamaları temizlenir); ekran **Ayarlar → Saklama**; kılavuz bölümü **Saklama ve Anonimleştirme** | imha, KVKK imhası, periyodik imha, otomatik silme, temizlik, çöp, arşivleme, maskeleme; "silindi" (anonimleştirme anlamında) | **Anonimleştirme ≠ silme**: anonimleştirilen ödünç, dosya ve teslim sayım ve istatistik için kalır (belge no ya da dosya numarası arşivdeki asılla eşleşebilir: "kişisel veri içermeyen" denmez — §4.18); silinen kayıt kalmaz. Program her gün tarar, **kendiliğinden hiçbir şey silmez**; işlem yönetici parolasıyla onaylanır, geri alınamaz, tek seferdedir; onay altı aydan uzun beklerse kapatılamayan uyarı çıkar. Dayanak KVKK 4/2-d (birebir alıntı) ve 7/1 (atıf); **Silme, Yok Etme veya Anonim Hâle Getirme Yönetmeliği depoda yoktur, atıf yapılmaz**. Süreler okulun ayarıdır (Kütüphane Politikası → Vitrin ve Saklama, 1-10 yıl), mevzuat hükmü diye sunulmaz. Ekran adları §4.18 |
| Silme ve imha (sözlük kuralı, F11) | kayıt, yedek dosyası, veri klasörü ve USB bellekteki yedek için **silme**; kâğıt için **"yırtarak yok etme"** (eski kurtarma anahtarı); **imha** YALNIZ TMY 28/5 bağlamında (**İmha tutanağı**, **"İmha kararı verildi"**, §4.14) | imha (kişisel veri, yedek, anahtar kâğıdı, USB bellek için), "imha kuralı" (kullanıcı metninde; tasarım belgesinin iç dilidir), "KVKK imhası", "veri imhası" | Mevzuat metni "imha" dese de (ör. Yönerge 10/3 "atık evrakı imha eder") kullanıcı metninde alıntılanmaz, "yok edilir" diye aktarılır. KVKK 7/1'in "silinir, yok edilir veya anonim hâle getirilir" üçlüsü atıf olarak anılabilir. Kılavuzda "imha" yalnız Ayıklama ve Nadir Eserler bölümünde geçer (test) |
| Belge izi (`BelgeIzi`, tasarım §6.2; F11) | **belgenin kişisiz izi**; ibare **"Anonimleştirilmiş kopya — ıslak imzalı asıl nüsha okul arşivindedir"** (birebir) | belge kaydı, arşiv (programdaki iz anlamında), suret | Kişiyi adıyla anan ve ıslak imzalı asılla okul arşivine giren belgeler iz bırakır: "Kütüphaneden ilişiği yoktur" belgesi, Kayıp/hasar tutanağı, Teslim listesi, Geri alma dökümü. Görev devri notu iz bırakmaz (adlar hiç saklanmaz). Ayrıntı §4.18 |
| Geri yükleme provası (F11) | **geri yükleme provası**; programın kendi denetiminde **"temiz bilgisayarda geri yükleme provası"** | restore testi, felaket kurtarma tatbikatı, test geri yükleme | Program her sürümde sınar; okul isterse başka bir **demirbaş** bilgisayarda kurtarma anahtarıyla yapar ve provadan sonra o bilgisayardaki veri, yedek ve günlük klasörlerini siler (kılavuzun Yedek bölümü, `docs/kurulum.md` §7.1) |
| Eski program, yeni veri (`SchemaTooNewError`, çıkış kodu 4; F11) | açılış iletisinin başlığı **"Program sürümü eski"**; çözüm **"programı güncelleyin"** | şema, migration, göç, sürüm uyuşmazlığı (kullanıcı metninde) | İki durumda çıkar: daha yeni sürümün açtığı veriyi eski program açmaya çalışınca ve daha yeni sürümle alınmış yedek eski programa geri yüklenince. Program veriyi korumak için açılmaz. İleti "tanımadığı **değişiklikler**" der; tanınmayan değişikliklerin (göçlerin) adları iletide GEÇMEZ, yalnız günlüğe (`logs/uygulama.log`) yazılır ve ipucu günlük dosyasını anar (27.09.2026 ana oturum kararı — §2 iç kimlikler). `docs/kurulum.md` §10.4, §11 |
| Lisans | **LGPLv3** (yalnız Pardus sürümünün lisans bildiriminde), **PolyForm Noncommercial** | — | Lisans adı teknik ad sayılmaz: bildirim yükümlülüğü gereği açıkça yazılır (`docs/kurulum.md` §4.1, `packaging/linux/BENIOKU.txt`) |
| Sürüm | **"yayımlanan son sürüm"**, **"kurulum dosyası"**; düğmeler **"Şimdi denetle"** · **"Doğrula ve indir"**; elle denetlemenin bağlantısı **okulapp.org/kutuphane-defteri** (programın sayfası; dosyalar indir.okulapp.org'dan iner) | GitHub sürümü, Release, kurucu; "Denetle" (tek başına, düğme adı olarak) | Güncelleme denetimi yalnız düğmeyle yapılır. Hedef GitHub'dır (27.09.2026 kullanıcı kararı); hizmetin adı ulaşılamama iletisinde (**"GitHub'a ulaşılamadı; okul ağında engellenmiş olabilir. Yeni sürümü indir.okulapp.org'dan elle denetleyebilirsiniz."**), Hakkında'da, kılavuzun Güncelleme bölümünde ve kurulum belgesinde geçer (program dışarı hangi adrese çıktığını söyler); Güncelleme ekranının açıklama metninde geçmez. Program indir.okulapp.org'a ve programın sayfasına istek atmaz: bağlantıyı dış tarayıcı açar. Ekran adları §4.19 |

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
| E7 | Ayıklama belgeleri: Ayıklama teklif listesi · Ayıklama tutanağı · Kayıttan düşme teklif listesi · İmha tutanağı · Devir listesi |
| E8 | El yazması ve nadir eserler listesi |
| E9 | Yıl sonu kütüphane raporu |
| E10 | Sayım tutanağı (eki: Taşınır Sayım ve Döküm Cetveline aktarılacak sayılar) |
| E11 | Taşınır Kütüphane Defteri dökümü · Yönetim hesabı cetveli hazırlığı |
| E12 | Ayın Kitapları afişi |
| E13 | Kütüphane aydınlatma metni |
| E14 | Kurtarma anahtarı çıktısı |
| E15 | Teslim listesi · Geri alma dökümü |
| E16 | Bağış ön kayıt listesi · Bağış değerlendirme sonucu |
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

*Aşağıdaki tablolar F11 sonundaki durumdur (27.09.2026); kaynak `AppShell.tsx`
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
| — | Yıl Sonu Raporu | `/yil-sonu-raporu` | Menüde yoktur; Genel Bakış'taki **Yıl Sonu Raporu** kartından (yıl sonu penceresinde, rapor sonlandırılana dek) ya da Yıl Sonu ekranının son adımından açılır. Yıl sonu kütüphane raporu (Md. 12/1). Yalnız yönetici kipinde (F8, §4.14) |
| — | Yıl Başı | `/yil-basi` | Menüde yoktur; Genel Bakış'taki **Yıl Başı** kartından (yıl başı penceresinde) ya da İlişik Listesi'nin sağ üstünden açılır. Adım adım ekran; kayıt yazmaz, işin yapıldığı ekrana götürür (§4.13). Yalnız yönetici kipinde |
| Katalog | Katalog | `/katalog` | Eser ve nüsha listelerinin tek ekranı |
| — | Eser Ayrıntısı | `/katalog/eser/:id` | Menüde yoktur; katalog listesindeki satıra tıklanarak açılır. Başlıkta modül adı geri bağlantısıdır ("Katalog / Eser Ayrıntısı") |
| — | Edinimler ve Bağışlar | `/katalog/edinimler` | Menüde yoktur; Katalog sayfasının sağ üstündeki **Edinimler ve Bağışlar** bağlantısıyla açılır |
| — | Hızlı Kayıt | `/katalog/hizli-kayit` | Menüde yoktur; Katalog sayfasının sağ üstündeki **Hızlı Kayıt** bağlantısıyla açılır. Kitap elde, ISBN okutarak tek tek giriş |
| — | Etiketler | `/katalog/etiketler` | Menüde yoktur; Katalog sayfasının sağ üstündeki **Etiketler** bağlantısıyla açılır. Sırt ve barkod etiketi basımı, basım kaydı, boş barkod aralığı, doğrulama okutması, şablon ve kalibrasyon. İçe aktarmanın **"Bu partinin etiketlerini bas"** kısayolu buraya gelir |
| — | İçe Aktarma | `/katalog/ice-aktarma` | Menüde yoktur; Katalog sayfasının sağ üstündeki **İçe Aktarma** bağlantısıyla açılır. Toplu giriş, yapay zekâ köprüsü, çevrimdışı künye ve aktarım geçmişi |
| — | Ayıklama | `/katalog/ayiklama` | Menüde yoktur; Katalog sayfasının sağ üstündeki **Ayıklama** bağlantısıyla açılır. Ayıklama teklifleri; `?teklif=<kimlik>` teklifi açar (iç kimlik ekrana yazılmaz, teklif ders yılı ve açılış tarihiyle tanınır). Başlıkta "Katalog / Ayıklama". Yalnız yönetici kipinde (F8, §4.14) |
| — | Nadir Eserler | `/katalog/nadir-eserler` | Menüde yoktur; Katalog sayfasının ve Ayıklama'nın sağ üstündeki **Nadir Eserler** bağlantısıyla açılır. El yazması ve nadir eserler listeleri ve nadir eser işaretli nüshalar. Yalnız yönetici kipinde (F8, §4.14) |
| — | Sayım | `/katalog/sayim` | Menüde yoktur; Katalog sayfasının sağ üstündeki **Sayım** bağlantısıyla ve Genel Bakış'taki **Sayım** kartından açılır. Sayım listesi; `?sayim=<kimlik>` sayımı açar (iç kimlik ekrana yazılmaz, sayım mali yılı ve başlangıç tarihiyle tanınır: "Sayım · 2026 · 21.12.2026"). Başlıkta "Katalog / Sayım". Yalnız yönetici kipinde (F9, §4.15) |
| Raporlar | Raporlar | `/raporlar` | F10. Kişisiz istatistik, çok okunanlar ve Ayın Kitapları afişi, dökümler ve dışa aktarım, kişi dökümü, okuma ödülü iç çıktısı (§4.16, §4.17). Genel Bakış'taki **Raporlar** kartından ve **Çok Okunanlar** kartından da açılır. Yalnız yönetici kipinde |
| Ayarlar | Ayarlar | `/ayarlar` | |
| — | Ağ Doktoru | `/ag-doktoru` | Menüde yoktur; **Ayarlar → Ağ Kataloğu** sekmesindeki **Ağ Doktoru** bağlantısıyla açılır. Yalnız yönetici kipinde (görevli kipinde her adreste görevli ekranı durur) |
| Kılavuz | Kullanım Kılavuzu | `/kilavuz` | |
| Hakkında ve Lisans | Hakkında ve Lisans | `/hakkinda` | Kenar çubuğunun altında, ana gezinmenin dışında |
| — | Kurulum Sihirbazı | `/kurulum` | Menüde yoktur. İlk açılışta kurulum kapısı buraya getirir; kurulumdan sonra Ayarlar'ın altındaki "Diğer Ayarlar" bölümünde **Kurulum Sihirbazı** kartıyla açılır |

Ana gezinmenin sırası: Genel Bakış · Dolaşım Masası · Kişiler · Katalog · Raporlar ·
Ayarlar · Kılavuz. Görevli kipinde gezinme bağlantıları gösterilmez; her adreste görevli ekranı
durur. Görevli ekranının varsayılan işi **Dolaşım Masası**dır; oradan **Doğrulama
Okutması**, **Katalogda Ara**, **Teslimden Geri Alma** (F7) ve süren sayım varken **Sayım
Okutması** (F9, madde 24) açılır (bölüm başlıkları; sayfanın h1'i ve üst çubuk "Görevli Kipi"
kalır).

### 4.2 Program durumu ekranları

Bunlar adres değildir; program durumuna göre sayfanın yerine gelir.

| Durum | Başlık |
|---|---|
| Kilitli | **Kayıtlar kilitli** |
| Görevli kipi | **Görevli Kipi** (üst çubukta da bu ad yazar) |
| Güvenlik dosyası yok ya da bozuk | **Güvenlik dosyası bulunamadı ya da okunamıyor** |
| Yedekten geri yüklendi | **Programı kapatıp yeniden açın** |

Pencere açılmadan çıkan açılış iletilerinin başlıkları (masaüstü ileti kutusu;
`desktop/errors.py`): **Program sürümü eski** (eski program, yeni veri — çıkış kodu 4;
F11) · **Veritabanı bozuk** · **Veritabanı güncellenemedi** · **Kütüphane Defteri zaten
çalışıyor** · **Pencere açılamadı** · **Program başlatılamadı**. İletinin gövdesi
sonucu, ikinci paragrafı yapılacak işi söyler (`docs/kurulum.md` §10, §11).

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
| Nadir Eserler | **Listeler** (`listeler`) · **Nadir Eser İşaretli Nüshalar** (`nushalar`) |
| İçe Aktarma | **Excel Aktarımı** (`excel`) · **Yapay Zekâ Köprüsü** (`kopru`) · **Çevrimdışı Künye** (`cevrimdisi`) · **Aktarım Geçmişi** (`gecmis`) |
| Raporlar | **İstatistik** (`istatistik`) · **Çok Okunanlar** (`cok-okunanlar`) · **Dökümler** (`dokumler`) · **Okuma Ödülü** (`okuma-odulu`) |
| Ayarlar | **Ders Yılları** (`ders-yillari`) · **Kapalı Günler** (`kapali-gunler`) · **Şubeler** (`subeler`) · **Kütüphane Politikası** (`politika`) · **Bölümler** (`bolumler`) · **Okul Bilgileri** (`okul`) · **Güvenlik** (`guvenlik`) · **Güncelleme** (`guncelleme`) · **Ağ Kataloğu** (`ag-katalogu`) · **Saklama** (`saklama`, F11) |

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
hafta sonrasına dek; yalnız sayı → Yıl Sonu) · **Yıl Sonu Raporu** (yıl sonu
penceresinde, etkin yılın raporu sonlandırılana dek: "Bu ders yılının raporu henüz
hazırlanmadı." / "Rapor taslak; sonlandırılmadı." → Yıl Sonu Raporu) · **Yıl Başı** (yalnız yıl başı
penceresinde — 15 Ağustos-31 Ekim ya da ders yılı başlangıcının çevresi — ve adımları
bitmemişken → Yıl Başı) · **Sayım** (F9; yalnız canlı sayım varken: "Sayım taslağı
hazırlanıyor; henüz başlatılmadı." / "Sayım sürüyor: N / M nüsha bulundu." / "İkinci sayım
sürüyor: …" / "Sayım tamamlandı; harcama yetkilisinin onayı bekleniyor."; süren seçenekler ayrı
satırlarda, **"İade her zaman açıktır."**; bağlantı **"Sayım'ı aç"**) · **Kitap Sayısı
10.000'i Aştı** (F10; yalnız elde bulunan kitap nüshası Yönetmelik Md. 7/1 eşiğini AŞINCA:
"Elde bulunan kitap: N.", maddenin cümlesi ve "Kart yalnız bilgi verir."; bağlantı ve düğme
yok — hüküm yorumlamaz) · **Çok Okunanlar** (F10; son dönemin ve son ayın ilk üç eseri, sayısız:
"Sıra farklı üye sayısına göredir; sayı gösterilmez."; bağlantı **"Çok Okunanlar'ı aç"** →
Raporlar → Çok Okunanlar; liste boşsa görünmez) · **Saklama Süresi Dolan Kayıtlar** (F11;
yalnız süresi dolan kayıt varken, yalnız sayı: "N kaydın saklama süresi doldu; silme ve
anonimleştirme onayınızı bekliyor."; onay altı aydan uzun beklerse **kapatılamayan** uyarı;
bağlantı **"Saklama ekranını aç"** → Ayarlar → Saklama) · **Bedel Bekleyen Dosyalar** (F11;
yalnız bedel adımında bir yıldan uzun bekleyen dosya varken; yıllık hatırlatma) · **Şifreli
Yedeği USB Belleğe Alın** (F11; yalnız son şifreli yedek indirmesinden 30 gün — ayar 7-90 —
geçince, hiç indirme yoksa yönetici parolası kurulduktan 7 gün sonra: "Son şifreli yedek
gg.aa.yyyy tarihinde indirildi (N gün önce)." / "Bu bilgisayarda henüz şifreli yedek
indirilmedi."; bağlantı **"Ayarlar → Güvenlik'i aç"**; program dosyanın USB'ye kopyalandığını
bilemez, kart "son indirme" der) · **Kişiler** ·
**Ayarlar** · **İlişik Listesi** · **Raporlar** (F10) · **Katalog Excel Şablonu** (bir sayfaya
gitmez, şablonu indirir).

### 4.6 Ayarlar → Güvenlik kartları

Sırasıyla: **Yönetici Parolası ve Şifreleme** (durumu, şifrelenen alanları,
"Parolayı değiştir" ve "Kilitle" düğmelerini taşır) · **Kurtarma Anahtarınız**
(yalnız yeni üretilmiş anahtar beklerken) · **Kurtarma Anahtarını Doğrula**
(yalnız anahtar doğrulanmamışken) · **Kurtarma Anahtarını Yenile** ·
**Kurtarma anahtarı çıktısı** (belge adı, §2 E14) · **Görev Devri** (F11; adımlar
"Parola ve anahtar yenilenir" · "Yeni anahtar saklanır" · "Görev devri notu basılır"; düğmeler
**"Görev devrini başlat"** / **"Görev devrini yeniden başlat"**, diyalog başlığı **"Görev devri
başlatılsın mı?"** (alanlar **"Mevcut yönetici parolası"** · **"Yeni yönetici parolası"** ·
**"Parola (tekrar)"**), onay **"Parolayı ve anahtarı yenile"**; kartın altında **"Açık işler"**
(görevi devralana kalan işlerin kişisiz sayıları, onay bekleyen saklama işlemi dahil); alanlar **"Görevi devreden (adı
soyadı)"** · **"Görevi devralan (adı soyadı)"** · **"Ek not (isteğe bağlı)"**; indirme
**"Görev devri notunu indir"**; kart adım adımdır: yalnız o anki adımın işi görünür, görev devrinin
yeni anahtarı **bu kartın içinde** “Kurtarma Anahtarınız” paneliyle saklatılır — ekranın başında
yalnız **"Görev devrinin yeni kurtarma anahtarı aşağıdaki “Görev Devri” kartında bekliyor."**
bandı durur; not indirilince **"Not indirildi. …"**) · **Şifreli Veritabanı Yedeği** (F11: son
indirme cümlesi, hatırlatmanın durumu — **"Hatırlatma süresi doldu: …"** / **"Genel Bakış N gün
sonra yeniden hatırlatır."** — ve **"Hatırlatma süresi"** seçimi) · **Yedekten Geri Yükleme**.

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
| Sayım için hizmet arası (masada) | şerit **"Sayım için hizmet arası — yeni ödünç ve teslim yapılamıyor. İade ve teslimden geri alma açık."**, altında **"Üye kartı okutmadan kitabın kütüphane etiketini okuttuğunuzda iadesi alınır."** (Yeni Teslim'de altında **"Sayım onaylanınca ya da iptal edilince teslim yeniden açılır. Dönen kitapları Geri Alma sekmesinde okutun."**); ödünç reddinden sonra **"Kitap iade için getirildiyse iadesi alınabilir."** (düğme **"İade al"**) | sayım kilidi, dondurma, masa kapalı, ödünç yasağı | F9. Okul kararıdır, yeni ödüncü ve yeni teslimi durdurur (madde 27); iade ve teslimden geri alma sürer. Şerit iki kipte de masa açılınca çıkar (madde 26, 25.09.2026 kullanıcı kararı): masa kişisiz masa durumunu (`library-desk-state`) okur, sayımın yönetici uçlarını sormaz; durum dakikada bir yeniden okunur, ödünç reddi şeridi hemen açar, başarılı ödünç kaldırır. İleti görevli ve yönetici kipinde, masada ve teslimde aynıdır, kişisiz ve tarihsizdir (`circulation.SERVICE_PAUSE_MESSAGE`) |
| Masadaki bilgi iletileri | **"Kitabın kütüphane etiketini okutun."** (kart okundu, sıra kitapta) · **"Üye kartı okundu."** · **"Kart okutma yeniden açıldı."** · **"Gerekçeli istisnayla ödünç verildi."** · başka üyedeki kitap iade alınıp verilince **"Kitap başka bir üyenin ödüncündeydi; iadesi alındı. Durumu kütüphane yöneticisine bildirin."**; "İade al ve ödünç ver" sürerken bağlam değişince **"İade alındı; üye bağlamı bu arada değiştiği için kitap ödünç verilmedi."**; yönetici kipinde iade **"İade alındı. N gün gecikti."** | — | Masadaki son işlemler listesinin (**"Bu ekrandaki son işlemler"**) satırlarıdır; görevli kipinde satırlarda üye adı yazmaz |
| Etiket ve kod iletileri | **"Bu ISBN barkodu. Kitabın kütüphane etiketini okutun."** · **"Bu bir üye kartı. Kitabın kütüphane etiketini okutun."** · **"Bu kod tanınmadı. Kitabın kütüphane etiketini ya da üye kartını okutun."** · **"Bu barkodla kayıtlı nüsha yok. Kitabı ayırın ve kütüphane yöneticisine gösterin."** · bağlanmamış boş etiket ve numarası iptal edilmiş etiket için Doğrulama Okutması'ndaki iletiler; görevli kipinde sonları **"Kitabı ayırın ve kütüphane yöneticisine gösterin."** | geçersiz barkod, hatalı etiket | Görevli kipinde Hızlı Kayıt yönergesi verilmez (ekran görevliye kapalıdır), kitap yöneticiye yönlendirilir |
| Görevli ekranının işleri | bölüm başlıkları **Dolaşım Masası** · **Doğrulama Okutması** · **Katalogda Ara** · **Teslimden Geri Alma** (F7) · **Sayım Okutması** (F9); düğmeler **"Doğrulama okutmasını aç"** / **"Okutmayı bitir"**, **"Katalogda ara"** / **"Dolaşım masasına dön"**, **"Teslimden geri al"** / **"Okutmayı bitir"**, **"Sayım okutmasını aç"** / **"Okutmayı bitir"**, **"Yönetici kipine geç"** | kiosk, öğrenci ekranı | Katalogda Ara'da alan **"Kaynak adı, yazar, konu ya da ISBN"**; künye ve nüsha durumu görünür, edinim ve kimde olduğu görünmez. **"Sayım okutmasını aç"** yalnız okutması açık süren bir sayım varken görünür (madde 24, 25.09.2026 kullanıcı kararı); kutu **"Kütüphane etiketi"**, açıklama **"Rafta ve kütüphanede duran kitapların kütüphane etiketini okutun. Aynı kitabı ikinci kez okutmak zararsızdır. Sayımın ilerlemesini, fazlasını ve sonuçlarını kütüphane yöneticisi görür."**; ekranda yalnız okutmanın iletisi, barkod ve kitabın adı yazar (kalem, ilerleme, sayım fazlası kartı yok). Okutma sürerken sayım kapanırsa **"Süren sayım yok: okutma kapandı. Dolaşım masasına dönmek için “Okutmayı bitir”e basın."** |

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
nüsha rafa döner."**; "Bedelle başka eser alındı" ile kapanmış kayıp dosyasında yalnız
**"Bulundu (bedel teslim alınmıştı)"** ve açıklama **"Kayıttan düşme yalnız önerildi; nüsha
hâlâ “Kayıp”. Kitap bulunduysa “Bulundu (bedel teslim alınmıştı)” seçin: öneri geri alınır ve
nüsha rafa döner; bedelle alınan eser kayıtta kalır."**; bedelden sonra bulunmada bilgi
**"Teslim alınan bedelin kişiye iadesi ya da başka kaynak alımında kullanılması okul
yönetiminin kararıdır; program para tutmaz."**); nüshası kayıttan düşülmüş öneri dosyasında
bölüm **Bulunan kitap** (**"Nüsha kayıttan düşülmüş; kitap bulunursa bu dosyadan rafa dönmez.
Kitabı “Sayım fazlası (kayda giriş)” yoluyla açılan bir edinimle, Eser Ayrıntısı'nda “Nüsha
ekle” diyerek yeni nüsha olarak kaydedin."**); bölüm **Onarım**
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
| Çözüm durumları | **Çözüm bekliyor** · **Bedel belirlendi** · **Bedel teslim alındı** · **Bulundu** · **Aynısı temin edildi** · **Onarıldı** · **Bedelle aynısı alındı** · **Bedelle başka eser alındı** · **Bulundu (bedel teslim alınmıştı)** · **Kayıttan düşme önerildi** · **Kayba dönüştü** | borç, ceza, tahsil edildi, ödendi, zayi, kayıttan düşüldü, bedel kaydedildi (iki adım ayrıdır), bedel iade edildi | `CaseResolution` ile birebir. Bedel yolları yalnız ortaöğretimde ve sırayla: "Bedel belirlendi" → "Bedel teslim alındı" → "Bedelle aynısı / başka eser alındı" ya da (kayıpta) "Bulundu (bedel teslim alınmıştı)" — sonuncusu "Bedelle başka eser alındı" ile kapanmış dosyada da, nüsha kayıttan düşülmemişse seçilir (25.09.2026 kullanıcı kararı). Açık dosyalar "Çözüm bekliyor", "Bedel belirlendi" ve "Bedel teslim alındı"dır; kişinin açık işi yalnız ilk ikisidir. Kayıttan düşme burada yalnız öneridir. "Kayba dönüştü" düğme değildir: yalnız hasar dosyasında, kayıp bildiriminin kapattığı dosyada görünür |
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
**Son Sınıflar ve Ayrılanlar** · **İlişik ve Belgeler** · **Yıl Sonu Raporu** (F8; adım
kayıt yazmaz, bağlantısı **"Yıl Sonu Raporu'nu aç"**, rapor sonlandırılınca tamamdır); düğmeler **"Geri"**,
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

### 4.14 Ayıklama, nadir eser ve yıl sonu raporu ekranlarının ve belgelerinin adları

Kılavuz bu adları birebir kullanır; ekrandaki metin değişirse buradaki de değişir
(kaynak `frontend/src/modules/ayiklama`, iletiler `services/weeding.py`,
`services/rare_works.py`, `services/annual_review.py`, belgeler
`apps/kutuphane/komisyon_belgeleri.py` ve `yil_raporu_belgesi.py`). F8'de eklendi.

**Ayıklama** (sayfa). Liste: süzgeç "Durum", düğme **"Yeni teklif"**; tablo Ders yılı ·
Açılış · Durum · Kalem · Kayıttan düşme · devir · Komisyon kararı. Teklif ayrıntısı:
başlık **"Ayıklama teklifi · <ders yılı> · gg.aa.yyyy"**, dönüş düğmesi **"Tekliflere
dön"**, adım rayı **Taslak** · **Komisyona sunuldu** · **Komisyon kararı** · **Harcama
yetkilisi onayı** · **Uygulandı**; bilgi satırları Ders yılı · Kalem · Komisyon kararı ·
Harcama yetkilisinin onayı · Komisyon üyeleri · İmha kararı · Uygulanma. Eylemler adıma
göre: **"Kalem ekle"** · **"Komisyona sun"** (onay "Teklif komisyona sunulsun mu?") ·
**"Teklifi sil"** (yalnız taslak) · **"Komisyon kararını bağla"** · **"Harcama yetkilisinin
onayını işle"** · **"Uygula"** (onay "Teklif uygulansın mı?" + ikinci doğrulama kutusu
"Harcama yetkilisinin onayını ve belgelerin imzalandığını denetledim.") · **"Teklifi geri
çek"** (onay "Teklif geri çekilsin mi?") · **"İptal et"** (pencere "Teklif iptal edilsin
mi?", alan "İptal gerekçesi (isteğe bağlı)"). Bölüm **Kalemler** (tablo Barkod · Kaynak adı ·
Gerekçe · TMY yolu · Kalem durumu; satırda **"Düzenle"** ve **"Çıkar"** yalnız taslakta,
sunulmuş teklifin devir kaleminde **"Devralacak kurum"**; devralacak kurum yoksa
**"Devralacak kurum yazılmadı"**). Kart **Ayıklama
Belgeleri** (belge başına "Önizle" · "PDF'i indir", devir listesinde ayrıca **"Excel'i
indir"**; basılamayan belgenin yanında sunucunun nedeni, ör. "Komisyon kararı bağlandıktan
sonra basılır.").

Pencereler: **Kalem ekle** (alanlar "Ayıklama gerekçesi", "TMY yolu" — gerekçeden
kendiliğinden, "Uyulmayan ölçüt" — yalnız 12/1-ç'de, "Devralacak okul ya da kurum" — yalnız
devirde, "Kütüphane etiketleri"; bölüm **Aday Nüshalar** (kutu "Ara", sayaç "N nüsha
seçildi"), alttaki iki bilgi kutusu **"Kayıp nüshaların kayıttan düşme önerileri"** ve
**"Hasar dosyalarının kayıttan düşme önerileri"** (seçilemez; ileti **"Hasar dosyasında
kayıttan düşme önerilen nüsha ayıklamaya konmaz (Md. 12/1 gerekçelerinden değildir); sayımda
kayıttan düşülür."** — 25.09.2026 kullanıcı kararı); düğme **"Teklife ekle (N)"**; engelli
nüshalar liste olarak) ·
**Kalemi düzenle** / **Devralacak kurumu düzenle** · **Komisyon kararını bağla** (alan
"Komisyon kararı" — yalnız "Ayıklama" türü; kalem başına kutu **"Komisyon ayıklanmasına
karar vermedi"** ve "Gerekçe"; düğme **"Kararı bağla"**) · **Harcama yetkilisinin onayı**
(alanlar "Harcama yetkilisinin adı", "Onay tarihi", "Komisyon üyeleri"; kutu **"İmha kararı
verildi (TMY md. 28/5)"** yalnız hurdaya ayırma yolunda; kalem başına kutu **"Onaylanmadı"**
ve "Gerekçe"; imha kararı işaretlenince liste **"İmha kararının kapsadığı kalemler"** — kalem
başına kutu, varsayılan seçili; düğme **"Onayı işle"**). Kalem tablosunda rozet **"Nadir eser
— ayıklanamaz"** ve kalem satırı **"İmha kararı (TMY 28/5)"**. "İmha" sözcüğü ekranda yalnız bu
kutuda, bu listede, bilgi satırlarında ve İmha tutanağının adında geçer (28/5 bağlamı).

**Nadir Eserler** (sayfa). Sekmeler **Listeler** · **Nadir Eser İşaretli Nüshalar**.
Listeler: **"Yeni liste"**; tablo Ders yılı · Durum · Eser · Komisyon kararı · Gönderim;
pencere başlığı belge adıdır (**El yazması ve nadir eserler listesi**): "Komisyon kararı"
seçicisi ve **"Kararı kaydet"**, bölüm **Listedeki Eserler** (satırda "Çıkar"), bölüm
**Bildirilmemiş Nadir Eserler** (**"Seçilenleri listeye ekle (N)"**), bölüm **Genel
Müdürlüğe Gönderim** (alanlar "Gönderim tarihi", "Gönderme yazısının sayısı (isteğe
bağlı)", düğme **"Gönderildi olarak işaretle"**, onay "Liste gönderildi olarak işaretlensin
mi?"), **"Listeyi sil"** (yalnız hazırlanan listede). Nüshalar sekmesi: kutu **"Yalnız
bildirilmemişler"**, rozet **"Bildirildi"** / **"Bildirilmedi"**.

**Yıl Sonu Raporu** (sayfa). Etkin yılın raporu yoksa kart **"<ders yılı> ders yılının
raporu henüz hazırlanmadı."** ve **"Raporu hazırla"**; birden çok raporda seçici "Ders
yılı". Alanlar **"Sayı"**, **"Tarih"**, **"Tespit edilen hususlar"** (yardım **"Kaynakların
durumu ve öneriler. Kişi adı yazmayın."**); düğmeler **"Kaydet"**, **"Raporu sonlandır"**
(onay "Rapor sonlandırılsın mı?"), **"Sonlandırmayı geri al"** (onay "Sonlandırma geri
alınsın mı?"); rozet **Taslak** / **"Sonlandırıldı · gg.aa.yyyy"**; kart **Rapordaki
Sayılar** (kişisiz); bilgi **"Raporu yeni ders yılı tanımlandıktan sonra sonlandırmanız önerilir; Haziran'da sonlandırırsanız yaz aylarındaki işler (ör. Ağustos'taki ayıklama) bu rapora girmez. Gerekirse sonlandırmayı geri alıp yeni ders yılı tanımlandıktan sonra yeniden sonlandırın."** (dönem kuralı değişmedi — 25.09.2026 kullanıcı kararı). Sağ üstte **Yıl Sonu** ve **İlişik Listesi** bağlantıları.

| Kavram | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| Teklif durumları | **Taslak** · **Komisyona sunuldu** · **Komisyon kararı bağlandı** · **Harcama yetkilisi onayladı** · **Uygulandı** · **İptal edildi** | onaylandı (tek başına), kapandı, silindi | `WeedingBatchStatus` ile birebir. Adım rayında kısa adlar ("Komisyon kararı", "Harcama yetkilisi onayı") kullanılır |
| Ayıklama gerekçesi | **Aşırı kullanımdan yıpranmış** · **Bilimsel değeri kalmamış** · **Kurumun düzeyine uygun değil** · **10. maddedeki ölçütlere uygun değil** | eskimiş, işe yaramaz, hurda | `WeedingReason` ile birebir; Md. 12/1'in a-ç bentleri (ekranda bentle birlikte, ör. "(Md. 12/1-a)"). Yaş ve gelişim düzeyine uygunsuzluk (10/1-b) "Kurumun düzeyine uygun değil"dedir ve devredilir |
| Uyulmayan ölçüt | **Türk millî eğitiminin genel amaçları ve temel ilkelerine uygun değil** · **Millî, manevi, kültürel, ahlâki ve insani değerlere uygun değil** · **Dengeli ve sağlıklı kişilik gelişimini desteklemiyor** · **Türkçenin doğru ve güzel kullanımını desteklemiyor** · **Eleştirel ve özgün düşünme becerilerini desteklemiyor** · **Farklı okuryazarlıkları desteklemiyor** · **Kütüphanede bulundurulamaz (Md. 10/4)** | — | Yalnız "10. maddedeki ölçütlere uygun değil" gerekçesinde; 10/1-b listede YOKTUR (sunucu ve DB kısıtı reddeder) |
| TMY yolu | **Kullanılmaz hâle gelme nedeniyle kayıttan düşme (TMY 27/1)** · **Hurdaya ayırma nedeniyle kayıttan düşme (TMY 28)** · **Başka bir MEB okuluna devir (TMY 24/2)** · **Başka bir kamu idaresine bedelsiz devir (TMY 31)** | imha (yol adı olarak), hurdaya çıkarma, bağış (devir anlamında) | `WeedingTmyPath` ile birebir; gerekçeden kendiliğinden gelir (tasarım §10 E7 tablosu). Belgelerde kısa biçim: "Kayıttan düşme (TMY md. 27/1)", "Hurdaya ayırma (TMY md. 28)", "Devir: MEB okulu (TMY md. 24/2)", "Devir: başka kamu idaresi (TMY md. 31)" |
| Kalem durumu | **Teklif listesinde** · **Komisyon ayıklanmasına karar vermedi** · **Onaylanmadı** · **Uygulandı** | reddedildi, silindi | `WeedingItemState` ile birebir. Dışarıda bırakılan kalem silinmez, gerekçesiyle belgede ayrı tabloda durur |
| Nadir eser listesi durumu | **Hazırlanıyor** · **Genel Müdürlüğe gönderildi** | onaylandı, kapandı | `RareWorksSubmissionStatus` ile birebir. Genel Müdürlük, Destek Hizmetleri Genel Müdürlüğüdür (Md. 4/1-c) |
| E7 belgeleri | başlıklar **"AYIKLAMA TEKLİF LİSTESİ"** · **"AYIKLAMA TUTANAĞI"** · **"KAYITTAN DÜŞME TEKLİF LİSTESİ"** (alt başlık "Kayıttan Düşme Teklif ve Onay Tutanağına esas hazırlık çıktısı") · **"İMHA TUTANAĞI"** · **"DEVİR LİSTESİ"** (+ Excel); imza **"Teklif eden — Kütüphane yöneticisi"**, **"SEÇİM VE AYIKLAMA KOMİSYONU"** (Komisyon başkanı · Üye), **"KOMİSYON"** (Komisyon üyesi; hurdaya ayırmada ilk satır **Komisyon üyesi (işin uzmanı)**), **"OLUR"** (Harcama yetkilisi), **"Devreden — Kütüphane yöneticisi"** / **"Devralan — …"** | kayıttan düşme tutanağı (resmî tutanak anlamında), VİF, hurda listesi | Resmî Kayıttan Düşme Teklif ve Onay Tutanağı ve Varlık İşlem Fişi TKYS'dedir; dipnot bunu söyler. "İmha" yalnız İmha tutanağındadır (testli). İmha tutanağı şablondur, yalnız imha kararının kapsadığı kalemleri basar: imha tarihi, yeri ve yöntemi elle yazılır. Kalemler yalnız Md. 12/1 gerekçelidir: kayıp ve hasar dosyasının kayıttan düşme önerisi ayıklamaya konmaz, sayımda kayıp/hasar tutanağıyla düşülür (25.09.2026 kullanıcı kararı). Kurumu yazılmamış devir kaleminde künye **"Yazılmadı"**, imza **"Devralan okul ya da kurum"** |
| E8 belgesi | başlık **"EL YAZMASI VE NADİR ESERLER LİSTESİ"**; Md. 12/2 alıntısı; imza **"SEÇİM VE AYIKLAMA KOMİSYONU"** | nadir kitap envanteri | Karar bağlanmamışsa imza satırları boştur |
| E9 belgesi | **"Sayı :"**, tarih, **"Konu : Yıl sonu kütüphane raporu (<ders yılı> ders yılı)"**, muhatap **"OKUL MÜDÜRLÜĞÜNE"**, bölümler **1. TESPİT EDİLEN HUSUSLAR** · **2. KOLEKSİYON ÖZETİ (RAPOR TARİHİNDE)** · **3. YIL İÇİNDE KAZANDIRILAN KAYNAKLAR** · **4. AYIKLANAN VE DEVREDİLEN KAYNAKLAR** · **5. ÖDÜNÇ İSTATİSTİĞİ**, kapanış **"Bilgilerinize arz ederim."**, imza **Kütüphane yöneticisi** (ad basılmaz); taslakta **"TASLAK — Rapor sonlandırılmadı; sayılar basım anındaki kayıtlardandır."** | okuma raporu, öğrenci listesi | KİŞİSEL VERİ YOK (testli): eşiğin altındaki grup "—" yazılır; toplamdan geri hesaplanamasın diye gerekirse bir grup daha gizlenir (tamamlayıcı gizleme). Aktif üye sayısı eşiksizdir: üyelik sayısı ödünç verisi değildir (27.09.2026 kullanıcı kararı, tasarım F10 ekleri K1; şema 3 — eski şemayla dondurulmuş rapor kendi kuralıyla "—" basar). Kazandırılan yalnız Md. 10/5 yollarıdır; **"Kayıt içi girişler (kazandırılan sayılmaz)"** ayrı alt başlıktır |
| E16 belgesi | başlık **"BAĞIŞ ÖN KAYIT LİSTESİ"**; Md. 10/3 alıntısı; sütun **"Kabul / Ret"** (komisyonda doldurulur); imza **"Hazırlayan — Kütüphane yöneticisi"** | bağış kabul tutanağı | Kararın sonucu bu listeye yazılmaz; onu **Bağış değerlendirme sonucu** verir |
| Bağış değerlendirme sonucu (E16) | başlık **"BAĞIŞ DEĞERLENDİRME SONUCU"**; künye Geliş tarihi · Bağışçı · Seçim ve Ayıklama Komisyonu kararı · Edinim tarihi · Sonuç (**"Kabul: … · Ret: …"**); tablolar **"KABUL EDİLEN KAYNAKLAR"** · **"REDDEDİLEN KAYNAKLAR"** (sütun **"Ret gerekçesi"**); Md. 10/3 alıntısı; TMY 16/1 ve 13/2-c notu; imza **"Hazırlayan — Kütüphane yöneticisi"**; dipnot TKYS | bağış kabul tutanağı, bağış tutanağı, kabul belgesi | 25.09.2026 kullanıcı kararı (tasarım F8 ekleri 13). Yalnız komisyon kararı uygulanmış ön kayıtta basılır (öncesinde **"Komisyon kararı uygulandıktan sonra basılır."**). Taşınır kayıt yetkilisinin Varlık İşlem Fişine dayanak ve bağışçıya bilgidir; resmî belge değildir. TMY'de "bağış kabul tutanağı" diye bir belge yoktur — kılavuz bunu tek olumsuz cümleyle söyler |

### 4.15 Sayım ekranlarının ve belgesinin adları

Kılavuz bu adları birebir kullanır; ekrandaki metin değişirse buradaki de değişir (kaynak
`frontend/src/modules/sayim`, iletiler `services/stocktake.py`, `services/tmy_kapisi.py`,
`services/circulation.py`, belge `apps/kutuphane/sayim_belgeleri.py`). F9'da eklendi.

**Sayım** (sayfa). Liste: tablo Mali yıl · Başlangıç · Durum · Seçenekler · Onay; canlı sayım
yoksa **"Yeni sayım"**, varsa **"Süren sayımı aç"** ve **"Onaylanmamış bir sayım var; yeni sayım
açmadan önce onu onaylayın ya da iptal edin."**. Sayım ayrıntısı: başlık **"Sayım · <mali yıl> ·
gg.aa.yyyy"**, dönüş düğmesi **"Sayımlara dön"**, adım rayı **Taslak** · **Sayım** · **İkinci
sayım** (noksan çıkmazsa atlanır) · **Harcama yetkilisi onayı** · **Onaylandı**; bilgi satırları
Mali yıl · Sayımın türü (**Yıl sonu sayımı** · **Ara sayım**) · Sayım kurulu · Başlangıç ·
Tamamlanma · Harcama yetkilisinin onayı; sürerken ve tamamlanmışken kutu **"Yıl sonu sayımı"**
(onaya dek değişir; F10); bölüm
**Seçenekler** (üç ayrı satır: TMY 32/3 durdurması · Sayım için hizmet arası · İade; süren
seçenekte rozet **"Sürüyor"**).

Taslakta kartlar **Sayım Kurulu** (alanlar "Kurul başkanı", "Taşınır kayıt yetkilisi", "Kurul
üyeleri", "Mali yıl (isteğe bağlı)", kutu **"Yıl sonu sayımı"** — açıklaması TMY 32/1'i ve
işaretsiz sayımın ekinin "Ara sayım" başlığını söyler; F10) · **Sayım Sırasındaki Seçenekler** (kutular **"TMY 32/3
durdurması"** — alanlar "Kurulun talep tarihi", "Harcama yetkilisinin adı", "Durdurma tarihi" —
ve **"Sayım için hizmet arası"** — alan "Okul kararı (isteğe bağlı)" —, her birinin altında
açıklaması ve iadenin hiç durmadığını söyleyen bilgi satırı) · **Ödünçteki, Teslimdeki ve
Onarımdaki Nüshalar** (seçiciler "Ödünçteki nüsha", "Sınıf kitaplığına teslim edilen nüsha",
"Öğretmene teslim edilen nüsha", "Onarımdaki nüsha"; altında kayıtlı seçimin dayanağı); alan
"Notlar"; düğmeler **"Sayımı başlat"** (onay "Sayım başlatılsın mı?"), **"Kaydet"**,
**"Taslağı sil"** (onay "Sayım taslağı silinsin mi?").

Süren sayımda kartlar **Kitapları Okutun** (kutu **"Kütüphane etiketi"**, sayaç **"Bu ekranda
bulunan: N"**, liste **"Son okutmalar"**) · **İkinci Sayım: Bulunamayan Nüshalar** (yalnız
ikinci sayımda) · **Bölümlere Göre İlerleme** ("N / M nüsha bulundu"; alt başlık **Yerinde
Sayılan Sınıf Kitaplıkları**) · **Sayım Fazlası** (**"Etiketsiz kitap ekle"**; satırda **"Eseri
seç"**, **"Kayda alınmayacak"**, **"Çıkar"**; karar rozetleri **"Kayda alınacak: …"** ·
**"Kayda alınmayacak"** · **"Karar bekliyor"** · **"Kayda alındı: …"** · **"Kayda alınmadı"** ·
**"Sayım sırasında kayda girdi: …"**; seçici **"Göster"** (**"Karar bekleyenler"** · **"Tümü"**),
sayaç **"N sayım fazlası · kararı bekleyen M"**, sayfalı liste);
düğmeler **"Sayımı tamamla"** / **"İkinci sayımı tamamla"** (onay "Sayım tamamlansın mı?" /
"İkinci sayım tamamlansın mı?"), **"İptal et"**. Tamamlanan sayımda **Sonuçlar** (etiketler
**"Kayıtlara göre (anlık görüntü)"** · **"Bulunan"** · **"Kayda göre alınan"** · **"Noksan"** ·
**"Sayım fazlası"**; gerektiğinde **"Henüz sayılmayan"** · **"Sayım sırasında kayıttan çıkan"** ·
**"Hasar önerisi (TMY 27/1)"** · **"İkinci sayımda bulunan"**) ve **Kalemler** (süzgeç "Sonuç",
varsayılan Noksan; "Ara"; sütunlar **Barkod** · **Kaynak adı** · **Bölüm** · **Kayda göre durum**
· **Sonuç** · **Onay sonucu**; sonuç altında gerektiğinde **"Toplanamadı; kayda göre alındı."**
(onarımdaki nüshada **"Onarımdan geri alınamadı; kayda göre alındı."**),
**"Hasar önerisi (TMY 27/1)"**, **"Kayıp dosyası: …"** / **"Hasar dosyası: …"**), düğme
**"Harcama yetkilisinin onayını işle"**. Taslak dışında kart **Sayım Belgeleri** ("Önizle" ·
"PDF'i indir" · "Excel'i indir"; sürerken açıklama **"Sayım sürerken ara döküm olarak basılır
(“TASLAK” ibaresiyle)."**, tamamlanınca **"Kurul ve harcama yetkilisi imzalar; onay imzalı
tutanağın tarihiyle işlenir."**; iptal edilmiş sayımda basılmaz). Tamamlama pencereleri
okutulmayanların nasıl sınıflandığını (ödünçte ve teslimde olan kayda göre alınır, sayım
sırasında kütüphaneye dönen bulunmuş sayılır) ve ikinci sayımı (md. 32/6) söyler.

Pencereler: **"Sayım onaylansın mı?"** (alanlar "Harcama yetkilisinin adı", "Onay tarihi";
bölüm **Onaylanmayan kalemler** — kalem başına kutu **"Onaylanmadı"** ve "Gerekçe", kutu "Ara";
ikinci doğrulama **"Harcama yetkilisinin imzaladığı sayım tutanağını denetledim."**; düğme
**"Onayla"**) · **"Sayım iptal edilsin mi?"** (alan "İptal gerekçesi (isteğe bağlı)") ·
**Etiketsiz kitap ekle** / **Kayda alınacağı eser** / **Kayda alınmayacak kitap** (alanlar
"Eser", "Açıklama" ya da "Gerekçe").

TMY 32/3 durdurmasının kapsadığı işlemlerin ekranlarında (Edinimler ve Bağışlar, Hızlı Kayıt, Eser
Ayrıntısı, onaylı ayıklama teklifi, Kayıp ve Hasar) bant **"TMY 32/3 durdurması
sürüyor"** (bağlantı **"Sayım'ı aç"**): "Sayım
onaylanana ya da iptal edilene dek … yapılamaz (Taşınır Mal Yönetmeliği md. 32/3). Durdurma
ödüncü ve iadeyi kapsamaz." Programa aktarımın ekranında (İçe Aktarma; Hızlı Kayıt'ta "Mevcut
koleksiyon (programa aktarım)" edinimiyle) bant **"Sayım sürüyor"**: **"Sayım sürerken programa
aktarım yapılamaz; sayım bitince aktarın."** (TMY'ye dayandırılmaz — F9 ekleri K4). Hızlı Kayıt'ta
durdurma sürerken **"Nüshayı aç"** kapalıdır. Dolaşım Masası'nda ve Teslimler → Yeni Teslim'de
şerit **"Sayım için hizmet arası — yeni ödünç ve teslim yapılamıyor. İade ve teslimden geri alma
açık."** (iki kipte de ekran açılınca çıkar — madde 26; durum dakikada bir yeniden okunur, ilk
başarılı ödünçle kalkar; Yeni Teslim'de **"Teslim et"** kapalıdır). Görevli Kipi sayfasında süren
sayım varken **"Sayım okutmasını aç"** (§4.10). Onay penceresinde kayıtta kayıp görünen ve sayım
sırasında onarıma gönderilen noksan için uyarı (**"Noksanlardan N kitap kayıtta kayıp görünüyor.
Kitap sayım tamamlandıktan sonra getirildiyse onaydan önce kayıp dosyasında “Bulundu”yu seçin;
onayda kayıttan düşülmez."** · **"Noksanlardan N kitap sayım sırasında onarıma gönderilmiş. …"**;
kalemin altında **"Kitap getirildiyse önce kayıp dosyasında “Bulundu”yu seçin."** · **"Kitap
onarımcıdaysa onaylamayın."**) ve gerekçenin yardımı **"Kişi adı yazmayın."** Sırada okutma
varken tamamlama düğmesi kapalıdır; ileti **"Sırada işlenmeyi bekleyen N okutma var. Okutmalar
bitince yeniden tamamlayın."**

| Kavram | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| Sayım durumları | **Taslak** · **Sürüyor** · **Tamamlandı** · **Onaylandı** · **İptal edildi** | açık, kapalı, kilitli (durum adı olarak) | `StockTakeStatus` ile birebir. İkinci sayım "Sürüyor"un içinde bir turdur; ekranda rozet **"İkinci sayım"** |
| Kurulun seçimi | **Kütüphanede sayılır** · **Sayımdan önce toplanır** · **Yerinde sayılır** · **Kayda göre alınır** | kayıttan sayılır, sanal sayım | `CountBasis` ile birebir. "Kütüphanede sayılır" seçilemez (raftaki ve kayıptaki nüsha); "Yerinde sayılır" yalnız sınıf kitaplığında. Seçici başına seçenekler: ödünç ve öğretmen **Sayımdan önce toplanır** · **Kayda göre alınır**; sınıf kitaplığı **Yerinde sayılır** · **Sayımdan önce toplanır** ("Kayda göre alınır" YOK — F9 ekleri K3, 25.09.2026: 32/5'in birinci cümlesi ortak kullanım alanını sayar, "sayım yapılmaksızın" yalnız ikinci cümlededir; toplanamayan şube nüshası yerinde aranır, bulunmazsa noksandır); onarımdaki nüsha kararın sözcükleriyle **"Sayımdan önce geri alınır"** · **"Kayda göre alınır — onarımda"** (K2; kod COLLECT · BY_RECORD). Dayanaklar: ödünç "32/5'e kıyasen; 23/4", şube "32/5 birinci cümleye kıyasen", öğretmen "32/5 ikinci cümle ya da 32/5'e kıyasen (23/4)", onarım **sayım kurulunun kararıdır** — "Taşınır Mal Yönetmeliğinde onarıma gönderilmiş taşınırın sayımına ilişkin doğrudan hüküm yoktur", 32/5 uydurulmaz. Okutulmayan onarımdaki nüsha noksan sayılmaz, kayda göre alınır ve tutanakta ayrı satırdadır; sayım sırasında onarıma gönderilen (anlık görüntüde rafta) nüsha okutulmazsa noksandır, onay penceresi uyarır |
| Sayım sonuçları | **Sayılmadı** · **Bulundu** · **Kayda göre alındı** · **Noksan** · **Fazla** · **Sayım sırasında kayıttan çıktı** | eksik, kayıp (sayım sonucu olarak), fazlalık | `StockTakeResult` ile birebir. Noksan TMY 32/6'nın sütun adıdır; ödünçteki, öğretmendeki ya da onarımdaki kitap noksan sayılmaz; sınıf kitaplığında bulunmayan kitap noksandır |
| Onay sonuçları | **Kayıttan düşüldü** · **Onaylanmadı** · **Onayda durumu değişmişti — düşülmedi** · **Kayıp kaydı kapandı** · **Kayda alındı** · **Kayda alınmadı** | silindi, reddedildi | `StockTakeOutcome` ile birebir. Onaylanmayan kalem gerekçesiyle kayıtta kalır |
| Okutma iletileri | **"Bulundu."** · **"Bulundu (ikinci sayım)."** · **"Bulundu. Kayıtta ödünçte görünüyor; kitap kütüphanedeyse masada iadesini alın."** · **"Bulundu. Kayıtta teslimde görünüyor; kitap kütüphanedeyse teslimden geri alın."** · **"Bulundu. Kayıtta kayıp görünüyor; sayım onaylanınca kayıp kaydı kapanır."** · **"Bu kitap bu sayımda zaten okutuldu."** · **"Bu nüsha sayım başladıktan sonra kayda girdi; bu sayımda sayılmaz."** · **"Bu nüsha sayım sırasında kayıttan çıktı; sayılmaz."** · **"Sayım fazlası: …"** (kayıttan düşülmüş, devredilmiş ya da silinmiş kaydın etiketi; bağlanmamış ya da numarası iptal edilmiş etiket; kayıtsız numara; etiket biçiminde olmayan kod) · **"Bu sayım fazlası zaten yazıldı."** · **"Bu bir üye kartı. Kitabın kütüphane etiketini okutun."** · **"Bu ISBN barkodu. Kitabın kütüphane etiketini okutun."** · **"Bu kod harf içeriyor; programın kütüphane etiketi değil. Kitabın kütüphane etiketini okutun; etiketi yoksa “Etiketsiz kitap ekle” ile yazın."** | hata (bulunamayan kitap için), bilinmeyen kitap | Kaynak `services/stocktake.py` (ISBN iletisi `barcode.py`); hiçbiri kişi adı taşımaz. Harfli kod rakamlarına indirgenip yazılmaz (iki ayrı eski etiket tek fazlada birleşmesin); etiketi okutulamayan kitap elle eklenir. Ödünçteki ya da teslimdeki kitabın iletisi kimde olduğunu söylemez. Üye kartı ve ISBN reddedilir, sayıma yazılmaz |
| Bulunma yolu | **Okutuldu** · **Sayım sırasında kütüphaneye döndü** | iade edildi (bulunma yolu olarak) | `StockTakeFoundVia` ile birebir. Dönüş: iade, teslimden geri alma, kayıp dosyasında bulunma ya da aynısının temini, sayım başladıktan SONRA onarımdan dönüş (Md. 23/1-c: iade hiçbir durumda durmaz) |
| Düşme yolu | **Sayım noksanı (TMY 32/7)** · **Kullanılmaz hâle gelme — hasar (TMY 27/1, 10/1-e)** | hurda, ayıklama (bu yollar için) | `StockTakeWriteOffPath` ile birebir; Excel'in "Kalemler" sayfasında yazılır. Sayımın iki düşme yolu ayıklama değildir ve Seçim ve Ayıklama Komisyonu kararı istemez |
| E10 belgesi | başlık **"SAYIM TUTANAĞI"** (alt başlık "Kütüphane materyali — Taşınır Mal Yönetmeliği md. 32"); durum notları **"TASLAK — Sayım sürüyor; sayılar basım anındaki kayıtlardandır ve kesin değildir."** · **"Sayım tamamlandı; harcama yetkilisinin onayı bekleniyor."** (kararı bekleyen sayım fazlası varken ardından **"N sayım fazlası kitabın kararı bekleniyor; …"**; ekte gelecek yıla devir **"Sayım fazlası kararları verilince yazılır"**, onaylanmamış hasar önerisi varken **"Harcama yetkilisinin onayından sonra yazılır"**); SONUÇLAR'da onarımda kayda göre alınan ayrı satır **"Kayda göre alınan (onarımda — sayım kurulunun kararı)"**; ekte satırlar **"Gelecek yıla devir (sayımda bulunan − onayda hasar nedeniyle kayıttan düşülen)"**, altında **"Sayımda bulunan miktar (sayım tutanağı)"** ve **"Onayda hasar nedeniyle kayıttan düşülen (TMY md. 27/1)"** (F9 ekleri madde 25 a); ek tablo **"ÖDÜNÇTEKİ, TESLİMDEKİ VE ONARIMDAKİ NÜSHALARIN SAYILIŞI"**; sürerken boş noksan tablosu **"Noksan sayım tamamlanınca belirlenir."**; ekin ikinci paragrafı yıl sonu sayımında **"Bu sayım yıl sonu sayımıdır …"**, işaretsiz sayımda ara sayım notu (**"Bu sayım yıl sonu sayımı olarak işaretlenmedi … cetvele aktarılmaz."**); künyede **"Sayımın türü"** (F10); tablolar **"SAYIM SONUÇLARI"** · **"SAYIM SIRASINDAKİ SEÇENEKLER"** · **"ÖDÜNÇTEKİ, TESLİMDEKİ VE ONARIMDAKİ NÜSHALAR — SAYIM KURULUNUN SEÇİMİ"** · **"BÖLÜMLERE GÖRE"** · **"SAYIM NOKSANI — KAYITTAN DÜŞME TEKLİFİ (TMY MD. 32/7)"** · **"HASAR NEDENİYLE KAYITTAN DÜŞME TEKLİFİ (TMY MD. 27/1)"** · **"KAYITTA KAYIP GÖRÜNÜP SAYIMDA BULUNAN KAYNAKLAR"** · **"SAYIM FAZLASI (TMY MD. 17)"** · onaydan sonra **"HARCAMA YETKİLİSİNİN ONAYLAMADIĞI KALEMLER (KAYITTA KALDI)"** ve **"ONAYDA DURUMU DEĞİŞEN KALEMLER (KAYITTAN DÜŞÜLMEDİ)"**; sütun **"Kayıp/hasar tutanağı"**; imza **"SAYIM KURULU"** (Sayım kurulu başkanı · Taşınır kayıt yetkilisi · Üye) ve **"OLUR"** (Harcama yetkilisi); dipnot TKYS; yeni sayfada ek **"EK: TAŞINIR SAYIM VE DÖKÜM CETVELİNE AKTARILACAK SAYILAR"** (yalnız "Yıl sonu sayımı" işaretli sayımda; işaretsiz sayımda başlık **"EK: ARA SAYIM — SAYILAR CETVELE AKTARILMAZ"**, Excel sayfası **Ara sayım** — F10; TMY 34/1 alıntısı; **"Bu döküm Taşınır Sayım ve Döküm Cetveli değildir; resmî cetvel TKYS'de düzenlenir."**) · Excel sayfaları **Sayım tutanağı** · **Kalemler** · **Cetvele aktarılacak sayılar** | sayım cetveli, döküm cetveli (ek için), envanter listesi | ÖDÜNÇ ALANIN VE TESLİM ALANIN KİMLİĞİ YOK (testli: sentetik adla PDF ve Excel taraması). Kişi adı yalnız kurulda ve harcama yetkililerinde (şifreli alandan). Taslakta ve iptal edilmiş sayımda basılmaz (**"Sayım başladıktan sonra basılır."** · **"İptal edilmiş sayımın tutanağı basılmaz."**). Resmî Sayım Tutanağı (taşınır kodu düzeyinde), Kayıttan Düşme Teklif ve Onay Tutanağı, Varlık İşlem Fişi ve Taşınır Sayım ve Döküm Cetveli TKYS'dedir |

### 4.16 Raporlar, istatistik ve çok okunanlar ekranlarının ve belgelerinin adları

Kılavuz bu adları birebir kullanır (kaynak `frontend/src/modules/raporlar`, belgeler
`apps/kutuphane/{ayin_kitaplari_belgesi,okuma_odulu_belgesi}.py`, hesap `services/populer.py`,
`selectors_istatistik.py`). F10'da eklendi; hepsi yönetici kipindedir.

**Raporlar** (sayfa; ana gezinmede). Sekmeler §4.3. Sayfa katalog, üye ve ödünç kayıtlarını
değiştirmez; tek yazan "Yeniden hesapla"dır ve yalnız kişisiz sıra tablosunu yazar.

**İstatistik** (sekme). Seçici **"Dönem"**: "YYYY-YYYY ders yılı (etkin)" · öbür ders yılları ·
**Tarih aralığı** (alanlar **"Başlangıç tarihi"** · **"Bitiş tarihi"**, düğme **"Göster"**);
dönem satırı **"Dönem gg.aa.yyyy – gg.aa.yyyy · gg.aa.yyyy tarihli kayıtlarla."**; not
**"İstatistik kişisizdir: üye bazında bilgi, adlı sıralama ve konuya göre ödünç dağılımı
yoktur. Ödünç kaydı okunan kitabı göstermez."** Bölümler: **Koleksiyon** (bugünkü kayıtlarla;
"Katalogdaki eser" · "Nüshası elde bulunan eser" · "Elde bulunan nüsha" · "Rafta" · "Elde
bulunan kitap" · "Kayıt defterindeki nüsha" · "Danışma kaynağı" · "El yazması ve nadir eser";
tablolar "Kaynak türüne göre" · "Nüsha durumuna göre" · "Bölüme göre", bölümsüz nüsha
**"Bölümü yazılmamış"**) · **Edinim** ("Kazandırılan nüsha" — yalnız Md. 10/5 yolları ·
"Kayıt içi giriş"; tablo "Edinim yoluna göre") · **Dolaşım** ("Verilen ödünç" · "İade" ·
"Gecikmeyle iade edilen" · "Kayba dönüşen ödünç" · "Ödünç alan farklı üye" · "Şu an ödünçte" ·
"Şu an gecikmiş"; tablolar "Üye türüne göre" · "Sınıf düzeyine göre" · "Aylara göre") ·
**Teslim** · **Kayıp ve Hasar** (tablo "Kapanan dosyalar, çözüme göre") · **Ayıklama ve Devir**
(tablolar "Gerekçeye göre (Md. 12/1)" · "Taşınır Mal Yönetmeliği yoluna göre"). Eşik altındaki
hücre **"—"** yazılır; açıklaması tablonun altındadır ve yıl sonu raporunun notuyla aynı kuraldır
(k farklı üyeden azı; tamamlayıcı gizleme). "Aktif üye (bugün)" sütunu eşiksizdir; açıklama
bunu **"Aktif üye sayısı ödünç verisi değildir; eşiksiz yazılır."** diye söyler (F10 ekleri K1).

**Çok Okunanlar** (sekme). Düğme **"Yeniden hesapla"** (bildirim **"Çok okunanlar yeniden
hesaplandı."**; geri yükleme sürerken sunucunun iletisi); kartlar **Dönemin Çok Okunanları**
(seçici **"Dönem"**; Ağ Kataloğu vitrininde görünen liste) ve **Ayın Kitapları** (seçici
**"Ay"**; afişin kaynağı); rozetler **Sürüyor** · **Kapandı**; satır **"Son hesap:
gg.aa.yyyy"**; boş liste **"Henüz liste yok: en az N farklı üyenin ödünç aldığı eser
bulunmuyor."**; ay kartında belge **Ayın Kitapları afişi** ("Önizle" · "PDF'i indir").

**Okuma Ödülü** (sekme). Not **"İç kullanım"** (gövdesi: çıktı öğrenci adı taşır; asılmaz,
çoğaltılmaz, ağda ve velilerle paylaşılmaz; yalnız yönetici kipinde basılır); kart **Okuma
ödülü iç çıktısı** (belge adı); Uygulama Kılavuzu 7 alıntısı ve **"Öneridir, bağlayıcı
değildir"**; seçiciler **"Dönem"** · **"Sınıf"** (Bütün sınıflar · …); alan **"Sıra sayısı"**
(1-50, varsayılan 10); düğmeler "Önizle" · "PDF'i indir". Adlar ekranda listelenmez, yalnız
PDF'tedir.

| Kavram | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| İstatistik (`selectors_istatistik`) | **istatistik**; **kişisiz**; eşik altı **"—"** | okuma istatistiği, öğrenci istatistiği, başarı, okuma oranı | Üye bazında bilgi, şube × konu ve konuya göre ödünç kırılımı YOKTUR (profil yasağı). Üye türü ve sınıf düzeyi kırılımı k farklı üyenin altında "—" |
| Çok okunanlar (`kd_katalog_populer`) | **çok okunanlar**; kartlar **Dönemin Çok Okunanları** · **Ayın Kitapları**; **"Yeniden hesapla"**; rozetler **Sürüyor** · **Kapandı** | popüler, en çok ödünç alınanlar, okunma sayısı, dondurma, dondurulmuş liste | Eşik en az k FARKLI üyedir; tek üyenin tekrarı eseri listeye sokmaz. **Sayı gösterilmez, yalnız sıra.** Kapanan pencere son hâliyle kalır ("Kapandı") |
| Çok okunanlar eşiği (`popular_min_members`) | **"Çok okunanlar için en az üye sayısı"** (Kütüphane Politikası → Vitrin ve Saklama; 3-10, varsayılan 5) | kota, alt sınır (tek başına) | Aynı eşik istatistikte ve yıl sonu raporunda üye türü ve sınıf düzeyi kırılımına da uygulanır |
| E12 | belge **Ayın Kitapları afişi** (başlık **"AYIN KİTAPLARI"**) | ayın okuru, en çok okuyanlar panosu | Md. 15/1-ğ, Kılavuz 6.2. Sıra, kaynak adı ve yazar; sayı ve kişi bilgisi yok; afiş bir duyurudur, antet ve dayanak basılmaz |
| E20 | belge **Okuma ödülü iç çıktısı** (başlık **"OKUMA ÖDÜLÜ İÇ ÇIKTISI"**); ibare **"İç kullanım"** | okuma karnesi, okuma puanı, okuduğu kitaplar, okuma şampiyonu, başarı listesi | Kılavuz 7'nin ÖNERİSİdir, bağlayıcı değildir. Ölçüt iade edilmiş FARKLI eser; sayı ve okul no basılmaz; eşitler aynı sırada. Ağa, panoya, Ayın Kitapları afişine ve yıl sonu raporuna girmez |
| Md. 7/1 kartı (`kitap_esigi`) | kart **Kitap Sayısı 10.000'i Aştı**; **"Elde bulunan kitap: N."**; **"Kart yalnız bilgi verir."**; kayıp bildirilmiş nüsha varsa **"Kayıp bildirilmiş ama henüz kayıttan düşülmemiş N kitap bu sayıya dahildir."** | kütüphaneci atanmalıdır, zorunlu, eksiklik | Yalnız kaynak türü "Kitap" olan, kayıttan düşülmemiş ve devredilmemiş nüsha sayılır (danışma kitapları dahil). Sayım kuralı programındır, Yönetmelik "kitap"ı tanımlamaz. Yalnız bilgi; hüküm yorumlamaz |

### 4.17 Dökümler, dışa aktarım ve kişi dökümü ekranlarının ve belgelerinin adları

Kılavuz bu adları birebir kullanır (kaynak `frontend/src/modules/dokumler`, belgeler
`apps/kutuphane/{disa_aktarim,katalog_dokumu,tmy_dokumleri,kisi_dokumu}.py`, dışa aktarım şeması
`docs/disa-aktarim.md`). F10'da eklendi; hepsi yönetici kipindedir.

**Dökümler** (Raporlar sayfasının sekmesi, `?tab=dokumler`). Kartlar: **Dışa Aktarım** (düğme
**"Dışa aktarım dosyasını indir"**; bağlantı **"Dışa aktarım dosyasını içe aktar"** → İçe
Aktarma → Excel Aktarımı, "Dışa aktarım dosyası" seçili; altında **Üye Özeti** — kişisiz
sayılar) · **Alfabetik Katalog Dökümü**
(seçiciler **"Eksen"**: Kaynak adına göre · Yazar adına göre · Konuya göre; **"Bölüm"**: Bütün
bölümler · … · **"Bölümü yazılmamış"** — F10 düzeltme turu) · **Taşınır Kütüphane Defteri Dökümü** (seçici **"Kapsam"**: Bütün kayıt · "YYYY
yılında girenler") · **Yönetim Hesabı Cetveli Hazırlığı** (yıl sonu sayımları; basılamayan
satırda sunucunun gerekçesi) · **Kişi Dökümü** (alanlar **"Okul no"**, **"Ad soyad"**; düğme
**"Ara"**; boş sonuç **"Bu bilgiyle eşleşen kişi bulunamadı."**). Belge düğmeleri "Önizle" ·
"PDF'i indir" · "Excel'i indir".

İçe Aktarma → Excel Aktarımı'nda seçici **"İçe aktarılacak dosya"**: **Excel listesi** ·
**Dışa aktarım dosyası**; dışa aktarım dosyasında edinim kartının yerine **Dışa Aktarım
Dosyasını Uygula** durur. Dışa aktarım dosyası **"Excel listesi"** olarak içe aktarılmaz
(**"Bu dosya Kütüphane Defteri'nin dışa aktarım dosyası. …"**); geri yükleme yalnız **boş bir
kataloga** (**"Katalogda kayıtlı eser var. …"**) ve **bütün satırlarla** yapılır (**"Dosyada
aktarılamayan N satır var. …"**; ekranda **"N satır aktarılamıyor. …"**) — F10 düzeltme turu.

| Kavram | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| Dışa aktarım (U1, §8.4) | **dışa aktarım**, **dışa aktarım dosyası** (belge adı **Katalog dışa aktarımı**); sayfalar **Bilgi** · **Katalog** · **Bölümler** · **Numara Sayaçları** · **Üye Özeti** | yedek (bu anlamda), yedekleme, senkronizasyon, "Bakanlığa aktarım" | Kişisel veri içermez. Tam taşıma için **şifreli yedek**tir; dışa aktarım kataloğun kendisidir. Geri yüklemede barkod ve kayıt no korunur, **hiçbir numara yeniden kullanılmaz**; yalnız boş kataloga ve bütün satırlarla; "Ödünçte" ve "Sınıf kitaplığında" nüsha "Rafta" açılır; komisyon kararı bağışta "Bağış değerlendirme", öbür yollarda "Kaynak seçimi" olarak yeniden kurulur |
| Üye özeti | **Üye Özeti** (üye türüne ve şubeye göre aktif üye sayısı) | üye listesi, okuma istatistiği | Kişisizdir; ödünç verisi değildir. **Eşiksizdir** (27.09.2026 kullanıcı kararı, tasarım F10 ekleri K1): üyelik sayısı profil yasağının konusu sayılmaz; k eşiği ve tamamlayıcı gizleme yalnız ödünçten türeyen sayılara uygulanır. İstatistik ve E9'daki aktif üye sayısı da aynı kuralla eşiksizdir |
| E17 | belge **Alfabetik katalog dökümü**; başlık **"ALFABETİK KATALOG DÖKÜMÜ"**; eksenler **Kaynak adına göre** · **Yazar adına göre** · **Konuya göre** | kitap listesi, envanter | Md. 11/1; yazar ekseninde "Soyad, Ad" ve çok yazarlıda "vd."; **kurum yazarı** ("Millî Eğitim Bakanlığı", "Türk Dil Kurumu" — adı "Bakanlığı", "Kurumu", "Müdürlüğü", "Üniversitesi" gibi bir sözcükle biten) ters çevrilmez, adıyla sıralanır (F10 düzeltme turu); **"Yazarı belli olmayan"** · **"Konusu yazılmamış"** başlıkları sondadır; bölüm süzgecinde **"Bölümü yazılmamış"** |
| E11 | belgeler **Taşınır Kütüphane Defteri dökümü** (başlık **"TAŞINIR KÜTÜPHANE DEFTERİ DÖKÜMÜ"**) · **Yönetim hesabı cetveli hazırlığı** (başlık **"KÜTÜPHANE YÖNETİM HESABI CETVELİ HAZIRLIĞI"**, durum notu **"Sayım kurulunca onaylanan Taşınır Sayım ve Döküm Cetveline dayanır; resmî cetveller TKYS'dedir."**) | Kütüphane Defteri (tek başına), demirbaş defteri, yönetim hesabı cetveli (hazırlık olmadan) | Ciltletilmemiş süreli yayın deftere girmez (TMY 10/1-a-4, 15/4). Hazırlık yalnız yıl sonu işaretli ve onaylanmış sayımdan basılır; ret iletileri **"Yönetim hesabı cetveli hazırlığı yalnız yıl sonu sayımından basılır. …"** · **"Yönetim hesabı cetveli hazırlığı sayım onaylandıktan sonra basılır: …"** (dayanak zinciri 34/3-a → 32/9 → 32/7) · **"İptal edilmiş sayımdan yönetim hesabı cetveli hazırlığı basılmaz."**; iptal edilmiş sayım listelenmez |
| Yıl sonu sayımı (`StockTake.is_year_end`) | kutu **"Yıl sonu sayımı"**; işaretsiz sayım **ara sayım** | dönem sonu sayımı, kesin sayım | TMY 32/1'in iki sayımı. İşaretsiz sayımın eki **"Ara sayım — sayılar cetvele aktarılmaz"** başlığını alır; ara sayımın ekinde "Gelecek yıla devir", ona göre "Fark" ve cetvel sütununa ilişkin not YOKTUR, "Kayda göre yıl sonu" yerine **"Kayda göre, belgenin düzenlendiği gün (…)"** yazar. Bir mali yılın tek yıl sonu sayımı olur (**"YYYY mali yılının yıl sonu sayımı zaten var (…). …"**) |
| Kişi dökümü (KVKK md. 11) | belge **Kişi dökümü** (başlık **"KİŞİ DÖKÜMÜ"**, durum notu **"Kişisel veri içerir. Yalnız başvuru sahibine verilir."**); tablolar **ÜYELİK VE ÜYE KARTI** · **ÖDÜNÇ KAYDI** · **KAYIP VE HASAR DOSYALARI** · **ÖĞRETMENE TESLİM** | okuma geçmişi, okuduğu kitaplar, kişi raporu, kişi dosyası | Okul no kör indeksle TAM eşleşir; aynı numaralı birden çok kayıt ayrı adaydır, döküm SEÇİLEN kişinindir. Dosya kişisi tek kuraldır (önce üyelik, yoksa teslim alan öğretmen): öğrencinin üyeliğiyle açılan teslim dosyası öğretmenin dökümüne girmez. Kapsam notu serbest metinde adın aranmadığını söyler. İndirme adında kişi adı yoktur |
| Bakanlık sistemi kullanımda (A21) | ayar **"Bakanlık sistemi kullanımda"**; hatırlatmalar **"Okuldan ayrılan kişi için Bakanlık otomasyon sistemindeki kaydı da güncelleyin. …"** (Ayrılış Havuzu ve Kişiler ekranında "Ayrıldı olarak işaretle" onayı — F10 düzeltme turu) · **"İlişik ve iade işlemlerinde Bakanlık otomasyon sistemindeki kaydı da güncelleyin. …"** (İlişik Listesi) | "Bakanlık sistemine gönder", "eşitle", "entegrasyon" | Varsayılan kapalıdır; yalnız hatırlatma açar. Konum cümlesi: **"Kütüphane Defteri okulun kütüphane işlerini yürüttüğü yerel araçtır; Bakanlık otomasyon sistemine bağlanmaz ve o sistemin yerine geçmez."** |

### 4.18 Saklama ve anonimleştirme ekranının ve belge ibaresinin adları (F11)

Ekran **Ayarlar → Saklama** (`?tab=saklama`); kartları sırasıyla **Saklama ve
Anonimleştirme** · **Süresi Dolan Kayıtlar** (iki grup: **"Silinecek"** · **"Kişiyle bağı
koparılacak (kayıt kalır)"**; ad tabloları **"Kaydı silinecek kişiler"** · **"Yalnız üyelik kaydı
silinecek kişiler (kişi kaydı kalır)"**) · **Ne Kalır** · **Bedel Bekleyen Dosyalar** ·
**Son İşlem** (işlemden sonra şifreli yedek indirilmediyse USB uyarısı ve **"Ayarlar → Güvenlik'i
aç"**). Düğmeler **"Silinecek kişileri göster"** / **"Adları gizle"** · **"Onayla ve uygula"**; pencere
**"Saklama işlemi uygulansın mı?"** (alan **"Yönetici parolası"**, kutu **"Bu işlemin geri
alınamayacağını anladım"**, düğme **"Uygula"**). Süreler Kütüphane Politikası → **Vitrin ve
Saklama** bölümündedir; yeni alan **"Okuldan ayrılan kişinin kaydında saklama (yıl)"**.
**Ne Kalır** kartının maddeleri kılavuzun "Ne kalır" ara başlığıyla aynı sırayı izler (kişiyle
bağı koparılmış ödünç, dosya ve teslim kayıtları — belge no ya da dosya numarası arşivdeki asılla
eşleşebilir · verilmiş kart numarası yeniden verilmez, silinen üyeliğin kartı
**"iptal edilmiş kart"** · belgenin izi ve ibare · kapanmış çok okunanlar ve sonlandırılmış yıl
sonu raporu değişmez · bedel adımındaki dosya silinmez; F11 düzeltme turu D-20 — test iki
listeyi karşılaştırır); altındaki satır yedeklerde kalan kopyaları sayar (önceki veritabanı
dosyalarının kaçının 14 günden eski olduğu dahil: işlem onları siler, daha yenileri için elle
silme önerilir — 27.09.2026 kullanıcı kararı) ve kılavuzun **Saklama ve Anonimleştirme**
bölümüne gönderir (bölüm adı Başlık Düzeninde). **Son İşlem** kartı silinen güncelleme öncesi
yedek ve önceki veritabanı sayılarını yazar. Ad tablolarının sütunları
**"Ad soyad"** · **"Sınıf / üye türü"** · **"Ayrılış"** (kişi kaydı silinecekler) ya da
**"Üyeliğin sonu"** (yalnız üyelik kaydı silinecekler), öbür liste ekranlarıyla aynı; bu
tablolarda "Sınıf / görevi" yazılmaz (program personelin görevini tutmaz — V2-01; D-16 — aynı
düzeltme Kayıp/hasar tutanağının kişi satırında da yapıldı). Kılavuzun ara başlıkları: **Süreler** · **Ne kalır** · **Onay** · **Yedeklerde kalan
kopyalar** · **Resmî belgeler**; Yedek bölümünde **USB belleğe yedek hatırlatması** · **USB
bellekteki yedekler** · **Geri yükleme provası**.

| Kavram | Kullanılır | Kullanılmaz | Not |
|---|---|---|---|
| Anonimleştirme (`anonymized_at`, §6.4) | **anonimleştirme**, **"kişiyle bağı koparılır"**; belgede kişi alanı **"Anonimleştirildi"** | imha, arşivleme, maskeleme, silme (bu anlamda) | **Anonimleştirme ≠ silme**: kayıt kalır (sayım ve istatistik), yalnız kişiyle bağı koparılır, gerekçe ve açıklamaları temizlenir. **Silme** kaydın kendisini kaldırır (kişi kaydı, sona ermiş üyelik kaydı). Bağı koparılan kayıt için **"kişisel veri içermeyen"** ya da **"anonim hâle getirilir (md. 7/1)"** denmez: belge no ya da dosya numarası okul arşivindeki ıslak imzalı asılla eşleşebilir (KVKK 3/1-b; F11 düzeltme turu D-12, TB39) — metin "kişiyle bağı koparılır" der ve sınırı yazar. "İmha" yalnız imha tutanağı bağlamındadır (TMY 28/5, §4.14); okulun kendi yedek kopyaları için de "silme" denir |
| Saklama taraması ve onay | **süresi dolan kayıtlar**; **onay bekleme başlangıcı**; ileti **"Onay bekleme süresi (6 ay) doldu: …"** | otomatik silme, temizlik, çöp, KVKK imhası | Program her gün tarar, **kendiliğinden hiçbir şey silmez**; işlem yalnız yönetici parolasıyla onaylanır, geri alınamaz, tek seferdedir. Liste onay sırasında değiştiyse **"Saklama listesi siz onaylarken değişti; …"** ve hiçbir şey yazılmaz |
| Tetik öncesi yedek | adı `pre-anonim-<tarih>-<saat>` (kullanıcı metninde **"işlemden hemen önce alınan yedek"**) | anonim yedek, arşiv | 14 gün saklanır; işlem kendinden önce alınmış güncelleme öncesi yedekleri ve 14 günden eski önceki veritabanı dosyalarını siler |
| Önceki veritabanı (`db-onceki-<tarih>-<saat>.sqlite3`, `backup_restore`) | **"geri yüklemeden kalan önceki veritabanı dosyası"**; Son İşlem kartında **"Silinen önceki veritabanı: …"** | yedek (bu dosya için), eski DB, çöp | Geri yükleme mevcut veritabanını silmez, veri klasöründe bu adla (`-wal`/`-shm` eşleriyle) kenara alır. **Saklama işlemi, adındaki tarih işlem anından 14 günden eski olanları eşleriyle siler** (27.09.2026 kullanıcı kararı; günlük ve işlem öncesi yedeklerle aynı süre ve gerekçe: yakın tarihli geri yüklemenin dönüş yolu kalır). Daha yenileri kalır; metin elle silmeyi ("gerekmiyorlarsa okul müdürlüğünün kararıyla siz silin") yalnız onlar için önerir. Yaş dosya zamanından değil addaki tarihten okunur |
| Belge ibaresi (`BelgeIzi`, KM-12) | **"Anonimleştirilmiş kopya — ıslak imzalı asıl nüsha okul arşivindedir"** (tasarım §6.2 — birebir) | taslak, suret, sahte | Kişiyle bağı koparılmış kayıttan yeniden basılan E6 ve E15'in başında durur. Belge izi kişisizdir (tür, tarih, belge no ya da dosya numarası) |
| USB bellekteki yedeklerin kuralı (§6.4 "dış kopyalar okulun elindedir") | **"Önerilen düzen"**; **"okulun sorumluluğundadır: düzeni okul müdürlüğü belirler"** (Yönerge 10/5'in öznesi personeldir, atıf personelin cümlesine bağlanır — D-19); **silme** | imha kuralı, imha, zorunlu (öneri için), yasal saklama süresi | Kılavuzun Yedek bölümü ve `docs/kurulum.md` §6.3 aynı altı maddeyi yazar: İndirilenler'de kopya bırakmama · son iki yedek · saklama işleminden sonra yeni yedek ve öncekilerin silinmesi · görev devrinden sonra aynısı · belleği elden çıkarmadan önce silme · kayıp bellekte okul müdürlüğüne bildirim (KVKK 12/5'in bildirimini okul müdürlüğü değerlendirir). Sayılar programın önerisidir; metin okul müdürlüğünün başka bir düzen belirleyebileceğini söyler |

### 4.19 Güncelleme ekranının adları (F11)

Ekran **Ayarlar → Güncelleme** (`?tab=guncelleme`); kart **Uygulama Güncellemesi**. Düğmeler
**"Şimdi denetle"** (sürerken **"Denetleniyor…"**) · **"Doğrula ve indir"** (sürerken
**"İndiriliyor…"**; yalnız Windows'ta); kutular **Kurulu sürüm** · **Yayımlanan son sürüm**;
iletiler **"Uygulama güncel."** · **"Yeni sürüm hazır: …"** · snackbar **"Kurulum dosyası
doğrulanarak indirildi."**. Denetim düşünce sunucunun iletisi aynen gösterilir; GitHub'a
ulaşılamazsa ileti **"GitHub'a ulaşılamadı; okul ağında engellenmiş olabilir. Yeni sürümü
indir.okulapp.org'dan elle denetleyebilirsiniz."** (sunucu `updates.ULASILAMADI_MESAJI` ile
ön yüz `ULASILAMADI_METNI` birebir — test). Altında elle denetleme bağlantısı
**okulapp.org/kutuphane-defteri** (dış tarayıcıda açılır; dosyalar indir.okulapp.org'dan
iner). Pardus'ta indirme düğmesi yoktur; ekran paketin indirme sayfasından alınıp kurulduğunu
söyler.

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
- Yıl sonu kütüphane raporu kişisel veri içermez: üye bazında bilgi, adlı
  sıralama ve şube × konu kırılımı yoktur; eşiğin altındaki grup "—" yazılır ve
  basılan toplamdan çıkarılarak bulunamasın diye gerekirse bir grup daha gizlenir;
  imzada ad basılmaz. "Tespit edilen hususlar" serbest metindir ve program
  onu denetleyemez: ekran ve kılavuz oraya kişi adı yazılmamasını söyler.
- Sayım verisi kişisizdir: sayım kaleminde, okutma iletisinde, ilerlemede ve Sayım
  tutanağında (PDF ve Excel) ödünç alanın ve teslim alanın kimliği yoktur; ödünçteki ve
  teslimdeki kitaplar yalnız sayıyla gösterilir (fazla ve noksan sayfaları Varlık İşlem Fişine
  eklenip muhasebe birimine gider — TMY 10/1-g, 32/8). Tutanakta geçen adlar yalnız sayım
  kurulu ile durduran ve onaylayan harcama yetkilileridir (şifreli alanlardan, yalnız belgenin
  kendisine çözülür). Yerinde sayılan sınıf kitaplığının şube etiketi kişisel veri değildir.
  Üye kartı sayımda okutulursa reddedilir ve numarası kaydedilmez.
- Ayıklama belgelerinde ve nadir eserler listesinde geçen adlar yalnız
  komisyon başkanı, katılımcılar, TMY komisyonu üyeleri ve harcama
  yetkilisidir (şifreli alanlardan, yalnız belgenin kendisine çözülür);
  kalemlerde üye ya da ödünç bilgisi yoktur. Devralacak kurum okulun ya da
  kurumun adıdır, kişi adı yazılmaz. Bağış ön kayıt listesi ve Bağış
  değerlendirme sonucu yalnız bağışçının adını taşır (aynı biçimde şifreli alandan).
