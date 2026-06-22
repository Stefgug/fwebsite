# start-local.ps1 — launches the mock backend + frontend for a local demo.
# Opens two PowerShell windows (one per server) so you see both logs live.
# Stop the demo by closing the two windows (or Ctrl+C in each).

$repo = $PSScriptRoot | Split-Path -Parent   # repo root (script lives in scripts/)
if (-not (Test-Path (Join-Path $repo "frontend\node_modules"))) {
    Write-Host "frontend dependencies missing — running npm install..." -ForegroundColor Yellow
    Push-Location (Join-Path $repo "frontend"); npm install; Pop-Location
}

Write-Host "Starting mock backend on http://localhost:1999 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit","-Command",
    "`$host.UI.RawUI.WindowTitle='Mock backend :1999'; Set-Location '$repo'; `$env:MOCK_STRAPI_PORT=1999; node scripts/mock-strapi.js"
)

Start-Sleep -Seconds 2

Write-Host "Starting frontend on http://localhost:3000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit","-Command",
    "`$host.UI.RawUI.WindowTitle='Frontend :3000'; Set-Location '$repo\frontend'; npm run dev"
)

Write-Host ""
Write-Host "Both servers launching in separate windows." -ForegroundColor Green
Write-Host "  Mock backend : http://localhost:1999"
Write-Host "  Site         : http://localhost:3000"
Write-Host ""
Write-Host "Give the frontend ~10-20s to compile, then open http://localhost:3000"
Write-Host "To stop: close the two new PowerShell windows."
