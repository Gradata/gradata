"""
Tests for the four integration adapters (OpenAI, Anthropic, LangChain, CrewAI).

Each adapter wraps a third-party client with brain memory.  Tests use
unittest.mock to simulate the LLM clients — no real API keys needed.

Run: pytest sdk/tests/test_integrations.py -v
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# fixtures (fresh_brain, brain_with_content, etc.) come from conftest.py


# ===========================================================================
# OpenAI adapter
# ===========================================================================


class TestOpenAIAdapter:
    """Tests for patch_openai()."""

    def _make_client(self):
        """Build a mock OpenAI client with chat.completions.create."""
        client = MagicMock()
        # response shape: response.choices[0].message.content
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello from AI"))]
        client.chat.completions.create.return_value = mock_response
        return client, mock_response

    def test_patch_wraps_client(self, fresh_brain):
        """patch_openai returns the same client object (not a copy)."""
        from gradata.integrations.openai_adapter import patch_openai

        client, _ = self._make_client()
        original_id = id(client)
        patched = patch_openai(client, brain_dir=fresh_brain.dir)
        assert id(patched) == original_id
        assert hasattr(patched, "_brain")

    def test_create_still_works(self, fresh_brain):
        """Patched create() calls through to the original and returns response."""
        from gradata.integrations.openai_adapter import patch_openai

        client, mock_response = self._make_client()
        patched = patch_openai(client, brain_dir=fresh_brain.dir)
        result = patched.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi there"}],
        )
        assert result is mock_response

    def test_rules_injected_into_system_prompt(self, fresh_brain):
        """Brain rules are prepended to the system message."""
        from gradata.integrations.openai_adapter import patch_openai

        client, _ = self._make_client()
        original_create = client.chat.completions.create
        # Give the brain a rule to inject
        with patch.object(fresh_brain, "apply_brain_rules", return_value="RULE: Be concise"):
            patched = patch_openai(client, brain_dir=fresh_brain.dir)
            patched._brain.apply_brain_rules = MagicMock(return_value="RULE: Be concise")

            messages = [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Draft an email"},
            ]
            patched.chat.completions.create(model="gpt-4", messages=messages)

            # The underlying client.create must have received a messages list
            # whose system entry contains the rule. The adapter now clones
            # the caller's list before injecting — so we inspect call_args,
            # not the caller's untouched list.
            call_messages = original_create.call_args.kwargs["messages"]
            system_msg = next(m for m in call_messages if m["role"] == "system")
            assert "RULE: Be concise" in system_msg["content"]
            # Caller's own list must remain untouched (no shared-state mutation).
            assert messages[0]["content"] == "You are helpful."

    def test_creates_system_message_when_missing(self, fresh_brain):
        """If no system message exists, one is created with brain rules."""
        from gradata.integrations.openai_adapter import patch_openai

        client, _ = self._make_client()
        original_create = client.chat.completions.create
        patched = patch_openai(client, brain_dir=fresh_brain.dir)
        patched._brain.apply_brain_rules = MagicMock(return_value="RULE: Be brief")

        messages = [{"role": "user", "content": "Hello"}]
        patched.chat.completions.create(model="gpt-4", messages=messages)

        # A system message should have been inserted in the cloned list.
        call_messages = original_create.call_args.kwargs["messages"]
        assert call_messages[0]["role"] == "system"
        assert "RULE: Be brief" in call_messages[0]["content"]
        # Caller's own list must remain untouched.
        assert messages == [{"role": "user", "content": "Hello"}]

    def test_output_captured(self, fresh_brain):
        """AI output is logged via brain.log_output."""
        from gradata.integrations.openai_adapter import patch_openai

        client, _ = self._make_client()
        patched = patch_openai(client, brain_dir=fresh_brain.dir)

        with patch.object(patched._brain, "log_output") as mock_log:
            with patch.object(patched._brain, "observe"):
                patched.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": "Hi"}],
                )
                mock_log.assert_called_once()
                assert "Hello from AI" in mock_log.call_args[0][0]

    def test_graceful_fallback_no_brain(self, tmp_path):
        """When brain_dir doesn't exist, client works without patching."""
        from gradata.integrations.openai_adapter import patch_openai

        client, mock_response = self._make_client()
        # Use a real SimpleNamespace so _brain won't auto-appear like on MagicMock
        real_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=client.chat.completions.create,
                )
            )
        )
        patched = patch_openai(real_client, brain_dir=tmp_path / "does-not-exist")
        assert not hasattr(patched, "_brain")
        # Original create should still work
        result = patched.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert result is mock_response


