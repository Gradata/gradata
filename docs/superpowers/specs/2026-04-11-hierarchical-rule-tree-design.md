# Hierarchical Rule Tree — Design Spec (v2, post-adversary)

**Date:** 2026-04-11
**Goal:** Organize rules into a hierarchical tree (Rosch category → domain → task_type → rule) for better scope isolation, a browsable knowledge structure, and retrieval precision at scale.

---

## Problem

Rules are flat records in system.db scored against 8 scope dimensions. Every retrieval scores ALL rules to find the top 5. This causes:
- Scope collisions across domains (SIM103: 8/50 agents flagged this)
- No navigable structure for users to browse what their brain learned
- No natural boundary for cloud sharing (all-or-nothing)
- At scale (500+ rules), retrieval precision degrades as irrelevant rules compete with relevant ones

**Note:** At current scale (100-300 rules), flat scoring is fast enough. The primary motivation is scope isolation and browsability, not raw speed. Speed becomes a bonus at 500+ rules.

## Solution

Organize rules into a tree stored as a `path` column in the lessons table. Rosch 6-category taxonomy is the trunk. Domain and task_type form the branches. Individual rules are leaves. A task-type index provides O(1) fast-path retrieval. Rules auto-climb the tree as they prove useful across sibling branches.

---

## Tree Structure

```
root/
  TONE/                              ← Rosch category (6 trunk nodes)
    _meta: {count: 14, avg_conf: 0.72}
    sales/                           ← domain
      email_draft/                   ← task_type
        rule_042                     ← leaf rule
        rule_087
      demo_prep/
        rule_103
    engineering/
      code_review/
        rule_211
  ACCURACY/
    sales/
      email_draft/
        rule_055
  STRUCTURE/
    ...
  DRAFTING/
    ...
  FORMAT/
    ...
  SECURITY/
    ...
```

Six trunk nodes from the existing Rosch taxonomy. Branches are domain + task_type (already in RuleScope). Leaves are individual Lesson records.

---

## Storage: path column in lessons table

No new tables. Add a `path TEXT` column to the existing lessons representation in system.db.

```sql
-- Path format: "CATEGORY/domain/task_type"
-- Examples:
--   "TONE/sales/email_draft"
--   "ACCURACY/engineering/code_review"
--   "STRUCTURE"  (climbed to trunk — applies everywhere)

ALTER TABLE lessons ADD COLUMN path TEXT DEFAULT '';
```

Backfill existing lessons by joining non-empty segments:
```python
path = "/".join(seg for seg in [category, scope_domain, scope_task_type] if seg)
# "TONE/sales/email_draft" or "TONE/sales" or "TONE"
```
Always strip trailing slashes. Normalize to lowercase for consistency.

---

## Retrieval: Task-Type Fast-Path Index

An in-memory dict built at brain load time. Maps task_type → list of tree paths that contain rules for that task.

```python
# Persisted in SQLite table `rule_tree_index`. Rebuilt on dirty flag (lesson writes invalidate).
# Lazy-loaded on first query, NOT at Brain.__init__.
task_index: dict[str, set[str]] = {
    "email_draft": {"TONE/sales/email_draft", "ACCURACY/sales/email_draft", ...},
    "code_review": {"TONE/engineering/code_review", "ACCURACY/engineering/code_review", ...},
}
```

### Retrieval algorithm

```python
def get_rules_for_context(tree, task_type, domain, max_rules=5):
    # 1. Fast-path: get candidate paths from task index
    paths = task_index.get(task_type, set())
    
    # 2. For each path, collect rules walking UP to root
    #    Leaf rules (most specific) get a specificity bonus
    candidates = []
    for path in paths:
        # Collect from leaf, then parent, then grandparent, up to trunk
        node = path
        depth = path.count("/")
        while node:
            rules_at_node = tree.get(node, [])
            for rule in rules_at_node:
                # Deeper = more specific = higher bonus
                rule._specificity = depth
                candidates.append(rule)
            node = "/".join(node.split("/")[:-1])  # walk up
            depth -= 1
    
    # 3. Score: existing rule_ranker composite score unchanged
    #    Specificity is a TIEBREAKER only — same composite = prefer more specific
    #    Different composites = composite wins
    return rank_rules(candidates, max_rules=max_rules)
```

