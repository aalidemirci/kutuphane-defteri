# Dışa Aktarım Dosyası — Şema (sürüm v1)

Kütüphane Defteri, okulun kütüphane işlerini yürüttüğü yerel araçtır. Kataloğunuzu
programın dışına her zaman **dışa aktarım dosyasıyla** çıkarabilirsiniz: Bakanlık
otomasyon sistemine ya da başka bir araca geçerken elinizde kitap kitap, nüsha nüsha
bir liste olsun diye. Aynı dosya, boş bir kuruluma **geri de yüklenir**: barkodlar ve
kayıt numaraları korunur, hiçbir numara yeniden kullanılmaz.

Bu belge dosyanın **tek ve sürümlü şemasıdır**. Sütunların sırası, başlığı ve anlamı
buradaki gibidir; program dosyayı bu şemaya göre üretir ve okur.

## Dosyayı nereden alırım?

Programda **Raporlar** sayfasının **Dökümler** bölümündeki **Dışa Aktarım** kartında
**Dışa aktarım dosyasını indir** düğmesine basın. Dosyanın adı indirildiği günün
tarihini taşır (ör. `Katalog-dışa-aktarımı_26.09.2026.xlsx`). Bu iş yalnız yönetici
kipinde yapılır.

## Kişisel veri yoktur

Dosyaya **üye, ödünç, teslim, kayıp/hasar kaydı** girmez. **Bağışçının adı** (edinimin
kaynak notu) ve **komisyon üyelerinin adları** da girmez; komisyon kararının yalnız
tarihi ve sayısı yazılır. **Üye Özeti** sayfası kişisiz sayılardır: üye türüne ve şubeye
göre aktif üye sayısı. Üyelik sayısı ödünç verisi olmadığı için eşiksizdir (27.09.2026
kullanıcı kararı); küçük bir şubenin sayısı da yazılır. Dosyayı başkasına verirken yine de
okulun kararıyla verin.

## Sayfalar

| Sayfa | İçerik |
|---|---|
| **Bilgi** | Dosya türü (“Kütüphane Defteri dışa aktarım dosyası”), şema sürümü (`v1`), dışa aktarım tarihi, okulun adı, eser ve nüsha sayıları, kısa açıklamalar. Program dosyayı bu sayfadan tanır. |
| **Katalog** | Kataloğun kendisi: her nüsha bir satır. |
| **Bölümler** | Bölüm listesi: ad, DOS aralığı başı ve sonu, kısa tarif, sıra. |
| **Numara Sayaçları** | Her yıl için verilmiş son numara. Silinmiş nüshaların ve boş barkod aralığında ayrılmış numaraların da ötesindedir. |
| **Üye Özeti** | Üye türüne ve şubeye göre aktif üye sayısı (kişisiz). Geri yüklemede okunmaz. |

## Katalog sayfası

**Her nüsha bir satırdır.** Aynı **Eser No**'yu taşıyan satırlar aynı eserin
nüshalarıdır; eserin künyesi (kaynak adı, yazar, konu…) bu satırların hepsinde yazar.
Nüshası olmayan eser — e-kitap, e-veri tabanı ya da bütün nüshaları silinmiş eser —
**barkodu boş tek satırla** yazılır ve **Nüsha Sayısı** 0'dır. Kayıttan düşülmüş ve
devredilmiş nüshalar da dosyadadır (çıkış tarihiyle); yanlış açılıp silinmiş nüsha
dosyada yoktur.

**İçe aktarım sözlüğünün üst kümesidir.** İlk on altı sütun, katalog Excel şablonunun
sütunlarıyla aynı başlıkları aynı sırayla taşır (bkz. `katalog-excel-sablonu.md`); sonra
dışa aktarıma özgü sütunlar gelir. Sayılar sayı, tarihler tarih hücresidir; barkod, ISBN
ve sınıflama kodu metindir.

Sütunlar, dosyadaki sırayla:

