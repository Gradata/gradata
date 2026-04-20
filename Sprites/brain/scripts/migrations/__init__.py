"""Gradata brain migrations.

Each migration is a numbered module (001_*.py, 002_*.py, ...) exposing:
    NAME: str
    def up(conn: sqlite3.Connection, tenant_id: str) -> dict

Applied migrations are recorded in the ``migrations`` table.
Run via ``python -m brain.scripts.migrations.run`` or call a specific
migration module directly with ``--brain <path>``.
"""
