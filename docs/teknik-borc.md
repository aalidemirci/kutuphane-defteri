# Teknik borç kütüğü

Buraya giren her kalem **biliniyor ve kabul edilmiş** demektir; denetimlerde
yeniden raporlanmaz (gerekçenin kendisi çürütülmedikçe). Kaynak: genel
tasarım §4.3 (tehdit modeli), §15 (açık kararlar), §16 (riskler). Kalem
kapanınca silinmez, "Kapanan" bölümüne tarihle taşınır.

## Açık

- **TB1 — Şube, üye türü ve zaman damgası düz metinde (U9'un kalan riski;
  tasarım §4.3, §6.3):** adlar, okul no, kart no ve kişi metinleri Fernet'le
  şifreli, eşleştirme kör indeksle yapılır. Ama şube, üye türü, barkod, eser
  adları ve ödünç/iade tarihleri **düz** kalır: katalog araması, sıralama ve
  sayım bunlara DB'de erişmek zorundadır. Veri dizinini kopyalayan biri ad,
  okul no ve kart no olmadan kişiye doğrudan ulaşamaz; ama **küçük şubede**
  "9/C'den bir öğrenci şu tarihte şu kitabı aldı" bilgisi kişiyi tahmin
  ettirebilir. Öğretmenin branşı ve unvanı hiç alınmadığı için öğretmen branş
  üzerinden tanınmaz (V2-01). Azaltma: ayrı kütüphane masası Windows hesabı +
  BitLocker önerisi (`docs/kurulum.md`), aktif üyenin iade edilmiş ödünçlerinde
  kişi bağının ders yılı sonu + 1 yıl sonra koparılması (§6.4). **Aydınlatma
  metnine (E13) yazılır.**

- **TB2 — Ağ kataloğunda bağlantı tüketme (slowloris; tasarım §4.3 GA-12,
  §5.2):** waitress'in `connection_limit` değeri sunucu geneline uygulanır, IP
  başına sınır tanımaz; `channel_timeout` yalnız hiç veri gelmeyen bağlantıyı
  keser. Yavaş gönderen bir istemci havuzu doldurabilir. Karşılık (F5,
  **uygulandı 24.09.2026**): katalog için ayrı havuz (`threads=4`),
  `connection_limit=300`, `channel_timeout=30`, kabul anında IP başına
  eşzamanlı bağlantı sınırı 20 (`desktop/katalog_server.py::katalog_sunucu_sinifi`,
  waitress `TcpWSGIServer` alt sınıfı; tavanı aşan bağlantı yanıt yazılmadan
  RST ile kapanır, yalnız kişisiz sayaç tutulur), `REMOTE_ADDR` başına
  token-bucket (katalog uygulaması). Ölçüm (Docker, 24.09.2026): tek adresten
  60 boşta bağlantıda 40'ı sınırda kesildi, başka adresten istek hizmet aldı;
  50 farklı istemcide hepsi 200, yönetim API'si p95 ~2 ms
  (`desktop/tests/test_katalog_yuk.py`). İki kaplı prova gerçek katalog
  uygulaması ve 10.000 eserle koştu (`scripts/ag_katalogu_provasi.sh`, tasarım
  §14.1 F5 ekleri 18). 50 ayrı adresten düşünme süresiz yükte 4.462 isteğin
  hepsi 200 döndü; hız sınırına takılan ve reddedilen bağlantı olmadı, yönetim
  API'si p95 158 ms kaldı. **Kalan risk yalnız katalogun
  erişilemez olmasıdır**: çok sayıda adresten gelen dağıtık yük ya da aynı
  NAT adresini paylaşan 3'ten fazla tarayıcı sınıra takılabilir (okul
  VLAN'ları arasında NAT beklenmez); veri riski yoktur, yönetim sunucusu ayrı
  dinleyicidedir.

- **TB3 — `PRAGMA synchronous=FULL` maliyeti (T15, A18):** WAL + `NORMAL`
  elektrik kesintisinde son işlemleri geri alabilir; dolaşımda bu sessiz
  kayıptır (SU-18). Bu yüzden `FULL` seçildi; her commit fsync bekler.
  **F0 ölçümü (21.09.2026, Docker/WSL2 ext4, 500 tek-satırlı işlem, her biri
  ayrı `BEGIN IMMEDIATE…COMMIT`):** NORMAL 0,009 ms/işlem, FULL 1,215 ms/işlem.
  Okutma başına ~1 ms insan hızındaki dolaşımda hissedilmez; toplu içe aktarım
  tek transaction'da olduğu için tek fsync öder. **Açık:** HDD'li eski
  Windows masaüstünde (NTFS fsync 5-20 ms beklenir) F12 saha provasında
  yeniden ölçülecek; yavaşlık çıkarsa `synchronous` gevşetilmez, yazma
  işlemleri toplanır.

- **TB4 — Logo geçici: kelebek çizimi (F0 kopyası):** `packaging/ikonlar/
  logo_uret.py` kardeş projenin koltuk-karesi kelebeğini üretiyor; açıklaması
  da o projenin salon krokisini anlatıyor. Kütüphaneye özgü bir çizim
  gelene kadar ikon ve logo bu yer tutucudur. Değiştirmek için
  `kutuphane-defteri-logo.png` yeniden üretilip `ikon_uret.py` koşulur
  (sözleşme hazır). Aynı dosyadaki "kelebek" sözcüğü kimlik kalıntısı
  taramasına (tasarım §2.3) takılır; logo değişince kendiliğinden kapanır.
  okulapp.org'daki proje görseli (`public/kutuphane-defteri.png`) de aynı
  logodan türeyecek (tasarım §17).

