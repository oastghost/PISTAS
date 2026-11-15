"""Applies db/migrations/NNN_*.sql in order, once each. No manual schema edits."""

import re
import sys
from pathlib import Path

from .config import ROOT
from .db import connect

MIGRATIONS = ROOT / "db" / "migrations"


def _statements(sql: str) -> list[str]:
    without_comments = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in without_comments.split(";") if s.strip()]


def migrate(**connection_overrides) -> list[str]:
    conn = connect(autocommit=True, **connection_overrides)
    applied: list[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migration ("
                "name VARCHAR(100) NOT NULL PRIMARY KEY, "
                "applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB"
            )
            cur.execute("SELECT name FROM schema_migration")
            done = {r["name"] for r in cur.fetchall()}
            for path in sorted(Path(MIGRATIONS).glob("[0-9][0-9][0-9]_*.sql")):
                if path.name in done:
                    continue
                for statement in _statements(path.read_text(encoding="utf-8")):
                    cur.execute(statement)
                cur.execute("INSERT INTO schema_migration (name) VALUES (%s)", (path.name,))
                applied.append(path.name)
    finally:
        conn.close()
    return applied


if __name__ == "__main__":
    names = migrate()
    print("applied:", ", ".join(names) if names else "nothing to do", file=sys.stdout)
