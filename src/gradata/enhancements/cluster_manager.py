"""Incremental centroid clustering for corrections via cosine similarity. Temporal-proximity
gating + running-average centroid updates (O(1), no reassignment). Pure computation; caller
owns state I/O. From EverOS (EverMind-AI) cluster_manager/manager.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ClusterAssignment",
    "ClusterConfig",
    "ClusterManager",
    "ClusterState",
    "cosine_similarity",
]


@dataclass
class ClusterConfig:
    """Configuration for the cluster manager.

    Attributes:
        similarity_threshold: Minimum cosine similarity to join a cluster.
        max_time_gap_days: Maximum temporal distance to consider clustering.
        min_cluster_size: Minimum items before a cluster is considered stable.
    """

    similarity_threshold: float = 0.65
    max_time_gap_days: float = 7.0
    min_cluster_size: int = 2


@dataclass
class ClusterState:
    """Serializable state for cluster manager.

    Caller is responsible for loading/saving this state.
    Adapted from EverOS's pure-computation pattern.

    Attributes:
        centroids: Mapping of cluster_id -> centroid vector.
        counts: Mapping of cluster_id -> item count.
        last_timestamps: Mapping of cluster_id -> last item timestamp.
        assignments: Mapping of item_id -> cluster_id.
        next_cluster_idx: Counter for generating cluster IDs.
    """

    centroids: dict[str, list[float]] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    last_timestamps: dict[str, float] = field(default_factory=dict)
    assignments: dict[str, str] = field(default_factory=dict)
    next_cluster_idx: int = 0

    @property
    def cluster_count(self) -> int:
        return len(self.centroids)

    @property
    def item_count(self) -> int:
        return len(self.assignments)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "centroids": self.centroids,
            "counts": self.counts,
            "last_timestamps": self.last_timestamps,
            "assignments": self.assignments,
            "next_cluster_idx": self.next_cluster_idx,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClusterState:
        """Deserialize from dict."""
        return cls(
            centroids=data.get("centroids", {}),
            counts=data.get("counts", {}),
            last_timestamps=data.get("last_timestamps", {}),
            assignments=data.get("assignments", {}),
            next_cluster_idx=data.get("next_cluster_idx", 0),
        )


@dataclass
class ClusterAssignment:
    """Result of assigning an item to a cluster.

    Attributes:
        item_id: The item that was assigned.
        cluster_id: The cluster it was assigned to.
        is_new: Whether a new cluster was created.
        similarity: Cosine similarity to the assigned cluster (0 if new).
        cluster_size: Number of items in the cluster after assignment.
    """

    item_id: str
    cluster_id: str
    is_new: bool
    similarity: float = 0.0
    cluster_size: int = 1


# ---------------------------------------------------------------------------
# Math utilities (shared implementation in _math.py)
# ---------------------------------------------------------------------------

from .._stats import cosine_similarity

# ---------------------------------------------------------------------------
# Cluster Manager
# ---------------------------------------------------------------------------


class ClusterManager:
    """Incremental centroid clustering with temporal gating.

    Adapted from EverOS's ClusterManager. Pure computation:
    caller provides and persists ClusterState.

    Algorithm:
    1. For each existing cluster:
       a. Check temporal proximity (skip if too far apart)
       b. Compute cosine similarity to centroid
    2. If best similarity >= threshold: assign to that cluster
    3. Else: create new cluster

    Centroid update is running-average (O(1) per update).
    """

    def __init__(self, config: ClusterConfig | None = None) -> None:
        self.config = config or ClusterConfig()

    def assign(
        self,
        state: ClusterState,
        item_id: str,
        vector: list[float],
        timestamp: float,
    ) -> ClusterAssignment:
        """Assign an item to the best matching cluster.

        Mutates state in-place. Caller should persist after.

        Args:
            state: Current cluster state.
            item_id: Unique identifier for the item.
            vector: Embedding vector for the item.
            timestamp: Unix timestamp of the item.

        Returns:
            ClusterAssignment with the result.
        """
        # Validate vector
        if not vector:
            raise ValueError("vector must be non-empty")
        if any(not isinstance(v, (int, float)) or v != v for v in vector):
            raise ValueError("vector contains non-finite values (NaN/None)")

        # Check dimension consistency with existing clusters
        for cid, centroid in state.centroids.items():
            if len(vector) != len(centroid):
                raise ValueError(
                    f"vector dimension {len(vector)} doesn't match "
                    f"cluster '{cid}' dimension {len(centroid)}"
                )
            break  # Only need to check one

        # Skip if already assigned
        if item_id in state.assignments:
            cluster_id = state.assignments[item_id]
            return ClusterAssignment(
                item_id=item_id,
                cluster_id=cluster_id,
                is_new=False,
                cluster_size=state.counts.get(cluster_id, 1),
            )

        # Find best cluster
        best_cluster = None
        best_similarity = -1.0

        for cluster_id, centroid in state.centroids.items():
            # Temporal gating
            last_ts = state.last_timestamps.get(cluster_id, 0.0)
            time_gap = abs(timestamp - last_ts)
            if time_gap > self.config.max_time_gap_days * 86400.0:
                continue

            # Cosine similarity
            sim = cosine_similarity(vector, centroid)
            if sim > best_similarity:
                best_similarity = sim
                best_cluster = cluster_id

        # Decision: join existing or create new
        if best_cluster is not None and best_similarity >= self.config.similarity_threshold:
            # Update existing cluster
            _uc_old = state.centroids[best_cluster]
            _uc_count = state.counts[best_cluster]
            state.centroids[best_cluster] = [
                (_uc_old[i] * _uc_count + vector[i]) / (_uc_count + 1) for i in range(len(vector))
            ]
            state.counts[best_cluster] = _uc_count + 1
            state.last_timestamps[best_cluster] = max(
                state.last_timestamps.get(best_cluster, 0.0),
                timestamp,
            )
            state.assignments[item_id] = best_cluster
            return ClusterAssignment(
                item_id=item_id,
                cluster_id=best_cluster,
                is_new=False,
                similarity=best_similarity,
                cluster_size=state.counts[best_cluster],
            )
        # Create new cluster
        cluster_id = f"cluster_{state.next_cluster_idx}"
        state.next_cluster_idx += 1
        state.centroids[cluster_id] = list(vector)
        state.counts[cluster_id] = 1
        state.last_timestamps[cluster_id] = timestamp
        state.assignments[item_id] = cluster_id
        return ClusterAssignment(
            item_id=item_id,
            cluster_id=cluster_id,
            is_new=True,
            similarity=0.0,
            cluster_size=1,
        )

    def get_cluster_items(
        self,
        state: ClusterState,
        cluster_id: str,
    ) -> list[str]:
        """Get all item IDs in a cluster."""
        return [item_id for item_id, cid in state.assignments.items() if cid == cluster_id]

    def get_stable_clusters(self, state: ClusterState) -> list[str]:
        """Get cluster IDs that meet the minimum size threshold."""
        return [cid for cid, count in state.counts.items() if count >= self.config.min_cluster_size]

    def stats(self, state: ClusterState) -> dict[str, Any]:
        """Get clustering statistics."""
        sizes = list(state.counts.values())
        return {
            "cluster_count": state.cluster_count,
            "item_count": state.item_count,
            "avg_cluster_size": sum(sizes) / max(1, len(sizes)),
            "max_cluster_size": max(sizes) if sizes else 0,
            "singleton_count": sum(1 for s in sizes if s == 1),
            "stable_cluster_count": len(self.get_stable_clusters(state)),
        }
