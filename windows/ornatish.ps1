# EngCheck - Windows uchun o'rnatuvchi.
# Python va Node.js yo'q bo'lsa winget orqali o'rnatadi, kutubxonalarni yuklaydi, interfeysni quradi va dasturni ishga tushiradi.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
try { Start-Transcript -Path (Join-Path $PSScriptRoot "ornatish-log.txt") -Force | Out-Null } catch { }

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Find-Python {
    foreach ($c in @(@("py", "-3"), @("python"), @("python3"))) {
        $exe = $c[0]; $rest = @(); if ($c.Count -gt 1) { $rest = $c[1..($c.Count - 1)] }
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $v = & $exe @rest -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$v -ge [version]"3.11") { return ,$c }
        } catch { }
    }
    return $null
}
function Need-Winget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget topilmadi. Microsoft Store'dan 'App Installer' ni o'rnating yoki Python 3.12 (python.org) va Node.js LTS (nodejs.org) ni qo'lda o'rnatib, shu faylni qayta ishga tushiring."
    }
}
function Run($exe, $arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Buyruq xato bilan tugadi: $exe $($arguments -join ' ')" }
}

Step "Python tekshirilmoqda"
$py = Find-Python
if (-not $py) {
    Need-Winget
    Write-Host "Python 3.12 o'rnatilmoqda..."
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    Refresh-Path
    $py = Find-Python
    if (-not $py) { throw "Python o'rnatildi, lekin topilmadi. Oynani yopib, ornatish.bat ni qayta ishga tushiring." }
}
Write-Host "Python: $($py -join ' ')"

Step "Node.js tekshirilmoqda"
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Need-Winget
    Write-Host "Node.js LTS o'rnatilmoqda..."
    winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
    Refresh-Path
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Node.js o'rnatildi, lekin topilmadi. Oynani yopib, ornatish.bat ni qayta ishga tushiring." }
}
Write-Host "Node.js: $(node --version)"

Step "Python muhiti va kutubxonalar (bir necha daqiqa)"
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $rest = @(); if ($py.Count -gt 1) { $rest = $py[1..($py.Count - 1)] }
    Run $py[0] ($rest + @("-m", "venv", (Join-Path $Root ".venv")))
}
Run $venvPy @("-m", "pip", "install", "--upgrade", "pip", "--quiet")
Run $venvPy @("-m", "pip", "install", "-e", "backend", "--quiet")
# Ixtiyoriy: bazani shifrlash va kalitlarni Windows hisob ma'lumotlari omborida saqlash
& $venvPy -m pip install "sqlcipher3-wheels>=0.5" "keyring>=24" --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "Diqqat: shifrlash kutubxonasi o'rnatilmadi - baza shifrlanmagan holda ishlaydi." -ForegroundColor Yellow }

Step "Interfeys qurilmoqda"
Push-Location (Join-Path $Root "frontend")
try {
    Run "npm.cmd" @("install", "--no-audit", "--no-fund")
    Run "npm.cmd" @("run", "build")
} finally { Pop-Location }

Step "Tayyor"
Write-Host "EngCheck o'rnatildi. Endi ishga tushiriladi; keyingi safar 'ishga-tushirish.bat' ni bosing." -ForegroundColor Green
& (Join-Path $PSScriptRoot "ishga-tushirish.ps1")
