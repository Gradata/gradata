"""
Brain — Core SDK class for procedural memory.

A Brain is a directory containing:
  - system.db (SQLite event log, facts, metrics, embeddings)
  - lessons.md (graduated behavioral rules)
  - brain.manifest.json (machine-readable quality proof)
  - .embed-manifest.json (file hash tracking for delta embedding)

Usage:
    brain = Brain.init("./my-brain")           # Bootstrap a new brain
    brain = Brain("./my-brain")                # Open existing brain

    # Core learning loop
    brain.correct(draft="original", final="user-edited version")
    rules = brain.apply_brain_rules("write an email")

    # Search
    results = brain.search("common mistakes")

    # Events
    brain.emit("CORRECTION", "user", {"category": "TONE", "detail": "..."})
    events = brain.query_events(event_type="CORRECTION", last_n_sessions=3)

    # Quality proof
    manifest = brain.manifest()

    # Export
    brain.export("./exports/my-brain.zip")

Note: Brain is NOT thread-safe. Each Brain instance uses SQLite which
does not support concurrent writes from multiple threads. Use one Brain
per process, or use process-level locks for multi-worker deployments.
"""

from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from gradata._types import Lesson

logger = logging.getLogger("gradata")


import contextlib

from gradata._env import env_str
from gradata.brain_inspection import BrainInspectionMixin