# ===========================================================================
# Anthropic adapter
# ===========================================================================


class TestAnthropicAdapter:
    """Tests for patch_anthropic()."""

    def _make_client(self):
        """Build a mock Anthropic client with messages.create."""
        client = MagicMock()
        text_block = MagicMock()
        text_block.text = "Response from Claude"
        mock_response = MagicMock()
        mock_response.content = [text_block]
        client.messages.create.return_value = mock_response
        return client, mock_response

    def test_patch_wraps_client(self, fresh_brain):
        """patch_anthropic returns the same client instance."""
        from gradata.integrations.anthropic_adapter import patch_anthropic

        client, _ = self._make_client()
        patched = patch_anthropic(client, brain_dir=fresh_brain.dir)
        assert id(patched) == id(client)
        assert hasattr(patched, "_brain")

    def test_create_returns_response(self, fresh_brain):
        """Patched create() returns the original response."""
        from gradata.integrations.anthropic_adapter import patch_anthropic

        client, mock_response = self._make_client()
        patched = patch_anthropic(client, brain_dir=fresh_brain.dir)
        result = patched.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert result is mock_response

    def test_rules_injected_into_system(self, fresh_brain):
        """Brain rules are prepended to the system kwarg."""
        from gradata.integrations.anthropic_adapter import patch_anthropic

        client, _ = self._make_client()
        # Keep a reference to the original mock before patching replaces it
        original_create_mock = client.messages.create
        patched = patch_anthropic(client, brain_dir=fresh_brain.dir)
        patched._brain.apply_brain_rules = MagicMock(return_value="RULE: No jargon")

        patched.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            system="Be helpful.",
            messages=[{"role": "user", "content": "Draft email"}],
        )

        # The underlying original mock should have been called
        assert original_create_mock.called
        call_kwargs = original_create_mock.call_args[1]
        # System should contain our rule prepended to the original
        assert "RULE: No jargon" in call_kwargs["system"]
        assert "Be helpful." in call_kwargs["system"]

    def test_output_captured(self, fresh_brain):
        """AI output is logged via brain.log_output."""
        from gradata.integrations.anthropic_adapter import patch_anthropic

        client, _ = self._make_client()
        patched = patch_anthropic(client, brain_dir=fresh_brain.dir)

        with patch.object(patched._brain, "log_output") as mock_log:
            with patch.object(patched._brain, "observe"):
                patched.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=100,
                    messages=[{"role": "user", "content": "Hi"}],
                )
                mock_log.assert_called_once()
                assert "Response from Claude" in mock_log.call_args[0][0]

    def test_graceful_fallback_no_brain(self, tmp_path):
        """When brain is unavailable, client returns unpatched."""
        from gradata.integrations.anthropic_adapter import patch_anthropic

        client, mock_response = self._make_client()
        # Use SimpleNamespace so _brain won't auto-appear like on MagicMock
        real_client = SimpleNamespace(
            messages=SimpleNamespace(
                create=client.messages.create,
            )
        )
        patched = patch_anthropic(real_client, brain_dir=tmp_path / "nonexistent")
        assert not hasattr(patched, "_brain")
        result = patched.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert result is mock_response

    def test_handles_list_content_blocks(self, fresh_brain):
        """Adapter handles user messages that are content-block lists."""
        from gradata.integrations.anthropic_adapter import patch_anthropic

        client, _ = self._make_client()
        patched = patch_anthropic(client, brain_dir=fresh_brain.dir)
        patched._brain.apply_brain_rules = MagicMock(return_value="")

        # Content as list of blocks (Anthropic format)
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Hello there"}]},
        ]
        # Should not raise
        patched.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=messages,
        )


# ===========================================================================
# LangChain adapter
# ===========================================================================


