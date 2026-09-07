"""What find_licences returns, now that chapter 10 has landed.

This file replaces tests/test_naive_on_purpose.py, which pinned the unbounded
behaviour so that chapter 8's measurement stayed reproducible until it was
deliberately changed. That promise has now been kept, and these tests hold the
new shape in place.
"""

from __future__ import annotations

from ledger import db
from ledger.tools import DEFAULT_LIMIT, MAX_LIMIT

WIDEST = """
SELECT title_id, COUNT(*) c FROM licences GROUP BY title_id ORDER BY c DESC LIMIT 1
"""


async def test_the_catalogue_still_has_a_long_tail():
    widest = db.query(WIDEST)[0]
    assert widest["c"] >= 100, (
        "the generator should keep producing a title with a punishing number of "
        "licences; without it chapters 8 and 10 have nothing to argue about"
    )


async def test_a_broad_query_is_paged_not_dumped(client):
    widest = db.query(WIDEST)[0]
    async with client:
        result = await client.call_tool(
            "find_licences", {"title_id": widest["title_id"]}
        )
    data = result.data

    assert data["total"] == widest["c"]
    assert data["returned"] == DEFAULT_LIMIT
    assert len(data["licences"]) == DEFAULT_LIMIT
    assert data["not_shown"] == widest["c"] - DEFAULT_LIMIT


async def test_a_truncated_result_says_how_to_narrow(client):
    """A total tells the model it asked too broadly. The histograms tell it what
    to ask instead. Guidance without the counts is just an apology."""
    widest = db.query(WIDEST)[0]
    async with client:
        data = (
            await client.call_tool("find_licences", {"title_id": widest["title_id"]})
        ).data

    assert sum(data["by_territory"].values()) == data["total"]
    assert sum(data["by_status"].values()) == data["total"]
    assert str(data["total"]) in data["guidance"]
    assert "territory" in data["guidance"]


async def test_a_complete_result_carries_no_guidance(client):
    """Do not pay for advice nobody needs. When everything fits, the envelope is
    total, returned and the rows."""
    row = db.one(
        "SELECT title_id, territory FROM licences GROUP BY title_id, territory "
        "HAVING COUNT(*) BETWEEN 1 AND 5 LIMIT 1"
    )
    async with client:
        data = (
            await client.call_tool(
                "find_licences",
                {"title_id": row["title_id"], "territory": row["territory"]},
            )
        ).data

    assert data["returned"] == data["total"]
    assert "guidance" not in data
    assert "by_territory" not in data


async def test_the_limit_is_clamped(client):
    widest = db.query(WIDEST)[0]
    async with client:
        data = (
            await client.call_tool(
                "find_licences", {"title_id": widest["title_id"], "limit": 10_000}
            )
        ).data
    assert data["returned"] == min(MAX_LIMIT, data["total"])


async def test_the_broad_result_is_an_order_of_magnitude_smaller(client):
    """The measurement chapter 10 is built on, as an assertion.

    Before paging, this call serialised to roughly 39,000 characters. The
    envelope — twenty rows, two histograms and a sentence — is under 8,000, and
    it tells the model more than the dump did."""
    import json

    widest = db.query(WIDEST)[0]
    async with client:
        data = (
            await client.call_tool("find_licences", {"title_id": widest["title_id"]})
        ).data

    assert len(json.dumps(data)) < 8_000
