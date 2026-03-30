"""
Brain — Core SDK class for operating a personal AI brain.

A Brain is a directory containing:
  - Markdown knowledge files (prospects, sessions, patterns, personas, etc.)
  - system.db (SQLite event log, facts, metrics, embeddings)
  - .embed-manifest.json (file hash tracking for delta embedding)
  - brain.manifest.json (machine-readable brain spec)

Usage:
    brain = Brain.init("./my-brain")           # Bootstrap a new brain
    brain = Brain("./my-brain")                # Open existing brain

    # Search
    results = brain.search("budget objections")
    results = brain.search("Hassan Ali", mode="keyword")

    # Embed
    brain.embed()                              # Delta (only changed files)
    brain.embed(full=True)                     # Full re-embed

    # Events
    brain.emit("CORRECTION", "user", {"category": "DRAFTING", "detail": "..."})
    events = brain.query_events(event_type="CORRECTION", last_n_sessions=3)

    # Facts
    facts = brain.get_facts(prospect="Hassan Ali")

    # Manifest
    manifest = brain.manifest()                # Generate brain.manifest.json

    # Export
    brain.export("./exports/my-brain.zip")     # Package for marketplace
"""

import logging
import sqlite3
import sys
from pathlib import Path

logger = logging.getLogger("gradata")

# ── Graceful optional dependency handling ─────────────────────────────
# FTS5 is the primary search engine. sqlite-vec planned for vector similarity.
# sentence-transformers is still optional for local embedding generation.

_sentence_transformers = None
_sentence_transformers_error = None
try:
    import sentence_transformers as _sentence_transformers
except ImportError:
    _sentence_transformers_error = (
        "sentence-transformers is not installed. Install it with:\n"
        "  pip install sentence-transformers\n"
        "Local embedding features require sentence-transformers."
    )
except Exception as _e:
    _sentence_transformers_error = f"sentence-transformers failed to import: {_e}"


def _require_sentence_transformers():
    """Raise a clear error if sentence-transformers is unavailable."""
    if _sentence_transformers is None:
        raise ImportError(_sentence_transformers_error)


