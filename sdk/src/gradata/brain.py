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
import sys
from pathlib import Path

from gradata._brain_search import BrainSearchMixin
from gradata._brain_events import BrainEventsMixin
from gradata._brain_learning import BrainLearningMixin
from gradata._brain_export import BrainExportMixin
from gradata._brain_quality import BrainQualityMixin
from gradata._brain_pipeline import BrainPipelineMixin
from gradata._brain_cloud import BrainCloudMixin

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


class Brain(
    BrainSearchMixin,
    BrainEventsMixin,
    BrainLearningMixin,
    BrainExportMixin,
    BrainQualityMixin,
    BrainPipelineMixin,
    BrainCloudMixin,
):
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

    def __repr__(self):
        return f"Brain('{self.dir}')"


# Re-export the type alias so callers can annotate return values of brain.pipeline()
try:
    from gradata.patterns.pipeline import Pipeline
except ImportError:
    pass
