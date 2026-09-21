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
>
> **F0 spike'ı, kapatma olayı (21.09.2026, geliştirme makinesi, Windows 11 +
> Inno Setup 6):** `kutuphane-defteri.iss` yerel ISCC ile derlendi. Aynı `[Code]`
> işlevleriyle derlenen düşük yetkili bir deneme kurucusu, gerçek
> `desktop/lock.py` + `desktop/instance_channel.py` modüllerini çalıştıran bir
> taklit programa karşı koşturuldu: `KutuphaneDefteri.Kapat` gönderildi,
> program düzenli kapandı, kurucu iki mutex'in kaybolmasını süreç bitene dek
> bekledi (~1 sn). Kapanmayan programda 30 sn beklendi, ileti (bastırılmış)
> İptal'e düştü, süreç zorla sonlandırılmadı. İkinci açılış kilidi reddetti ve
> `Goster` olayını teslim etti. **Doğrulanmayanlar:** gerçek yönetici kurucu ve
> kaldırıcı, UAC'ye başka hesabın (BTR) kimliği girilmesi (W12), gerçek paketli
> exe (tepsi, pencere, oturum kapanışı) — W11-W14 ve çek-listesi 7-12.

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
| W11 | Kapatma olayı kurucu VE kaldırıcıda çalışır: `InitializeSetup`/`InitializeUninstall` → `OpenEventW`+`SetEvent` (kernel32 `external`) → `CheckForMutexes` döngüsü; `AppMutex` yok (tasarım §4.2-5). Derleme ve düşük yetkili spike geçti (yukarıdaki not) | `kutuphane-defteri.iss` `[Code]`, `desktop/instance_channel.py` | kurucu program açıkken dosyaların üzerine yazar ("dosya kullanımda") ya da her seferinde 30 sn bekleyip "tepsiden Çık'ı seçin" der; kurulum günlüğünde (`/LOG`) "Kapatma olayı açılamadı" satırı |
| W12 | UAC'ye BAŞKA hesabın (BTR) kimliği girildiğinde yükseltilmiş kurucu masa hesabının olay ve mutex'lerini açabilir: nesneler SY/BA/IU/OW'ye açık güvenlik tanımlayıcısıyla kurulur | `desktop/win32_objects.py` (`MUTEX_SDDL`, `EVENT_SDDL`) | varsayılan tanımlayıcıda olduğu gibi erişim reddi: kurucu "program kapalı" sanıp kuruluma geçer (Inno `OpenMutex` reddini "yok" okur); günlükte "Kapatma olayı açılamadı" |
| W13 | pystray 0.19.5 `run_detached` + `icon.stop()`: "Çık" sonrası süreç tamamen biter; tepsi simgesi (.ico → Pillow) görünür, sol tık pencereyi açar | `desktop/tray.py` | Çık'tan sonra süreç Görev Yöneticisi'nde kalır, mutex'ler bırakılmaz (kurucu 30 sn bekler); simge boş ya da hiç yok |
| W14 | Windows oturum kapanışı/yeniden başlatma programca engellenmez: pywebview `closing` iptalinin ardından bağlanan .NET `FormClosing` işleyicisi `WindowsShutDown`/`TaskManagerClosing`'de iptali geri alır (pythonnet `+=` ve `str(CloseReason)` adı) | `desktop/window.py` (`install_session_end_passthrough`) | Windows kapanırken "Bu uygulama kapanmayı engelliyor" ekranı; sonraki açılışta günlükte "Önceki oturum beklenmedik biçimde kapandı" |

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
7. **Tepsi (F0 spike, W13):** çarpı pencereyi gizler, program kapanmaz; tepsi
   simgesi görünür; sol tık ve "Pencereyi aç" pencereyi geri getirir (önce
   küçültülmüşse eski boyutuyla); "Çık" sonrası `kutuphane-defteri.exe`
   Görev Yöneticisi'nde KALMAZ.
8. **İkinci açılış:** program tepsideyken kısayoldan yeniden aç → pencere öne
   gelir, ikinci süreç 0 koduyla çıkar, ileti kutusu çıkmaz. "Yedekten Geri
   Yükle" kısayolu → "Program tepside çalışıyor. Tepsideki simgeden Çık'ı seçip
   yeniden deneyin." ve çıkış kodu 2.
9. **F0 spike: kapatma olayı — CI Windows derlemesinde ve elle kurulum/kaldırmada
   doğrulanacak (W11, W12).** Program tepsideyken (pencere gizli) kurucuyu
   yeniden çalıştır → program ≤30 sn içinde kendiliğinden düzenli kapanır ve
   kurulum sürer; aynısı Denetim Masası'ndan kaldırmada. Kurucuyu kütüphane
   masası hesabında başlatıp UAC'ye BTR kimliği girerek de dene (W12). Program
   kapanmazsa "Kütüphane Defteri hâlâ çalışıyor…" iletisi, Yeniden Dene/İptal;
   süreç zorla sonlandırılMAZ. `/LOG` ile koşturulursa günlükte "Kapatma olayı
   gönderildi." ve "Program düzenli kapandı." satırları görünür.
10. **Temiz kapanış işareti (T15):** "Çık" sonrası
    `%LOCALAPPDATA%\KutuphaneDefteri\data\temiz-kapanis.json` VAR; program
    Görev Yöneticisi'nden sonlandırılınca YOK ve sonraki açılışta
    `logs\uygulama.log`'da "Önceki oturum beklenmedik biçimde kapandı" satırı.
11. **Oturum kapanışı (W14):** program tepsideyken Windows'u yeniden başlat ya
    da oturumu kapat → kapanış engellenmez; sonraki açılışta günlükte "Önceki
    oturum düzenli kapanmış."
12. `--autotest` çıkış kodu 0 ve `uygulama.log`'da "Temiz kapanış işareti
    yazıldı." (duman testi; pencere ve tepsi açılmaz).
13. Defender/AV taraması: onedir olduğu için imzasız da olsa engellenmemeli;
    engellenirse `docs/kurulum.md`'deki istisna adımları güncellenmeli.

## 4. Sonraki sürüm (v2) için

* **Kod imzalama** — Azure Trusted Signing veya SignPath (açık kaynak ücretsiz
  katmanı). İmzalanınca SmartScreen uyarısı ve AV yanlış-pozitif riski düşer.
* **Fixed-Version WebView2** — kilitli/çevrimdışı okul bilgisayarları için
  WebView2'nin sabit sürümünü paketin içine gömen "full" zip varyantı. Bu
  varyant henüz üretilmiyor.