- **TB5 — Linux derleme tabanı Debian 11 destek dışı (kardeş projeden devralındı;
  A6):** `.deb` Pardus 21 uyumu için `python:3.12-bullseye` kabında derlenir;
  Debian 11 LTS 31.08.2026'da bitti. Güvenlik deposu tarihli arşive
  sabitlendi (`packaging/linux/apt_dene.sh`). Sıradaki kırılma: `bullseye` ANA
  deposunun da `archive.debian.org`'a taşınması; belirtisi derleme kabında
  404'tür, çözümü aynı sabitlemenin ana depo satırlarına uygulanmasıdır.
  Kalıcı çözüm Pardus 21 desteğinin ne zaman bırakılacağı kararıdır (taban
  bookworm'a çıkarsa glibc yükselir, Pardus 21'de paket açılmaz). **Karar
  kullanıcıdadır**, saha kurulumlarına bakılarak verilir.

- **TB6 — İmzasız exe + dinleyen port (tasarım §16-15):** kurulum dosyası
  imzasızdır; tarayıcıyla indirilince SmartScreen "tanınmayan uygulama"
  uyarısı çıkar. Ağ kataloğu açıkken dinleyen port bazı antivirüslerde ek
  uyarıya yol açabilir. Azaltma: SHA-256 doğrulaması (`docs/kurulum.md`),
  onedir paket (yanlış pozitifi azaltır). İmzalama v2 işidir.

