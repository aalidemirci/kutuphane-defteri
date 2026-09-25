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

**Çevrimdışı ne demek:** açılışta ağ yok, telemetri yok, bulut yok; dışarı
kişisel veri çıkmaz. Dış istek yalnız kullanıcının başlattığı iki kapıdan
çıkar — güncelleme denetimi ve ISBN künye sorgusu (varsayılan kapalı). Ayrıntı
§3'teki T11 maddesindedir.

Kardeşlerinden tek farkı **iki yüzeyi** olmasıdır:

| Yüzey | Kim | Nerede dinler | Ne sunar |
|---|---|---|---|
| **Yönetim** | Masadaki kütüphane yöneticisi ve öğrenci görevli | `127.0.0.1`, rastgele port, oturum belirteçli | Django + DRF API + React SPA (pywebview penceresi) |
| **Ağ Kataloğu** | Okul ağındaki bilgisayarlar ve etkileşimli tahtalar | ayarla açılır, port 8765, varsayılan KAPALI | Ayrı WSGI uygulaması, sunucuda üretilen sade HTML, JavaScript yok, **salt okur, kişisel veri yok, dış bağlantı açmaz** |

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
   - **Katalog hiçbir dış bağlantı açmaz:** katalog uygulamasında ve
     şablonlarında giden istek (`urllib.request`, `http.client`, soket
     bağlantısı) ve ISBN künye modülü bulunmaz. Program tek süreç olduğu için
     bu bir **kod yolu değişmezidir** (§5.10-20).
   - Katalog yalnız `prepare_django` tamamlandıktan sonra ve ayarı açıksa
     (`KatalogAyari.acik`, varsayılan KAPALI) kalkar. Açma, kapama ve yeniden
     başlatma tek kanaldan yapılır: `desktop/katalog_kontrol.py` (T16). Okul
     ağı adresinde (`0.0.0.0` ya da seçili IP) Windows'ta YALNIZ güvenlik
     duvarı denetiminin beş maddesi geçerse dinler; geçmezse `127.0.0.1`'e de
     düşmez (§5.7, §5.10-10). Linux'ta ufw/firewalld durumu bilgi olarak
     okunur, kural açılmaz; Ağ Doktoru'nun önerdiği komut kaynak sınırlıdır
     (yerel alt ağ + tahta ağı blokları, F5 ekleri 27). `--autotest` katalogu
     yalnız 127.0.0.1'de kaldırır.
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
   kayıttan düşme, devir ve kayıp dosyası çözümünü kapsar (kayıp dosyasında
   bulunma ve bedel adımları hariç — F9 ekleri K1; programa aktarım da durur ama
   iletisi TMY'ye dayanmaz — K4). **"Sayım için hizmet arası"** okul kararıdır
   ve yeni ödüncü ve yeni teslimi durdurur (F9 ekleri 27, 25.09.2026 kullanıcı
   kararı); TMY'ye dayandırılmaz, çünkü ödünç TMY'de giriş-çıkış değildir (13/1,
   23/4). İkisi tutanakta **ayrı satırdadır**. **İade ve teslimden geri alma
   hiçbir durumda kilitlenmez.**

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
    **Linux Qt zinciri ayrıdır** (23.09.2026): `qtpy` + `PySide6` (LGPLv3; GPL
    lisanslı PyQt5/PyQt6/PySide2 spec'te koşulsuz `excludes`'tadır ve bunu bir
    lisans kapısı testi sınar). Sürüm **6.8.3'te sabittir** — üstü Pardus 21'de
    açılmaz (TB27). Duman testi karşılığı `packaging/linux/build.sh` adım 4b'dir:
    paketlenmiş dizinde `QtWebEngineProcess` ve Qt kitaplıkları yoksa derleme
    durur.

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
- **Dış istek yalnız kullanıcının başlattığı İKİ kapıdan çıkar** (T11, 23.09.2026):
  (1) güncelleme denetimi — "Denetle" düğmesiyle, `indir.okulapp.org`
  manifestinden (MEB ağında GitHub engellidir); (2) ISBN ile künye sorgusu
  (U13, tasarım §8.5) — ayarla açılır, **varsayılan kapalıdır**, her sorguyu
  kullanıcı başlatır ve dışarı yalnız normalize ISBN gider. **Açılışta ağ yok,
  telemetri yok, kişisel veri çıkmaz.** Açılışta, arka planda ya da toplu içe
  aktarımda dış istek atan kod eklenmez; Ağ Kataloğu hiçbir dış bağlantı açmaz.
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
| e-Okul aktarımı kimseyi "ayrıldı" yapmıyor, ayrılış da kaydı silmiyor | 22.09.2026 kullanıcı kararı: listede bulunmayan kişi **Ayrılış Havuzu**'na düşer, kararı kullanıcı verir; ayrılan kişinin iade etmediği kaynak olabileceği için kayıt kalır. Ayrılmış kayıtların temizliği F11 saklama taramasına bağlıdır | §14.1 F1 ekleri, TB16 |

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

**F0 İskelet — kapandı (21.09.2026, PR #1).** KS iskeletinin KD'ye çevrilmesi,
sınav ve ders modüllerinin sökümü, belgeler ve mevzuat metinleri, iki sunucu
iskeleti (katalog yalnız 127.0.0.1), bağımlılık zincirleri (segno, pystray),
`barcode128.py`, Inno yönetici kurulumu + kapatma olayı, tepsi, tek kopya
kanalı, `synchronous=FULL` + temiz kapanış işareti, kimlik kalıntı taraması.
Kod kapısı yeşil; **elle doğrulanacaklar** `packaging/windows/NOTLAR.md`'de
(tepsi simgesi, Çık, kurucunun açık programı kapatması, Pardus Qt tepsisi).

**F1 Çekirdek + güvenlik — kod tarafı bitti (22.09.2026).** Zorunlu yönetici
parolası ve parolasız dalın sökümü · fail-closed şifreli yazma
(`KeyMissingError`) · kör indeks (okul no) · güvenlik dosyası kayıp/okunamaz
kilidi ve çıkış yolları · `KipDurumu` + KipMiddleware + izin listesi + boşta ve
mutlak süre · Student/Personnel sadeleştirmesi (unvan ve branş yok, üye türü
var) · e-Okul mutabakatı ve **Ayrılış Havuzu** (aktarım kimseyi ayırmaz ve
silmez — 22.09.2026 kullanıcı kararı) · Holiday `SCHOOL_BREAK` + kapalı günler
ekranı · üç adımlı kurulum sihirbazı, kurtarma anahtarı çıktısı, doğrulaması ve
yenilemesi · Başlangıç Yol Haritası · katalog Excel şablonu ve sütun sözlüğü ·
kılavuz bölümleri. Tasarımdan sapmalar ve F1'de alınan kararlar: tasarım §14.1
**"F1 ekleri"**; kalan riskler `docs/teknik-borc.md` (TB16-TB19).

**F2 Katalog — kod tarafı bitti (23.09.2026).** `LibraryPolicy` (ödünç süresi
alanı YOK — Md. 18 sabit), `Section`, `Work`, `Copy`, `CopyCounter`,
`Acquisition`, `DonationIntake` + kalemleri, `CommissionDecision`,
`CatalogImportRun`, `LabelSheetTemplate` + `LabelCalibration` modelleri (tek
göç `0001_initial`) · Türkçe arama anahtarı ve üç eksenli TR sıralama
(`search_key`, `sort_key`, `author_sort_key`, `subject_sort_key`; katlama tek
kaynaktan — `apps/kutuphane/keys.py`) · ISBN normalleştirme ve ISBN-10 → 13
çevrimi (sağlama hatası kaydı ENGELLEMEZ, uyarı döner) · barkod ve kayıt no tek
sayaçtan, yıl `localdate()` ile, asla yeniden kullanılmaz · nüsha kuralları
(dijital kaynakta nüsha açılmaz, süreli yayın ciltliyse kayda girer,
`is_loanable` tek türetim + DB eşi `LOANABLE_Q`) · bağış ön kaydı ve komisyon
kararıyla toplu kataloglama (karar TÜRÜ denetlenir) · sayfalı `library/…`
uçları (hiçbiri görevli kipi izin listesinde DEĞİL) · Katalog, Eser Ayrıntısı,
Edinimler ve Bağışlar ekranları, Ayarlar'a Kütüphane Politikası ve Bölümler
sekmeleri · kılavuzun Katalog bölümü · sözlük §4. D2, D6, D7, D11 kapandı.
Tasarımdan sapmalar ve F2'de alınan kararlar: tasarım §14.1 **"F2 ekleri"**.

**F3 İçe aktarma — kod tarafı bitti (23.09.2026, PR #4).** Excel içe aktarma
(önizleme = uygulama, kovalar, içerik özetiyle fikirdeşlik) · AI JSON köprüsü ·
hızlı kayıt · ISBN ile künye getirme (U13, varsayılan kapalı) ve çevrimdışı künye
yolu. Sapmalar: tasarım §14.1 **"F3 ekleri"**.

**F4 Etiketler — kod tarafı bitti (24.09.2026).** Etiket motoru
(`apps/kutuphane/labels/`: sırt, barkod, boş barkod etiketi ve kalibrasyon
sayfası; Code128-C yazıcı noktasına hizalı, QR isteğe bağlı, 5 mm güvenli kenar
payı, tek belgede en çok 1.300 etiket) · iki basım işareti (sırt ve barkod ayrı)
ve basım partisi (D10: PDF basıldı değildir; onay, geri alma, yeniden basım) ·
basım sırası (D20) · doğrulama okutması · boş barkod aralığı ve Hızlı Kayıt'ta
etiket bağlama (önce etiket yolu) · Etiketler ekranı (şablon ve kalibrasyon
Ayarlar'da değil, Etiketler → Şablonlar ve Kalibrasyon'da) · kılavuzun Etiketler
bölümü. 24.09.2026 kullanıcı kararları: **doğrulama okutması görevli kipine açık
tek etiket ucudur** (`library-label-verify` POST, yanıt daraltılmış) ve **sırt +
barkod partisi geri alınınca doğrulanmış nüshanın iki işareti de korunur**.
Sapmalar ve kararlar: tasarım §14.1 **"F4 ekleri"**; gerçek yazıcı ve okuyucu
kanıtı F12'ye ertelendi.

**F5 Ağ kataloğu + tepsi — kod tarafı bitti (24.09.2026, dal
`f5-ag-katalogu`).** Katalog WSGI (`backend/katalog/`: yalnız stdlib +
`django.template`; `kd_katalog_*` görünümleri, `mode=ro` + eylem kodlu
authorizer, sayfalar ve tahta kipi, hız sınırı, bakım kapısı, waitress'in
Türkçe hata yanıtları) · `KatalogAyari` (varsayılan KAPALI; port ve IP'nin tek
kaynağı) · `desktop/katalog_kontrol.py` (T16), güvenlik duvarı denetimi, IP
adayları, IP başına 20 bağlantı, `kd-gunluk` gün değişimi kapısı (günlük yedek,
IP denetimi, uyku), tepsi kip matrisi, parolalı Çık (`app/quit/`), otomatik
başlatma ve kurucu görevleri · Ağ Doktoru, Ayarlar → Ağ Kataloğu, afiş, bilgi
notu, PYS talep metni, yer imi dosyaları · kılavuz ve `docs/ag-kurulumu.md`.
Kod kapısının iki ağ kanıtı (ikinci bilgisayardan arama, 50 istemcili yük)
`scripts/ag_katalogu_provasi.sh` ile iki Docker kabında üretilir ve gecelik
kapıda (`KD_YAVAS=1`) koşar. Bütünleştirme sonrası denetimin düzeltme turu
(F5 ekleri 19-30): güvenlik duvarı 4. maddesi bütün izin kurallarının
birleşimiyle; authorizer tam ad kümesiyle (TB31); saatlik damgasız işler
(kaybolan seçili IP, okunamayan denetimin yeniden denenmesi); Pardus komutu
kaynak sınırlı; açılamayan katalog her yüzeyden kapatılabilir; Inno
`[Registry]` yerleşimi (WebView2 dalı derlenmiyordu). Sapmalar, kararlar ve
ölçümler: tasarım §14.1 **"F5 ekleri"**; tahta, Windows paketi ve okul ağı
kanıtları F12'ye ertelendi. Açık kullanıcı kararları: güncelleme denetiminin
hedefi (F5 ekleri 15), Pardus taşınabilir arşivinde Ağ Kataloğu (F5 ekleri 27).

**F6 Üyelik + dolaşım — kod tarafı bitti (24.09.2026, dal `f6-dolasim`).**
`Membership` (öğrenci XOR personel, kişi başına tek aktif üyelik, kart no şifreli
+ kör indeks, sonlandırma nedeni kapalı listeden ve zorunlu), `IssuedCard`,
`CardRevocation`, `Loan` (bir nüshada tek açık ödünç; istisna ve kartsız
gerekçesi şifreli) — tek göç `0005_uyelik_ve_odunc` · kart no `9` + 6 rastgele
hane + Luhn, asla yeniden verilmez (`IssuedCard` + veri dizinindeki verilmiş kart
defteri — geri yükleme onu geri sarmaz) · kartı yenile, sonlandır, sil · şube
bazlı üyelik istek listesi · `services.circulation` §9 kurallarının tek yeri
(sayılar KİŞİ bazında; görevli kipinde üyeye bağlı retler nüshanın kimde
olduğundan ÖNCE) · dolaşım masası ve görevli ekranı (`ui/BarcodeInput` sıralı
kuyruk; kart okutma kilidi pencere değil şerit — iade kilitlenmez; pencere
açıkken okutmalar tampona alınır) · GA-7 iki kural (art arda 5 geçersiz; 10
dakikada 5 tanınmayan/iptal edilmiş, geçerli kart sıfırlamaz) · görevli izin
listesine beş masa ucu + katalog okuma (parametre kuralıyla; gövde yalnız UTF-8
JSON) · E2 üye kartı, E4 pusula + gecikmiş listesi, E13 aydınlatma metni, E19
masa kartı · pano: gecikmiş ödünç sayısı ve "Son Oturumu Kontrol Edin" (T15) ·
kılavuzun Üyelik ve Dolaşım Masası bölümleri, sözlük §4.10-4.11. D8, D9, D12,
D19, D21 kapandı. Sapmalar, kararlar ve düzeltme turu: tasarım §14.1 **"F6
ekleri"**; yeni kalan riskler TB32 (son sınıf tarihi), TB33 (veri dizini de
kaybolursa kart numarası), TB34 (görevli kipinde "bu üyede / başka üyede" ayrımı
korunur — 25.09.2026 kullanıcı kararı, F6 ekleri 26); `kip_sureleri()` F7'de
`LibraryPolicy`'ye bağlandı (F7 ekleri 10).

**F7 Teslim, kayıp, ilişik, yıl akışları — kod tarafı bitti (25.09.2026, dal
`f7-teslim`).** `Delivery` (şube XOR öğretmen, açık teslimde PROTECT, nüsha başına
tek açık teslim), `LossDamageCase` (sorumlu notu şifreli, bedel yalnız kayıt),
`CopyRepair` — tek göç `0006_teslim_kayip_onarim` · toplu teslim (TEK işlem, sayı
sınırı yok, belge no `<yıl>/<sıra>`), okutmayla geri alma (görevli kipine açık tek
F7 ucu `library-delivery-take-back`), E15 teslim listesi ve geri alma dökümü (oturumdan
ya da belge no'dan) · ödünç ile teslim arasında tek açık kayıt (nüsha durumunun
koşullu geçişi — `services.nusha_durumu`) · kayıp/hasar/onarım (D3 kapandı): Md. 19
kademe kapısı (bedel yolları yalnız ortaöğretimde, tahsilat yok), **bedel iki
adımdır** — "Bedel belirlendi"de kişinin açık işi sürer, "Bedel teslim alındı"da
biter (ilişikten çıkar, E5 basılır) ve dosya okulun açık işi olarak bedelle alıma dek
açık kalır (25.09.2026 kullanıcı kararı, F7 ekleri 26), kayıp bildirimi
ödünç/teslimi "Kayba dönüştü" ile kapatır, açık hasar dosyası da kayba dönüşür,
kayıttan düşme yalnız öneridir ve kayıp dosyasında "Bulundu" ile geri alınır · TMY
32/3 kapı noktası (`services.tmy_kapisi`; F7'de boş, kapsam çözüm türüne göre) · kişi
bağı tek kural (önce üyelik, yoksa teslim alan) · ilişik listesi (son sınıf → okuldan
ayrılan → diğerleri), E5 "Kütüphaneden ilişiği yoktur" belgesi (ön koşul diye
sunulmaz), E6 tutanak (gerçek uzunlukta tek sayfa) · Yıl Sonu ve Yıl Başı adım adım
ekranları (kayıt yazmaz; `year_rollover` yok) · kip süreleri `LibraryPolicy`'ye
bağlandı · kılavuz ve sözlük §4.12-4.13. Sapmalar, kararlar, düzeltme turu ve
kullanıcı kararı: tasarım §14.1 **"F7 ekleri"** (madde 14-26; düzelticinin iki
sapması — "Kayba dönüştü" ve TMY 32/3'ün daraltılmış kapsamı — onaylandı); bilinen
sınırlar (a)-(i). Okuyucuyla toplu teslim, görevli kipinde geri alma ve F7
belgelerinin gerçek yazıcı çıktısı F12'ye ertelendi.

**F8 Komisyon + ayıklama — kod tarafı bitti (25.09.2026, dal `f8-ayiklama`).**
`WeedingBatch` + `WeedingItem`, `RareWorksSubmission` + satırı, `AnnualLibraryReview` —
tek göç `0007_ayiklama_nadir_eser_yil_raporu` · ayıklama iki karardır: Seçim ve Ayıklama
Komisyonu kararı (Md. 12/1) ile harcama yetkilisi onayı (TMY 10/1-e, 28/4); durum
makinesi taslak → sunuldu → karar → onay → uygulandı, geri çekme ve iptal (D15) · **E7
tablosu tek kaynak** (`models.WEEDING_PATHS`; DB kısıtı + servis + `weeding/rules/`):
10/1-b gerekçeli kalem 28'e gidemez, devir yalnız düzeye uygunsuzlukla · yalnız raftaki
nüsha ayıklanır, nadir eser ayıklanamaz (D14), TMY 32/3 kapısı uygulamada · nüsha durumu
yalnız "Uygulandı"da değişir (terminal, yumuşak silme değil) · nadir eserler listesi
karara bağlı (D14); gönderilmiş ya da kararı bağlanmış listedeki işaret kaldırılamaz ·
bağış kararı → toplu katalog (edinim tarihi kabul tarihidir, katalogdaki esere bağlanır) ·
karar kullanımı (D7) · E7 (beş belge TMY yoluna göre, imha kalem düzeyinde), E8, E9
(kişisiz; eşik + tamamlayıcı gizleme; kazandırılan yalnız Md. 10/5), E16 · Ayıklama,
Nadir Eserler, Yıl Sonu Raporu ekranları, kılavuz ve sözlük §4.14. D7, D14, D15 kapandı.
Sapmalar, kararlar ve düzeltme turu: tasarım §14.1 **"F8 ekleri"** (madde 22-33: teklife ya
da nadir listesine girmiş nüsha silinemez, kararın tarihi ona dayanan kayıttan sonraya
alınamaz, geri çekilen teklife aynı karar yalnız kapsamındaki kalemlerle bağlanır, E9
tamamlayıcı gizleme). **25.09.2026 kullanıcı kararları** (F8 ekleri 13, 14, 34, 35; hepsi
uygulandı, açık karar yok): A8 kabul — cetvel üretilmez, karardan sonra **"Bağış
değerlendirme sonucu"** basılır (TMY'de "bağış kabul tutanağı" yoktur) · bedeli teslim
alınmış kayıp dosyasında ve "Bedelle başka eser alındı"dan sonra (nüsha kayıttan
düşülmemişse) **"Bulundu (bedel teslim alınmıştı)"**; bedelin iadesi okul yönetiminin
kararıdır, program para tutmaz · kayıp ve **hasar** dosyasının kayıttan düşme önerisi
ayıklamaya konmaz (ara belge düzeltmesi ve kalemin dosya bağı kalktı) · rapor dönemi
kuralı kalır, Yıl Sonu Raporu ekranı uyarır. E7-E9, E16'nın gerçek yazıcı çıktısı F12'ye
ertelendi.

**F9 Sayım — kod tarafı bitti (25.09.2026, dal `f9-sayim`).** `StockTake` + `StockTakeItem`
(kurul, durduran ve onaylayan harcama yetkilisi adları şifreli; kalem kişisiz), terminal durum
**"Hasar (kayıttan düşüldü)"** — tek göç `0008_sayim` · taslak → sürüyor (iki tur; 32/6) →
tamamlandı → onaylandı | iptal; aynı anda tek canlı sayım · başlatmada **anlık görüntü** ·
**iki AYRI seçenek**: TMY 32/3 durdurması (isteğe bağlı; kurulun talebi + harcama yetkilisinin
adı ve tarihi; `tmy_kapisi.ensure_open` doldu — edinim ve yeni nüsha, kayıttan düşme, devir,
kayıp bildirimi, kayıp dosyasının bulunma ve bedel adımları dışındaki çözümü, hasarda düşme
önerisi; programa aktarım da kapalı ama iletisi TMY'siz) ve **sayım için hizmet arası** (okul
kararı; yeni ödünç ve yeni teslim) · **iade ve teslimden geri alma hiçbir durumda durmaz**,
sayım sırasında kütüphaneye dönen nüsha "bulundu" · kilitler onaya ya da iptale dek (D17) ·
okutma kuyruğu (ISBN ve üye kartı yazılmaz, harfli kod yazılmaz; görevli kipinde de açık,
yanıt daralır), sayım fazlası `surplus_barcode`'da (D16) · kurulun ödünçteki, teslimdeki ve
onarımdaki nüsha seçimi (32/5'e kıyasen; şubede yerinde ya da toplanır — kayda göre değil,
23/6'ya kıyasen; onarımda sayım kurulunun kararı) · onay TEK işlem: noksan 32/7, hasar önerisi 27/1 + 10/1-e
komisyonsuz, LOST uzlaştırma, fazla TMY 17 ile tek edinimde; her noksan ve fazla onayda
YENİDEN doğrulanır · E10 Sayım tutanağı (PDF + XLSX; iki seçenek ve iade ayrı satırda, ödünç
alanın kimliği yok) + ek **"Taşınır Sayım ve Döküm Cetveline aktarılacak sayılar"** (34/1'in
dört büyüklüğü; cetvel TKYS'de) · Sayım ekranları, Genel Bakış kartı, bantlar, masa şeridi ·
kılavuzun Sayım bölümü, sözlük §4.15. **D1'in F9 kısmı, D4, D16, D17, D18 kapandı.** Sapmalar,
kararlar ve düzeltme turu (denetimin 22 bulgusu; madde 28-43: aynı gün onarımdan dönüş,
kayıp dosyasında temin, sayımda bağlanan boş etiketin ikinci kez kayda girmesi, harfli kodun
birleşmesi, kararsız fazlada kesinlik, tutanak taşması, pencerelerde okutma kaybı, masa şeridi,
Hızlı Kayıt ön denetimi, fazla kartının sayfalanması, dürüst dayanak metinleri): tasarım §14.1
**"F9 ekleri"**. **Kararlar (25.09.2026) uygulandı** (F9 ekleri madde 24-27 ve K1-K7, karar
turu madde 44-52; bekleyen karar yok): KULLANICI KARARI — sayım okutması görevli kipine açık
(izin listesine yalnız `library-stocktake-scan` POST; kişisiz masa durumu `library-desk-state`
GET), hizmet arası yeni teslimi de durdurur ve masada iki kipte açılışta görünür; ANA OTURUM
KARARI — ekte gelecek yıla devirden onayda 27/1 ile düşülen çıkarılır (madde 25 a), kayıp
dosyasında "Bulundu" 32/3 kapsamı dışında (K1), onarımdaki nüsha için kurul seçimi
`repair_basis` (K2), şubede "Kayda göre alınır" yok (K3), programa aktarım durdurmada kapalı
ama TMY'siz iletiyle (K4), ikinci turda fazla teyidi yok (K5), harfli eski etiket yazılmaz
(K7). E10'un gerçek yazıcı çıktısı ve sayım gününün kendisi F12'ye ertelendi.

Sıradaki: F10 Raporlar + dışa aktarım (kişisiz istatistik ve eşikli kırılımlar, Md. 7'nin 10.000
eşiği, çok okunanlar — k farklı üye, gün değişimi kapısına eklenir — + E12, E11 ciltsiz süreli
yayın hariç ve D1'in kalan kısmı 34/2-c + 34/3-a, E17, E20, sürümlü dışa aktarım şeması +
gidiş-dönüş, kişi dökümü, "Bakanlık sistemi kullanımda" hatırlatma ayarı). F10, F9'dan sayıma
**"yıl sonu sayımı" işaretini** üstlenir (F9 ekleri K6 KARAR — F10 sözleşmesine devredildi;
işaretsiz sayımın eki cetvele aktarılacak sayı basmaz). Tam tablo: tasarım §14.1. Saha hazırlık
hattı (S1-S15, kod dışı): §14.2.

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
| `docs/ag-kurulumu.md` | BTR için ağ kılavuzu (güvenlik duvarı, adres, tahtalar, sınama) |
| `docs/disa-aktarim.md` | *(F10)* sürümlü dışa aktarım şeması |
| `packaging/windows/NOTLAR.md` | Windows paketinde doğrulanmamış varsayımlar |
| `README.md` | Kısa tanıtım |

---

## 9. Diğer ajanlar

Claude dışındaki ajanlar (Codex vb.) için depo kökündeki `AGENTS.md` bu
dosyaya işaret eder. Brifing iki yerde tutulmaz; yalnız bu dosya güncellenir.
