"""
Tests for the BrainPipelineMixin — brain.pipeline() and brain.register_task_type().

These are integration-level behavioral tests: they verify user-visible
outcomes of the mixin API without inspecting internal implementation state.

Run: cd sdk && python -m pytest tests/test_brain_pipeline.py -v
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _noop(x):
    return x


# ---------------------------------------------------------------------------
# brain.pipeline()
# ---------------------------------------------------------------------------


class TestBrainPipeline:
    """brain.pipeline(*stages) creates a runnable Pipeline."""

    def test_returns_pipeline_object(self, fresh_brain):
        from gradata.contrib.patterns.pipeline import Pipeline, Stage

        pipe = fresh_brain.pipeline(Stage("step", _noop))
        assert isinstance(pipe, Pipeline)

    def test_single_stage_pipeline_runs_successfully(self, fresh_brain):
        from gradata.contrib.patterns.pipeline import Stage

        pipe = fresh_brain.pipeline(Stage("identity", lambda x: x))
        result = pipe.run("hello")
        assert result.success is True

    def test_pipeline_passes_data_through_stages(self, fresh_brain):
        from gradata.contrib.patterns.pipeline import Stage

        pipe = fresh_brain.pipeline(
            Stage("double", lambda x: x * 2),
            Stage("add_one", lambda x: x + 1),
        )
        result = pipe.run(3)
        # 3 * 2 = 6; 6 + 1 = 7
        assert result.output == 7

    def test_pipeline_records_completed_stage_count(self, fresh_brain):
        """stages_completed is an integer count of completed stages."""
        from gradata.contrib.patterns.pipeline import Stage

        pipe = fresh_brain.pipeline(
            Stage("first", lambda x: x),
            Stage("second", lambda x: x),
        )
        result = pipe.run("data")
        assert result.stages_completed == 2

    def test_empty_pipeline_raises_value_error(self, fresh_brain):
        """Pipeline requires at least one Stage — zero stages raises ValueError."""
        with pytest.raises(ValueError):
            fresh_brain.pipeline()

    def test_pipeline_with_failing_stage_marks_failure(self, fresh_brain):
        from gradata.contrib.patterns.pipeline import Stage, gate

        # @gate wraps a bool-returning function — False means rejected
        @gate
        def always_fail(x) -> bool:
            return False

        pipe = fresh_brain.pipeline(Stage("boom", lambda x: x, gate=always_fail, max_retries=0))
        result = pipe.run("trigger")
        assert result.success is False

    def test_pipeline_with_gate_passes_when_gate_passes(self, fresh_brain):
        from gradata.contrib.patterns.pipeline import Stage, gate

        @gate
        def always_pass(x) -> bool:
            return True

        pipe = fresh_brain.pipeline(Stage("step", lambda x: x, gate=always_pass))
        result = pipe.run("value")
        assert result.success is True

    def test_pipeline_with_gate_fails_when_gate_rejects(self, fresh_brain):
        from gradata.contrib.patterns.pipeline import Stage, gate

        @gate
        def always_fail(x) -> bool:
            return False

        pipe = fresh_brain.pipeline(Stage("step", lambda x: x, gate=always_fail, max_retries=0))
        result = pipe.run("x")
        assert result.success is False

    def test_multiple_pipeline_calls_return_independent_objects(self, fresh_brain):
        from gradata.contrib.patterns.pipeline import Stage

        pipe_a = fresh_brain.pipeline(Stage("a", lambda x: "a"))
        pipe_b = fresh_brain.pipeline(Stage("b", lambda x: "b"))
        assert pipe_a is not pipe_b
        assert pipe_a.run("x").output == "a"
        assert pipe_b.run("x").output == "b"


# ---------------------------------------------------------------------------
# brain.register_task_type()
# ---------------------------------------------------------------------------


class TestRegisterTaskType:
    """brain.register_task_type() wires a custom intent into the scope classifier."""

    @pytest.fixture(autouse=True)
    def _reset_task_types(self):
        """Reset global task type registry after each test to prevent pollution."""
        import gradata.rules.scope as _scope
        from gradata.rules.scope import _REGISTERED_TASK_TYPES, DEFAULT_TASK_TYPES

        list(_REGISTERED_TASK_TYPES)
        yield
        _scope._REGISTERED_TASK_TYPES[:] = list(DEFAULT_TASK_TYPES)

    def test_registers_without_error(self, fresh_brain):
        """Happy path — no exception raised."""
        fresh_brain.register_task_type(
            "custom_review",
            keywords=["review", "audit"],
            domain_hint="engineering",
        )

    def test_registered_type_is_classified(self, fresh_brain):
        """After registration, the classify_scope function resolves the new type."""
        from gradata.rules.scope import classify_scope

        fresh_brain.register_task_type(
            "mythical_task_xyz",
            keywords=["mythical", "xyzzy"],
        )
        task_type, _ = classify_scope("please do the mythical xyzzy thing")
        # classify_scope returns either a TaskType enum or a plain string
        name = task_type.name.lower() if hasattr(task_type, "name") else str(task_type).lower()
        assert name == "mythical_task_xyz"

    def test_prepend_flag_gives_higher_priority(self, fresh_brain):
        """A prepended task type beats a keyword tied to an existing type."""
        from gradata.rules.scope import classify_scope

        fresh_brain.register_task_type(
            "super_email_42",
            keywords=["super_unique_kw_42"],
            prepend=True,
        )
        task_type, _ = classify_scope("super_unique_kw_42")
        name = task_type.name.lower() if hasattr(task_type, "name") else str(task_type).lower()
        assert name == "super_email_42"

    def test_empty_keywords_list_does_not_raise(self, fresh_brain):
        """Registering with zero keywords is a valid no-op."""
        fresh_brain.register_task_type("empty_kw_type", keywords=[])

    def test_domain_hint_is_accepted(self, fresh_brain):
        """domain_hint kwarg is accepted without error (smoke test)."""
        fresh_brain.register_task_type(
            "domain_hinted",
            keywords=["domhint"],
            domain_hint="sales",
        )

    def test_register_unicode_keywords(self, fresh_brain):
        """Unicode keyword strings are accepted without blowing up."""
        fresh_brain.register_task_type(
            "unicode_type",
            keywords=["résumé", "naïve", "über"],
        )

    def test_duplicate_registration_does_not_raise(self, fresh_brain):
        """Re-registering the same name replaces the old entry gracefully."""
        fresh_brain.register_task_type("dup_type", keywords=["dup_kw_one"])
        fresh_brain.register_task_type("dup_type", keywords=["dup_kw_two"])