- **TB7 — Her güncelleme yönetici (BTR) ister (U4, tasarım §16-14):** kurulum
  Program Files'a yapılır ve güvenlik duvarı kuralı kurucuda eklenir; bu
  yüzden her sürüm geçişinde UAC'ye yönetici kimliği girilir. Güncelleme BTR'nin
  takvimine bağlı kalabilir. Azaltma: güncelleme kipinde güvenlik duvarı
  kuralına dokunulmaz (değiştirilmiş port ve BTR'nin eklediği bloklar korunur);
  güncelleme denetimi yalnız düğmeyle yapılır, program kendisi indirmeye
  zorlamaz.

- **TB8 — Anonimleştirilen bağlar yedeklerde bir süre kalır (V2-02, §6.4):**
  günlük ve `pre-anonim` yedeklerde en çok 14 gün; `pre-migrate` yedeklerinde
  son 5 güncellemeye kadar (tetik anında eski `pre-migrate`ler silinir).
  Kullanıcının indirdiği şifreli yedekler ve USB kopyaları okulun elindedir;
  imha kuralı kılavuzda yazılır. Aydınlatma metni bu kapsamı aynen söyler.

- **TB9 — Kişisel Verilerin Silinmesi… Yönetmeliği depoda yok (§6.4):**
  anonimleştirme onayının azami bekleme süresi (6 ay) bu Yönetmeliğin
  periyodik imha hükmüne göre ayarlanacak. Metin resmî kaynaktan birebir
  alınana kadar bu Yönetmeliğe madde atfı yazılmaz
  (`docs/mevzuat/BENIOKU.md` §2).

- **TB16 — Ayrılmış kişi kayıtları F11'e kadar süresiz duruyor (F1 eki 7, §6.4):**
  kullanıcı kararıyla (22.09.2026) ayrılış artık hiçbir kaydı silmiyor; "hiç üye
  olmamış ve yükümlülüksüz kişi ayrılışta katı silinir" dalı kalktı, çünkü ayrılanın
  iade etmediği kitabı olabilir ve kaydı kaybolmamalı. Bedeli: okuldan ayrılmış
  kişilerin ad, okul no (şifreli) ve sınıf/şube (düz) kayıtları saklama taraması
  gelene kadar programda kalıyor — §6.4'ün "hemen sil" satırı artık boş. Azaltma:
  kayıtlar şifreli ve yerel; kullanıcı gereksiz bir kaydı "Sil" ile kaldırabilir.
  **Kapanışı F11'dedir:** saklama taraması ayrılmış kişileri aday gösterir, süre
  (varsayılan öneri: ayrılıştan 2 yıl sonra) ve yönetici onayı orada kararlaşır;
  aydınlatma metni (E13, F6) bu kapsamı aynen söyler.

- **TB17 — Kurtarma anahtarı yenileme ele geçmiş anahtarı geçersiz kılmaz (F1 eki 8,
  §6.3):** "Kurtarma anahtarını yenile" aynı DEK'i yeni anahtarla sarmalar; veri
  yeniden şifrelenmez (yeniden şifreleme bütün kayıtları yeniden yazmak, eski yedekleri
  okunamaz kılmak ve yedek anahtarını değiştirmek demekti). Bedeli: yenilemeden önce
  alınmış yedekler ve veri klasöründe saklanan `guvenlik-arsiv-<damga>.json` ESKİ
  anahtarla açılmaya devam eder. Yani yenileme "kaybolan/kaydedilemeyen kâğıdın yerine
  yenisini koymak" içindir, **ele geçmiş anahtara karşı koruma değildir**. Azaltma:
  arayüz, kılavuz ve `docs/kurulum.md` bunu açıkça söyler ve böyle bir durumda yönetici
  parolasının da değiştirilmesini, eski yedeklerin gözden geçirilmesini önerir. Gerçek
  çözüm (DEK döndürme + bütün kayıtların yeniden şifrelenmesi + yedeklerin yeniden
  mühürlenmesi) F11 bakım fazına bırakıldı.

- **TB18 — "Olası aynı kişi" adayı ad benzerliğiyle bulunur; adaşı eleyemez (F1 eki 7,
  §8.3)** *(daraltıldı: 22.09.2026 — gerekçe gösterimi + ikinci doğrulama)*: kural
  (`name_match.match_reason` / `probably_same_person`) adın aynı olmasını TEK BAŞINA yeterli
  sayar, çünkü kuralın asıl işi **soyadı değişimidir** ve orada soyadlar tamamen farklıdır
  ("AYŞE YILMAZ" → "AYŞE KARA"); soyad yakınlığı aramak kuralı işlevsiz bırakırdı. Bedeli:
  aynı aktarımda okula yeni gelen bir adaş (Ayşe, Fatma, Mehmet gibi yaygın adlarda) havuzda
  bekleyen kişinin aday sütununda görünebilir; `selectors.leave_pool_similar_personnel`in
  tarih süzgeci yalnız ESKİ kayıtları eler, aynı aktarımda açılan adaşı elemez (elemesi de
  istenmez: soyadı değişimi tam olarak o kayıttır). Yanlış birleştirme geri alınamaz
  (`persons.merge_personnel` kaynağı katı siler). Azaltma: aday yalnız ÖNERİDİR, hiçbir şey
  kendiliğinden olmaz; havuz ekranı adayların yalnız ad benzerliğiyle bulunduğunu ve adaş
  olabileceğini söyler. Kullanıcı kararıyla (22.09.2026) iki önlem eklendi: **(1)** kural
  gerekçeyi de döndürür (`MatchReason`: ad ve soyadı birebir aynı / adı aynı, soyadı farklı /
  yazım farkı); selector ve serializer taşır, aday satırı "Neden aday: …" diye yazar ve
  adayın üye türü ile sicile eklendiği günü gösterir (aktarım önizlemesinde de aynı gerekçe
  yazılır). **(2)** Birleştirme onayı ikinci bir doğrulama ister: diyalog (başlık "Bu iki
  kayıt aynı kişi mi?") iki kaydı ayırt eden bilgiyi ve işlemin geri alınamadığını yazar,
  "Birleştir" düğmesi "Bu iki kaydın aynı kişi olduğunu doğruladım" kutusu işaretlenmeden
  açılmaz (`ConfirmProvider.acknowledgeLabel`; kutu bir sonraki onaya devredilmez).
  **Kalan risk:** önlemler kullanıcının dikkatine dayanır — program hâlâ iki adaşı
  ayırt edemez, yanlış birleştirme hâlâ geri alınamaz. Gerçek çözüm (e-Okul'da kişiyi ada
  bağlamayan bir anahtar) veride yoktur; F6'da üyelik bağları gelince yeniden değerlendirilir.

- **TB19 — Kurulum bitmeden yönetici kipi süreyle kapanmaz (F1 eki 8, §4.4)**
  *(daraltıldı: 22.09.2026 — anahtar gözetimsiz ekranda gizleniyor)*: kullanıcı
  kararı 2-1 gereği `setup_completed` yanlışken boşta (3 dk) ve mutlak (30 dk) süreler kipi
  düşürmez ve süre dolduğunda sayaçlar yeniden başlar — zaman üst sınırı yoktur. Bedeli:
  sihirbazın 1. adımında "Sakladım, doğrula"ya basılmadan bırakılan ekranda kurtarma anahtarı
  düz metin olarak durur; program kendiliğinden ne görevli kipine iner ne kilitlenir ve
  tasarım §4.5'e göre tepside günlerce açık kalabilir. Karar bilinçlidir (süre dolup kipin
  düşmesi kullanıcıyı anahtarı saklamadan ekrandan atıyordu). Azaltma: "Kilitle" ve "Görevli
  kipine geç" kurulum sırasında da elle çalışır; kılavuz kurulumun tek oturumda bitirilmesini
  ve anahtar saklanmadan masadan kalkılmamasını söyler. Kullanıcı kararıyla (22.09.2026)
  **kip askısı aynen korunarak** panelin kendisi önlem alır: 5 dakika hiç etkileşim olmazsa
  kurtarma anahtarı ekranda gizlenir ("Anahtar güvenlik için gizlendi" + "Anahtarı göster"),
  gösterince sayaç sıfırlanır. Gizliyken anahtar DOM'da değildir, yazdırma alanı da onu
  taşımaz; PDF yolu etkilenmez. Sayaç YALNIZ GÖRSELDİR ve istemcide durur (`lib/api.ts`in
  kip için zaten tuttuğu etkileşim saati okunur, yeni küresel dinleyici eklenmez): kipi
  düşürmez, anahtarı bellekten silmez — ekrana bakan üçüncü kişiye karşı kaza önleyicidir,
  makineye erişen birine karşı değil. **Kalan risk:** program kurulum bitene kadar hâlâ
  kendiliğinden kilitlenmez ve anahtar bellekte durur; askıyı yalnız bekleyen anahtar varken
  uygulamak ölçüyü daraltırdı ama kullanıcı kararını değiştirir, ertelendi.

- **TB20 — Bakanlık kataloğu ucu belgesiz ve şartsız (U13, tasarım §8.5; 23.09.2026):**
  ISBN künye getirmenin birincil kaynağı olan KYGM halk kütüphaneleri Koha kataloğunun
  SRU ucu (`koha.ekutuphane.gov.tr:210`) 23.09.2026'da çalışır durumdaydı ve Türkçe
  veriyi kusursuz verdi, ama **yayımlanmış bir kullanım şartı, API belgesi, lisansı,
  atıf kuralı ya da hizmet taahhüdü yoktur**; arandı, bulunamadı. Aynı sunucunun web
  yüzeyi WAF ile korunuyor (OAI-PMH "Request Rejected", OPAC bot denetimine
  yönlendiriyor), yani açık portun bilinçli bir hizmet değil gözden kaçmış bir
  yapılandırma olma ihtimali gerçektir: **uç her an kapanabilir.** Üç ayrı bedel: (1)
  uç yalnız **düz HTTP** konuşuyor, TLS yok — yol üzerindeki bir aktör sorgulanan
  ISBN'i görebilir ve dönen künyeyi değiştirebilir (künye zehirlenmesi); (2) tek ISBN
  için **yüzlerce mükerrer kayıt** dönebiliyor (ölçülen en yüksek değer 123), kayıt
  seçimi programın sorumluluğundadır; (3) MEB ağında standart dışı 210 portunun ve düz
  HTTP'nin açık olup olmadığı **doğrulanamadı** (Yönerge 11/22 önceliği 21/80/443'e
  verir). Azaltma: özellik varsayılan KAPALI ve fail-open · gelen künye ön izleme +
  onay olmadan hiçbir alana yazılmaz · yerel önbellek · bulunamayan ISBN için Open
  Library yedeği · toplu indirme ve yeniden dağıtım YAPILMAZ, yalnız tek tek sorgu ·
  yazılı izin ve atıf koşulu kuruma sorulur (S14) · erişim BTR ile sınanır (S15).
  **Kalan risk:** uç kapanırsa özellik sessizce yalnız Open Library'ye düşer ve onun
  Türkçe verisi kusurludur (TB21); künye zehirlenmesine karşı tek katman kullanıcının
  onay ekranındaki dikkatidir.

