; =============================================================================
;  kutuphane-defteri.iss — Inno Setup kurulum betiği (Windows)
; =============================================================================
;  BU DOSYA BU ORTAMDA DOĞRULANMADI — ilk Windows koşusunda sınanacak.
;
;  Tasarım §2.1 U4 (okulzili deseni):
;   * PrivilegesRequired=admin → kurucu HER ZAMAN yönetici ister; program
;     Program Files altına ({autopf}) bütün hesaplar için kurulur. Kurucu
;     kütüphane masası hesabında başlatılır, UAC penceresine BTR kimliği
;     girilir (tasarım §4.5). Her güncelleme de yönetici ister (tasarım §16).
;   * Kurulum dizini standart kullanıcıya SALT OKUNURDUR: program oraya hiçbir
;     şey yazmaz (veri, günlük ve fontconfig önbelleği %LOCALAPPDATA% altında).
;   * WebView2 Runtime yoksa gömülü Evergreen kurucusu sessizce çalıştırılır.
;   * Kullanıcı verisi kurulum dizininde DEĞİLDİR; kaldırma veriyi silmez.
;   * Güvenlik duvarı kuralı, otomatik başlatma görevi ve kapatma olayı
;     (tasarım §4.2-5, §4.5, §5.7) sonraki fazların işidir; burada YOKTUR.
;
;  Derleme (build.ps1 çağırır):
;    iscc /DAppVersion=2026.9.0 /DNumericVersion=2026.9.0.0 ^
;         /DSourceDir=...\dist\paket-win\kutuphane-defteri /DOutputDir=...\dist\cikti ^
;         packaging\windows\kutuphane-defteri.iss
; =============================================================================

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef NumericVersion
  #define NumericVersion "0.0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\paket-win\kutuphane-defteri"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist\cikti"
#endif

#define AppName "Kütüphane Defteri"
#define AppExeName "kutuphane-defteri.exe"
#define AppUserModelId "KutuphaneDefteri.Desktop"
#define AppIconSource "..\ikonlar\kutuphane-defteri.ico"
#define InstalledIconName "kutuphane-defteri-" + AppVersion + ".ico"
#define WebView2Setup "MicrosoftEdgeWebView2Setup.exe"

