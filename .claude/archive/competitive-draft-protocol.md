# Competitive Drafting Protocol (DeepMind Self-Play)

## When to Use
- Default ON for follow-up emails (where angle choice matters most)
- Default OFF for first touches (Oliver usually specifies the approach)
- Oliver can toggle: "just one" skips it, "give me options" forces it

## How It Works
1. Complete pre-draft research gate as normal
2. Identify 2 viable approaches (different angle, tone, or structure)
3. Draft both versions — full drafts, not outlines
4. Present with 1-line reasoning: "Version A: pain-point angle, direct tone. Version B: case-study angle, consultative tone."
5. Oliver picks one (or says "combine" for hybrid)
6. Log the pick to PATTERNS.md under ## Draft Preferences

## What Gets Tracked
```
PICK: [date] | prospect: [name] | persona: [type] |
      picked: [angle+tone] | rejected: [angle+tone] |
      reason: [Oliver's stated reason or "no reason given"]
```

## How It Compounds
- After 10 picks for same persona: surface preference pattern
- After 20 picks: auto-recommend the winning approach, stop presenting the loser
- After 50 picks total: "Oliver's Draft Style Profile" emerges — defaults per persona
- Track: pick_count, angle_win_rate_by_persona, tone_preference_by_persona

## Integration with Loop
- Picks feed PATTERNS.md (preference data)
- Outcomes feed Loop (which picked version got replies)
- Over time: "Oliver picks direct+pain-point for agencies, AND it converts 40% — double signal"
