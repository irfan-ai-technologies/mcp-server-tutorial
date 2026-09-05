"""Resources: context the application decides to load, addressed by URI.

The test for whether something belongs here rather than in a tool is not "is it
a read?" — plenty of tools read. It is whether the *client* should be able to
decide to load it without the model asking. An orientation document, a schema, a
named record the user is already looking at: those are resources. A search whose
arguments the model has to choose is a tool.

Resources are also the disclosure channel. Chapter 21 builds on the two
templates below to let a model walk an agreement hierarchy without reading it.
"""

from __future__ import annotations

import json

from ledger import db
from ledger.app import mcp


# region: catalogue_overview
@mcp.resource(
    "ledger://catalogue",
    name="Catalogue overview",
    description=(
        "Size and vocabulary of the catalogue: how many titles and licences "
        "exist, which territories and rights appear, and the periods royalties "
        "are reported for. Load this before reasoning about coverage."
    ),
    mime_type="application/json",
)
def catalogue_overview() -> str:
    """Cheap, stable, and worth having in context before anything else.

    Note what it does not contain: any actual title. An overview that grows with
    the catalogue is not an overview, it is a dump with a friendly name.
    """
    counts = db.one(
        """
        SELECT (SELECT COUNT(*) FROM titles)        AS titles,
               (SELECT COUNT(*) FROM licensees)     AS licensees,
               (SELECT COUNT(*) FROM licences)      AS licences,
               (SELECT COUNT(*) FROM agreements)    AS agreements,
               (SELECT COUNT(*) FROM royalty_lines) AS royalty_lines
        """
    )
    vocabulary = {
        "territories": [r["territory"] for r in db.query(
            "SELECT DISTINCT territory FROM licences ORDER BY territory")],
        "rights": [r["rights"] for r in db.query(
            "SELECT DISTINCT rights FROM licences ORDER BY rights")],
        "statuses": ["active", "expired", "pending"],
        "periods": [r["period"] for r in db.query(
            "SELECT DISTINCT period FROM royalty_lines ORDER BY period")],
    }
    return json.dumps({"counts": counts, "vocabulary": vocabulary}, indent=2)
# endregion: catalogue_overview


# region: title_resource
@mcp.resource(
    "ledger://title/{title_id}",
    name="Title",
    description="One title by identifier, with its licence counts.",
    mime_type="application/json",
)
def title_resource(title_id: str) -> str:
    """The same data get_title returns, addressable rather than callable.

    Both existing is not duplication. The tool is for a model that has to decide
    to look; the resource is for a client that already knows which title the
    user is working on and can put it in context without a round trip.
    """
    title = db.one("SELECT * FROM titles WHERE id = :id", id=title_id)
    if title is None:
        return json.dumps({"error": f"no title {title_id}"})
    counts = db.one(
        """
        SELECT COUNT(*) AS licences, COUNT(DISTINCT territory) AS territories
        FROM licences WHERE title_id = :id
        """,
        id=title_id,
    )
    return json.dumps(title | counts, indent=2)
# endregion: title_resource


@mcp.resource(
    "ledger://agreement/{agreement_id}",
    name="Agreement",
    description=(
        "One agreement, the agreement it amends, and the agreements that amend "
        "it. Follow the child URIs to walk down; follow parent to walk up."
    ),
    mime_type="application/json",
)
def agreement_resource(agreement_id: str) -> str:
    """One node of the hierarchy, with links rather than contents.

    This is the shape chapter 21 argues for: each read hands back enough to
    decide where to go next, and nothing more. A resource that returned the
    whole subtree would be easier to write and useless at depth.
    """
    node = db.one("SELECT * FROM agreements WHERE id = :id", id=agreement_id)
    if node is None:
        return json.dumps({"error": f"no agreement {agreement_id}"})

    children = db.query(
        "SELECT id, kind, reference, signed_on FROM agreements "
        "WHERE parent_id = :id ORDER BY signed_on",
        id=agreement_id,
    )
    licences = db.one(
        "SELECT COUNT(*) AS c FROM licences WHERE agreement_id = :id",
        id=agreement_id,
    )["c"]

    return json.dumps(
        {
            **node,
            "parent": (
                f"ledger://agreement/{node['parent_id']}"
                if node["parent_id"] else None
            ),
            "children": [
                {**c, "uri": f"ledger://agreement/{c['id']}"} for c in children
            ],
            "licences_granted": licences,
        },
        indent=2,
    )
