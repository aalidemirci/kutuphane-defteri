# Windows paketleme — doğrulanmamış varsayımlar ve ilk koşu çek-listesi

> **Durum (21.09.2026):** Bu hat kardeş proje KS'den devralındı ve orada
> doğrulandı: KS'nin 29.08.2026 CI koşusu uçtan uca yeşildi (setup.exe +
> portable.zip üretildi, Türkçe PDF duman testi gömülü DejaVu ile geçti,
> `--autotest` çıkış 0; W1 ve W5 fiilen, W2-W4 ve W6-W8 dolaylı doğrulandı).
> W9 da KS'de doğrulandı (30.08.2026): paketlenmiş exe Windows 11'de gerçek
> pencere açtı, WebView2/pythonnet zinciri çalıştı. Kurucu düzeltmeler (PS1
> BOM'u, MSYS2 python gölgelemesi, paket içi fontconfig) de KS'den gelir.
>
> **Kütüphane Defteri adıyla henüz hiçbir Windows koşusu yapılmadı.** Ayrıca
> iki fark KS'de hiç sınanmadı: kurucu artık **yönetici kurulumudur** (U4,
> W8) ve `--pdf-duman` örnek belgeyi paketteki evrak şablonundan
> (`documents/base.html`) üretir. İlk koşuda aşağıdaki çek-listesi baştan
> yürütülür.

## 1. Doğrulanması gereken varsayımlar

| # | Varsayım | Nerede | Yanlışsa belirtisi |
|---|---|---|---|
| W1 | MSYS2 `mingw-w64-x86_64-ntldd-git` paket adı doğru | CI iş akışı, `dll_kapanisi.py` | pacman "target not found"; `objdump` yedeğine düşülür (betik bunu zaten yapar) |
| W2 | WeasyPrint'in aradığı DLL adları `libpango-1.0-0.dll`, `libpangoft2-1.0-0.dll`, `libharfbuzz-0.dll`, `libgobject-2.0-0.dll`, `libfontconfig-1.dll` desenlerine uyuyor | `dll_kapanisi.py::SEED_PATTERNS` | `--pdf-duman` "cannot load library" ile çöker |
| W3 | `WEASYPRINT_DLL_DIRECTORIES` paket kökünü göstermek yeterli (WeasyPrint ≥60) | `rthook_kd.py` | aynı hata; alternatif `os.add_dll_directory()` |
| W4 | fontconfig `<dir>` mutlak yol + `<cachedir>` yazılabilir dizin kabul ediyor | `fonts.conf.tmpl` | PDF üretilir ama font DejaVu değildir → `--pdf-duman` "gömülü DejaVu ile dizilmemiş" hatası verir (duman testi bunu YAKALAR) |
| W5 | WebView2 Evergreen bootstrapper bağlantısı `https://go.microsoft.com/fwlink/p/?LinkId=2124703` | CI iş akışı | indirme 404; elle indirilip `packaging/windows/` altına konur |
| W6 | Inno Setup 6.3+ `ArchitecturesAllowed=x64compatible` destekliyor | `kutuphane-defteri.iss` | derleme hatası → `x64` yazılır (6.2 ve öncesi) |
| W7 | `compiler:Languages\Turkish.isl` Inno kurulumunda mevcut | `kutuphane-defteri.iss` | derleme hatası → dosya Inno deposundan indirilip eklenir |
| W8 | `PrivilegesRequired=admin` ile `{autopf}` = `Program Files`; paketlenmiş program kurulum dizinine hiçbir şey YAZMAZ (fontconfig önbelleği `%LOCALAPPDATA%` altında) | `kutuphane-defteri.iss`, `rthook_kd.py` | standart hesapta açılışta "erişim reddedildi" ya da PDF'te font hatası; `KD_RTHOOK_UYARI` günlüğe düşer |
| W9 | pywebview `edgechromium` arka ucu `pythonnet` ile çalışıyor ve PyInstaller ile paketleniyor | `requirements-paketleme.txt`, spec | pencere açılmaz; `webview/lib/*.dll` elle `datas`'a eklenmesi gerekebilir |
| W10 | Kurulum sonrası "programı çalıştır" adımı yükseltilmemiş (kurucuyu başlatan) hesapla koşar | `kutuphane-defteri.iss` `[Run]` (`runasoriginaluser`) | veri UAC'ye kimliği girilen hesabın (BTR) profilinde oluşur |

