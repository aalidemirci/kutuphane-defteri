# =============================================================================
#  gorev-kur.ps1 - oturum acilisinda Kutuphane Defteri'ni baslatan zamanlanmis gorev
# =============================================================================
#  Tasarim 4.2-3 ve 4.5 (okulzili deseni). Kurucu bu betigi `runasoriginaluser`
#  ile, yani kurucuyu BASLATAN hesabin (kutuphane masasi hesabi) baglaminda
#  calistirir; UAC'ye BTR kimligi girilse de gorev masa hesabina yazilir. Kurucu
#  BTR'nin kendi oturumunda baslatilirsa gorev BTR'ye yazilir (GA-15; kurulum
#  belgesi bunu soyler).
#
#  * Tetik YALNIZ bu hesabin oturum acilisidir (-User): baska bir hesap oturum
#    actiginda program onun adina baslamaz.
#  * Varsayilan acilis kilit ekrani gorunur acilistir; -Tepside verilirse
#    program pencereyi acmadan tepside baslar (`--tepside`).
#  * Yeniden baslatma sayaci YOK: Cik ile kapanan programi Gorev Zamanlayici
#    geri acmamali; ikinci kopya zaten kendini kapatir (MultipleInstances).
#  * Program Windows oturumu acilmadan ne kendisi ne Ag Katalogu kalkar.
#
#  Betik bilerek ASCII'dir (PowerShell 5.1 BOM'suz dosyayi ANSI okur;
#  packaging/tests/test_betik_kodlamasi.py).
# =============================================================================
param([switch]$Tepside)

$ErrorActionPreference = 'Stop'
$gorevAdi = 'Kutuphane Defteri'
$exe = Join-Path $PSScriptRoot 'kutuphane-defteri.exe'
$kullanici = "$env:USERDOMAIN\$env:USERNAME"

if ($Tepside) {
    $eylem = New-ScheduledTaskAction -Execute $exe -Argument '--tepside'
} else {
    $eylem = New-ScheduledTaskAction -Execute $exe
}
$tetik = New-ScheduledTaskTrigger -AtLogOn -User $kullanici
$ayarlar = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$sorumlu = New-ScheduledTaskPrincipal -UserId $kullanici -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $gorevAdi -Action $eylem -Trigger $tetik -Settings $ayarlar `
    -Principal $sorumlu -Description 'Kutuphane Defteri: oturum acilisinda baslat' -Force | Out-Null
