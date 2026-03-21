# Correction Patterns — Sales Pack

Regex patterns used by the capture hooks to detect corrections, positive feedback, and guardrail violations in real time. These fire during `UserPromptSubmit` and queue items for `/reflect` to process.

## Explicit Markers (highest priority)

| Pattern | Name | Confidence | Decay |
|---------|------|-----------|-------|
| `remember:` | remember | 0.90 | 120 days |

User can type `remember: [anything]` to force-queue a learning regardless of other signals.

## Positive Feedback

| Pattern | Name | Confidence | Decay |
|---------|------|-----------|-------|
| `perfect!\|exactly right\|that's exactly` | perfect | 0.70 | 90 days |
| `that's what I wanted\|great approach` | great-approach | 0.70 | 90 days |
| `keep doing this\|love it\|excellent\|nailed it` | keep-doing | 0.70 | 90 days |

Positive signals reinforce what's working. Queued with sentiment: "positive".

## Correction Openers (auto-detected)

| Pattern | Name | Strong? | Notes |
|---------|------|---------|-------|
| `^no[,. ]+` | no, | Yes | Starts with "no," — common correction opener |
| `^don't\b\|^do not\b` | don't | Yes | Starts with don't/do not |
| `^stop\b\|^never\b` | stop/never | Yes | Starts with stop/never |
| `that's (wrong\|incorrect)` | that's-wrong | Yes | Explicit wrongness |
| `^actually[,. ]` | actually | No | Weak — could be informational |
| `^I meant\b\|^I said\b` | I-meant/said | Yes | Clarification |
| `^I told you\b\|^I already told\b` | I-told-you | Yes | Repeated instruction |
| `use .{1,30} not\b` | use-X-not-Y | Yes | "use X not Y" substitution |

Strong patterns get 0.80 confidence. Weak patterns get 0.60 and require message length < 150 chars.

## Guardrail Violations (scope/permission corrections)

| Pattern | Name | Confidence | Decay |
|---------|------|-----------|-------|
| `don't (add\|include\|create\|send\|change\|do) .{1,40} unless` | dont-unless-asked | 0.90 | 120 days |
| `only (change\|modify\|edit\|touch\|do\|handle) what I (asked\|requested\|said\|told)` | only-what-asked | 0.90 | 120 days |
| `stop (changing\|modifying\|doing\|adding\|removing) (unrelated\|other\|extra)` | stop-unrelated | 0.90 | 120 days |
| `don't (over-complicate\|add extra\|be too\|make unnecessary\|go beyond)` | dont-overcomplicate | 0.85 | 90 days |
| `don't (change\|redo\|undo\|rework) (unless\|without)` | dont-change-unless | 0.85 | 90 days |
| `leave .{1,30} (alone\|unchanged\|as is)` | leave-alone | 0.85 | 90 days |
| `don't (assume\|guess\|make up\|fabricate\|hallucinate)` | dont-assume | 0.90 | 120 days |
| `(minimal\|minimum\|only necessary\|just what I asked)` | minimal-changes | 0.80 | 90 days |
| `I already (told\|said\|explained\|mentioned)` | already-told | 0.85 | 120 days |
| `that's not what I (meant\|asked\|said\|wanted)` | not-what-i-meant | 0.85 | 90 days |

## False Positive Filters (language-agnostic)

These structural patterns suppress correction detection:

| Pattern | Reason |
|---------|--------|
| Ends with `?` | Question, not correction |
| Starts with `please\|can you\|could you` | Task request, not correction |
| Contains `help\|fix\|check\|review` + `this\|that\|it` | Task verb, not correction |
| Contains `error\|failed\|cannot\|unable to` | Error description, not correction |
| Starts with `I need\|I want\|I would like` | Task request |
| Starts with `ok\|okay\|alright` + `so\|now\|let` | Task continuation |

## Non-Correction Phrases (false positive suppression)

| Pattern | Why It's Not a Correction |
|---------|--------------------------|
| `no problem` | Agreement |
| `no worries` | Agreement |
| `no need` | Acknowledgment |
| `no way` | Surprise/exclamation |
| `don't worry` | Reassurance |
| `don't mind` | Agreement |
| `don't bother` | Polite decline |
| `never mind` | Dismissal |
| `stop worrying` | Reassurance |

## Length Thresholds

| Threshold | Value | Purpose |
|-----------|-------|---------|
| Max capture prompt | 500 chars | Skip very long prompts (likely system content, not corrections) |
| Max weak pattern | 150 chars | Weak patterns only fire on short messages |
| Short correction | 80 chars | Very short messages without `?` are more likely corrections |

Exception: explicit `remember:` markers are always processed regardless of length.

## Confidence Tiers (for pattern aggregation)

| Sample Size | Label | Action |
|------------|-------|--------|
| <3 | INSUFFICIENT | Don't act on it |
| 3-9 | HYPOTHESIS | Test cautiously |
| 10-25 | EMERGING | Lean into it |
| 25-50 | PROVEN | Default behavior |
| 50-100 | HIGH CONFIDENCE | Core playbook |
| 100+ | DEFINITIVE | Canonical truth |