| Sıra | Sütun | Değer | Anlamı |
|---|---|---|---|
| 1 | Eser Adı | Serbest metin | Eserin kaynak adı. |
| 2 | Yazar | Serbest metin | Yazarın adı ve soyadı; birden çok yazar virgülle ayrılır. |
| 3 | Çevirmen | Serbest metin | Çeviri eserde çevirmen. |
| 4 | Yayınevi | Serbest metin | Yayınevinin adı. |
| 5 | Baskı | Serbest metin | Kaçıncı baskı. |
| 6 | Yayın Yılı | Dört haneli yıl | Bu baskının yılı. |
| 7 | ISBN | 10 ya da 13 haneli numara | Kullanıcının yazdığı biçimiyle. |
| 8 | Konu | Serbest metin | Konular, virgülle ayrılmış. |
| 9 | Sınıflama Kodu | Serbest metin | Dewey Onlu Sınıflama (DOS) kodu. |
| 10 | Dil | Serbest metin | Eserin dili. |
| 11 | Kaynak Türü | Kitap / Süreli yayın / Görsel-işitsel materyal / E-kitap / E-veri tabanı | Eserin kaynak türü. |
| 12 | Nüsha Sayısı | 1 ya da 0 | Nüsha satırında 1; nüshası olmayan eserin satırında 0. |
| 13 | Bölüm | Serbest metin | Nüshanın durduğu bölüm (nüshasız eserde eserin bölümü). |
| 14 | Eski Kayıt No | Serbest metin | Kitaptaki eski damga ya da eski defter numarası. |
| 15 | Ciltli Süreli Yayın | Evet / Hayır | Ciltletilmiş süreli yayın nüshası. |
| 16 | Danışma Kaynağı | Evet / Hayır | Ödünç verilmez, kütüphanede okunur. |
| 17 | Eser No | Tam sayı | Dosya içindeki eser numarası; aynı numaralı satırlar aynı eserin nüshalarıdır. Programın iç kimliği değildir. |
| 18 | Barkod | 10 haneli numara | Yıl + altı hane sıra; nüshasız eserde boş. |
| 19 | Kayıt No | Tam sayı | Barkodun sayı hâli; Taşınır Kütüphane Defteri dökümünün sıra numarası. |
| 20 | TKYS Kodu | Serbest metin | Taşınır Kayıt ve Yönetim Sistemi'ndeki (TKYS) karşılık. |
| 21 | Durum | Rafta / Ödünçte / Sınıf kitaplığında / Onarımda / Kayıp / Ayıklandı (kayıttan düşüldü) / Sayım noksanı (kayıttan düşüldü) / Kayıp (kayıttan düşüldü) / Hasar (kayıttan düşüldü) / Devredildi | Nüshanın durumu. |
| 22 | Edinim Yolu | Bakanlık gönderimi / Satın alma / Bağış / Değişim / Sayım fazlası (kayda giriş) / Mevcut koleksiyon (programa aktarım) | Nüshanın geldiği edinimin yolu. |
| 23 | Edinim Tarihi | Tarih (gg.aa.yyyy) | Giriş tarihi. |
| 24 | Birim Fiyat | Sayı (kuruşlu) | Edinimin birim fiyatı; bilinmiyorsa boş, bedelsiz girişte 0. |
| 25 | Komisyon Kararı Tarihi | Tarih (gg.aa.yyyy) | Edinim bir Seçim ve Ayıklama Komisyonu kararına bağlıysa kararın tarihi (bağışta zorunlu — Okul Kütüphaneleri Yönetmeliği Md. 10/3). Geri yüklemede karar bağışta “Bağış değerlendirme”, öbür yollarda “Kaynak seçimi” türüyle kurulur. |
| 26 | Komisyon Kararı Sayısı | Serbest metin | Aynı kararın sayısı. |
| 27 | Kayıttan Çıkış Tarihi | Tarih (gg.aa.yyyy) | Kayıttan düşülmüş ya da devredilmiş nüshada harcama yetkilisinin onay tarihi. |
| 28 | Piyasada Mevcudu Yok | Evet / Hayır | Ödünç verilmez (Md. 16/1-b). |
| 29 | El Yazması / Nadir Eser | Evet / Hayır | Nüshanın el yazması ya da nadir eser işareti (Md. 12/2). |
| 30 | Sınıflama Kaynağı | Katalogdan bulundu / Tahmini / Elle girildi | Sınıflama kodunun nereden geldiği. |
| 31 | Yer Numarası | Serbest metin | Sırt etiketindeki yer numarası. |
| 32 | Eser Bölümü | Serbest metin | Eserin kendi bölümü (“Bölüm” nüshanın bölümüdür). |
| 33 | Barkod Etiketi Basıldı | Evet / Hayır | Barkod etiketinin basım işareti. |
| 34 | Sırt Etiketi Basıldı | Evet / Hayır | Sırt etiketinin basım işareti. |
| 35 | Etiket Doğrulandı | Evet / Hayır | Yapıştırılan barkod etiketi doğrulama okutmasından geçti mi. |

## Dosyayı geri yüklemek

Dosyayı boş bir kuruluma geri
yüklemek için: **Katalog → İçe Aktarma** sayfasında **İçe aktarılacak dosya** seçicisinde **Dışa aktarım
dosyası**'nı seçin, dosyayı yükleyin, **Önizle**'ye, sonra **Uygula**'ya basın. Önizleme
uygulamanın birebir provasıdır ve hiçbir kayıt yazmaz.

- **Yalnız boş bir kataloga.** Katalogda kayıtlı eser varken önizleme de uygulama da
  reddedilir: dosyadaki eserler katalogdakilerle eşleştirilmez, dolu kataloğa aktarım
  eserleri çoğaltırdı.