class Brain(BrainInspectionMixin):
    """A personal AI brain backed by a directory of knowledge files."""

    def __init__(
        self,
        brain_dir: str | Path | None = None,
        working_dir: str | Path | None = None,
        encryption_key: str | None = None,
    ):
        from gradata._paths import resolve_brain_dir

        self.dir = resolve_brain_dir(brain_dir)
        if not self.dir.exists():
            from gradata.exceptions import BrainNotFoundError

            raise BrainNotFoundError(f"Brain directory not found: {self.dir}")

        self.db_path = self.dir / "system.db"
        self.manifest_path = self.dir / "brain.manifest.json"
        self.embed_manifest_path = self.dir / ".embed-manifest.json"

        # Encryption at rest (optional: pip install gradata[encrypted])
        self._encryption_key = None
        if encryption_key or env_str("GRADATA_ENCRYPTION_KEY"):
            from gradata._encryption import open_encrypted_db, resolve_encryption_key

            self._encryption_key = resolve_encryption_key(encryption_key)
            if self._encryption_key:
                open_encrypted_db(self.dir, self._encryption_key)

        self._instruction_cache: object | None = None  # lazy: InstructionCache
        self._fired_rules: list[
            Lesson
        ] = []  # Rules injected this session (for misfire attribution)
        self._convergence_cache: dict | None = None
        self._convergence_session: int | None = None

        # Rule cache (Pattern 2: session-scoped, invalidated on correct())
        from gradata.rules.cache import RuleCache

        self._rule_cache = RuleCache()

        # Capability probe cached once: apply_brain_rules() is a hot path
        # and we don't want find_spec() in every call.
        import importlib.util as _util

        self._has_self_improvement = (
            _util.find_spec("gradata.enhancements.self_improvement") is not None
        )

        from gradata.rules.rule_graph import RuleGraph

        self._rule_graph = RuleGraph(self.dir / "rule_graph.json")

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

        # JSONL is canonical; SQLite is a query projection. A process can die
        # after append+fsync and before SQLite commit, so every open heals any
        # projection lag before readers query the events table.
        try:
            from gradata._events import reconcile_jsonl_to_sqlite

            reconcile_jsonl_to_sqlite(ctx=self.ctx)
        except Exception as exc:
            logger.debug("event projection reconcile failed: %s", exc)

        # Initialize pattern registries (lazy — ImportError safe)
        try:
            from gradata.enhancements.behavioral_engine import DirectiveRegistry

            self.contracts = DirectiveRegistry()
        except ImportError:
            self.contracts = None  # type: ignore[assignment]
        try:
            from gradata.contrib.patterns.tools import ToolRegistry

            self.tools = ToolRegistry()
        except ImportError:
            self.tools = None  # type: ignore[assignment]
        self.agent_graduation = None  # Future: agent-level graduation tracking

        # Procedural memory pipeline (observe→cluster→discriminate→route→bracket)
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
                except Exception as e:
                    logger.debug("Router warm-start failed: %s", e)
        except ImportError:
            pass

        # Bootstrap RuleContext — makes graduated rules available to all patterns
        try:
            from gradata.enhancements.rule_context_bridge import bootstrap_rule_context

            lessons_path = self._find_lessons_path()
            bootstrap_rule_context(
                lessons_path=lessons_path,
                db_path=self.db_path,
            )
        except ImportError:
            pass  # Bridge not available (minimal install)

        # Event bus for reactive nervous system
        from gradata.events_bus import EventBus

        self.bus = EventBus()

        # Register built-in nervous system subscribers (lazy, never block init)
        try:
            from gradata.services.embeddings import subscribe_to_bus as _embed_sub

            _embed_sub(self.bus)
        except ImportError:
            pass
        try:
            from gradata.services.session_history import SessionHistory as _SH

            self._session_history = _SH()
            self._session_history.subscribe_to_bus(self.bus)
        except ImportError:
            pass

        # Query budget — sliding-window rate limiter
        from gradata.security.query_budget import QueryBudget

        self._query_budget = QueryBudget()

        # Cloud connection (None = local-only mode)
        self._cloud = None

        # Per-brain salt for non-deterministic graduation thresholds
        from gradata.security.brain_salt import load_or_create_salt

        self._brain_salt = load_or_create_salt(self.dir)

    @property
    def session(self) -> int:
        """Current session number (from event log)."""
        try:
            from gradata._events import get_current_session

            return get_current_session()
        except Exception as exc:
            logger.debug("get_current_session failed: %s", exc)
            return 0

    @classmethod
    def init(
        cls,
        brain_dir: str | Path,
        *,
        domain: str | None = None,
        name: str | None = None,
        company: str | None = None,
        embedding: str | None = None,
        interactive: bool | None = None,
    ) -> Brain:
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
            # If caller provided key args, skip the wizard
            has_args = any(v is not None for v in (name, domain, company, embedding))
            interactive = not has_args and hasattr(sys, "stdin") and sys.stdin.isatty()

        return onboard(
            brain_dir,
            name=name,
            domain=domain,
            company=company,
            embedding=embedding,
            interactive=interactive,
        )

    # ── Credit Budgets (daily API spend limits) ──────────────────────────

    def _budget_op(self, fn_name: str, *args):
        """Run a budget operation with connection management."""
        from gradata import _db

        conn = _db.get_connection(self.db_path)
        _db.ensure_credit_budgets(conn)
        try:
            return getattr(_db, fn_name)(conn, *args)
        finally:
            conn.close()

    def check_budget(self, api_name: str, count: int = 1) -> dict:
        """Check if an API call is within daily budget."""
        return self._budget_op("check_budget", api_name, count)

    def spend_budget(self, api_name: str, count: int = 1) -> dict:
        """Record API usage against the daily budget."""
        return self._budget_op("spend_budget", api_name, count)

    def budget_summary(self) -> list[dict]:
        """Return all budget rows for morning brief reporting."""
        return self._budget_op("budget_summary")

    # ── Lessons path resolution ─────────────────────────────────────────

    def _find_lessons_path(self, create: bool = False) -> Path | None:
        """Find lessons.md: env var → brain_dir → parent/.claude → working_dir/.claude."""
        import os

        env_path = os.environ.get("BRAIN_LESSONS_PATH", "")
        if env_path and Path(env_path).is_file():
            return Path(env_path)

        brain_local = self.dir / "lessons.md"
        if brain_local.is_file():
            return brain_local

        # Fallback: external project paths (read-only — never write here)
        for p in (
            self.dir.parent / ".claude" / "lessons.md",
            self.ctx.working_dir / ".claude" / "lessons.md",
        ):
            if p.is_file():
                if not create:
                    return p
                break  # Found external but create=True → fall through to create local

        if create:
            brain_local.parent.mkdir(parents=True, exist_ok=True)
            brain_local.write_text("", encoding="utf-8")
            return brain_local
        return None

    def _load_lessons(self, create: bool = False):
        """Load and parse lessons from lessons.md. Returns list or empty list.

        Caches the parsed result keyed on (path, mtime) so repeated reads in
        the same session skip the parse when the file is unchanged. Writer
        paths that re-parse + mutate + rewrite should call ``parse_lessons``
        directly (see forget/disable_lesson/add_rule) to avoid sharing
        mutable state with the cache.
        """
        from gradata.enhancements.self_improvement import parse_lessons

        path = self._find_lessons_path(create=create)
        if not path or not path.is_file():
            self._lessons_parse_cache = None
            return []
        mtime = path.stat().st_mtime
        key = (str(path), mtime)
        cache = getattr(self, "_lessons_parse_cache", None)
        if cache is not None and cache[0] == key:
            return cache[1]
        lessons = parse_lessons(path.read_text(encoding="utf-8"))
        self._lessons_parse_cache = (key, lessons)
        return lessons

    @property
    def memory(self):
        """Access the MemoryManager for this brain.

        Provides store/retrieve/update/delete/decay across episodic,
        semantic, and procedural memory types.

        Usage:
            brain.memory.store("semantic", "API uses gRPC")
            brain.memory.store("episodic", "Sent proposal to Acme")
            results = brain.memory.retrieve("API patterns")
        """
        if not hasattr(self, "_memory_manager"):
            from gradata.contrib.patterns.memory import MemoryManager

            self._memory_manager = MemoryManager()
        return self._memory_manager

    def close(self):
        """Cleanup: re-encrypt database if encryption is enabled."""
        if self._encryption_key:
            from gradata._encryption import close_encrypted_db

            close_encrypted_db(self.dir, self._encryption_key)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __repr__(self):
        return f"Brain('{self.dir}')"

    # ── Core Learning Loop (heavy methods delegated to _core.py) ───────

    def correct(
        self,
        draft: str,
        final: str,
        category: str | None = None,
        context: dict | None = None,
        session: int | None = None,
        agent_type: str | None = None,
        approval_required: bool = False,
        dry_run: bool = False,
        min_severity: str = "as-is",
        scope: str | None = None,
        applies_to: str | None = None,
        auto_heal: bool = False,
    ) -> dict:
        """Record a correction: user edited draft into final version.

        ``applies_to`` is an optional free-form scope token (e.g.
        ``"client:acme"``, ``"task:emails"``, ``"global"``) that binds the
        correction to a specific context. When set, it is persisted on the
        event and propagated to any lesson that graduates from this
        correction's lineage. Injection-time filtering by ``applies_to``
        is a follow-up, persistence only for now. A ``None`` value preserves
        the existing global behaviour.

        ``auto_heal`` controls whether detected RULE_FAILURE events trigger
        automatic patching via the self-healing loop. Defaults to ``False``
        (silent detection only). Set to ``True`` to apply patches inline; each
        patch returns a ``PatchReceipt`` and emits a stderr line. Auto-heal is
        also skipped when ``dry_run=True``, ``approval_required=True``, or
        when the brain is in renter mode.
        """
        self._rule_cache.invalidate()  # Correction invalidates cached rules
        from gradata._core import brain_correct

        result = brain_correct(
            self,
            draft,
            final,
            category=category,
            context=context,
            session=session,
            agent_type=agent_type,
            approval_required=approval_required,
            dry_run=dry_run,
            min_severity=min_severity,
            scope=scope,
            applies_to=applies_to,
            auto_heal=auto_heal,
        )

        # Activation telemetry — fires once per machine, only if opted in.
        # Guarded so a telemetry bug can never break the learning loop.
        try:
            from gradata import _telemetry

            _telemetry.send_once("first_correction_captured")
            # If this correction produced a graduation, mark it too. The
            # result dict contains a 'graduated' list on the happy path;
            # be defensive in case the schema changes.
            if not dry_run and result and result.get("graduated"):
                _telemetry.send_once("first_graduation")
        except Exception as e:
            logger.debug("telemetry send_once failed: %s", e)

        return result

    def record_correction(
        self,
        text: str,
        *,
        assistant_draft: str | None = None,
        category: str = "GENERAL",
        **extras,
    ) -> dict:
        """Record a user correction as a CORRECTION event.

        Lightweight companion to :meth:`correct` — does not run the diff /
        classification pipeline; simply persists the raw correction signal
        plus the assistant draft that triggered it (under ``draft_text``)
        so downstream tooling (e.g. rule-to-hook graduation) can replay
        generated hooks against the ground-truth violating text.

        Args:
            text: The user's correction message (what they wrote).
            assistant_draft: The AI output the user was correcting. Stored
                under ``data['draft_text']`` when provided.
            category: Correction category (defaults to ``"GENERAL"``).
            **extras: Any additional fields to merge into the event's
                ``data`` dict.

        Returns:
            The emitted CORRECTION event dict.
        """
        # Apply extras first, then explicit fields so callers can't override
        # the primary signals (detail/category/draft_text) via **extras.
        data: dict = dict(extras)
        data["detail"] = text
        data["category"] = category
        if assistant_draft is not None:
            data["draft_text"] = assistant_draft
        return self.emit("CORRECTION", "user", data, [f"category:{category}"])

    def patch_rule(
        self, category: str, old_description: str, new_description: str, reason: str = ""
    ) -> dict:
        """Rewrite a rule's description. Preserves confidence/metadata. Emits RULE_PATCHED event."""
        from gradata._db import write_lessons_safe
        from gradata.enhancements.self_healing import apply_patch
        from gradata.enhancements.self_improvement import format_lessons, parse_lessons

        # Only patch the brain-local lessons file — never external fallbacks
        lessons_path = self.dir / "lessons.md"
        if not lessons_path.is_file():
            return {"patched": False, "error": "not_found: no brain-local lessons file"}

        lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
        patched = apply_patch(lessons, category, old_description, new_description)

        if not patched:
            return {"patched": False, "error": f"not_found: no rule matching category={category!r}"}

        write_lessons_safe(lessons_path, format_lessons(lessons))

        # lessons.md just changed; invalidate caches so readers don't serve
        # a pre-patch copy until the next auto_heal() flush.
        self._lessons_parse_cache = None
        with contextlib.suppress(Exception):
            self._rule_cache.invalidate()

        # Re-sign the patched rule so HMAC verification stays valid
        try:
            from gradata.enhancements.rule_integrity import sign_and_store

            sign_and_store(self.ctx, new_description, category, patched.confidence)
        except ImportError:
            pass  # unsigned mode — no-op

        self.emit(
            "RULE_PATCHED",
            "brain.patch_rule",
            {
                "category": category,
                "old_description": old_description[:200],
                "new_description": new_description[:200],
                "reason": reason,
                "confidence_preserved": patched.confidence,
            },
            [f"category:{category}", "self_healing"],
        )

        return {
            "patched": True,
            "old_description": old_description,
            "new_description": new_description,
            "confidence_preserved": patched.confidence,
        }

    def auto_heal(
        self,
        failure_events: list[dict] | None = None,
        *,
        max_patches: int = 5,
    ) -> dict:
        """Close the self-healing loop for recent RULE_FAILURE events.

        Reads recent RULE_FAILURE events, generates deterministic patch
        candidates, gates them through ``retroactive_test``, and applies
        the survivors via ``self.patch_rule``. Emits ``RULE_PATCHED``
        events for each successful patch.

        Args:
            failure_events: Optional list of RULE_FAILURE events. When
                omitted, reads the most recent events from the brain's
                log.
            max_patches: Hard cap on patches applied per call
                (default 5).

        Returns:
            Summary dict with ``examined``, ``patched``, ``skipped``,
            ``patches`` (applied), and ``skipped_reasons``.
        """
        from gradata.enhancements.self_healing import auto_heal_failures

        result = auto_heal_failures(self, failure_events=failure_events, max_patches=max_patches)
        # Patching rewrites lessons.md; invalidate the in-memory rule cache
        # so subsequent apply_brain_rules() calls see the patched text
        # instead of a stale pre-patch prompt.
        if result.get("patched"):
            with contextlib.suppress(Exception):  # pragma: no cover -- defensive
                self._rule_cache.invalidate()
        return result

    def add_rule(
        self,
        description: str,
        category: str,
        state: str = "RULE",
        confidence: float = 0.90,
        data: dict | None = None,
    ) -> dict:
        """Add a rule to lessons.md via the canonical parse/format pipeline.

        This is the programmatic entry point for fast-tracking user-declared
        rules. Unlike hand-formatting a ``[date] [STATE:conf] CATEGORY: desc``
        line directly, this method routes through :func:`parse_lessons` /
        :func:`format_lessons` (the same code path graduation uses), so any
        future schema change auto-propagates to callers like ``gradata rule
        add``.

        Args:
            description: The rule's human-readable text (must be non-empty).
            category: Rule category (e.g. ``"USER"``, ``"DRAFTING"``). Must
                be non-empty — this matches how graduation classifies rules.
            state: Lesson state name. Defaults to ``"RULE"``. Accepts any
                member of :class:`LessonState` (e.g. ``"INSTINCT"``,
                ``"PATTERN"``, ``"RULE"``). Case-insensitive.
            confidence: Confidence score in ``[0.0, 1.0]``. Values outside
                the range are clamped (same as :class:`Lesson.__post_init__`).
                Defaults to ``0.90`` (the RULE-tier threshold).
            data: Optional dict with extra lesson fields (e.g.
                ``{"root_cause": "...", "agent_type": "researcher"}``). Only
                known :class:`Lesson` fields are applied; unknown keys are
                ignored silently.

        Returns:
            Dict with ``added`` (bool), ``category``, ``description``, and
            ``confidence`` (post-clamp). On error: ``added=False`` + ``reason``.

        Example:
            >>> brain.add_rule("Use colons not em-dashes", "DRAFTING")
            {'added': True, 'category': 'DRAFTING', ...}
        """
        from datetime import date

        from gradata._db import lessons_lock
        from gradata._types import Lesson, LessonState
        from gradata.enhancements.self_improvement import format_lessons, parse_lessons

        description = (description or "").strip()
        # Canonicalize category casing so callers passing "drafting" and
        # "DRAFTING" don't create duplicate logical buckets (parse_lessons
        # preserves whatever casing is on disk, so we pick one form — upper —
        # at the add_rule boundary). Must match the form used by duplicate
        # comparisons, persistence, and the emit() tag below.
        category = (category or "").strip().upper()

        if not description:
            return {"added": False, "reason": "empty_description"}
        if not category:
            return {"added": False, "reason": "empty_category"}

        # Resolve LessonState (case-insensitive, fallback to RULE on unknown)
        state_upper = str(state or "RULE").upper()
        try:
            lesson_state = LessonState[state_upper]
        except KeyError:
            return {"added": False, "reason": f"unknown_state: {state!r}"}

        # Clamp confidence (Lesson.__post_init__ does this too, but we want
        # to report the clamped value in the return dict)
        try:
            conf = float(confidence)
        except (TypeError, ValueError):
            return {"added": False, "reason": f"invalid_confidence: {confidence!r}"}
        conf = round(max(0.0, min(1.0, conf)), 2)

        lessons_path = self._find_lessons_path(create=True)
        if lessons_path is None:  # pragma: no cover — create=True always returns
            return {"added": False, "reason": "no_lessons_file"}

        # Duplicate check: same canonical category + normalized description
        def _norm(s: str) -> str:
            return " ".join(s.split()).lower()

        desc_norm = _norm(description)

        # Build the new Lesson (cheap, no I/O) before locking so we hold the
        # critical section as briefly as possible.
        lesson = Lesson(
            date=date.today().isoformat(),
            state=lesson_state,
            confidence=conf,
            category=category,
            description=description,
        )
        if data:
            field_names = set(Lesson.__dataclass_fields__.keys())  # type: ignore[attr-defined]
            # Don't let callers override the primary fields (date/state/conf/
            # category/description) via data — those come from explicit args.
            protected = {"date", "state", "confidence", "category", "description"}
            for k, v in data.items():
                if k in field_names and k not in protected:
                    setattr(lesson, k, v)

        # TOCTOU protection: hold the same lock write_lessons_safe uses for
        # the entire read → duplicate-check → append → write sequence so
        # concurrent add_rule calls can't both observe "no duplicate" and
        # then each append the same lesson.
        with lessons_lock(lessons_path):
            existing = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            for l in existing:
                # l.category may have arbitrary casing (parse_lessons preserves
                # on-disk form); compare case-insensitively against the canonical
                # upper-cased `category` we're inserting.
                if (l.category or "").strip().upper() == category and _norm(
                    l.description
                ) == desc_norm:
                    return {
                        "added": False,
                        "reason": "duplicate",
                        "category": category,
                        "description": description,
                    }
            existing.append(lesson)
            # Write inside the lock — reuse the same serializer but call the
            # raw writer directly since we already hold the lock.
            lessons_path.write_text(format_lessons(existing), encoding="utf-8")

        # Best-effort event log — never fail the add if event emission fails
        try:
            self.emit(
                "LESSON_ADDED",
                "brain.add_rule",
                {
                    "category": category,
                    "description": description[:200],
                    "state": lesson_state.value,
                    "confidence": conf,
                },
                [f"category:{category}", f"state:{lesson_state.value}"],
            )
        except Exception as e:  # pragma: no cover — defensive
            logger.debug("add_rule event emit failed: %s", e)

        return {
            "added": True,
            "category": category,
            "description": description,
            "state": lesson_state.value,
            "confidence": conf,
        }

    def end_session(
        self,
        session_corrections: list[dict] | None = None,
        session_type: str = "full",
        machine_mode: bool | None = None,
        skip_meta_rules: bool = False,
    ) -> dict:
        """Run full graduation sweep at end of session."""
        from gradata._core import brain_end_session

        return brain_end_session(
            self,
            session_corrections=session_corrections,
            session_type=session_type,
            machine_mode=machine_mode,
            skip_meta_rules=skip_meta_rules,
        )

    def auto_evolve(
        self,
        output: str,
        task: str = "",
        agent_type: str = "",
        evaluator=None,
        dimensions=None,
        threshold: float = 7.0,
    ) -> dict:
        """Evaluate output and auto-generate corrections for failed dimensions."""
        from gradata._core import brain_auto_evolve

        return brain_auto_evolve(
            self,
            output,
            task=task,
            agent_type=agent_type,
            evaluator=evaluator,
            dimensions=dimensions,
            threshold=threshold,
        )

    def detect_implicit_feedback(self, user_message: str, session: int | None = None) -> dict:
        """Detect implicit behavioral feedback in user prompts."""
        from gradata._core import brain_detect_implicit_feedback

        return brain_detect_implicit_feedback(self, user_message, session=session)

    def convergence(self) -> dict:
        """Get corrections-per-session convergence data."""
        from gradata._core import brain_convergence

        return brain_convergence(self)

    def _get_convergence(self) -> dict:
        """Get cached convergence data (one DB query per session)."""
        if self._convergence_cache is not None and self._convergence_session == self.session:
            return self._convergence_cache
        from gradata._core import brain_convergence

        self._convergence_cache = brain_convergence(self)
        self._convergence_session = self.session
        return self._convergence_cache

    def efficiency(self, *, estimate_time: bool = False) -> dict:
        """Quantify effort saved by brain learning.

        Returns effort_ratio (ratio of current vs initial correction rate).
        Pass estimate_time=True for approximate time-saved estimates.
        """
        from gradata._core import brain_efficiency

        return brain_efficiency(self, estimate_time=estimate_time)

    def prove(self) -> dict:
        """Generate statistical proof that this brain improves output quality.

        Returns a proof document showing whether and how strongly the brain
        has learned from corrections. Used for marketplace trust verification.
        """
        from gradata._core import brain_prove

        return brain_prove(self)

    def share(self) -> dict:
        """Export graduated rules as a shareable package for team distribution.

        Only includes PATTERN and RULE state lessons — proven behavioral
        rules that have survived the graduation pipeline.
        """
        from gradata._core import brain_share

        return brain_share(self)

    def absorb(self, package: dict) -> dict:
        """Import shared rules from another brain's share() output.

        Rules enter as INSTINCT — this brain must validate them through
        its own correction cycle before they graduate.
        """
        from gradata._core import brain_absorb

        return brain_absorb(self, package)

    # ── Output Logging ─────────────────────────────────────────────────

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
        """Log an AI-generated output for tracking."""
        data = {
            "output_type": output_type,
            "output_text": text[:5000],
            "outcome": "pending",
            "major_edit": False,
            "rules_applied": rules_applied or [],
        }
        if prompt is not None:
            data["prompt"] = prompt[:2000]
        if self_score is not None:
            data["self_score"] = self_score
        if scope is not None:
            data["scope"] = scope
        return self.emit(
            "OUTPUT", "brain.log_output", data, [f"output:{output_type}"], session or 0
        )

    # ── Rules ──────────────────────────────────────────────────────────

    def apply_brain_rules(
        self,
        task: str,
        context: dict | None = None,
        agent_type: str | None = None,
        max_rules: int | None = None,
        max_recall_tokens: int | None = None,
        ranker: str | None = None,
    ) -> str:
        """Get applicable brain rules for a task, formatted for prompt injection."""
        from gradata._config import _load_brain_config

        cfg = _load_brain_config(self.dir)
        if max_rules is None:
            max_rules = 10
        if max_recall_tokens is None:
            max_recall_tokens = cfg.max_recall_tokens
        if ranker is None:
            ranker = cfg.ranker

        self._query_budget.record("apply_rules")
        if self._query_budget.is_rate_exceeded("apply_rules"):
            logger.warning("Query budget exceeded for apply_rules")
            return ""  # enforce: block injection when budget exhausted
        # SECURITY: Never pull rules from cloud. Cloud is a read-only dashboard.
        # Rules are always computed locally from the brain's own lessons.
        # Pulling rules from cloud would allow a compromised server to inject
        # malicious instructions into AI prompts → remote code execution.
        # Capability check: enhancements package must be installed for rules.
        import importlib.util as _util

        if _util.find_spec("gradata.enhancements.self_improvement") is None:
            return ""
        from gradata._scope import build_scope
        from gradata.rules.rule_engine import apply_rules, format_rules_for_prompt

        ctx = dict(context or {})
        ctx.setdefault("task", task)
        if agent_type:
            ctx.setdefault("agent_type", agent_type)
        lessons_path = self._find_lessons_path()
        if not lessons_path:
            return ""
        scope = build_scope(ctx)

        # Check rule cache first (Pattern 2: skip re-ranking if scope unchanged)
        from gradata.rules.cache import RuleCache

        cache_key = RuleCache.make_key(
            f"{scope.task_type}:{ranker}:{max_recall_tokens}:{max_rules}",
            scope.domain,
            scope.audience,
        )
        cached = self._rule_cache.get(cache_key)
        if cached is not None:
            return cached

        # mtime-cached parse: reuses prior result when lessons.md is unchanged.
        lessons = self._load_lessons()

        # Try tree-based retrieval first (falls back to flat if no paths).
        # Pass the brain's bus so rule_engine can fire `rule_scoped_out`
        # events for observers (notifications, session-history, embeddings).
        _bus = getattr(self, "bus", None)
        try:
            from gradata.rules.rule_engine import apply_rules_with_tree

            applied = apply_rules_with_tree(
                lessons,
                scope,
                max_rules=max_rules,
                ranker=ranker,
                event_bus=_bus,
            )
        except (ImportError, Exception):
            applied = apply_rules(lessons, scope, max_rules=max_rules, bus=_bus)

        # Emit `rules.injected` so downstream effectiveness tracking
        # (SessionHistory.compute_effectiveness) sees what entered this
        # session's prompts. Fire-and-forget — never fails apply_brain_rules.
        if _bus is not None and applied:
            try:
                _bus.emit(
                    "rules.injected",
                    {
                        "rules": [
                            {
                                "id": a.rule_id,
                                "category": a.lesson.category,
                                "confidence": a.lesson.confidence,
                                "state": a.lesson.state.value,
                            }
                            for a in applied
                        ],
                        "scope": {
                            "task_type": scope.task_type,
                            "domain": scope.domain,
                            "audience": scope.audience,
                        },
                        "task": task,
                    },
                )
            except Exception as e:
                logger.debug("rules.injected emit failed: %s", e)

        result = format_rules_for_prompt(applied)
        if max_recall_tokens > 0 and result:
            budget_chars = max_recall_tokens * 4
            if len(result) > budget_chars:
                result = result[:budget_chars].rstrip()
                if not result.endswith("</brain-rules>"):
                    last_tag_boundary = result.rfind(">")
                    if last_tag_boundary >= 0:
                        result = result[: last_tag_boundary + 1].rstrip()
                    else:
                        result = "<brain-rules>"
                    result = f"{result}\n</brain-rules>"
        self._rule_cache.put(cache_key, result)
        return result

    def scoped_rules(
        self, domain: str = "", task_type: str = "", agent_type: str = "", max_rules: int = 10
    ) -> str:
        """Get brain rules scoped to a specific domain and task type, as a string.

        Convenience wrapper around :meth:`apply_brain_rules` that builds the
        context dict from named parameters. For an object-oriented view that
        exposes ``rules()``, ``inject()``, and scoped ``correct()``, see
        :meth:`scope`.

        Args:
            domain: Operational domain, e.g. ``"sales"``, ``"engineering"``.
            task_type: Task kind, e.g. ``"email_draft"``, ``"code_review"``.
            agent_type: Agent role for scoped injection, e.g. ``"researcher"``.
            max_rules: Maximum number of rules to return (default 10).

        Returns:
            Formatted rule string for prompt injection, or ``""`` if no rules
            match or the brain has no graduated lessons.
        """
        context: dict = {}
        if domain:
            context["domain"] = domain
        if task_type:
            context["task_type"] = task_type
        return self.apply_brain_rules(
            task=f"{domain} {task_type}".strip() or "general",
            context=context,
            agent_type=agent_type or None,
            max_rules=max_rules,
        )

    def scope(self, domain: str):
        """Return a :class:`ScopedBrain` view over this brain.

        A ScopedBrain filters graduated rules to those tagged with ``domain``
        (via ``scope_json.domain``, ``scope_json.applies_to`` starting with
        ``"{domain}:"``, or a matching category) and proxies writes (correct,
        emit) through to this brain so learning still accrues to one store.

        Args:
            domain: Non-empty domain string, e.g. ``"code"``, ``"sales"``.

        Returns:
            A :class:`gradata._scoped_brain.ScopedBrain` bound to this brain.

        Example::

            code_brain = brain.scope("code")
            prompt = code_brain.inject("refactor the parser")
            code_brain.correct("old draft", "new draft")  # tagged applies_to="code"
        """
        from gradata._scoped_brain import ScopedBrain

        return ScopedBrain(self, domain)

    def plan(self, task: str, context: dict | None = None) -> dict:
        """Generate a structured plan using graduated rules."""
        rules_text = self.apply_brain_rules(task, context)
        rules_list = [
            l.strip("- ").strip() for l in rules_text.split("\n") if l.strip().startswith("-")
        ]
        steps = []
        if rules_list:
            steps.append({"step": 1, "action": "Review applicable rules", "rules": rules_list})
        steps.append({"step": len(steps) + 1, "action": f"Execute: {task}", "rules": []})
        steps.append(
            {"step": len(steps) + 1, "action": "Self-check against rules", "rules": rules_list}
        )
        return {
            "task": task,
            "steps": steps,
            "rules_count": len(rules_list),
            "context": context or {},
        }

    # ── Lesson Management ──────────────────────────────────────────────

    def forget(self, what: str = "last") -> dict | list[dict]:
        """Human-friendly way to undo lessons.

        Examples:
            brain.forget("last")           # most recent lesson
            brain.forget("last 3")         # last 3 lessons
            brain.forget("casual tone")    # fuzzy match description
            brain.forget("all tone")       # everything in TONE category
        """
        try:
            from gradata.enhancements.self_improvement import format_lessons, parse_lessons
        except ImportError:
            return {"rolled_back": False, "error": "enhancements not installed"}
        from gradata._db import write_lessons_safe
        from gradata._types import LessonState

        lessons_path = self._find_lessons_path()
        if not lessons_path or not lessons_path.is_file():
            return {"rolled_back": False, "error": "no lessons file"}
        lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))

        what = what.strip()
        wl = what.lower()

        # Resolve target indices
        active = [
            (i, l)
            for i, l in enumerate(lessons)
            if l.state in (LessonState.INSTINCT, LessonState.PATTERN, LessonState.RULE)
        ]
        targets: list[int] = []

        if wl == "last" or wl.startswith("last "):
            parts = wl.split()
            n = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 1
            if not active:
                return {"rolled_back": False, "error": "no active lessons"}
            targets = [i for i, _ in active[-n:]]

        elif wl.startswith("all "):
            cat = what[4:].strip()
            targets = [i for i, l in active if l.category.upper() == cat.upper()]
            if not targets:
                return {"rolled_back": False, "error": f"no active lessons in '{cat}'"}

        else:
            # Fuzzy match on description — single target
            return self.rollback(description=what)

        # Batch kill: mutate in memory, write once
        results = []
        for idx in targets:
            lesson = lessons[idx]
            old_state, old_conf = lesson.state.value, lesson.confidence
            lesson.state, lesson.confidence = LessonState.KILLED, 0.0
            results.append(
                {
                    "rolled_back": True,
                    "lesson_index": idx,
                    "category": lesson.category,
                    "description": lesson.description,
                    "previous_state": old_state,
                    "previous_confidence": old_conf,
                }
            )
        write_lessons_safe(lessons_path, format_lessons(lessons))

        # lessons.md changed — evict mtime cache + formatted-rule cache so the
        # next apply_brain_rules() call reflects the forget.
        self._lessons_parse_cache = None
        with contextlib.suppress(Exception):
            self._rule_cache.invalidate()

        for r in results:
            with contextlib.suppress(Exception):
                self.emit(
                    "LESSON_CHANGE",
                    "brain.forget",
                    {
                        "action": "rolled_back",
                        "lesson_index": r["lesson_index"],
                        "lesson_category": r["category"],
                        "lesson_description": r["description"][:200],
                        "previous_state": r["previous_state"],
                        "previous_confidence": r["previous_confidence"],
                        "kill_reason": "manual_forget",
                    },
                    [f"category:{r['category']}", "rollback"],
                    0,
                )

        return results[0] if len(results) == 1 else results

    def rollback(
        self,
        lesson_id: int | None = None,
        description: str | None = None,
        category: str | None = None,
    ) -> dict:
        """Disable a specific lesson by setting its state to KILLED."""
        try:
            from gradata.enhancements.self_improvement import format_lessons, parse_lessons
        except ImportError:
            return {"rolled_back": False, "error": "enhancements not installed"}
        from gradata._types import LessonState

        lessons_path = self._find_lessons_path()
        if not lessons_path or not lessons_path.is_file():
            return {"rolled_back": False, "error": "no lessons file"}
        lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
        target, target_idx = None, None
        if lesson_id is not None and 0 <= lesson_id < len(lessons):
            target, target_idx = lessons[lesson_id], lesson_id
        elif description:
            for i, l in enumerate(lessons):
                if description.lower() in l.description.lower():
                    target, target_idx = l, i
                    break
        elif category:
            for i, l in enumerate(lessons):
                if l.category.upper() == category.upper() and l.state not in (
                    LessonState.KILLED,
                    LessonState.ARCHIVED,
                ):
                    target, target_idx = l, i
                    break
        if target is None:
            return {"rolled_back": False, "error": "lesson not found"}
        old_state, old_conf = target.state.value, target.confidence
        target.state, target.confidence = LessonState.KILLED, 0.0
        from gradata._db import write_lessons_safe

        write_lessons_safe(lessons_path, format_lessons(lessons))
        # lessons.md changed — evict caches so readers see the kill immediately.
        self._lessons_parse_cache = None
        with contextlib.suppress(Exception):
            self._rule_cache.invalidate()
        try:
            self.emit(
                "LESSON_CHANGE",
                "brain.rollback",
                {
                    "action": "rolled_back",
                    "lesson_index": target_idx,
                    "lesson_category": target.category,
                    "lesson_description": target.description[:200],
                    "previous_state": old_state,
                    "previous_confidence": old_conf,
                    "kill_reason": "manual_rollback",
                },
                [f"category:{target.category}", "rollback"],
                0,
            )
        except Exception as e:
            logger.debug("Rollback event emit failed: %s", e)
        return {
            "rolled_back": True,
            "lesson_index": target_idx,
            "category": target.category,
            "description": target.description,
            "previous_state": old_state,
            "previous_confidence": old_conf,
        }

    def lineage(self, category: str | None = None, limit: int = 50) -> list[dict]:
        """Query lesson state transition history."""
        if not self.db_path.is_file():
            return []
        import sqlite3

        from gradata._db import get_connection

        try:
            with contextlib.closing(get_connection(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                if category:
                    rows = conn.execute(
                        "SELECT * FROM lesson_transitions WHERE category = ? "
                        "ORDER BY transitioned_at DESC LIMIT ?",
                        (category.upper(), limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM lesson_transitions ORDER BY transitioned_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    # ── Human-in-the-Loop Approval ──────────────────────────────────

    def _resolve_pending(self, approval_id: int, resolution: str, mutator) -> dict:
        """Shared logic for approve/reject: look up pending, mutate lesson, resolve."""
        import sqlite3

        from gradata._db import get_connection, lessons_lock
        from gradata.enhancements.self_improvement import format_lessons, parse_lessons

        # Open conn only to read the pending row, then close before taking the
        # file lock. Holding a SQLite connection across a potentially-blocking
        # file-lock section kept a WAL reader slot idle under contention.
        with contextlib.closing(get_connection(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM pending_approvals WHERE id = ? AND resolution IS NULL",
                (approval_id,),
            ).fetchone()
        if not row:
            return {"resolved": False, "reason": "not_found_or_already_resolved"}
        cat, desc = row["lesson_category"], row["lesson_description"]

        lessons_path = self._find_lessons_path()
        if not lessons_path or not lessons_path.is_file():
            return {"resolved": False, "reason": "no_lessons_file"}

        with lessons_lock(lessons_path):
            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            matched = False
            for lesson in lessons:
                if (
                    lesson.category == cat
                    and lesson.description[:100] == desc[:100]
                    and lesson.pending_approval
                ):
                    mutator(lesson)
                    matched = True
                    break
            if matched:
                from gradata._db import write_lessons_safe

                write_lessons_safe(lessons_path, format_lessons(lessons))
                # lessons.md changed — evict caches so readers see the
                # approval/rejection immediately.
                self._lessons_parse_cache = None
                with contextlib.suppress(Exception):
                    self._rule_cache.invalidate()

        if not matched:
            return {"resolved": False, "reason": "lesson_not_found_in_file"}

        from datetime import date

        with contextlib.closing(get_connection(self.db_path)) as conn:
            # Re-check resolution IS NULL to prevent lost-race overwrites when
            # two workers resolve the same approval concurrently. rowcount == 0
            # means another worker won the race.
            cur = conn.execute(
                "UPDATE pending_approvals SET resolution = ?, resolved_at = ? "
                "WHERE id = ? AND resolution IS NULL",
                (resolution, date.today().isoformat(), approval_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return {
                    "resolved": False,
                    "reason": "already_resolved_by_other_worker",
                }
        return {"resolved": True, "category": cat, "description": desc}

    def review_pending(self) -> list[dict]:
        """List lessons awaiting human approval with before/after context."""
        if not self.db_path.is_file():
            return []
        try:
            import contextlib
            import sqlite3

            from gradata._db import get_connection

            with contextlib.closing(get_connection(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM pending_approvals "
                    "WHERE resolution IS NULL ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.debug("review_pending query failed: %s", e)
            return []

    def approve_lesson(self, approval_id: int) -> dict:
        """Approve a pending lesson — sets confidence to INITIAL and enters graduation pipeline."""
        from gradata.enhancements.self_improvement import INITIAL_CONFIDENCE

        def _approve(lesson):
            lesson.confidence = INITIAL_CONFIDENCE
            lesson.pending_approval = False

        result = self._resolve_pending(approval_id, "approved", _approve)
        if result.get("resolved"):
            try:
                self.emit(
                    "LESSON_REVIEW",
                    "brain.approve_lesson",
                    {
                        "action": "approved",
                        "approval_id": approval_id,
                        "lesson_category": result["category"],
                        "lesson_description": result["description"][:200],
                    },
                    [f"category:{result['category']}", "review", "action:approved"],
                )
            except Exception as e:
                logger.debug("Approve event emit failed: %s", e)
            return {"approved": True, **result}
        return {"approved": False, "reason": result.get("reason", "unknown")}

    def reject_lesson(self, approval_id: int, reason: str = "") -> dict:
        """Reject a pending lesson — kills it with reason."""
        from gradata._types import LessonState

        def _reject(lesson):
            lesson.state = LessonState.KILLED
            lesson.kill_reason = f"rejected: {reason}" if reason else "rejected"
            lesson.pending_approval = False

        result = self._resolve_pending(approval_id, "rejected", _reject)
        if result.get("resolved"):
            try:
                self.emit(
                    "LESSON_REVIEW",
                    "brain.reject_lesson",
                    {
                        "action": "rejected",
                        "approval_id": approval_id,
                        "lesson_category": result["category"],
                        "lesson_description": result["description"][:200],
                        "reason": reason,
                    },
                    [f"category:{result['category']}", "review", "action:rejected"],
                )
            except Exception as e:
                logger.debug("Reject event emit failed: %s", e)
            return {"rejected": True, "reason": reason, **result}
        return {"rejected": False, "reason": result.get("reason", "unknown")}

    def agent_profile(self, agent_type: str) -> dict:
        """Get the skill evolution profile for an agent type."""
        from gradata._types import LessonState

        lessons = self._load_lessons()
        agent_lessons = [l for l in lessons if l.agent_type == agent_type]
        if not agent_lessons:
            return {"agent_type": agent_type, "total_lessons": 0}
        by_cat: dict[str, int] = {}
        skills, weaknesses = [], []
        for l in agent_lessons:
            by_cat[l.category] = by_cat.get(l.category, 0) + 1
            if l.state in (LessonState.PATTERN, LessonState.RULE):
                skills.append(
                    {
                        "category": l.category,
                        "state": l.state.value,
                        "confidence": l.confidence,
                        "description": l.description[:80],
                    }
                )
            elif l.state == LessonState.INSTINCT and l.confidence < 0.40:
                weaknesses.append(
                    {
                        "category": l.category,
                        "confidence": l.confidence,
                        "description": l.description[:80],
                    }
                )
        return {
            "agent_type": agent_type,
            "total_lessons": len(agent_lessons),
            "correction_categories": by_cat,
            "skills_acquired": skills,
            "active_weaknesses": weaknesses,
        }

    # ── Export ─────────────────────────────────────────────────────────

    def export_rules(self, min_state: str = "PATTERN", skill_name: str = "") -> str:
        """Export graduated brain rules as OpenSpace-compatible SKILL.md."""
        from gradata._core import brain_export_rules

        return brain_export_rules(self, min_state=min_state, skill_name=skill_name)

    def export_rules_json(self, min_state: str = "PATTERN") -> list[dict]:
        """Export graduated rules as a flat, sorted JSON array."""
        from gradata._core import brain_export_rules_json

        return brain_export_rules_json(self, min_state=min_state)

    def export_skill(
        self, output_dir: str | None = None, min_state: str = "PATTERN", skill_name: str = ""
    ) -> Path:
        """Export graduated rules as a full skill directory."""
        from gradata._core import brain_export_skill

        return brain_export_skill(
            self, output_dir=output_dir, min_state=min_state, skill_name=skill_name
        )

    def export_skills(self, output_dir: str | None = None, min_state: str = "PATTERN") -> list[str]:
        """Export graduated rules as per-category SKILL.md files."""
        from gradata._core import brain_export_skills

        return brain_export_skills(self, output_dir=output_dir, min_state=min_state)

    # ── Rule Inspection API + Batch Approval ─────────────────────────
    # Provided by BrainInspectionMixin (brain_inspection.py):
    #   rules(), explain(), trace(), export_data(),
    #   pending_promotions(), approve_promotion(), reject_promotion()

    # ── Notifications ──────────────────────────────────────────────────

    def on_notification(self, callback: Callable | None = None) -> None:
        """Register a callback for human-readable learning notifications.

        If *callback* is None, uses the built-in CLI handler (colored stderr).
        Notifications are formatted from EventBus events — corrections,
        graduations, meta-rules, session summaries.

        Usage::

            brain.on_notification()                    # CLI colored output
            brain.on_notification(my_slack_handler)     # custom handler
            brain.on_notification(lambda n: print(n.message))
        """
        from gradata.notifications import cli_handler, subscribe

        subscribe(self.bus, callback or cli_handler)

    # ── Events ─────────────────────────────────────────────────────────

    def emit(
        self,
        event_type: str,
        source: str,
        data: dict | None = None,
        tags: list | None = None,
        session: int | None = None,
    ) -> dict:
        """Emit an event to the brain's event log."""
        from gradata._events import emit

        return emit(event_type, source, data or {}, tags or [], session or 0, ctx=self.ctx)

    def query_events(
        self,
        event_type: str | None = None,
        session: int | None = None,
        last_n_sessions: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query events from the brain's event log."""
        try:
            from gradata._events import query

            return query(
                event_type=event_type,
                session=session,
                last_n_sessions=last_n_sessions,
                limit=limit,
                ctx=self.ctx,
            )
        except ImportError:
            return []

    def get_facts(self, prospect: str | None = None, fact_type: str | None = None) -> list[dict]:
        """Query structured facts from the brain."""
        try:
            from gradata._fact_extractor import query_facts

            return query_facts(prospect=prospect, fact_type=fact_type, ctx=self.ctx)
        except ImportError:
            return []

    def observe(
        self,
        messages: list[dict] | str,
        user_id: str = "default",
        *,
        kind: str | None = None,
    ) -> list[dict] | dict:
        """Extract facts from a conversation without requiring corrections."""
        if isinstance(messages, str):
            event_type = (kind or "observation").strip().upper()
            return self.emit(event_type, "brain.observe", {"content": messages})
        try:
            from gradata.enhancements.memory_extraction import MemoryExtractor
        except ImportError:
            return []
        extractor = MemoryExtractor()
        candidates = extractor.extract(messages)
        if not candidates:
            return []
        existing = self.get_facts()
        actions = extractor.reconcile(candidates, existing)
        results = []
        for action in actions:
            if action.op == "add":
                event = self.emit(
                    "FACT_EXTRACTED",
                    "brain.observe",
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
                    "FACT_INVALIDATED",
                    "brain.observe",
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
                    "FACT_UPDATED",
                    "brain.observe",
                    {
                        "target_id": action.target_id,
                        "new_content": action.fact.content,
                        "user_id": user_id,
                    },
                )
                results.append({"op": "update", "target": action.target_id, "event": event})
        return results

    # ── Search ─────────────────────────────────────────────────────────

    def search(
        self, query: str, mode: str | None = None, top_k: int = 5, file_type: str | None = None
    ) -> list[dict]:
        """Search the brain using FTS5 keyword search."""
        if mode == "events":
            return self._search_events(query, top_k)
        try:
            from gradata._query import brain_search

            results = brain_search(query, file_type=file_type, top_k=top_k, mode=mode, ctx=self.ctx)
        except ImportError:
            results = self._grep_search(query, top_k)
        return results

    def _grep_search(self, query: str, top_k: int) -> list[dict]:
        """Fallback search: grep through markdown files."""
        results, q = [], query.lower()
        for f in self.dir.rglob("*.md"):
            if ".git" in str(f) or "scripts" in str(f):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if q in text.lower():
                    for line in text.splitlines():
                        if q in line.lower():
                            results.append(
                                {
                                    "source": str(f.relative_to(self.dir)),
                                    "text": line[:200],
                                    "score": 1.0,
                                    "confidence": "keyword_match",
                                }
                            )
                            break
            except Exception as e:
                logger.debug("Grep search read failed for file: %s", e)
                continue
            if len(results) >= top_k:
                break
        return results

    def _search_events(self, query: str, top_k: int = 5) -> list[dict]:
        """Search over event history."""
        try:
            from gradata._query import brain_search

            return brain_search(query, file_type="event", top_k=top_k, ctx=self.ctx)
        except ImportError:
            import sqlite3

            db = getattr(self, "db_path", None)
            if not db or not db.exists():
                return []
            results, terms = [], query.lower().split()
            if not terms:
                return []
            # Push term filter into SQL so we don't scan 500 rows + filter
            # Python-side. Each term becomes a `data_json LIKE ?` — lowercase
            # both sides so the filter matches regardless of stored case.
            where = " AND ".join(["LOWER(data_json) LIKE ?"] * len(terms))
            params: list = [f"%{t}%" for t in terms]
            params.append(top_k)
            with sqlite3.connect(str(db)) as conn:
                rows = conn.execute(
                    f"SELECT id, ts, type, source, data_json FROM events "
                    f"WHERE {where} ORDER BY id DESC LIMIT ?",
                    params,
                ).fetchall()
            for row_id, ts, etype, _, data_json in rows:
                results.append(
                    {
                        "source": f"event:{etype}:{row_id}",
                        "file_type": "event",
                        "text": (data_json or "")[:500],
                        "score": 1.0,
                        "confidence": "keyword_match",
                        "modified": ts,
                    }
                )
            return results

    def embed(self, full: bool = False) -> int:
        """Embed brain files into SQLite. Returns chunks embedded."""
        try:
            from gradata._embed import main as embed_main

            return embed_main(brain_dir=self.dir, full=full)
        except ImportError as e:
            raise ImportError(
                f"Embedding requires: {e}\nRun: pip install sentence-transformers"
            ) from e

    # ── Manifest & Export ──────────────────────────────────────────────

    def manifest(self) -> dict:
        """Generate brain.manifest.json and return it."""
        try:
            from gradata._brain_manifest import generate_manifest, write_manifest

            m = generate_manifest(ctx=self.ctx)
            # Embed prove() data so the manifest is a complete quality certificate
            try:
                m["proof"] = self.prove()
            except Exception as exc:
                logger.debug("proof generation failed: %s", exc)
                m["proof"] = {
                    "proven": False,
                    "confidence_level": "error",
                    "evidence": {},
                    "summary": "Proof generation failed",
                }
            write_manifest(m, ctx=self.ctx)
            return m
        except ImportError:
            return {"schema_version": "1.0.0", "metadata": {"brain_version": "unknown"}}

    def export(self, output_path: str | None = None, mode: str = "full") -> Path:
        """Export brain as a shareable archive."""
        try:
            from gradata._export_brain import export_brain

            return export_brain(
                include_prospects=(mode != "no-prospects"),
                domain_only=(mode == "domain-only"),
                ctx=self.ctx,
            )
        except ImportError as e:
            raise RuntimeError(f"Export requires brain modules: {e}") from e

    def browse_tree(self, path: str = "") -> dict:
        """Browse the hierarchical rule tree.

        Args:
            path: Subtree path to browse. Empty = full tree.

        Returns:
            Nested dict representing the tree structure.
        """
        from gradata.rules.rule_tree import RuleTree

        lessons = self._load_lessons()
        tree = RuleTree(lessons)
        return tree.get_tree_structure(prefix=path)

    def export_tree(self, format: str = "json", path: str = "./export") -> Path:
        """Export the brain's rule tree to an external format.

        Args:
            format: One of "json", "obsidian"
            path: Output path (file for json, directory for obsidian)

        Returns:
            Path to the exported file/directory.
        """
        from gradata.rules.rule_tree import RuleTree, export_tree_json, export_tree_obsidian

        lessons = self._load_lessons()
        tree = RuleTree(lessons)
        output = Path(path)

        if format == "json":
            export_tree_json(tree, output)
        elif format == "obsidian":
            export_tree_obsidian(tree, output)
        else:
            export_tree_json(tree, output)  # default to JSON

        return output

    def context_for(self, message: str) -> str:
        """Compile relevant context for a user message."""
        try:
            from gradata._context_compile import compile_context

            return compile_context(message, ctx=self.ctx)
        except ImportError:
            results = self.search(message[:100], top_k=3)
            if not results:
                return ""
            lines = ["## Brain Context"]
            lines.extend(f"- [{r.get('source', '')}] {r.get('text', '')[:150]}" for r in results)
            return "\n".join(lines)

    def stats(self) -> dict:
        """Return brain statistics."""
        import sqlite3

        md_count = sum(
            1 for _ in self.dir.rglob("*.md") if ".git" not in str(_) and "scripts" not in str(_)
        )
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        embedding_count = 0
        if self.db_path.exists():
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    row = conn.execute("SELECT COUNT(*) FROM brain_embeddings").fetchone()
                    embedding_count = row[0] if row else 0
            except Exception as e:
                logger.debug("Embedding count query failed: %s", e)
        return {
            "brain_dir": str(self.dir),
            "markdown_files": md_count,
            "db_size_mb": round(db_size / 1024 / 1024, 2),
            "embedding_chunks": embedding_count,
            "has_manifest": self.manifest_path.exists(),
            "has_embeddings": embedding_count > 0,
        }

    def briefing(self, output_dir: str | Path = ".") -> str:
        """Generate a brain briefing and return as markdown."""
        try:
            from gradata.enhancements.reporting import generate_briefing

            return generate_briefing(self).to_markdown()
        except ImportError:
            return "# Brain Briefing\n\nBriefing module not available."

    def knowledge_graph(self) -> dict:
        """Return a knowledge graph of learned rules, clusters, and causal links.

        Assembles nodes (one per lesson), rule clusters, cross-domain candidates,
        and contradiction pairs from existing brain data without any additional I/O
        beyond reading lessons.md.

        Returns:
            Dict with keys: nodes, clusters, causal_links, contradictions,
            cross_domain, stats.
        """
        try:
            from gradata.enhancements.rule_pipeline import build_knowledge_graph

            lessons_path = self._find_lessons_path()
            if not lessons_path:
                return {
                    "nodes": [],
                    "clusters": [],
                    "causal_links": [],
                    "contradictions": [],
                    "cross_domain": [],
                    "stats": {},
                }
            return build_knowledge_graph(lessons_path, self.db_path)
        except ImportError:
            return {
                "nodes": [],
                "clusters": [],
                "causal_links": [],
                "contradictions": [],
                "cross_domain": [],
                "stats": {},
            }

    def backfill_from_git(
        self,
        repo_path: str | Path = ".",
        lookback_days: int = 90,
        file_patterns: list[str] | None = None,
        max_commits: int = 500,
    ) -> dict:
        """Bootstrap this brain from git history."""
        try:
            from gradata.enhancements.git_backfill import backfill_from_git

            return backfill_from_git(
                brain=self,
                repo_path=repo_path,
                lookback_days=lookback_days,
                file_patterns=file_patterns,
                max_commits=max_commits,
            ).to_dict()
        except ImportError:
            return {"error": "git_backfill module not available"}

    # ── Quality ────────────────────────────────────────────────────────

    def health(self) -> dict:
        """Generate brain health report."""
        try:
            from gradata.enhancements.reporting import generate_health_report

            return dataclasses.asdict(generate_health_report(self.db_path))
        except ImportError:
            return {"healthy": True, "issues": []}

    def get_constraints(self, task: str) -> list[str]:
        """Get applicable CARL constraints for a task."""
        return self.contracts.get_constraints(task) if self.contracts else []

    def register_tool(self, spec, handler=None) -> None:
        """Register a tool in the brain's tool registry."""
        if self.tools is not None:
            self.tools.register(spec, handler)

    def track_rule(
        self,
        rule_id: str,
        accepted: bool,
        misfired: bool = False,
        contradicted: bool = False,
        session: int | None = None,
    ) -> dict | None:
        """Log a RULE_APPLICATION event."""
        from gradata.rules.rule_tracker import log_application

        if session is None:
            try:
                from gradata._events import get_current_session

                session = get_current_session()
            except Exception as e:
                logger.debug("get_current_session failed, defaulting to 0: %s", e)
                session = 0
        return log_application(
            rule_id=rule_id,
            session=session,
            accepted=accepted,
            misfired=misfired,
            contradicted=contradicted,
        )

    def register_task_type(
        self, name: str, keywords: list[str], domain_hint: str = "", *, prepend: bool = False
    ) -> None:
        """Register a custom task type in the global scope classifier."""
        from gradata.rules.scope import register_task_type as _register

        _register(name, keywords, domain_hint, prepend=prepend)

    # ── Pattern Convenience Methods ────────────────────────────────────
    # These delegate to contrib.patterns. They stay on Brain for backward
    # compat but the patterns themselves are the canonical API.

    def guard(self, text: str, direction: str = "input") -> dict:
        """Run guardrail checks on text. See gradata.contrib.patterns.guardrails."""
        from gradata.contrib.patterns.guardrails import (
            InputGuard,
            OutputGuard,
            banned_phrases,
            destructive_action,
            injection_detector,
            pii_detector,
        )

        if direction == "input":
            checks = InputGuard(pii_detector, injection_detector).check(text)
        else:
            checks = OutputGuard(banned_phrases, destructive_action).check(text)
        failing = [c for c in checks if c.result == "fail"]
        return {
            "all_passed": not failing,
            "blocked": direction == "input" and bool(failing),
            "block_reason": "; ".join(f"{c.name}: {c.details}" for c in failing)
            if failing
            else None,
            "checks": [{"name": c.name, "result": c.result, "details": c.details} for c in checks],
        }

    def reflect(
        self, draft: str, checklist=None, evaluator=None, refiner=None, max_cycles: int = 3
    ) -> dict:
        """Run reflection loop. See gradata.contrib.patterns.reflection."""
        from gradata.contrib.patterns.reflection import EMAIL_CHECKLIST, default_evaluator
        from gradata.contrib.patterns.reflection import reflect as _reflect

        result = _reflect(
            output=draft,
            checklist=checklist or EMAIL_CHECKLIST,
            evaluator=evaluator or default_evaluator,
            refiner=refiner or (lambda o, f: o),
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

    def pipeline(self, *stages):
        """Create a Pipeline. See gradata.contrib.patterns.pipeline."""
        from gradata.contrib.patterns.pipeline import Pipeline

        return Pipeline(*stages)

    def run(self, tasks: list[str] | str, worker: Callable, *, max_concurrent: int = 3) -> dict:
        """Execute task(s) through orchestrator. See gradata.contrib.patterns.orchestrator."""
        from gradata.contrib.patterns.orchestrator import execute_orchestrated

        if isinstance(tasks, str):
            tasks = [tasks]
        return execute_orchestrated(tasks, worker, brain=self, max_concurrent=max_concurrent)

    def spawn_queue(
        self,
        tasks: list[str],
        worker: Callable,
        *,
        max_concurrent: int = 3,
        timeout_seconds: int = 1800,
        on_complete: Callable | None = None,
    ) -> dict:
        """Execute tasks through a pull-based queue with N concurrent workers."""
        import concurrent.futures

        results, failed = [], []

        def _run(t):
            try:
                r = worker(t)
                if on_complete:
                    on_complete(r)
                return {"task": t, "status": "completed", "result": r}
            except Exception as e:
                return {"task": t, "status": "failed", "error": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            futures = {pool.submit(_run, t): t for t in tasks}
            for f in concurrent.futures.as_completed(futures, timeout=timeout_seconds):
                try:
                    o = f.result()
                    (results if o["status"] == "completed" else failed).append(o)
                except Exception as e:
                    failed.append({"task": futures[f], "status": "timeout", "error": str(e)})
        try:
            self.emit(
                "QUEUE_COMPLETED",
                "spawn_queue",
                {"total": len(tasks), "completed": len(results), "failed": len(failed)},
            )
        except Exception as e:
            logger.debug("Queue completion event emit failed: %s", e)
        return {
            "total": len(tasks),
            "completed": len(results),
            "failed": len(failed),
            "results": results,
            "failures": failed,
        }
