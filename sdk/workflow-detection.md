# Workflow Detection System

> Automatically identifies recurring task patterns across sessions.
> Agent suggests, user confirms — never auto-saves without approval.
> Works for any domain: client onboarding, audit prep, candidate screening,
> campaign setup, session notes, quarterly reports, contract review, etc.

---

## Detection Logic

### Task Signatures

Every major task completed in a working session gets hashed into a **task signature** — a tuple of:

```
(task_type, tools_used, output_type, steps_followed)
```

**Examples:**
- `(draft_email, [gmail, vault], email, [research, draft, self-check, approval])`
- `(prepare_report, [sheets, web_search], report, [gather, analyze, format, review])`
- `(review_contract, [file_read, web_search], annotated_doc, [read, flag_risks, summarize])`

### Trigger Conditions

A workflow suggestion fires when ALL of these are true:

1. **Same task signature appears in 3+ different sessions** — not 3 times in one session, but across separate working sessions
2. **The agent recognizes the same step order** — at least 70% of steps match between instances
3. **The task takes 2+ tool calls** — trivial single-step tasks don't need workflows
4. **The signature has NOT been previously declined** — declined signatures enter a 10-session cooldown

### Detection Process

**At session wrap-up:**
1. Hash each major task completed into a signature
2. Append to `workflows/detection-log.md` with session date and step details
3. Compare new signature against all prior entries
4. If match count reaches 3: queue the suggestion for next session startup

**At next session startup (if queued):**
1. Present the detected pattern to the user:
   > "I've noticed you do [task description] in a similar way across sessions.
   > Want me to save this as a named workflow? I'll capture the steps, tools,
   > and quality checks so it runs consistently."
2. If user confirms → create workflow file
3. If user declines → mark signature as declined, set 10-session cooldown

---

## Saved Workflow Format

Created in `workflows/[name].md`:

```markdown
# Workflow: [Name]

Created: [date] from [session references]
Trigger: [phrase or intent that activates this workflow]

## Steps
1. [Step with tool and expected output]
2. [Step with tool and expected output]
...

## Tools Required
- [tool 1]
- [tool 2]

## Quality Checks
- [check derived from observed patterns]
- [check derived from user corrections during these tasks]

## Starter Lessons
[5 INSTINCT lessons generated from observed patterns — see below]
```

---

## Auto-Integration

When a workflow is saved:

1. **context-manifest.md** — add as Tier 2 entry with trigger intent
2. **Starter lessons** — generate 5 INSTINCT lessons from the 3 observed instances:
   - What step required retries? → "Verify [X] before [step]"
   - What correction did the user give? → "Always [correction] when [task]"
   - What tool failed? → "Use [fallback] when [tool] fails during [task]"
   - What took longest? → "Optimize [step] by [method]"
   - What was the quality gap? → "Check [dimension] before presenting [output]"
3. **detection-log.md** — mark signature as "saved" so detection stops suggesting it

---

## Decline Handling

- Declined signature gets a 10-session cooldown
- After cooldown, if the pattern reappears 3 more times with different step details (user changed their approach), re-suggest
- If declined twice for the same signature, permanently suppress

---

## Maintenance

- Detection log is append-only during sessions
- At every 10th session wrap-up: compact the log (remove signatures older than 30 sessions that weren't saved or declined)
- Maximum 20 saved workflows — at limit, suggest archiving least-used
