"""Sprites Agent Launcher — VS Code edition"""
import subprocess
import shutil
import os
from pathlib import Path

ROOT = Path(__file__).parent
BRAIN = Path("C:/Users/olive/SpritesWork/brain")
HOOKS = ROOT / ".claude" / "hooks"

def check(name, cmd):
    if shutil.which(cmd):
        ver = subprocess.run([cmd, "--version"], capture_output=True, text=True)
        print(f"  [OK] {name} {ver.stdout.strip()}")
    else:
        print(f"  [WARN] {name} not found")

def main():
    print("\n  Starting Sprites agent...\n")

    check("Node", "node")
    check("Python", "python")

    # Loop state
    loop_state = BRAIN / "loop-state.md"
    if loop_state.exists():
        print("\n  --- Last Known State ---")
        print(loop_state.read_text(encoding="utf-8"))
        print("  --- End State ---\n")
    else:
        print("  [WARN] brain/loop-state.md not found\n")

    # Hooks
    if HOOKS.is_dir():
        print("  [OK] Hooks folder exists")
    else:
        print("  [WARN] .claude/hooks/ not found")

    print("\n  Remote Control will activate automatically\n")

    # Launch Claude Code with dangerously-skip-permissions
    os.chdir(ROOT)
    os.execvp("claude", ["claude", "--dangerously-skip-permissions", "--remote-control"])

if __name__ == "__main__":
    main()
