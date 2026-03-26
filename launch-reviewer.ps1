# Sprites Review Orchestrator — Terminal 2
# Real-time quality supervisor for the Work Orchestrator (Terminal 1)
$Host.UI.RawUI.WindowTitle = "Sprites Reviewer"

Write-Host @"

  ╔══════════════════════════════════════════╗
  ║   SPRITES REVIEW ORCHESTRATOR            ║
  ║   Terminal 2 — Real-Time Quality Judge   ║
  ╚══════════════════════════════════════════╝

"@ -ForegroundColor Magenta

# Check prerequisites
$ok = $true
if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "  [OK] Node $(node --version)" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Node not found" -ForegroundColor Yellow
    $ok = $false
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "  [OK] Python $(python --version 2>&1)" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Python not found" -ForegroundColor Yellow
}

# Check review queue
$queueDir = "C:\Users\olive\SpritesWork\brain\review-queue"
if (Test-Path $queueDir) {
    $pending = (Get-ChildItem $queueDir -Filter "*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "-review\.json$|-escalate\.json$" }).Count
    Write-Host "  [OK] Review queue: $pending pending" -ForegroundColor Green
} else {
    New-Item -ItemType Directory -Path $queueDir -Force | Out-Null
    Write-Host "  [OK] Review queue created" -ForegroundColor Green
}

# Check if Terminal 1 is running
Write-Host ""
Write-Host "  Launching reviewer in Sprites Work directory..." -ForegroundColor Cyan
Write-Host "  CLAUDE.md: .claude/reviewer/CLAUDE.md" -ForegroundColor DarkGray
Write-Host "  Role: Review Orchestrator (judge, critique, escalate)" -ForegroundColor DarkGray
Write-Host "  Escalation: 2 rounds max, then Oliver decides" -ForegroundColor DarkGray
Write-Host ""

# Launch Claude Code from the main working directory
# --append-system-prompt injects the reviewer role on top of the standard CLAUDE.md
# --name makes it identifiable in peer discovery and /resume
# Set environment variable so hooks know this is the reviewer terminal
$env:AIOS_ROLE = "reviewer"

Set-Location "C:\Users\olive\OneDrive\Desktop\Sprites Work"
claude --permission-mode auto --name "reviewer" --append-system-prompt "CRITICAL ROLE OVERRIDE: You are the Review Orchestrator (Terminal 2). Read .claude/reviewer/CLAUDE.md IMMEDIATELY and follow those instructions for the entire session. You do NOT do work tasks. Your only job is to judge, critique, and review Terminal 1's outputs. Start by reading .claude/reviewer/CLAUDE.md, then run list_peers to find Terminal 1, then begin your monitoring loop."
