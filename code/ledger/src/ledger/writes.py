"""The first tool in this book that changes something, and what that costs.

Everything until now has been a read, which made `idempotentHint: True` free.
It is not free here, and the reason is chapter 11's: a broken response stream
loses the in-flight request, the client MUST re-issue it as a new request, and
your tool has no way to know it is seeing the same call twice.

So the caller supplies an idempotency key and the server remembers the outcome
against it. Second call, same key: the stored result comes back, nothing runs
again. Same key with different arguments: refused, loudly, because that is a
client bug rather than a retry and silently returning the old answer would hide
it.

The catalogue itself stays read-only. Reservations live in their own database
next to it — a separation worth keeping past the point where it is convenient,
because "the thing we read" and "the thing we write" have different backup,
migration and permission stories.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

from fastmcp.exceptions import ToolError

from ledger import db
from ledger.app import mcp

SCHEMA = """
CREATE TABLE IF NOT EXISTS reservations (
    id            TEXT PRIMARY KEY,
    title_id      TEXT NOT NULL,
    territory     TEXT NOT NULL,
    rights        TEXT NOT NULL,
    window_start  TEXT NOT NULL,
    window_end    TEXT NOT NULL,
    created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency (
    key           TEXT PRIMARY KEY,
    argument_hash TEXT NOT NULL,
    result        TEXT NOT NULL,
    created_at    INTEGER NOT NULL
);
"""


def writes_path() -> Path:
    return Path(os.environ.get("LEDGER_WRITES_DB", db.db_path().parent / "writes.db"))


def _connect() -> sqlite3.Connection:
    path = writes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# region: idempotency
def _fingerprint(args: dict) -> str:
    return hashlib.sha256(
        json.dumps(args, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def once(key: str, args: dict, do):
    """Run `do()` at most once for `key`, and return the same result thereafter.

    The insert is the lock. Two concurrent calls with the same key race to write
    the reservation row; SQLite lets exactly one win on the primary key, and the
    loser reads back what the winner stored. No application-level locking, and
    nothing to release if the process dies mid-call.

    The argument fingerprint is what turns this from a cache into a safety
    mechanism: reusing a key with different arguments is not a retry, it is a
    client bug, and it is refused rather than answered from the store.
    """
    fingerprint = _fingerprint(args)
    conn = _connect()
    try:
        seen = conn.execute(
            "SELECT argument_hash, result FROM idempotency WHERE key = :key",
            {"key": key},
        ).fetchone()

        if seen is not None:
            if seen["argument_hash"] != fingerprint:
                raise ToolError(
                    f"idempotency key {key!r} was already used with different "
                    f"arguments; use a new key for a new request"
                )
            return {**json.loads(seen["result"]), "replayed": True}

        result = do(conn)
        try:
            conn.execute(
                "INSERT INTO idempotency VALUES (:key, :hash, :result, :now)",
                {
                    "key": key,
                    "hash": fingerprint,
                    "result": json.dumps(result),
                    "now": int(time.time()),
                },
            )
        except sqlite3.IntegrityError:
            # Lost the race. The winner's result is authoritative.
            stored = conn.execute(
                "SELECT result FROM idempotency WHERE key = :key", {"key": key}
            ).fetchone()
            return {**json.loads(stored["result"]), "replayed": True}
        return {**result, "replayed": False}
    finally:
        conn.close()
# endregion: idempotency


# region: reserve
@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def reserve_window(
    title_id: str,
    territory: str,
    rights: str,
    window_start: str,
    window_end: str,
    idempotency_key: str,
) -> dict:
    """Hold a licensing window on a title so it cannot be sold twice.

    Safe to retry: call it again with the same idempotency_key and you get the
    original reservation back rather than a second one.

    Args:
        title_id: a title identifier such as T-1042.
        territory: ISO 3166-1 alpha-2 code, e.g. GB.
        rights: one of the rights in the catalogue overview, e.g. svod.
        window_start: ISO date the window opens, e.g. 2027-01-01.
        window_end: ISO date it closes.
        idempotency_key: any unique string you generate for this request.
            Reuse it when retrying the same request; never for a different one.
    """
    if window_end <= window_start:
        raise ToolError(
            f"window_end {window_end} is not after window_start {window_start}"
        )
    if db.one("SELECT id FROM titles WHERE id = :id", id=title_id) is None:
        raise ToolError(f"no title {title_id!r}; find it with search_titles first")

    clash = db.one(
        """
        SELECT id, licensee_id FROM licences
        WHERE title_id = :title_id AND territory = :territory
          AND rights = :rights AND exclusive = 1
          AND window_start < :window_end AND window_end > :window_start
        LIMIT 1
        """,
        title_id=title_id,
        territory=territory,
        rights=rights,
        window_start=window_start,
        window_end=window_end,
    )
    if clash is not None:
        raise ToolError(
            f"licence {clash['id']} already holds exclusive {rights} in "
            f"{territory} across that window; check with find_licences"
        )

    args = {
        "title_id": title_id,
        "territory": territory,
        "rights": rights,
        "window_start": window_start,
        "window_end": window_end,
    }

    def do(conn: sqlite3.Connection) -> dict:
        reservation_id = f"RES-{_fingerprint({**args, 'k': idempotency_key})[:12]}"
        conn.execute(
            "INSERT INTO reservations VALUES "
            "(:id, :title_id, :territory, :rights, :window_start, :window_end, :now)",
            {"id": reservation_id, **args, "now": int(time.time())},
        )
        return {"reservation_id": reservation_id, **args}

    return once(idempotency_key, args, do)
# endregion: reserve
