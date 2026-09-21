# CLAUDE.md — Kütüphane Defteri

> Her oturumda otomatik yüklenir. Amaç: projeyi ilk kez gören bir ajanın kodu
> doğru okuması ve **kasıtlı kararları kusur sanmaması**. Ana referans:
> [`docs/tasarim/2026-09-21-genel-tasarim.md`](docs/tasarim/2026-09-21-genel-tasarim.md).
> "Neden böyle?" sorusunun cevabı çoğunlukla oradadır. Kanıt ve denetim:
> `docs/kesif/`.
>
> Depo dili **Türkçe**: yorumlar, commit mesajları, testler, belgeler ve
> kullanıcıya görünen bütün metinler. Tanımlayıcılar (sınıf, alan, uç adları)
> İngilizcedir; model ve API yüzeyi OYS'den çıkarıldığı için korunur. Kullanıcı
> metninin sözlüğü [`docs/sozluk.md`](docs/sozluk.md)'dir ve bağlayıcıdır.

---

## 1. Altmış saniyede proje

Kütüphane Defteri, bir okul kütüphanesinin işlerini yürüten **çevrimdışı bir
masaüstü programıdır** (Windows 10/11 + Pardus). Kapsadığı işler: katalog ve
etiket; üyelik, ödünç ve iade, sınıf kitaplığına teslim; sayım; komisyon ve
ayıklama; Taşınır Mal Yönetmeliği (TMY) hazırlık çıktıları.

Kardeşlerinden tek farkı **iki yüzeyi** olmasıdır:

| Yüzey | Kim | Nerede dinler | Ne sunar |
|---|---|---|---|
| **Yönetim** | Masadaki kütüphane yöneticisi ve öğrenci görevli | `127.0.0.1`, rastgele port, oturum belirteçli | Django + DRF API + React SPA (pywebview penceresi) |
| **Ağ Kataloğu** | Okul ağındaki bilgisayarlar ve etkileşimli tahtalar | ayarla açılır, port 8765, varsayılan KAPALI | Ayrı WSGI uygulaması, sunucuda üretilen sade HTML, JavaScript yok, **salt okur, kişisel veri yok** |

**Köken** (tasarım §1, §12):
- İş mantığı: OYS'nin (`../okulapp`) `apps/kutuphane` modülü, uyarlanarak.
- Masaüstü, paketleme, okul çekirdeği, `shared/`, ön yüz kiti: **kelebek-sinav
  (KS)** iskeleti (`../kelebek-sinav`). KS de disiplin-defteri'nden (DD)
  türedi.
- DD'den (`../disiplin-defteri-codex`) yalnız tatil takvimi ve iş günü
  aritmetiği, uyarlanarak.
- Tasarımın **AYNEN / UYARLA / ALMA** haritası (§12) bağlayıcıdır. Haritaya
  uymayan "iyileştirme" yapılmaz; AYNEN dosyalarda imza ve sözleşme değişmez.