- **Bütün satırlarla.** Önizlemede aktarılamayan bir satır varsa uygulama yapılmaz. Numara
  sayaçları dosyaya göre ilerlediği için aktarılmayan satırın barkodu bu kurulumda bir daha
  kullanılamazdı. Önizlemedeki nedenlere göre dosyayı düzeltin; düzeltilemeyen satırı
  dosyadan silin (o kitap sonra yeni etiketle kaydedilir) ve yeniden önizleyin.

- **Barkod ve kayıt no korunur; hiçbir numara yeniden kullanılmaz.** Bir satırın barkodu
  bu kurulumda kayıtlı bir nüshadaysa (silinmiş nüsha dahil), bir boş barkod aralığında
  ayrılmışsa ya da bu kurulumun numara sayacının gerisindeyse (bir kez verilmiş sayılır)
  satır aktarılmaz ve nedeni önizlemede yazar. Barkod 10 hanedir ve yılla başlar; 8 haneli
  üye kartı numarası barkod yerine yazılmışsa ayrıca söylenir. Dosyada aynı barkod iki
  satırda yazılıysa yalnız ilki aktarılır.
- **Numara sayaçları ilerletilir.** Aktarımdan sonra her yılın sayacı, dosyanın **Numara
  Sayaçları** sayfasındaki değere ve aktarılan en büyük numaraya çekilir. Böylece eski
  kurulumda silinmiş nüshaların ve bağlanmamış boş etiketlerin numaraları yeni
  kurulumda bir daha verilmez.
- **Eserler dosyadaki gibi açılır.** Aynı **Eser No**'lu satırlar tek esere bağlanır;
  katalogdaki eserlerle eşleştirme yapılmaz (künyesi aynı iki ayrı eser ayrı kalır).
- **Edinimler dosyadan kurulur.** Aynı yol, tarih, birim fiyat ve komisyon kararı tek
  edinim olur. Komisyon kararı, kararın tarihi ve sayısıyla yeniden kurulur: bağışta “Bağış
  değerlendirme”, öbür yollarda “Kaynak seçimi” kararı olarak. Başkan ve katılımcı adları
  dosyada olmadığı için boş kalır ve kararın notu bunu söyler.
- **Bölümler dosyadan açılır.** **Bölümler** sayfasındaki bölümler kurulumda yoksa ad,
  DOS aralığı, tarif ve sırasıyla açılır. Sayfada olmayan bir bölüm adı önizlemede sorulur.
- **Durum.** Rafta, Onarımda, Kayıp ve kayıttan düşülmüş ya da devredilmiş durumlar
  korunur. **Ödünçte** ve **Sınıf kitaplığında** olan nüsha **Rafta** açılır: ödünç ve
  teslim kayıtları kişisel veri taşıdığı için dosyada yoktur; satırın uyarısı bunu söyler.
  Kayıptaki nüshanın kayıp dosyası ve onarımdaki nüshanın onarım kaydı da dosyada yoktur.
- **Aynı dosya ikinci kez uygulanamaz.** Kitaplar kayda iki kez girerdi.
- **Sayım sürerken** (TMY 32/3 durdurması seçilmişse) aktarım yapılamaz; sayım bitince
  aktarın.

Dosya **Excel listesi** olarak içe aktarılmaz: program dosyayı **Bilgi** sayfasından tanır
ve **Dışa aktarım dosyası**'nın seçilmesini ister. Excel listesi yolunda bütün nüshalar yeni
numara alır, kitapların üzerindeki eski etiketler başka kayıtları gösterir ve kayıttan
çıkmış nüshalar “Rafta” açılırdı.

## Dosyada olmayanlar

- Üyelik, ödünç, teslim, kayıp/hasar dosyası ve onarım kaydı (kişisel veri ya da kişiye
  bağlı kayıt).
- Edinimin kaynak notu (bağışçı ya da satıcı adı) ve notları; komisyon kararının başkanı
  ve katılımcıları.
- Ayıklama teklifleri, sayımlar, basım partileri ve boş barkod aralıkları. Bağlanmamış boş
  etiketin numarası sayaçla korunur ama yeni kurulumda o etiket bir kitaba bağlanamaz;
  kitaba yeni etiket basılır.
- Etiket işaretlerinin tarihleri (yalnız “Evet/Hayır”).

Programın bütün kayıtlarıyla taşınması için dışa aktarım değil **şifreli yedek**
kullanılır (bkz. `kurulum.md`).

## Sürüm kuralı

Şema sürümü **Bilgi** sayfasında yazar (`v1`). Sütun eklenir ya da bir sütunun anlamı
değişirse sürüm yükselir; program yalnız tanıdığı sürümü okur ve tanımadığı sürümde
“Dosyayı programın güncel sürümüyle yeniden dışa aktarın” der. Sütunların tek kaynağı
programdaki şemadır (`backend/apps/kutuphane/export_schema.py`); bu belgedeki tablo ile
şema bir testle birebir eşitlenir.
