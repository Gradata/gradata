# Agent Onboarding Wizard

> Run this on first setup. Answer these questions and the system generates your initial config.
> After setup, delete this file — your config lives in CLAUDE.md, .carl/, and .claude/

## Step 1: Who Are You?

**Role:** [sales / marketing / recruiting / ops / finance / engineering / consulting / other]
**Title:** [e.g., Account Executive, Marketing Manager, Recruiter]
**Company:** [company name]
**Team size:** [just me / 2-5 / 6-20 / 20+]
**What does a good day look like?** [free text — helps calibrate priorities and energy]

## Step 2: Your Tools

Check all that apply:
- [ ] CRM (which? Pipedrive / Salesforce / HubSpot / other)
- [ ] Email (Gmail / Outlook / other)
- [ ] Calendar (Google / Outlook / Calendly / other)
- [ ] Call recording (Fireflies / Gong / Chorus / other)
- [ ] Lead enrichment (Apollo / ZoomInfo / Clay / other)
- [ ] Marketing automation (Instantly / Mailchimp / HubSpot / other)
- [ ] Project management (Linear / Jira / Asana / other)
- [ ] Communication (Slack / Teams / other)
- [ ] Analytics (Google Analytics / Mixpanel / other)
- [ ] Other: ___

## Step 3: Your Communication Style

**Writing tone:** [direct / warm / formal / casual / consultative]
**Typical message length:** [short (1-3 sentences) / medium (4-8 sentences) / detailed (9+ sentences)]
**Banned words or phrases:** [list any words you never want in outputs]
**Signature:** [paste your email signature]
**Opening style:** [e.g., "Hi [First Name]," / "Hey [First Name]," / "[First Name],"]

## Step 4: Your Top 5 Recurring Tasks

List the tasks you do most often (the agent will build gates and workflows for these):
1. ___
2. ___
3. ___
4. ___
5. ___

## Step 5: Quality Standards

**How do you handle mistakes?** [I want to know immediately / batch corrections at end of day / only flag critical errors]
**Approval workflow:** [approve everything before it goes out / approve drafts only / trust the agent for routine tasks]
**Cost sensitivity:** [always ask before spending / ask above $X / trust the agent's judgment]

## Step 6: Domain-Specific (Auto-Generated Based on Role)

### If Sales:
- **ICP:** [describe your ideal customer — industry, size, geography, tech stack]
- **Sales methodology:** [SPIN / Gap Selling / Challenger / MEDDIC / none / custom]
- **Pipeline stages:** [list your CRM stages]
- **Booking link:** [your scheduling URL]

### If Marketing:
- **Channels:** [SEO / Paid / Social / Email / Content / other]
- **Target audience:** [describe]
- **Brand voice doc:** [link or paste]
- **KPIs:** [what metrics matter most?]

### If Recruiting:
- **Roles typically hiring for:** [engineering / sales / ops / etc.]
- **ATS:** [Greenhouse / Lever / Workday / other]
- **Sourcing channels:** [LinkedIn / Indeed / referrals / other]
- **Hiring process stages:** [list]

### If Ops/Engineering/Other:
- **Primary systems:** [list]
- **Key workflows:** [describe top 3]
- **Compliance requirements:** [any regulatory constraints?]

---

## What Gets Generated

After completing this wizard, the agent generates:

1. **CLAUDE.md** — Master rules file with:
   - FRAMEWORK sections (universal — truth protocol, session startup/wrap-up, self-improvement, quality system)
   - DOMAIN sections (role-specific — your tools, workflows, writing style, ICP/audience)

2. **.carl/global** — Universal rules (truth protocol, verification, uncertainty handling)
3. **.carl/[domain]** — Role-specific rules based on your tasks and tools

4. **.claude/gates.md** — Quality gates for your top 5 tasks:
   - Research gate (what to check before starting)
   - Output gate (what to verify before presenting)
   - Approval gate (what needs your sign-off)

5. **.claude/quality-rubrics.md** — Scoring rubrics calibrated to your standards

6. **brain/loop-state.md** — Initial handoff template

7. **.claude/lessons.md** — Empty lessons file, ready to learn from your corrections

## Setup Checklist

After wizard completion:
- [ ] Review generated CLAUDE.md — edit anything that doesn't feel right
- [ ] Connect your tools (CRM, email, calendar MCP integrations)
- [ ] Run one test task and verify the agent follows your style
- [ ] Give 3 corrections — this seeds the learning loop
- [ ] After 3 sessions, check lessons.md — the system should be noticeably better

## Time to First Value

| Without wizard | With wizard |
|---------------|-------------|
| 5+ sessions to calibrate | 1 session to functional |
| 50+ corrections before it "gets you" | ~10 corrections to fine-tune |
| Manual file creation | Auto-generated config |
| Hope nothing is missing | Checklist ensures coverage |