| Katman | Teknoloji |
|---|---|
| Backend | Django 5.1 + DRF 3.15, SQLite (WAL, hedef `synchronous=FULL`), Python 3.12 |
| Evrak | WeasyPrint + openpyxl + pypdf, tek kapı `shared/pdf.py`, gömülü DejaVu · QR: segno · 1D barkod: bağımlılıksız `shared/barcode128.py` (Code128-C) |
| Yönetim arayüzü | React 18 + TS + Vite + Tailwind (KS'nin M3 kiti) |
| Ağ Kataloğu | Ayrı WSGI; Django'nun istek zinciri, middleware'i, URLconf'u ve ORM'si YOK, yalnız `django.template`; `sqlite3` salt okur bağlantı |
| Masaüstü | pywebview + iki waitress dinleyicisi · tepsi: Windows'ta pystray, Linux'ta Qt |
| Paket | Windows: PyInstaller onedir + Inno Setup (**yönetici kurulumu**) · Linux: `.deb` |
| Güvenlik | **Zorunlu** yönetici parolası · Fernet alan şifrelemesi · kör indeks · şifreli yedek (`.kdbak`) · görevli/yönetici kipi |
| Sürüm | CalVer (`VERSION`) + GitHub Release + `indir.okulapp.org` manifesti |

Sabit ödünç süresi, sayı sınırları, sayım ve ayıklama kuralları Okul
Kütüphaneleri Yönetmeliği (RG 23.11.2024/32731) ile TMY'ye bağlıdır. Metinler
`docs/mevzuat/`'tadır.

---

## 2. Altın kurallar

0. **Kasıtlı olanı kusur sanma.** Rapor yazmadan önce §4 "bulgu DEĞİL"
   tablosunu ve [`docs/teknik-borc.md`](docs/teknik-borc.md)'yi oku. Orada
   yazan kalem biliniyor ve kabul edilmiştir; ancak **gerekçenin kendisi**
   yanlışsa raporlanır.

1. **İki yüzeyin değişmezleri** (tasarım §4.1; testleri §5.10-1/2/3, F0):
   - Yönetim `BackgroundServer`'ı `DEFAULT_HOST` (127.0.0.1) dışında host kabul
     etmez. `0.0.0.0` yalnız `desktop/katalog_server.py` içinde geçer.
   - Katalog uygulaması Django URLconf'unu, ORM'yi, `django.db`'yi ve
     `apps.*.models`'ı **import etmez**. Şablonlarında `{% url` ve `{% load`
     geçmez.
   - Katalog `HTTP_COOKIE` okumaz, çerez yazmaz. Yalnız GET/HEAD; gövde 1 KB'ı
     aşamaz.
   - Katalog yalnız `prepare_django` tamamlandıktan sonra kalkar. F0-F4'te
     yalnız 127.0.0.1'de dinler; `0.0.0.0` güvenlik duvarı denetimiyle F5'te
     gelir.
   - `api/` altındaki her desen katalog portunda 404 döner.
   - Yönetim portu hiçbir ekranda ya da belgede ilan edilmez. Program içindeki
     katalog bağlantıları seçili LAN IP'siyle kurulur ve harici tarayıcıda
     açılır (çerezler portlar arasında yalıtılmaz).
   - Katalog veriye yalnız `kd_katalog_*` görünümlerinden, eylem kodlu
     authorizer'dan geçerek ulaşır. `Loan`, `Membership`, `Acquisition` ve
     kişi tabloları görünümlere hiç girmez (§5.3).

2. **Katalog alanları asla şifrelenmez** (T6). Şifreli alanda DB araması
   yapılamaz ve katalog program kilitliyken de çalışmalıdır. Şifrelenenler
   §6.3'teki listedir: kişi adları, okul no, kart no, gerekçe ve not
   metinleri, komisyon/kurul/onaylayan adları, bağışçı. Anahtar yokken
   `EncryptedField` boş olmayan değeri yazmaz, **hata yükseltir**
   (fail-closed). Parola kurulmadan kişi yazan her uç **409** döner.

3. **Kör indeks** (T14, KS'den bilinçli sapma). Okul no ve kart no için
   `HMAC-SHA256(HKDF(DEK, "kd-kor-indeks"), normalize(değer))`. Kart okutma,
   e-Okul eşleştirmesi ve iptal kart denetimi **tam eşleşmeyle bu indeksten**
   yapılır; teklik kısıtı indekse konur; okul no'ya göre sıralama Python'dadır.
   Okul no ya da kart no üzerinden düz alanla yeni sorgu yazılmaz. Anahtar
   DEK'ten türediği için parola değişimi indeksi bozmaz. Verilmiş bütün kart
   numaraları kişisiz `IssuedCard` tablosunda kalır: **kart no asla yeniden
   kullanılmaz**.

4. **Kip fail-closed** (U5, §4.4). Durumlar: `KİLİTLİ` → `YÖNETİCİ` ⇄
   `GÖREVLİ` (+ `GÜVENLİK_DOSYASI_KAYIP`, `YENİDEN_BAŞLAT_GEREK`). Kip durumu tek
   süreç içi nesnedir (`KipDurumu`, T16).
   - Görevli kipinin izin listesi **uç ve parametre** düzeyindedir. Yeni bir
     uç varsayılan olarak kapalıdır; listeye bilinçli eklenir. Red 403 +
     `{"code":"kip_yetkisiz"}` (belirteç 403'ünden ayrılır).
   - `HEALTH_PATH`, `setup/status/`, `security/status/` hiçbir durumda
     kesilmez.
   - `override_reason` taşıyan ödünç görevli kipinde 403 alır. **Md. 18 sayı
     sınırı ve Md. 16/1 kaynakları hiçbir kipte istisna almaz.**
   - Boşta dönüş sunucuda tembel dolar; yalnız `X-KD-Etkinlik` başlıklı
     istekler süreyi tazeler. Varsayılan 3 dk, mutlak 30 dk.
   - Koruyan test URL desenlerini dolaşır (§5.10-8). Yeni bir uç izin listesine
     yalnız görevlinin o işe gerçekten ihtiyacı varsa girer; testi yeşile
     çekmek için listeye eklemek kusurdur.
   - Görevli kipindeki Çık `POST /api/v1/app/quit/` ile ve gövdede yönetici
     parolasıyla yapılır; parolasız istek 403 alır.

5. **Profil yasağı** (§3 KVKK). Ödünç verisi KVKK md. 6'ya kaymasın diye
   testlerle kilitlenir:
   - üye bazında konu ya da sınıf dağılımı üretilmez;
   - şube × konu kırılımı en az k farklı üye eşiği olmadan yapılmaz;
   - not ya da başarı verisi alanı eklenmez;
   - adlı okuma sıralaması ağa, panoya, yıl sonu raporuna ve velilerle
     paylaşılabilecek çıktılara girmez;
   - okuma ödülü iç çıktısı yalnız yönetici kipinde, "iç kullanım" ibaresiyle.

   **Ödünç ≠ okuduğu kitap.** Öğrenci bazlı ödünç sayısı öğretmene ya da
   e-Okul'a aktarılmaz. Çok okunanlar en az k farklı üye eşiğiyle (varsayılan
   5) hesaplanır ve **sayı gösterilmez**.

6. **Md. 18 süresi sabittir:** "Bir kitabı ödünç alma süresi on beş gündür."
   `LibraryPolicy`'de süre ayar alanı YOKTUR (OYS'nin 1-15 aralığı alınmadı).
   Sayı sınırı öğrenciye 3, öğretmene 5. İade tarihi `bugün + 15`; kaydırma iki
   ayrı kuraldır: hafta sonu/resmî/dini tatilde TBK 93'e **kıyasen** izleyen iş
   gününe; ara tatil ve yarıyılda **okulun tercihiyle** (dayanağı yok, ayarla
   kapanır). Kaydırılmış tarih kullanıcıya "Md. 18 gereği" diye sunulmaz.
   Uzatma, ceza ve harç yoktur.

7. **Sayımda iki ayrı seçenek** (§9-10). **TMY 32/3 durdurması** isteğe
   bağlıdır (kurul talebi + harcama yetkilisi adı ve tarihi) ve yalnız edinim,
   kayıttan düşme, devir ve kayıp dosyası çözümünü kapsar. **"Sayım için
   hizmet arası"** okul kararıdır ve yalnız yeni ödüncü durdurur; TMY'ye
   dayandırılmaz, çünkü ödünç TMY'de giriş-çıkış değildir (13/1, 23/4). İkisi
   tutanakta **ayrı satırdadır**. **İade hiçbir durumda kilitlenmez.**

8. **Türkçe arama ve sıralama** (T7). SQLite'ın `LIKE`'ı ve BINARY sıralaması
   Türkçe harflerde çalışmaz. Arama `search_key`, sıralama `sort_key`,
   `author_sort_key`, `subject_sort_key` alanlarıyla yapılır; hepsi TR
   katlamalıdır ve aynı katlama sorguya da uygulanır. Kapı: "şiir"/"ŞİİR",
   "ılık"/"ILIK", "İnce"/"ince".

9. **Tarih ve Türkçe büyük harf** (kardeşlerde en çok gerçek kusur bu iki
   sınıftan çıktı).
   - Ön yüzde `new Date().toISOString().slice(0,10)` YASAK →
     `lib/format.ts::todayIso()`; koruma testi `format.test.ts`.
   - Backend'de UTC'den tarih türetilmez: `timezone.localdate()` (ör. barkod
     yılı, D6). Saat dilimi `Europe/Istanbul`.
   - Evrakta `text-transform: uppercase` YASAK (WeasyPrint i→I basar). Python'da
     çıplak `.upper()`/`.lower()` Türkçe metne uygulanmaz: görüntüleme için
     `shared/text.py::tr_upper`, eşleştirme için `apps/okul/normalize.py`.

10. **Bağımlılık zinciri: dört halka + masaüstü zinciri** (K7 borcu). Backend
    pakete kaynak ağaç olarak girer; PyInstaller yeni modülü kendisi görmez.
    Her yeni Python bağımlılığı dört yere yazılır:
    `backend/requirements.txt` → `packaging/tests/test_spec_kapsami.py::DAGITIM_IMPORT_ESLEME`
    → `packaging/pyinstaller/kutuphane_defteri.spec` `hiddenimports`
    → `packaging/pyinstaller/giris.py::RUNTIME_MODULES` (paketli ikili
    `--bagimlilik-duman` ile gerçekten import eder).
    Yalnız masaüstünde gereken paketler (pystray, six) ayrı zincirdedir:
    `packaging/requirements-paketleme.txt` (`sys_platform` işaretiyle) ↔
    `giris.py::DESKTOP_RUNTIME_MODULES`; test ikisini platform işaretine göre
    eşitler. pystray LGPLv3'tür: lisans metni **ve kaynağı** pakete girer.
    segno ve pystray bu zincirin sınandığı ilk bağımlılıklardır (F0).

11. **Test ve lint yalnız Docker'da.** Host'a Python ya da Node kurulmaz;
    host'ta `pytest` koşulmaz. Kapı: `bash scripts/gates.sh` yeşil olmadan iş
    bitmiş sayılmaz (§5).

12. **KVKK: kişisel veri depoya girmez.** Gerçek öğrenci, personel ya da veli
    verisi, e-Okul ihracı, veritabanı, yedek, ekran görüntüsü ve günlük dosyası
    depoya, issue'ya, PR'a ve dış hizmete girmez. İki katman: `.gitignore`
    ÖNLER, `packaging/depo_sizintisi.py` DENETLER (gates.sh'in ilk kapısı —
    izlenen dosyalarda veri biçimi ve TCKN sağlaması arar). Dağıtım paketinin
    karşılığı `packaging/veri_sizintisi.py`. İkisi de bulguyu **konumla**
    raporlar, değeri basmaz.
    - Sentetik fixture muafiyeti **dosya adıyla** yazılır (hem `.gitignore` hem
      `MUAF_YOLLAR`); joker kullanılmaz. Sağlamalı örnek kimlik numarası test
      kaynağına yazılmaz, çalışma anında üretilir.
    - Program TCKN, veli verisi, cinsiyet, personel unvanı ve branşı **almaz**
      (V2-01): branş, küçük okulda öğretmeni kişiye bağlar.
    - Ekran görüntüleri yalnız uydurma veriyle alınır. Herkese açık metinde
      (README, site, issue) kurum adı, kişi adı ve okul ağının gerçek IP
      blokları yazılmaz.

13. **Mevzuat atfı depodaki metinden doğrulanır** (`docs/mevzuat/`,
    atıf haritası `BENIOKU.md`). Yeni atıf eklemeden önce metin eklenir. Konum
    dili: program kendini "okulun kütüphane işlerini yürüttüğü **yerel araç**"
    diye tanıtır; "Bakanlık otomasyon sisteminin yerine geçer" iddiası hiçbir
    metinde (arayüz, kılavuz, site, evrak) yer almaz.

14. **Kimlik sabitleri** (§2.3): `KD_*` ortam değişkenleri, `kd_oturum`,
    `X-KD-Token`, `.kdbak` (MAGIC `KDBAK\x02`), veri dizini
    `%LOCALAPPDATA%\KutuphaneDefteri` / XDG `kutuphane-defteri`, mutex'ler
    `KutuphaneDefteri` ve `Global\KutuphaneDefteri`. KS/DD kalıntısına sıfır
    tolerans; F0 kapısı kaynak kodu, evrak şablonlarını ve ön yüz metinlerini
    TR katlamalı tarar: `kelebek`, `ks[_:-]`, `x-ks-`, `ksbak`,
    `disiplin[ _-]?defteri`, `disiplindefteri`, `x-dd-`, `ddbak` (yalın
    "disiplin" ve "sınav" taranmaz; `docs/` köken anlattığı için kapsam dışı).

---

## 3. Bilinen tuzaklar (kardeş projelerden devralınan, burada da geçerli)

- **PDF tek kapıdan ve sırayla.** WeasyPrint'e yalnız
  `shared.pdf.html_to_pdf` ile gidilir: süreç genelinde kilit + paylaşılan
  `FontConfiguration`. Pango/fontconfig aynı süreçte eşzamanlı basımda yerel
  belleği bozar (KS'de 19.09.2026'da paketli program erişim ihlaliyle kapandı).
  Koruma testi `shared/tests/test_pdf.py` başka `write_pdf` çağrısına izin
  vermez. Yerel çöküş Python istisnası değildir, `uygulama.log`a düşmez;
  `logs/cokme.log` (`faulthandler`) o anın yığınını tutar.
- **WeasyPrint ölçü tuzakları (sayfa bütçesi).** İç birim CSS px'tir (1 pt =
  4/3 px). Tablo hücresine `height` vermek satırı kısaltmaz, uzatır. Gövdedeki
  `<style>` ve inline `style` içindeki CSS değişkenleri yok sayılır. Sütun
  hesabına güvenilecekse `table-layout: fixed`; bu durumda yüzde + dolgu
  content-box'ta sayfayı taşırır, `box-sizing: border-box` yalnız o tabloya
  verilir. Hücreye blok kutu koyan tablolarda `tr { break-inside: avoid }`
  şarttır. `overflow: hidden` kutunun yanına float konmaz. **Sayfa bütçesi
  testleri gerçek uzunlukta verilerle** koşar; kısa fixture yanlış yeşil verir.
  Etiketlerde Code128 modülü yazıcı noktasına hizalanır (X = 0,254 mm).
