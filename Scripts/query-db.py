"""
query-db.py — Query the Sprites.ai system database and print formatted results.

Usage:
    python tools/query-db.py "SELECT * FROM deals"
    python tools/query-db.py "SELECT prospect_name, value FROM deals WHERE value > 500"
    python tools/query-db.py "SELECT name, times_used, confidence FROM frameworks"
"""

import sqlite3
import sys
import os

BRAIN_DIR = os.environ.get("BRAIN_DIR", "C:/Users/olive/SpritesWork/brain")
DB_PATH = os.path.join(BRAIN_DIR, "system.db")


def format_table(headers, rows):
    """Format results as an aligned ASCII table."""
    if not rows:
        print("(no rows returned)")
        return

    # Convert all values to strings, handle None
    str_rows = []
    for row in rows:
        str_rows.append([str(v) if v is not None else "NULL" for v in row])

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in str_rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    # Cap column width at 40 chars
    widths = [min(w, 40) for w in widths]

    # Print header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * widths[i] for i in range(len(headers)))

    print(header_line)
    print(sep_line)

    # Print rows
    for row in str_rows:
        vals = []
        for i, val in enumerate(row):
            if len(val) > widths[i]:
                val = val[:widths[i] - 3] + "..."
            vals.append(val.ljust(widths[i]))
        print(" | ".join(vals))

    print(f"\n({len(str_rows)} row{'s' if len(str_rows) != 1 else ''})")


def main():
    if len(sys.argv) < 2:
        print("Usage: python query-db.py \"SQL QUERY\"")
        print()
        print("Examples:")
        print('  python query-db.py "SELECT * FROM deals"')
        print('  python query-db.py "SELECT name, confidence FROM frameworks"')
        print('  python query-db.py "SELECT * FROM audit_scores ORDER BY session"')
        print('  python query-db.py ".tables"')
        sys.exit(1)

    query = sys.argv[1].strip()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Run init-db.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Handle special commands
    if query == ".tables":
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cur.fetchall()
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t[0]}")
            count = cur.fetchone()[0]
            print(f"  {t[0]:20s} ({count} rows)")
        conn.close()
        return

    if query.startswith(".schema"):
        parts = query.split()
        if len(parts) > 1:
            table = parts[1]
            cur.execute(f"SELECT sql FROM sqlite_master WHERE name=?", (table,))
        else:
            cur.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        for row in cur.fetchall():
            print(row[0])
            print()
        conn.close()
        return

    try:
        cur.execute(query)

        if cur.description is None:
            # Non-SELECT statement (INSERT, UPDATE, DELETE)
            conn.commit()
            print(f"OK. {cur.rowcount} row(s) affected.")
        else:
            headers = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            format_table(headers, rows)

    except sqlite3.Error as e:
        print(f"SQL ERROR: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
