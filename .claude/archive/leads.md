# Lead Lists

Master status file: Leads/STATUS.md

## Folder Structure
```
Leads/
├── STATUS.md              <- index of all campaigns + stage
├── done/                  <- completed campaigns
│   ├── adsgpt-post/
│   ├── claude-setup-post/
│   └── 80-marketer-post/
├── wip/                   <- active campaigns
│   └── claude-code-80hrs-2026-03-16/
├── enriched/              <- Prospeo/ZeroBounce output files
└── (raw/ and filtered/ removed — were stale duplicates of wip/)
```

## Active Sweep
Script: linkedin-sweep-nomatch.py
Input: Leads/wip/claude-code-80hrs-2026-03-16/claude-code-80hrs-NO-MATCH.csv
Output: Leads/wip/claude-code-80hrs-2026-03-16/claude-code-80hrs-NO-MATCH-SWEPT.csv
Run daily: `python linkedin-sweep-nomatch.py` (200/day, ~2.5 hrs)