- **Soft-delete ileri FK'da süzmez.** `obj.fk` erişimi ve `select_related`
  silinmiş kaydı geri getirir; yumuşak silmede `PROTECT` ve `SET_NULL` hiç
  tetiklenmez. Canlılık tek bir yardımcıdan sorulur; evraka ad basan her yol
  `deleted_at`'i elle denetler. Saklama ve anonimleştirme bağ koparmayı
  (`membership=NULL`, `Delivery.recipient`) açık güncellemeyle yapar,
  `on_delete`'e güvenmez. Katalog görünümleri silinmiş eser ve nüshayı
  **tanımlarında** süzer (§5.1).
- **Kullanıcıya gösterilen her liste TR sıralanır.** DB `order_by` SQLite'ta
  BINARY'dir (Ç/Ğ/İ/Ö/Ş/Ü Z'den sonra). ViewSet'lerde `get_queryset` QuerySet
  döndürür; sıralı liste `list()` içinde `*_sorted()` selector'ıyla ya da
  `*_sort_key` alanıyla verilir. Şifreli alanlarda ad-temelli filtre, sıralama
  ve teklik DB'de çalışmaz → selector katmanında Python.
- **SQLite.** Yedek daima `Connection.backup()` ile alınır; WAL'de dosya
  kopyalamak yasaktır. Pardus 21'in SQLite'ında `serialize` yoktur (KS'de
  yedek çöküşü). JSON alanında `__contains` yoktur → Python süzme. Katalog
  testleri dosya tabanlı `TEST NAME` + `django_db(transaction=True)` ile koşar:
  bellek içi test veritabanını ayrı bir `mode=ro` bağlantı göremez. Katalog
  görünümleri migration'da kalıcı durmaz; `pre_migrate`/`post_migrate`
  kancalarıyla yeniden kurulur (§5.3).
