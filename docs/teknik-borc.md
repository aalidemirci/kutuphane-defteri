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
  keser. Yavaş gönderen bir istemci havuzu doldurabilir. Karşılık (F5):
  katalog için ayrı havuz, `connection_limit=300`, `channel_timeout=30`, kabul
  anında IP başına eşzamanlı bağlantı sınırı (dispatcher alt sınıfı, ör. 20),
  `REMOTE_ADDR` başına token-bucket. **Kalan risk yalnız katalogun erişilemez
  olmasıdır**; veri riski yoktur, yönetim sunucusu ayrı dinleyicidedir.

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

- **TB10 — Linux'ta katalog soketinde `SO_REUSEADDR` yok (F0 spike, F5'te
  karar):** Windows'taki `SO_EXCLUSIVEADDRUSE` karşılığı olarak Linux'ta
  `SO_REUSEADDR` konmadı. Bedeli: bağlantıyı sunucu önce kapatırsa port yaklaşık
  60 sn TIME_WAIT'te kalır, Pardus'ta hızlı yeniden açılışta katalog "port
  kullanımda" diyebilir. F5'te ağ istemcileri gelince yeniden değerlendirilecek.

- **TB11 — waitress'in kendi hata yanıtları Türkçe değil (F5):** 400/413/431
  yanıtları uygulamaya hiç ulaşmaz; gövdede "(generated by waitress)" yazar, CSP
  başlığı taşımaz. Katalog yüzeyi F5'te ağa açılmadan önce ele alınacak
  (tasarım §5.4).

- **TB12 — Windows'ta `0.0.0.0:8765`'e başka süreç bağlanabilir (F0 spike):**
  katalog 127.0.0.1'de `SO_EXCLUSIVEADDRUSE` ile dinlerken aynı porta 0.0.0.0
  üzerinden bağlanma başarılı oluyor (loopback trafiği yine kataloğa gider).
  F5'te katalog 0.0.0.0'da dinlemeye geçince bu durum ortadan kalkar; o zamana
  dek bilgi notu.

- **TB13 — Tepsisiz Linux'ta arayüzden çıkış yolu yok (F0 → F5):** tepsi
  yoksa çarpı pencereyi küçültür; program yalnız kanalın `kapat` komutu ve
  oturum kapanışındaki SIGTERM ile kapanır. Arayüzdeki "Çık" F5'te gelir.

- **TB14 — Çıkışta açık WAL checkpoint yok (F0):** düzenli kapanışta
  `PRAGMA wal_checkpoint(TRUNCATE)` çağrılmıyor; SQLite son bağlantı kapanınca
  checkpoint yapar. Kurucunun kapatma olayında dosyaların tutarlı kaldığı
  F12 saha provasında doğrulanacak.

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

## Kapanan

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
