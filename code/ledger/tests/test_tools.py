"""What the server does, exercised through a real MCP client.

No LLM anywhere in here. Everything the book claims about a tool is something a
test can assert, which is the whole argument of chapter 7.
"""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from ledger import db

EXPECTED_TOOLS = {"search_titles", "get_title", "find_licences", "licence_detail"}


async def test_tool_surface_is_what_we_think_it_is(client):
    async with client:
        tools = {t.name for t in await client.list_tools()}
    assert tools == EXPECTED_TOOLS


async def test_every_tool_documents_itself(client):
    """A tool with no description is a tool the model will misuse. Chapter 9
    argues this at length; here it is simply enforced."""
    async with client:
        for tool in await client.list_tools():
            assert tool.description, f"{tool.name} has no description"
            properties = tool.input_schema.get("properties", {})
            assert properties, f"{tool.name} exposes no parameters"
            for name, schema in properties.items():
                assert schema.get("description") or tool.description, (
                    f"{tool.name}.{name} is undocumented"
                )


async def test_search_finds_a_title(client):
    async with client:
        result = await client.call_tool("search_titles", {"query": "the"})
    assert result.data
    assert {"id", "name", "kind"} <= set(result.data[0])


async def test_search_rejects_an_empty_query(client):
    async with client:
        with pytest.raises(ToolError, match="empty"):
            await client.call_tool("search_titles", {"query": "  "})


async def test_search_clamps_the_limit(client):
    async with client:
        result = await client.call_tool(
            "search_titles", {"query": "the", "limit": 10_000}
        )
    assert len(result.data) <= 100


async def test_get_title_counts_its_licences(client):
    title_id = db.one("SELECT id FROM titles LIMIT 1")["id"]
    expected = db.one(
        "SELECT COUNT(*) c FROM licences WHERE title_id = :id", id=title_id
    )["c"]
    async with client:
        result = await client.call_tool("get_title", {"title_id": title_id})
    assert result.data["licences"] == expected


async def test_unknown_title_says_what_to_do_next(client):
    async with client:
        with pytest.raises(ToolError, match="search_titles"):
            await client.call_tool("get_title", {"title_id": "T-nope"})


async def test_find_licences_filters_by_territory(client):
    row = db.one(
        "SELECT title_id, territory FROM licences GROUP BY title_id HAVING COUNT(*) > 3"
    )
    async with client:
        result = await client.call_tool(
            "find_licences",
            {"title_id": row["title_id"], "territory": row["territory"]},
        )
    assert result.data
    assert {r["territory"] for r in result.data} == {row["territory"]}


async def test_find_licences_rejects_an_unknown_status(client):
    async with client:
        with pytest.raises(ToolError, match="active, expired, pending"):
            await client.call_tool(
                "find_licences", {"title_id": "T-1000", "status": "lapsed"}
            )


async def test_licence_detail_walks_up_to_a_master(client):
    licence_id = db.one("SELECT id FROM licences LIMIT 1")["id"]
    async with client:
        result = await client.call_tool("licence_detail", {"licence_id": licence_id})
    chain = result.data["agreement_chain"]
    assert chain, "a licence always sits under at least one agreement"
    assert chain[-1]["kind"] == "master"
    assert chain[-1]["parent_id"] is None
