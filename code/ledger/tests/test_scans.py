"""Walking every licence on a title, across calls that share nothing."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from ledger import db

WIDEST = """
SELECT title_id, COUNT(*) c FROM licences GROUP BY title_id ORDER BY c DESC LIMIT 1
"""


async def test_a_scan_walks_every_row_exactly_once(client):
    widest = db.query(WIDEST)[0]
    seen: list[str] = []

    async with client:
        opened = (
            await client.call_tool(
                "open_licence_scan", {"title_id": widest["title_id"]}
            )
        ).data
        handle = opened["handle"]

        while handle:
            page = (
                await client.call_tool("read_licence_scan", {"handle": handle})
            ).data
            seen.extend(row["id"] for row in page["licences"])
            handle = page["handle"]

    assert len(seen) == opened["total"] == widest["c"]
    assert len(set(seen)) == len(seen), "a row came back on two pages"


async def test_re_reading_a_handle_returns_the_same_page(client):
    """The position lives in the handle, not on the server, which is what makes
    a retry after a dropped stream safe rather than a way to skip rows."""
    widest = db.query(WIDEST)[0]
    async with client:
        handle = (
            await client.call_tool(
                "open_licence_scan", {"title_id": widest["title_id"]}
            )
        ).data["handle"]

        first = (await client.call_tool("read_licence_scan", {"handle": handle})).data
        again = (await client.call_tool("read_licence_scan", {"handle": handle})).data

    assert [r["id"] for r in first["licences"]] == [r["id"] for r in again["licences"]]


# region: another_instance
async def test_a_handle_survives_the_server_it_came_from(client):
    """The point of the exercise. A handle minted by one instance is honoured by
    another that has never heard of it — here, a freshly constructed server
    object standing in for a second process behind a load balancer."""
    widest = db.query(WIDEST)[0]
    async with client:
        handle = (
            await client.call_tool(
                "open_licence_scan", {"title_id": widest["title_id"]}
            )
        ).data["handle"]

    import importlib

    from fastmcp import Client

    import ledger.server

    other_instance = Client(importlib.reload(ledger.server).mcp)
    async with other_instance as elsewhere:
        page = (
            await elsewhere.call_tool("read_licence_scan", {"handle": handle})
        ).data

    assert page["returned"] > 0
# endregion: another_instance


async def test_opening_a_scan_on_nothing_says_what_to_do(client):
    async with client:
        with pytest.raises(ToolError, match="get_title"):
            await client.call_tool("open_licence_scan", {"title_id": "T-nope"})


async def test_a_forged_handle_is_refused_by_the_tool(client):
    async with client:
        with pytest.raises(ToolError, match="verification|malformed"):
            await client.call_tool(
                "read_licence_scan", {"handle": "licence_scan.bm90.aGE"}
            )
