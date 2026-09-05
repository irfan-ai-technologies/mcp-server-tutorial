"""SQLite access for the catalogue.

Read-only by design: nothing in the book writes to the catalogue, so the server
opens the file in read-only mode and any attempt to mutate it fails loudly
rather than quietly corrupting a reader's dataset.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# repo_root/code/ledger/src/ledger/db.py -> repo_root
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "data" / "generated" / "ledger.db"


class CatalogueMissing(RuntimeError):
    """The generated database is not where we expected it."""


def db_path() -> Path:
    """Where the catalogue lives. LEDGER_DB overrides, which is how tests point
    at the small fixture without touching the reader's full database."""
    return Path(os.environ.get("LEDGER_DB", DEFAULT_DB))


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = db_path()
    if not path.is_file():
        raise CatalogueMissing(
            f"no catalogue at {path} — run: uv run data/generate.py"
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query(sql: str, **params: object) -> list[dict]:
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def one(sql: str, **params: object) -> dict | None:
    rows = query(sql, **params)
    return rows[0] if rows else None
