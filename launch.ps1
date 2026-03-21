# Sprites Agent Launcher
Write-Host "Starting Sprites agent..." -ForegroundColor Cyan

# Check Node
if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Node $(node --version)" -ForegroundColor Green
} else {
    Write-Host "[WARN] Node not found - some tools may not work" -ForegroundColor Yellow
}

# Check Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Python $(python --version 2>&1)" -ForegroundColor Green
} else {
    Write-Host "[WARN] Python not found - some tools may not work" -ForegroundColor Yellow
}

# Read loop-state for startup brief
$loopState = Join-Path (Join-Path $PSScriptRoot "brain") "loop-state.md"
if (Test-Path $loopState) {
    Write-Host "`n--- Last Known State ---" -ForegroundColor Cyan
    Get-Content $loopState -Raw | Write-Host
    Write-Host "--- End State ---`n" -ForegroundColor Cyan
} else {
    Write-Host "[WARN] brain/loop-state.md not found - no prior state available" -ForegroundColor Yellow
}

# Check hooks folder
$hooksDir = Join-Path (Join-Path $PSScriptRoot ".claude") "hooks"
if (Test-Path $hooksDir) {
    Write-Host "[OK] Hooks folder exists" -ForegroundColor Green
} else {
    Write-Host "[WARN] .claude/hooks/ not found - hooks may not fire" -ForegroundColor Yellow
}

Write-Host "`nRemote Control will activate automatically" -ForegroundColor Cyan
Write-Host ""

# Launch Claude Code
Set-Location "C:\Users\olive\OneDrive\Desktop\Sprites Work"
claude .
