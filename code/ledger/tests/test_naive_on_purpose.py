"""The v0 server is naive, and the book depends on it staying that way until
chapter 10 fixes it. These tests pin the flaw so nobody quietly patches it and
breaks the measurement in chapter 8.
"""

from __future__ import annotations

from ledger import db

WIDEST = """
SELECT title_id, COUNT(*) c FROM licences GROUP BY title_id ORDER BY c DESC LIMIT 1
"""


async def test_the_catalogue_has_a_long_tail():
    widest = db.query(WIDEST)[0]
    assert widest["c"] >= 100, (
        "the generator should produce at least one title with a punishing number "
        "of licences; without it chapter 8 has nothing to measure"
    )


async def test_find_licences_returns_everything_it_finds(client):
    """Deliberately unbounded. When this test starts failing, it is because
    chapter 10 has landed — update it there, not before."""
    widest = db.query(WIDEST)[0]
    async with client:
        result = await client.call_tool(
            "find_licences", {"title_id": widest["title_id"]}
        )
    assert len(result.data) == widest["c"]
