"""MiroFish Simulation Engine — expert panel discussion with structured debate rounds.

Generates multi-round debates between AI personas about architecture questions.
Uses Ollama (Gemma4:e4b) for local generation.

Usage:
    python mirofish_sim.py --config config.json --output dir/
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_URL, ollama_generate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mirofish")

# ---------------------------------------------------------------------------
# Round types (15 rounds)
# ---------------------------------------------------------------------------
ROUND_TYPES = [
    "open_thesis",  # 1
    "open_thesis",  # 2
    "cross_examination",  # 3
    "cross_examination",  # 4
    "adversarial_attack",  # 5
    "adversarial_defense",  # 6
    "cross_pollination",  # 7
    "synthesis",  # 8
    "implementation_check",  # 9
    "edge_cases",  # 10
    "privacy_review",  # 11
    "feasibility_vote",  # 12
    "final_refinement",  # 13
    "consensus_statement",  # 14
    "dissent_register",  # 15
]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
@dataclass
class Agent:
    """An expert persona in the simulation."""

    name: str
    archetype: str
    persona: str
    behavioral_bias: str

    def system_prompt(self) -> str:
        return (
            f"You are {self.name}, a {self.archetype}.\n"
            f"Persona: {self.persona}\n"
            f"Your behavioral bias is: {self.behavioral_bias}.\n"
            "Respond concisely and in character. Stay grounded in evidence."
        )


# ---------------------------------------------------------------------------
# Post
# ---------------------------------------------------------------------------
@dataclass
class Post:
    """A single forum post, comment, or reaction."""

    id: str
    agent_name: str
    archetype: str
    round_num: int
    post_type: str  # post / comment / like / disagree
    content: str
    parent_id: str | None
    references: list[str]
    timestamp: str
    likes: int = 0

    @classmethod
    def create(
        cls,
        agent: Agent,
        round_num: int,
        content: str,
        post_type: str = "post",
        parent_id: str | None = None,
        references: list[str] | None = None,
    ) -> Post:
        post_id = f"R{round_num}-{uuid.uuid4().hex[:8]}"
        return cls(
            id=post_id,
            agent_name=agent.name,
            archetype=agent.archetype,
            round_num=round_num,
            post_type=post_type,
            content=content,
            parent_id=parent_id,
            references=references or [],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent_name,
            "archetype": self.archetype,
            "round": self.round_num,
            "type": self.post_type,
            "content": self.content,
            "parent_id": self.parent_id,
            "references": self.references,
            "timestamp": self.timestamp,
            "likes": self.likes,
        }


# ---------------------------------------------------------------------------
# Forum
# ---------------------------------------------------------------------------
class Forum:
    """Manages posts, likes, and discussion context."""

    def __init__(self) -> None:
        self.posts: list[Post] = []
        self._likes: dict[str, set[str]] = {}  # post_id -> set of agent names

    def add_post(self, post: Post) -> None:
        self.posts.append(post)

    def add_like(self, post_id: str, agent_name: str) -> None:
        self._likes.setdefault(post_id, set()).add(agent_name)
        # Update the post object too
        for p in self.posts:
            if p.id == post_id:
                p.likes = len(self._likes[post_id])
                break

    def get_likes(self, post_id: str) -> int:
        return len(self._likes.get(post_id, set()))

    def get_posts_by_round(self, round_num: int) -> list[Post]:
        return [p for p in self.posts if p.round_num == round_num]

    def top_posts(self, n: int = 5) -> list[Post]:
        scored = [(self.get_likes(p.id), p) for p in self.posts if p.post_type == "post"]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:n]]

    def save_jsonl(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for post in self.posts:
                f.write(json.dumps(post.to_dict(), ensure_ascii=False) + "\n")

    def summary_context(self, max_posts: int = 10) -> str:
        """Build a text summary of the forum for prompt injection."""
        top = self.top_posts(n=max_posts)
        if not top:
            return "No posts yet."
        lines = []
        for p in top:
            likes = self.get_likes(p.id)
            snippet = p.content[:200]
            lines.append(f"[{p.agent_name}] (R{p.round_num}, {likes} likes): {snippet}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ollama generation
# ---------------------------------------------------------------------------
DEFAULT_MODEL = DEFAULT_OLLAMA_MODEL
OLLAMA_URL = DEFAULT_OLLAMA_URL


def _generate(prompt: str, system: str = "", model: str = DEFAULT_MODEL) -> str:
    """Call Ollama generate endpoint. Returns response text."""
    return ollama_generate(
        prompt,
        system=system,
        model=model,
        url=OLLAMA_URL,
        timeout=120,
        num_predict=500,
        temperature=0.8,
    )


# ---------------------------------------------------------------------------
# Round prompts
# ---------------------------------------------------------------------------
def _round_prompt(
    round_type: str,
    question: str,
    forum: Forum,
    agent: Agent,
    round_num: int,
) -> str:
    """Build the user prompt for a given round type."""
    context = forum.summary_context(max_posts=8)

    base = f"DISCUSSION QUESTION: {question}\n\nFORUM CONTEXT:\n{context}\n\n"

    prompts = {
        "open_thesis": (
            f"{base}Round {round_num} — OPEN THESIS.\n"
            "Present your initial position on the question. Be specific and cite evidence."
        ),
        "cross_examination": (
            f"{base}Round {round_num} — CROSS EXAMINATION.\n"
            "Pick the weakest argument from the forum and challenge it directly. "
            "Ask probing questions."
        ),
        "adversarial_attack": (
            f"{base}Round {round_num} — ADVERSARIAL ATTACK.\n"
            "Find the strongest consensus position and attack it. "
            "Identify hidden assumptions and failure modes."
        ),
        "adversarial_defense": (
            f"{base}Round {round_num} — ADVERSARIAL DEFENSE.\n"
            "Defend the position that was most attacked. "
            "Strengthen it with new evidence or reframing."
        ),
        "cross_pollination": (
            f"{base}Round {round_num} — CROSS POLLINATION.\n"
            "Combine ideas from two different posts to create a novel synthesis. "
            "Credit the original authors."
        ),
        "synthesis": (
            f"{base}Round {round_num} — SYNTHESIS.\n"
            "Identify the 2-3 strongest ideas and weave them into a coherent proposal."
        ),
        "implementation_check": (
            f"{base}Round {round_num} — IMPLEMENTATION CHECK.\n"
            "How would the top proposals actually be implemented? "
            "Identify concrete steps and blockers."
        ),
        "edge_cases": (
            f"{base}Round {round_num} — EDGE CASES.\n"
            "What edge cases would break the top proposals? "
            "Consider scale, adversarial users, and failure modes."
        ),
        "privacy_review": (
            f"{base}Round {round_num} — PRIVACY REVIEW.\n"
            "What privacy and security concerns does the top proposal raise? "
            "How should they be mitigated?"
        ),
        "feasibility_vote": (
            f"{base}Round {round_num} — FEASIBILITY VOTE.\n"
            "Rate the top proposal's feasibility 1-10 and explain your score. "
            "Would you ship this?"
        ),
        "final_refinement": (
            f"{base}Round {round_num} — FINAL REFINEMENT.\n"
            "Suggest one specific improvement to the leading proposal."
        ),
        "consensus_statement": (
            f"{base}Round {round_num} — CONSENSUS STATEMENT.\n"
            "Draft a one-paragraph consensus statement that captures "
            "the group's best thinking."
        ),
        "dissent_register": (
            f"{base}Round {round_num} — DISSENT REGISTER.\n"
            "If you disagree with the consensus, state your dissent clearly. "
            "If you agree, say so briefly."
        ),
    }
    return prompts.get(round_type, f"{base}Round {round_num}. Share your thoughts.")


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------
def _generate_synthesis(forum: Forum, question: str, model: str = DEFAULT_MODEL) -> str:
    """Generate a final synthesis from top posts."""
    context = forum.summary_context(max_posts=15)
    prompt = (
        f"QUESTION: {question}\n\n"
        f"TOP POSTS FROM 15-ROUND EXPERT DEBATE:\n{context}\n\n"
        "Write a comprehensive synthesis that:\n"
        "1. Identifies the strongest consensus positions\n"
        "2. Notes key dissents\n"
        "3. Proposes actionable next steps\n"
        "Keep it under 500 words."
    )
    return _generate(
        prompt, system="You are a neutral moderator summarizing an expert debate.", model=model
    )


# ---------------------------------------------------------------------------
# Main simulation loop
# ---------------------------------------------------------------------------
def run_simulation(config: dict[str, Any], output_dir: str | Path) -> Path:
    """Run a full MiroFish simulation.

    Args:
        config: Dict with keys: question, agents[], rounds (int), model, agents_per_round
        output_dir: Directory to write results

    Returns:
        Path to the output JSONL file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    question = config["question"]
    model = config.get("model", DEFAULT_MODEL)
    num_rounds = config.get("rounds", 15)
    # Build agents
    agents = [
        Agent(
            name=a["name"],
            archetype=a["archetype"],
            persona=a["persona"],
            behavioral_bias=a.get("behavioral_bias", "neutral"),
        )
        for a in config["agents"]
    ]
    agents_per_round = config.get("agents_per_round") or len(agents)

    forum = Forum()
    jsonl_path = output_dir / "posts.jsonl"

    for round_num in range(1, num_rounds + 1):
        round_idx = min(round_num - 1, len(ROUND_TYPES) - 1)
        round_type = ROUND_TYPES[round_idx]
        log.info("Round %d/%d — %s", round_num, num_rounds, round_type)

        # Select agents for this round
        selected = random.sample(agents, min(agents_per_round, len(agents)))

        for agent in selected:
            prompt = _round_prompt(round_type, question, forum, agent, round_num)
            content = _generate(prompt, system=agent.system_prompt(), model=model)

            post = Post.create(
                agent=agent,
                round_num=round_num,
                content=content,
                post_type="post" if round_num <= 2 else "comment",
            )
            forum.add_post(post)
            log.info("  %s posted (%d chars)", agent.name, len(content))

        # After round 2, agents can like earlier posts
        if round_num > 2:
            earlier_posts = [p for p in forum.posts if p.round_num < round_num]
            for agent in selected:
                if earlier_posts:
                    liked = random.choice(earlier_posts)
                    forum.add_like(liked.id, agent.name)

        # Save progress after each round
        forum.save_jsonl(jsonl_path)

    # Final synthesis
    log.info("Generating final synthesis...")
    synthesis = _generate_synthesis(forum, question, model)
    synthesis_path = output_dir / "synthesis.md"
    synthesis_path.write_text(synthesis, encoding="utf-8")
    log.info("Synthesis written to %s", synthesis_path)

    # Save final state
    forum.save_jsonl(jsonl_path)
    log.info("Done. %d posts written to %s", len(forum.posts), jsonl_path)

    return jsonl_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="MiroFish expert panel simulation")
    parser.add_argument("--config", required=True, help="Path to config JSON")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    run_simulation(config, args.output)


if __name__ == "__main__":
    main()
