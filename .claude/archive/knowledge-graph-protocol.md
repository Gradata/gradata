# Knowledge Graph Protocol (Palantir Ontology)

> "The Ontology represents decisions, not just data." — Palantir
> Every decision has 3 elements: data (input), logic (evaluation), action (execution).

## When to Update the Graph

### After every prospect interaction:
- Add/update prospect → company → industry → persona relationships
- Log the decision: what data informed the approach, what logic chose the angle, what action was taken

### After every deal close (won or lost):
- Update relationship strengths based on outcome
- angle → persona: if angle won, increase strength. If lost, decrease.
- objection → counter: if counter worked, increase. If failed, decrease.
- framework → persona: track which frameworks close which personas

### After every Oliver correction:
- If Oliver overrides an angle choice: weaken the rejected relationship, strengthen the preferred one

## How to Query Before Actions

### Before drafting:
```
python knowledge_graph.py query-playbook [persona]
```
Returns: top angles (by strength), common objections (by frequency), winning frameworks

### Before demo prep:
```
python knowledge_graph.py query-similar prospect:[name]
```
Returns: similar prospects by persona/industry, what worked for them

### After deal close:
```
python knowledge_graph.py query-decision-chain [deal_id]
```
Returns: full history of every decision made on this deal — for win/loss analysis

## Relationship Strength Rules
- New relationship: 0.5 (neutral)
- Positive outcome: +0.1 (max 1.0)
- Negative outcome: -0.1 (min 0.0)
- Oliver override: +0.2 for preferred, -0.2 for rejected (Oliver's signal is worth 2x)
- Strength < 0.2 after 5+ evidence points: relationship is weak, flag for review
- Strength > 0.8 after 5+ evidence points: relationship is strong, auto-recommend

## Updating Strength After Outcomes

Use `add-relationship` with a new strength value — the script averages it into the existing evidence:

```
# Angle worked for this persona → nudge up
python knowledge_graph.py add-relationship "persona:agency_owner" responds_to "angle:time-savings" 0.8

# Objection counter failed → nudge down
python knowledge_graph.py add-relationship "objection:too expensive" countered_by "framework:ROI-first" 0.2

# Oliver override: preferred angle
python knowledge_graph.py add-relationship "persona:pe_rollup" responds_to "angle:portfolio-scale" 0.9
```

## Standard Relationship Labels

| Relationship | Example |
|---|---|
| `responds_to` | persona → angle |
| `raises` | persona → objection |
| `countered_by` | objection → framework |
| `won_with` | persona → framework |
| `lost_because` | prospect → objection |
| `works_at` | prospect → company |
| `in_industry` | company → industry |
| `has_persona` | prospect → persona |
| `similar_to` | prospect → prospect |
| `uses_case_study` | persona → case_study |

## Entity Types

| Type | When to use |
|---|---|
| `prospect` | Individual contact (e.g. "John Smith") |
| `company` | Org name (e.g. "Ugly Ads") |
| `industry` | Vertical (e.g. "ecom_agency", "dtc_brand") |
| `persona` | Role archetype (e.g. "agency_owner", "solo_founder") |
| `angle` | Email/call angle (e.g. "time-savings", "portfolio-scale") |
| `objection` | Common objection (e.g. "too expensive", "not the right time") |
| `case_study` | Reference story (e.g. "Ugly Ads 3x ROAS") |
| `framework` | Sales framework (e.g. "CCQ", "ROI-first", "TRAP") |

## Decision Logging — When to Log

Log a decision whenever:
1. An email angle is chosen (pre-draft gate)
2. A demo thread order is selected (demo prep gate)
3. An objection counter is deployed (live or in follow-up)
4. A close attempt is made (proposal stage)
5. A deal is moved to a new stage

Format for `data_used`: comma-separated sources (e.g. `"PATTERNS.md,Fireflies:transcript-123,Pipedrive:deal-456"`)
Format for `logic_applied`: the rule or framework invoked (e.g. `"LOOP_RULE_1,CCQ,time-savings angle"`)
Format for `action_taken`: the concrete output (e.g. `"Sent cold email v2 — time-savings angle, CCQ framework"`)

## Integration with Session Workflow

**Pre-draft gate step (add after PATTERNS.md check):**
```
python knowledge_graph.py query-playbook [persona]
```
If persona has 5+ evidence points and a strength >0.8 angle: use that angle as default, log override if different.

**Post-close (wrap-up):**
```
python knowledge_graph.py add-relationship "persona:[type]" responds_to "angle:[used]" [0.7 if won, 0.3 if lost]
python knowledge_graph.py query-decision-chain [deal_id]
```
Add win/loss note to decision chain for calibration.

## Script Location
```
C:\Users\olive\OneDrive\Desktop\Sprites Work\Scripts\knowledge_graph.py
```
DB: `C:\Users\olive\SpritesWork\brain\system.db` (shared with analytics.py and chaos tests)
