---
name: correction_pipeline_classification
description: Keyword ordering in CATEGORY_KEYWORDS is load-bearing — first-match wins. Specific categories before broad ones (e.g. ARCHITECTURE before ACCURACY so "refactor" beats "wrong"). CONTEXT before PROCESS for multi-word context signals.
type: feedback
---

CATEGORY_KEYWORDS dict order is the classifier's priority. Changing order changes classification results.

**Why:** classify_correction() iterates the dict in insertion order and returns on first match. "wrong" in ACCURACY would swallow ARCHITECTURE/LEADS/PRICING corrections if ACCURACY came first.

**How to apply:** When adding new categories or keywords, place more-specific categories before less-specific ones. Run the test suite (19 cases) after any keyword changes.