- **TB21 — Open Library'nin Türkçe veri kusurları (U13, tasarım §8.5; 23.09.2026):**
  yedek kaynağın Türkçe kayıtlarında ölçülmüş beş kusur var: (1) **Türkçe harf
  düşmesi** — "Yap Kredi Yaynlar", "Destek Yaynlar"; (2) **ham HTML varlığı** —
  `Do&#x11F;an Kitap` (aynı kayıtta üç varyant); (3) **ayrışık (NFD) kod noktaları** —
  "İletişim" ayrık birleştirici işaretlerle geliyor ve `apps/okul/normalize.py`
  katlaması bu biçimi kullanıcının yazdığı biçimle **eşleştiremiyor**; (4) **çevirmen
  yazar sayılmış** — Orhan Pamuk kitaplarına Kazak ve İspanyol çevirmenler yazar
  alanında eklenmiş, yazar iki kez yinelenmiş; (5) **uydurma tarihler** — Amazon
  kaynaklı kayıtlarda "13 Nisan"/"28 Ekim" günleri anormal sıklıkta. Bu veri onaysız
  kataloğa girerse deponun TR katlama disiplinini (T7: `search_key`, `sort_key`,
  `author_sort_key`) ve `docs/sozluk.md` yazım kurallarını **sessizce** bozar: kullanıcı
  "İletişim" yazıp arar, kendi kataloğundaki kitabı bulamaz. Azaltma: Open Library
  **yalnız yedek kaynaktır** · içe alma sınırında **NFC normalleştirmesi zorunludur** ve
  koruma testi vardır (§5.10-19) · HTML varlıkları çözülür · **çevirmen alanı dışarıdan
  doldurulmaz**, kullanıcıya sorulur · tarihten yalnız yıl alınır · hiçbir alan onaysız
  yazılmaz, gelen metinde Türkçe harf yoksa kullanıcıya uyarı çıkar. **Kalan risk:**
  düzeltme kullanıcının gözüne dayanır; program "Kurk Mantolu Madonna"nın yanlış
  olduğunu kendi başına bilemez.

- **TB22 — Elle yazılan ISBN-10 ile nüsha barkodu tam ayrılamıyor (F2 düzelticisinden
  devreden; `apps/kutuphane/barcode.py::classify_scan`):** iki şema da salt rakam ve 10
  hanedir, ayrım yalnız yıl ön ekiyledir (`SCAN_YEAR_MIN`…`SCAN_YEAR_MAX` = 2000-2999).
  Bedeli iki kalem: (1) ilk dört hanesi 2000-2999 aralığına düşen ISBN-10'lar (ör.
  Fransızca "20…" grubu) **nüsha barkodu sanılır**; (2) üst duvar `SCAN_YEAR_MAX = 2999`
  keyfîdir — barkod yılı `localdate().year`'dan gelir, yani 3000 yılına kadar sorun
  çıkmaz ama duvarın kendisi bir varsayımdır ve sınama dışıdır. Ayrım yalnız ELLE
  yazımda gerekir: okutulan ISBN barkodu 13 hanedir ve 978/979 ön ekiyle kesin ayrılır.
  Azaltma: okul U7 gereği **yeniden etiketleniyor**, elindeki numaralar 13 hanelidir;
  ISBN-10 zaten 2007'den beri basılmıyor; yıl gibi görünmeyen 10 haneli numara
  sağlaması tutuyorsa ISBN-10 sayılır ve kullanıcı "nüsha bulunamadı" yerine doğru
  iletiyi görür. **Kalan risk:** salt rakamdan oluşan iki 10 haneli şema arasında bu
  belirsizlik kaçınılmazdır; kapatmanın tek yolu barkod şemasını değiştirmektir (U7 ve
  T8 kararı, açılmaz).

