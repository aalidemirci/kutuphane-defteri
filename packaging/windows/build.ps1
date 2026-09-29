<#
=============================================================================
 packaging/windows/build.ps1 — Windows paketlerini üretir
=============================================================================
 BU BETİK BU ORTAMDA DOĞRULANMADI — ilk Windows koşusunda sınanacak.
 (Linux'ta yalnız sözdizimi gözden geçirmesi yapıldı; PowerShell çalıştırılmadı.)

 Ön koşullar:
   * Python 3.12 (PATH'te)
   * MSYS2 + `pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-fontconfig
     mingw-w64-x86_64-ntldd-git`
   * Inno Setup 6.3+ (`iscc.exe` PATH'te) — kurulum paketi için
   * `frontend/dist` derlenmiş olmalı (`npm run build`)

 Kullanım (depo kökünden):
     powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1

 Çıktılar: dist\cikti\
   kutuphane-defteri-<sürüm>-win64-setup.exe      (Inno, yönetici İSTER — U4)
   kutuphane-defteri-<sürüm>-win64-portable.zip   (taşınabilir)
   SHA256SUMS.txt

 Paket kökünde (ikisinde de): LICENSE.txt (PolyForm Noncommercial; kurucunun
 lisans sayfası) ve THIRD_PARTY_LICENSES\ (üçüncü taraf lisansları, derlemede
 eklenen paket-icerigi.txt ve yerel-kutuphaneler\ ile — F12, TB28).
=============================================================================
#>
[CmdletBinding()]
param(
    [string]$MingwBin = "C:\msys64\mingw64\bin",
    # Kullanilacak Python. Bos birakilirsa PATH'ten cozulur AMA mingw64\bin
    # altindakiler ELENIR: MSYS2'nin python.exe'si ayni dizinde durur, PATH'te
    # onde oldugunda gercek Python'u golgeler ve pip bulunamaz (ilk CI
    # kosusunda tam olarak bu oldu).
    [string]$PythonExe = "",
    [switch]$SkipDeps,
    [switch]$SkipInno,
    [switch]$WithoutQt
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Version = (Get-Content (Join-Path $Repo "VERSION") -Raw).Trim()
# Windows sürüm kaynağı yalnız sayı kabul eder ("2026.7.0-dev" → "2026.7.0.0").
$NumericVersion = ($Version -split "-")[0]
while (($NumericVersion -split "\.").Count -lt 4) { $NumericVersion += ".0" }

$DistRoot   = Join-Path $Repo "dist"
$Output     = Join-Path $DistRoot "cikti"
# Ara dizinler platforma özel: Linux derlemesi (docker-build.sh) aynı depoda eş
# zamanlı koşarsa ortak `dist/paket` ağacında ÇARPIŞIRLARDI (build.ps1'in
# Remove-Item'ı kabın yazdığı ağacı siler). Nihai artefaktlar yine dist/cikti'de.
$PackageDir = Join-Path $DistRoot "paket-win"
$WorkDir    = Join-Path $DistRoot "_build-win"
$VenvDir    = Join-Path $DistRoot "_venv-win"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$DllDir     = Join-Path $Repo "packaging\windows\dll"
$AppDir     = Join-Path $PackageDir "kutuphane-defteri"
$AppExe     = Join-Path $AppDir "kutuphane-defteri.exe"

function Write-Adim([string]$Mesaj) { Write-Host "== $Mesaj" -ForegroundColor Cyan }

# Windows 10/11'in varsayılan sistem PATH'i: programın kullanıcının makinesinde gördüğü.
function Get-SistemPath {
    return @(
        (Join-Path $env:SystemRoot "System32"),
        $env:SystemRoot,
        (Join-Path $env:SystemRoot "System32\Wbem"),
        (Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0")
    ) -join ";"
}

# Pencereli (GUI) bir uygulama `&` ile çağrıldığında PowerShell BEKLEMEZ ve
# $LASTEXITCODE anlamsız olur. Paketlenmiş exe `console=False` ile derlendiği
# için duman testleri MUTLAKA bu yardımcıdan geçmelidir. PATH her çağrıda
# `Get-SistemPath`'tir (29.09.2026 doğrulama turu): koşucunun PATH'i (mingw64\bin,
# Python, JDK) paketten eksik bir DLL'i gizlemesin.
function Invoke-Uygulama([string]$Yol, [string[]]$Argumanlar, [hashtable]$Ortam = @{}) {
    $tumOrtam = @{ "PATH" = (Get-SistemPath) }
    foreach ($anahtar in $Ortam.Keys) { $tumOrtam[$anahtar] = $Ortam[$anahtar] }
    $eski = @{}
    foreach ($anahtar in $tumOrtam.Keys) {
        $eski[$anahtar] = [Environment]::GetEnvironmentVariable($anahtar)
        [Environment]::SetEnvironmentVariable($anahtar, $tumOrtam[$anahtar])
    }
    try {
        $surec = Start-Process -FilePath $Yol -ArgumentList $Argumanlar -Wait -PassThru -NoNewWindow
        return $surec.ExitCode
    } finally {
        foreach ($anahtar in $tumOrtam.Keys) {
            [Environment]::SetEnvironmentVariable($anahtar, $eski[$anahtar])
        }
    }
}

# --- 1. Ön koşullar ---------------------------------------------------------
Write-Adim "ön koşullar"

if (-not $PythonExe) {
    $mingwTam = try { (Resolve-Path $MingwBin -ErrorAction Stop).Path } catch { $MingwBin }
    $PythonExe = Get-Command python -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and -not $_.Source.StartsWith($mingwTam, "OrdinalIgnoreCase") } |
        Select-Object -First 1 -ExpandProperty Source
}
if (-not $PythonExe) { throw "Python bulunamadı (mingw64 dışında bir python.exe gerekli)." }
& $PythonExe -c "import sys" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Python çalıştırılamadı: $PythonExe" }
Write-Host "    python: $PythonExe"
if (-not (Test-Path (Join-Path $Repo "frontend\dist\index.html"))) {
    throw "frontend/dist/index.html yok. Önce arayüzü derleyin: npm run build"
}

# --- 2. Python bağımlılıkları (yalıtılmış sanal ortam) ---------------------
# Paket YALNIZ gereksinim dosyalarının kurduğu dağıtımlarla derlenir. Neden sanal ortam:
# GitHub'ın Windows koşucusu varsayılan Python'una (araç önbelleğindeki 3.12.x —
# setup-python'ın seçtiği AYNI kurulum) imaj hazırlanırken `pip install pipx` koşar
# (actions/runner-images `Install-Pipx.ps1`); pipx'in Windows bağımlılığı colorama da
# oraya kurulur. Django `core/management/color.py` colorama'yı KOŞULLU import ettiği için
# PyInstaller onu pakete aldı ve lisans denetimi durdu (29.09.2026 CI koşusu). Linux
# derlemesi temiz bir kapta koşar; Windows'ta eşdeğeri bu sanal ortamdır. Yerel
# derlemede de kullanıcının kendi kurduğu paketler pakete sızmaz.
if (-not $SkipDeps) {
    Write-Adim "yalıtılmış sanal ortam ($VenvDir)"
    & $PythonExe -m venv --clear $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Sanal ortam kurulamadı: $VenvDir" }

    Write-Adim "python bağımlılıkları (lisans listesindeki sürümlere kısıtlı)"
    # Geçişli bağımlılıklar pinli değildir; kısıt dosyası onları THIRD_PARTY_LICENSES
    # listesinin sürümlerine bağlar — pakete giren sürüm BENIOKU'dakiyle aynı olur
    # (F12 düzeltme turu). Dosyayı betik yazar: PowerShell 5.1'in `>` yönlendirmesi
    # UTF-16 yazardı, pip okuyamazdı.
    $Kisitlar = Join-Path $DistRoot "kisitlar-windows.txt"
    & $VenvPython (Join-Path $Repo "packaging\lisanslar\lisanslar.py") kisitlar `
        --platform windows --cikti $Kisitlar
    if ($LASTEXITCODE -ne 0) { throw "Kısıt dosyası üretilemedi." }
    & $VenvPython -m pip install --disable-pip-version-check -q -c $Kisitlar `
        -r (Join-Path $Repo "backend\requirements.txt") `
        -r (Join-Path $Repo "packaging\requirements-paketleme.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install başarısız." }
} elseif (-not (Test-Path $VenvPython)) {
    throw "Sanal ortam yok ($VenvDir). -SkipDeps olmadan bir kez koşun."
}
# Bundan sonraki her Python adımı (DLL kapanışı, PyInstaller, lisans denetimi) sanal
# ortamın yorumlayıcısıyla koşar.
$PythonExe = $VenvPython
Write-Host "    derleme yorumlayıcısı: $PythonExe"

# --- 3. WeasyPrint DLL kapanışı --------------------------------------------
Write-Adim "DLL kapanışı ($MingwBin)"
# `dll_kapanisi.py` ntldd/objdump aracını PATH'ten çözer. CI bunu zaten yapar;
# yerel kurulumda yalnız -MingwBin verilmiş olabileceği için burada da ekle.
if (-not (($env:PATH -split ";") -contains $MingwBin)) {
    $env:PATH = "$env:PATH;$MingwBin"
}
& $PythonExe (Join-Path $Repo "packaging\windows\dll_kapanisi.py") --mingw-bin $MingwBin --cikti $DllDir
if ($LASTEXITCODE -ne 0) { throw "DLL kapanışı başarısız." }

# --- 4. PyInstaller ---------------------------------------------------------
Write-Adim "PyInstaller onedir"
Remove-Item -Recurse -Force $PackageDir, $WorkDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$env:KD_WITH_QT = if ($WithoutQt) { "0" } else { "1" }
$env:KD_DLL_DIR = $DllDir
# Yalın PATH: PyInstaller bir ikilinin bağımlılığını önce ikilinin kendi dizininde, sonra
# temel yorumlayıcının dizininde (`sys.base_prefix`; vcruntime140*.dll buradan gelir), sonra
# PATH'te arar ve Microsoft çalışma zamanı adlarını (`_win_includes`) nerede bulursa oradan
# pakete alır. Koşucunun PATH'i yabancı kopyalarla doludur: 29.09.2026 CI koşusunda
# Temurin JDK'nın `bin`'indeki Universal CRT (ucrtbase.dll + 42 api-ms-win-*.dll) pakete
# girdi. PyInstaller yalnız Windows sistem dizinleri, sanal ortam ve MSYS2 mingw64\bin
# (hooks-contrib `hook-weasyprint` fontconfig'i orada arar) ile koşar. Spec UCRT'yi
# ayrıca ayıklar (`ucrt_suz`); lisans denetimi sahibi bilinmeyen dosyada durur.
$EskiPath = $env:PATH
$env:PATH = @(
    (Join-Path $env:SystemRoot "System32"),
    $env:SystemRoot,
    (Join-Path $VenvDir "Scripts"),
    $MingwBin
) -join ";"
try {
    & $PythonExe -m PyInstaller --noconfirm --clean --log-level WARN `
        --distpath $PackageDir --workpath $WorkDir `
        (Join-Path $Repo "packaging\pyinstaller\kutuphane_defteri.spec")
    $PyInstallerKodu = $LASTEXITCODE
} finally {
    $env:PATH = $EskiPath
}
if ($PyInstallerKodu -ne 0) { throw "PyInstaller başarısız." }
if (-not (Test-Path $AppExe)) { throw "Çalıştırılabilir üretilmedi: $AppExe" }

# Lisans kapısı (F12, TB28): THIRD_PARTY_LICENSES\ ve LICENSE.txt (UTF-8 BOM —
# Inno LicenseFile) paket köküne kopyalanır; pakete GERÇEKTEN giren her dosyanın
# sahibi bulunur (Python dağıtımı → lisans listesi; WeasyPrint DLL'leri → MSYS2
# paket veritabanı ve paketin share\licenses dosyaları). Listede olmayan dağıtım,
# sahibi bilinmeyen dosya, pystray kaynağının eksikliği (LGPL), süzülmemiş pyphen
# sözlükleri, Universal CRT ya da projenin olmayan paket içi fontconfig yapılandırması
# derlemeyi durdurur. Veri sızıntısı denetiminden ÖNCE koşar.
Write-Adim "lisans denetimi (THIRD_PARTY_LICENSES)"
$Msys2Kok = (Resolve-Path (Join-Path $MingwBin "..\..")).Path
& $PythonExe (Join-Path $Repo "packaging\lisanslar\lisanslar.py") paket `
    --paket $AppDir `
    --calisma (Join-Path $WorkDir "kutuphane_defteri") `
    --platform windows `
    --dll-dizini $DllDir `
    --msys2-kok $Msys2Kok
if ($LASTEXITCODE -ne 0) { throw "Lisans denetimi başarısız." }

# Statik DLL kapanışı (29.09.2026 doğrulama turu): paketteki her PE dosyasının (exe, dll,
# pyd) içe aktardığı her DLL (gecikmeli dahil) ya pakette ya da Windows 10/11'in
# bileşenidir. Dosyalar üzerinden, çalışma anından bağımsız sınanır: koşucunun PATH'indeki
# kopyalar (mingw64\bin, JDK …) eksik bir DLL'i gizleyemez; Universal CRT'nin (pakette yok)
# işletim sisteminden geldiği kararı da burada kilitlenir.
Write-Adim "paketin statik DLL kapanışı"
& $PythonExe (Join-Path $Repo "packaging\windows\paket_kapanisi.py") $AppDir
if ($LASTEXITCODE -ne 0) { throw "Paketin DLL kapanışı eksik." }

# Paketleme tanımına yanlışlıkla gerçek veritabanı, medya veya Excel dosyası
# eklenirse dağıtımı burada durdur.
Write-Adim "paket kişisel veri sızıntısı denetimi"
& $PythonExe (Join-Path $Repo "packaging\veri_sizintisi.py") $AppDir
if ($LASTEXITCODE -ne 0) { throw "Paket kişisel veri denetimi başarısız." }

# Paket içi fontconfig yapılandırması (`_internal\etc\fonts\fonts.conf` = projenin
# packaging\pyinstaller\fonts.paket.conf'u) artık spec'te yerleşir (`lisanslar.
# fontconfig_yerlestir`); derleme sonrası kopyalama adımı (eski 4b) YOKTUR. Lisans denetimi
# diskte yalnız o dosyayı kabul eder, `--pdf-duman` PDF'in gömülü DejaVu ile dizildiğini sınar.

# --- 5. Duman testleri ------------------------------------------------------
# Duman testleri kullanıcının makinesindeki gibi Windows'un varsayılan sistem PATH'iyle
# koşar (`Invoke-Uygulama`): koşucunun PATH'indeki mingw64\bin, Python ve JDK kopyaları
# paketten eksik bir DLL'i gizlemesin (dondurulmuş `ctypes.util.find_library` PATH'e bakar).
# pystray kaynağı pakette mi (LGPLv3 — spec `module_collection_mode`)? Lisans
# denetimi de arar; burada ikinci sigorta: bağımlılık dumanı pystray'i bu
# dosyalardan import eder.
if (-not (Test-Path (Join-Path $AppDir "_internal\pystray\__init__.py"))) {
    throw "pystray kaynağı pakette yok (_internal\pystray\__init__.py) — LGPL gereği girmeli."
}

# ÖNCE bağımlılık kapısı: eksik bir hiddenimport'u burada yakalamak, sonraki
# testlerin anlaşılmaz hatalarını okumaktan ucuzdur (hiddenimports zinciri).
Write-Adim "duman testi: --bagimlilik-duman (hiddenimports)"
$kod = Invoke-Uygulama $AppExe @("--bagimlilik-duman")
if ($kod -ne 0) {
    throw "Bağımlılık duman testi BAŞARISIZ (çıkış $kod). spec hiddenimports eksik."
}

# Kip örnek belgeyi paketteki evrak şablonundan (documents/base.html) üretir;
# şablon ağacı pakete girmemişse de burada düşer.
Write-Adim "duman testi: --pdf-duman (evrak şablonu + Türkçe PDF)"
$pdf = Join-Path $Output "pdf-duman.pdf"
$kod = Invoke-Uygulama $AppExe @("--pdf-duman", $pdf)
if ($kod -ne 0) {
    throw "PDF duman testi BAŞARISIZ (çıkış $kod). Evrak şablonları, WeasyPrint DLL kapanışı veya fontconfig eksik."
}
if (-not (Test-Path $pdf)) { throw "PDF üretilmedi: $pdf" }

Write-Adim "duman testi: --autotest"
$gecici = Join-Path ([System.IO.Path]::GetTempPath()) ("kd-" + [Guid]::NewGuid().ToString("N"))
$kod = Invoke-Uygulama $AppExe @("--autotest") @{ "KD_APP_HOME" = $gecici }
Remove-Item -Recurse -Force $gecici -ErrorAction SilentlyContinue
if ($kod -ne 0) { throw "Açılış denetimi BAŞARISIZ (çıkış $kod)." }

# --- 6. Taşınabilir zip -----------------------------------------------------
Write-Adim "taşınabilir zip"
$zip = Join-Path $Output "kutuphane-defteri-$Version-win64-portable.zip"
Remove-Item -Force $zip -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $AppDir "*") -DestinationPath $zip

# Son arşivde de aynı denetim (Linux'ta .deb + .tar.gz — iki platformda eşit
# kapsam, F12). Kurulum dosyası (setup.exe) listelenemez: içeriği $AppDir ile
# .iss [Files] bölümündeki üç sabit depo dosyasıdır (test_veri_sizintisi.py).
Write-Adim "son arşivde kişisel veri sızıntısı denetimi"
& $PythonExe (Join-Path $Repo "packaging\veri_sizintisi.py") $zip
if ($LASTEXITCODE -ne 0) { throw "Taşınabilir arşivde kişisel veri denetimi başarısız." }

# --- 7. Inno Setup kurulum paketi -------------------------------------------
if (-not $SkipInno) {
    # WebView2 Evergreen önyükleyicisi kurucuya gömülür (tasarım §14 F12).
    # KS'de önce yalnız CI indiriyordu; yerel/elle üretilen her setup.exe
    # onsuz çıkıyor ve .iss önişlemcisi bunu SESSİZCE düşürüyordu. İndirilemezse
    # paket yine üretilir (iss artık uyarı basar); program ilk açılışta Türkçe
    # yönlendirme verir (desktop/window.py).
    $WebView2Yolu = Join-Path $Repo "packaging\windows\MicrosoftEdgeWebView2Setup.exe"
    if (-not (Test-Path $WebView2Yolu)) {
        Write-Adim "WebView2 Evergreen kurucusu indiriliyor"
        try {
            Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" `
                -OutFile $WebView2Yolu
        } catch {
            Write-Host "    UYARI: WebView2 kurucusu indirilemedi — paket onsuz üretilecek." -ForegroundColor Yellow
        }
    }

    Write-Adim "Inno Setup"
    $iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue)
    if ($null -eq $iscc) {
        $isccAdaylari = @(
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
        )
        $isccYolu = $isccAdaylari | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
        if ($isccYolu) {
            $iscc = [PSCustomObject]@{ Source = $isccYolu }
        } else {
            throw "iscc.exe bulunamadı. Inno Setup 6.3+ kurun (choco install innosetup)."
        }
    }
    & $iscc.Source `
        "/DAppVersion=$Version" `
        "/DNumericVersion=$NumericVersion" `
        "/DSourceDir=$AppDir" `
        "/DOutputDir=$Output" `
        (Join-Path $Repo "packaging\windows\kutuphane-defteri.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup başarısız." }
}

# --- 8. Sağlama toplamları --------------------------------------------------
Write-Adim "SHA256SUMS.txt"
$satirlar = @()
Get-ChildItem -Path $Output -Include *.exe, *.zip -File -Recurse | Sort-Object Name | ForEach-Object {
    $ozet = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()
    $satirlar += "$ozet  $($_.Name)"
}
$satirlar | Set-Content -Path (Join-Path $Output "SHA256SUMS.txt") -Encoding ascii

Write-Adim "bitti — çıktılar: $Output"
Get-ChildItem $Output