- **Django `{# #}` yorumu tek satırlıktır.** Çok satıra yayılırsa metin olarak
  basılır; çok satırlı açıklama `{% comment %}` ile yazılır.
- **DRF tek alanlı `UniqueConstraint`'ten alan düzeyinde `UniqueValidator`
  türetir;** `Meta.validators = []` onu silmez. Teklik mesajı servisten
  gelecekse alan elle tanımlanır (`validators=[]`). Kör indeks alanlarındaki
  teklikte buna dikkat.
- **Servis hatası merkezî çevrilir.** `shared.exceptions.kd_exception_handler`
  Django `ValidationError`'ını 400'e çevirir (DRF tanımaz, 500 olurdu) ve
  servis kaynaklı retlerde `message`'a gerekçeyi yazar. `?format=` DRF içerik
  müzakeresine ayrılmıştır; rapor biçimi `?kind=pdf|xlsx` alır.
- **`version_key` iki kopyadır** (`desktop/version.py`,
  `apps/okul/services/updates.py`) ve aynı kalmalıdır; ön sürüm eki doğal
  sıralanır (`beta.10 > beta.9`).
- **Tek dış istek güncelleme denetimidir** ve yalnız "Denetle" düğmesiyle,
  `indir.okulapp.org` manifestinden yapılır (T11). MEB ağında GitHub engellidir.
  Açılışta dış istek atan kod eklenmez.
