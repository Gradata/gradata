---
title: GRA-374 multi_cli_install_success_rate experiment
date: 2026-05-19
issue: GRA-374
metric: multi_cli_install_success_rate
status: discarded
verdict: DISCARD
---

# GRA-374: multi_cli_install_success_rate experiment

This records the launched 7-day experiment and final evaluation for Paperclip issue GRA-374.

## Experiment question

Does implementing the shared bash-hooks connector for Codex, Hermes, and OpenCode raise multi-CLI install success from 20% to at least 80%?

## Metric

`multi_cli_install_success_rate` = target CLIs where `gradata install --agent <cli>` results in both:

1. rule injection working, and
2. correction capture working end-to-end.

Target CLI set: Claude Code, Codex, Cursor, Hermes, OpenCode.

## Baseline

| CLI | Rule injection | Correction capture | Status |
|---|---|---|---|
| Claude Code | yes | yes | PASS |
| Codex | yes (`pre_tool`) | no | FAIL |
| Cursor | yes (MCP) | unverified | FAIL, conservative |
| Hermes | yes (`pre_tool_use`) | no | FAIL |
| OpenCode | yes (`preTool`) | no | FAIL |

Baseline: 1/5 = 20%.

## Run window

| Field | Value |
|---|---|
| Window start | 2026-05-12 |
| Window end | 2026-05-19 |
| Intervention dependency | GRA-55 |
| Evaluation issue | GRA-1161 |
| Follow-up implementation issue | GRA-1163 |

## Decision rule

| Outcome | Action |
|---|---|
| At least 4/5 CLIs pass | KEEP: graduate the experiment |
| 2-3/5 CLIs pass | PARTIAL: file per-CLI debug issues |
| Fewer than 2/5 CLIs pass | DISCARD: re-scope or re-implement |

## Evaluation result

Code audit on 2026-05-19 found that the intervention had not shipped. GRA-55 had been marked done, but the expected adapter changes were absent.

Observed adapter state:

| Adapter | Expected for success | Observed | Result |
|---|---|---|---|
| Codex | `post_tool` + `session_end` capture hooks | `pre_tool` only | FAIL |
| Hermes | `post_tool_call` + session-end capture hooks | `pre_tool_call` only | FAIL |
| OpenCode | `postTool` + `sessionEnd` capture hooks | `preTool` only | FAIL |

Final metric: 1/5 = 20%, unchanged from baseline.

Verdict: DISCARD.

The hypothesis remains untested because the intervention was not deployed. This is an execution failure, not evidence against the mechanism.

## Follow-up

GRA-1163 was opened to re-implement the missing post-tool and session-end capture hooks with a verification gate requiring adapter diffs before close.

## Paperclip references

- GRA-374: launch one-measure experiment on `multi_cli_install_success_rate`
- GRA-55: original adapter work, false-positive close
- GRA-1161: evaluation issue
- GRA-1163: re-implementation issue