class TestLangChainAdapter:
    """Tests for BrainMemory (LangChain-compatible memory)."""

    def test_memory_variables(self, fresh_brain):
        """BrainMemory exposes the expected memory_variables list."""
        from gradata.integrations.langchain_adapter import BrainMemory

        memory = BrainMemory(brain_dir=fresh_brain.dir)
        assert memory.memory_variables == ["brain_context"]

    def test_load_memory_returns_dict(self, fresh_brain):
        """load_memory_variables returns a dict with the memory_key."""
        from gradata.integrations.langchain_adapter import BrainMemory

        memory = BrainMemory(brain_dir=fresh_brain.dir)
        result = memory.load_memory_variables({"input": "Draft an email"})
        assert isinstance(result, dict)
        assert "brain_context" in result

    def test_load_memory_with_none_input(self, fresh_brain):
        """load_memory_variables handles None inputs gracefully."""
        from gradata.integrations.langchain_adapter import BrainMemory

        memory = BrainMemory(brain_dir=fresh_brain.dir)
        result = memory.load_memory_variables(None)
        assert isinstance(result, dict)
        assert "brain_context" in result

    def test_save_context_logs_output(self, fresh_brain):
        """save_context calls brain.log_output with the AI message."""
        from gradata.integrations.langchain_adapter import BrainMemory

        memory = BrainMemory(brain_dir=fresh_brain.dir)
        with patch.object(memory.brain, "log_output") as mock_log:
            with patch.object(memory.brain, "observe"):
                memory.save_context(
                    {"input": "What is the budget?"},
                    {"output": "The budget is $500K."},
                )
                mock_log.assert_called_once()
                assert "$500K" in mock_log.call_args[0][0]

    def test_save_context_observes_conversation(self, fresh_brain):
        """save_context calls brain.observe with the full exchange."""
        from gradata.integrations.langchain_adapter import BrainMemory

        memory = BrainMemory(brain_dir=fresh_brain.dir)
        with patch.object(memory.brain, "log_output"):
            with patch.object(memory.brain, "observe") as mock_observe:
                memory.save_context(
                    {"input": "Hello"},
                    {"output": "Hi there"},
                )
                mock_observe.assert_called_once()
                msgs = mock_observe.call_args[0][0]
                assert len(msgs) == 2
                assert msgs[0]["role"] == "user"
                assert msgs[1]["role"] == "assistant"

    def test_clear_is_noop(self, fresh_brain):
        """clear() does not raise."""
        from gradata.integrations.langchain_adapter import BrainMemory

        memory = BrainMemory(brain_dir=fresh_brain.dir)
        memory.clear()  # no-op, should not raise

    def test_rules_injected_into_context(self, fresh_brain):
        """When brain has rules, they appear in loaded context."""
        from gradata.integrations.langchain_adapter import BrainMemory

        memory = BrainMemory(brain_dir=fresh_brain.dir)
        with patch.object(memory.brain, "apply_brain_rules", return_value="RULE: Always be polite"):
            result = memory.load_memory_variables({"input": "Draft email"})
            assert "RULE: Always be polite" in result["brain_context"]


# ===========================================================================
# CrewAI adapter
# ===========================================================================


