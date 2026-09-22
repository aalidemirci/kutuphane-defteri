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
  §8.3):** kural (`name_match.probably_same_person`) adın aynı olmasını TEK BAŞINA yeterli
  sayar, çünkü kuralın asıl işi **soyadı değişimidir** ve orada soyadlar tamamen farklıdır
  ("AYŞE YILMAZ" → "AYŞE KARA"); soyad yakınlığı aramak kuralı işlevsiz bırakırdı. Bedeli:
  aynı aktarımda okula yeni gelen bir adaş (Ayşe, Fatma, Mehmet gibi yaygın adlarda) havuzda
  bekleyen kişinin aday sütununda görünebilir; `selectors.leave_pool_similar_personnel`in
  tarih süzgeci yalnız ESKİ kayıtları eler, aynı aktarımda açılan adaşı elemez (elemesi de
  istenmez: soyadı değişimi tam olarak o kayıttır). Yanlış birleştirme geri alınamaz
  (`persons.merge_personnel` kaynağı katı siler). Azaltma: aday yalnız ÖNERİDİR, hiçbir şey
  kendiliğinden olmaz; havuz ekranı adayların yalnız ad benzerliğiyle bulunduğunu ve adaş
  olabileceğini söyler, birleştirme iki adı da yazan onay diyaloğundan geçer. Daha iyisi
  (aday satırında eşleşme gerekçesi + ikinci doğrulama, ya da e-Okul'da kişiyi ada bağlamayan
  bir anahtar) kullanıcı kararı ister; F6'da üyelik bağları gelince yeniden değerlendirilir.

- **TB19 — Kurulum bitmeden yönetici kipi süreyle kapanmaz (F1 eki 8, §4.4):** kullanıcı
  kararı 2-1 gereği `setup_completed` yanlışken boşta (3 dk) ve mutlak (30 dk) süreler kipi
  düşürmez ve süre dolduğunda sayaçlar yeniden başlar — zaman üst sınırı yoktur. Bedeli:
  sihirbazın 1. adımında "Sakladım, doğrula"ya basılmadan bırakılan ekranda kurtarma anahtarı
  düz metin olarak durur; program kendiliğinden ne görevli kipine iner ne kilitlenir ve
  tasarım §4.5'e göre tepside günlerce açık kalabilir. Karar bilinçlidir (süre dolup kipin
  düşmesi kullanıcıyı anahtarı saklamadan ekrandan atıyordu). Azaltma: "Kilitle" ve "Görevli
  kipine geç" kurulum sırasında da elle çalışır; kılavuz kurulumun tek oturumda bitirilmesini
  ve anahtar saklanmadan masadan kalkılmamasını söyler. Askıyı yalnız bekleyen anahtar varken
  uygulamak ölçüyü daraltırdı ama kullanıcı kararını değiştirir; ertelendi.

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
