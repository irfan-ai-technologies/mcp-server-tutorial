"""The four tools ledger v0 exposes.

This is the naive version and it stays naive until chapter 10. It is correct,
it is tested, and it will fall over the moment a model asks about a popular
title — which is exactly what chapter 8 needs to measure.
"""

from __future__ import annotations

from typing import Literal

from fastmcp.exceptions import ToolError

from ledger import db
from ledger.app import mcp

# region: search_titles
READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}


@mcp.tool(annotations=READ_ONLY)
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


@mcp.tool(annotations=READ_ONLY)
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
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@mcp.tool(annotations=READ_ONLY)
def find_licences(
    title_id: str,
    territory: str | None = None,
    status: Literal["active", "expired", "pending"] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    """Licences attached to a title, newest window first.

    Returns a page of licences plus the total that matched. When more matched
    than were returned, the result also carries counts by territory and status
    so you can narrow without guessing.

    Args:
        title_id: a title identifier such as T-1042.
        territory: ISO 3166-1 alpha-2 code, e.g. GB. Omit for every territory —
            a widely-licensed title can match well over a hundred.
        status: active, expired or pending. Omit for all three.
        limit: rows to return, 1-100. The default of 20 is usually enough to
            answer a question; ask for more only when you know you need it.
    """
    limit = max(1, min(limit, MAX_LIMIT))
    where = """
        FROM licences l
        JOIN licensees e ON e.id = l.licensee_id
        WHERE l.title_id = :title_id
          AND (:territory IS NULL OR l.territory = :territory)
          AND (:status IS NULL OR l.status = :status)
    """
    params = {"title_id": title_id, "territory": territory, "status": status}

    # Count first. A total costs one cheap query and is the single most useful
    # thing you can hand a model that has asked too broad a question.
    total = db.one(f"SELECT COUNT(*) AS n {where}", **params)["n"]

    rows = db.query(
        f"""
        SELECT l.id, l.territory, l.rights, l.exclusive,
               l.window_start, l.window_end, l.status,
               e.name AS licensee, l.agreement_id
        {where}
        ORDER BY l.window_start DESC, l.id
        LIMIT :limit
        """,
        **params,
        limit=limit,
    )

    result: dict = {"total": total, "returned": len(rows), "licences": rows}
    if total > len(rows):
        # Not the rows themselves — the shape of what was left out, so the next
        # call can be specific. Two small histograms beat a hundred more rows.
        result["not_shown"] = total - len(rows)
        result["by_territory"] = {
            r["territory"]: r["n"]
            for r in db.query(
                f"SELECT l.territory, COUNT(*) AS n {where} "
                "GROUP BY l.territory ORDER BY n DESC, l.territory",
                **params,
            )
        }
        result["by_status"] = {
            r["status"]: r["n"]
            for r in db.query(
                f"SELECT l.status, COUNT(*) AS n {where} GROUP BY l.status",
                **params,
            )
        }
        result["guidance"] = (
            f"{total} licences match; {len(rows)} returned. Narrow by territory "
            f"or status using the counts above, or raise limit up to {MAX_LIMIT} "
            f"if you genuinely need every row."
        )
    return result
# endregion: find_licences


@mcp.tool(annotations=READ_ONLY)
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
