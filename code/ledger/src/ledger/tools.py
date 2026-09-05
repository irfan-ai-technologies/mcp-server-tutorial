"""The four tools ledger v0 exposes.

This is the naive version and it stays naive until chapter 10. It is correct,
it is tested, and it will fall over the moment a model asks about a popular
title — which is exactly what chapter 8 needs to measure.
"""

from __future__ import annotations

from fastmcp.exceptions import ToolError

from ledger import db
from ledger.app import mcp


# region: search_titles
@mcp.tool
def search_titles(query: str, limit: int = 20) -> list[dict]:
    """Find titles by name. Use this first — every other tool takes a title_id.

    Args:
        query: words from the title's name; matching is case-insensitive.
        limit: maximum titles to return, 1-100.
    """
    if not query.strip():
        raise ToolError("query is empty; pass one or more words from the title name")
    limit = max(1, min(limit, 100))
    return db.query(
        """
        SELECT id, name, kind, release_year, original_language
        FROM titles
        WHERE name LIKE :pattern
        ORDER BY release_year DESC, name
        LIMIT :limit
        """,
        pattern=f"%{query.strip()}%",
        limit=limit,
    )
# endregion: search_titles


@mcp.tool
def get_title(title_id: str) -> dict:
    """Everything known about one title, plus how many licences it carries.

    Args:
        title_id: a title identifier such as T-1042, from search_titles.
    """
    title = db.one("SELECT * FROM titles WHERE id = :id", id=title_id)
    if title is None:
        raise ToolError(f"no title {title_id!r}; use search_titles to find one")

    counts = db.one(
        """
        SELECT COUNT(*) AS licences,
               SUM(status = 'active') AS active,
               COUNT(DISTINCT territory) AS territories
        FROM licences WHERE title_id = :id
        """,
        id=title_id,
    )
    return title | counts


# region: find_licences
@mcp.tool
def find_licences(
    title_id: str,
    territory: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """Licences attached to a title.

    Args:
        title_id: a title identifier such as T-1042.
        territory: ISO 3166-1 alpha-2 code, e.g. GB. Omit for every territory.
        status: active, expired or pending. Omit for all three.
    """
    if status is not None and status not in {"active", "expired", "pending"}:
        raise ToolError(
            f"status {status!r} is not one of: active, expired, pending"
        )

    # No limit, and no total. A handful of titles carry 180 licences, and asking
    # about one of them returns every row. Chapter 8 prices that; chapter 10
    # fixes it. Leaving it naive here is the point.
    return db.query(
        """
        SELECT l.id, l.territory, l.rights, l.exclusive,
               l.window_start, l.window_end, l.status,
               e.name AS licensee, l.agreement_id
        FROM licences l
        JOIN licensees e ON e.id = l.licensee_id
        WHERE l.title_id = :title_id
          AND (:territory IS NULL OR l.territory = :territory)
          AND (:status IS NULL OR l.status = :status)
        ORDER BY l.window_start DESC, l.id
        """,
        title_id=title_id,
        territory=territory,
        status=status,
    )
# endregion: find_licences


@mcp.tool
def licence_detail(licence_id: str) -> dict:
    """One licence in full, with the chain of agreements it sits under.

    Args:
        licence_id: a licence identifier such as LIC-10420, from find_licences.
    """
    licence = db.one(
        """
        SELECT l.*, e.name AS licensee, e.kind AS licensee_kind, t.name AS title
        FROM licences l
        JOIN licensees e ON e.id = l.licensee_id
        JOIN titles t ON t.id = l.title_id
        WHERE l.id = :id
        """,
        id=licence_id,
    )
    if licence is None:
        raise ToolError(f"no licence {licence_id!r}")

    # Amendments hang off masters, and side letters off amendments. Walking the
    # chain here is fine for one licence; chapter 21 turns it into something a
    # model can navigate across the whole corpus.
    chain: list[dict] = []
    agreement_id = licence["agreement_id"]
    while agreement_id:
        node = db.one("SELECT * FROM agreements WHERE id = :id", id=agreement_id)
        if node is None:
            break
        chain.append(node)
        agreement_id = node["parent_id"]

    return licence | {"agreement_chain": chain}
