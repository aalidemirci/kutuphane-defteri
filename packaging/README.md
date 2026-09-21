# packaging/ — paket üretimi

Kullanıcıya yönelik kurulum kılavuzu: **`docs/kurulum.md`**.
Bu dosya paketi ÜRETEN kişi içindir. Hat kardeş proje KS'den devralındı
(tasarım §12 AYNEN/UYARLA); Kütüphane Defteri adıyla henüz hiçbir paket
koşusu yapılmadı.

## Dosya haritası

```
packaging/
├── requirements-paketleme.txt   PyInstaller + pywebview + (Windows) pythonnet,
│                                pystray, six + (Linux) PyQt5
├── pyinstaller/
│   ├── kutuphane_defteri.spec   Windows + Linux ORTAK spec
│   ├── giris.py                 paket giriş noktası + teşhis kipleri
│   │                            (`--pdf-duman`, `--bagimlilik-duman`)
│   ├── rthook_kd.py             çalışma-zamanı kancası (DLL/fontconfig/SPA yolu)
│   ├── fonts.conf.tmpl          Windows fontconfig şablonu (gömülü DejaVu)
│   └── fonts.paket.conf         paket içi fontconfig — build.ps1 adım 4b bunu
│                                `_internal/etc/fonts/fonts.conf` üzerine kopyalar
├── fontlar/                     DejaVu Sans 4 kesim + lisans (pakete gömülür)
├── ikonlar/                     logo_uret.py + ikon_uret.py + PNG kesimleri + .ico
├── depo_sizintisi.py            depoda kişisel veri denetimi (KVKK kapısı)
├── veri_sizintisi.py            dağıtım paketinde kişisel veri denetimi
├── linux/
│   ├── docker-build.sh          HOST'tan çalıştırılan sarmalayıcı  ← BURADAN BAŞLA
│   ├── build.sh                 kap İÇİNDE koşan asıl derleme
│   ├── test-kurulum.sh          debian:11 + debian:12 kurulum provası
│   ├── kap-ici-test.sh          prova kabının içinde koşan betik
│   ├── apt_dene.sh              apt ayna tutarsızlığı sarmalı
│   ├── debian-control.tmpl      .deb üstverisi (@VERSION@/@SIZE@/@DEPENDS@)
│   ├── postinst / prerm         bakım betikleri (ASCII — aşağıdaki nota bakın)
│   ├── kutuphane-defteri.desktop menü kaydı
│   ├── kur.sh / kaldir.sh       taşınabilir .tar.gz kurucusu
│   └── BENIOKU.txt              .tar.gz içindeki kullanıcı notu
└── windows/
    ├── build.ps1                DLL kapanışı + PyInstaller + duman testi + Inno
    ├── dll_kapanisi.py          ntldd/objdump ile WeasyPrint DLL kapanışı
    ├── kutuphane-defteri.iss    Inno Setup (yönetici kurulumu — U4)
    └── NOTLAR.md                DOĞRULANMAMIŞ varsayımlar + ilk koşu çek-listesi
```

## Linux paketi üretme

```bash
docker compose run --rm frontend npm run build     # frontend/dist şart
bash packaging/linux/docker-build.sh               # .deb + .tar.gz
bash packaging/linux/test-kurulum.sh               # debian:11 + debian:12 provası
```

Hızlı doğrulama derlemesi (PyQt5 indirilmez; pencere açılmaz, yalnız
`--autotest`/`--pdf-duman`/`--bagimlilik-duman` çalışır):

```bash
KD_WITH_QT=0 bash packaging/linux/docker-build.sh
```

