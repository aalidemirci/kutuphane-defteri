# docs/mevzuat — Kütüphane Defteri'nin mevzuat kaynağı

Bu klasör, programın ve tasarım belgesinin dayandığı mevzuatın **birebir
metnini** tutar. Kural (kardeş projelerden gelir): **her madde atfı buradaki
metinden doğrulanır.** Yeni bir atıf eklenecekse önce metin bu klasöre girer,
sonra atıf yazılır. Madde numarası bellekten ya da ikincil kaynaktan
yazılmaz.

Metinler özetlenmez, düzeltilmez. `(Değişik:…)`, `(Mülga:…)`, `(Ek:…)`
şerhleri kaynaktaki gibi kalır. Mülga hüküm yoktur, atıf yapılmaz.

## 1. Dosyalar

| Dosya | Kapsam | Nereden alındı | Ne için |
|---|---|---|---|
| `meb-okul-kutuphaneleri-yonetmeligi.md` | tam metin (RG 23.11.2024/32731) | OYS deposu `data/mevzuat/` (birebir kopya) | Programın asıl dayanağı: ödünç, üyelik, kart, süre, sayı sınırı, kataloglama, ayıklama |
| `meb-okul-kutuphaneleri-yonetmeligi-uygulama-kilavuzu.md` | tam metin (MEB, Ankara 2025) | OYS deposu `data/mevzuat/` (birebir kopya) | Yıl sonu raporu, etkinlik ve okuma ödülü önerileri. **Bağlayıcı değildir**, Yönetmeliğin uygulama rehberidir |
| `meb-bilgi-ve-sistem-guvenligi-yonergesi.md` | tam metin (OLUR 31.05.2018) | evrakmotoru deposu `mevzuat/` (birebir kopya) | Ağ kataloğunun konumu, BTR bilgi notu, demirbaş bilgisayar şartı, AI köprüsü uyarısı |
| `6698-kvkk.md` | tam metin (RG 07.04.2016/29677, 7499 sk. değişikliğiyle) | evrakmotoru deposu `mevzuat/` (birebir kopya) | Hukuki sebep, özel nitelikli veri sınırı, silme/anonimleştirme, aydınlatma, ilgili kişi hakları, veri güvenliği |
| `kvkk-aydinlatma-yukumlulugu-tebligi.md` | tam metin (RG 10.03.2018/30356) | evrakmotoru deposu `mevzuat/` (birebir kopya) | Kütüphane aydınlatma metninin usulü |
| `tasinir-mal-yonetmeligi.md` | tam metin (RG 10.10.2024/32688) | evrakmotoru deposu `mevzuat/` (birebir kopya) | Taşınır Kütüphane Defteri dökümü, sayım, kayıttan düşme, devir, yönetim hesabı |
| `6098-turk-borclar-kanunu-md92-93.md` | md. 92-93 alıntısı | evrakmotoru deposundaki tam metinden, satırlar birebir | İade tarihinin tatile rastlaması (kıyas dayanağı) |
| `ortaogretim-kurumlari-yonetmeligi-ilgili-maddeler.md` | md. 94/1, 95/1-2, 96/3, 100, 157/2-h, 164/1-g alıntısı | OYS deposundaki tam metinden, satırlar birebir | Kütüphane memuru, dayanıklı taşınırlar listesi, kitabı eksik vermenin disiplin karşılığı |

**Kopyalama notları.**
- Tam metin dosyalarının üst bilgisi (`kaynak`, `resmi-gazete`, `son-guncelleme`)
  kaynaktaki gibidir. Kaynak depoya ve resmî adrese oradan bakılır.
- Alıntı dosyalarında üst bilgi kaynaktan aynen alındı. Yalnız `kapsam` alanı
  "alıntı" diye değiştirildi, `alinti-kaynagi` alanı eklendi.
- OYS'den gelen dosyalardaki "`data/mevzuat-notlari/`" gibi bağlantılar OYS
  deposuna aittir. O klasör bu depoda yoktur.
- OKY'nin OYS'deki kopyası 03.07.2026 değişikliğini (RG 33299) içermiyor.
  Alıntılanan maddeler evrakmotoru'ndaki güncel tam metinle karşılaştırıldı ve
  aynı çıktı; o değişiklik bu maddelere dokunmuyor.

## 2. Eksik metin