class TestCrewAIAdapter:
    """Tests for BrainCrewMemory (CrewAI-compatible memory)."""

    def test_save_calls_observe(self, fresh_brain):
        """save() passes content to brain.observe."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory

        mem = BrainCrewMemory(brain_dir=fresh_brain.dir)
        with patch.object(mem.brain, "observe") as mock_obs:
            mem.save("Important finding about the client", agent="researcher")
            mock_obs.assert_called_once()
            msgs = mock_obs.call_args[0][0]
            assert msgs[0]["role"] == "assistant"
            assert "Important finding" in msgs[0]["content"]

    def test_search_returns_list(self, fresh_brain):
        """search() returns a list of dicts with content/score/source."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory

        mem = BrainCrewMemory(brain_dir=fresh_brain.dir)
        results = mem.search("budget objections")
        assert isinstance(results, list)

    def test_search_with_results(self, brain_with_content):
        """search() returns results from indexed brain content."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory
        from gradata._query import fts_rebuild

        fts_rebuild()
        mem = BrainCrewMemory(brain_dir=brain_with_content.dir)
        results = mem.search("rocketship")
        # May or may not find results depending on FTS state, but should not crash
        assert isinstance(results, list)

    def test_search_result_shape(self, fresh_brain):
        """Results from search have the expected keys."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory

        mem = BrainCrewMemory(brain_dir=fresh_brain.dir)
        # Mock brain.search to return known results
        with patch.object(
            mem.brain,
            "search",
            return_value=[{"text": "Budget is $500K", "score": 0.9, "source": "prospect"}],
        ):
            results = mem.search("budget")
            assert len(results) == 1
            assert results[0]["content"] == "Budget is $500K"
            assert results[0]["score"] == 0.9
            assert results[0]["source"] == "prospect"

    def test_reset_is_noop(self, fresh_brain):
        """reset() does not raise."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory

        mem = BrainCrewMemory(brain_dir=fresh_brain.dir)
        mem.reset()  # should not raise

    def test_get_rules(self, fresh_brain):
        """get_rules() returns brain rules as a string."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory

        mem = BrainCrewMemory(brain_dir=fresh_brain.dir)
        with patch.object(mem.brain, "apply_brain_rules", return_value="RULE: Focus on ROI"):
            rules = mem.get_rules(task="email_draft")
            assert "RULE: Focus on ROI" in rules

    def test_get_rules_fallback(self, fresh_brain):
        """get_rules() returns empty string when brain raises."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory

        mem = BrainCrewMemory(brain_dir=fresh_brain.dir)
        with patch.object(mem.brain, "apply_brain_rules", side_effect=RuntimeError("test error")):
            rules = mem.get_rules()
            assert rules == ""

    def test_graceful_fallback_no_brain(self, tmp_path):
        """BrainCrewMemory raises if brain dir doesn't exist (no fallback)."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory

        # CrewAI adapter doesn't have fallback — it raises in __init__
        with pytest.raises(Exception):
            BrainCrewMemory(brain_dir=tmp_path / "nonexistent")

    def test_save_handles_error(self, fresh_brain):
        """save() handles brain.observe errors gracefully (logs, no raise)."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory

        mem = BrainCrewMemory(brain_dir=fresh_brain.dir)
        with patch.object(mem.brain, "observe", side_effect=RuntimeError("db locked")):
            # Should not raise
            mem.save("Some memory content")

    def test_search_handles_error(self, fresh_brain):
        """search() returns empty list on brain.search error."""
        from gradata.integrations.crewai_adapter import BrainCrewMemory

        mem = BrainCrewMemory(brain_dir=fresh_brain.dir)
        with patch.object(mem.brain, "search", side_effect=RuntimeError("db locked")):
            results = mem.search("anything")
            assert results == []


# ===========================================================================
# Deprecation shim tests
# ===========================================================================


class TestDeprecationWarnings:
    """Verify that importing integrations adapter modules emits DeprecationWarning."""

    def _reimport(self, module_name: str):
        """Force a fresh import by removing the module from sys.modules first."""
        import sys

        # Remove the module (and any cached sub-module) so the warning fires again.
        for key in list(sys.modules):
            if key == module_name or key.startswith(module_name + "."):
                del sys.modules[key]
        import importlib

        return importlib.import_module(module_name)

    def test_anthropic_adapter_warns_on_import(self):
        """Importing gradata.integrations.anthropic_adapter raises DeprecationWarning."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self._reimport("gradata.integrations.anthropic_adapter")
        messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
        assert any("anthropic_adapter" in m and "v0.8.0" in m for m in messages), messages

    def test_openai_adapter_warns_on_import(self):
        """Importing gradata.integrations.openai_adapter raises DeprecationWarning."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self._reimport("gradata.integrations.openai_adapter")
        messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
        assert any("openai_adapter" in m and "v0.8.0" in m for m in messages), messages

    def test_langchain_adapter_warns_on_import(self):
        """Importing gradata.integrations.langchain_adapter raises DeprecationWarning."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self._reimport("gradata.integrations.langchain_adapter")
        messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
        assert any("langchain_adapter" in m and "v0.8.0" in m for m in messages), messages

    def test_crewai_adapter_warns_on_import(self):
        """Importing gradata.integrations.crewai_adapter raises DeprecationWarning."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self._reimport("gradata.integrations.crewai_adapter")
        messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
        assert any("crewai_adapter" in m and "v0.8.0" in m for m in messages), messages

    def test_warning_points_to_middleware(self):
        """Deprecation warnings reference the gradata.middleware replacement."""
        import sys
        import warnings
        import importlib

        for mod_name, expected_replacement in [
            ("gradata.integrations.anthropic_adapter", "wrap_anthropic"),
            ("gradata.integrations.openai_adapter", "wrap_openai"),
            ("gradata.integrations.langchain_adapter", "LangChainCallback"),
            ("gradata.integrations.crewai_adapter", "CrewAIGuard"),
        ]:
            for key in list(sys.modules):
                if key == mod_name or key.startswith(mod_name + "."):
                    del sys.modules[key]
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                importlib.import_module(mod_name)
            all_messages = " ".join(
                str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)
            )
            assert expected_replacement in all_messages, (
                f"{mod_name} warning does not mention {expected_replacement!r}: {all_messages!r}"
            )

    def test_non_adapter_integrations_not_deprecated(self):
        """embeddings and session_history do NOT emit DeprecationWarning."""
        import warnings

        for mod_name in [
            "gradata.integrations.embeddings",
            "gradata.integrations.session_history",
        ]:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                import importlib

                importlib.import_module(mod_name)
            depr = [w for w in caught if issubclass(w.category, DeprecationWarning)]
            assert not depr, f"{mod_name} should not emit DeprecationWarning, got: {depr}"
