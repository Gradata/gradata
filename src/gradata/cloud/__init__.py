"""
Gradata Cloud — Server-side graduation, meta-learning, and marketplace.
=========================================================================
Layer 2 Cloud: connects local brains to Gradata's hosted intelligence.

Local mode (free, open source):
  - Store/retrieve memories (SQLite + FTS5)
  - Log corrections and events
  - Basic search
  - Base patterns (15 agentic patterns)

Cloud mode (Gradata platform):
  - INSTINCT->PATTERN->RULE graduation engine
  - Correction density analysis + maturity phases
  - Quality scoring (5-dimension validator)
  - Compound growth calculation + Brain Report Card
  - Meta-learning across all brains on platform
  - Marketplace routing + trust scoring
  - Adaptive retrieval optimization

Usage:
    from gradata import Brain

    brain = Brain("./my-brain")
    brain.connect_cloud(api_key="pk_...")  # or set GRADATA_API_KEY env var

    # Now correct() and apply_brain_rules() route to cloud
    brain.correct(draft, final)  # graduation runs server-side
"""

from gradata.cloud.client import CloudClient

__all__ = ["CloudClient"]