- **TB23 — Yedekler kendi dönemlerinin parola ve kurtarma anahtarıyla açılabilir kalır
  (görev devri; §4.4, §6.3):** parola değişimi ve kurtarma anahtarının yenilenmesi DEK'i
  yeniden üretmez, yalnız sarmalı yeniler. Her `.kdbak` alındığı anın güvenlik dosyasını
  başlığında taşıdığı için, **devirden önce alınmış yedekler eski parola ve eski kurtarma
  anahtarıyla açılabilir**. Bütün alanların yeniden şifrelenmesi (DEK döndürme) v1
  bütçesi dışındadır. Azaltma: görev devri notu (E18) eski anahtarın imhasını ve eski
  yedeklerin akıbetini yazar; kılavuz bunu açıkça söyler. Kapatma yolu F11'de
  değerlendirilir.

- **TB24 — Şifrelemeye geçişten önceki düz metin veritabanı dosyasında kalabilir
  (§6.3):** `PRAGMA secure_delete=ON` yeni silmeleri kapsar, ama daha önce yazılmış
  sayfalar ve WAL artığı için `VACUUM` çalıştırılmaz. Pratikte parola sihirbazın ilk
  adımıdır ve `enable()` yalnız kişi tabloları boşken çalışır, yani geçişte düz kişi
  verisi bulunmaz; kalan risk kuramsaldır. Tam koruma disk şifrelemesidir (BitLocker /
  LUKS — `docs/kurulum.md`).

- **TB25 — Okul ağı bilgisi depoya girmez (yayın kuralı; 23.09.2026):** keşif ve ağ
  belgelerinde gerçek IP blokları, alt ağ maskeleri, host numaraları, VLAN, SSID, proxy
  ve sunucu adları **yazılmaz**; yerlerine `<idari-ağ>`, `<tahta-ağı>`, `<ek-alt-ağ>`,
  `<bilgisayar-adı>` yer tutucuları kullanılır. Depo herkese açıktır ve sahibi gerçek
  adıyla görünür; bu bilgiler tek başına zararsız görünse de kurumu daraltır. F5'te
  yazılacak `docs/ag-kurulumu.md` bu kurala uyar. **Kalan risk:** kural elle denetlenir;
  `packaging/depo_sizintisi.py` ağ bilgisine bakmaz.

- **TB26 — Denetim belgesinin yayın sürümü (23.09.2026):** `docs/kesif/…-tasarim-
  denetimi.md` yayına açılırken üç bulgunun (GA-2, UY-1, SU-25) sömürü ayrıntısı
  çıkarıldı; bulgular ve kararları yerinde kaldı. Bu üçü kardeş projede (kelebek-sinav,
  herkese açık) **hâlâ açıktır**; bu projede karşılıkları F1'de kapatıldı (§4.3, §4.4,
  §6.3). Kalan iş kod dışıdır: kardeş projenin yamalanması.

- **TB27 — Linux paketinde PySide6 sürüm tavanı ve boyut (23.09.2026):** Pardus 21
  (Debian bullseye) Mesa 20.3.5 taşıdığı için PySide6 **6.9.1 ve üstü açılmaz**
  (`libQt6WebEngineCore` `gbm_bo_get_fd_for_plane` sembolünü ister); sürüm `6.8.3`'e
  sabitlendi. Bedeli: Pardus 21 desteklendiği sürece Qt ve Chromium güvenlik yamaları
  alınamaz. İkinci bedel boyuttur: PySide6 kurulumu ~645 MB (PyQt5 ~150 MB idi), `.deb`
  İlk CI derlemesinde ölçüldü (23.09.2026): `.deb` 188 MB (sıkıştırılmış), kurulu boyut daha büyük. Azaltma seçenekleri (henüz uygulanmadı): dil dosyalarının
  Türkçe ve İngilizceyle sınırlanması, gereksiz Qt eklentilerinin dışlanması. İlk CI
  derlemesinde gerçek boyut ölçülecek. **Karar kullanıcıdadır:** Pardus 21 desteği
  bırakılırsa tavan kalkar (TB5 ile aynı karar).

- **TB28 — Üçüncü taraf lisans metinleri pakete girmedi (F12 iş kalemi):** PySide6
  (LGPLv3) ve pystray (LGPLv3) lisans metni **ve** pystray kaynağı, material-symbols
  (Apache-2.0) LICENSE + NOTICE, DejaVu dışındaki Python ve ön yüz bağımlılıklarının
  lisansları pakete konmalıdır (`THIRD_PARTY_LICENSES/` + `BAGIMLILIKLAR.md`). `.deb`
  için `/usr/share/doc/kutuphane-defteri/copyright`, Inno için `LicenseFile=` eksiktir.
  Bugün ihlal yoktur (henüz sürüm yayımlanmadı); **ilk sürümden önce kapanmalıdır**.

