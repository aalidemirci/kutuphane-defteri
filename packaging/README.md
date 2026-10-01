# packaging/ — paket üretimi

Kullanıcıya yönelik kurulum kılavuzu: **`docs/kurulum.md`**.
Bu dosya paketi ÜRETEN kişi içindir. Hat kardeş proje KS'den devralındı
(tasarım §12 AYNEN/UYARLA); Kütüphane Defteri adıyla CI paket hattı F4'ten
(24.09.2026) bu yana her faz PR'ında yeşildir (Linux .deb + debian:11/12
kurulum provası, Windows setup.exe + portable.zip). Kurucular sahada henüz
çalıştırılmadı (`docs/saha-kabulu.md`).

## Dosya haritası

```
packaging/
├── requirements-paketleme.txt   PyInstaller + pywebview + (Windows) pythonnet,
│                                pystray, six + (Linux) qtpy, PySide6
├── pyinstaller/
│   ├── kutuphane_defteri.spec   Windows + Linux ORTAK spec
│   ├── giris.py                 paket giriş noktası + teşhis kipleri
│   │                            (`--pdf-duman`, `--bagimlilik-duman`)
│   ├── rthook_kd.py             çalışma-zamanı kancası (DLL/fontconfig/SPA yolu)
│   ├── fonts.conf.tmpl          Windows fontconfig şablonu (gömülü DejaVu)
│   └── fonts.paket.conf         paket içi fontconfig — spec bunu (Windows)
│                                `_internal/etc/fonts/fonts.conf` adıyla koyar
├── fontlar/                     DejaVu Sans 4 kesim + lisans (pakete gömülür)
├── ikonlar/                     program simgesi ("Raf ve etiket", 29.09.2026) — çıktılar
│   │                            depodadır, derleme ikon üretmez
│   ├── logo_uret.py             ana çizim (1024) + elle çizilmiş 16/24/32 kesimleri
│   └── ikon_uret.py             48+ kesimler, .ico (her boyut kendi karesiyle),
│                                frontend/public/app-logo.png; `--site DOSYA` yalnız
│                                okulapp.org görselini yazar; testi test_ikonlar.py
├── depo_sizintisi.py            depoda kişisel veri denetimi (KVKK kapısı)
├── veri_sizintisi.py            dağıtım paketinde kişisel veri denetimi
│                                (paket dizini + son arşivler .zip/.deb/.tar.gz)
├── lisanslar/                   üçüncü taraf lisansları (F12, TB28)
│   ├── lisanslar.py             `uret` (depodaki THIRD_PARTY_LICENSES/),
│   │                            `paket` (derleme sonrası lisans kapısı),
│   │                            `deb-copyright` (DEP-5)
│   ├── on_yuz_paketleri.mjs     Vite çıktısına giren npm paketleri
│   └── uret.sh                  ikisini Docker'da koşan sarmalayıcı
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
    ├── paket_kapanisi.py        paketin statik DLL kapanışı (PE içe aktarmaları)
    ├── kutuphane-defteri.iss    Inno Setup (yönetici kurulumu — U4)
    └── NOTLAR.md                DOĞRULANMAMIŞ varsayımlar + ilk koşu çek-listesi
```

## Linux paketi üretme

```bash
docker compose run --rm frontend npm run build     # frontend/dist şart ve güncel olmalı
bash packaging/linux/docker-build.sh               # .deb + .tar.gz
bash packaging/linux/test-kurulum.sh               # debian:11 + debian:12 provası
```

