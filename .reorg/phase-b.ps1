# Phase B — Folder Reorg (post-session execution)
# =================================================
# Run this from a FRESH PowerShell terminal (no active Claude Code sessions).
# Reason: Phase B moves the brain runtime + SDK source; any running session
# will lose its cwd and hook targets partway through.
#
# Usage:
#   pwsh -ExecutionPolicy Bypass -File .reorg\phase-b.ps1 -DryRun    # preview
#   pwsh -ExecutionPolicy Bypass -File .reorg\phase-b.ps1            # execute
#
# Preconditions (script checks & aborts if not met):
#   - No running Claude Code processes
#   - OneDrive sync paused (for Desktop/Gradata delete)
#   - Clean git working tree (or user acknowledges dirty state)
#   - Current branch committed or stashed

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipChecks
)

$ErrorActionPreference = 'Stop'
$WS = 'C:\Users\olive\OneDrive\Desktop\Sprites Work'
$DESKTOP = 'C:\Users\olive\OneDrive\Desktop'
$OLDBRAIN = 'C:\Users\olive\SpritesWork\brain'
$NEWBRAIN = Join-Path $WS 'Sprites\brain'
$SETTINGS = Join-Path $env:USERPROFILE '.claude\settings.json'

function Say($msg, $color = 'White') { Write-Host "[phase-b] $msg" -ForegroundColor $color }
function Do-Move($from, $to) {
    if (-not (Test-Path $from)) { Say "skip (not present): $from" 'DarkGray'; return }
    if (Test-Path $to) { Say "skip (target exists): $to" 'Yellow'; return }
    if ($DryRun) { Say "DRY-RUN move: $from -> $to" 'Cyan'; return }
    Say "move: $from -> $to" 'Green'
    $parent = Split-Path $to -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Move-Item -Path $from -Destination $to -Force
}
function Do-Delete($path) {
    if (-not (Test-Path $path)) { Say "skip delete (not present): $path" 'DarkGray'; return }
    if ($DryRun) { Say "DRY-RUN delete: $path" 'Cyan'; return }
    Say "delete: $path" 'Red'
    Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $path) { cmd /c "rmdir /s /q `"$path`"" 2>&1 | Out-Null }
}

# ── Preflight ────────────────────────────────────────────────────────
if (-not $SkipChecks) {
    Say 'Preflight checks...' 'Cyan'
    $claudeProcs = Get-Process claude, node -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -match 'claude' }
    if ($claudeProcs) {
        Say "ABORT: claude processes running. Close them first:" 'Red'
        $claudeProcs | Format-Table Id, Name, Path
        exit 1
    }
    Push-Location $WS
    $gitStatus = git status --porcelain 2>$null
    Pop-Location
    if ($gitStatus) { Say "WARNING: git working tree is dirty in $WS. Commit or stash first, or re-run with -SkipChecks." 'Yellow' }
}

Say "=== Phase B starting ($(if ($DryRun){'DRY-RUN'}else{'LIVE'})) ===" 'Cyan'

# ── 1. Delete stale Desktop/Gradata (9d-old main clone) ─────────────
Do-Delete (Join-Path $DESKTOP 'Gradata')

# ── 2. Move Desktop/gradata-cloud → Sprites Work/Gradata/cloud ──────
Do-Move (Join-Path $DESKTOP 'gradata-cloud') (Join-Path $WS 'Gradata\cloud')

# ── 3. Move brain runtime into Sprites/brain ────────────────────────
Do-Move $OLDBRAIN $NEWBRAIN

# ── 4. Move sales persona into Sprites ──────────────────────────────
Do-Move (Join-Path $WS '.forge') (Join-Path $WS 'Sprites\.forge')
Do-Move (Join-Path $WS 'domain\forge') (Join-Path $WS 'Sprites\domain\forge')
Do-Move (Join-Path $WS 'Leads') (Join-Path $WS 'Sprites\Leads')

# ── 5. Move SDK content into Gradata ────────────────────────────────
# pyproject.toml must move WITH src/ and tests/ so `pip install -e .` works from Gradata/
$sdkItems = @(
    'src', 'tests', 'docs', 'examples',
    'pyproject.toml', 'uv.lock', 'README.md', 'CHANGELOG.md',
    'LICENSE', 'CODE_OF_CONDUCT.md', 'CONTRIBUTING.md', 'SECURITY.md', 'CREDITS.md',
    'mkdocs.yml', 'Dockerfile', 'docker-compose.yml',
    'packages', 'gradata-install', 'gradata-plugin',
    'website-next', 'design-system', 'hooks'
)
foreach ($item in $sdkItems) {
    Do-Move (Join-Path $WS $item) (Join-Path $WS "Gradata\$item")
}

# ── 6. Update ~/.claude/settings.json BRAIN_DIR + GRADATA_BRAIN_DIR ─
if (-not $DryRun) {
    Say 'Updating ~/.claude/settings.json BRAIN_DIR' 'Green'
    $raw = Get-Content $SETTINGS -Raw
    $newPath = ($NEWBRAIN -replace '\\', '/')
    $raw = $raw -replace '"GRADATA_BRAIN_DIR":\s*"[^"]+"', "`"GRADATA_BRAIN_DIR`": `"$newPath`""
    $raw = $raw -replace '"BRAIN_DIR":\s*"[^"]+"', "`"BRAIN_DIR`": `"$newPath`""
    Set-Content -Path $SETTINGS -Value $raw -NoNewline
} else {
    Say "DRY-RUN: would update BRAIN_DIR in $SETTINGS" 'Cyan'
}

# ── 7. Update hardcoded defaults in brain/scripts/paths.py ──────────
$brainPaths = Join-Path $NEWBRAIN 'scripts\paths.py'
if ((Test-Path $brainPaths) -and -not $DryRun) {
    Say 'Updating brain/scripts/paths.py fallback paths' 'Green'
    $content = Get-Content $brainPaths -Raw
    $newBrainSlash = ($NEWBRAIN -replace '\\', '/')
    $content = $content -replace 'C:/Users/olive/SpritesWork/brain', $newBrainSlash
    Set-Content -Path $brainPaths -Value $content -NoNewline
}

# ── 8. Commit the reorg ─────────────────────────────────────────────
if (-not $DryRun) {
    Push-Location $WS
    Say 'Staging + committing reorg' 'Green'
    git add -A 2>&1 | Out-Null
    git commit -m "chore(reorg): split into Gradata/Hausgem/Sprites subfolders (Phase B)

Moves:
- SDK (src/, tests/, docs/, pyproject.toml, etc.) -> Gradata/
- Sales persona (.forge/, domain/forge/, Leads/) -> Sprites/
- Brain runtime (C:/Users/olive/SpritesWork/brain) -> Sprites/brain/
- gradata-cloud (Desktop) -> Gradata/cloud/

Rationale: Brand Nat TikTok pattern (one business per top-level folder).
See Sprites Work/{Gradata,Sprites,Hausgem}/CLAUDE.md for scope per folder." 2>&1 | Out-Null
    Pop-Location
}

Say '=== Phase B complete ===' 'Cyan'
Say 'Next: start a fresh Claude Code session from within Sprites Work/. Verify:' 'White'
Say '  - cd Sprites Work/Gradata && pip install -e . works' 'White'
Say '  - cd Sprites Work && claude (hooks resolve BRAIN_DIR correctly)' 'White'
Say '  - Sprites/brain/system.db opens, events append cleanly' 'White'
