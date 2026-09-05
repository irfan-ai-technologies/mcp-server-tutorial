"""Resources are addressable, cheap, and honest about what they don't contain."""

from __future__ import annotations

import json

from ledger import db


async def test_the_overview_does_not_grow_with_the_catalogue(client):
    """An overview that lists every title is a dump. This one stays small no
    matter how large the catalogue gets, which is the only reason it is safe to
    load before anything else."""
    async with client:
        payload = json.loads((await client.read_resource("ledger://catalogue"))[0].text)

    assert payload["counts"]["titles"] > 0
    assert payload["vocabulary"]["rights"]
    assert "titles" not in payload["vocabulary"]
    assert len(json.dumps(payload)) < 4_000


async def test_a_title_is_readable_by_uri(client):
    title_id = db.one("SELECT id FROM titles LIMIT 1")["id"]
    async with client:
        payload = json.loads(
            (await client.read_resource(f"ledger://title/{title_id}"))[0].text
        )
    assert payload["id"] == title_id
    assert "licences" in payload


async def test_an_unknown_title_reads_as_an_error_not_a_crash(client):
    async with client:
        payload = json.loads(
            (await client.read_resource("ledger://title/T-nope"))[0].text
        )
    assert "error" in payload


async def test_an_agreement_links_rather_than_nests(client):
    """The whole point of chapter 21: each read hands back enough to choose the
    next one, and no more. A node with children must not inline them."""
    parent = db.one(
        "SELECT parent_id FROM agreements WHERE parent_id IS NOT NULL LIMIT 1"
    )["parent_id"]

    async with client:
        payload = json.loads(
            (await client.read_resource(f"ledger://agreement/{parent}"))[0].text
        )

    assert payload["children"], "this agreement was chosen because it has children"
    for child in payload["children"]:
        assert child["uri"].startswith("ledger://agreement/")
        assert "children" not in child, "a child must be a link, not a subtree"


async def test_walking_up_from_a_leaf_reaches_a_master(client):
    leaf = db.one(
        "SELECT id FROM agreements WHERE kind = 'side_letter' LIMIT 1"
    ) or db.one("SELECT id FROM agreements WHERE kind = 'amendment' LIMIT 1")

    uri = f"ledger://agreement/{leaf['id']}"
    seen = []
    async with client:
        while uri:
            payload = json.loads((await client.read_resource(uri))[0].text)
            seen.append(payload["kind"])
            uri = payload["parent"]

    assert seen[-1] == "master"
    assert len(seen) >= 2
