#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Gradata installer

Usage:
  bash install.sh
  bash install.sh --help

Installs the Gradata SDK, detects local AI coding tools, initializes a brain,
and wires detected tools through `gradata install --agent`.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if [ "$#" -gt 0 ]; then
  echo "Unsupported argument: $1"
  usage
  exit 2
fi

if [ "$(id -u)" = "0" ]; then
  echo "Don't run with sudo. Install to user space."
  exit 1
fi

OS=$(uname -s)
PLATFORM=""
case "$OS" in
  Darwin) PLATFORM="macos" ;;
  Linux) PLATFORM="linux" ;;
  *) echo "Unsupported: $OS"; exit 1 ;;
esac

if [ "$PLATFORM" = "linux" ] && grep -qi microsoft /proc/version 2>/dev/null; then
  PLATFORM="wsl"
fi

INSTALL_LABEL=""
if command -v uv >/dev/null 2>&1; then
  INSTALL_LABEL="uv tool install gradata"
  install_sdk() { uv tool install gradata; }
elif command -v pipx >/dev/null 2>&1; then
  INSTALL_LABEL="pipx install gradata"
  install_sdk() { pipx install gradata; }
elif command -v pip3 >/dev/null 2>&1; then
  INSTALL_LABEL="pip3 install --user gradata"
  install_sdk() { pip3 install --user gradata; }
else
  echo "Need uv, pipx, or pip3. Install Python 3.11+ first."
  exit 1
fi

echo "Platform: $PLATFORM"
echo "Installing Gradata SDK via: $INSTALL_LABEL"
if ! install_sdk; then
  echo "SDK install command failed. If Gradata is already installed, continuing."
fi

run_gradata() {
  if command -v gradata >/dev/null 2>&1; then
    gradata "$@"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 -m gradata.cli "$@"
    return
  fi
  python -m gradata.cli "$@"
}

TOOLS=()
[ -d "$HOME/.claude" ] && TOOLS+=("claude-code")
[ -d "$HOME/.codex" ] && TOOLS+=("codex")
[ -d "$HOME/.config/Cursor" ] && TOOLS+=("cursor")
[ -d "$HOME/.gemini" ] && TOOLS+=("gemini")
[ -d "$HOME/.config/opencode" ] && TOOLS+=("opencode")
[ -d "$HOME/.hermes" ] && TOOLS+=("hermes")

if [ "${#TOOLS[@]}" -eq 0 ]; then
  echo "No AI coding tool detected. Install Claude Code, Cursor, Codex, etc., then re-run."
  exit 1
fi

echo "Detected AI tools: ${TOOLS[*]}"

if [ -d ".git" ]; then
  BRAIN_DIR="./.gradata"
else
  BRAIN_DIR="$HOME/gradata/default"
fi

run_gradata init --no-interactive "$BRAIN_DIR"

for TOOL in "${TOOLS[@]}"; do
  echo "Installing $TOOL hook..."
  if ! run_gradata install --agent "$TOOL" --brain "$BRAIN_DIR"; then
    echo "$TOOL hook install failed (continuing)"
  fi
done

cat <<EOF

✓ Gradata installed.

Brain location: $BRAIN_DIR
Tools wired:    ${TOOLS[*]}

Next: open your AI tool and start working. Every correction
you make becomes a learned rule in your brain.

Try the demo: gradata demo
View your brain: gradata status

✓ Gradata installed. Next correction = automatic learning.
EOF
