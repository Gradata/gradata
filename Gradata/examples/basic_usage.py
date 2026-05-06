"""Basic Gradata usage — learn from corrections in 10 lines."""

from pathlib import Path

from gradata.brain import Brain

# Create a brain (or open existing)
brain_dir = Path("./demo-brain")
brain_dir.mkdir(exist_ok=True)
(brain_dir / "lessons.md").write_text("", encoding="utf-8")
brain = Brain(str(brain_dir))

# Simulate corrections — your AI drafts, you fix
corrections = [
    ("We are pleased to inform you of our decision.", "Hey, here's what we decided."),
    ("Dear Sir, Please find attached the requested document.", "Here's the doc you asked for."),
    ("I would like to suggest that we consider...", "Let's just do it."),
    ("Per our previous correspondence regarding...", "Following up on our chat —"),
    ("We sincerely appreciate your patience.", "Thanks for waiting."),
]

for draft, final in corrections:
    result = brain.correct(draft=draft, final=final)
    severity = result.get("diff", {})
    print(f"  Corrected: {draft[:40]}... → {final[:40]}...")

# Check what the brain learned
lessons_path = brain_dir / "lessons.md"
if lessons_path.exists():
    content = lessons_path.read_text(encoding="utf-8")
    print(f"\n--- Lessons learned ({content.count('[INSTINCT')} instincts) ---")
    for line in content.splitlines():
        if line.startswith("["):
            print(f"  {line[:100]}")

# Check convergence (need multiple sessions for meaningful data)
conv = brain.convergence()
print(f"\nConvergence: {conv['trend']} ({conv['total_corrections']} corrections)")

print("\nDone! Run this again — the brain will reinforce existing lessons.")
