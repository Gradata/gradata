import pytest
from gradata.services.session_history import SessionHistory


class TestSessionHistory:
    def test_record_injected_rules(self):
        sh = SessionHistory()
        sh.on_rules_injected(
            {
                "rules": [
                    {"id": "r1", "description": "validate email"},
                    {"id": "r2", "description": "check imports"},
                ]
            }
        )
        assert sh.injected_this_session == {"r1", "r2"}

    def test_record_correction_marks_rule(self):
        sh = SessionHistory()
        sh.on_rules_injected({"rules": [{"id": "r1", "description": "x"}]})
        sh.on_correction_created({"lesson": {"rule_id": "r1"}})
        assert "r1" in sh.corrected_this_session

    def test_compute_effectiveness(self):
        sh = SessionHistory()
        sh.on_rules_injected(
            {
                "rules": [
                    {"id": "r1", "description": "x"},
                    {"id": "r2", "description": "y"},
                    {"id": "r3", "description": "z"},
                ]
            }
        )
        sh.on_correction_created({"lesson": {"rule_id": "r1"}})
        scores = sh.compute_effectiveness()
        assert scores["r1"]["effective"] is False
        assert scores["r2"]["effective"] is True
        assert scores["r3"]["effective"] is True

    def test_empty_session(self):
        sh = SessionHistory()
        assert sh.compute_effectiveness() == {}

    def test_reset(self):
        sh = SessionHistory()
        sh.on_rules_injected({"rules": [{"id": "r1", "description": "x"}]})
        sh.reset()
        assert sh.injected_this_session == set()

    def test_on_session_ended_attaches_effectiveness(self):
        sh = SessionHistory()
        sh.on_rules_injected({"rules": [{"id": "r1", "description": "x"}]})
        payload = {}
        sh.on_session_ended(payload)
        assert "rule_effectiveness" in payload

    def test_apply_brain_rules_emits_rules_injected(self, tmp_path):
        """Regression: brain.apply_brain_rules() must fire rules.injected on the
        in-memory bus. Without this emit, SessionHistory's effectiveness tracking
        stays dormant — all three of its handlers subscribe, but rules.injected
        is the one with no emitter elsewhere in the codebase."""
        from gradata.brain import Brain

        brain = Brain.init(str(tmp_path), domain="Test")
        # Generate at least one graduated rule.
        for i in range(6):
            brain.correct(
                draft=f"Dear Sir or Madam, about item {i}",
                final=f"Hey, about item {i}",
                category="TONE",
            )
        brain.end_session()

        sh = SessionHistory()
        sh.subscribe_to_bus(brain.bus)

        rules_text = brain.apply_brain_rules("write an email")
        assert rules_text, "expected graduated rule text"
        assert len(sh.injected_this_session) >= 1, (
            "rules.injected did not fire — SessionHistory is dormant"
        )
