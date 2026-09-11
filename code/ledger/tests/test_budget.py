"""The tool surface has a budget, and the build fails when it is exceeded.

Chapter 8 measures what a server costs before anyone asks it anything. This is
that measurement wired to CI. The numbers are deliberately chosen with headroom
— they are not a target, they are a tripwire — and raising one should be an
argued commit rather than a reflex.

Characters, not tokens: exact, tokenizer-independent, and close enough to
proportional that a budget in characters holds a budget in tokens.
"""

from __future__ import annotations

import json

# Raised from 4,000 in the chapter 12 commit: the scan pair added 1,499
# characters and took the surface to 4,472. Worth arguing about — two tools for
# one capability is the most expensive shape there is, and chapter 12 says why
# it is still the right call here. The next increase should be harder than this
# one, which is the whole reason the number is written down.
TOOLS_LIST_BUDGET = 5_000
# Raised from 1,200 in the chapter 10 commit. find_licences went to 1,226
# characters when it gained a limit parameter, a paged return shape and a
# description that warns about breadth — and that trade bought an eight-fold
# reduction in what the tool actually returns. Argued, not reflexive.
ONE_TOOL_BUDGET = 1_400
DESCRIPTION_FLOOR = 25


def wire_size(obj) -> int:
    return len(obj.model_dump_json(exclude_none=True))


async def test_the_tool_surface_fits_its_budget(client):
    async with client:
        tools = await client.list_tools()

    total = sum(wire_size(t) for t in tools)
    assert total <= TOOLS_LIST_BUDGET, (
        f"tools/list is {total:,} characters against a budget of "
        f"{TOOLS_LIST_BUDGET:,}. Raise the budget deliberately, or read "
        f"chapter 19 about not needing to."
    )


async def test_no_single_tool_dominates(client):
    async with client:
        for tool in await client.list_tools():
            size = wire_size(tool)
            assert size <= ONE_TOOL_BUDGET, (
                f"{tool.name} is {size:,} characters — usually a schema that "
                f"grew a nested object or a long enum"
            )


async def test_descriptions_say_something(client):
    """A description short enough to be free is short enough to be useless."""
    async with client:
        for tool in await client.list_tools():
            assert len(tool.description or "") >= DESCRIPTION_FLOOR, (
                f"{tool.name}: {tool.description!r} is not enough for a model "
                f"to choose on"
            )


async def test_no_tool_name_is_a_prefix_of_another(client):
    """Names are read as a set. Overlapping names get chosen between at random,
    and no amount of description repairs it."""
    async with client:
        names = sorted(t.name for t in await client.list_tools())

    for a in names:
        for b in names:
            if a != b:
                assert not b.startswith(a + "_"), f"{b!r} shadows {a!r}"


async def test_the_instructions_block_is_not_empty(mcp_server=None):
    """The cheapest place to establish vocabulary, and the most often left blank."""
    from ledger.app import mcp

    assert mcp.instructions and len(mcp.instructions) > 200, (
        "instructions is where a model learns what the nouns mean; three "
        "sentences there save a dozen careful tool descriptions"
    )


async def test_the_overview_resource_stays_loadable(client):
    """Anything a client may auto-load needs a ceiling someone chose."""
    async with client:
        payload = (await client.read_resource("ledger://catalogue"))[0].text
    assert len(json.loads(payload)["vocabulary"]) >= 3
    assert len(payload) < 4_000