This replaces the current approach of scoring ALL rules. Instead: index lookup → walk up tree → score only candidates. O(branch_size) instead of O(total_rules).

### Fallback

If task_type is unknown or not in the index, fall back to scoring all trunk-level (climbed) rules. These are the universal rules that apply everywhere — same as the current behavior but limited to proven-universal rules.

---

## Auto-Climb: Scope Generalization

Rules start at the most specific leaf. When a rule proves useful across sibling branches, it climbs to the parent node (broader scope).

### Climb trigger

A rule climbs when it fires successfully (no correction in that category) in **2+ sibling branches** within **5 sessions**.

Example:
1. `rule_042` lives at `TONE/sales/email_draft/`
2. User does a demo_prep task. Rule fires (injected from parent-walk). No correction.
3. User does another demo_prep task next session. Rule fires again. No correction.
4. Climb trigger: rule fired in `email_draft/` (home) + `demo_prep/` (sibling) = 2 branches
5. Rule moves to `TONE/sales/` (parent node)

### Climb levels

```
Level 0 (leaf):   TONE/sales/email_draft/rule_042  — most specific
Level 1 (branch): TONE/sales/rule_042              — applies to all sales tasks
Level 2 (trunk):  TONE/rule_042                    — applies everywhere in TONE
```

A rule at Level 2 is effectively a meta-rule — it's proven universal within its category.

### Climb ↔ Graduation relationship

Climbing is orthogonal to graduation (INSTINCT → PATTERN → RULE). A rule can:
- Be RULE-state at Level 0 (high confidence, narrow scope)
- Be PATTERN-state at Level 1 (moderate confidence, medium scope)
- Climbing doesn't change confidence. Graduation doesn't change scope.

### Anti-climb: scope contraction

If a climbed rule starts getting contradicted at its current level, it contracts back to the last stable level.

Trigger: 2+ contradictions at current level within 3 sessions → rule contracts back one level.

### Oscillation damping (adversary fix)

Three safeguards prevent climb/contract cycles:
1. **Minimum dwell time:** A rule must stay at its current level for 5 sessions before it can climb again.
2. **Climb cap:** Maximum 3 total climb events per rule lifetime. After 3 climbs, the rule's level is frozen.
3. **No excluded_paths:** Contraction moves the rule DOWN one level entirely (simpler than partial exclusion). If a trunk-level rule gets contradicted in one branch, it goes back to the branch level, not "trunk minus one branch."

Each rule tracks: `climb_count` (int), `last_climb_session` (int), `current_level` (int 0-2).

---

## Placement: Where New Rules Go

When `self_improvement.py` creates a new lesson from a correction:

1. Classify the correction: primary category (first Rosch match), secondary categories (remaining matches)
2. Build path from primary: `"/".join(seg for seg in [category, domain, task_type] if seg)`
3. Store `secondary_categories: list[str]` as metadata on the rule (no duplication in tree)
4. Place rule at primary path
5. Update the task-type index

If domain or task_type are unknown, the rule starts higher in the tree:
- No task_type → `TONE/sales`
- No domain → `TONE`
- No category → flat fallback pool (existing behavior, not a tree node)

### Multi-category rules (adversary fix)

Rules like "don't use em dashes" span TONE + FORMAT. The rule lives at its primary category path but also surfaces when retrieving secondary categories. During retrieval, after collecting candidates from the primary tree walk, also include rules whose `secondary_categories` list contains the queried category. No duplication in storage — just a metadata field that widens retrieval.

---

## Export API

```python
# Browse the tree
tree = brain.browse()                          # returns full tree structure
tree = brain.browse("TONE/sales/")             # returns subtree
rules = brain.browse("TONE/sales/email_draft") # returns rules at leaf

# Export to external tools
brain.export(format="obsidian", path="./vault/")   # folder tree + .md files
brain.export(format="json", path="./export.json")   # full tree as JSON
brain.export(format="markdown", path="./docs/")     # flat markdown summary

# CLI
# gradata browse TONE/sales/
# gradata export --format obsidian --path ./vault/
```

### Obsidian export format

