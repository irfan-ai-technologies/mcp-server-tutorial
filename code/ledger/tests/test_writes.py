"""The write tool, and the retry that must not become a second reservation."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastmcp.exceptions import ToolError

from ledger import db, writes


@pytest.fixture(autouse=True)
def writes_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_WRITES_DB", str(tmp_path / "writes.db"))


def a_free_slot() -> dict:
    """A title, territory and rights with no exclusive licence in 2031."""
    row = db.one(
        """
        SELECT t.id AS title_id FROM titles t
        WHERE NOT EXISTS (
            SELECT 1 FROM licences l
            WHERE l.title_id = t.id AND l.exclusive = 1
              AND l.territory = 'GB' AND l.rights = 'svod'
        ) LIMIT 1
        """
    )
    return {
        "title_id": row["title_id"],
        "territory": "GB",
        "rights": "svod",
        "window_start": "2031-01-01",
        "window_end": "2031-12-31",
    }


async def test_a_reservation_is_made_once(client):
    args = a_free_slot() | {"idempotency_key": uuid.uuid4().hex}
    async with client:
        first = (await client.call_tool("reserve_window", args)).data
    assert first["replayed"] is False
    assert first["reservation_id"].startswith("RES-")


# region: retry
async def test_retrying_returns_the_original_rather_than_a_second(client):
    """The failure this exists to prevent: a dropped stream, a client reissuing
    the request as the specification tells it to, and a window reserved twice."""
    args = a_free_slot() | {"idempotency_key": uuid.uuid4().hex}

    async with client:
        first = (await client.call_tool("reserve_window", args)).data
        again = (await client.call_tool("reserve_window", args)).data

    assert again["replayed"] is True
    assert again["reservation_id"] == first["reservation_id"]

    conn = writes._connect()
    rows = conn.execute("SELECT COUNT(*) c FROM reservations").fetchone()["c"]
    conn.close()
    assert rows == 1
# endregion: retry


async def test_reusing_a_key_for_different_arguments_is_refused(client):
    """A cache would return the old answer. That hides a client bug in which two
    different requests share a key, and the second one silently never happens."""
    key = uuid.uuid4().hex
    first = a_free_slot() | {"idempotency_key": key}
    second = first | {"territory": "DE"}

    async with client:
        await client.call_tool("reserve_window", first)
        with pytest.raises(ToolError, match="already used with different arguments"):
            await client.call_tool("reserve_window", second)


async def test_concurrent_identical_calls_make_one_reservation(client):
    """Two in-flight retries of the same request, which is what a flaky
    connection actually produces. The insert is the lock."""
    args = a_free_slot() | {"idempotency_key": uuid.uuid4().hex}

    async with client:
        results = await asyncio.gather(
            *(client.call_tool("reserve_window", args) for _ in range(5))
        )

    ids = {r.data["reservation_id"] for r in results}
    assert len(ids) == 1
    assert sum(1 for r in results if r.data["replayed"] is False) == 1


async def test_an_exclusive_clash_is_refused_with_the_licence_id(client):
    clash = db.one(
        "SELECT title_id, territory, rights, window_start, window_end "
        "FROM licences WHERE exclusive = 1 LIMIT 1"
    )
    async with client:
        with pytest.raises(ToolError, match="already holds exclusive"):
            await client.call_tool(
                "reserve_window",
                {**dict(clash), "idempotency_key": uuid.uuid4().hex},
            )


async def test_a_backwards_window_is_refused_before_anything_is_written(client):
    args = a_free_slot() | {
        "window_start": "2031-12-31",
        "window_end": "2031-01-01",
        "idempotency_key": uuid.uuid4().hex,
    }
    async with client:
        with pytest.raises(ToolError, match="is not after"):
            await client.call_tool("reserve_window", args)

    conn = writes._connect()
    assert conn.execute("SELECT COUNT(*) c FROM reservations").fetchone()["c"] == 0
    conn.close()