- **Gün değişimi kapısı** (T9). Program tepside günlerce açık kalabilir;
  "her gün yeniden açılır" varsayımı geçersizdir. Günlük yedek, rotasyon,
  saklama taraması, IP denetimi ve çok okunanlar açılışta ve saatte bir koşan
  kapıdan geçer (F5 iskeleti).

---

## 4. Bunlar bulgu DEĞİL — kasıtlı kararlar

Aşağıdakiler bir web uygulamasında bulgu olurdu. Burada her biri gerekçesiyle
kayıtlıdır.

| Görünen "sorun" | Gerçek | Kaynak |
|---|---|---|
| Yönetim API'sinde `AUTHENTICATION_CLASSES = []`, `AllowAny`, kullanıcı hesabı yok | Yönetim yüzeyi yalnız 127.0.0.1'de dinler. Aynı makinedeki başka sürece karşı oturum belirteci (`X-KD-Token`, fail-closed 403) vardır. Masadaki kişi ayrımı hesapla değil **kiple** yapılır: yönetici parolası + `KipMiddleware` izin listesi | T3, §4.3, §4.4 |
| `SECRET_KEY` kaynakta sabit | Program imza, oturum ve CSRF kullanmaz; katalog imza ve çerez kullanmaz. Anahtarı "kurulumda üretmek" yönetici kurucuda uygulanamaz ve bugün etkisi yoktur. İmza gerektiren özellik eklenirse ilk açılışta rastgele üretilir | T17 |
| Ağ Kataloğunda TLS yok, HTTP + doğrudan IP | Katalog kişisel veri taşımaz. Okul ağında sertifika dağıtımı yükü ağırdır; mDNS VLAN'lar arasında çalışmaz | T5, §5.6 |
| Ağ Kataloğunda erişim günlüğü yok | Bilinçli: IP ve arama terimi yazılmaz (KVKK). Yalnız kişisiz günlük sayaçlar ve Ağ Doktoru'nun son hatası tutulur | §5.5 |
| `AuditLog` / erişim kaydı yok | Kalıcı iz resmî belgelerde ve `BelgeIzi`'ndedir; hassas okuma kip ve şifrelemeyle sınırlanır | B4 |
| `select_for_update` etkisiz | SQLite'ta no-op. Tek yazar + `transaction_mode=IMMEDIATE` | B13 |
| Görevli kipinde Çık'ın parola istemesi Görev Yöneticisi ile aşılır | Koruma **kaza önleyicidir**, güvenlik sınırı değildir | §4.2-4 |
| Katalog `0.0.0.0`'da dinliyor | Yalnız `katalog_server.py`'de, güvenlik duvarı kuralı beş maddelik denetimden geçerse (F5). Yönetim sunucusu asla | §4.1, §5.7 |
| Ağ Doktoru'nun "dinleyici ayakta" öz sınaması güvenlik duvarını kanıtlamaz | Biliniyor: makinenin kendi IP'sine bağlantı loopback'ten geçer. Arayüz bunu söyler ve başka bilgisayar için `Test-NetConnection` komutu verir | §5.9 |
| Şifreli kipte ad üzerinden DB araması yok | Bilinçli (U9): arama ve sıralama Python'da; eşleştirme kör indeksle | §6.3 |
| Şube, üye türü, barkod ve tarihler düz metin | Kabul edilmiş kalan risk | TB1 |
| Kilitliyken iade yok, ikinci parola yuvası yok | v1 kapsamı dışında (bütünlük ve kriptografi bedeli) | A17 |
| Celery, SMS, veli bildirimi yok | Periyodik işler gün değişimi kapısında; veli verisi toplanmaz, yerine tek kişilik pusula | T9, T10 |
| OpenAPI / drf-spectacular yok | Tipler elle; serializer alan listesi anlık görüntüyle test edilir | T13 |
| Veri `ProgramData`'da değil hesabın `%LOCALAPPDATA%`'sında | `ProgramData` bütün hesaplara okuma hakkı verirdi; önerilen hesap ayrı kütüphane masası hesabıdır | §4.5 |
| Personel unvanı, branşı ve öğrenci cinsiyeti yok | Veri en aza indirme; branş öğretmeni kişiye bağlar | V2-01, §6.1 |

