# Graph Report - src/gradata  (2026-04-09)

## Corpus Check
- 156 files · ~134,114 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2590 nodes · 5389 edges · 114 communities detected
- Extraction: 60% EXTRACTED · 40% INFERRED · 0% AMBIGUOUS · INFERRED: 2151 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Brain` - 227 edges
2. `Lesson` - 194 edges
3. `LessonState` - 180 edges
4. `BrainContext` - 134 edges
5. `RuleGraph` - 93 edges
6. `EventBus` - 88 edges
7. `LearningPipeline` - 76 edges
8. `BrainInspectionMixin` - 74 edges
9. `ToolRegistry` - 73 edges
10. `MemoryManager` - 72 edges

## Surprising Connections (you probably didn't know these)
- `Rule Inspection API — standalone functions for introspecting brain rules. =====` --uses--> `Lesson`  [INFERRED]
  src\gradata\inspection.py → src\gradata\_types.py
- `Read and parse lessons.md from a file path.` --uses--> `Lesson`  [INFERRED]
  src\gradata\inspection.py → src\gradata\_types.py
- `Convert a Lesson dataclass to a serializable dict with a stable ID.` --uses--> `Lesson`  [INFERRED]
  src\gradata\inspection.py → src\gradata\_types.py
- `List brain rules from lessons.md.      Args:         db_path: Path to system.` --uses--> `Lesson`  [INFERRED]
  src\gradata\inspection.py → src\gradata\_types.py
- `Trace a rule back to its source corrections and transitions.      Args:` --uses--> `Lesson`  [INFERRED]
  src\gradata\inspection.py → src\gradata\_types.py

## Communities

### Community 0 - "Brain Inspection & Patterns"
Cohesion: 0.04
Nodes (233): AdditionTracker, Accumulate addition fingerprints; emit a lesson dict at threshold.      Args:, BrainInspectionMixin, Brain inspection mixin — rule inspection, approval, and export methods.  Extra, Reject a graduated rule — demotes back to INSTINCT with confidence 0.40., Mixin providing rule inspection, export, and batch approval methods.      Must, List graduated brain rules. See gradata.inspection.list_rules., Trace a rule to its source corrections. See gradata.inspection.explain_rule. (+225 more)

### Community 1 - "Brain Core & Adapters"
Cohesion: 0.01
Nodes (158): patch_anthropic(), Anthropic Integration — Patch Anthropic client with brain memory. =============, Patch an Anthropic client to use brain memory.      Args:         client: An, Brain, BrainInspectionMixin, cmd_context(), cmd_convergence(), cmd_correct() (+150 more)

### Community 2 - "Cluster Management"
Cohesion: 0.02
Nodes (100): ClusterAssignment, ClusterConfig, ClusterManager, ClusterState, Cluster Manager — Incremental centroid clustering for corrections. ============, Result of assigning an item to a cluster.      Attributes:         item_id: T, Incremental centroid clustering with temporal gating.      Adapted from EverOS, Assign an item to the best matching cluster.          Mutates state in-place. (+92 more)

### Community 3 - "Agent Modes & Permissions"
Cohesion: 0.02
Nodes (114): AgentMode, auto_select_mode(), check_permission(), format_mode_prompt(), get_current_mode(), get_mode(), ModeConfig, Agent Modes — Gradata ==================================== Switchable operatin (+106 more)

### Community 4 - "Agent Graduation Pipeline"
Cohesion: 0.02
Nodes (114): _infer_agent_type(), main(), PostToolUse hook: emit AGENT_OUTCOME event after Agent tool completes., _infer_agent_type(), main(), PreToolUse hook: inject relevant brain rules into Agent subagent context., _relevance_score(), _build_progress() (+106 more)

### Community 5 - "Memory System"
Cohesion: 0.03
Nodes (48): classify_memory_scope(), EpisodicMemory, get_memory_scope_filter(), InMemoryStore, Memory, MemoryStore, _now_iso(), _parse_iso() (+40 more)

### Community 6 - "Guardrails & Middleware"
Cohesion: 0.06
Nodes (66): Exception, GuardedResult, Aggregated outcome of running input + output guards around an agent call., Middleware, MiddlewareChain, MiddlewareContext, MiddlewareError, Middleware Chain — Composable ordered middleware with anchor positioning. ===== (+58 more)

### Community 7 - "Embeddings & Similarity"
Cohesion: 0.03
Nodes (63): cluster_lessons_by_similarity(), EmbeddingClient, get_client(), _is_trusted_url(), Two-tier embedding integration with event bus subscription.  Provides lightwei, Register embedding handlers. Embeddings are cached for clustering., subscribe_to_bus(), _categories_extinct() (+55 more)

### Community 8 - "Meta-Rules Engine"
Cohesion: 0.06
Nodes (71): _classify_meta_transfer_scope(), _detect_themes(), discover_meta_rules(), _eval_single_condition(), evaluate_conditions(), format_meta_rules_for_prompt(), get_context_weight(), __getattr__() (+63 more)

### Community 9 - "Behavioral Extraction"
Cohesion: 0.06
Nodes (63): Archetype, ArchetypeMatch, _contains_action_verb(), detect_archetype(), extract_instruction(), _extract_topic(), _find_sentence_containing(), generate_instruction() (+55 more)

### Community 10 - "Orchestrator & Routing"
Cohesion: 0.06
Nodes (45): classify_request(), execute_orchestrated(), get_route_rules(), IntentPattern, Orchestrator — Domain-Agnostic Pattern Router =================================, Maps a named intent to its primary pattern and optional secondaries.      Attr, Register or replace an intent-to-pattern mapping.      Domain-specific brains, Full classification of a single incoming request.      Attributes:         qu (+37 more)

### Community 11 - "Events & Analytics"
Cohesion: 0.09
Nodes (36): audit_trend(), compute_leading_indicators(), correction_rate(), _detect_session(), emit(), emit_gate_override(), emit_gate_result(), _ensure_table() (+28 more)

### Community 12 - "Memory Taxonomy"
Cohesion: 0.07
Nodes (25): AtomicFact, BaseMemoryUnit, BrainProfile, classify_memory_type(), CorrectionNarrative, CrossBrainProfile, MemoryType, _merge_fields() (+17 more)

### Community 13 - "Rule Context Bridge"
Cohesion: 0.06
Nodes (22): bootstrap_rule_context(), on_graduation_event(), Rule Context Bridge — Populates RuleContext from graduation events.  This is t, Event trigger: when a lesson graduates to PATTERN or RULE, publish.      Regis, Load all existing graduated rules into RuleContext at session start.      Read, get_rule_context(), GraduatedRule, RuleContext — Central hub for graduated rules consumed by all patterns.  This (+14 more)

### Community 14 - "Safety Guardrails"
Cohesion: 0.08
Nodes (30): _check_banned(), _check_destructive(), check_exec_command(), _check_injection(), _check_pii(), _check_scope(), check_write_path(), Guard (+22 more)

### Community 15 - "Module Group 15"
Cohesion: 0.15
Nodes (8): BaseHTTPRequestHandler, _category_from_path(), _Handler, main(), _pick_port(), _register_signal_handler(), _setup_logging(), _write_pid_file()

### Community 16 - "Module Group 16"
Cohesion: 0.08
Nodes (19): BehavioralContract, ConstraintViolation, may_rules(), must_rules(), PrioritizedConstraint, CARL — Behavioral Contracts per Domain with Priority Tiers. ===================, Return all constraints as PrioritizedConstraint objects.          Legacy strin, Return constraints filtered by priority level. (+11 more)

### Community 17 - "Module Group 17"
Cohesion: 0.11
Nodes (21): compute_blandness(), compute_metrics(), MetricsWindow, Metrics — Rolling window quality metrics from events. =========================, Snapshot of quality metrics over a session window., Compute blandness using inverted Type-Token Ratio (TTR).      TTR = unique_wor, Compute rolling window metrics from events database.      Returns dict with ke, Alert (+13 more)

### Community 18 - "Module Group 18"
Cohesion: 0.09
Nodes (16): classify_all_relations(), _detect_opposite_direction(), detect_rule_conflict(), ExperimentManager, ExperimentResult, _extract_keywords(), from_dict(), Rule Evolution — A/B testing + conflict detection for rule lifecycle. ========= (+8 more)

### Community 19 - "Module Group 19"
Cohesion: 0.1
Nodes (27): _check_brain_dir(), _check_disk_space(), _check_events_jsonl(), _check_manifest(), _check_python_version(), _check_sentence_transformers(), _check_sqlite3(), _check_system_db() (+19 more)

### Community 20 - "Module Group 20"
Cohesion: 0.1
Nodes (23): apply_graduation_scoring(), cascade_retrieve(), CascadeConfig, Chunk, extract_expansion_terms(), NaiveRAG, order_by_relevance_position(), RAG — Retrieval-Augmented Generation with cascade and graduation scoring. ===== (+15 more)

### Community 21 - "Module Group 21"
Cohesion: 0.11
Nodes (27): _canonical_payload(), _ensure_table(), generate_key(), _get_secret_key(), _load_signature(), load_signatures(), HMAC Rule Signing — tamper detection for graduated rules. =====================, Verify rule signature. Returns False if tampered.      Returns True (pass-thro (+19 more)

### Community 22 - "Module Group 22"
Cohesion: 0.1
Nodes (18): BrainBriefing, BriefingRule, _count_active_lessons(), export_briefing(), format_health_report(), generate_briefing(), generate_health_report(), HealthReport (+10 more)

### Community 23 - "Module Group 23"
Cohesion: 0.15
Nodes (24): chunk_markdown(), classify_file(), embed_files(), embed_texts(), embed_texts_gemini(), embed_texts_local(), _ensure_embeddings_table(), extract_session_number() (+16 more)

### Community 24 - "Module Group 24"
Cohesion: 0.12
Nodes (23): _compute_trust_score(), _count_lessons_in_file(), main(), print_report(), Brain Validator — Independent Quality Verification for Marketplace Trust ======, Is this brain genuinely trained or just padded with empty sessions?, Does the brain actually learn? Corrections should decrease over time., Are events well-formed with required fields? (+15 more)

### Community 25 - "Module Group 25"
Cohesion: 0.12
Nodes (21): ApprovalRequest, ApprovalResult, assess_risk(), _extract_affected(), gate(), HumanLoopGate, preview_action(), Human-in-the-Loop Pattern — Risk-Tiered Approval Gates ======================== (+13 more)

### Community 26 - "Module Group 26"
Cohesion: 0.11
Nodes (19): DependencyGraph, merge_results(), ParallelBatch, ParallelResult, ParallelTask, Parallel Execution Pattern — Dependency-Aware Task Dispatch ===================, Invoke *task.handler* with *task.input_data* and capture the result.      Exce, Sort *tasks* into dependency waves using Kahn's algorithm.      Each wave cont (+11 more)

### Community 27 - "Module Group 27"
Cohesion: 0.1
Nodes (18): ActualResult, DeviationDetail, DeviationScore, format_summary(), PlanItem, Reconciliation — Mandatory plan-vs-actual comparison (UNIFY). =================, Full reconciliation output from a UNIFY pass.      Attributes:         plan_i, Performs mandatory plan-vs-actual reconciliation.      The reconciler compares (+10 more)

### Community 28 - "Module Group 28"
Cohesion: 0.1
Nodes (18): criteria_from_graduated_rules(), Criterion, CriterionScore, CritiqueChecklist, CritiqueResult, default_evaluator(), Self-Critique / Reflection Pattern — Generate-Critique-Refine Loop ============, An ordered collection of :class:`Criterion` objects.      Evaluates an arbitra (+10 more)

### Community 29 - "Module Group 29"
Cohesion: 0.11
Nodes (17): evaluate_success_conditions(), GateVerdict, QualityGate, QualityResult, QualityRubric, Quality Gates — 8.0 minimum threshold system with fix cycling. ================, Configurable quality gate with fix-cycle support.      Args:         rubrics:, Run a single evaluation pass and return a verdict.          Args: (+9 more)

### Community 30 - "Module Group 30"
Cohesion: 0.11
Nodes (15): gate(), GateResult, PipelineResult, Sequential Pipeline Pattern ============================ Assembly-line executi, Wrap a bool-returning function so it satisfies the gate protocol.      The dec, A single named step in a :class:`Pipeline`.      Args:         name:        U, Execute the handler, then run the gate check.          The method retries the, Return the first ``_SUMMARY_LIMIT`` characters of ``repr(value)``. (+7 more)

### Community 31 - "Module Group 31"
Cohesion: 0.19
Nodes (19): build_prospect_map(), _CARL_GLOBAL(), _CARL_LOOP(), collect_brain_files(), collect_domain_files(), count_lessons(), _DOMAIN_CONFIG(), _DOMAIN_SOUL() (+11 more)

### Community 32 - "Module Group 32"
Cohesion: 0.12
Nodes (12): ABC, AnthropicProvider, GenericHTTPProvider, get_provider(), LLMProvider, OpenAIProvider, LLM provider abstraction for behavioral extraction.  Supports Anthropic (defau, Get an LLM provider by name.      Args:         name: "anthropic", "openai", (+4 more)

### Community 33 - "Module Group 33"
Cohesion: 0.12
Nodes (17): create_handoff(), Delegation, DelegationResult, load_agent_definition(), orchestrate(), OrchestratedResult, Sub-Agent Orchestrator — structured delegation with typed contracts. ==========, Execute delegations with dependency ordering and synthesis.      Args: (+9 more)

### Community 34 - "Module Group 34"
Cohesion: 0.17
Nodes (17): _attribute_domain_fires(), brain_absorb(), brain_auto_evolve(), brain_convergence(), brain_correct(), brain_detect_implicit_feedback(), brain_efficiency(), brain_end_session() (+9 more)

### Community 35 - "Module Group 35"
Cohesion: 0.12
Nodes (17): budget_summary(), check_budget(), ensure_credit_budgets(), ensure_table(), get_connection(), lessons_lock(), Database Helpers — Shared SQLite utilities for all Gradata modules. ===========, Write to lessons.md with file locking for concurrency safety.      Acquires an (+9 more)

### Community 36 - "Module Group 36"
Cohesion: 0.16
Nodes (17): close_encrypted_db(), decrypt_file(), derive_key(), encrypt_file(), _get_fernet(), load_or_generate_salt(), open_encrypted_db(), Encryption at rest for brain databases.  Optional feature — requires: pip inst (+9 more)

### Community 37 - "Module Group 37"
Cohesion: 0.12
Nodes (12): create_brain_mcp_tools(), MCPBridge, MCPServer, MCPToolSchema, MCP Integration — Model Context Protocol server discovery and routing. ========, Default MCP tool schemas for a brain.      These are the standard operations e, Schema for a tool exposed via MCP.      Maps to the MCP tool definition format, Represents a connected MCP server. (+4 more)

### Community 38 - "Module Group 38"
Cohesion: 0.2
Nodes (17): apply_rules(), beta_domain_reliability(), _beta_ppf_05(), capture_example_from_correction(), classify_transfer_scope(), compute_rule_difficulty(), compute_scope_weight(), detect_task_type() (+9 more)

### Community 39 - "Module Group 39"
Cohesion: 0.27
Nodes (16): build_packet(), _correction_rate(), _detect_session(), _events_query(), format_as_prompt(), _fts_search(), _fuzzy_match_prospect(), _load_audit_context() (+8 more)

### Community 40 - "Module Group 40"
Cohesion: 0.15
Nodes (15): _behavioral_contract(), _correction_rate_trend(), _lesson_distribution(), _outcome_correlation(), _quality_metrics(), _rag_status(), Brain Manifest Metrics. ======================== Lesson/correction metrics and, Correlate compound score trend with user-reported outcome metrics.      Users (+7 more)

### Community 41 - "Module Group 41"
Cohesion: 0.16
Nodes (9): CloudClient, CloudClient — API client for Gradata Cloud. ===================================, Get applicable rules from cloud (server-side graduation state).          Retur, Sync local brain state to cloud.          Uploads new events since last sync., Make an authenticated POST request to the cloud API., Read the local brain.manifest.json if it exists., Client for Gradata Cloud API.      Provides server-side graduation, quality sc, Authenticate and register this brain with the cloud.          Returns True if (+1 more)

### Community 42 - "Module Group 42"
Cohesion: 0.18
Nodes (15): _dict_to_yaml(), explain_rule(), export_rules(), _lesson_to_dict(), list_rules(), _load_lessons_from_path(), Rule Inspection API — standalone functions for introspecting brain rules. =====, Export rules in the specified format.      Args:         db_path: Path to sys (+7 more)

### Community 43 - "Module Group 43"
Cohesion: 0.16
Nodes (15): default_evaluator(), dimensions_from_graduated_rules(), EvalDimension, EvalLoopResult, EvalResult, evaluate(), evaluate_optimize_loop(), Evaluator-Optimizer Pattern ============================ Two independent agent (+7 more)

### Community 44 - "Module Group 44"
Cohesion: 0.17
Nodes (15): auto_detect_verification(), ensure_table(), get_relevant_rules(), get_verification_stats(), log_verification(), Rule verification: pre-execution filtering and post-hoc output checking.  Pre-, Scan rule description for checkable patterns.      Returns list of (compiled_r, Check output against applied rules for verifiable violations.      When *conte (+7 more)

### Community 45 - "Module Group 45"
Cohesion: 0.23
Nodes (13): brain_search(), classify_confidence(), compute_recency_weight(), detect_query_mode(), _ensure_fts_table(), fts_index(), fts_index_batch(), fts_rebuild() (+5 more)

### Community 46 - "Module Group 46"
Cohesion: 0.14
Nodes (10): ExecutionPlan, PlannedStep, Tool Registration — typed tool signatures with plan-before-execute. ===========, Look up a tool by name., Execute a registered tool.          Args:             name: Tool name., Generate a naive execution plan for a task.          This is a simple keyword-, A single step in an execution plan., A plan of tool calls before execution. (+2 more)

### Community 47 - "Module Group 47"
Cohesion: 0.21
Nodes (11): extract_from_file(), _get_db(), _get_entity_names(), get_stats(), _init_tables(), _load_fact_types(), _parse_frontmatter(), query_facts() (+3 more)

### Community 48 - "Module Group 48"
Cohesion: 0.24
Nodes (13): _classify_correction_direction(), compute_learning_velocity(), detect_correction_poisoning(), _detect_machine_context(), format_lessons(), fsrs_bonus(), fsrs_penalty(), graduate() (+5 more)

### Community 49 - "Module Group 49"
Cohesion: 0.21
Nodes (11): CorrectionContext, detect_correction(), extract_correction_context(), _extract_implied_changes(), _is_edited_version(), Passive Correction Detection from Conversation Text. ==========================, Rich context about a detected correction.      Attributes:         is_correct, Extract rich correction context from a user message.      Goes beyond simple d (+3 more)

### Community 50 - "Module Group 50"
Cohesion: 0.21
Nodes (9): _get_entity_names(), _load_taxonomy(), Tag Taxonomy — Configurable vocabulary for brain event tagging. ===============, Build the active taxonomy: core + domain config (or sales defaults).      Prio, Reload taxonomy from brain config. Call after set_brain_dir()., Get valid entity names from brain's entity directory.      In sales: brain/pro, reload_taxonomy(), validate_tag() (+1 more)

### Community 51 - "Module Group 51"
Cohesion: 0.2
Nodes (10): classify_addition(), _classify_python_addition(), _FingerprintCounter, is_addition(), _make_lesson(), Return (category, structural_type) fingerprint for the addition.      *file_ex, Track occurrences of a fingerprint across sessions., Record one occurrence. Returns a lesson dict when threshold met. (+2 more)

### Community 52 - "Module Group 52"
Cohesion: 0.18
Nodes (11): _check_negation(), _check_opposite_sentiment(), _check_polarity(), _extract_topic_words(), _normalize(), Semantic Contradiction Detector — catch rules that fight each other. ==========, Check for action negation (use vs avoid/don't use)., Check for opposite sentiment on overlapping topics. (+3 more)

### Community 53 - "Module Group 53"
Cohesion: 0.4
Nodes (10): _check(), check_embeddings(), check_event_pipes(), check_facts_freshness(), check_fts5(), check_index_completeness(), check_manifest(), Data Flow Audit. ================== Verifies data pipes connect: events, index (+2 more)

### Community 54 - "Module Group 54"
Cohesion: 0.24
Nodes (9): evaluate_rule_candidates(), explore(), Tree of Thoughts — branching exploration for graduation decisions. Evaluates mu, Evaluate multiple wordings for a graduating rule.      When a lesson is about, A single candidate in the exploration tree., Result of Tree of Thoughts exploration., Explore candidate rule wordings using tree search.      Args:         candida, Thought (+1 more)

### Community 55 - "Module Group 55"
Cohesion: 0.24
Nodes (9): query_provenance(), Audit Trail + Provenance — SQLite-backed rule provenance tracking. ============, Scan events.jsonl for events matching the given IDs.      Args:         event, Full trace of a rule: provenance table, events fallback, transitions.      Arg, Insert a provenance row linking a rule to a correction event.      Args:, Query the rule_provenance table.      Args:         db_path: Path to system.d, _scan_events_for_ids(), trace_rule() (+1 more)

### Community 56 - "Module Group 56"
Cohesion: 0.2
Nodes (5): Brain Manifest Helpers. ======================= Shared constants and utility f, Return (max_session, min_session) for a recent window. Shared helper., Enumerate SDK capabilities from adapted modules.      Probes each module for a, _sdk_capabilities(), _session_window()

### Community 57 - "Module Group 57"
Cohesion: 0.27
Nodes (8): Truth Protocol — Evidence-based output validation. ============================, Scan ``output`` for unverifiable claims and banned success phrases.      Check, Result of a single truth-validation rule.      Args:         name: Short iden, Aggregate result from a ``verify_*`` call.      Args:         checks: All ind, Register a check and update aggregate state., TruthCheck, TruthVerdict, verify_claims()

### Community 58 - "Module Group 58"
Cohesion: 0.24
Nodes (7): backfill_from_git(), BackfillStats, Git Backfill — Bootstrap a brain from git history. ============================, Bootstrap a brain from git history.      Scans git diffs and feeds them as cor, Statistics from a git backfill operation., Scan git history and extract before/after diffs.      Args:         repo_path, scan_git_diffs()

### Community 59 - "Module Group 59"
Cohesion: 0.2
Nodes (9): capture_correction(), hook_status(), install_hook(), Claude Code hooks integration — auto-capture corrections from Claude Code sessio, Add Gradata hooks to Claude Code settings., Remove Gradata hooks from Claude Code settings., Check if Gradata hooks are installed., Called by Claude Code hook — reads stdin for tool use context and records correc (+1 more)

### Community 60 - "Module Group 60"
Cohesion: 0.33
Nodes (8): from_brain_dir(), make_paths(), SDK Paths — Portable Path Resolution ====================================== SD, Re-point all module-level path variables to a new brain directory.      Called, Resolve brain directory from argument, env var, or cwd., Build all derived paths from a brain directory.      Returns a dict of Path ob, resolve_brain_dir(), set_brain_dir()

### Community 61 - "Module Group 61"
Cohesion: 0.29
Nodes (7): generate_manifest(), Brain Manifest Generator (SDK Layer). ====================================== G, Write manifest to brain/brain.manifest.json., Validate existing manifest against current state., Generate the complete brain manifest.      Includes DB session cross-check, be, validate_manifest(), write_manifest()

### Community 62 - "Module Group 62"
Cohesion: 0.25
Nodes (7): get_rule_history(), get_session_applications(), log_application(), Rule Application Tracker — records outcomes via the event system. =============, Recent RULE_APPLICATION events for a specific rule., Emit a RULE_APPLICATION event through the standard event pipeline.      Return, All RULE_APPLICATION events for a given session.

### Community 63 - "Module Group 63"
Cohesion: 0.29
Nodes (7): generate_brain_salt(), load_or_create_salt(), Per-brain salt for non-deterministic graduation thresholds.  Each brain gets a, Generate a 32-byte random salt as a 64-char hex string., Load .brain_salt from *brain_dir*, creating it if absent.      Returns the 64-, Compute a salted threshold by jittering *base* within +/-5%.      Uses HMAC-SH, salt_threshold()

### Community 64 - "Module Group 64"
Cohesion: 0.32
Nodes (7): _canonical_payload(), HMAC-SHA256 manifest signing and verification.  Signs brain manifests with a p, Return a **new** dict with ``signature`` and ``signed_at`` fields added., Verify that *manifest* has a valid HMAC-SHA256 signature.      Returns ``False, Produce canonical JSON bytes, excluding ``signature`` and ``signed_at``., sign_manifest(), verify_manifest()

### Community 65 - "Module Group 65"
Cohesion: 0.25
Nodes (4): Remove timestamps older than the sliding window., Return the number of calls for *endpoint* inside the current window., Return ``True`` if *endpoint* has exceeded ``max_calls``., Detect burst anomalies for *endpoint*.          A burst is flagged when:

### Community 66 - "Module Group 66"
Cohesion: 0.25
Nodes (7): constant_time_pad(), obfuscate_instruction(), Score obfuscation — strip raw confidence floats from prompt-injected rules.  R, Map a raw confidence float to its tier label.      Thresholds match the gradua, Strip raw confidence floats from a formatted instruction string.      Replaces, Execute *fn* and pad to minimum duration with random jitter.      Prevents tim, truncate_score()

### Community 67 - "Module Group 67"
Cohesion: 0.33
Nodes (6): detect_conflict(), extract_diff_tokens(), Split on whitespace, lowercase, strip punctuation, return token set., Return (added_tokens, removed_tokens) between old and new text., True if new correction removes enough of what original added., tokenize()

### Community 68 - "Module Group 68"
Cohesion: 0.33
Nodes (5): PII and credential detection/redaction for the Gradata pipeline.  Critical pip, Return *text* with all detected PII replaced by placeholders., Return (cleaned_text, report_dict).      Report dict keys:         redactions, redact_pii(), redact_pii_with_report()

### Community 69 - "Module Group 69"
Cohesion: 0.33
Nodes (5): get_similarity_threshold(), Brain RAG Pipeline — Shared Configuration. ====================================, Reload domain-specific config from brain/taxonomy.json if it exists.      This, Get similarity threshold for a category. Higher = stricter matching., reload_config()

### Community 70 - "Module Group 70"
Cohesion: 0.33
Nodes (5): create_provenance_record(), Correction provenance authentication via HMAC-SHA256.  Each correction gets a, Create an HMAC-SHA256 signed provenance record for a correction.      Args:, Verify an HMAC-SHA256 signed provenance record.      Args:         record: Pr, verify_provenance()

### Community 71 - "Module Group 71"
Cohesion: 0.4
Nodes (3): EventBus -- lightweight in-memory pub/sub for Gradata's nervous system.  This, Emit *event* with *payload*. Errors are logged, never raised., _safe_call()

### Community 72 - "Module Group 72"
Cohesion: 0.6
Nodes (4): compile_context(), extract_entities(), _get_prospect_names(), Context Compiler. =================== Extracts entities from a user message, q

### Community 73 - "Module Group 73"
Cohesion: 0.4
Nodes (2): Attach effectiveness scores to the session-end payload and reset.          Res, Return per-rule effectiveness scores.          Returns:             Dict mapp

### Community 74 - "Module Group 74"
Cohesion: 0.4
Nodes (2): Record a conflict between two rules., Record that these rules fired together in a session.

### Community 75 - "Module Group 75"
Cohesion: 0.5
Nodes (3): Schema migrations for system.db., Apply pending migrations. Returns count applied., run_migrations()

### Community 76 - "Module Group 76"
Cohesion: 0.5
Nodes (2): Evaluate every guard against *input_data*.          Args:             input_d, Evaluate every guard against *output_data*.          Args:             output

### Community 77 - "Module Group 77"
Cohesion: 0.5
Nodes (3): classify_mode(), Rule-based mode classifier — Signal 5.  Detects user intent mode from prompt t, Classify user prompt into a mode.      Returns:         (mode, confidence) wh

### Community 78 - "Module Group 78"
Cohesion: 0.5
Nodes (3): Optional LLM-enhanced principle synthesis for meta-rules.  When an OpenAI-comp, Synthesise a behavioral principle from related lessons via LLM.      Returns a, synthesise_principle_llm()

### Community 79 - "Module Group 79"
Cohesion: 0.5
Nodes (1): Rule graph — conflict and co-occurrence edges between lessons.  Lightweight ad

### Community 80 - "Module Group 80"
Cohesion: 0.67
Nodes (1): Instruction Cache — caches LLM-extracted behavioral instructions.  Key = hash

### Community 81 - "Module Group 81"
Cohesion: 1.0
Nodes (1): Outcome Feedback -- External signal to confidence feedback loop.

### Community 82 - "Module Group 82"
Cohesion: 1.0
Nodes (1): Build a BrainContext from a brain directory path.          Args:

### Community 83 - "Module Group 83"
Cohesion: 1.0
Nodes (1): Load install state from JSON file.

### Community 84 - "Module Group 84"
Cohesion: 1.0
Nodes (1): Create a manifest with default modules and profiles.

### Community 85 - "Module Group 85"
Cohesion: 1.0
Nodes (1): Return all registered modules.

### Community 86 - "Module Group 86"
Cohesion: 1.0
Nodes (1): Return all registered profiles.

### Community 87 - "Module Group 87"
Cohesion: 1.0
Nodes (1): Current remaining capacity ratio.

### Community 88 - "Module Group 88"
Cohesion: 1.0
Nodes (1): Current context bracket.

### Community 89 - "Module Group 89"
Cohesion: 1.0
Nodes (1): Current bracket guidance.

### Community 90 - "Module Group 90"
Cohesion: 1.0
Nodes (1): Current bracket as prompt injection XML.

### Community 91 - "Module Group 91"
Cohesion: 1.0
Nodes (1): Return the history of bracket transitions.

### Community 92 - "Module Group 92"
Cohesion: 1.0
Nodes (1): Max rules to inject based on current degradation bracket.          Throttles r

### Community 93 - "Module Group 93"
Cohesion: 1.0
Nodes (1): Whether the detector has flagged a loop (WARN or STOP).

### Community 94 - "Module Group 94"
Cohesion: 1.0
Nodes (1): Return the full event history.

### Community 95 - "Module Group 95"
Cohesion: 1.0
Nodes (1): Return the current sliding window of call hashes.

### Community 96 - "Module Group 96"
Cohesion: 1.0
Nodes (1): Hash a tool call for deterministic comparison.          Normalizes by sorting

### Community 97 - "Module Group 97"
Cohesion: 1.0
Nodes (1): Return ordered list of middleware names.

### Community 98 - "Module Group 98"
Cohesion: 1.0
Nodes (1): Number of middlewares in the chain.

### Community 99 - "Module Group 99"
Cohesion: 1.0
Nodes (1): Compute HMAC-SHA256 for integrity verification.

### Community 100 - "Module Group 100"
Cohesion: 1.0
Nodes (1): True if all plan items passed with no gaps or drift.

### Community 101 - "Module Group 101"
Cohesion: 1.0
Nodes (1): Fraction of plan items that fully passed.

### Community 102 - "Module Group 102"
Cohesion: 1.0
Nodes (1): Return criterion names in definition order.

### Community 103 - "Module Group 103"
Cohesion: 1.0
Nodes (1): MUST violations are blocking; SHOULD and MAY are not.

### Community 104 - "Module Group 104"
Cohesion: 1.0
Nodes (1): Return only MUST (blocking) constraints.

### Community 105 - "Module Group 105"
Cohesion: 1.0
Nodes (1): Return only SHOULD (warning) constraints.

### Community 106 - "Module Group 106"
Cohesion: 1.0
Nodes (1): Return only MAY (suggestion) constraints.

### Community 107 - "Module Group 107"
Cohesion: 1.0
Nodes (1): Return set of all registered domains.

### Community 108 - "Module Group 108"
Cohesion: 1.0
Nodes (1): Deserialize from dict.

### Community 109 - "Module Group 109"
Cohesion: 1.0
Nodes (1): Send a prompt and return the completion text, or None on failure.

### Community 110 - "Module Group 110"
Cohesion: 1.0
Nodes (1): Whether this prediction is currently in its active window.

### Community 111 - "Module Group 111"
Cohesion: 1.0
Nodes (1): Whether this prediction's window has passed.

### Community 112 - "Module Group 112"
Cohesion: 1.0
Nodes (1): Merge source fields into target, keeping highest level.

### Community 113 - "Module Group 113"
Cohesion: 1.0
Nodes (1): SSRF protection: only allow HTTPS to gradata.ai or localhost.

## Knowledge Gaps
- **634 isolated node(s):** `Audit Trail + Provenance — SQLite-backed rule provenance tracking. ============`, `Insert a provenance row linking a rule to a correction event.      Args:`, `Query the rule_provenance table.      Args:         db_path: Path to system.d`, `Scan events.jsonl for events matching the given IDs.      Args:         event`, `Full trace of a rule: provenance table, events fallback, transitions.      Arg` (+629 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Module Group 81`** (2 nodes): `outcome_feedback.py`, `Outcome Feedback -- External signal to confidence feedback loop.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 82`** (1 nodes): `Build a BrainContext from a brain directory path.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 83`** (1 nodes): `Load install state from JSON file.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 84`** (1 nodes): `Create a manifest with default modules and profiles.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 85`** (1 nodes): `Return all registered modules.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 86`** (1 nodes): `Return all registered profiles.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 87`** (1 nodes): `Current remaining capacity ratio.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 88`** (1 nodes): `Current context bracket.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 89`** (1 nodes): `Current bracket guidance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 90`** (1 nodes): `Current bracket as prompt injection XML.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 91`** (1 nodes): `Return the history of bracket transitions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 92`** (1 nodes): `Max rules to inject based on current degradation bracket.          Throttles r`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 93`** (1 nodes): `Whether the detector has flagged a loop (WARN or STOP).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 94`** (1 nodes): `Return the full event history.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 95`** (1 nodes): `Return the current sliding window of call hashes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 96`** (1 nodes): `Hash a tool call for deterministic comparison.          Normalizes by sorting`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 97`** (1 nodes): `Return ordered list of middleware names.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 98`** (1 nodes): `Number of middlewares in the chain.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 99`** (1 nodes): `Compute HMAC-SHA256 for integrity verification.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 100`** (1 nodes): `True if all plan items passed with no gaps or drift.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 101`** (1 nodes): `Fraction of plan items that fully passed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 102`** (1 nodes): `Return criterion names in definition order.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 103`** (1 nodes): `MUST violations are blocking; SHOULD and MAY are not.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 104`** (1 nodes): `Return only MUST (blocking) constraints.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 105`** (1 nodes): `Return only SHOULD (warning) constraints.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 106`** (1 nodes): `Return only MAY (suggestion) constraints.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 107`** (1 nodes): `Return set of all registered domains.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 108`** (1 nodes): `Deserialize from dict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 109`** (1 nodes): `Send a prompt and return the completion text, or None on failure.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 110`** (1 nodes): `Whether this prediction is currently in its active window.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 111`** (1 nodes): `Whether this prediction's window has passed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 112`** (1 nodes): `Merge source fields into target, keeping highest level.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Group 113`** (1 nodes): `SSRF protection: only allow HTTPS to gradata.ai or localhost.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Brain` connect `Brain Core & Adapters` to `Brain Inspection & Patterns`, `Events & Analytics`, `Agent Graduation Pipeline`, `Guardrails & Middleware`?**
  _High betweenness centrality (0.242) - this node is a cross-community bridge._
