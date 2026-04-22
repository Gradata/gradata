"""Regression tests for ``_migrations._runner`` helpers.

Focus: ``create_index_if_missing`` must never drop an index belonging to
another table when ``unique=True`` is requested for the current table.
CodeRabbit flagged a scenario where two tables held an index of the same
name — the UNIQUE upgrade path would silently DROP the foreign index.
"""

from __future__ import annotations

import sqlite3

from gradata._migrations._runner import create_index_if_missing, index_exists


def test_create_index_if_missing_refuses_to_drop_foreign_table_index():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t_a (id INTEGER, val TEXT)")
        conn.execute("CREATE TABLE t_b (id INTEGER, val TEXT)")
        # Create a non-UNIQUE index on t_a. The name is intentionally
        # ambiguous — CodeRabbit's reproduction relied on the same name
        # being requested for a different table.
        conn.execute("CREATE INDEX shared_name ON t_a(val)")
        assert index_exists(conn, "shared_name")

        # Requesting a UNIQUE index of the same name on t_b must be a no-op
        # (or a skip) rather than dropping the t_a index.
        created = create_index_if_missing(conn, "shared_name", "t_b", "val", unique=True)
        assert created is False

        # The original index on t_a must still be there and still be on t_a.
        row = conn.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type='index' AND name='shared_name'"
        ).fetchone()
        assert row is not None
        assert row[0] == "t_a"
    finally:
        conn.close()


def test_create_index_if_missing_upgrades_nonunique_same_table():
    """Same-table non-UNIQUE → UNIQUE upgrade path still works."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (id INTEGER, val TEXT)")
        conn.execute("CREATE INDEX idx_val ON t(val)")
        created = create_index_if_missing(conn, "idx_val", "t", "val", unique=True)
        assert created is True
        # Confirm the recreated index is UNIQUE.
        for _, name, is_unique, *_ in conn.execute("PRAGMA index_list(t)").fetchall():
            if name == "idx_val":
                assert bool(is_unique)
                break
        else:
            raise AssertionError("idx_val missing after upgrade")
    finally:
        conn.close()


def test_create_index_if_missing_no_op_when_already_unique():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (id INTEGER, val TEXT)")
        conn.execute("CREATE UNIQUE INDEX idx_val ON t(val)")
        created = create_index_if_missing(conn, "idx_val", "t", "val", unique=True)
        assert created is False
    finally:
        conn.close()
