---
name: cold-email-manifesto
description: >
  Cold email conversion methodology from The Cold Email Manifesto by Alex Berman and Robert Indries.
  Use this skill whenever Oliver needs help writing cold emails, improving open or reply rates, crafting
  subject lines, structuring email offers, or scaling cold email campaigns without killing deliverability.
  Also trigger when he says "my cold emails aren't working," "how do I write better subject lines,"
  "what's a good cold email offer," "how do I scale outreach," "my reply rate is low," "write me a cold
  email for [prospect]," "CCQ format," "help me with email copy," "what should my breakup email say,"
  or any discussion about cold email structure, A/B testing email copy, or Instantly campaign creation.
  This skill focuses specifically on cold email craft — for full multi-channel cadences, see outbound-playbook.
  For warm/lifecycle emails, see email-sequence.
metadata:
  version: 2.0.0
  source: "The Cold Email Manifesto by Alex Berman & Robert Indries"
---

# Cold Email Manifesto

The goal of a cold email is one thing: get a reply. Not a sale, not a demo booking, not even a click. A reply. Everything in the email exists to make replying feel easy and natural.

## The Offer Is Everything

Your offer is not your product. Your offer is the specific outcome you're promising. The reason this distinction matters: nobody wakes up wanting to buy an "AI marketing platform." But they do wake up wanting to stop paying $5K/month in agency retainers while getting mediocre results.

**The Offer Formula: [Specific result] + [Specific proof] + [Timeframe if possible]**

For Sprites:
- "5.8x ROAS in month one, zero agency retainers" (paid ads angle)
- "214% organic traffic growth in 90 days" (SEO angle)
- "One platform replacing 3 agencies across 8 brands" (multi-brand angle)

**Test:** If you removed Sprites' name and replaced it with a competitor's, would the email still work? If yes, the offer isn't specific enough.

## The CCQ Framework

The simplest, highest-converting cold email structure. See [references/email-templates.md](references/email-templates.md) for full templates with Sprites-specific examples.

### 1. Compliment (Personalized opener)
One specific, genuine observation. Not "I love your website." Something that shows you actually looked.

Good: "Saw you're running paid across 5 brands with a team of 3 — that's a heavy lift."
Good: "Your comment on [post] about [topic] caught my eye."
Bad: "I came across your profile and was impressed."

### 2. Case Study (One sentence proof)
One result. One company. One number.

"We just helped H.M. Cole — 8-brand menswear rollup — go from agency retainers to 5.8x ROAS with AI automation."

### 3. Question (Low-friction CTA)
A simple yes/no question. Not a meeting request in email 1. Not a link. A question.

"Worth exploring?" / "Is this on your radar?" / "Curious?"

## Subject Lines

**Rules:** 1-4 words, lowercase, no punctuation tricks, no emojis. Should look like an internal email from a colleague, not a sales pitch.

**Patterns that work:**
- `[company] ads` / `[company] seo`
- `quick question`
- `ad automation` / `agency costs`

**Never use:** "Exciting opportunity," "Can I get 15 minutes?", "[First Name], let's connect"

## Deliverability

The best email in the world is useless if it lands in spam. See [references/deliverability.md](references/deliverability.md) for the full technical guide.

**Key rules:**
- No HTML, images, or tracking pixels — plain text only
- No links in email 1 — save for email 2+
- Under 150 words
- Bounce rate under 3% (verify every email before sending)
- Volume under 50/day per sending account
- Use separate domains for cold outreach — never risk the primary domain

## Follow-Up Cadence

- Email 1 (Day 1): Cold intro via CCQ
- Email 2 (Day 3): Different angle, lead with case study
- Email 3 (Day 7): Value-add (stat, insight, or trend)
- Email 4 (Day 10): Breakup

Each email stands alone and introduces a NEW angle. "Just following up" is never acceptable.

**Angle rotation for Sprites:**
1. Execution gap (AI insights vs. AI execution)
2. Case study (H.M. Cole ROAS or Iris Finance SEO)
3. GEO / AI search visibility
4. Breakup — soft close, door stays open

## Metrics

| Metric | Good | Great |
|--------|------|-------|
| Open rate | 50%+ | 70%+ |
| Reply rate | 5%+ | 10%+ |
| Positive reply rate | 2%+ | 5%+ |
| Meeting book rate (from positive replies) | 50%+ | 70%+ |

**Diagnosing:** Low opens = subject lines. High opens, low replies = body copy/CTA. High replies, low meetings = reply handling.

## How to Apply This Skill

When Oliver asks for cold email help:
1. Ask who the audience is and what angle fits (multi-brand, solo consultant, agency, SEO)
2. Draft using CCQ structure with Sprites-specific offer
3. Follow the writing rules from CLAUDE.md (no em dashes, no fluff, "Hi [First Name]," opener, signature block, hyperlinked CTA)
4. Keep under 150 words, each sentence on its own line
5. If writing a sequence, rotate angles across the 4 emails
