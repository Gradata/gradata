from __future__ import annotations

import logging

from gradata.enhancements.meta_rules import MetaRule, is_injectable_meta_rule


def test_meta_source_filtering_logs_warning(caplog) -> None:
    meta = MetaRule(
        id="meta-bad",
        principle="deterministic principle",
        source_categories=["DRAFTING"],
        source_lesson_ids=["lesson-1"],
        confidence=0.8,
        created_session=1,
        last_validated_session=1,
        source="deterministic",
    )

    with caplog.at_level(logging.WARNING):
        assert is_injectable_meta_rule(meta) is False

    assert "dropping meta-rule meta-bad (source=deterministic) from injection" in caplog.text