| Metin | Durum | Beklenen kullanım |
|---|---|---|
| Kişisel Verilerin Silinmesi, Yok Edilmesi veya Anonim Hâle Getirilmesi Hakkında Yönetmelik | **Eksik — resmî kaynaktan (mevzuat.gov.tr) birebir alınacak.** Kardeş depoların hiçbirinde yok | Saklama ve anonimleştirme (tasarım §6.4). Onay beklemenin azami süresi (6 ay) bu Yönetmeliğin periyodik imha hükmüne göre yeniden ayarlanır. Metin gelmeden bu Yönetmeliğe madde atfı yazılmaz |

## 3. Atıf haritası

Kısaltmalar: **Yön.** Okul Kütüphaneleri Yönetmeliği · **Kılavuz** Uygulama
Kılavuzu · **Yönerge** Bilgi ve Sistem Güvenliği Yönergesi · **TMY** Taşınır
Mal Yönetmeliği · **OKY** Ortaöğretim Kurumları Yönetmeliği. Bölüm numaraları
[genel tasarım](../tasarim/2026-09-21-genel-tasarim.md) belgesine aittir.

### 3.1 Okul Kütüphaneleri Yönetmeliği ve Kılavuz

| Tasarımdaki yer | Atıf | Hüküm (kısaca) |
|---|---|---|
| §3 otomasyon şartı, konum dili | Yön. 9/2 · 11/2 · 16/2 · 16/3 · 17 · 18 · 20-23 | İşlemler "Bakanlıkça belirlenen" ya da "kütüphane otomasyon sistemi" üzerinden yürütülür. Program kendini bu sistemin yerine koymaz, "yerel araç" der |
| §3 sınıflama, §5.4 `/konular` | Yön. 8/1-a · 11/1 | Bakanlıkça belirlenen kataloglama ve sınıflama sistemi; katalog yazar, eser adı ve konuya göre alfabetik |
| §3 KVKK dayanağı | Yön. 8/1-f · 16/2 · 16/3 · 18 · 23 | Ödünç kaydı, iade takibi, ayrılışta üyeliğin sonlanması ve iadenin sağlanması |
| §3 okul türü, §9-9 (kılavuzun Kayıp, Hasar ve Onarım bölümü) | Yön. 19 | Kayıp ve hasar bedeli **yalnız ortaöğretimde** |
| §3 okul türü, U11 | Yön. 4/1-i · 5/1 | İlkokulda sınıf kitaplığı |
| §4.4 terim | Yön. 4/1-e, f · 7/1 · 20 | Kütüphaneci, kütüphaneden sorumlu öğretmen, "kütüphane yöneticisi"; 10.000 kitap eşiği; yardımcı memur |
| §6.2 `Section` | Yön. 4/1-a · 6/1 | Kütüphane bölümü (Yönetmelikte "alan") |
| §6.2 `LibraryPolicy`, §9-4 | Yön. 18 | Süre **on beş gün, sabit**; öğrenciye en fazla 3, öğretmene en fazla 5 |
| §8.3 ilişik ve yıl sonu, E5 (kılavuzun İlişik Listesi ve Yıl Sonu ve Yıl Başı bölümleri) | Yön. 18/1 | Okuldan ayrılma sebebiyle üyelik sonlanınca "alınan ödünç kitabın kütüphaneye iadesi sağlanır"; "Kütüphaneden ilişiği yoktur" belgesi bu hükmün uygulanmasına yöneliktir, karne ya da diploma ön koşulu değildir (§4) |
| §9-1 | Yön. 13/1 · 16/1 · 17/1 | Doğal kullanıcı öğrenci ve öğretmen; diğer personel yalnız "kullanıcı hizmetleri"nde sayılır. Diğer personele ödünç Yönetmelikte düzenlenmemiştir, programda müdürlük kararıyla açılan **ihtiyat kuralıdır** |
| §9-2 | Yön. 17/1 | Üyelik isteğe bağlıdır ("üye olmak isteyen") |
| §9-3, §8.1 | Yön. 14/1-a · 16/1 a-c | Danışma kaynağı (ders kitabı dahil), piyasada mevcudu olmayan eser ve süreli yayın ödünç verilmez |
| §4.4 kartsız ödünç (U12) | Yön. 23/1-a | Kartın görevliye verilmesi; kartsız ödünç bundan sapma olarak kayda geçer |
| §9-10 sayım | Yön. 23/1-c | İade otomasyon üzerinden alınır; iade hiçbir durumda kilitlenmez |
| §10 E2, E5 konum kalıbı | Yön. 20 | Kullanıcı kartı; programın kartı onun "yerel karşılığı"dır |
| §10 E7 ayıklama (kılavuzun Ayıklama ve Nadir Eserler bölümü) | Yön. 12/1 a-ç · 10/1 · 10/4 · 4/1-ı | Ayıklama gerekçeleri; 10/1-b'ye uymayan kaynak **devredilir** (düzeye uygunsuzluğun — 12/1-c — da devre bağlanması ve devrin "yalnız" bu gerekçeyle yapılması programın kuralıdır, Yönetmeliğe yüklenmez); 10/4'e aykırı kitap okul kütüphanelerinde bulundurulamaz; komisyonun başkanı (10/1) ve bileşimi (4/1-ı) |
| §10 E8 (aynı bölüm) | Yön. 12/2 · 4/1-c | El yazmaları ve nadir eserler listesi Genel Müdürlüğe (Destek Hizmetleri Genel Müdürlüğü). Nadir eserin ayıklanamaması programın kuralıdır (D14); 12/2 yalnız listenin gönderilmesini düzenler |
| §10 E9 (kılavuzun Yıl Sonu Raporu bölümü) | Yön. 12/1 · 10/5 · Kılavuz 2.4 | Ders yılı sonu raporu; "kazandırılan" yalnız 10/5 yollarıdır (programa aktarım ve sayım fazlası kayıt içi giriş). "Kazandırılan, ayıklanan … raporlanır" cümlesi Kılavuz 2.4'ündür, Md. 12/1'e atfedilmez |
| §10 E12 | Yön. 15/1-ğ · Kılavuz 6.2 | Çok okunan kitaplar listesinin ilanı |
| §10 E16, §6.2 bağış | Yön. 10/3 · Kılavuz 2.3.3 | Bağış komisyonca **değerlendirilir** (10/3); uygun bulunan kitabın kütüphaneye kazandırılması Kılavuz 2.3.3'tür |
| §10 E20, §3 profil yasağı | Kılavuz 7 | Okuma ödülü **önerisi**; bağlayıcı değil, iç çıktı |
| F10 istatistik | Yön. 7/1 | 10.000 kitap eşiği |

