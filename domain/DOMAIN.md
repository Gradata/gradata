# Sprites.ai Sales Domain Configuration

> Domain-specific rules for Sprites.ai sales operations.
> Loaded by AIOS at startup via CLAUDE.md domain loading section.
> Generic OS infrastructure lives in CLAUDE.md and .claude/ — this file contains only Sprites-specific context.

## Oliver's Role
AE at Sprites.ai. Full cycle: prospecting, cold calls, demos, closing. Not a BDR.

## Prospect Loading (two tiers)
Source of truth for pipeline: domain/pipeline/startup-brief.md.
- **Tier 1 (auto-load):** Prospects with a meeting, demo, or follow-up due within 48 hours. Read their full brain/prospects/ file at startup. No ask, no delay.
- **Tier 2 (on-demand):** Everyone else. Do NOT load at startup. When Oliver names a prospect or company mid-session, load their full brain file immediately.
Do not read all prospect files at startup. Only Tier 1 prospects get loaded.

## Prospect Research Order (FREE FIRST — always)
0. **Pipedrive** — source of truth. 0.5. **Vault** — brain/ notes. Free, instant.
1. **Free web** — WebSearch, LinkedIn browser, company site. 2. **NotebookLM** — persona patterns (see .claude/skills/notebooklm/SKILL.md for tier system).
3. **Apollo MCP** (costs credits — ask first). 4. **Apollo browser**. 5. **Clay** (if needed). 6. **Fireflies** — search by attendee email + name + company. All team members (oliver@, anna@, siamak@spritesai.com).
**Cost rule:** Exhaust steps 0-2 before any paid tool. State cost + ask permission. Full hierarchy: .claude/fallback-chains.md.

## Mandatory Gates (full checklists: domain/gates/)
Every gate: research → checkpoint → Oliver approval → output. No exceptions.
- **Pre-Draft** — domain/gates/pre-draft.md
- **Demo Prep** — domain/gates/demo-prep.md
- **Post-Demo Follow-Up** — domain/gates/post-demo.md
- **Cold Call Script** — domain/gates/cold-call.md
- **LinkedIn Message** — domain/gates/linkedin.md
- **Pipedrive Notes** — domain/gates/pipedrive-note.md
- **Win/Loss Analysis** — domain/gates/win-loss.md
- **Lead Filtering** — domain/pipeline/lead-filtering-sop.md
- **Calendar Check** — 2 months out before any task/next step.

## Voice, Writing & Email Frameworks
See domain/soul.md for Sprites-specific email frameworks, persona boundaries, and signature.
See soul.md (root) for generic writing quality standards.
* **Thread matching.** When replying to a prospect, search Gmail for Oliver's MOST RECENT sent email to that person (`to:[email] from:oliver@spritesai.com`). Use THAT threadId. Never grab a threadId from an older or different conversation. Verify the subject line matches before creating the draft.

## Pipedrive Auto-Sync (do without asking)
* Demo booked → create/update deal, pre-demo note, Demo Scheduled
* Demo completed (Fireflies) → transcript, notes, Proposal Made
* Follow-up drafted → log email activity
* Cold call → sync notes with date
* "Add [name]" → Apollo, create deal + contact + note
* "Update [company]" → Fireflies, Apollo, Gmail, refresh
* Activities: subject, type, deal_id, person_id, org_id, due_date, done, note. Always schedule next.
* Credits: batch reads then writes, RUBE_MULTI_EXECUTE, Oliver-tagged only.

## Weekly Review (Mondays)
Template: domain/pipeline/weekly-pulse-template.md. Save to brain/pipeline/.

## Tool Stack
Pipedrive (Composio, 1K/mo) | Apollo (MCP+browser) | Gmail | GCal | Calendly | Fireflies | Clay (sparingly) | NotebookLM (8 notebooks) | Apify | Sheets | Prospeo | ZeroBounce | Instantly

## ICP
Multi-brand ecom, PE rollups, franchise, solo consultants, lean DTC, agencies. 10-300 employees. Meta Pixel and/or Google Ads. US primary, UK/CA/AU/NZ/EU secondary.

## Loop (Closed-Loop Sales Intelligence)
Universal learning engine for ALL sales activities — emails, calls, demos, proposals, closes.
Every interaction tagged → outcomes tracked → patterns aggregated → next action smarter.
- CARL: domain/carl/loop (ALWAYS_ON, 60 rules) | Patterns: brain/emails/PATTERNS.md | Audit: .claude/loop-audit.md | Prospect template: brain/prospects/_TEMPLATE.md
- Two tiers: COLD (Instantly bulk, read-only) and PIPELINE (Claude-written personalized via Gmail). **No auto-sequences for CRM leads.** Instantly is for cold strangers only.
- Call scoring: after every Fireflies transcript, score talk ratio, questions asked, next steps clarity, objection handling.
- Pre-action: always read PATTERNS.md. Never repeat a failed angle. 70/30 proven/experimental.
- Post-action: log tags to prospect note, set next_touch, update Pipedrive. Wrap-up: recalculate PATTERNS.md tables.
- Confidence: <3=[INSUFFICIENT], 3-9=[HYPOTHESIS], 10-25=[EMERGING], 25-50=[PROVEN], 50-100=[HIGH CONFIDENCE], 100+=[DEFINITIVE].

## Enterprise Capabilities
- **Predictive Pipeline** — Deal health scores (0-100) + close probability (brain/forecasting.md). **Signal Monitoring** — brain/signals.md.
- **On-Demand Pipeline Scan** — Gmail/Fireflies/Pipedrive/Instantly at every startup, cached in brain/morning-brief.md.
- **Self-Evolving Playbooks** — Frameworks auto-promote to DEFAULT at 40%+ conversion. Dead frameworks archived after 20 sessions unused.

## Signature & Reference Files
Signature: see domain/soul.md. Reference files (load on demand, Tier 2): domain/pipeline/startup-brief.md | domain/sprites_context.md | "domain/playbooks/sales-methodology.txt" | "domain/templates/templates.txt" | "domain/playbooks/prospecting-instructions.txt" | "domain/playbooks/my-role.txt" | .claude/lessons.md | "domain/prep/Demo Threads.txt"

## Domain File Pointers
- Product/ICP/case studies: domain/sprites_context.md
- Sales frameworks: domain/playbooks/sales-methodology.txt
- Email templates: domain/templates/templates.txt
- Prospecting playbook: domain/playbooks/prospecting-instructions.txt
- Oliver's role + banned words: domain/playbooks/my-role.txt
- Demo thread URLs: domain/prep/Demo Threads.txt
- Lead campaign index: domain/leads/STATUS.md
- NotebookLM registry: domain/notebooks/registry.md
- Obsidian brain: C:/Users/olive/SpritesWork/
- CARL domains: domain/carl/