class Brain:
    """A personal AI brain backed by a directory of knowledge files."""

    def __init__(self, brain_dir: str | Path, working_dir: str | Path | None = None):
        self.dir = Path(brain_dir).resolve()
        if not self.dir.exists():
            from gradata.exceptions import BrainNotFoundError
            raise BrainNotFoundError(f"Brain directory not found: {self.dir}")

        self.db_path = self.dir / "system.db"
        self.manifest_path = self.dir / "brain.manifest.json"
        self.embed_manifest_path = self.dir / ".embed-manifest.json"

        logger.debug("Brain init: %s (db=%s)", self.dir, self.db_path)

        # Build immutable context for this brain instance (DI path)
        from gradata._paths import BrainContext, set_brain_dir
        self.ctx = BrainContext.from_brain_dir(self.dir, working_dir)

        # Point all SDK modules to this brain directory (backward compat path)
        set_brain_dir(self.dir, working_dir)

        # Reload taxonomy and config from brain dir (if taxonomy.json exists)
        try:
            from gradata._tag_taxonomy import reload_taxonomy
            reload_taxonomy()
        except ImportError:
            pass
        try:
            from gradata._config import reload_config
            reload_config(self.dir)
        except ImportError:
            pass

        # Apply any pending schema migrations
        from gradata._migrations import run_migrations
        run_migrations(self.db_path)

        # Initialize pattern registries (lazy — ImportError safe)
        try:
            from gradata_cloud.profiling.carl import ContractRegistry
            self.contracts: ContractRegistry = ContractRegistry()
        except ImportError:
            try:
                from gradata.enhancements.carl import ContractRegistry
                self.contracts: ContractRegistry = ContractRegistry()
            except ImportError:
                self.contracts = None  # type: ignore[assignment]
        try:
            from gradata.patterns.tools import ToolRegistry
            self.tools: ToolRegistry = ToolRegistry()
        except ImportError:
            self.tools = None  # type: ignore[assignment]

        # Agent graduation tracker (compounding agent behavioral profiles)
        try:
            from gradata_cloud.graduation.agent_graduation import AgentGraduationTracker
            self.agent_graduation: AgentGraduationTracker = AgentGraduationTracker(self.dir)
        except ImportError:
            try:
                from gradata.enhancements.agent_graduation import AgentGraduationTracker
                self.agent_graduation: AgentGraduationTracker = AgentGraduationTracker(self.dir)
            except ImportError:
                self.agent_graduation = None  # type: ignore[assignment]

        # Learning pipeline (end-to-end: observe→cluster→discriminate→route→bracket)
        self._learning_pipeline = None
        try:
            from gradata.enhancements.learning_pipeline import LearningPipeline
            self._learning_pipeline = LearningPipeline(brain_dir=self.dir)

            # Warm-start the Q-Learning router from historical corrections
            if self._learning_pipeline._router and self.db_path.exists():
                try:
                    from gradata.enhancements.router_warmstart import warm_start_router
                    warm_router = warm_start_router(
                        db_path=self.db_path,
                        router_path=self.dir / "q_router.json",
                    )
                    self._learning_pipeline._router = warm_router
                except Exception:
                    pass  # Warm-start is best-effort
        except ImportError:
            pass

        # Cloud connection (None = local-only mode)
        self._cloud = None

    @classmethod
    def init(
        cls,
        brain_dir: str | Path,
        *,
        domain: str = None,
        name: str = None,
        company: str = None,
        embedding: str = None,
        interactive: bool = None,
    ) -> "Brain":
        """Bootstrap a new brain directory with the onboarding wizard.

        Args:
            brain_dir: Path to create the brain in.
            domain: Brain domain (e.g. "Sales", "Engineering").
            name: Brain name for the manifest.
            company: Company name (creates company.md if provided).
            embedding: "local" (default) or "gemini".
            interactive: If True, prompts for missing values. Auto-detected
                         from terminal if not specified.

        Returns:
            Brain instance pointing at the new directory.
        """
        from gradata.onboard import onboard

        if interactive is None:
            interactive = hasattr(sys, "stdin") and sys.stdin.isatty()

        return onboard(
            brain_dir,
            name=name,
            domain=domain,
            company=company,
            embedding=embedding,
            interactive=interactive,
        )

    # ── Search ─────────────────────────────────────────────────────────

    def search(self, query: str, mode: str = None, top_k: int = 5,
               file_type: str = None) -> list[dict]:
        """Search the brain using FTS5 keyword search.

        All modes use FTS5 keyword search. sqlite-vec planned for vector similarity.
        """
        try:
            from gradata._query import brain_search
            return brain_search(
                query, file_type=file_type, top_k=top_k, mode=mode, ctx=self.ctx
            )
        except ImportError:
            # Fallback: basic file grep
            return self._grep_search(query, top_k)

    def _grep_search(self, query: str, top_k: int) -> list[dict]:
        """Fallback search: grep through markdown files."""
        results = []
        query_lower = query.lower()
        for f in self.dir.rglob("*.md"):
            if ".git" in str(f) or "scripts" in str(f):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if query_lower in text.lower():
                    # Find the matching line for context
                    for line in text.splitlines():
                        if query_lower in line.lower():
                            results.append({
                                "source": str(f.relative_to(self.dir)),
                                "text": line[:200],
                                "score": 1.0,
                                "confidence": "keyword_match",
                            })
                            break
            except Exception:
                continue
            if len(results) >= top_k:
                break
        return results

    # ── Embedding ──────────────────────────────────────────────────────

    def embed(self, full: bool = False) -> int:
        """Embed brain files into SQLite. Returns chunks embedded.

        Embeddings stored in SQLite brain_embeddings table.
        """
        try:
            from gradata._embed import main as embed_main
            return embed_main(brain_dir=self.dir, full=full)
        except ImportError as e:
            raise ImportError(
                f"Embedding requires additional dependencies: {e}\n"
                "Run: pip install sentence-transformers"
            ) from e
        except Exception as e:
            print(f"Embed error: {e}")
            return -1

    # ── Events ─────────────────────────────────────────────────────────

    def emit(self, event_type: str, source: str, data: dict = None,
             tags: list = None, session: int = None) -> dict:
        """Emit an event to the brain's event log."""
        from gradata._events import emit
        return emit(event_type, source, data or {}, tags or [], session, ctx=self.ctx)

    def query_events(self, event_type: str = None, session: int = None,
                     last_n_sessions: int = None, limit: int = 100) -> list[dict]:
        """Query events from the brain's event log."""
        try:
            from gradata._events import query
            return query(event_type=event_type, session=session,
                         last_n_sessions=last_n_sessions, limit=limit, ctx=self.ctx)
        except ImportError:
            return []

    # ── Facts ──────────────────────────────────────────────────────────

    def get_facts(self, prospect: str = None, fact_type: str = None) -> list[dict]:
        """Query structured facts from the brain."""
        try:
            from gradata._fact_extractor import query_facts
            return query_facts(prospect=prospect, fact_type=fact_type, ctx=self.ctx)
        except ImportError:
            return []

    def extract_facts(self) -> int:
        """Extract structured facts from all prospect files."""
        try:
            from gradata._fact_extractor import extract_all, store_facts
            facts = extract_all(ctx=self.ctx)
            store_facts(facts, ctx=self.ctx)
            return len(facts)
        except ImportError:
            return 0

    # ── Manifest ───────────────────────────────────────────────────────

    def manifest(self) -> dict:
        """Generate brain.manifest.json and return it."""
        try:
            from gradata._brain_manifest import generate_manifest, write_manifest
            m = generate_manifest(ctx=self.ctx)
            write_manifest(m, ctx=self.ctx)
            return m
        except ImportError:
            # Minimal manifest without brain_manifest module
            return {
                "schema_version": "1.0.0",
                "metadata": {
                    "brain_version": "unknown",
                    "domain": "unknown",
                },
            }

    # ── Export ──────────────────────────────────────────────────────────

    def export(self, output_path: str = None, mode: str = "full") -> Path:
        """Export brain as a shareable archive."""
        try:
            from gradata._export_brain import export_brain
            return export_brain(
                include_prospects=(mode != "no-prospects"),
                domain_only=(mode == "domain-only"),
                ctx=self.ctx,
            )
        except ImportError as e:
            raise RuntimeError(f"Export requires brain modules: {e}")

    # ── Context ────────────────────────────────────────────────────────

    def context_for(self, message: str) -> str:
        """Compile relevant context for a user message."""
        try:
            from gradata._context_compile import compile_context
            return compile_context(message, ctx=self.ctx)
        except ImportError:
            # Fallback: basic search
            results = self.search(message[:100], top_k=3)
            if not results:
                return ""
            lines = ["## Brain Context"]
            for r in results:
                lines.append(f"- [{r.get('source', '')}] {r.get('text', '')[:150]}")
            return "\n".join(lines)

    # ── Core Learning Loop (correction capture) ────────────────────────

    def correct(
        self,
        draft: str,
        final: str,
        category: str | None = None,
        context: dict | None = None,
        session: int | None = None,
    ) -> dict:
        """Record a correction: the user edited a draft into a final version.

        This is the primary learning signal. The founding docs call it the
        biggest technical risk — how corrections get INTO the system.

        This method:
        1. Computes diff (edit distance + severity)
        2. Classifies edits (tone/content/structure/factual/style)
        3. Emits a CORRECTION event with full metadata
        4. Returns the analysis for immediate use

        Args:
            draft: The AI-generated text before user editing.
            final: The text after user editing.
            category: Optional override for correction category.
            context: Optional session context dict for scope building.
            session: Session number (auto-detected if omitted).
        """
        # ── Input validation ──────────────────────────────────────────
        if not draft and not final:
            raise ValueError("Both draft and final are empty — nothing to correct.")
        if draft == final:
            raise ValueError("draft and final are identical — no correction detected.")
        max_input = 100_000
        if len(draft) + len(final) > max_input:
            raise ValueError(
                f"Combined input length ({len(draft) + len(final)}) exceeds "
                f"limit ({max_input}). Truncate inputs before calling correct()."
            )
        if session is not None and (not isinstance(session, int) or session < 1):
            raise ValueError(f"session must be a positive integer, got {session!r}")

        # Route to cloud if connected, otherwise run locally
        if self._cloud and self._cloud.connected:
            try:
                return self._cloud.correct(draft, final, category, context, session)
            except Exception as e:
                logger.warning("Cloud correct() failed, falling back to local: %s", e)
                self._cloud.connected = False

        # Try full enhancement pipeline (diff + classify + extract)
        # Prefer gradata_cloud (proprietary), fall back to enhancements/ (bundled)
        try:
            from gradata.enhancements.diff_engine import compute_diff
            try:
                from gradata_cloud.graduation.edit_classifier import classify_edits, summarize_edits
            except ImportError:
                from gradata.enhancements.edit_classifier import classify_edits, summarize_edits
        except ImportError:
            # Enhancements not installed — basic correction logging only
            data = {
                "draft_text": draft[:2000],
                "final_text": final[:2000],
                "edit_distance": 0.0,
                "severity": "unknown",
                "outcome": "unknown",
                "major_edit": False,
                "category": category or "UNKNOWN",
                "summary": "",
                "classifications": [],
            }
            tags = [f"category:{category or 'UNKNOWN'}"]
            return self.emit("CORRECTION", "brain.correct", data, tags, session)

        from gradata._scope import build_scope

        diff = compute_diff(draft, final)
        classifications = classify_edits(diff)
        summary = summarize_edits(classifications)

        # Auto-detect category from classifications if not provided
        if not category and classifications:
            category = classifications[0].category.upper()

        # Build scope from context (Engineering Spec: every correction is scoped)
        scope_data = {}
        if context:
            from gradata._scope import scope_to_dict
            scope_data = scope_to_dict(build_scope(context))

        data = {
            # Engineering Spec fields: draft_text, final_text, edit_distance, outcome, major_edit
            "draft_text": draft[:2000],
            "final_text": final[:2000],
            "edit_distance": diff.edit_distance,
            "severity": diff.severity,
            "outcome": diff.severity,  # as-is / minor / moderate / major / discarded
            "major_edit": diff.severity in ("major", "discarded"),
            "category": category or "UNKNOWN",
            "summary": summary,
            "classifications": [
                {"category": c.category, "severity": c.severity, "description": c.description}
                for c in classifications
            ],
            "lines_added": diff.summary_stats.get("lines_added", 0),
            "lines_removed": diff.summary_stats.get("lines_removed", 0),
        }
        if scope_data:
            data["scope"] = scope_data

        tags = [f"category:{category or 'UNKNOWN'}", f"severity:{diff.severity}"]
        if diff.severity in ("major", "discarded"):
            tags.append("major_edit:true")

        event = self.emit("CORRECTION", "brain.correct", data, tags, session)
        event["diff"] = diff
        event["classifications"] = classifications

        # Auto-extract patterns from classifications (step 3 of core loop)
        patterns = []
        try:
            try:
                from gradata_cloud.graduation.pattern_extractor import extract_patterns
            except ImportError:
                from gradata.enhancements.pattern_extractor import extract_patterns
            scope_obj = build_scope(context) if context else None
            patterns = extract_patterns(classifications, scope=scope_obj)
            if patterns:
                event["patterns_extracted"] = len(patterns)
                logger.debug("Extracted %d patterns from correction", len(patterns))
        except Exception as e:
            logger.warning("Pattern extraction failed: %s", e)

        # Step 3b: CLOSE THE LOOP — every correction becomes a lesson candidate
        # This is the critical link: correction → lesson in lessons.md → rules
        # Key insight: don't wait for pattern clustering. Each correction with
        # sufficient severity is a lesson candidate. Graduation handles quality.
        try:
            from datetime import date as _date
            from gradata._types import Lesson, LessonState, CorrectionType
            try:
                from gradata_cloud.graduation.self_improvement import (
                    parse_lessons, format_lessons, update_confidence,
                    INITIAL_CONFIDENCE,
                )
            except ImportError:
                from gradata.enhancements.self_improvement import (
                    parse_lessons, format_lessons, update_confidence,
                    INITIAL_CONFIDENCE,
                )

            # Only create lessons for meaningful corrections (not trivial typos)
            if diff.severity not in ("as-is",):
                lessons_path = self._find_lessons_path(create=True)
                if lessons_path:
                    existing_text = ""
                    if lessons_path.is_file():
                        existing_text = lessons_path.read_text(encoding="utf-8")
                    existing_lessons = parse_lessons(existing_text) if existing_text else []

                    # Build lesson description from the correction
                    cat = (category or "UNKNOWN").upper()
                    desc = summary if summary else f"Corrected {cat.lower()} ({diff.severity})"

                    # Deduplicate: same category + similar description = same lesson
                    existing_keys = {
                        (l.category, l.description[:40]) for l in existing_lessons
                    }
                    key = (cat, desc[:40])

                    if key not in existing_keys:
                        # New lesson — start as INSTINCT
                        new_lesson = Lesson(
                            date=_date.today().isoformat(),
                            state=LessonState.INSTINCT,
                            confidence=INITIAL_CONFIDENCE,
                            category=cat,
                            description=desc,
                        )
                        existing_lessons.append(new_lesson)
                        event["lessons_created"] = 1
                        logger.info("New lesson: [INSTINCT:%.2f] %s: %s",
                                   INITIAL_CONFIDENCE, cat, desc[:60])

                    # Update confidence on ALL lessons based on this correction
                    correction_data = [{
                        "category": cat,
                        "severity_label": diff.severity,
                    }]
                    severity_data = {cat: diff.severity}
                    existing_lessons = update_confidence(
                        existing_lessons,
                        correction_data,
                        severity_data=severity_data,
                    )

                    # Write back
                    lessons_path.write_text(
                        format_lessons(existing_lessons),
                        encoding="utf-8",
                    )
                    if "lessons_created" not in event:
                        event["lessons_updated"] = True

        except Exception as e:
            logger.warning("Lesson creation failed: %s", e)

        # Step 4: Run through the learning pipeline (observe→cluster→discriminate→route→bracket)
        if self._learning_pipeline:
            try:
                task_type = ""
                if context:
                    task_type = context.get("task_type", context.get("task", ""))
                pipeline_result = self._learning_pipeline.process_correction(
                    draft=draft,
                    final=final,
                    severity=diff.severity,
                    category=category or "UNKNOWN",
                    session_id=str(session or ""),
                    task_type=task_type,
                    occurrence_count=1,
                )
                event["pipeline"] = {
                    "stages_completed": pipeline_result.stages_completed,
                    "is_high_value": pipeline_result.is_high_value,
                    "discriminator_confidence": pipeline_result.discriminator_confidence,
                    "recommendation": pipeline_result.discriminator_recommendation,
                    "cluster_id": pipeline_result.cluster_id,
                    "context_bracket": pipeline_result.context_bracket,
                    "memory_type": pipeline_result.memory_type,
                    "processing_time_ms": pipeline_result.processing_time_ms,
                }
                logger.debug(
                    "Pipeline: %d stages, high_value=%s, bracket=%s",
                    len(pipeline_result.stages_completed),
                    pipeline_result.is_high_value,
                    pipeline_result.context_bracket,
                )
            except Exception as e:
                logger.warning("Learning pipeline failed: %s", e)

        return event

    def log_output(
        self,
        text: str,
        output_type: str = "general",
        prompt: str | None = None,
        self_score: float | None = None,
        scope: dict | None = None,
        session: int | None = None,
        rules_applied: list[str] | None = None,
    ) -> dict:
        """Log an AI-generated output for tracking.

        Per Engineering Spec: each output needs prompt, draft_text,
        edit_distance, outcome, major_edit. The draft is captured here;
        edit_distance and outcome are computed when correct() is called.

        Args:
            text: The AI-generated draft text.
            output_type: Type of output (email, research, code, etc).
            prompt: The user prompt that triggered this output.
            self_score: Self-assessment score (0-10). Used for Brier calibration.
            scope: Optional scope dict (domain, task_type, audience, channel, stakes).
            session: Session number (auto-detected if omitted).
            rules_applied: List of rule IDs active when this output was generated.
                Enables external signal → rule attribution for outcome feedback.
        """
        data = {
            "output_type": output_type,
            "output_text": text[:5000],
            "outcome": "pending",        # pending -> accepted / minor / moderate / major / discarded
            "major_edit": False,
            "rules_applied": rules_applied or [],
        }
        if prompt is not None:
            data["prompt"] = prompt[:2000]
        if self_score is not None:
            data["self_score"] = self_score
        if scope is not None:
            data["scope"] = scope

        tags = [f"output:{output_type}"]
        return self.emit("OUTPUT", "brain.log_output", data, tags, session)

    def apply_brain_rules(
        self,
        task: str,
        context: dict | None = None,
    ) -> str:
        """Get applicable brain rules for a task, formatted for prompt injection.

        Args:
            task: Description of the task being performed.
            context: Optional context dict with domain, prospect info, etc.
        """
        # Route to cloud if connected
        if self._cloud and self._cloud.connected:
            try:
                return self._cloud.apply_rules(task, context)
            except Exception as e:
                logger.warning("Cloud apply_rules() failed, falling back to local: %s", e)
                self._cloud.connected = False

        try:
            try:
                from gradata_cloud.graduation.self_improvement import parse_lessons
            except ImportError:
                from gradata.enhancements.self_improvement import parse_lessons
        except ImportError:
            return ""  # Neither cloud nor enhancements installed — no rules available
        from gradata._scope import build_scope
        from gradata.patterns.rule_engine import apply_rules, format_rules_for_prompt

        ctx = context or {}
        ctx.setdefault("task", task)
        scope = build_scope(ctx)

        # Load lessons — check env var, brain dir, then parent's .claude/ for compat
        import os
        env_path = os.environ.get("BRAIN_LESSONS_PATH", "")
        lessons_path = None
        if env_path and Path(env_path).is_file():
            lessons_path = Path(env_path)
        elif (self.dir / "lessons.md").is_file():
            lessons_path = self.dir / "lessons.md"
        elif (self.dir.parent / ".claude" / "lessons.md").is_file():
            lessons_path = self.dir.parent / ".claude" / "lessons.md"
        if lessons_path is None:
            return ""

        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        applied = apply_rules(lessons, scope)
        return format_rules_for_prompt(applied)

    # ── Info ───────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return brain statistics."""
        md_count = sum(1 for _ in self.dir.rglob("*.md")
                       if ".git" not in str(_) and "scripts" not in str(_))
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        # Check for embeddings in SQLite
        has_embeddings = False
        embedding_count = 0
        if self.db_path.exists():
            try:
                conn = sqlite3.connect(str(self.db_path))
                row = conn.execute(
                    "SELECT COUNT(*) FROM brain_embeddings"
                ).fetchone()
                embedding_count = row[0] if row else 0
                has_embeddings = embedding_count > 0
                conn.close()
            except Exception:
                pass

        return {
            "brain_dir": str(self.dir),
            "markdown_files": md_count,
            "db_size_mb": round(db_size / 1024 / 1024, 2),
            "embedding_chunks": embedding_count,
            "has_manifest": self.manifest_path.exists(),
            "has_embeddings": has_embeddings,
        }

    # ── Pattern integration ──────────────────────────────────────────

    def classify(self, message: str) -> dict:
        """Classify a user message into intent, audience, pattern."""
        try:
            from gradata.patterns.orchestrator import classify_request
            c = classify_request(message)
            import dataclasses
            return dataclasses.asdict(c) if dataclasses.is_dataclass(c) else vars(c)
        except ImportError:
            return {"intent": "general", "selected_pattern": "pipeline"}

    def health(self) -> dict:
        """Generate brain health report."""
        try:
            try:
                from gradata_cloud.scoring.reports import generate_health_report
            except ImportError:
                from gradata.enhancements.reports import generate_health_report
            import dataclasses
            report = generate_health_report(self.db_path)
            return dataclasses.asdict(report)
        except ImportError:
            return {"healthy": True, "issues": []}

    def success_conditions(self, window: int = 20) -> dict:
        """Evaluate success conditions from SPEC.md Section 5."""
        try:
            try:
                from gradata_cloud.scoring.success_conditions import evaluate_success_conditions
            except ImportError:
                from gradata.enhancements.success_conditions import evaluate_success_conditions
            import dataclasses
            report = evaluate_success_conditions(self.db_path, window)
            return dataclasses.asdict(report)
        except ImportError:
            return {"all_met": False, "conditions": []}

    def register_contract(self, contract) -> None:
        """Register a CARL behavioral contract."""
        if self.contracts is not None:
            self.contracts.register(contract)

    def get_constraints(self, task: str) -> list[str]:
        """Get applicable CARL constraints for a task."""
        if self.contracts is not None:
            return self.contracts.get_constraints(task)
        return []

    def register_tool(self, spec, handler=None) -> None:
        """Register a tool in the brain's tool registry."""
        if self.tools is not None:
            self.tools.register(spec, handler)

    # ── Pattern API — new convenience methods ────────────────────────────

    def guard(self, text: str, direction: str = "input") -> dict:
        """Run guardrail checks on text. direction: ``"input"`` or ``"output"``."""
        from gradata.patterns.guardrails import (
            InputGuard,
            OutputGuard,
            banned_phrases,
            destructive_action,
            injection_detector,
            pii_detector,
        )
        if direction == "input":
            guard_obj = InputGuard(pii_detector, injection_detector)
            checks = guard_obj.check(text)
        else:
            guard_obj = OutputGuard(banned_phrases, destructive_action)
            checks = guard_obj.check(text)

        failing = [c for c in checks if c.result == "fail"]
        blocked = direction == "input" and bool(failing)
        return {
            "all_passed": not failing,
            "blocked": blocked,
            "block_reason": "; ".join(f"{c.name}: {c.details}" for c in failing) if failing else None,
            "checks": [{"name": c.name, "result": c.result, "details": c.details} for c in checks],
        }

    def reflect(
        self,
        draft: str,
        checklist=None,
        evaluator=None,
        refiner=None,
        max_cycles: int = 3,
    ) -> dict:
        """Run a generate-critique-refine reflection loop on a draft.

        Returns dict with ``final_output``, ``cycles_used``, ``converged``, ``critiques``.
        """
        from gradata.patterns.reflection import (
            EMAIL_CHECKLIST,
            default_evaluator,
        )
        from gradata.patterns.reflection import (
            reflect as _reflect,
        )

        if checklist is None:
            checklist = EMAIL_CHECKLIST
        if evaluator is None:
            evaluator = default_evaluator
        if refiner is None:
            refiner = lambda output, failed: output  # noqa: E731

        result = _reflect(
            output=draft,
            checklist=checklist,
            evaluator=evaluator,
            refiner=refiner,
            max_cycles=max_cycles,
        )
        return {
            "final_output": result.final_output,
            "cycles_used": result.cycles_used,
            "converged": result.converged,
            "critiques": [
                {
                    "cycle": c.cycle,
                    "all_required_passed": c.all_required_passed,
                    "overall_score": c.overall_score,
                }
                for c in result.critiques
            ],
        }

    def assess_risk(self, action: str, context: dict | None = None) -> dict:
        """Classify risk level of an action. Returns tier, reason, affected, reversible."""
        from gradata.patterns.human_loop import assess_risk as _assess_risk
        result = _assess_risk(action, context)
        return {
            "tier": result.tier,
            "reason": result.reason,
            "affected": result.affected,
            "reversible": result.reversible,
        }

    def track_rule(
        self,
        rule_id: str,
        accepted: bool,
        misfired: bool = False,
        contradicted: bool = False,
        session: int | None = None,
    ) -> dict | None:
        """Log a RULE_APPLICATION event. Returns event dict or None on failure."""
        from gradata.patterns.rule_tracker import log_application

        # Infer current session from events if not provided
        if session is None:
            try:
                from gradata._events import get_current_session
                session = get_current_session()
            except Exception:
                import sys
                print("[brain] WARNING: session detection failed, defaulting to 0", file=sys.stderr)
                session = 0

        return log_application(
            rule_id=rule_id,
            session=session,
            accepted=accepted,
            misfired=misfired,
            contradicted=contradicted,
        )

    def process_outcome_feedback(self, session: int | None = None) -> dict[str, float]:
        """Process external signal outcomes (DELTA_TAG) for confidence feedback.

        Returns {rule_id: confidence_delta} dict. Deltas are capped per tier
        and weighted below user corrections (external attribution is uncertain).
        Idempotent: processing the same session twice returns empty dict.
        """
        try:
            from gradata.enhancements.outcome_feedback import process_session_outcomes
            return process_session_outcomes(session, ctx=self.ctx)
        except ImportError:
            return {}
        except Exception as e:
            logger.warning("Outcome feedback processing failed: %s", e)
            return {}

    def pipeline(self, *stages) -> "Pipeline":
        """Create a Pipeline with the given Stage instances."""
        from gradata.patterns.pipeline import Pipeline
        return Pipeline(*stages)

    def register_task_type(
        self,
        name: str,
        keywords: list[str],
        domain_hint: str = "",
        *,
        prepend: bool = False,
    ) -> None:
        """Register a custom task type in the global scope classifier."""
        from gradata.patterns.scope import register_task_type as _register
        _register(name, keywords, domain_hint, prepend=prepend)

    # ── Session-End Graduation (auto-promote survivors) ─────────────────

    def end_session(
        self,
        session_corrections: list[dict] | None = None,
        session_type: str = "full",
    ) -> dict:
        """Run full graduation sweep at end of session.

        This is the auto-promotion mechanism. Every lesson that SURVIVED
        this session (wasn't contradicted) gets a confidence bump. Lessons
        that cross thresholds (0.60 → PATTERN, 0.90 → RULE) get promoted.
        Lessons that hit kill limits get archived.

        Should be called at session end (wrap-up, hook, or manually).

        Args:
            session_corrections: All corrections from this session.
            session_type: "full", "sales", or "systems" for decay scoping.

        Returns:
            Dict with promotion/demotion/kill counts.
        """
        try:
            try:
                from gradata_cloud.graduation.self_improvement import (
                    parse_lessons, format_lessons, update_confidence, graduate,
                )
            except ImportError:
                from gradata.enhancements.self_improvement import (
                    parse_lessons, format_lessons, update_confidence, graduate,
                )

            lessons_path = self._find_lessons_path()
            if not lessons_path or not lessons_path.is_file():
                return {"error": "no lessons.md found"}

            text = lessons_path.read_text(encoding="utf-8")
            lessons = parse_lessons(text)
            if not lessons:
                return {"lessons": 0, "promotions": 0, "demotions": 0}

            before_states = {l.description[:40]: l.state.value for l in lessons}

            # Run full confidence update with all session corrections
            lessons = update_confidence(
                lessons,
                session_corrections or [],
                session_type=session_type,
            )

            # Run graduation (promote/demote/kill)
            active, graduated = graduate(lessons)

            # Count changes
            promotions = 0
            demotions = 0
            kills = 0
            for l in active + graduated:
                key = l.description[:40]
                old_state = before_states.get(key, "")
                new_state = l.state.value
                if old_state and new_state != old_state:
                    if new_state in ("PATTERN", "RULE"):
                        promotions += 1
                    elif new_state == "INSTINCT" and old_state == "PATTERN":
                        demotions += 1
                    elif new_state in ("KILLED", "UNTESTABLE"):
                        kills += 1

            # Write back
            all_lessons = active + graduated
            lessons_path.write_text(
                format_lessons(all_lessons),
                encoding="utf-8",
            )

            # Archive graduated RULE lessons to lessons-archive.md
            archive_path = lessons_path.parent / "lessons-archive.md"
            new_rules = [l for l in graduated if l.state.value == "RULE"
                        and before_states.get(l.description[:40]) != "RULE"]
            if new_rules and archive_path.exists():
                from datetime import date
                archive_text = archive_path.read_text(encoding="utf-8")
                archive_lines = [archive_text.rstrip()]
                archive_lines.append(f"\n## Graduated {date.today().isoformat()} (auto)")
                for r in new_rules:
                    archive_lines.append(
                        f"[{r.date}] {r.category}: {r.description} → Auto-graduated (confidence {r.confidence:.2f})"
                    )
                archive_path.write_text("\n".join(archive_lines) + "\n", encoding="utf-8")

            result = {
                "total_lessons": len(all_lessons),
                "active": len(active),
                "graduated": len(graduated),
                "promotions": promotions,
                "demotions": demotions,
                "kills": kills,
                "new_rules": [l.description[:60] for l in new_rules] if new_rules else [],
            }

            if promotions or demotions or kills:
                logger.info(
                    "Graduation sweep: %d promotions, %d demotions, %d kills",
                    promotions, demotions, kills,
                )

            return result

        except Exception as e:
            logger.warning("Graduation sweep failed: %s", e)
            return {"error": str(e)}

    # ── Implicit Feedback Detection (novel — neither Mem0 nor Letta has this)

    def detect_implicit_feedback(self, user_message: str, session: int = None) -> dict:
        """Detect implicit behavioral feedback in user prompts.

        The correction pipeline captures explicit draft→final edits. But most
        feedback is implicit: "are you sure?", "what about X?", "make sure you..."
        These signals indicate the AI missed something, forgot something, or
        needs behavioral adjustment.

        This is a novel signal source. No competitor captures it.

        Args:
            user_message: The user's raw prompt text.
            session: Session number (auto-detected if omitted).

        Returns:
            Dict with 'signals' (list of detected signal types),
            'has_feedback' (bool), and 'event' (if feedback was detected).
        """
        signals = []
        text = user_message.lower()

        # Pushback: user is correcting or disagreeing
        pushback_markers = [
            "are you sure", "that's wrong", "that's not right", "not accurate",
            "no, not that", "no don't", "stop doing", "why did you", "why didn't you",
        ]
        for marker in pushback_markers:
            if marker in text:
                signals.append({"type": "pushback", "marker": marker})

        # Reminder: user is repeating an instruction
        reminder_markers = [
            "make sure", "don't forget", "remember to", "you should always",
            "i already told", "i just said", "as i mentioned", "like i said",
        ]
        for marker in reminder_markers:
            if marker in text:
                signals.append({"type": "reminder", "marker": marker})

        # Gap: user is pointing out something missed
        gap_markers = [
            "what about", "you forgot", "you missed", "you skipped",
            "you ignored", "you dropped", "did you check", "did you verify",
        ]
        for marker in gap_markers:
            if marker in text:
                signals.append({"type": "gap", "marker": marker})

        # Challenge: user is questioning quality/completeness
        challenge_markers = [
            "are we sure", "is that right", "is that correct",
            "won't that", "won't people", "i feel like",
        ]
        for marker in challenge_markers:
            if marker in text:
                signals.append({"type": "challenge", "marker": marker})

        has_feedback = len(signals) > 0
        event = None

        if has_feedback:
            event = self.emit(
                "IMPLICIT_FEEDBACK", "brain.detect_implicit_feedback",
                {
                    "signals": [s["type"] for s in signals],
                    "markers": [s["marker"] for s in signals],
                    "snippet": user_message[:200],
                },
                tags=[f"signal:{s['type']}" for s in signals],
                session=session,
            )

        return {
            "signals": signals,
            "has_feedback": has_feedback,
            "event": event,
        }

    # ── Lessons path resolution ─────────────────────────────────────────

    def _find_lessons_path(self, create: bool = False) -> Path | None:
        """Find the lessons.md file, optionally creating it.

        Search order: brain_dir/lessons.md, parent/.claude/lessons.md.
        If create=True and neither exists, creates brain_dir/lessons.md.
        """
        candidates = [
            self.dir / "lessons.md",
            self.dir.parent / ".claude" / "lessons.md",
        ]
        for p in candidates:
            if p.is_file():
                return p
        if create:
            path = self.dir / "lessons.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
            return path
        return None

    # ── Briefing (portable context for any agent) ──────────────────────

    def briefing(self, output_dir: str | Path = ".") -> str:
        """Generate a brain briefing and return as markdown.

        The briefing is a single file any AI agent can consume:
        Claude Code, Cursor, Copilot, or any system prompt.

        Args:
            output_dir: Where to write export files (optional).

        Returns:
            Markdown string with rules, anti-patterns, corrections, health.
        """
        try:
            from gradata.enhancements.brain_briefing import generate_briefing
            b = generate_briefing(self)
            return b.to_markdown()
        except ImportError:
            return "# Brain Briefing\n\nBriefing module not available."

    def export_briefing(
        self,
        output_dir: str | Path = ".",
        formats: list[str] | None = None,
    ) -> dict:
        """Export briefing to agent-specific files.

        Writes to BRAIN-RULES.md, .cursorrules, copilot-instructions.md.

        Args:
            output_dir: Directory to write files to.
            formats: List of targets ("claude", "cursor", "copilot", "generic").
        """
        try:
            from gradata.enhancements.brain_briefing import export_briefing
            written = export_briefing(self, output_dir, formats)
            return {k: str(v) for k, v in written.items()}
        except ImportError:
            return {"error": "Briefing module not available."}

    # ── Git Backfill ─────────────────────────────────────────────────────

    def backfill_from_git(
        self,
        repo_path: str | Path = ".",
        lookback_days: int = 90,
        file_patterns: list[str] | None = None,
        max_commits: int = 500,
    ) -> dict:
        """Bootstrap this brain from git history.

        Walks git log, extracts before/after diffs, and feeds them as
        corrections. A new brain can start with months of learning.

        Args:
            repo_path: Path to the git repository.
            lookback_days: How far back to scan (default 90 days).
            file_patterns: Glob patterns to filter (default: py, md, ts, js, txt).
            max_commits: Max commits to process.

        Returns:
            Dict with backfill statistics.
        """
        try:
            from gradata.enhancements.git_backfill import backfill_from_git
            stats = backfill_from_git(
                brain=self,
                repo_path=repo_path,
                lookback_days=lookback_days,
                file_patterns=file_patterns,
                max_commits=max_commits,
            )
            return stats.to_dict()
        except ImportError:
            return {"error": "git_backfill module not available"}
        except Exception as e:
            logger.warning("Git backfill failed: %s", e)
            return {"error": str(e)}

    # ── Passive Memory Extraction (stolen from Mem0) ────────────────────

    def observe(self, messages: list[dict], user_id: str = "default") -> list[dict]:
        """Extract facts from a conversation without requiring corrections.

        Stolen from Mem0's passive extraction pipeline. Captures preferences,
        entities, relationships, and action items from any conversation.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            user_id: User identifier for scoped fact storage.

        Returns:
            List of reconcile action dicts (add/update/invalidate/skip).
        """
        try:
            try:
                from gradata_cloud.scoring.memory_extraction import MemoryExtractor
            except ImportError:
                from gradata.enhancements.memory_extraction import MemoryExtractor
        except ImportError:
            return []

        extractor = MemoryExtractor()
        candidates = extractor.extract(messages)

        if not candidates:
            return []

        # Get existing facts for reconciliation
        existing = self.get_facts()
        actions = extractor.reconcile(candidates, existing)

        # Execute actions
        results = []
        for action in actions:
            if action.op == "add":
                event = self.emit(
                    "FACT_EXTRACTED", "brain.observe",
                    {
                        "content": action.fact.content,
                        "fact_type": action.fact.fact_type,
                        "confidence": action.fact.confidence,
                        "source_role": action.fact.source_role,
                        "entities": action.fact.entities,
                        "user_id": user_id,
                    },
                )
                results.append({"op": "add", "fact": action.fact.content, "event": event})
            elif action.op == "invalidate":
                event = self.emit(
                    "FACT_INVALIDATED", "brain.observe",
                    {
                        "target_id": action.target_id,
                        "reason": action.reason,
                        "superseded_by": action.fact.content,
                        "user_id": user_id,
                    },
                )
                results.append({"op": "invalidate", "target": action.target_id, "event": event})
            elif action.op == "update":
                event = self.emit(
                    "FACT_UPDATED", "brain.observe",
                    {
                        "target_id": action.target_id,
                        "new_content": action.fact.content,
                        "user_id": user_id,
                    },
                )
                results.append({"op": "update", "target": action.target_id, "event": event})

        if results:
            logger.info("Observed %d facts from %d messages (%d actions)",
                       len(candidates), len(messages), len(results))

        return results

    # ── Cloud ──────────────────────────────────────────────────────────

    def connect_cloud(self, api_key: str = None, endpoint: str = None) -> "Brain":
        """Connect this brain to Gradata Cloud for server-side graduation.

        When connected, correct() and apply_brain_rules() route to the cloud
        API instead of running enhancements locally. The cloud runs the full
        graduation pipeline, meta-learning, and marketplace readiness scoring.

        Falls back to local mode if connection fails.

        Args:
            api_key: Gradata API key. If None, reads from GRADATA_API_KEY env var.
            endpoint: Cloud API endpoint. Defaults to https://api.gradata.com/v1.
        """
        try:
            from gradata.cloud import CloudClient
            self._cloud = CloudClient(
                brain_dir=self.dir,
                api_key=api_key,
                endpoint=endpoint,
            )
            self._cloud.connect()
        except ImportError:
            logger.warning("Cloud client not installed: pip install gradata[cloud]")
        except Exception as e:
            logger.warning("Cloud connection failed, using local mode: %s", e)
        return self

    @property
    def cloud_connected(self) -> bool:
        """True if this brain is connected to Gradata Cloud."""
        return self._cloud is not None and self._cloud.connected

    def __repr__(self):
        return f"Brain('{self.dir}')"


# Re-export the type alias so callers can annotate return values of brain.pipeline()
try:
    from gradata.patterns.pipeline import Pipeline
except ImportError:
    pass
