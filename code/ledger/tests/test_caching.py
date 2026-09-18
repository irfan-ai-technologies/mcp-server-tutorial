"""Ordering is a caching decision, so it gets a test rather than a convention."""

from __future__ import annotations


async def test_tools_come_back_sorted(client):
    async with client:
        names = [t.name for t in await client.list_tools()]
    assert names == sorted(names), (
        "tools/list must be deterministic — registration order depends on the "
        "import order in ledger.server, which nobody reviews as load-bearing"
    )


async def test_the_order_is_the_same_on_a_second_call(client):
    async with client:
        first = [t.name for t in await client.list_tools()]
        second = [t.name for t in await client.list_tools()]
    assert first == second


async def test_the_order_survives_a_different_instance(client):
    """Two processes behind a load balancer must agree, or half the requests
    invalidate the cache the other half just warmed."""
    import importlib

    from fastmcp import Client

    import ledger.server

    async with client:
        here = [t.name for t in await client.list_tools()]

    other = Client(importlib.reload(ledger.server).mcp)
    async with other as elsewhere:
        there = [t.name for t in await elsewhere.list_tools()]

    assert here == there


async def test_resources_and_prompts_are_sorted_too(client):
    async with client:
        resources = [str(r.uri) for r in await client.list_resources()]
        templates = [
            str(t.uri_template) for t in await client.list_resource_templates()
        ]
        prompts = [p.name for p in await client.list_prompts()]

    assert resources == sorted(resources)
    assert templates == sorted(templates)
    assert prompts == sorted(prompts)
