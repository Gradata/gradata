"""Tests for mirofish_sim.py — expert panel discussion engine."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "brain" / "scripts"))


class TestAgent:
    def test_agent_creation(self):
        from mirofish_sim import Agent

        agent = Agent(
            name="Dr. Yuki Tanaka",
            archetype="icl_researcher",
            persona="Expert in few-shot learning.",
            behavioral_bias="optimist",
        )
        assert agent.name == "Dr. Yuki Tanaka"
        assert agent.archetype == "icl_researcher"

    def test_system_prompt(self):
        from mirofish_sim import Agent

        agent = Agent("Test", "researcher", "Studies ML.", "skeptic")
        prompt = agent.system_prompt()
        assert "Test" in prompt
        assert "researcher" in prompt
        assert "skeptic" in prompt


class TestPost:
    def test_post_creation(self):
        from mirofish_sim import Post, Agent

        agent = Agent("Test Agent", "test", "A test agent", "neutral")
        post = Post.create(agent=agent, round_num=1, content="My proposal is...", post_type="post")
        assert post.agent_name == "Test Agent"
        assert post.round_num == 1
        assert post.post_type == "post"
        assert post.id.startswith("R1-")

    def test_comment_references_parent(self):
        from mirofish_sim import Post, Agent

        agent = Agent("Test Agent", "test", "A test agent", "neutral")
        parent = Post.create(agent=agent, round_num=1, content="Original", post_type="post")
        comment = Post.create(
            agent=agent,
            round_num=2,
            content="I disagree",
            post_type="comment",
            parent_id=parent.id,
            references=[parent.id],
        )
        assert comment.parent_id == parent.id
        assert parent.id in comment.references

    def test_to_dict(self):
        from mirofish_sim import Post, Agent

        agent = Agent("Test", "test", "Test", "neutral")
        post = Post.create(agent=agent, round_num=1, content="Content", post_type="post")
        d = post.to_dict()
        assert d["agent"] == "Test"
        assert d["content"] == "Content"
        assert d["round"] == 1


class TestForum:
    def test_add_and_get_likes(self):
        from mirofish_sim import Post, Agent, Forum

        agent1 = Agent("Agent 1", "test", "Agent 1", "neutral")
        agent2 = Agent("Agent 2", "test", "Agent 2", "neutral")
        forum = Forum()
        post = Post.create(agent=agent1, round_num=1, content="Great idea", post_type="post")
        forum.add_post(post)
        forum.add_like(post.id, agent2.name)
        assert forum.get_likes(post.id) == 1

    def test_top_posts_by_likes(self):
        from mirofish_sim import Post, Agent, Forum

        agents = [Agent(f"Agent {i}", "test", f"Agent {i}", "neutral") for i in range(5)]
        forum = Forum()
        posts = []
        for i, a in enumerate(agents):
            p = Post.create(agent=a, round_num=1, content=f"Idea {i}", post_type="post")
            forum.add_post(p)
            posts.append(p)
        for a in agents:
            forum.add_like(posts[2].id, a.name)
        top = forum.top_posts(n=1)
        assert top[0].id == posts[2].id

    def test_save_to_jsonl(self, tmp_path):
        from mirofish_sim import Post, Agent, Forum

        agent = Agent("Test", "test", "Test agent", "neutral")
        forum = Forum()
        post = Post.create(agent=agent, round_num=1, content="Test content", post_type="post")
        forum.add_post(post)
        output = tmp_path / "posts.jsonl"
        forum.save_jsonl(output)
        with open(output) as f:
            data = json.loads(f.readline())
        assert data["agent"] == "Test"
        assert data["content"] == "Test content"

    def test_get_posts_by_round(self):
        from mirofish_sim import Post, Agent, Forum

        agent = Agent("Test", "test", "Test", "neutral")
        forum = Forum()
        p1 = Post.create(agent=agent, round_num=1, content="R1", post_type="post")
        p2 = Post.create(agent=agent, round_num=2, content="R2", post_type="post")
        forum.add_post(p1)
        forum.add_post(p2)
        r1_posts = forum.get_posts_by_round(1)
        assert len(r1_posts) == 1
        assert r1_posts[0].content == "R1"

    def test_summary_context(self):
        from mirofish_sim import Post, Agent, Forum

        agent = Agent("Test", "test", "Test", "neutral")
        forum = Forum()
        post = Post.create(
            agent=agent,
            round_num=1,
            content="A great proposal about memory systems",
            post_type="post",
        )
        forum.add_post(post)
        forum.add_like(post.id, "Other Agent")
        ctx = forum.summary_context(max_posts=5)
        assert "Test" in ctx
        assert "1 likes" in ctx or "memory" in ctx.lower()