Hızlı doğrulama derlemesi (PySide6 indirilmez; pencere açılmaz, yalnız
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
kuralı ve otomatik başlatma görevi kurucunun isteğe bağlı görevleridir (F5;
tasarım §4.5, §5.7). Lisans sayfası `LICENSE.txt`, üçüncü taraf lisansları
`{app}\THIRD_PARTY_LICENSES\` (F12). Kurucu ve kaldırıcı `AppMutex` KULLANMAZ: `[Code]` içindeki
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

**İlk sürüm beta'dır** (F12, kullanıcı kararı 3 — 27.09.2026): `VERSION`
`2026.10.0-beta.1`'e hazırlandı (`.deb` `2026.10.0~beta.1`, Windows sürüm
kaynağı `2026.10.0.0`). Etiketi (`v2026.10.0-beta.1`) F12 birleşince ana oturum
**kullanıcı onayıyla** atar. Güncelleme denetimi kararlı sürüm kullanan okula
ön-sürüm ÖNERMEZ; beta kullanıcısı sonraki betayı ve kararlı sürümü alır
(`updates.offered`). Yayın adımlarının kendisi (etiket ↔ VERSION kapısı, `~` →
`.`, pre-release işareti, R2'nin secret'sız atlanması ve `r2-yukle.sh` ile
yüklenmesi) ve sonradan yükleme işi (`r2-yukle.yml`) sahte `gh`/`npx` ile
`packaging/tests/test_surum_yolu.py`'de koşturulur — `yayin` işi yalnız etikette,
`r2-yukle.yml` yalnız elle koştuğu için PR kapıları onları başka türlü görmez.

## apt komutları ayna tutarsızlığına karşı sarmalı

Linux tarafındaki her `apt-get install`, `packaging/linux/apt_dene.sh` içindeki
`apt_dene` sarmalından geçer: başarısızlıkta `/var/lib/apt/lists/*` silinir ve
artan beklemeyle üç kez denenir. Debian 11 güvenlik deposu tarihli arşive
sabitlenir (bullseye LTS 31.08.2026'da bitti). Gerekçeler ve KS'deki vakalar
betiğin başlığındadır; davranış `packaging/tests/test_apt_dene.py` ile
sabitlenir.

## Yayın hattı (etiket push'undan sonra)

`v*` etiketi `paketleme.yml`'nin `yayin` işini tetikler; iş sırasıyla
yayımlanacak son paketleri `veri_sizintisi.py` ile bir kez daha denetler,
`SHA256SUMS.txt` üretir, GitHub Release'i açar ve paketleri **Cloudflare R2**
kovasına (`okulapp-indirme/kutuphane-defteri/`) yükler — okullar siteden
indirir, MEB ağında GitHub sık sık engellidir. Paketler kovaya Release'teki
adlarıyla gider (beta `.deb`'inin adında `~` değil `.` vardır); kovadaki
`SHA256SUMS` dosyası SÜRÜMLÜ adla yazılır (`SHA256SUMS-<sürüm>.txt`), çünkü
kovada eski sürümlerin paketleri de durur.

Yükleme mantığı **tek yerdedir**: `packaging/r2-yukle.sh` (kova, önek, adlar,
içerik türleri). Yayın işi de, var olan Release'i sonradan yükleyen
`r2-yukle.yml` de bu betiği çağırır. Betik yüklemeden önce `SHA256SUMS.txt`'yi
doğrular: özet tutmazsa, özette olmayan ya da türü bilinmeyen bir dosya varsa
HİÇBİR dosya yüklenmez ve adım kırmızı olur. Özet en son yüklenir (kovada özet
görünüyorsa paketleri de oradadır). Davranışı sahte `gh`/`npx` ile
`packaging/tests/test_surum_yolu.py` sınar.

**Boyut sınırı.** wrangler `r2 object put` tek parçada en çok 300 MiB yükler
(Cloudflare "Upload objects": "up to 315 MB"). Sınırı aşan bir paket varken betik
yine HİÇBİR dosya yüklemez. `v2026.10.0-beta.1`'in en büyüğü Linux arşiviydi
(247.424.211 bayt, ~236 MiB). Paket sınırı aşarsa yükleme çok parçalı S3 yoluna
(rclone ya da `aws s3`, R2 S3 erişim anahtarlarıyla) taşınmalıdır; bu bugün
betikte yoktur.

### R2 secret'ları

R2 adımı iki depo secret'ı ister:

| Secret | İçerik |
|---|---|
| `CLOUDFLARE_API_TOKEN` | R2 API token'ı, izni **Admin Read & Write** |
| `CLOUDFLARE_ACCOUNT_ID` | Kovanın bulunduğu Cloudflare hesabının kimliği |

*Object Read & Write* YETMEZ: wrangler `r2 object put` Cloudflare REST API'siyle
çalışır ve object-düzeyi token REST'te 403 (kod 10000 "Authentication error")
ile reddedilir. DD hattında 28.09.2026'da tam böyle kırıldı ve Admin Read &
Write token'la uçtan uca yeşil doğrulandı; KS belgeleri de aynı gün düzeltildi
(Cloudflare: developers.cloudflare.com/r2/platform/troubleshooting). Kova
(`okulapp-indirme`) kardeş programlarla ortaktır, önek ayrımı kovanın içindedir:
DD'nin kullandığı token ve hesap kimliği burada da geçerlidir.

Tanımlı değilse yayın işindeki adım, sürüme ve dizine bakmadan uyarı basıp ATLANIR
(secret'ı olmayan bir çatalda da sürüm çıkabilmeli; betik kimliği ilk denetler);
yeşil koşu o durumda "paketler indirme alanında" demek DEĞİLDİR.

Eklemek hesap sahibinin işidir. Değer komut satırına, betiğe, belgeye ya da
sohbete **yazılmaz**: `gh` değeri kendisi sorar, kabuk geçmişine düşmez.

```bash
gh secret set CLOUDFLARE_ACCOUNT_ID --repo aalidemirci/kutuphane-defteri
gh secret set CLOUDFLARE_API_TOKEN  --repo aalidemirci/kutuphane-defteri
gh secret list --repo aalidemirci/kutuphane-defteri   # yalnız adlar ve tarihler görünür
```

GitHub secret'ları geri okunamaz: DD deposundaki değer oradan kopyalanamaz,
token'ın saklandığı yerden alınır. Elde yoksa Cloudflare panelinde R2 → API
token'larını yönet → **yeni** token (izin Admin Read & Write; secret'a yazılan,
oluşturulunca bir kez gösterilen *Token value*'dur, S3 erişim anahtarları
değil). Var olan token'ı yeniden üretmek ("roll") DD'nin kopyasını geçersiz
kılar. Hesap kimliği panelde R2 genel bakış sayfasında görünür.

### R2 adımı atlandıysa ya da kırıldıysa

Paketleri yeniden üretmeye gerek yok: Actions → **R2'ye yükle** → "Run
workflow" → **etiket** = `v<VERSION>` (ör. `v2026.10.0-beta.1`). İş
(`.github/workflows/r2-yukle.yml`) var olan Release'in dosyalarını
`gh release download` ile indirir ve aynı betikle yükler. Burada kimlik
**zorunludur**: secret yoksa iş kırmızı biter, hiçbir şey yüklemeden yeşil
bitmez. Komut satırından:

```bash
gh workflow run r2-yukle.yml --repo aalidemirci/kutuphane-defteri -f etiket=v<VERSION>
```

Elle tetiklenen iş akışı GitHub'da yalnız varsayılan dalda (`main`) bulunduğunda
görünür. İlk beta (`v2026.10.0-beta.1`) secret'lar tanımlanmadan çıktı; R2'ye bu
yolla yüklenir. Yüklemeden sonra beş dosya için
`curl -sI https://indir.okulapp.org/kutuphane-defteri/<ad>` → 200 ve
`Content-Length` Release'teki boyutla aynı olmalıdır (özet dosyasının adı
`SHA256SUMS-<sürüm>.txt`).

### Yüklemeden sonra: site

Yükleme sonrası elle kalan iş, `okulapp.org` deposundaki
`src/data/kd-release.json` dosyasını güncellemektir (tasarım §17 — ortak yayın
alanı kuralları). Program güncellemeyi GitHub Release'ten denetler; R2'deki
paketler elle indirme içindir ve program oraya istek atmaz, bu yüzden bir
`manifest.json` üretilmez (tasarım §2.2 T11 v4, 27.09.2026 kullanıcı kararı).

Sitedeki İndir düğmeleri `kd-release.json` `"available": true` iken basılır. Bu
bayrak, beş adres 200 dönüp `Content-Length` Release'teki boyutla tutmadan `true`
yapılmaz: site dalı R2'den önce birleşirse canlıda kırık İndir düğmesi çıkardı
(30.09.2026: sürüm verisi dolduruldu, bayrak R2 yüklemesine dek `false`).

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

**Beşinci adım — lisans listesi (F12, TB28).** Python ya da npm bağımlılığı
eklenince, çıkınca ya da sürümü değişince `bash packaging/lisanslar/uret.sh`
koşulur (Docker, ağ gerekir) ve `THIRD_PARTY_LICENSES/` farkı gözden geçirilip
işlenir. `packaging/tests/test_lisans_kapisi.py` her pini, çalışma zamanı
kapanışını ve `frontend/package.json` bağımlılıklarını listeyle karşılaştırır;
derlemede `lisanslar.py paket` listede olmayan dağıtımı pakette bulursa
derlemeyi durdurur. Lisansı yalnız GPL olan bileşen pakete giremez.

## Lisanslar ve THIRD_PARTY_LICENSES (F12)

Programın lisansı PolyForm Noncommercial 1.0.0'dır (`LICENSE`). Pakete giren
her üçüncü taraf bileşenin adı, sürümü, lisansı ve lisans METNİ depo kökündeki
**`THIRD_PARTY_LICENSES/`** dizinindedir: `BENIOKU.txt` (Türkçe dizin + LGPL
kaynak erişimi ve yazılı teklif), `bilesenler.json` (makine okunur) ve bileşen başına lisans
dosyaları. Dizin **elle yazılmaz**, `packaging/lisanslar/uret.sh` üretir:

1. ön yüz kabında Vite derlemesi YAZMADAN koşar ve çıktıya gerçekten giren npm
   paketlerini toplar (ağaç sarsmayla düşenler girmez; Tailwind'in ürettiği CSS
   ve Vite'ın çalışma anı yardımcıları dahil — `on_yuz_paketleri.mjs`);
2. backend kabında backend + paketleme pinlerinin bağımlılık kapanışını İKİ
   platform için (`sys_platform` işaretleriyle) çözer; lisans dosyaları kurulu
   dağıtımdan, yoksa PyPI'daki tekerlekten ya da kaynak arşivinden okunur.
   PySide6 tekerlekleri lisans metni taşımaz: ortak LGPL-3.0/GPL-3.0 metni
   verilir. Python çalışma zamanı, DejaVu, WebView2 SDK (NuGet'teki lisans),
   Evergreen önyükleyicisi notu, Qt ile ayrı kitaplık olarak gelen ICU 73.2
   (lisans metni ICU'nun etiketinden) ve Qt kitaplıklarına derlenmiş üçüncü taraf
   kodun (Chromium dahil) bildirim adresleri elle tanımlı bileşenlerdir. Beta'da
   Qt/Chromium bildirimleri adresle verilir (KULLANICI KARARI 28.09.2026, KB-3 (a));
   kararlı sürümden önce üretici bildirim METNİNİ Qt 6.8.3 kaynak arşivindeki
   `qt_attribution.json` dosyalarından üretir (KB-3 (b), `docs/teknik-borc.md` TB28).

**Derlemede** (`build.ps1`, `build.sh`, PyInstaller'dan hemen sonra)
`lisanslar.py paket`: dizini ve `LICENSE.txt`'yi paket köküne koyar (Windows'ta
BOM'lu — Inno `LicenseFile`), PyInstaller'ın SON aşama TOC dosyalarından (COLLECT,
PYZ, PKG, EXE — spec süzgeçlerinden sonraki hâl; Analysis TOC'u okunmaz) pakete giren
her dosyanın sahibini bulur ve şunlarda derlemeyi DURDURUR: listede olmayan Python
dağıtımı; sahibi bilinmeyen dosya; yalnız GPL'li yerel kütüphane (readline,
gdbm); PyInstaller'ın gömülemeyen derleme kodu (yalnız önyükleyici, `loader/`,
`rthooks/`, `fake-modules/` girebilir); süzülmemiş pyphen sözlükleri; pakette
olmayan pystray kaynağı; Windows'un Universal CRT'si (`ucrtbase.dll`,
`api-ms-win-*.dll` — Windows 10/11'in bileşeni, pakete girmez). Paketle gelen sistem kütüphanelerinin lisans ve telif
dosyaları (Windows'ta MSYS2 paket veritabanından, Linux'ta dpkg +
`/usr/share/doc/<paket>/copyright`) kaynak kod adresleriyle
`THIRD_PARTY_LICENSES/yerel-kutuphaneler/` altına, pakette gerçekten bulunan
bileşenlerin listesi `paket-icerigi.txt`'ye yazılır.

27.09.2026 yerel Linux derlemesinin bulguları (hepsi giderildi, denetim artık
yakalar): stdlib `readline` eklentisi GPL-3.0'lı `libreadline.so.8`'i pakete
taşıyordu (spec `excludes`); pywebview'ın kendi PyInstaller kancası
`collect_submodules("webview")` ile toplanıp PyInstaller'ın GPL-2.0+ derleme
kodunu ve altgraph'ı pakete sürüklüyordu (süzgeç); hook-pyphen bir kısmı yalnız
GPL olan bütün heceleme sözlüklerini topluyordu (yalnız en_US kalır). O gün Qt'li
yerel derleme denetimden "geçti" ama denetim o tarihte Qt'yi yalnız DAĞITIM
etiketiyle (PySide6_Addons: "LGPL-3.0-only OR GPL-…") değerlendiriyordu: paket, Qt'nin
açık kaynak sürümünde YALNIZ GPL-3.0 ile sunulan modüllerini (Charts, Data
Visualization, Graphs, Quick 3D, Quick Timeline, Virtual Keyboard, Wayland Compositor;
22 kitaplık, QML eklentileri ve `QtDataVisualization` bağlayıcısı, ~29 MB) taşıyordu.
**F12 düzeltme turu (28.09.2026):** spec bunları `lisanslar.qt_gpl_suz` ile ayıklar (ada
göre ve DT_NEEDED kapanışıyla — örneğin Virtual Keyboard'un giriş eklentisi ve Quick 3D'nin
profil eklentisi adında modül adı taşımaz); `lisanslar.py paket` aynı kuralı paketin
diskteki hâlinde dosya düzeyinde sınar, `kap-ici-test.sh` kurulu pakette bir kez daha
arar. Program bu modüllerin hiçbirini kullanmaz (pencere QtWebEngineWidgets'tır). Qt'nin
LGPL'li modülleri pakette kalır. Windows tarafı (MSYS2 veritabanı ve SPDX lisans
değerlendirmesi, BOM'lu lisans sayfası, pip kısıt dosyası) ilk CI koşusunda doğrulanır
(`packaging/windows/NOTLAR.md` W21-W26).

**İlk CI Windows koşusunun bulguları (29.09.2026, PR #9; hepsi giderildi, denetim artık
yakalar):** (A) PyInstaller 6.11 Universal CRT adlarını `_win_includes` listesinde tutar ve
python312.dll'in bağımlılığını PATH'te bulduğu ilk kopyadan toplar — koşucunun PATH'indeki
Temurin JDK'sından `ucrtbase.dll` + 42 `api-ms-win-*.dll` girdi. UCRT Windows 10/11'in
bileşenidir, uygulama klasöründeki kopya kullanılmaz (Microsoft Learn, "Universal CRT
deployment"): spec `lisanslar.ucrt_suz` ile ayıklar, `build.ps1` PyInstaller'ı yalın PATH'le
koşar, Inno `MinVersion=10.0`. (B) hooks-contrib `hook-weasyprint` `libfontconfig-1.dll`'in
yanındaki MSYS2 `etc/fonts` ağacını pakete koyar; MSYS2 veritabanı yalnız DLL yollarını
tutuyordu. Artık %FILES%'teki her TAM yol sahiplenilir; DLL dışı dosyada içerik pacman'ın
`mtree` sha256 özetiyle doğrulanır (önek ya da desen kuralı yok). (C) Koşucunun varsayılan
Python'unda (setup-python'ın seçtiği aynı kurulum) pipx ve Windows bağımlılığı colorama
kuruluydu; Django colorama'yı koşullu import ettiği için pakete girdi. `build.ps1` artık
yalıtılmış sanal ortamda (`dist\_venv-win`) derler; colorama hiçbir pinin kapanışında
olmadığı için listeye EKLENMEDİ. Aynı koşuda `packaging` Windows paketine girdi ama liste onu
yalnız Linux'ta biliyordu: setuptools vendored bağımlılıklarının KURULU olanını tercih eder,
`packaging` PyInstaller'ın bağımlılığı olarak her ortamda kuruludur — üretici bunu
`KURULUYU_TERCIH_EDEN` kuralıyla (setuptools `core` eki ∩ paket ortamının kapanışı) iki
platform için ayrı çözer. (D) pywebview'ın kendi kancası Windows'ta `webview/lib`'i Analysis
sırasında topladığı için spec girdi süzgeci Android arşivini kaçırıyordu: `_webview_platform_disi`
Analysis'ten sonra da uygulanır.

**Aynı günün doğrulama turu (29.09.2026):** (1) Sanal ortam depo içinde durduğu için
(`dist\_venv-win`) denetim, depo kuralını site-packages'tan önce sınayıp sanal ortamın
RECORD'suz dosyasını sessizce "proje dosyası" sayıyordu; artık dosyayı kapsayan EN DAR kök
sınıfı belirler (`_en_dar_sinif`), dizinler `python_dizinleri` ile hesaplanır. (2) Paket içi
fontconfig: build.ps1 fonts.conf'u lisans denetiminden SONRA eziyordu, `paket-icerigi.txt`
pakette olmayan MSYS2 dosyasını anlatıyordu ve conf.d'deki 25 dosya (projenin fonts.conf'u
`<include>` taşımaz) hiç yüklenmiyordu. Değiştirme artık spec'te (`lisanslar.fontconfig_yerlestir`:
MSYS2 ağacı ayıklanır, `fonts.paket.conf` `etc/fonts/fonts.conf` adıyla girer); çalışma
davranışı değişmez, denetim diskte yalnız o dosyayı kabul eder. (3) Duman testleri Windows'un
varsayılan sistem PATH'iyle koşar ve `windows/paket_kapanisi.py` paketteki her PE dosyasının
içe aktardığı DLL'in pakette ya da Windows 10/11'de olduğunu dosyalar üzerinden sınar: koşucunun
PATH'i (mingw64\bin, Python, JDK) eksik bir DLL'i gizleyemez, UCRT kararı dosya düzeyinde
kilitlenir. (4) Python kümeleri platform platform testte sabittir
(`BEKLENEN_PYTHON_KUMELERI`): üreticinin bir platform kayması derlemede yalnız uyarı olurdu.

**Yerel kütüphanelerde GPL kuralı:** Windows'ta MSYS2 paketinin `%LICENSE%` alanı SPDX
olarak değerlendirilir; yalnız GPL görünen paket ancak `MSYS2_GPL_IZINLERI`'nde DLL
düzeyinde gerekçeli izinle (GCC çalışma anı istisnası; libintl ve libiconv'un LGPL
kitaplıkları) geçer. Linux'ta Debian copyright dosyaları makine okunur biçimde
güvenilir olmadığından kural bilinen yalnız-GPL kitaplıkların ad listesidir
(`YASAK_YEREL`: readline, gdbm, fftw3, gsl, poppler, ghostscript, x264 …).

**Sürümler:** geçişli bağımlılıklar pinli değildir; derleme ortamı
`lisanslar.py kisitlar` ile üretilen pip kısıt dosyasıyla (`pip install -c`) listedeki
sürümlere bağlanır — pakete giren sürüm `BENIOKU.txt`'dekiyle aynıdır.

**Ön yüz:** `scripts/gates.sh`, Vite çıktısına giren npm paketlerini
(`on_yuz_paketleri.mjs`) listedeki npm kayıtlarıyla ad ve sürümde karşılaştırır
(`lisanslar.py npm-denetle`); yeni bir geçişli paket kapıyı kırar.

Kurulum yüzü: Inno `LicenseFile` + `{app}\THIRD_PARTY_LICENSES\` (dosyalar
yoksa kurucu `#error` ile derlenmez); `.deb`'de DEP-5 biçimli
`/usr/share/doc/kutuphane-defteri/copyright` (`lisanslar.py deb-copyright`) ve
oradan `/opt/kutuphane-defteri/THIRD_PARTY_LICENSES`'a bağlantı; taşınabilir
arşivlerde `uygulama/THIRD_PARTY_LICENSES/`.

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
işaretli Qt paketleri (qtpy, PySide6) listeye bilerek girmez: `KD_WITH_QT=0`
doğrulama derlemesi Qt'yi kurmaz, listeye girselerdi o derlemenin dumanı
düşerdi. Yeni bir platform işaretli paket testi kırar ve bilinçli karar ister.

Linux Qt zincirinin karşılığı `build.sh`'in **adım 4b** denetimidir: derleme,
paketlenmiş dizinde `QtWebEngineProcess`, `libQt6WebEngineCore.so.6` ve
`libQt6Widgets.so.6` dosyalarını arar, bulamazsa durur. Yardımcı süreç eksik
paketlenirse program açılır ama pencere beyaz kalır; duman kipleri bunu
yakalamaz.

### Lisans: pystray LGPLv3

pystray **LGPLv3**'tür (six MIT). Dağıtılan pakete pystray'in **lisans metni
ve kaynağı** girer — *F12'de uygulandı (27.09.2026):*

* Lisans metni `THIRD_PARTY_LICENSES/LGPL-3.0-metni.txt` ve `GPL-3.0-metni.txt`
  (pystray'in `COPYING.LGPL` ve `COPYING` dosyalarından; LGPLv3, GPLv3 metnine
  atıf yapar). Bileşen tablosu `BENIOKU.txt` ve `bilesenler.json`'dadır
  (okulzili'deki `BAGIMLILIKLAR.md`'nin karşılığı).
* Kaynak: spec `module_collection_mode={"pystray": "py"}` (yalnız Windows) —
  pystray PYZ arşivine bayt kodu olarak değil `_internal\pystray\*.py` KAYNAK
  DOSYASI olarak girer; kullanıcı kütüphaneyi değiştirip programı onunla
  çalıştırabilir (LGPLv3 §4). Kaynak arşivi ayrıca indirilmez.
* Denetim: `lisanslar.py paket` (`kaynagi_pakette` işaretli bileşen) ve
  `build.ps1` adım 5'in başı `_internal\pystray\__init__.py`'yi arar; yoksa
  derleme durur.

### Lisans: PySide6 LGPLv3 (Linux)

**Neden PyQt5 değil.** Linux paketi 23.09.2026'ya kadar PyQt5 + PyQtWebEngine
gömüyordu; ikisi de **GPLv3**'tür. GPLv3 dağıtılan bütüne ek kısıtlama
konmasını yasaklar, bu ürünün lisansı (PolyForm Noncommercial, depo kökündeki
`LICENSE`) ise ticari kullanımı kısıtlar — ikisi aynı pakette birlikte
dağıtılamaz. Yayın denetiminin bulgusudur; çözüm **PySide6**'ya (Qt for
Python, **LGPLv3**) geçmektir.

**LGPLv3 ne ister.** Kütüphane dinamik bağlanmalı ve kullanıcı onu kendi
sürümüyle **değiştirip programı yeniden bağlayabilmelidir**. Paket bu şartı
yapısı gereği karşılar:

* Paket **onedir**'dir (tek dosya değil): Qt kütüphaneleri ayrı `.so` dosyaları
  olarak durur (PyInstaller 6 yerleşiminde `_internal/` altında; **kesin yol ilk
  gerçek derlemede doğrulanacak**) ve çalışma anında `dlopen` ile yüklenir.
  Kullanıcı bu dosyaları kendi derlediği aynı ABI'li Qt 6.8 sürümüyle
  değiştirip programı yeniden çalıştırabilir; kaynak koda ya da yeniden
  derlemeye gerek yoktur.
* `.deb` dosyaları `/opt/kutuphane-defteri/` altına kurulur; taşınabilir
  `.tar.gz` kullanıcı klasörüne açılır. İkisinde de dosyalar yerinde
  değiştirilebilir.
* PySide6'nın kendi sürümü, `PySide6/__init__.py` ile `Qt/lib/` içindeki
  `.so` adlarından okunabilir; pin `requirements-paketleme.txt`'tedir.

**F12'de uygulandı (27.09.2026).** **Tekerleklerin içinde lisans METNİ yoktur**
(denetlendi, 23.09.2026): `PySide6-Essentials`, `PySide6-Addons` ve `shiboken6`
dağıtımları lisansı yalnız üstveride bildirir —
`License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Üçlü lisanstan
**LGPLv3 seçilir**; seçim `bilesenler.json`'da (`secilen`) ve `BENIOKU.txt`'de
yazılıdır. Lisans metni ortak `LGPL-3.0-metni.txt` + `GPL-3.0-metni.txt`'dir
(FSF'nin standart metni; pystray'in dağıtımından alınır, depoya elle metin
konmaz). qtpy'nin MIT metni kendi tekerleğindendir. Önceki taslakta anılan
"Qt LGPL Exception" metni Qt 5'in LGPL-2.1 seçeneğine aitti; Qt 6 LGPL-2.1
sunmadığı için eklenmedi. Dizin paket köküne `lisanslar.py paket` ile kopyalanır.
Kullanıcıya dönük metin `docs/kurulum.md`'de bir cümleyle durur:

> Programın Linux sürümü, pencereyi çizen Qt kütüphanelerini LGPLv3 lisansıyla
> birlikte dağıtır. Kütüphane dosyaları kurulum klasöründe ayrı dosyalar
> hâlindedir; isteyen kendi sürümüyle değiştirebilir.

**PySide6'nın kaynağı pakete GİRMEZ** (Qt 6.8.3 kaynak arşivi yüzlerce MB'dir).
Tekerlekler Qt Company'nin yayımladığı hâlleriyle, **değiştirilmeden** dağıtılır;
tam sürümün kaynak arşivlerinin adresleri `BENIOKU.txt`'dedir (download.qt.io:
`qt-everywhere-src-6.8.3.tar.xz`, `pyside-setup-everywhere-src-6.8.3.tar.xz` —
27.09.2026'da erişilebilir olduğu denetlendi). GPLv3 §6(d) kaynağın üçüncü taraf
sunucuda durmasına izin verir ama erişilebilirliğini dağıtanın yükümlülüğü
sayar ve nesne kodunun yanında açık yönlendirme ister: Release notu
(`.github/workflows/paketleme.yml`) `BENIOKU.txt`'ye ve Qt/PySide6 kaynak adreslerine
yönlendirir (`test_surum_yolu.py` sürümü lisans listesiyle eşitler). §6(b)'nin yazılı
teklifi yalnız fiziksel taşıyıcıyla dağıtımı kapsar (KB-1 düzeltme turu, 29.09.2026 —
tasarım F12 ekleri DT-7). **KULLANICI KARARI (28.09.2026, KB-1 — tasarım §14.1 F12 ekleri karar turu
KT-1):** beta için `BENIOKU.txt`'de **yazılı teklif** vardır — üreticinin metni
(`lisanslar.py::_yazili_teklif`; kapsadığı LGPL bileşenler `bilesenler.json`'dan
türer, Windows'taki LGPL-2.1'li MSYS2 DLL'leri dahil): her sürüm, beta dahil, yayımdan
itibaren en az üç yıl; istek yolu deponun Issues sayfası (`DEPO_ADRESI`, güncelleme
denetiminin deposuyla aynı — kapı testli) ya da geliştiricinin e-posta adresi
(`ILETISIM_EPOSTA`, Hakkında ekranı ve `LICENSE` ile aynı — kapı testli; **29.09.2026
kullanıcı kararı**, tasarım F12 ekleri İA-2); kişi adı, unvan, kurum adı yazılmaz.
Metin `uret.sh` ile üretilir; kapı testi depodaki `BENIOKU.txt`'nin üreticinin çıktısıyla
birebir aynı olduğunu sınar. **Kararlı sürümden önce** Windows'un MSYS2 kaynak arşivleri
Release'e ayrı bir "kaynak" paketi olarak konur (KB-1 (b); `docs/teknik-borc.md` TB28).
Kararda Qt kaynağının (~1 GB) aynalanması yoktur: Qt için download.qt.io adresi ve yazılı
teklif geçerlidir. (pystray'de durum farklıdır: kaynağı pakettedir.)

**Not — Windows tarafı Qt kullanmaz.** Pencere motoru WebView2'dir; bu bölüm
yalnız Linux/Pardus paketini bağlar.