## 2. Bilinen Windows tuzakları (kodda karşılığı var)

* **GUI exe'yi PowerShell beklemez.** `console=False` ile derlenen exe `&` ile
  çağrılınca PowerShell hemen döner ve `$LASTEXITCODE` anlamsızdır. `build.ps1`
  bu yüzden duman testlerini `Start-Process -Wait -PassThru` ile koşturur.
* **`sys.stdout`/`sys.stderr` `None`'dır.** Penceresiz derlemede konsol yoktur;
  `print()` `AttributeError` üretir. `giris.py` bu yüzden `print` kullanmaz,
  `sys.stderr`'i `None` kontrolüyle yazar. `desktop/logging_setup.py`
  `--autotest` kipinde `StreamHandler(sys.stderr)` kuruyor; Windows'ta bu
  handler sessizce hiçbir şey yazmaz (çökmez, ama Windows'ta `--autotest`
  çıktısı YALNIZ günlük dosyasındadır).
* **MSHTML düşüşü.** pywebview WebView2 bulamazsa eski IE motoruna düşer ve
  React 18 çalışmaz (beyaz pencere). `desktop/window.py` motoru açıkça
  `edgechromium` verir ve registry denetimi yapar — düşüş KODLA ENGELLİ.
* **`%APPDATA%` (Roaming) kullanılmaz.** Gezici profil/OneDrive senkronu açık
  SQLite dosyasını bozar; veri `%LOCALAPPDATA%` altındadır (`desktop/paths.py`).

## 3. İlk Windows koşusu çek-listesi

1. `npm run build` → `frontend\dist` oluştu mu?
2. `powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1`
3. `dist\cikti\pdf-duman.pdf` açılıyor mu; antet, "ĞÜŞİÖÇ ığüşiöç" ve "Sayfa
   1 / 1" altlığı düzgün görünüyor mu? (Duman testi metni zaten pypdf ile
   doğrular; gözle de bakılmalı.)
4. Kurulum paketini **yönetici olmayan** bir hesapta (kütüphane masası hesabı)
   çalıştır → UAC yönetici kimliği istesin, program `C:\Program
   Files\Kütüphane Defteri` altına kurulsun; son adımdaki "çalıştır" programı
   masa hesabıyla açsın ve veri `%LOCALAPPDATA%\KutuphaneDefteri` altında
   oluşsun (W8, W10).
5. **WebView2 kurulu OLMAYAN** bir makinede/VM'de aç → Türkçe yönlendirme
   diyaloğu çıksın, program çıkış kodu 7 versin (beyaz pencere DEĞİL).
6. Taşınabilir zip'i USB'den çalıştır → MotW olmadığından SmartScreen çıkmamalı.
7. Program açıkken ikinci kez çalıştır → "zaten çalışıyor" (çıkış kodu 2).
8. Program açıkken kurucuyu yeniden çalıştır → `AppMutex` "programı kapatın"
   iletisini göstersin (geçici davranış; kapatma olayı gelince değişir).
9. Defender/AV taraması: onedir olduğu için imzasız da olsa engellenmemeli;
   engellenirse `docs/kurulum.md`'deki istisna adımları güncellenmeli.

## 4. Sonraki sürüm (v2) için

* **Kod imzalama** — Azure Trusted Signing veya SignPath (açık kaynak ücretsiz
  katmanı). İmzalanınca SmartScreen uyarısı ve AV yanlış-pozitif riski düşer.
* **Fixed-Version WebView2** — kilitli/çevrimdışı okul bilgisayarları için
  WebView2'nin sabit sürümünü paketin içine gömen "full" zip varyantı. Bu
  varyant henüz üretilmiyor.