- **TB29 — İki hazır etiket tabakasının ölçüsü doğrulanmadı (F4, tasarım §7.2; 24.09.2026):**
  48,5 × 25,4 mm 44'lü tabakanın kenar boşlukları yayımlanmış bir kaynaktan
  doğrulanamadı. Yerleşim simetrik kabulle hesaplandı (yan 8,0 mm, üst ve alt 8,8 mm)
  ve şablon adına "yaklaşık ölçü" yazıldı. Ölçü ve adet örneği Tanex TW-2044'tür
  (44'lü). **Avery Zweckform 3657 aynı etiket ölçüsündedir ama 40'lıdır (4 × 10)**; o
  tabakayı alan okul 10 satırlı yeni şablon tanımlar, hazır 44'lü şablon ona uymaz.
  52,5 × 29,7 mm 40'lı tabaka aritmetik olarak kenarsızdır (4 × 52,5 = 210,
  10 × 29,7 = 297); yazıcının basamadığı kenar payı (yaygın lazerde 4,23 mm, bazılarında
  5 mm) dış sütun ve satırlara düşer. İlk sürümde bu pay yalnız "kenara yakın yazı ya da
  sessiz bölge kesilebilir, kalibrasyon sayfasında görürsünüz" diye anlatılıyordu;
  ölçülen gerçek bundan kötüydü (denetim, 24.09.2026): 4. sütunda QR'ın konum deseni
  0,47 mm kesiliyor, 5 mm paylı yazıcıda 1. sütunun START barları da kesiliyor,
  kalibrasyon cetvellerinin hiçbiri basılmıyordu. **Azaltma (uygulandı):** etiket düzeni
  bar, QR modülü ve yazıyı sayfa kenarından en az 5 mm içeride tutar
  (`labels/geometry.py::PRINT_SAFE_MARGIN_MM`, `layout.ink_insets`; sessiz bölge paya
  taşabilir) ve kalibrasyon sayfası cetveli basılamayan dış kenar yerine etiketin iç
  kenarına koyar (`calibration.measured_edges`); ikisi PDF'in kendisinden ölçülerek
  sınanır (`test_etiket_pdf.py`). **Kalan risk:** basamadığı kenarı 5 mm'den geniş bir
  yazıcıda 40'lı tabakanın dış hücreleri yine kesilebilir (kılavuz kenar boşluklu tabaka
  önerir); kalibrasyon kayması bir hücreyi sayfadan taşıracak kadar büyükse o hücrede
  olağan düzen basılır. Okul tabakayı S4'te satın alıp ölçene dek 44'lü şablon tahminidir;
  gerçek basım F12 saha kanıtıdır.
- **TB30 — Ağ Doktoru'nun UAC adımı yönetim isteğini bekletir (F5, tasarım §5.7;
  24.09.2026):** "Kuralı ekle/güncelle" ve Windows'ta port değişikliği
  (`library/network-catalog/firewall-rule/`, `port/`) UAC yardımcısının bitmesini
  **eşzamanlı** bekler (`guvenlik_duvari.kural_guncelle_uac`, en çok 120 sn). Bu sürede
  o HTTP isteği bir yönetim iş parçacığını tutar ve arayüzün düğmeleri kapalıdır;
  öbür ekranlar çalışır. Kural yazıldıktan sonra denetçi katalogu önce ESKİ port ayarıyla
  yeniden kurar (port maddesi o an tutmaz), port kaydedilince hemen yeniden kurar:
  arada saniyelerce "Güvenlik duvarı izni yok" görünebilir. Gerekçe: UAC penceresi
  kullanıcının önündeyken ayrı bir iş kuyruğu ve yoklama eklemek, tek kullanıcılı
  programda kazanç getirmez; sıra "önce kural, sonra ayar" UAC reddedilince portun
  değişmemesini sağlar (§14.1 F5 ekleri 13).
- **TB31 — Katalog authorizer'ı görünümü aynı adlı CTE'den ayıramaz (F5, tasarım §5.3;
  24.09.2026):** SQLite, görünüm üzerinden okumada görünümün adını 5. argümanda
  verir; FROM'daki adlı bir CTE'nin adını da aynı yerde verir. Görünümle aynı adı
  taşıyan bir CTE (`WITH kd_katalog_eser AS (SELECT title AS baslik FROM
  kutuphane_work) …`) izin listesindeki (tablo, sütun) çiftlerini görünüm
  TANIMINDAKİ süzgeçler (yumuşak silme, nüsha durumu) olmadan okuyabilir. Barkod,
  kişi, ödünç ve üyelik tabloları yine reddedilir (izin listesinde yoklar); PRAGMA,
  yazma ve izin listesi dışı fonksiyon yine yasaktır. **Sömürülemez**: katalogda
  keyfi SQL çalışmaz; değerler parametredir, sütun ve sıralama sabit kümeden seçilir,
  `LIKE … ESCAPE` doğrudur. Güvencenin dayanağı katalog SQL'inin SABİT olmasıdır;
  `katalog/tests/test_veri_erisimi.py` kaynak taramasıyla katalog paketinde `WITH`
  olmadığını ve okunan adların `UST_DUZEY_OKUNABILIR` kümesinde olduğunu sınar.
  Önekli ama kümede olmayan ad (CTE, ileride eklenecek tablo) authorizer'da
  reddedilir (§14.1 F5 ekleri 20). Katalog kullanıcı girdisinden SQL üreten bir yol
  kazanırsa bu kalem yeniden açılır.
