# Gradata Stress Test Protocol

Reproduce the graduation pipeline stress test to verify correction-driven procedural memory works as claimed.

## Prerequisites

```bash
pip install gradata
python -c "from gradata import Brain; print('ok')"
```

## Quick Stress Test (5 minutes)

```bash
cd your-project
python -c "
from gradata import Brain

brain = Brain.init('./stress-brain', domain='Testing', name='Stress Test')

# Simulate 50 corrections across 5 categories
categories = ['DRAFTING', 'TONE', 'ACCURACY', 'PROCESS', 'COMMUNICATION']
for i in range(50):
    cat = categories[i % 5]
    brain.correct(
        draft=f'Draft output {i} in {cat.lower()} style',
        final=f'Corrected output {i} with proper {cat.lower()} handling',
        session=i // 10 + 1,
    )

# Check graduation results
from gradata import parse_lessons
lessons_path = brain.dir / 'lessons.md'
if lessons_path.exists():
    lessons = parse_lessons(lessons_path.read_text())
    states = {}
    for l in lessons:
        states[l.state.value] = states.get(l.state.value, 0) + 1
    print(f'Lessons: {len(lessons)}')
    print(f'States: {states}')
    print(f'Avg confidence: {sum(l.confidence for l in lessons) / max(1, len(lessons)):.2f}')
else:
    print('No lessons generated yet')

# Check manifest
manifest = brain.manifest()
print(f'Manifest keys: {list(manifest.keys())}')
"
```

## Expected Results

- Lessons should be created from corrections
- After 50 corrections, some lessons should have graduated from INSTINCT to PATTERN
- Confidence scores should be between 0.0 and 1.0
- No lessons should have negative confidence
- Kill/promotion ratio should be roughly balanced (not 4:1 kills)

## Full Stress Test (30 minutes)

For a more thorough test with multiple brain personalities:

```bash
git clone https://github.com/gradata-systems/gradata
cd gradata/sdk
pip install -e ".[dev]"
python ../brain/scripts/stress_test_v3.py --personas 5 --rounds 20
```

This runs 5 domain personas (sales, engineering, marketing, recruiting, cs) through 20 rounds each, producing ~500 corrections total.

### What to check

1. **Kill/promotion ratio**: Should be < 3:1 (previous 2:1 penalty caused 74:19)
2. **Confidence distribution**: Should have lessons across the full 0.0-1.0 range
3. **Meta-rule emergence**: With 500+ corrections, at least 1-2 meta-rules should form
4. **No confidence collapse**: Machine-mode corrections shouldn't drive all lessons to 0.0

## Key Constants (calibrated from 2992 real events)

| Constant | Value | Rationale |
|----------|-------|-----------|
| CONTRADICTION_PENALTY | -0.10 | Calibrated 1:1 ratio (was -0.24 at 2:1) |
| SURVIVAL_BONUS | 0.08 | Flat, no severity scaling |
| ACCEPTANCE_BONUS | 0.10 | Unchanged |
| MACHINE_CONTRADICTION_PENALTY | -0.06 | 60% of human penalty for bulk contexts |
| PATTERN threshold | 0.60 | Requires 3+ applications |
| RULE threshold | 0.90 | Requires 5+ applications |

## Reporting Issues

If results differ from expected, run:

```bash
gradata doctor
gradata validate --strict
```

File issues at: https://github.com/gradata-systems/gradata/issues
