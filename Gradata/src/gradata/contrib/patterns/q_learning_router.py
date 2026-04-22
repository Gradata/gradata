"""
Q-Learning Agent Router — Reinforcement learning for task-to-agent routing.
============================================================================
Adapted from: ruflo (ruvnet/ruflo) v3/@claude-flow/cli/src/ruvector/q-learning-router.ts

Epsilon-greedy Q-learning router that learns which agent handles each
task type best, based on reward signals from the correction pipeline.

Key adaptations for Gradata:
- Reward signals from correction severity (not hardcoded)
- Feature extraction tuned for Gradata task types
- Persistence to brain vault
- Integration with orchestrator.py route_by_keywords

See ``QLearningRouter`` (route, update_reward) → ``RouteDecision``
(agent, confidence, exploiting).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import platform
import random
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "Experience",
    "QLearningRouter",
    "RouteDecision",
    "RouterConfig",
]


@dataclass
class RouterConfig:
    """Configuration for the Q-Learning router.

    Attributes:
        agents: List of available agent names to route to.
        learning_rate: Alpha — how fast new experience overwrites old.
        discount_factor: Gamma — how much future rewards matter.
        epsilon_start: Initial exploration rate (1.0 = fully random).
        epsilon_min: Minimum exploration rate after decay.
        epsilon_decay: Decay rate per update (multiplicative).
        cache_size: Max entries in the LRU route cache.
        cache_ttl: Cache entry time-to-live in seconds.
        replay_buffer_size: Max entries in experience replay buffer.
        feature_dim: Dimensionality of feature vectors.
        save_interval: Auto-save after this many updates.
    """

    agents: list[str] = field(
        default_factory=lambda: [
            "coder",
            "reviewer",
            "architect",
            "researcher",
            "debugger",
            "writer",
            "optimizer",
            "tester",
        ]
    )
    learning_rate: float = 0.1
    discount_factor: float = 0.95
    epsilon_start: float = 1.0
    epsilon_min: float = 0.05
    epsilon_decay: float = 0.995
    cache_size: int = 256
    cache_ttl: float = 300.0  # 5 minutes
    replay_buffer_size: int = 1000
    feature_dim: int = 32
    save_interval: int = 100


@dataclass
class RouteDecision:
    """A routing decision made by the Q-Learning router.

    Attributes:
        agent: The selected agent name.
        state_hash: Hash of the state that produced this decision.
        q_values: Q-values for all agents at this state.
        confidence: Confidence in the decision (max Q / sum Q).
        exploiting: True if decision was greedy, False if exploring.
    """

    agent: str
    state_hash: str = ""
    q_values: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    exploiting: bool = True


@dataclass
class Experience:
    """A single experience tuple for replay.

    Attributes:
        state_hash: State where action was taken.
        action_idx: Index of the chosen agent.
        reward: Reward received.
        td_error: Temporal difference error magnitude (for prioritized replay).
    """

    state_hash: str
    action_idx: int
    reward: float
    td_error: float = 0.0


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

# Keywords associated with each domain — used for feature extraction
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "code": ["code", "implement", "function", "class", "method", "refactor", "build"],
    "review": ["review", "check", "audit", "inspect", "quality", "lint"],
    "debug": ["debug", "fix", "bug", "error", "crash", "broken", "failing"],
    "test": ["test", "spec", "coverage", "assert", "verify", "validate"],
    "research": ["research", "investigate", "explore", "find", "search", "compare"],
    "write": ["write", "draft", "email", "document", "content", "blog", "article"],
    "design": ["design", "architecture", "system", "schema", "model", "structure"],
    "optimize": ["optimize", "performance", "speed", "memory", "cache", "scale"],
}


def _extract_features(text: str, dim: int = 32) -> list[float]:
    """Extract a feature vector from task text.

    Uses keyword matching + n-gram hashing for a fixed-dimension
    feature vector. Adapted from ruflo's feature extraction.

    Args:
        text: Task description text.
        dim: Output feature vector dimensionality.

    Returns:
        List of floats in [0.0, 1.0] of length dim.
    """
    features = [0.0] * dim
    text_lower = text.lower()
    words = text_lower.split()

    # Keyword features (first 8 dimensions)
    for i, (_domain, keywords) in enumerate(_DOMAIN_KEYWORDS.items()):
        if i >= dim:
            break
        match_count = sum(1 for kw in keywords if kw in text_lower)
        features[i] = min(1.0, match_count / max(1, len(keywords)))

    # N-gram hash features (remaining dimensions)
    for n in range(1, 4):  # unigrams, bigrams, trigrams
        for j in range(len(words) - n + 1):
            ngram = " ".join(words[j : j + n])
            h = int(hashlib.md5(ngram.encode()).hexdigest(), 16)
            idx = 8 + (h % max(1, dim - 8))
            if idx < dim:
                features[idx] = min(1.0, features[idx] + 0.1)

    return features


def _hash_state(features: list[float], quantize_bits: int = 4) -> str:
    """Hash a feature vector into a discrete state identifier.

    Quantizes features to reduce state space, then hashes.

    Args:
        features: Feature vector to hash.
        quantize_bits: Bits per feature for quantization.

    Returns:
        Hex string state hash.
    """
    scale = (1 << quantize_bits) - 1
    quantized = tuple(int(f * scale) for f in features)
    return hashlib.sha256(str(quantized).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Q-Learning Router
# ---------------------------------------------------------------------------


class QLearningRouter:
    """Q-Learning based agent router with experience replay.

    Uses epsilon-greedy exploration with configurable decay,
    experience replay for stable learning, and LRU caching
    for fast repeat lookups.

    Reward signals should come from the Gradata correction pipeline:
    - High reward (0.8-1.0): task completed, no corrections
    - Medium reward (0.4-0.7): task completed with minor corrections
    - Low reward (0.0-0.3): task required major corrections or rewrite
    """

    def __init__(self, config: RouterConfig | None = None) -> None:
        self.config = config or RouterConfig()
        if not self.config.agents:
            raise ValueError("RouterConfig.agents must be non-empty")
        self.q_table: dict[str, list[float]] = {}
        self.epsilon = self.config.epsilon_start
        self.update_count = 0
        # O(1) agent->index lookup used by reward updates (avoids linear list.index()).
        self._agent_index: dict[str, int] = {a: i for i, a in enumerate(self.config.agents)}

        # LRU cache: state_hash -> (agent, timestamp)
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()

        # Circular replay buffer
        self._replay_buffer: list[Experience] = []
        self._replay_idx = 0

        # Statistics
        self._stats = {
            "total_routes": 0,
            "cache_hits": 0,
            "explorations": 0,
            "exploitations": 0,
        }

    def route(self, task_description: str) -> RouteDecision:
        """Route a task to the best agent.

        Uses epsilon-greedy: with probability epsilon, picks a random
        agent (exploration). Otherwise picks the agent with highest
        Q-value for this state (exploitation).

        Args:
            task_description: Free-text description of the task.

        Returns:
            A RouteDecision with the selected agent and metadata.
        """
        features = _extract_features(task_description, self.config.feature_dim)
        state_hash = _hash_state(features)

        self._stats["total_routes"] += 1

        # Check cache
        if state_hash in self._cache:
            cached_agent, cached_time = self._cache[state_hash]
            if time.time() - cached_time < self.config.cache_ttl:
                self._stats["cache_hits"] += 1
                self._cache.move_to_end(state_hash)
                q_vals = self._get_q_values(state_hash)
                return RouteDecision(
                    agent=cached_agent,
                    state_hash=state_hash,
                    q_values=dict(zip(self.config.agents, q_vals, strict=False)),
                    confidence=self._compute_confidence(q_vals),
                    exploiting=True,
                )

        # Ensure state exists in Q-table
        q_values = self._get_q_values(state_hash)

        # Epsilon-greedy selection
        if random.random() < self.epsilon:
            # Explore
            action_idx = random.randrange(len(self.config.agents))
            self._stats["explorations"] += 1
            exploiting = False
        else:
            # Exploit
            action_idx = max(range(len(q_values)), key=lambda i: q_values[i])
            self._stats["exploitations"] += 1
            exploiting = True

        agent = self.config.agents[action_idx]

        # Update cache
        self._cache[state_hash] = (agent, time.time())
        if len(self._cache) > self.config.cache_size:
            self._cache.popitem(last=False)

        return RouteDecision(
            agent=agent,
            state_hash=state_hash,
            q_values=dict(zip(self.config.agents, q_values, strict=False)),
            confidence=self._compute_confidence(q_values),
            exploiting=exploiting,
        )

    def update_reward(
        self,
        decision: RouteDecision,
        reward: float,
    ) -> None:
        """Update Q-values based on observed reward.

        Args:
            decision: The route decision that was executed.
            reward: Reward signal in [0.0, 1.0].
                Map from Gradata correction severity:
                - 1.0: no correction needed
                - 0.7: trivial correction
                - 0.5: minor correction
                - 0.3: moderate correction
                - 0.1: major correction
                - 0.0: complete rewrite
        """
        reward = max(0.0, min(1.0, reward))
        state_hash = decision.state_hash
        action_idx = self._agent_index[decision.agent]

        q_values = self._get_q_values(state_hash)
        old_q = q_values[action_idx]

        # Q-learning update: Q(s,a) = Q(s,a) + α * (r + γ * max(Q(s',a')) - Q(s,a))
        # Since we don't have a next state, simplified to:
        # Q(s,a) = Q(s,a) + α * (r - Q(s,a))
        td_error = reward - old_q
        new_q = old_q + self.config.learning_rate * td_error

        q_values[action_idx] = new_q
        self.q_table[state_hash] = q_values

        # Add to replay buffer
        experience = Experience(
            state_hash=state_hash,
            action_idx=action_idx,
            reward=reward,
            td_error=abs(td_error),
        )
        self._add_to_replay(experience)

        # Decay epsilon
        self.epsilon = max(
            self.config.epsilon_min,
            self.epsilon * self.config.epsilon_decay,
        )

        self.update_count += 1

        # Replay from buffer periodically
        if self.update_count % 10 == 0:
            self._replay(batch_size=min(8, len(self._replay_buffer)))

    def reward_from_severity(self, severity: str) -> float:
        """Convert Gradata correction severity to reward signal.

        Maps the 5-level severity scale to [0.0, 1.0] rewards.

        Args:
            severity: One of "trivial", "minor", "moderate", "major", "rewrite".

        Returns:
            Reward value in [0.0, 1.0].
        """
        severity_rewards = {
            "trivial": 0.85,
            "minor": 0.65,
            "moderate": 0.40,
            "major": 0.15,
            "rewrite": 0.0,
        }
        return severity_rewards.get(severity, 0.5)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hmac(data_bytes: bytes) -> str:
        """Compute HMAC-SHA256 for integrity verification.

        Key is derived from machine identity (not secret, just tamper detection).
        """
        key = f"gradata-router-{platform.node()}".encode()
        return hmac.new(key, data_bytes, "sha256").hexdigest()

    def save(self, filepath: str | Path) -> None:
        """Save router state to JSON file with HMAC integrity check.

        Args:
            filepath: Path to save the router state.
        """
        state = {
            "version": "1.0.0",
            "q_table": self.q_table,
            "epsilon": self.epsilon,
            "update_count": self.update_count,
            "stats": self._stats,
            "config": {
                "agents": self.config.agents,
                "learning_rate": self.config.learning_rate,
                "discount_factor": self.config.discount_factor,
                "epsilon_min": self.config.epsilon_min,
                "epsilon_decay": self.config.epsilon_decay,
            },
        }
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        state["_hmac"] = self._compute_hmac(body)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def load(self, filepath: str | Path) -> bool:
        """Load router state from JSON file with HMAC integrity verification.

        Args:
            filepath: Path to load the router state from.

        Returns:
            True if loaded successfully, False if file doesn't exist or is tampered.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            return False

        with open(filepath, encoding="utf-8") as f:
            state = json.load(f)

        # Verify HMAC if present (backward compat: files without HMAC still load)
        stored_hmac = state.pop("_hmac", None)
        if stored_hmac is not None:
            body = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
            expected = self._compute_hmac(body)
            if stored_hmac != expected:
                logging.getLogger(__name__).warning(
                    "Q-table integrity check failed: %s may be tampered", filepath
                )
                return False

        # Semantic version comparison (not string comparison)
        try:
            file_ver = tuple(int(x) for x in state.get("version", "0").split("."))
            min_ver = (1, 0, 0)
            if file_ver < min_ver:
                return False
        except (ValueError, TypeError):
            return False

        self.q_table = state.get("q_table", {})
        self.epsilon = state.get("epsilon", self.config.epsilon_start)
        self.update_count = state.get("update_count", 0)
        self._stats.update(state.get("stats", {}))

        return True

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return router statistics."""
        return {
            **self._stats,
            "epsilon": round(self.epsilon, 4),
            "update_count": self.update_count,
            "q_table_size": len(self.q_table),
            "cache_size": len(self._cache),
            "replay_buffer_size": len(self._replay_buffer),
            "cache_hit_rate": (
                round(self._stats["cache_hits"] / max(1, self._stats["total_routes"]), 4)
            ),
        }

    def get_best_agent(self, task_description: str) -> str:
        """Get the best agent for a task without recording the route.

        Pure lookup, no side effects. Useful for preview/suggestions.
        """
        features = _extract_features(task_description, self.config.feature_dim)
        state_hash = _hash_state(features)
        q_values = self._get_q_values(state_hash)
        best_idx = max(range(len(q_values)), key=lambda i: q_values[i])
        return self.config.agents[best_idx]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_q_values(self, state_hash: str) -> list[float]:
        """Get or initialize Q-values for a state."""
        if state_hash not in self.q_table:
            # Initialize with small random values to break ties
            self.q_table[state_hash] = [random.uniform(0.0, 0.01) for _ in self.config.agents]
        return self.q_table[state_hash]

    def _compute_confidence(self, q_values: list[float]) -> float:
        """Compute confidence as softmax concentration."""
        if not q_values:
            return 0.0
        max_q = max(q_values)
        if max_q <= 0:
            return 0.0
        total = sum(q_values)
        if total <= 0:
            return 0.0
        return round(max_q / total, 4)

    def _add_to_replay(self, experience: Experience) -> None:
        """Add experience to circular replay buffer."""
        if len(self._replay_buffer) < self.config.replay_buffer_size:
            self._replay_buffer.append(experience)
        else:
            self._replay_buffer[self._replay_idx] = experience
            self._replay_idx = (self._replay_idx + 1) % self.config.replay_buffer_size

    def _replay(self, batch_size: int = 8) -> None:
        """Replay experiences from buffer with prioritized sampling.

        Experiences with higher TD error are sampled more frequently.
        """
        if not self._replay_buffer:
            return

        # Prioritized sampling by TD error
        td_errors = [max(0.01, e.td_error) for e in self._replay_buffer]
        total_td = sum(td_errors)
        probs = [td / total_td for td in td_errors]

        # Sample batch
        indices = random.choices(
            range(len(self._replay_buffer)),
            weights=probs,
            k=min(batch_size, len(self._replay_buffer)),
        )

        for idx in indices:
            exp = self._replay_buffer[idx]
            q_values = self._get_q_values(exp.state_hash)
            old_q = q_values[exp.action_idx]
            td_error = exp.reward - old_q
            q_values[exp.action_idx] = old_q + self.config.learning_rate * 0.5 * td_error
            self.q_table[exp.state_hash] = q_values