- **TB32 — Son sınıflara ayrı son ödünç tarihi görevliye sınıf düzeyini sezdirir (F6,
  tasarım §8.3; 24.09.2026):** `last_loan_date_graduating` tanımlıysa iki tarih
  arasındaki günlerde son sınıf öğrencisinin ödüncü reddedilir, öbür sınıflarınki
  verilir. Görevli iletisi tarihsizdir ve iki ret aynı metindir ("Yıl sonu son ödünç
  tarihi geçti — …"; §14.1 F6 ekleri 15), ama masadaki görevli retin o günlerde
  yalnız bazı öğrencilere geldiğini görerek kartın sahibinin son sınıfta olduğunu
  sezebilir. Kişi masadadır ve bilgi yaşından da çoğu zaman bellidir; kapatmanın tek
  yolu son sınıf tarihini kaldırmaktır. Azaltma: ayar isteğe bağlıdır, masa kartı
  görevliye ekranda görülenin paylaşılmayacağını söyler.
- **TB33 — Veri dizini de kaybolursa yedekten sonra verilen kart numaraları yeniden
  çekilebilir (F6, tasarım §7.1, D21; 24.09.2026):** geri yükleme `IssuedCard`'ı geri
  sarar; güvenceyi veri dizinindeki yalnız-eklenen verilmiş kart defteri
  (`verilmis-kartlar.txt`, kişisiz kör indeksler) taşır (§14.1 F6 ekleri 18). Defter
  yedeğe girmez (geri yüklemeden etkilenmemesi için). Bilgisayar değişip program yeni
  veri dizinine yalnız yedekten kurulursa defter yoktur; yedekten sonra basılmış
  kartların numarası 10⁶'lık uzaydan yeniden çekilebilir (her yeni kartta yaklaşık
  "kayıp kart sayısı / 10⁶" olasılıkla). Azaltma: taşıma kontrol listesinde yedek
  eski bilgisayarda taşımadan hemen önce alınır (`docs/kurulum.md` §7), yani
  `IssuedCard` güncel gelir; risk yalnız eski bir yedeğin boş veri dizinine geri
  yüklendiği arıza yolundadır. Geri yüklemeden sonra tanınmayan kartlar toplanır ve
  üyelik yeniden açılır (kılavuz). DEK değişirse (güvenlik dosyasını
  sıfırlayıp kuruluma dönmek) defterdeki indeksler eşleşmez; o yol yalnız boş
  veritabanında açıktır.
- **TB34 — Görevli, kartını bildiği üyenin elindeki kitapları barkod deneyerek
  çıkarabilir (F6, tasarım §7.3, §4.4; 25.09.2026):** görevli kipinde ödünçteki bir
  kitap okutulunca masa "Bu kitap zaten bu üyede." ile "Bu kitap başka bir üyede."
  arasında ayrım yapar (§7.3 tablosu aynen; §14.1 F6 ekleri 6, 26). Bir üyenin kartını
  ya da kart numarasını bilen görevli o kartı okutup kitapların barkodlarını tek tek
  denerse, "bu üyede" iletisinden o üyenin elindeki kitapları çıkarabilir. Ret yazma
  yapmaz ve kart geçerli olduğu için hiçbir sayaç artmaz. Kitap adları durum
  sorgusundan zaten açıktır; açığa çıkan, kitabın o üyede olduğudur. **Azaltma:**
  görevli ayrımı yalnız engeli olmayan üyede görür: görevli kipinde üyeye bağlı
  engeller (üyelik, yıl sonu, gecikme, sayı sınırı) nüshanın kimde olduğundan ÖNCE
  koşar, gecikmesi olan ya da sınırı dolu üyede her kitap aynı reddi alır; gecikmiş
  kitap bu yoldan çıkarılamaz (F6 ekleri 14) · GA-7 kart denetimi: kart numarası
  rastgele ve sağlamalıdır, iki kilit kuralı numara denemeyi durdurur; görevli
  başkasının kartını tahminle bulamaz, kartın kendisine ya da numarasına sahip olması
  gerekir (§4.3, F6 ekleri 19) · görevli öğrencilerin müdürlükçe yazılı
  görevlendirilmesi ve gizlilik bilgilendirmesi (S7) · masa kartındaki gizlilik
  uyarısı ("kimin hangi kitabı aldığını söylemeyin", E19). Aydınlatma metni
  görevlinin okuttuğu kitabın o üyede olup olmadığını gördüğünü söyler (F6 ekleri
  24). Tam kapanış görevli kipinde tek ret kodu olurdu ("Bu kitap ödünçte. Önce iade
  alınsın mı?" + yalnız "İade al"); bu, §7.3'ün görevliye verdiği "başka üyede →
  iade + uyarı" akışını değiştirirdi. **Karar kullanıcınındır (25.09.2026):** ayrım
  korunur, kalem kabul edilmiş kalan risktir.

## Kapanan

- **TB11 — waitress'in kendi hata yanıtları Türkçe değil** *(kapandı:
  24.09.2026 — F5)*. Açıkken: istek uygulamaya hiç ulaşmadan reddedildiğinde
  (bozuk istek satırı 400, büyük başlık 431, büyük gövde 413, uygulama
  istisnası 500) yanıtı waitress üretiyordu: İngilizce düz metin, gövdede
  "(generated by waitress)", CSP yok. Kapanış: `backend/katalog/waitress_hatalari.py`
  waitress'in bu yanıtları ürettiği TEK yolu (`HTTPChannel.error_task_class`)
  alt sınıfla değiştirir; gövde katalogun sabit Türkçe hata sayfasıdır
  (`katalog.hatalar`), başlıklar uygulamanın güvenlik başlıklarıdır. Kanal
  sınıfı SUNUCU ÖRNEĞİNDE değiştirilir (`uygula`) ya da görev sınıfı masaüstü
  sunucusuna verilir (`katalog.app.WAITRESS_HATA_GOREVI`); yönetim sunucusu
  özgün sınıflarla çalışır, küresel yama yoktur. Kanıt:
  `katalog/tests/test_waitress_hatalari.py` (gerçek waitress, ham soket). Kalan
  ayrıntı: başlığı `max_request_header_size`'ı (8 KB) çok aşan bir istekte
  waitress bağlantıyı okunmamış veriyle kapatır; istemci TCP sıfırlaması
  alabilir ve Türkçe sayfayı hiç görmeyebilir — bu bir tarayıcının üretmediği,
  elle kurulmuş bir istektir.