[Setup]
; AppId ASLA DEĞİŞMEZ — değişirse yükseltmeler yan yana kurulur.
AppId={{6EA9384D-3BC5-4D2F-9025-ADB60E01897C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
VersionInfoVersion={#NumericVersion}
AppPublisher=Kütüphane Defteri
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; U4: yönetici kurulumu → {autopf} = Program Files; {group} ve {autodesktop}
; ortak (bütün hesaplar) Başlat menüsü ve masaüstüdür. Kullanıcıya "yalnız
; benim için" seçeneği SUNULMAZ (PrivilegesRequiredOverridesAllowed yok).
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=kutuphane-defteri-{#AppVersion}-win64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#AppIconSource}
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
; GEÇİCİ (KS'den devralındı): program çalışırken yükseltme yapılmasın (SQLite
; dosyası açık olabilir). Ad, uygulamanın açtığı mutex'le BİREBİR aynı olmak
; zorunda (desktop/lock.py::APP_MUTEX_NAME). Tasarım §2.3 ve §4.2-5 AppMutex'i
; KULLANMAZ: program tepside yaşayacağı için kurucu/kaldırıcı `[Code]` içinden
; `KutuphaneDefteri.Kapat` adlı olayı gönderip mutex'lerin serbest kalmasını
; bekleyecek. O akış F0 spike'ında doğrulanınca bu satır kaldırılır.
AppMutex=KutuphaneDefteri

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek kısayollar:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#AppIconSource}"; DestDir: "{app}"; DestName: "{#InstalledIconName}"; Flags: ignoreversion
; WebView2 Evergreen kurucusu — build.ps1 indirdiyse pakete girer.
#if FileExists(AddBackslash(SourcePath) + WebView2Setup)
Source: "{#WebView2Setup}"; DestDir: "{app}"; Flags: ignoreversion
#else
; Sessiz düşme tuzağı kapatıldı: dosya yoksa derleme kırılmaz ama uyarı basılır
; (WebView2'siz makinede kurulum biter, program çıkış kodu 7 ile kapanırdı).
#pragma warning "WebView2 kurucusu (" + WebView2Setup + ") bulunamadı — paket onsuz üretiliyor."
#endif

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#InstalledIconName}"; AppUserModelID: "{#AppUserModelId}"
; Geri yükleme kipi: bozuk veritabanında bütünlük denetimi pencereyi açmaz;
; hata iletisi kullanıcıyı bu kısayola yönlendirir (desktop/integrity.py).
; Kip kendi konsol penceresini açar (desktop/restore.py, AllocConsole).
Name: "{group}\{#AppName} — Yedekten Geri Yükle"; Filename: "{app}\{#AppExeName}"; Parameters: "--geri-yukle"; IconFilename: "{app}\{#InstalledIconName}"; Comment: "Veritabanını bir yedekten geri yükler"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#InstalledIconName}"; AppUserModelID: "{#AppUserModelId}"; Tasks: desktopicon

[InstallDelete]
; Sürüm bazlı ad Windows ikon önbelleğini yeniler; eski sürüm ikonları temizlenir.
Type: files; Name: "{app}\kutuphane-defteri-*.ico"

[Run]
; WebView2 yoksa önce onu kur (sessiz). Kurulamazsa kurulum yine tamamlanır;
; program ilk açılışta Türkçe yönlendirme verir (desktop/window.py).
Filename: "{app}\{#WebView2Setup}"; Parameters: "/silent /install"; \
    StatusMsg: "Microsoft Edge WebView2 bileşeni kuruluyor..."; \
    Check: WebView2Eksik and WebView2KurucusuVar; Flags: waituntilterminated skipifdoesntexist
; Program YÜKSELTİLMİŞ kimlikle açılmamalı: veri, programı çalıştıran hesabın
; %LOCALAPPDATA%'sına yazılır; UAC'de BTR kimliği girildiyse yükseltilmiş süreç
; veriyi BTR'nin profiline açardı. `runasoriginaluser` postinstall girdilerinde
; zaten varsayılandır; niyet belgelensin diye açıkça yazılır.
Filename: "{app}\{#AppExeName}"; Description: "{#AppName} programını çalıştır"; \
    Flags: nowait postinstall skipifsilent runasoriginaluser

[Messages]
turkish.FinishedLabel=Kurulum tamamlandı.%n%nVerileriniz (kütüphane kayıtları ve yedekler) programın kurulduğu klasörde DEĞİL, kullanıcı klasörünüzde saklanır. Programı kaldırsanız bile kayıtlarınız silinmez.

[Code]
const
  WebView2ClientId = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

// Evergreen WebView2 Runtime kayıt defterinde 'pv' sürümüyle kendini bildirir.
// (Aynı üç anahtar desktop/window.py'de de denetlenir — tek doğruluk kaynağı
// orasıdır; burada yalnız kurucunun çalıştırılıp çalıştırılmayacağı belirlenir.)
function WebView2Eksik: Boolean;
var
  Surum: String;
begin
  Result := True;
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WebView2ClientId, 'pv', Surum) then
    if (Surum <> '') and (Surum <> '0.0.0.0') then Result := False;
  if Result and RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WebView2ClientId, 'pv', Surum) then
    if (Surum <> '') and (Surum <> '0.0.0.0') then Result := False;
  if Result and RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WebView2ClientId, 'pv', Surum) then
    if (Surum <> '') and (Surum <> '0.0.0.0') then Result := False;
end;

function WebView2KurucusuVar: Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\{#WebView2Setup}'));
end;
