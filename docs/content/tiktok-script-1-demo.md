# TikTok Script 1 — Live Demo (60s)

**Working title:** "Watch Claude learn from my corrections in real-time"
**Format:** @agentic.james style. Fast cuts, screen recording over face cam, text overlays every 2-3 seconds.
**Music:** Low-energy lo-fi under voiceover, beat drop at the payoff (35s).

---

## 0:00 – 0:05 — HOOK

**VOICEOVER:**
"Watch my AI get smarter every time I correct it. No fine-tuning. No RAG. Just corrections."

**ON SCREEN:**
- Face cam, hard zoom.
- Text overlay: **"AI that actually learns YOUR style"**
- Cut to terminal showing Claude output being edited.

---

## 0:05 – 0:15 — PROBLEM SETUP

**VOICEOVER:**
"If you use Claude, ChatGPT, Gemini, whatever. You've done this. You correct the same thing Monday. Correct it again Tuesday. Correct it again Wednesday. The model forgets every session."

**ON SCREEN:**
- Split-screen: three chat windows, dated Mon / Tues / Wed.
- Each shows the same correction: striking through an em dash, replacing with a colon.
- Text overlay pops: **"HubSpot 2024: 75% of marketers spend 30+ min editing AI output"**
- Text overlay: **"Writer.com: 25% of your saved time goes back into corrections"**

---

## 0:15 – 0:35 — GRADATA IN ACTION

**VOICEOVER:**
"This is Gradata. Every time I correct Claude, it logs an event. Severity, category, the exact diff. Hits a threshold, it graduates. INSTINCT, to PATTERN, to RULE."

**ON SCREEN (0:15-0:22):**
- Terminal: `tail -f brain/events.jsonl`
- Three correction events stream in. Highlight severity field.
- Text overlay: **"events.jsonl — every correction logged"**

**VOICEOVER:**
"Three fires, it climbs to PATTERN. Five confirmations, it hits RULE. Now it gets injected into every future session automatically."

**ON SCREEN (0:22-0:30):**
- Animated diagram of graduation pipeline.
- INSTINCT (0.40) → PATTERN (0.60) → RULE (0.90).
- Fire counter incrementing.
- Text overlay: **"Graduation pipeline — 0 of 200 AI experts proposed this"**

**ON SCREEN (0:30-0:35):**
- Show brain/system.db row with new rule.
- XML `<brain-rules>` block injected into session prompt.
- Text overlay: **"65% fewer tokens than naive injection"**

---

## 0:35 – 0:50 — THE PAYOFF

**VOICEOVER:**
"Here's the same prompt, three days later. Different session. I never corrected it again. Watch."

**ON SCREEN:**
- Fresh Claude session.
- Prompt: "Write me a 3-sentence intro for my launch post."
- Output appears. Zoom on the punctuation. No em dashes. Colons where em dashes used to be.
- Text overlay: **"Rule fired. No correction needed."**
- Beat drop.
- Split to side-by-side: Day 1 output (red strikethroughs everywhere) vs Day 7 output (clean).
- Text overlay: **"Synthetic test: 100% correction drop by session 5"**

---

## 0:50 – 1:00 — CTA

**VOICEOVER:**
"Open source SDK is live. Link in bio. Comment GRADATA for early access to the cloud tier with brain sharing."

**ON SCREEN:**
- GitHub repo page: github.com/Gradata/gradata
- Star count visible.
- Text overlay: **"github.com/Gradata/gradata"**
- Final frame: Gradata logo + **"Comment GRADATA for cloud early access"**

---

## Caption

Your AI forgets every session. Gradata fixes that. Open source, works with Claude Code today. Link in bio.

#AI #ClaudeCode #AIcoding #devtools #opensource #LLM

---

## Production notes

- Screen recordings at 1920x1080, crop to 9:16 after.
- Keep face cam bottom-right, 25% width.
- Text overlays: San Francisco Bold, white with black stroke.
- All metrics shown must carry the on-screen qualifier "synthetic" or "benchmark" — never "real users".
- Pin the top comment: "SDK is AGPL-3.0. Cloud tier is paid. What do you want me to build into the brain next?"