- **TB10 — Linux'ta katalog soketinde `SO_REUSEADDR` yok** *(kapandı: 24.09.2026 —
  F5 kararı)*. Açıkken: Windows'taki `SO_EXCLUSIVEADDRUSE` karşılığı olarak
  Linux'ta seçenek konmamıştı; bağlantıyı sunucu önce kapatınca port ~60 sn
  TIME_WAIT'te kalıyor, katalog hızlı yeniden açılışta "port kullanımda"
  diyebiliyordu. Karar: Linux'ta `SO_REUSEADDR` KONUR. Linux'ta bu seçenek
  Windows'taki gibi port paylaşımı değildir: dinleyen bir soketin adresine
  ikinci bir soket seçenekle de bağlanamaz (çekirdek dinleyen soketle çakışmayı
  her durumda reddeder). Ağ istemcileri gelince sunucunun kapattığı bağlantı
  (`channel_timeout`, `Connection: close`) olağandır; port, IP ya da aç/kapa
  değişikliğinde katalog program kapanmadan yeniden kurulur. Kanıt:
  `desktop/tests/test_katalog_server.py` (sunucunun kapattığı bağlantıdan sonra
  aynı porta yeniden bağlanılır; `SO_REUSEADDR`'lı korsan soket dinleyen porta
  bağlanamaz). Windows'ta TIME_WAIT beklemesi için denetçi portu 5 dakika boyunca
  10 sn arayla kendiliğinden yeniden dener (`katalog_kontrol`, durum
  "bekliyor").
- **TB12 — Windows'ta `0.0.0.0:8765`'e başka süreç bağlanabilir** *(kapandı:
  24.09.2026 — F5)*. Açıkken: katalog 127.0.0.1'de `SO_EXCLUSIVEADDRUSE` ile
  dinlerken aynı porta 0.0.0.0 üzerinden bağlanma başarılı oluyordu; LAN'dan
  gelen trafik o sürece gidebilirdi. Kapanış: katalog artık okul ağı adresinde
  dinler — tüm arayüz kipinde özel kullanımlı joker soket portun bütün
  adreslerini tutar; seçili IP kipinde o IP'ye gelen trafik en belirgin bağa,
  yani kataloğa gider (başka bir sürecin joker bağı yalnız katalogun hizmet
  vermediği adresleri alabilir). Güvenlik duvarı denetimi geçmezse katalog
  hiç dinlemez (loopback'e düşmez). Kanıt: Windows'ta
  `test_windows_tum_arayuzde_ozel_kullanim_tb12_acigini_kapatir`; kalan saha
  kanıtı `packaging/windows/NOTLAR.md` W15.
- **TB13 — Tepsisiz Linux'ta arayüzden çıkış yolu yok** *(kapandı: 24.09.2026 —
  F5)*. Açıkken: tepsi yoksa çarpı pencereyi küçültüyordu; program yalnız
  kanalın `kapat` komutu ve oturum kapanışındaki SIGTERM ile kapanıyordu.
  Kapanış: üst çubukta her durumda görünen "Çık" (`POST app/quit/`; görevli
  kipinde yönetici parolası ister, kilitli ve "yeniden başlat" durumunda
  parolasız) ve "Programı kapatıp yeniden açın" ekranındaki "Programdan çık"
  düğmesi. Kanıt: `backend/apps/okul/tests/test_cikis_ucu.py` (§5.10-18),
  `frontend/src/modules/cikis/CikisDugmesi.test.tsx`.
- **TB14 — Çıkışta açık WAL checkpoint yok** *(kapandı: 24.09.2026 — F5)*.
  Açıkken: düzenli kapanışta `PRAGMA wal_checkpoint(TRUNCATE)` çağrılmıyordu.
  Kapanış: iki sunucu durduktan sonra `desktop/django_bootstrap.py::wal_checkpoint`
  WAL'i ana dosyaya aktarır ve kırpar; okuyucu kalmışsa kısmi kalır ve
  çıkışı durdurmaz (`desktop/tests/test_main_f5.py`). Kurucunun kapatma
  olayında dosyaların tutarlı kaldığının saha kanıtı F12'dedir
  (`packaging/windows/NOTLAR.md` çek-listesi 9-10).
- **TB15 — F1'e devreden F0 kalıntıları** *(kapandı: 22.09.2026 — F1 dalga
  2/3)*. Açıkken: `Personnel.title/branch` modelde ve arayüzde duruyordu
  (tasarım §6.1 V2-01: alınmaz); sihirbazda parola ilk adım değildi;
  `SchoolConfig.app_password_hash`'in `verbose_name`'i "uygulama parolası
  özeti" idi. Kapanış: unvan ve branş modelden, serializer'dan, içe aktarımdan,
  şablondan ve ön yüzden kalktı (göç 0003; `test_models.py`
  `test_unvan_ve_brans_alani_yoktur`); `verbose_name` "yönetici parolası parmak
  izi" oldu (göç 0003); sihirbazın ilk, atlanamaz adımı yönetici parolası ve
  kurtarma anahtarıdır (tasarım §14.1 F1; `KurulumPage`, `setup/complete/`
  kapısı). "Uygulama parolası" metni, "Parolayı kaldır" akışı ve parolasız dal
  F1 dalga 1'de söküldü (§6.3-6).
