# Enhancements API Reference

Layer 1 enhancements build on Layer 0 patterns. Import from `aios_brain.enhancements`.

## Self-Improvement

```python
from aios_brain.enhancements.self_improvement import parse_lessons, Lesson

# Parse lessons from a lessons.md file
lessons = parse_lessons(lessons_text)

for lesson in lessons:
    print(f"{lesson.status}: {lesson.category} (confidence={lesson.confidence})")
```

## Agent Graduation

```python
from aios_brain.enhancements.agent_graduation import AgentGraduationTracker

tracker = AgentGraduationTracker(brain_dir)

# Record agent output quality
tracker.record_outcome("research", output_preview="...", outcome="approved", edits=None, session=42)
tracker.record_outcome("writer", output_preview="...", outcome="edited", edits="rewrote intro", session=42)

# Check approval gate level
gate = tracker.get_approval_gate("research")  # "confirm" | "preview" | "auto"

# Get agent's graduated lessons for prompt injection
rules = tracker.get_agent_rules("research")
```

## Diff Engine

```python
from aios_brain.enhancements.diff_engine import compute_diff

diff = compute_diff(
    "Hi John, I wanted to reach out about our AI platform.",
    "John, saw your team scaling ads. We cut creative testing time in half.",
)
print(diff.edit_distance)     # 0.72
print(diff.severity)          # "major"
print(diff.summary_stats)     # {"lines_added": 1, "lines_removed": 1}
```

## Edit Classifier

```python
from aios_brain.enhancements.edit_classifier import classify_edits, summarize_edits

classifications = classify_edits(diff)
summary = summarize_edits(classifications)

for c in classifications:
    print(f"{c.category}: {c.severity} — {c.description}")
```

## Pattern Extractor

```python
from aios_brain.enhancements.pattern_extractor import extract_patterns

patterns = extract_patterns(classifications, scope=scope)
```

## Metrics

```python
from aios_brain.enhancements.metrics import compute_metrics

metrics = compute_metrics(db_path, window=20)
# metrics.correction_rate, metrics.severity_distribution, etc.
```

## Failure Detectors

```python
from aios_brain.enhancements.failure_detectors import detect_failures
from aios_brain.enhancements.metrics import compute_metrics

current = compute_metrics(db_path, window=10)
previous = compute_metrics(db_path, window=20)
alerts = detect_failures(current, previous)
for alert in alerts:
    print(f"ALERT: {alert.detector} [{alert.severity}] {alert.message}")
```

## CARL

```python
from aios_brain.enhancements.carl import ContractRegistry, BehavioralContract

registry = ContractRegistry()
registry.register(BehavioralContract(
    name="sales_rules",
    domain="sales",
    constraints=["Never include pricing in cold emails"],
))
constraints = registry.get_constraints("draft cold email")
```

## Quality Gates

```python
from aios_brain.enhancements.quality_gates import QualityGate, GENERAL_RUBRICS

gate = QualityGate(rubrics=GENERAL_RUBRICS, threshold=8.0, max_cycles=2)

# Single evaluation
verdict = gate.evaluate(output_text, scorer=my_scorer)
print(verdict.passed, verdict.overall_score)

# Full fix loop
result = gate.run_with_fix(output_text, scorer=my_scorer, fixer=my_fixer)
print(result.converged, result.cycles_used)
```

## Correction Tracking

```python
from aios_brain.enhancements.correction_tracking import compute_correction_profile

profile = compute_correction_profile(db_path, window=10)
print(f"Rate: {profile.correction_rate}")
print(f"Trend: {profile.density_trend}")      # improving / stable / degrading
print(f"MTBF: {profile.mtbf} sessions")       # mean sessions between corrections
print(f"MTTR: {profile.mttr} sessions")       # mean correction streak length
```

## Brain Scores

```python
from aios_brain.enhancements.brain_scores import compute_brain_scores

scores = compute_brain_scores(db_path)
# Compound metric: events, corrections, graduation, coverage
```

## Judgment Decay

```python
from aios_brain.enhancements.judgment_decay import compute_decay, compute_batch_decay

# Single lesson decay
result = compute_decay(lesson, current_session=42, idle_sessions=5)
print(result.new_confidence)

# Batch decay across all lessons
results = compute_batch_decay(lessons, current_session=42)
# Each result has new_confidence, was_reinforced, flagged_untestable
```

## Reports

```python
from aios_brain.enhancements.reports import generate_health_report

report = generate_health_report(db_path)
print(report.healthy)
print(report.issues)
```

## Truth Protocol

```python
from aios_brain.enhancements.truth_protocol import verify_claims, verify_citations, verify_mutations

# Check for banned phrases and unsupported numbers
verdict = verify_claims(output_text)
print(verdict.passed, verdict.violations)

# Check citations against known sources
verdict = verify_citations(output_text, sources=["report.pdf", "api_response"])

# Check that state-changing actions have audit evidence
verdict = verify_mutations(["created deal | id=194", "sent email -> thread_id=abc"])
```
