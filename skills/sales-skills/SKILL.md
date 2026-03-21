---
name: sales-skills
description: Router for the 9 Salesably sales skills suite — account qualification, call analysis, cold call scripts, company intelligence, follow-up emails, multithread outreach, POWERFUL framework, prospect research, and sales orchestrator. Use this skill when Oliver needs structured sales methodology that goes beyond the core skills (cold-email-manifesto, buyer-psychology, JOLT, fanatical-prospecting). Trigger when Oliver asks about deal qualification, account tiering, call coaching, multithreading into an account, the POWERFUL framework, or when he needs the sales orchestrator to figure out which skill to use. Also trigger on "Salesably", "sales skills", "which sales skill", or "help me work this deal".
---

# Salesably Sales Skills Suite

## Why This Exists
These 9 skills cover structured sales methodology from prospecting through close. They complement the core knowledge skills (buyer-psychology, JOLT, cold-email-manifesto, fanatical-prospecting) with actionable frameworks and templates.

## The 9 Skills

Load only the specific skill relevant to the task — never all 9.

### Foundation Layer
| Skill | When to Use |
|-------|-------------|
| `powerful-framework` | Qualifying deals, assessing opportunity health, coaching on deal strategy |
| `prospect-research` | Building prospect profiles, personalizing outreach, understanding buyers |

### Strategy Layer
| Skill | When to Use |
|-------|-------------|
| `account-qualification` | Tiering accounts, prioritizing efforts, defining ICP fit |
| `company-intelligence` | Deep company research for executive meetings, account planning |

### Execution Layer
| Skill | When to Use |
|-------|-------------|
| `cold-call-scripts` | Phone prospecting, voicemail scripts, gatekeeper navigation |
| `follow-up-emails` | Structured follow-up sequences after meetings or events |
| `multithread-outreach` | Engaging multiple stakeholders at a target account |

### Analysis Layer
| Skill | When to Use |
|-------|-------------|
| `call-analysis` | Reviewing call recordings, scoring performance, identifying coaching areas |
| `sales-orchestrator` | Unsure which skill to use, planning multi-step deal strategy |

## How to Load
Each skill lives at `skills/sales-skills/skills/[skill-name]/SKILL.md`. Read only what you need:

```
Read skills/sales-skills/skills/powerful-framework/SKILL.md
```

## Routing Guide
- "How do I qualify this deal?" → `powerful-framework`
- "Help me multithread into Acme Corp" → `multithread-outreach`
- "Score my last call" → `call-analysis`
- "Write a cold call script" → `cold-call-scripts`
- "Which accounts should I focus on?" → `account-qualification`
- "I don't know what to do next with this deal" → `sales-orchestrator`
