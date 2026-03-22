---
name: rule-validator
description: Validates CARL rules for conflicts, dead references, and coverage gaps. Run after any rule addition or at startup if rules changed since last session. Use when adding rules, debugging unexpected behavior, or during system health checks.
---

# Rule Validator

## What It Checks

### 1. Conflict Detection
- Scan all .carl/ domain files for rules that contradict each other
- Flag: two rules giving opposite instructions for the same trigger
- Flag: a rule referencing a file that doesn't exist
- Flag: a rule referencing a LOOP_RULE number that doesn't exist

### 2. Dead Reference Check
- Every rule that references a file path -> verify file exists
- Every rule that references another rule by number -> verify that rule exists
- Every rule that references a brain/ file -> verify it exists
- Report: "[RULE] references [FILE] which does not exist"

### 3. Coverage Analysis
- List all trigger keywords across all CARL domains
- Flag overlapping keywords between domains (same keyword triggers multiple domains)
- Flag orphan keywords (in manifest but not used in any rule)

### 4. Threshold Consistency
- All confidence thresholds should use the same scale
- All kill switch thresholds should be consistent (5 cycles)
- All bloat limits should be documented and non-conflicting

### 5. Event Connection Integrity
- Every event connection (hooks, LOOP_RULE_28-34) references a source and target component
- Verify both source and target exist and are tracked in system-patterns.md
- Verify no circular dependencies that could cause infinite loops

## How to Run

Read all .carl/ files. For each rule:
1. Extract file references (any path-like string)
2. Extract rule references (LOOP_RULE_N patterns)
3. Check for contradiction keywords ("never" vs "always" on same topic)
4. Verify referenced files exist

Output format:
```
RULE VALIDATION -- [date]
Rules scanned: [N] across [N] domains
Conflicts: [N] (list)
Dead references: [N] (list)
Coverage gaps: [N] (list)
Cross-wire integrity: [PASS/FAIL]
VERDICT: [CLEAN / NEEDS ATTENTION / CRITICAL]
```

Run automatically when: new rules added, session startup if .carl/ files modified since last session.