### 3.2 Taşınır Mal Yönetmeliği

| Tasarımdaki yer | Atıf | Hüküm (kısaca) |
|---|---|---|
| §3 TMY, §9-10 | TMY 13/1 · 23/4 | Ödünç TMY anlamında giriş ya da çıkış değildir; kütüphane materyali "ödünç takip sistemleri ile takip edilir" |
| §3, §8.4, E11 | TMY 9/1-ç · 10/1-a-4 · 15/4 | Taşınır Kütüphane Defteri; süreli yayına VİF düzenlenmez, ciltletildikten sonra kayda alınır |
| E11 | TMY 34/2-c · 34/3-a | Müze/Kütüphane Yönetim Hesabı Cetveli |
| §9-10, E10 | TMY 32/3 | Giriş ve çıkışların durdurulması **isteğe bağlıdır** (kurul talebi + harcama yetkilisi), "hizmetin aksamaması" kaydıyla. İkinci cümle ("Sayım yapılırken gerekli önlemlerin alınması, sayım kurulunun görev ve sorumluluğu altındadır") "sayım için hizmet arası"nın anılabilecek en uzak dayanağıdır; hizmet arası okul kararıdır (§4) |
| F9 sayım — kurul, zaman, iki seçenek (kılavuzun Sayım bölümü; tasarım F9 ekleri) | TMY 32/1 · 32/2 · 32/3 · 13/1 · 23/4 · Yön. 23/1-c | Sayım yıl sonlarında ve harcama yetkilisinin gerekli gördüğü durum ve zamanlarda yapılır (32/1). Kurul: harcama yetkilisinin ya da görevlendireceği kişinin başkanlığında, taşınır kayıt yetkilisinin de katılımıyla en az üç kişi (32/2 — program başkan + taşınır kayıt yetkilisi + en az bir üye ister). Ödünç TMY'de giriş-çıkış değildir (13/1, 23/4): 32/3 durdurması ödüncü ve iadeyi kapsamaz; iade hiçbir durumda durmaz (Yön. 23/1-c) |
| F9 sayım — sayılış ve sonuç (kılavuzun Sayım bölümü; E10) | TMY 32/5 · 32/6 · 32/7 · 27/1 · 27/3 · 10/1-a · 10/1-e · 17/1 | Sınıf kitaplığı yerinde sayılır: 32/5 birinci cümleye **kıyasen** (ortak kullanım alanı, Dayanıklı Taşınırlar Listesi — 23/6'ya kıyasen); şubeyi sayılmadan **kayda göre** almanın dayanağı YOKTUR (kıyasın sonucu "sayılır"dır; "sayım yapılmaksızın" yalnız ikinci cümlededir ve kamu görevlilerine teslim belgesiyle verilen taşınır içindir) — seçenek kaldırıldı, toplanamayan şube nüshası yerinde aranır (F9 ekleri K3, 25.09.2026); onarımdaki nüsha kayda göre alınır ya da sayımdan önce geri alınır: TMY'de hüküm yok, sayım kurulunun kararı (K2 — §4); öğretmene teslim kayda göre: 32/5 ikinci cümle (Taşınır Teslim Belgesi varsa) ya da 32/5'e kıyasen (23/4); ödünçteki nüsha "32/5'e kıyasen; 23/4". Farklı çıkanın sayımı bir kez daha tekrarlanır (32/6 — program yalnız noksanı yeniden aratır). Noksan için Kayıttan Düşme Teklif ve Onay Tutanağı ve VİF, fazla için VİF (32/7); 27/1 "sayımda noksan çıkan" ve "kullanılamaz hâle gelen" taşınırı sayar (hasar önerisinin düşülmesi); kasıt, kusur, ihmal ya da tedbirsizliği harcama yetkilisi değerlendirir (27/3). Durumu belgeleyen tutanak varsa komisyonsuz onay (10/1-e — tutanağın o belge sayılması harcama yetkilisinin takdiridir, metinler böyle yazar). Onay tarihi tamamlanma gününden önce olamaz: VİF dayanağından önceki tarihi taşıyamaz (10/1-a). Sayım fazlası VİF ile kayda alınır; değer son bir yıldaki aynı nitelikte girişin değeri, yoksa değer tespit komisyonununki (17/1 — program değer yazmaz) |
| F9 E10 — kişisel veri ve ek | TMY 10/1-g · 32/8 · 32/9 · 34/1 · 10/1-ğ · 32/1 | Sayım Tutanağının fazla/noksan sayfaları VİF'e bağlanır ve muhasebe birimine gider (10/1-g, 32/8): tutanakta ödünç alanın ve teslim alanın kimliği yoktur. Taşınır Sayım ve Döküm Cetvelini sayım kurulu düzenler, kurul ile taşınır kayıt yetkilisi imzalar (32/9) — program üretmez, TKYS'dedir; ekte 34/1'in dört büyüklüğü ("Gelecek Yıla Devir" = "Sayımda Bulunan Miktar", 10/1-ğ; sayımda bulunup onayda 27/1 ile düşülen sayımın kendi çıkışıdır — ekte devirden çıkarılır ve ayrı satırda yazılır, F9 ekleri madde 25 a). Cetvel "yıl sonu hesaplarına ilişkin işlemlerinde" düzenlenir (10/1-ğ) ve kayıt yetkilisinin yıl sonu hesabını oluşturur (32/9); 32/1 yıl sonu sayımını harcama yetkilisinin gerekli gördüğü sayımdan ayırır — ekin ara sayım notu buna dayanır (F9 düzeltme turu) |
| §9-11, E15 (kılavuzun Sınıf Kitaplığına ve Öğretmene Teslim bölümü) | TMY 32/5 · 23/6 | Ortak kullanım alanı sayımı ve Dayanıklı Taşınırlar Listesi; kişilere verilen miktar (kıyasen) |
| E10 | TMY 32/7 · 32/8 · 32/9 · 10/1-g | Noksan düşüm teklifi, belgelerin muhasebe birimine gidişi, Sayım ve Döküm Cetveli |
| E7 (kılavuzun Ayıklama ve Nadir Eserler bölümü) | TMY 5/8 · 10/1-a · 10/1-e · 24/1 · 24/2 · 27/1 · 27/3 · 28 (1, 3, 4, 5, 7, 8) · 31 | Kayıttan düşme, komisyon (28/1: biri işin uzmanı), imha tutanağı (kalem düzeyinde), ekonomik değeri olan hurda (28/8), devir. 10/1-e: "durumu belgeleyen tutanak" varsa komisyonsuz onay — Ayıklama tutanağının bu belge sayılması yorumdur, metinler harcama yetkilisinin takdiri olarak yazar. 10/1-a: VİF dayanağından önceki tarihi taşıyamaz (onay, gönderim ve bağış edinimi karardan önce olamaz; karar tarihi sonradan onlardan sonraya alınamaz) |
| §6.2 bağış, Bağış değerlendirme sonucu (kılavuzun Katalog ve Ayıklama bölümleri; tasarım F8 ekleri 13) | TMY 16/1 · 13/2-c · 10/1 | Bağış taşınır kayıt yetkilisince Varlık İşlem Fişiyle kayda alınır, bir nüshası bağışçıya verilir (16/1); programın kataloglaması taşınır kaydı değildir. Kayda esas değer bağışçının belgeyle belirttiği değer, yoksa değer tespit komisyonunun belirlediği değerdir (13/2-c — "Birim fiyat" yardımı ve sonucun notu). 10/1'in belge listesinde "bağış kabul tutanağı" yoktur |
| §9-9 bulunan kitap (tasarım F8 ekleri 14) | Yön. 19/1 · TMY 17 | Md. 19/1 bedelden sonra bulunmayı düzenlemez; "kaydı silinerek" kayıttan düşmeyle yerine gelir. Kayıttan düşülmüş nüshanın bulunması sayım fazlası gibi girişe kıyasen yapılır (TMY 17) |
| Kayıp ve hasar önerisinin kayıttan düşülmesi (F9; tasarım F8 ekleri 34) | TMY 27/1 · 10/1-e · Yön. 12/1 | Md. 12/1'in bentleri kaybı ve hasarı saymaz; yok olan ya da kullanılamaz hâle gelen taşınır durumu belgeleyen tutanakla (E6) komisyonsuz, harcama yetkilisi onayıyla düşülür (10/1-e) |
| A8 kararı (tasarım F8 ekleri 13 — kullanıcı kararı 25.09.2026: cetvel üretilmez, E10 ekinde 34/1 büyüklükleri) | TMY 4/1-b · 10/1-ğ · 10/2 · 32/4 · 32/6 · 32/9 · 34/1 · 34/2-b · 34/3-a | "Bakanlık" TMY'de Hazine ve Maliye Bakanlığıdır (4/1-b); cetvel biçimi onundur (10/2). Sayım Tutanağı sütunları (32/4, 32/6) ile cetvelin büyüklükleri (34/1: önceki yıldan devir, yıl içinde giren, çıkan, ertesi yıla devir) ayrıdır; "Gelecek Yıla Devir" = "Sayımda Bulunan Miktar" (10/1-ğ) |

### 3.3 Bilgi ve Sistem Güvenliği Yönergesi

| Tasarımdaki yer | Atıf | Hüküm (kısaca) |
|---|---|---|
| §3, §5.9 BTR bilgi notu | Yönerge 11/7 | "Aktif ağ cihazı" sistem yöneticisinin bilgisi dışında eklenemez; dinlenen port bu hükme ancak ihtiyatlı yorumla girer |
| §3 U10 | Yönerge 4/1-s | "Sistem yöneticisi" tanımı. Okul BTR'si ve müdür bu tanıma girmez; U10 bunu bilerek BTR'nin bilgisiyle yetinir |
| §3, §5.9, E3 | Yönerge 5/11 · 11/16 · 11/22 | Port ve hizmet açma; erişim hakkının yetkisiz kişiye verilmemesi |
| §5.6 IP değişimi (kılavuzun Ağ Kataloğu bölümü, `docs/kurulum.md` §8.3) | Yönerge 11/6 | Bilgisayara tahsis edilen IP ve MAC adresi yalnız Bakanlıkça yetkilendirilmiş kişilerce değiştirilir: sabit adres BTR aracılığıyla (DHCP'de) ayrılır ya da yetkili birimden istenir; kütüphane yöneticisi adresi elle değiştirmez |
| §3 | Yönerge 11/9 · 11/20-21 · 11/25 · 14/3 | Uzaktan erişim (yönetim erişimi); erişim noktası, DHCP, DNS, proxy yok; veri toplayan form yok; internet sitesi bağlamı |
| §3, sihirbaz | Yönerge 11/8 · 11/23 | Program yalnız kurum demirbaşı bilgisayara kurulur |
| §8.2 AI köprüsü | Yönerge 11/23 · 11/3-h, ı | Veriyi dış hizmete taşıma; asıl yol Excel'dir |
| §3, §8.5 ISBN künye getirme | Yönerge 5/8 · 6/7 | **Kişisel veri paylaşımı yasağını kuran hükümler bunlardır.** 5/8 öğretmen, öğrenci ve veliye ait bilgilerin 3. şahıslarla paylaşılmasını yasaklar; 6/7 gizlilik içeren bilgi ve kişisel veri için aynısını söyler. **11/8 DEĞİL** — 11/8 kişisel bilişim kaynaklarıyla ilgilidir ve bu depoda demirbaş bilgisayar bağlamında kullanılır (yukarıdaki satır). Künye sorgusunda dışarı yalnız normalize ISBN çıkar |
| §8.5 ISBN künye getirme | Yönerge 11/23 · 11/3-h | **Çatışmaz:** 11/23 dışarı veri aktarımını yasaklar, ISBN sorgusu veri çıkarmaz, getirir. 11/3-h "resmî işlemler dışındaki" erişimi yasaklar; kataloglama Yönetmelik md. 8/1-a ile kurulmuş resmî bir iştir |
| §8.5, §5.9 E3 | Yönerge 11/12 · 11/19 · 11/22 | Operasyonel engel: kategorisiz adrese erişim izni verilmez, talep Yardım Masası'ndan açılır (11/12) · MEBNET'te SSL denetimli proxy ve MEB kök sertifikası (11/19) · port önceliği 21/80/443 (11/22), Bakanlık ucu 210 portundadır |
| §8.5 çevrimdışı yol | Yönerge 11/18 · 10/4 · 10/5 | Kurum bilgisayarına cep telefonu, mobil modem ya da kişisel erişim noktası bağlanamaz: çevrimdışı yol **ayrı cihaz** demektir. Dosya taşımada taşınabilir bellek kuralları |

### 3.4 KVKK ve Aydınlatma Tebliği

| Tasarımdaki yer | Atıf | Hüküm (kısaca) |
|---|---|---|
| §3 dayanak | KVKK 5/2-ç | Hukuki yükümlülük |
| §3 profil yasağı | KVKK 6 · 6/3 | Özel nitelikli veri; 6/3'te genel bir hukuki yükümlülük bendi yoktur. Ödünç verisinin md. 6'ya kaymaması için profil yasağı |
| §3 aydınlatma metni (E13) | KVKK 10/1 · Aydınlatma Tebliği | Aydınlatmanın asgari unsurları ve usulü |
| §8.5 ISBN künye getirme | KVKK 3/1-d · 10 · 9 | Kişisel veri "gerçek kişiye ilişkin"dir (3/1-d); dışarı çıkan ISBN esere aittir, bu yüzden kişisel veri işlenmez. Md. 10 aydınlatma yükümlülüğü kişisel verinin **elde edilmesine** bağlı olduğu için **doğmaz — E13'e satır eklenmez**; md. 9 (yurt dışına aktarım) tetiklenmez |
| §8.4 kişi dökümü, E13 | KVKK 11 | İlgili kişinin hakları |
| §6.4 saklama | KVKK 4/2 · 7 | Amaçla sınırlılık; sebep ortadan kalkınca silme, yok etme ya da anonimleştirme. Ayrıntılı usul için eksik Yönetmeliğe bakın (§2) |
| E19 masa kartı | KVKK 12/1 | Veri güvenliği önlemleri (görevli öğrencinin bilgilendirilmesi) |

### 3.5 TBK ve OKY

| Tasarımdaki yer | Atıf | Hüküm (kısaca) |
|---|---|---|
| §9-5 iade tarihi | TBK 92/1 | Gün olarak belirlenmiş süre ilk gün sayılmadan işler: iade tarihi `bugün + 15` |
| §9-5 iade tarihi | TBK 93 | Son gün kanunen tatile rastlarsa izleyen ilk güne geçer. Yön. 18'de hüküm olmadığı için **kıyasen** uygulanır |
| §9-9 kayıp ve hasar (kılavuzun Kayıp, Hasar ve Onarım bölümü) | OKY 164/1-g | Kütüphaneden alınan kitabı eksik vermek ya da kötü kullanmak kınama konusudur. Program disiplin sürecini **başlatmaz** |
| §9-11 teslim, E15 | OKY 96/3 | Okulun bütün bölümlerinde dayanıklı taşınırlar listesi |
| Bağlam | OKY 94/1-b · 95/2 · 100 · 157/2-h | Kütüphane memuru; okulda kütüphane bulunması; kütüphanenin Yönetmeliğe göre işletilmesi; öğrenciden kitapları koruması beklenir |

## 4. Dayanağı olmayan kurallar (bilerek)

Aşağıdaki kurallar programın ya da okulun tercihidir. Kullanıcı metninde
mevzuat hükmü gibi sunulmaz:

- **Ara tatil ve yarıyılda iade tarihinin kaydırılması** (tasarım §9-5, A23).
  Ara tatil ve yarıyıl kanunen tatil günü değildir, TBK 93 kapsamına girmez.
  Kaydırma okulun tercihidir ve ayarla kapatılabilir.
- **İdari izin ve "diğer" kapalı günlerde iade tarihinin kaydırılması**
  (tasarım §6.1 Holiday `OTHER`, §9-5). İdari izin kanunen tatil günü
  değildir, TBK 93 kapsamına girmez. Kütüphane o gün kapalı olduğu için iade
  alınamaz; kaydırma programın kuralıdır ve her zaman uygulanır. Kullanıcı
  metninde TBK 93 kıyası altında anılmaz.
- **Diğer personele ödünç için müdürlük kararı şartı ve sayı sınırı**
  (tasarım §6.2, §9-1). Yönetmelik diğer personele ödüncü düzenlemez.
- **"Sayım için hizmet arası"** (tasarım §9-10). Yeni ödüncü ve yeni teslimi
  durduran okul kararıdır (teslim — F9 ekleri madde 27, 25.09.2026 kullanıcı
  kararı), TMY'ye dayandırılmaz; en fazla 32/3'ün ikinci cümlesi anılabilir.
- **Onarımdaki nüshanın sayımda kayda göre alınması** (tasarım F9 ekleri K2).
  TMY'de onarıma gönderilmiş taşınırın sayımına ilişkin hüküm yoktur: onarım
  bakım yükümlülüğü (5/3), esaslı onarımın değer artışı ve VİF'siz yedek parça
  (10/1-a), iç imkânla onarımın iş talep belgesi (10/1-c), değer artırıcı
  harcamanın dışında kalan bakım-onarım (14/1) ve binayla teslim alınan taşınır
  (15/5) bağlamında geçer; md. 32'nin hiçbir fıkrası onarımı anmaz. Seçim sayım
  kurulunun kararı olarak yazılır, 32/5 atfedilmez.
- **Programa aktarımın sayım sırasında kapalı tutulması** (tasarım F9 ekleri
  K4). Mevcut koleksiyonun programa aktarımı taşınır girişi değildir (13/1'in
  giriş hâllerinden değildir); TMY 32/3 durdurması süresince kapalı tutulması
  programın kuralıdır ve ret iletisi TMY'ye dayandırılmaz.
- **"İlişiği yoktur" belgesi** (E5) karne ya da diploma için ön koşul diye
  sunulmaz; Yönetmelikte yalnız "iadesi sağlanır" hükmü vardır (md. 18).

## 5. Bilinen tuhaflıklar

- **OKY md. 100** hâlâ 22/8/2001 tarihli (mülga) Okul Kütüphaneleri
  Yönetmeliğine gönderme yapar. Yürürlükteki metin 2024 Yönetmeliğidir
  (Yön. 25). Kütüphane için OKY 100'e değil, doğrudan 2024 Yönetmeliğine atıf
  yapılır.
- **Sınıflama sistemi.** 2024 Yönetmeliği sınıflama sistemini adlandırmaz
  (8/1-a, 11/1: "Bakanlıkça belirlenen"). Dewey ve AAKK II adları mülga 2001
  metnindeydi. Program Dewey'i fiilî standart olarak kullanır, sınıflama kodu
  serbest alandır (tasarım §3, A19).
- **Kılavuz bağlayıcı değildir.** Kılavuzdaki okuma ödülü ve raporlama
  maddeleri "-bilir/-abilir" kipindedir; profil yasağı (tasarım §3) Kılavuz 7'nin
  önerilerinden önce gelir.
