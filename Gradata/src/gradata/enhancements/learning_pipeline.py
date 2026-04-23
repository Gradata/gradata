"""
Learning Pipeline — End-to-end correction processing chain.
=============================================================
Wires the adapted modules into a unified pipeline:

    observation_hooks (capture)
      → cluster_manager (group related corrections)
      → lesson_discriminator (filter noise)
      → self_improvement (graduate INSTINCT→PATTERN→RULE)
      → q_learning_router (route based on learned rewards)
      → context_brackets (degrade gracefully)

Each stage is optional — the pipeline degrades gracefully when
modules are missing. The Brain class calls process_correction()
as the single entry point after a correction is captured.

Usage::

    from gradata.enhancements.learning_pipeline import LearningPipeline

    pipeline = LearningPipeline(brain_dir=Path("./my-brain"))
    result = pipeline.process_correction(
        draft="Dear Sir,",
        final="Hey,",
        severity="moderate",
        category="TONE",
        session_id="s42",
        task_type="email_draft",
    )
    print(result.stages_completed)   # ["observe", "cluster", "discriminate", "graduate"]
    print(result.is_high_value)      # True
    print(result.cluster_id)         # "cluster_3"
    print(result.lesson_state)       # "PATTERN"
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

__all__ = [
    "LearningPipeline",
    "PipelineResult",
]


@dataclass
class PipelineResult:
    """Result from processing a correction through the full pipeline.

    Attributes:
        stages_completed: Which pipeline stages ran successfully.
        stages_skipped: Which stages were skipped (module missing or not applicable).
        stages_failed: Which stages failed with errors.
        observation: The captured observation (if observe stage ran).
        cluster_id: Cluster this correction was assigned to (if cluster stage ran).
        cluster_is_new: Whether a new cluster was created.
        is_high_value: Whether the discriminator deemed this high-value.
        discriminator_confidence: Confidence from the discriminator.
        discriminator_recommendation: graduate/monitor/discard.
        lesson_state: Current lesson state after graduation (INSTINCT/PATTERN/RULE).
        route_decision: Agent routing decision for similar future tasks.
        context_bracket: Current context bracket after processing.
        memory_type: Classified memory type for this correction.
        processing_time_ms: Total pipeline processing time.
        metadata: Arbitrary metadata from pipeline stages.
    """

    stages_completed: list[str] = field(default_factory=list)
    stages_skipped: list[str] = field(default_factory=list)
    stages_failed: list[str] = field(default_factory=list)
    # Observe
    observation: Any = None
    # Cluster
    cluster_id: str = ""
    cluster_is_new: bool = False
    # Discriminate
    is_high_value: bool = False
    discriminator_confidence: float = 0.0
    discriminator_recommendation: str = ""
    # Graduate
    lesson_state: str = ""
    # Route
    route_decision: Any = None
    # Context
    context_bracket: str = ""
    # Memory type
    memory_type: str = ""
    # Timing
    processing_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """True if no stages failed."""
        return len(self.stages_failed) == 0

    @property
    def stages_total(self) -> int:
        return len(self.stages_completed) + len(self.stages_skipped) + len(self.stages_failed)


class LearningPipeline:
    """End-to-end correction processing pipeline.

    Connects all adapted modules into a single flow. Each stage
    is independent — failures in one stage don't block others.

    The pipeline does NOT require a Brain instance. It operates
    on raw data and returns structured results. The Brain class
    can call this pipeline in its correct() method.
    """

    def __init__(
        self,
        brain_dir: Path | str | None = None,
        observation_dir: Path | str | None = None,
        router_path: Path | str | None = None,
        cluster_config: Any = None,
        discriminator_config: Any = None,
    ) -> None:
        self.brain_dir = Path(brain_dir) if brain_dir else None
        self._init_stages(observation_dir, router_path, cluster_config, discriminator_config)

    def _init_stages(self, observation_dir, router_path, cluster_config, discriminator_config):
        """Initialize pipeline stages. Each is optional."""

        # Stage 1: Observation capture
        self._observer = None
        try:
            from gradata.enhancements.observation_hooks import ObservationStore

            obs_dir = observation_dir or (
                self.brain_dir / "observations" if self.brain_dir else None
            )
            if obs_dir:
                self._observer = ObservationStore(base_dir=obs_dir)
        except ImportError:
            pass

        # Stage 2: Clustering
        self._cluster_mgr = None
        self._cluster_state = None
        try:
            from gradata.enhancements.cluster_manager import (
                ClusterConfig,
                ClusterManager,
                ClusterState,
            )

            self._cluster_mgr = ClusterManager(cluster_config or ClusterConfig())
            self._cluster_state = ClusterState()
            # Try loading persisted state
            if self.brain_dir:
                state_file = self.brain_dir / "cluster_state.json"
                if state_file.exists():
                    import json

                    data = json.loads(state_file.read_text(encoding="utf-8"))
                    self._cluster_state = ClusterState.from_dict(data)
        except ImportError:
            pass

        # Stage 3: Discriminator
        self._discriminator = None
        try:
            from gradata.enhancements.lesson_discriminator import LessonDiscriminator

            self._discriminator = LessonDiscriminator(discriminator_config)
        except ImportError:
            pass

        # Stage 4: Memory taxonomy
        self._memory_taxonomy = None
        try:
            from gradata.enhancements.memory_taxonomy import classify_memory_type

            self._memory_taxonomy = classify_memory_type
        except ImportError:
            pass

        # Stage 5: Q-Learning Router
        self._router = None
        try:
            from gradata.contrib.patterns.q_learning_router import QLearningRouter

            self._router = QLearningRouter()
            if router_path:
                self._router.load(router_path)
            elif self.brain_dir:
                rp = self.brain_dir / "q_router.json"
                if rp.exists():
                    self._router.load(rp)
        except ImportError:
            pass

        # Stage 6: Context tracking
        self._context_tracker = None
        try:
            from gradata.contrib.patterns.context_brackets import ContextTracker

            self._context_tracker = ContextTracker(max_tokens=200_000)
        except ImportError:
            pass

    def process_correction(
        self,
        draft: str = "",
        final: str = "",
        severity: str = "minor",
        category: str = "",
        session_id: str = "",
        task_type: str = "",
        project_id: str = "",
        occurrence_count: int = 1,
        is_user_explicit: bool = False,
        existing_rule_ids: list[str] | None = None,
        vector: list[float] | None = None,
    ) -> PipelineResult:
        """Process a correction through the full learning pipeline.

        Each stage runs independently. Failures are logged but don't
        block subsequent stages.

        Args:
            draft: Original AI output.
            final: User-corrected version.
            severity: Correction severity (trivial/minor/moderate/major/rewrite).
            category: Correction category (TONE, CONTENT, etc).
            session_id: Current session identifier.
            task_type: Type of task where correction occurred.
            project_id: Portable project identifier.
            occurrence_count: How many times this pattern has been seen.
            is_user_explicit: Whether user explicitly flagged this.
            existing_rule_ids: Rules that already cover this area.
            vector: Pre-computed embedding vector for clustering.

        Returns:
            PipelineResult with outputs from each stage.
        """
        start = time.time()
        result = PipelineResult()

        # Defensive: coerce None to empty string
        draft = draft or ""
        final = final or ""
        severity = severity or "minor"
        category = category or ""

        # ── Stage 1: Observe ──────────────────────────────────────────
        if self._observer:
            try:
                from gradata.enhancements.observation_hooks import observe_tool_use

                obs = observe_tool_use(
                    tool_name="brain.correct",
                    input_data=f"severity={severity} category={category}",
                    output_data=f"draft_len={len(draft)} final_len={len(final)}",
                    session_id=session_id,
                    project_id=project_id,
                    success=True,
                )
                self._observer.append(obs)
                result.observation = obs
                result.stages_completed.append("observe")
            except Exception as e:
                _log.warning("Observe stage failed: %s", e)
                result.stages_failed.append("observe")
        else:
            result.stages_skipped.append("observe")

        # ── Stage 2: Cluster ──────────────────────────────────────────
        if self._cluster_mgr and self._cluster_state and vector:
            try:
                assignment = self._cluster_mgr.assign(
                    state=self._cluster_state,
                    item_id=f"{session_id}_{category}_{int(time.time())}",
                    vector=vector,
                    timestamp=time.time(),
                )
                result.cluster_id = assignment.cluster_id
                result.cluster_is_new = assignment.is_new
                result.stages_completed.append("cluster")
            except Exception as e:
                _log.warning("Cluster stage failed: %s", e)
                result.stages_failed.append("cluster")
        elif not vector:
            result.stages_skipped.append("cluster")
            result.metadata["cluster_skip_reason"] = "no_vector"
        else:
            result.stages_skipped.append("cluster")

        # ── Stage 3: Discriminate ─────────────────────────────────────
        if self._discriminator:
            try:
                verdict = self._discriminator.evaluate(
                    correction_text=f"{draft[:200]} → {final[:200]}",
                    severity=severity,
                    task_type=task_type,
                    occurrence_count=occurrence_count,
                    is_user_explicit=is_user_explicit,
                    existing_rule_ids=existing_rule_ids,
                )
                result.is_high_value = verdict.is_high_value
                result.discriminator_confidence = verdict.confidence
                result.discriminator_recommendation = verdict.recommendation
                result.stages_completed.append("discriminate")
            except Exception as e:
                _log.warning("Discriminate stage failed: %s", e)
                result.stages_failed.append("discriminate")
        else:
            result.stages_skipped.append("discriminate")

        # ── Stage 4: Classify memory type ─────────────────────────────
        if self._memory_taxonomy:
            try:
                combined = f"{category} {severity} {draft[:100]} {final[:100]}"
                mem_type = self._memory_taxonomy(combined)
                result.memory_type = mem_type.value
                result.stages_completed.append("classify_memory")
            except Exception as e:
                _log.warning("Memory classification failed: %s", e)
                result.stages_failed.append("classify_memory")
        else:
            result.stages_skipped.append("classify_memory")

        # ── Stage 5: Route ────────────────────────────────────────────
        if self._router and task_type:
            try:
                decision = self._router.route(task_type)
                result.route_decision = decision
                result.stages_completed.append("route")

                # Feed reward from severity
                reward = self._router.reward_from_severity(severity)
                self._router.update_reward(decision, reward)
            except Exception as e:
                _log.warning("Route stage failed: %s", e)
                result.stages_failed.append("route")
        else:
            result.stages_skipped.append("route")

        # ── Stage 6: Context bracket ──────────────────────────────────
        if self._context_tracker:
            try:
                # Estimate token consumption from correction text
                token_estimate = (len(draft) + len(final)) // 4
                self._context_tracker.consume(token_estimate)
                result.context_bracket = self._context_tracker.bracket.value
                result.stages_completed.append("context_bracket")
            except Exception as e:
                _log.warning("Context bracket failed: %s", e)
                result.stages_failed.append("context_bracket")
        else:
            result.stages_skipped.append("context_bracket")

        result.processing_time_ms = int((time.time() - start) * 1000)
        return result

    def save_state(self) -> None:
        """Persist pipeline state (cluster state, router Q-table)."""
        if not self.brain_dir:
            return

        # Save cluster state
        if self._cluster_state:
            import json

            state_file = self.brain_dir / "cluster_state.json"
            state_file.write_text(
                json.dumps(self._cluster_state.to_dict(), indent=2),
                encoding="utf-8",
            )

        # Save router
        if self._router:
            self._router.save(self.brain_dir / "q_router.json")

    def stats(self) -> dict[str, Any]:
        """Get pipeline statistics across all stages."""
        stats: dict[str, Any] = {"stages_available": []}

        if self._observer:
            stats["stages_available"].append("observe")
        if self._cluster_mgr and self._cluster_state:
            stats["stages_available"].append("cluster")
            from gradata.enhancements.cluster_manager import ClusterManager

            stats["cluster"] = ClusterManager().stats(self._cluster_state)
        if self._discriminator:
            stats["stages_available"].append("discriminate")
        if self._memory_taxonomy:
            stats["stages_available"].append("classify_memory")
        if self._router:
            stats["stages_available"].append("route")
            stats["router"] = self._router.stats()
        if self._context_tracker:
            stats["stages_available"].append("context_bracket")
            stats["context"] = {
                "bracket": self._context_tracker.bracket.value,
                "remaining_ratio": round(self._context_tracker.remaining_ratio, 4),
                "tokens_used": self._context_tracker.tokens_used,
            }

        return stats


# ═══════════════════════════════════════════════════════════════════════
# Correction Metrics (from correction_tracking.py)
# ═══════════════════════════════════════════════════════════════════════


def compute_density(corrections: int = 0, outputs: int = 0, **kwargs) -> float:
    """Compute correction density: corrections / outputs."""
    if outputs <= 0:
        return 0.0
    return round(corrections / outputs, 6)
