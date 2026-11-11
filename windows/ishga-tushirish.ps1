# EngCheck'ni ishga tushiradi va brauzerda ochadi. Ma'lumotlar: %USERPROFILE%\.engcheck
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { throw "Dastur hali o'rnatilmagan. Avval 'ornatish.bat' ni ishga tushiring." }
# Interfeys qurilmagan bo'lsa (brauzerda "not_found" chiqadi) - shu yerda quramiz
if (-not (Test-Path (Join-Path $Root "frontend\dist\index.html"))) {
    Write-Host "Interfeys hali qurilmagan - qurilmoqda (bir necha daqiqa)..." -ForegroundColor Yellow
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw "Node.js topilmadi. https://nodejs.org saytidan LTS versiyasini o'rnating, so'ng shu faylni qayta ishga tushiring."
    }
    Push-Location (Join-Path $Root "frontend")
    try {
        & npm.cmd install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install xato bilan tugadi (yuqoridagi matnni yuboring)." }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw "Interfeysni qurishda xato (yuqoridagi matnni yuboring)." }
    } finally { Pop-Location }
}
# Oldingi nusxa hali ishlab turgan bo'lsa, port band bo'ladi
$busy = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host "EngCheck'ning oldingi nusxasi to'xtatilmoqda..." -ForegroundColor Yellow
    $busy | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}
$Port = 8765
Set-Location (Join-Path $Root "backend")
Start-Job -ArgumentList $Port -ScriptBlock {
    param($p)
    for ($i = 0; $i -lt 60; $i++) {
        try { Invoke-WebRequest "http://127.0.0.1:$p/api/setup" -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Seconds 1 }
    }
    Start-Process "http://127.0.0.1:$p"
} | Out-Null
Write-Host "EngCheck: http://127.0.0.1:$Port   (to'xtatish uchun shu oynani yoping yoki Ctrl+C bosing)" -ForegroundColor Green
& $venvPy -m engcheck --port $Port
