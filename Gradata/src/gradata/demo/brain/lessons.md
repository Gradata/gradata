[2026-01-05] [RULE:0.95] DRAFTING: Never use em dashes in email prose — use colons, commas, or rewrite
  Root cause: User corrected em dashes 8 times across sessions
  Fire count: 14 | Sessions since fire: 1 | Misfires: 0

[2026-01-08] [RULE:0.93] TONE: Write in a direct, concise tone — avoid filler words and hedging
  Root cause: User consistently removed "I think", "perhaps", "maybe" from drafts
  Fire count: 11 | Sessions since fire: 0 | Misfires: 1

[2026-01-10] [RULE:0.91] CODE: Always validate input at system boundaries — never trust external data
  Root cause: User added input validation to 6 functions that lacked it
  Fire count: 9 | Sessions since fire: 2 | Misfires: 0

[2026-01-12] [RULE:0.92] PROCESS: Plan before implementing — outline approach before writing code
  Root cause: User rejected 4 implementations that started without a plan
  Fire count: 8 | Sessions since fire: 1 | Misfires: 0

[2026-01-14] [RULE:0.90] ACCURACY: Verify data before including it in output — never assume correctness
  Root cause: User caught 5 instances of unverified statistics in reports
  Fire count: 7 | Sessions since fire: 3 | Misfires: 1

[2026-01-18] [PATTERN:0.78] DRAFTING: Use bullet points for lists of 3+ items — avoid inline enumeration
  Root cause: User reformatted inline lists to bullets in 4 emails
  Fire count: 6 | Sessions since fire: 2 | Misfires: 0

[2026-01-20] [PATTERN:0.75] CODE: Use early returns to reduce nesting — avoid deep if/else chains
  Root cause: User refactored nested conditionals to guard clauses
  Fire count: 5 | Sessions since fire: 1 | Misfires: 0

[2026-01-22] [PATTERN:0.72] TONE: Match formality to the audience — casual for team, formal for clients
  Root cause: User adjusted tone in 3 emails based on recipient
  Fire count: 4 | Sessions since fire: 3 | Misfires: 1

[2026-01-25] [PATTERN:0.68] ACCURACY: Include source links when citing data or statistics
  Root cause: User added citations to 3 reports that lacked them
  Fire count: 4 | Sessions since fire: 2 | Misfires: 0

[2026-01-28] [PATTERN:0.65] PROCESS: Check existing code before creating new files — avoid duplication
  Root cause: User found existing utility that made new file unnecessary
  Fire count: 3 | Sessions since fire: 4 | Misfires: 0

[2026-02-01] [PATTERN:0.71] DRAFTING: Lead with the key takeaway — don't bury the lede
  Root cause: User moved conclusions to the top of 3 documents
  Fire count: 5 | Sessions since fire: 1 | Misfires: 0

[2026-02-03] [PATTERN:0.63] CODE: Prefer explicit error messages over generic ones
  Root cause: User rewrote ValueError messages to include context
  Fire count: 3 | Sessions since fire: 5 | Misfires: 0

[2026-02-05] [PATTERN:0.67] TONE: Avoid exclamation marks in professional communication
  Root cause: User removed exclamation marks from 4 client emails
  Fire count: 4 | Sessions since fire: 2 | Misfires: 0

[2026-02-08] [PATTERN:0.62] PROCESS: Run tests after every code change — never assume passing
  Root cause: User caught 2 regressions by running tests
  Fire count: 3 | Sessions since fire: 3 | Misfires: 0

[2026-02-10] [PATTERN:0.64] ACCURACY: Double-check date calculations and timezone handling
  Root cause: User fixed 2 off-by-one date errors in reports
  Fire count: 3 | Sessions since fire: 4 | Misfires: 1

[2026-02-15] [INSTINCT:0.52] DRAFTING: Use active voice over passive voice in all writing
  Root cause: User rewrote passive constructions in 2 documents
  Fire count: 2 | Sessions since fire: 5 | Misfires: 0

[2026-02-17] [INSTINCT:0.48] CODE: Keep functions under 30 lines — extract helpers when they grow
  Root cause: User split a 60-line function into 3 helpers
  Fire count: 2 | Sessions since fire: 3 | Misfires: 0

[2026-02-19] [INSTINCT:0.45] TONE: Use "we" instead of "I" in company communications
  Root cause: User changed pronouns in 1 announcement
  Fire count: 1 | Sessions since fire: 6 | Misfires: 0

[2026-02-22] [INSTINCT:0.50] ACCURACY: Round percentages to whole numbers unless precision matters
  Root cause: User simplified "43.7%" to "44%" in a summary
  Fire count: 2 | Sessions since fire: 4 | Misfires: 0

[2026-02-25] [INSTINCT:0.44] PROCESS: Add TODO comments for known limitations instead of ignoring them
  Root cause: User added TODO markers to 2 workarounds
  Fire count: 1 | Sessions since fire: 7 | Misfires: 0

[2026-03-01] [INSTINCT:0.55] DRAFTING: Keep email subject lines under 50 characters
  Root cause: User shortened 2 subject lines that were too long
  Fire count: 2 | Sessions since fire: 2 | Misfires: 0

[2026-03-03] [INSTINCT:0.42] CODE: Use pathlib over os.path for file operations
  Root cause: User refactored os.path calls to pathlib in 1 module
  Fire count: 1 | Sessions since fire: 8 | Misfires: 0

[2026-03-05] [INSTINCT:0.47] TONE: Avoid jargon when writing for non-technical audiences
  Root cause: User simplified technical terms in a client proposal
  Fire count: 1 | Sessions since fire: 5 | Misfires: 0

[2026-03-08] [INSTINCT:0.53] ACCURACY: Cross-reference numbers between sections of the same document
  Root cause: User found contradicting figures in a financial summary
  Fire count: 2 | Sessions since fire: 3 | Misfires: 0

[2026-03-10] [INSTINCT:0.40] PROCESS: Document decisions in commit messages, not just what changed
  Root cause: User rewrote a commit message to explain the reasoning
  Fire count: 1 | Sessions since fire: 9 | Misfires: 0

[2026-03-12] [INSTINCT:0.51] DRAFTING: Use numbered lists for sequential steps, bullets for unordered items
  Root cause: User changed bullets to numbers in a setup guide
  Fire count: 2 | Sessions since fire: 2 | Misfires: 0

[2026-03-15] [INSTINCT:0.43] CODE: Prefer named constants over magic numbers
  Root cause: User extracted a threshold value to a named constant
  Fire count: 1 | Sessions since fire: 6 | Misfires: 0

[2026-03-18] [INSTINCT:0.46] TONE: Start emails with context, not a question
  Root cause: User restructured an email that opened with "Can you...?"
  Fire count: 1 | Sessions since fire: 4 | Misfires: 0

[2026-03-20] [INSTINCT:0.49] ACCURACY: Spell out acronyms on first use in any document
  Root cause: User added full form for "SDK" in an onboarding doc
  Fire count: 2 | Sessions since fire: 3 | Misfires: 0

[2026-03-22] [INSTINCT:0.41] PROCESS: Review diff before committing — catch unintended changes
  Root cause: User caught an accidental debug print in a diff review
  Fire count: 1 | Sessions since fire: 7 | Misfires: 0

