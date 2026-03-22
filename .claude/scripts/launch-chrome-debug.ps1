# Launch Chrome with remote debugging enabled
# Run this once — then the plan-usage scraper can connect to your running Chrome
# Usage: Right-click → Run with PowerShell, or: powershell -File .claude\scripts\launch-chrome-debug.ps1

$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$debugPort = 9222

Write-Host "Launching Chrome with remote debugging on port $debugPort..."
Start-Process $chromePath -ArgumentList "--remote-debugging-port=$debugPort"
Write-Host "Chrome launched. The plan-usage scraper can now connect."
Write-Host "You can use Chrome normally — debugging runs in background."
