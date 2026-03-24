"""
AIOS Brain SDK — Quickstart Example
====================================
Creates a brain, logs outputs, records corrections, and shows
how the brain learns from feedback over time.

Run:  python examples/quickstart.py
"""

from aios_brain import Brain

# 1. Create a new brain
brain = Brain.init("./my-brain", domain="Sales", name="Demo Brain")
print(f"Brain created at: {brain.dir}")

# 2. Log an AI-generated output
brain.log_output(
    "Hi John, I wanted to reach out about our AI platform.",
    output_type="email",
    self_score=7.0,
    session=1,
)
print("Output logged.")

# 3. User corrects the output — this is how the brain learns
event = brain.correct(
    draft="Hi John, I wanted to reach out about our AI platform.",
    final="John — saw your team is scaling paid ads. We automate the creative testing that usually eats 15hrs/week. Worth a look?",
    session=1,
)
print(f"Correction recorded: severity={event['data']['severity']}, "
      f"edit_distance={event['data']['edit_distance']:.2f}")

# 4. Get applicable rules for next draft
rules = brain.apply_brain_rules("email_draft", {"audience": "marketing_manager"})
if rules:
    print(f"Rules for next draft:\n{rules}")
else:
    print("No rules yet — brain needs more corrections to graduate lessons.")

# 5. Check brain health
health = brain.health()
print(f"\nBrain health: {health['events_total']} events, "
      f"{health['corrections_total']} corrections, "
      f"{health['outputs_total']} outputs")

# 6. Generate manifest (quality proof)
manifest = brain.manifest()
print(f"Manifest: {manifest['metadata'].get('sessions_trained', 0)} sessions trained")

# 7. Search the brain
results = brain.search("email tone")
print(f"Search results: {len(results)}")

print("\nDone! Your brain is learning.")
