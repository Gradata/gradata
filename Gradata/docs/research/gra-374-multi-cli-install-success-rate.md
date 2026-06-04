# GRA-374: multi_cli_install_success_rate experiment

Status: evaluated — DISCARD
Window: 2026-05-12 to 2026-05-19
Primary owner: gradata-eng
Related issues: GRA-374, GRA-55, GRA-1161, GRA-1163

## Objective

Define and evaluate one quick 7-day experiment for Gradata's multi-agent installer:
can the installer reach a useful cross-CLI success rate after adding bidirectional
hook capture for Codex, Hermes, and OpenCode?

## One measure

`multi_cli_install_success_rate`

Definition:

- Numerator: CLI targets whose install plus correction-capture smoke test passes.
- Denominator: CLI targets tested.
- Target set: Claude Code, Codex, Cursor, Hermes, OpenCode.
- Success threshold: at least 4 of 5 CLIs pass, i.e. >=80%.

Formula:

```text
multi_cli_install_success_rate = passing_cli_targets / tested_cli_targets
```

## Baseline

Before GRA-55, only Claude Code had confirmed bidirectional support.

| CLI | Baseline install/capture state |
| --- | --- |
| Claude Code | PASS |
| Codex | FAIL — capture broken |
| Cursor | FAIL conservative — unverified |
| Hermes | FAIL — capture broken |
| OpenCode | FAIL — capture broken |

Baseline: 1/5 = 20%.

## Measurement runbook

For each target CLI:

```bash
gradata install --agent <cli>
# Record exit code.

# Make one test correction in that CLI.

gradata list-corrections --last 1h --format json
# PASS if at least one fresh correction from that CLI appears.
```

Decision rule:

| Result | Decision |
| --- | --- |
| >=4/5 pass | KEEP — continue multi-CLI installer investment |
| 2-3/5 pass | PARTIAL — file per-CLI debug issues |
| <2/5 pass | DISCARD — re-scope before more onboarding investment |

## Evaluation result

Verdict: DISCARD.

Reason: the prerequisite implementation, GRA-55, was not actually merged. Code audit
showed Codex, Hermes, and OpenCode still had injection-only hook registration and no
post-tool/session-end capture path. Cursor remained unverified, so the conservative
cross-CLI result stayed at the baseline.

| CLI | Injection | Capture | Evaluation status |
| --- | --- | --- | --- |
| Claude Code | yes | yes | PASS |
| Codex | yes | no | FAIL |
| Cursor | yes, via MCP | unverified | FAIL conservative |
| Hermes | yes | no | FAIL |
| OpenCode | yes | no | FAIL |

Final result: 1/5 = 20%.

## Follow-up

The hypothesis was not disproven; the prerequisite implementation did not ship.
Follow-up issue GRA-1163 was filed to re-implement post_tool and session_end hooks
for Codex, Hermes, and OpenCode with an explicit verification gate before completion.

## Paperclip artifact note

This document exists because the original GRA-374 completion was reverted by the
artifact monitor: it had a useful in-thread experiment spec but no durable merged
artifact URL. This file is the durable artifact for the experiment spec and evaluation.