- **Why does `LessonState` connect `Brain Inspection & Patterns` to `Brain Core & Adapters`, `Agent Modes & Permissions`, `Behavioral Extraction`, `Events & Analytics`, `Module Group 15`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Why does `BrainContext` connect `Brain Inspection & Patterns` to `Brain Core & Adapters`, `Agent Graduation Pipeline`, `Module Group 39`, `Module Group 72`, `Module Group 40`, `Embeddings & Similarity`, `Events & Analytics`, `Module Group 45`, `Module Group 47`, `Module Group 53`, `Module Group 23`, `Module Group 56`, `Module Group 24`, `Module Group 60`, `Module Group 61`, `Module Group 31`?**
  _High betweenness centrality (0.141) - this node is a cross-community bridge._
- **Are the 164 inferred relationships involving `Brain` (e.g. with `Lesson` and `BrainInspectionMixin`) actually correct?**
  _`Brain` has 164 INFERRED edges - model-reasoned connections that need verification._
- **Are the 191 inferred relationships involving `Lesson` (e.g. with `Brain` and `Brain — Core SDK class for procedural memory.  A Brain is a directory containi`) actually correct?**
  _`Lesson` has 191 INFERRED edges - model-reasoned connections that need verification._
- **Are the 177 inferred relationships involving `LessonState` (e.g. with `Brain` and `Brain — Core SDK class for procedural memory.  A Brain is a directory containi`) actually correct?**
  _`LessonState` has 177 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `BrainContext` (e.g. with `Brain` and `Brain — Core SDK class for procedural memory.  A Brain is a directory containi`) actually correct?**
  _`BrainContext` has 132 INFERRED edges - model-reasoned connections that need verification._