Çıktılar `dist/cikti/` altındadır (`dist/` .gitignore'da). Derleme kabı
bilinçli olarak `python:3.12-bullseye`'dır: glibc 2.31 = Pardus 21 tabanı.

## Windows paketi üretme

Windows paketi **ancak bir Windows makinede veya CI'da** üretilebilir.
Adımlar ve doğrulanmamış varsayımlar: `packaging/windows/NOTLAR.md`.

Kurucu **yönetici kurulumudur** (tasarım §2.1 U4): Program Files'a kurulur,
her kurulum ve güncelleme UAC'de yönetici kimliği ister. Güvenlik duvarı
kuralı ve otomatik başlatma görevi sonraki fazların işidir (tasarım §4.5, §5.7).
Kurucu ve kaldırıcı `AppMutex` KULLANMAZ: `[Code]` içindeki
`InitializeSetup`/`InitializeUninstall` çalışan programa `KutuphaneDefteri.Kapat`
olayını gönderir ve iki mutex serbest kalana dek en çok 30 sn bekler (tasarım
§4.2-5; doğrulama çek-listesi `packaging/windows/NOTLAR.md`).

## Duman testleri

Paketlenmiş ikili her derlemede iki teşhis kipiyle sınanır (`giris.py`):

* `--bagimlilik-duman` — `RUNTIME_MODULES`'ın tamamını, Windows'ta ek olarak
  `DESKTOP_RUNTIME_MODULES`'ı (pystray, six, `clr`) import eder.
* `--pdf-duman [dosya.pdf]` — evrakın taban şablonundan
  (`backend/templates/documents/base.html`) küçük bir Türkçe örnek belge
  üretir; şablon ağacının pakette olduğunu, WeasyPrint zincirini, Türkçe
  harfleri ve gömülü DejaVu fontunu doğrular.

## Sürüm

Tek doğruluk kaynağı depo kökündeki **`VERSION`** dosyasıdır (CalVer:
`YYYY.M.N`). Ön-sürüm ekleri şu sırayla ilerler:

    -alpha.N  →  -beta.N  →  -rc.N  →  (ek yok: kesin sürüm)

Sıra `version_key` ile uyumludur: ekin rakam öbekleri sayı, gerisi metin
olarak karşılaştırılır (`beta.10` > `beta.9`), ön-sürüm kesin sürümden önce
gelir. **`-dev` hatta kullanılmaz**: metin olarak `beta`dan sonra geldiği için
`dev` → `beta` geçişi sürüm düşüşü sayılır ve veri damgası "daha yeni sürümle
yazılmış" diye programı açtırmaz. `desktop/version.py` ile
`backend/apps/okul/services/updates.py` içindeki iki `version_key` kopyası aynı
kalmalıdır. Buradan türetilenler:

* paketlenmiş uygulamanın sürüm damgası (`desktop/version.py`),
* `.deb` sürümü — `-` yerine `~` konur (`2026.9.0-alpha.0` →
  `2026.9.0~alpha.0`), çünkü Debian sıralamasında `~` kesin sürümden ÖNCE gelir,
* Windows sürüm kaynağı — yalnız sayı kısmı (`2026.9.0.0`),
* artefakt dosya adları,
* `v*` etiketi ile GitHub Release (ön-sürüm eki taşıyan etiket "prerelease").

## apt komutları ayna tutarsızlığına karşı sarmalı

Linux tarafındaki her `apt-get install`, `packaging/linux/apt_dene.sh` içindeki
`apt_dene` sarmalından geçer: başarısızlıkta `/var/lib/apt/lists/*` silinir ve
artan beklemeyle üç kez denenir. Debian 11 güvenlik deposu tarihli arşive
sabitlenir (bullseye LTS 31.08.2026'da bitti). Gerekçeler ve KS'deki vakalar
betiğin başlığındadır; davranış `packaging/tests/test_apt_dene.py` ile
sabitlenir.

## Yayın hattı (etiket push'undan sonra)

`v*` etiketi `paketleme.yml`'nin `yayin` işini tetikler; iş sırasıyla
`SHA256SUMS.txt` üretir, GitHub Release'i açar ve paketleri **Cloudflare R2**
kovasına (`okulapp-indirme/kutuphane-defteri/`) yükler — okullar siteden
indirir, MEB ağında GitHub sık sık engellidir. Kovadaki `SHA256SUMS` dosyası
SÜRÜMLÜ adla yazılır (`SHA256SUMS-<sürüm>.txt`).

R2 adımı iki secret ister — `CLOUDFLARE_API_TOKEN` (R2 *Object Read & Write*
izni) ve `CLOUDFLARE_ACCOUNT_ID`. Tanımlı değilse adım uyarı basıp ATLANIR;
yeşil koşu o durumda "paketler indirme alanında" demek DEĞİLDİR.

Yükleme sonrası elle kalan iş, `okulapp.org` deposundaki
`src/data/kd-release.json` dosyasını güncellemektir (tasarım §17 — ortak yayın
alanı kuralları). Uygulamanın okuyacağı `manifest.json` (tasarım §2.2 T11) henüz
üretilmiyor.

Etiket, push ve R2 yüklemesi dışa açık işlerdir; **kullanıcı onaylı adımlardır**
(tasarım §14.1).

## İki dil kuralı

* **Python tanımlayıcıları İngilizce** (depo geneliyle aynı), yorumlar ve
  kullanıcıya görünen iletiler Türkçe.
* **Kabuk betikleri**: değişken adları Türkçe, çıktılar Türkçe.
* **`postinst`/`prerm` ASCII'dir.** Bu iki dosya `/bin/sh` (dash) ile çalışır;
  dash'in ASCII-dışı bayt davranışı dağıtımdan dağıtıma değiştiği için bakım
  betiklerinde Türkçe karakter kullanılmaz (`test_betik_kodlamasi.py` kapısı).
* **`.ps1` dosyaları UTF-8 BOM taşır.** PowerShell 5.1 BOM'suz dosyayı ANSI
  sanıp Türkçe karakterleri bozar (aynı test dosyası).

## Yeni bir üçüncü taraf bağımlılık eklerken

`backend/` ağacı pakete **kaynak dosya** olarak kopyalanır; PyInstaller'ın
statik çözümleyicisi orayı TARAMAZ. Backend yeni bir üçüncü taraf paket import
ediyorsa dört halka birlikte güncellenir:

1. `backend/requirements.txt` (pin),
2. `packaging/tests/test_spec_kapsami.py::DAGITIM_IMPORT_ESLEME`,
3. `kutuphane_defteri.spec` → `hiddenimports`,
4. `giris.py` → `RUNTIME_MODULES`.

Testler halkalardan biri eksikse kırılır. Gerekçe ve ayrıntı spec dosyasının
başındaki açıklamada.

## Masaüstü zinciri (yalnız kabuğun bağımlılıkları)

Backend'in değil **masaüstü kabuğunun** ihtiyaç duyduğu paketler (Windows
tepsisi için pystray ve six, WebView2 köprüsü için pythonnet) backend
zincirine girmez; ayrı zincirdedir (tasarım §4.5, denetim UY-6):

1. `requirements-paketleme.txt` — pin + `; sys_platform == "win32"` işareti,
2. `test_spec_kapsami.py::PAKETLEME_IMPORT_ESLEME` (dağıtım → modül),
3. spec'in `if WINDOWS:` bloğu — `collect_submodules("pystray")`, `six`,
   `six.moves`, `PIL.ImageDraw`, `PIL.IcoImagePlugin` (okulzili emsali),
4. `giris.py::DESKTOP_RUNTIME_MODULES` — `--bagimlilik-duman` bu listeyi
   yalnız Windows'ta import eder.

Test win32 işaretli satırlarla `DESKTOP_RUNTIME_MODULES`'ı eşitler. Linux
işaretli Qt paketleri listeye bilerek girmez: `KD_WITH_QT=0` doğrulama
derlemesi Qt'yi kurmaz. Yeni bir platform işaretli paket testi kırar ve
bilinçli karar ister.

### Lisans: pystray LGPLv3

pystray **LGPLv3**'tür (six MIT). Dağıtılan pakete pystray'in **lisans metni
ve kaynağı** girer. **Uygulaması F12'dedir**; bugün pakete lisans dosyası
gömülmez, indirilmez.

İzlenecek yol okulzili'nin yaklaşımıdır:

* Depo kökünde `THIRD_PARTY_LICENSES/` dizini bulunur. İçinde
  `pystray-COPYING.txt` (GPLv3 metni; LGPLv3 onun üzerine kurulur),
  `pystray-COPYING.LGPL.txt` ve `six-LICENSE.txt` yer alır. Dizin spec'te
  `datas` ile olduğu gibi pakete kopyalanır.
* Bir bağımlılık tablosu tutulur (okulzili'de `BAGIMLILIKLAR.md`): bileşen,
  sürüm, kullanım ve lisans.
* pystray'in kaynağı pakete girer. F12'de PyInstaller'ın PYZ arşivi yerine
  pystray'i `.py` olarak toplaması (`module_collection_mode`) ya da kaynak
  arşivinin pakete konması seçenekleri değerlendirilir.

Önerilen F12 denetimi: `build.ps1` paketlenmiş dizinde lisans dosyalarını ve
pystray kaynağını arar, bulamazsa derlemeyi durdurur.