Each rule becomes a `.md` file with YAML frontmatter. Each tree node becomes a folder. `_index.md` in each folder shows branch stats.

```markdown
---
id: rule_042
confidence: 0.85
state: PATTERN
path: TONE/sales/email_draft
fires: 12
misfires: 1
tags: [conciseness, cold-outreach]
---

Be casual and direct with VPs. Skip "Dear" and "I hope this finds you well."

## Evidence
- 4 corrections across sessions 14, 18, 22, 31

## Related
- [[rule_087]] — email subject line brevity
```

---

## Cloud Sharing: Branch-Level Opt-In

```python
brain.share("TONE/sales/")           # share sales tone rules to marketplace
brain.share("ACCURACY/", public=True) # share all accuracy rules publicly
brain.keep_private("SECURITY/")       # never sync security rules
```

### Privacy gate (adversary fix)

`brain.share()` filters by `transfer_scope` (existing field on rules: PERSONAL/TEAM/UNIVERSAL). Only UNIVERSAL rules are shared by default. PERSONAL and TEAM rules are excluded unless explicitly overridden:

```python
brain.share("TONE/sales/")                          # only UNIVERSAL rules in this branch
brain.share("TONE/sales/", include_personal=True)    # explicitly opt in personal rules
```

The tree provides natural privacy boundaries. Users share branches, not individual rules. Shared branches get aggregated in the cloud — when 50+ users share the same rule in `TONE/sales/email_draft/`, it becomes a marketplace recommendation.

---

## Migration (adversary-hardened)

Existing brains have flat lessons with category + scope fields. Migration:

1. Add `path TEXT DEFAULT ''` column to lessons table
2. Read all lessons from system.db
3. For each lesson: parse `scope_json`, build path from `"/".join(seg for seg in [category, domain, task_type] if seg)`
4. Normalize: lowercase, strip trailing slashes, collapse double slashes
5. Write path column
6. Build and persist task-type index in `rule_tree_index` table
7. **Validate:** count lessons with non-empty paths. If <90% got valid paths, log warning but continue (don't abort — empty paths fall back to flat scoring)
8. **Error handling:** malformed `scope_json` records get `path = category` (trunk-level fallback)

Backward compatible: if `path` is empty, fall back to current flat scoring. No existing behavior changes for un-migrated lessons.

No rollback needed — the `path` column is purely additive. Flat scoring still works for all rules regardless of path value.

---

## Files to Modify

| File | Change |
|------|--------|
| `src/gradata/_scope.py` | Add `path` field to RuleScope, path builder |
| `src/gradata/_db.py` | Add `path` column migration |
| `src/gradata/rules/rule_engine.py` | Tree-based retrieval with fast-path index |
| `src/gradata/rules/rule_ranker.py` | Add specificity bonus to scoring |
| `src/gradata/enhancements/self_improvement.py` | Place new rules at correct tree path |
| `src/gradata/enhancements/meta_rules.py` | Climbed trunk-level rules = meta-rules |
| `src/gradata/brain.py` | Add `browse()` and `export()` methods |
| `src/gradata/brain_inspection.py` | Tree visualization for inspection |
| `src/gradata/_export_brain.py` | Obsidian/JSON/markdown export formatters |

New files:
| File | Purpose |
|------|---------|
| `src/gradata/rules/rule_tree.py` | RuleTree class: build, query, climb, contract |
| `tests/test_rule_tree.py` | Tree operations tests |

---

## Success Criteria

1. No scope collisions: rules in `TONE/sales/` never leak to `TONE/engineering/`
2. Auto-climb works: rules proven across 2+ siblings broaden to parent
3. Anti-climb works: contradicted rules contract back one level, with 5-session cooldown
4. No oscillation: climb cap (3 max) + dwell time prevents infinite cycles
5. Multi-category rules surface in both primary and secondary category retrievals
6. Obsidian export produces valid vault with wiki links
7. Cloud sharing respects transfer_scope (UNIVERSAL only by default)
8. Migration backfills 90%+ of existing lessons with valid paths
9. Backward compatible: empty path falls back to flat scoring
10. All existing tests pass (1934+)
11. Task-type index persisted in SQLite, lazy-loaded, invalidated on writes
