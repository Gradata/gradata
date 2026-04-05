"""
Layer 1: Brain Enhancements.

enhancements/ imports from patterns/ but never the reverse.
These wire into base patterns to make brains compound over time.

AVAILABLE modules (open source, shipped in SDK):
  diff_engine          -- Edit distance + 5-level severity
  quality_gates        -- (moved to contrib/enhancements/)
  truth_protocol       -- (moved to contrib/enhancements/)
  self_improvement     -- INSTINCT->PATTERN->RULE graduation
  carl                 -- Behavioral contracts with MUST/SHOULD/MAY tiers
  correction_tracking  -- Density, half-life, MTBF
  brain_scores         -- (moved to contrib/enhancements/)
  edit_classifier      -- 5-category classification
  pattern_extractor    -- Extract patterns from classified edits
  metrics              -- Rolling window quality metrics
  failure_detectors    -- 4 automated regression alerts
  reports              -- Health, CSV, metrics, rule audit
  success_conditions   -- 6-condition validation
  meta_rules           -- Emergent meta-rule discovery (compound procedural memory)
  rule_integrity       -- HMAC signing for tamper detection
  rule_verifier        -- Output verification against rules
  rule_canary          -- Rule regression detection
  rule_conflicts       -- Contradiction detection
  contradiction_detector -- Semantic contradiction detection before graduation
  outcome_feedback     -- (moved to contrib/enhancements/)
  observation_hooks    -- 100% deterministic tool-use capture (from everything-claude-code)
  install_manifest     -- (moved to contrib/enhancements/)
  memory_taxonomy      -- 5-type memory units with Foresight (from EverOS)
  cluster_manager      -- Incremental centroid clustering (from EverOS)
  lesson_discriminator -- Importance scoring before graduation (from EverOS)
  learning_pipeline    -- End-to-end: observe→cluster→discriminate→route→bracket
  eval_benchmark       -- (moved to contrib/enhancements/)
  router_warmstart     -- Bootstrap Q-Learning router from vault data

CLOUD-ONLY modules (require gradata_cloud package):
  agent_graduation     -- Agent/subagent behavioral graduation

PLANNED modules (not yet implemented):
  loop_intelligence    -- Activity tracking, pattern aggregation
  sales_profile        -- Sales behavioral profiling
  tone_profile         -- Tone analysis and adaptation
  call_profile         -- Call performance profiling
  calibration          -- Brier score calibration
  gate_calibration     -- Gate threshold auto-calibration
  memory_extraction    -- Passive memory extraction (Mem0-inspired)
  judgment_decay       -- Confidence decay over time
  contextual_bandit    -- Multi-armed bandit for rule selection
  collaborative_filter -- Cross-brain pattern sharing
  rules_distillation   -- Pattern-to-rule distillation
"""