**Kural:** Bu tabloya ya da teknik borç kütüğüne giren bir konuyu yalnız
*gerekçenin yanlış olduğunu* gösterebiliyorsan raporla; "auth yok" demekle
yetinme.

---

## 5. Nasıl koşulur

Her şey Docker konteynerinde çalışır. İmaj hazırsa `build` gerekmez.

```bash
docker compose build backend                     # yalnız imaj yoksa ya da bağımlılık değiştiyse
docker compose run --rm backend python manage.py migrate
docker compose run --rm frontend npm install     # ilk kurulumda
bash scripts/gates.sh                            # TAM kapı — bunu koş
```

Tek tek koşmak için (Git Bash'te yol dönüşümünü kapatın; `-T` TTY'siz ortam
içindir):

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm -T backend pytest apps/okul -q
MSYS_NO_PATHCONV=1 docker compose run --rm -T -w /repo backend pytest desktop/tests packaging/tests -q --no-cov
docker compose run --rm frontend npx vitest run src/lib
```

`scripts/gates.sh` sırası: depo sızıntısı (KVKK) → backend `pytest` → `ruff
check` → `ruff format --check` → `mypy` → **ayrı koşuda** `desktop/` +
`packaging/` testleri (günlük yapılandırmasını değiştirdikleri için backend
testleriyle aynı süreçte koşmazlar) → desktop/packaging ruff + mypy → ön yüz
`typecheck` → `eslint` → `prettier --check` → `vitest` (kapsam eşiği
`frontend/vitest.config.ts`). Her adım çıkış koduna ek olarak nöbetçi satırı
(`KAPI_OK_<ad>`) üretir; bu makinede `docker compose run` çıkış kodunu zaman
zaman yutar. Kapı GitHub'da da koşar (`.github/workflows/kapilar.yml`, betiği
olduğu gibi çağırır).

**Ortam notları.** Docker Desktop bu makinede elle başlatılır. Compose kök
olarak yazdığı için `backend/data/`, `*_cache/`, `frontend/node_modules/`
root sahipli olabilir. Compose port açmaz; Ağ Kataloğu masaüstü kabuğunda
açılır, geliştirme konteynerinde değil.

---

## 6. Commit ve süreç

- **Conventional Commits, Türkçe, kapsam etiketli:** `feat(kutuphane): …`,
  `fix(okul): …`, `feat(katalog): …`, `chore(paket): …`, `ci: …`,
  `test(masaustu): …`, `docs: …`. Türkçe karakterli mesaj PowerShell'den
  `git commit -F <dosya>` ya da heredoc ile geçilir.
- **Sürüm:** CalVer, `VERSION` dosyası. `v*` etiketi paketleri üretir, GitHub
  Release'i açar ve paketleri R2'ye yükler; manifest
  `indir.okulapp.org/kutuphane-defteri/manifest.json`'dur.
- **Yayın işleri dışa açıktır ve kullanıcı onaylıdır:** etiket, push, R2
  yüklemesi, site commit'i. Otonom oturum bunları kendi başına yapmaz.
- **okulapp.org ortak yayın alanıdır.** Siteye yazarken
  `../okulapp.org/CLAUDE.md` → "Ortak çalışma düzeni" BAĞLAYICIDIR: yalnız
  kendi alanına yaz (bu projenin alanı: `src/data/kd-release.json`,
  `src/pages/kutuphane-defteri/**`, `src/layouts/KDLayout.astro`,
  `public/kutuphane-defteri.png`) · işe `git fetch` + güncel `origin/main`
  ile başla, eski tabandan açılmış dal güncellenmeden birleştirilmez ·
  production yalnız `main` push'uyla değişir (Workers Builds "Version
  command" `npx wrangler versions upload` kalır, `deploy` yapılmaz) · commit
  başlığı "Kütüphane Defteri: …". Ortak dosyalara (BaseLayout palet tipi,
  `global.css` palet blokları, sitenin CLAUDE.md alan tablosu) yalnız ilk
  eklemede, tek seferlik commit'le dokunulur (tasarım §17).
- **Faz kapısı:** faz, kod kapısı geçilmeden kapanmaz; sapmalar "F<n> eki
  (tarih)" satırıyla işlenir. Okulun denetiminde olmayan saha kanıtları
  (tahta erişimi, gerçek okuyucu) fazı kilitlemez, F12'ye ertelenir. Her fazda
  FE testleri ve kılavuz bölümü ek iş kalemidir.

---

## 7. Faz durumu

**F0 İskelet — sürüyor (21.09.2026).** Tamamlanan: KS iskeletinin kopyası ve KD
kimlik çevirisi; sınav ve ders modüllerinin çıkarılması. Sürenler: kalan KS'ye
özgü kodun temizliği, belgeler, iki sunucu iskeleti, bağımlılık zincirleri,
Inno yönetici kurulumu, `synchronous=FULL` + temiz kapanış işareti, spike'lar
(Windows pystray iş parçacığı, Linux Qt ana iş parçacığı,
`SO_EXCLUSIVEADDRUSE` + waitress `sockets=`, Inno kapatma olayı).

F0 kod kapısı: exe açılır, tepsiye iner, Çık ile kapanır · çıkış kodları ·
`--pdf-duman`, `--bagimlilik-duman` · §5.10-1/2/3 · temiz kapanış işareti
yazılır, zorla sonlandırmada eksik kalır · kimlik kalıntı taraması sıfır ·
gates yeşil.

Sıradaki: F1 çekirdek + güvenlik (sihirbaz, parolasız dal sökümü, kör indeks,
kip). Tam tablo: tasarım §14.1. Saha hazırlık hattı (S1-S13, kod dışı): §14.2.

---

## 8. Belge haritası

| Dosya | İçerik |
|---|---|
| `docs/tasarim/2026-09-21-genel-tasarim.md` | **Ana referans.** Kararlar (U1-U12, T1-T17), mimari, ağ kataloğu, veri modeli, dolaşım kuralları, evrak kataloğu, çıkarım haritası, faz planı, riskler |
| `docs/kesif/2026-09-21-kesif-raporlari.md` | Keşif raporları R1-R9 (kanıt) |
| `docs/kesif/2026-09-21-tasarim-denetimi.md` | Tasarım denetimi bulguları (GA/KM/UY/SU/EK) |
| `docs/mevzuat/` | Mevzuat metinleri; `BENIOKU.md` kaynak listesi ve atıf haritası |
| `docs/sozluk.md` | Bağlayıcı kullanıcı sözlüğü ve yazım kuralları |
| `docs/teknik-borc.md` | Bilinen ve kabul edilmiş kalan riskler |
| `docs/kurulum.md` | Son kullanıcı ve BTR için kurulum, taşıma, sorun giderme, çıkış kodları |
| `docs/ag-kurulumu.md` | *(F5)* BTR için ağ kılavuzu |
| `docs/disa-aktarim.md` | *(F10)* sürümlü dışa aktarım şeması |
| `packaging/windows/NOTLAR.md` | Windows paketinde doğrulanmamış varsayımlar |
| `README.md` | Kısa tanıtım |

---

## 9. Diğer ajanlar

Claude dışındaki ajanlar (Codex vb.) için depo kökündeki `AGENTS.md` bu
dosyaya işaret eder. Brifing iki yerde tutulmaz; yalnız bu dosya güncellenir.
