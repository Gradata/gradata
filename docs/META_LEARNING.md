# Gradata Meta-Learning Architecture

## How the Brain Learns (4 Levels)

The Gradata brain compounds knowledge through a 4-level learning architecture.
Each level feeds the graduation pipeline (INSTINCT → PATTERN → RULE) with
signals of different strength and origin.

---

## Level 0: User → Brain (IMPLEMENTED)

**Signal strength: 1.0x (ground truth)**

The user corrects an AI-generated output. The diff between draft and final
is the strongest possible learning signal — a human edited real text.

```
User prompt → AI draft → brain.log_output(text, rules_applied=[...])
                       → User edits the draft
                       → brain.correct(draft, final)
                           → diff_engine.compute_diff()        [edit distance + severity]
                           → edit_classifier.classify_edits()  [TONE/CONTENT/STRUCTURE/FACTUAL/STYLE]
                           → pattern_extractor.extract_patterns()
                           → CORRECTION event emitted
                       → update_confidence(lessons, corrections)
                           → Contradicted categories: FSRS penalty (-0.20 * severity)
                           → Survived categories: FSRS bonus (+0.08)
                       → graduate(lessons)
                           → INSTINCT(0.60) → PATTERN(0.90) → RULE
```

**Why it can't be gamed:** Edit distance is computed from real text diffs,
not user-declared. Severity is measured, not self-reported.

---

## Level 1: Brain → Agents (IMPLEMENTED)

**Communication method: XML-tagged rules in system prompt**

When the brain has graduated rules, they are injected into agent prompts:

```
brain.apply_brain_rules(task, context)
  → rule_engine.apply_rules(lessons, scope)
    → Filter: only PATTERN + RULE state (INSTINCT excluded)
    → Score: weighted scope matching (exact task_type > partial > wildcard)
    → Sort: state priority DESC, difficulty DESC, relevance DESC
    → Cap: max 10 rules
  → format_rules_for_prompt(rules)
    → <brain-rules>
        1. [RULE:0.95] DRAFTING: Never use em dashes in email prose
        2. [PATTERN:0.72] TONE: Use colons over dashes for emphasis
        ...
        REMINDER: DRAFTING: Never use em dashes in email prose
      </brain-rules>
```

The agent reads these rules like any system instruction. Primacy/recency
positioning ensures the highest-priority rules get the most attention.

**Agent approval gate:** New agent types start at CONFIRM (human reviews
every output). After 70% first-draft acceptance across 10+ outputs, gate
graduates to PREVIEW (quick review). After 90% FDA across 25+, AUTO mode.
3 consecutive rejections demote one level.

---

## Level 2: Agents → Brain (STUB — upward distillation)

**Signal strength: 0.5x (agent-discovered, not human-validated)**

When an agent discovers a behavioral pattern through repeated application:

```
Agent PATTERN/RULE (confidence ≥ 0.60)
  → emit AGENT_RULE_CANDIDATE event
  → Brain evaluates: is this useful beyond the agent's narrow scope?
  → If accepted: create brain-level INSTINCT at confidence 0.15
    (lower than human corrections at 0.30 — requires human confirmation)
  → Normal graduation pipeline from there
```

**Scope guard:** Agent scope tags are preserved during distillation. A research
agent's rule scoped to `task_type: research` stays scoped — it won't get
injected into email drafting prompts.

**Agent → Agent communication:** There is no direct agent-to-agent channel.
All knowledge flows through the brain layer. Agent A's graduated rule distills
up to brain, brain injects into Agent B's prompt next session. The brain is
the shared knowledge bus.

---

## Level 3: External Signals → Brain (NEW)

**Signal strength: 0.3-0.5x (attribution uncertain)**

Real-world outcomes (email replies, deal progression, calendar bookings) are
captured as DELTA_TAG events with outcome tags. These feed back into rule
confidence — but weaker than user corrections because attribution is uncertain.

```
External signal (email reply, CRM deal update, Calendar booking)
  → DELTA_TAG event with tags: entity:, channel:, outcome:
  → brain.process_outcome_feedback(session)
    → collect_outcomes(): query DELTA_TAG events with outcomes
    → attribute_to_rules(): match outcomes to OUTPUT events via rules_applied field
    → compute_external_confidence_delta(): per-rule delta, capped
  → Apply deltas after update_confidence() (separate, not mixed)
```

**Outcome → Signal mapping:**

| Outcome | Signal | Weight | Rationale |
|---------|--------|--------|-----------|
| positive-reply | acceptance | 0.5x | Rule likely helped, but other factors exist |
| meeting-booked | acceptance | 0.5x | Strong positive signal |
| deal-advanced | acceptance | 0.5x | Multiple interactions contributed |
| demo-completed | acceptance | 0.5x | Good prep rules validated |
| deal-lost | contradiction | 0.3x | Can't isolate cause — competitor, timing, price |
| negative-reply | contradiction | 0.3x | May not be the email's fault |
| no-reply | neutral | 0.0x | 97% of cold emails get no reply — no signal |
| ghosted | neutral | 0.0x | Ambiguous — not actionable |

**Safeguards:**
- Min 20 total outcomes before activation (cold start protection)
- Max 3 signals per rule per session (prevents volume gaming)
- Can't cross tier boundaries (external alone can't promote INSTINCT → PATTERN)
- Idempotent (OUTCOME_FEEDBACK_PROCESSED event prevents double-counting)

---

## Why This Architecture Works

1. **Strongest signal dominates:** User corrections (1.0x) > Agent feedback (0.5x) > External signals (0.3-0.5x). The hierarchy ensures human judgment always wins.

2. **Can't be gamed:** Edit distance is computed from real diffs. External signals come from 3rd party APIs (email, CRM, Calendar). The brain can't declare its own success.

3. **Compounds over time:** Each level adds signal. A rule that survives user corrections AND gets positive email replies AND is validated by agent application has triple confirmation.

4. **Degrades gracefully:** If no external signals exist, Level 0+1 work fine alone. If no agents exist, Level 0 works alone. Each level is additive, not required.

---

## The Five Proof Metrics

These metrics prove the brain is learning:

| Metric | Computation | What it proves |
|--------|-------------|---------------|
| **CRO Trend** | corrections/outputs, window-over-window | User corrects less over time |
| **FDA** | sessions with zero major corrections / total | First drafts accepted as-is |
| **Categories Extinct** | categories with zero corrections in 20 sessions | Entire mistake types eliminated |
| **Lesson Graduation** | INSTINCT → PATTERN → RULE counts | Observations become confirmed rules |
| **Compound Score** | Weighted 0-100 health number | Single "is it working?" metric |

All five are in `brain.manifest.json`, computed from `system.db` events,
and trackable session-by-session.
