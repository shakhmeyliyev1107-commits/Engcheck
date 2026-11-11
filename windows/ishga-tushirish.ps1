# EngCheck'ni ishga tushiradi va brauzerda ochadi. Ma'lumotlar: %USERPROFILE%\.engcheck
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { throw "Dastur hali o'rnatilmagan. Avval 'ornatish.bat' ni ishga tushiring." }
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
