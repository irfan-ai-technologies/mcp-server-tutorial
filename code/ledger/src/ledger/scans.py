"""A walk over every licence on a title, one page at a time, without sessions.

Chapter 10 deliberately left `find_licences` without a cursor, on the grounds
that a model told "180 matched, here are 20" should nearly always narrow rather
than page. This is the case where it should not: a reconciliation that has to
touch every row.

The handle returned by each call is a continuation. It carries the query and the
position, signed, so the next call can land on any instance.
"""

from __future__ import annotations

from fastmcp.exceptions import ToolError

from ledger import db, handles
from ledger.app import mcp

PAGE = 50
SCAN = "licence_scan"


def _page(title_id: str, territory: str | None, after_id: str) -> list[dict]:
    return db.query(
        """
        SELECT l.id, l.territory, l.rights, l.exclusive,
               l.window_start, l.window_end, l.status, e.name AS licensee
        FROM licences l
        JOIN licensees e ON e.id = l.licensee_id
        WHERE l.title_id = :title_id
          AND (:territory IS NULL OR l.territory = :territory)
          AND l.id > :after_id
        ORDER BY l.id
        LIMIT :limit
        """,
        title_id=title_id,
        territory=territory,
        after_id=after_id,
        limit=PAGE,
    )


# region: open_scan
@mcp.tool(annotations={"readOnlyHint": True, "idempotentHint": True})
def open_licence_scan(title_id: str, territory: str | None = None) -> dict:
    """Begin walking every licence on a title, for work that needs all of them.

    Most questions do not need this — find_licences answers them in one call and
    tells you what it left out. Use a scan for reconciliation, export, or any
    task where missing a row is a defect.

    Args:
        title_id: a title identifier such as T-1042.
        territory: ISO 3166-1 alpha-2 code. Omit to walk every territory.
    """
    total = db.one(
        """
        SELECT COUNT(*) AS n FROM licences
        WHERE title_id = :title_id
          AND (:territory IS NULL OR territory = :territory)
        """,
        title_id=title_id,
        territory=territory,
    )["n"]
    if total == 0:
        raise ToolError(
            f"no licences on {title_id!r}"
            + (f" in {territory}" if territory else "")
            + "; check the title with get_title first"
        )

    handle = handles.mint(
        SCAN, {"title_id": title_id, "territory": territory, "after": ""}
    )
    return {
        "handle": handle,
        "total": total,
        "page_size": PAGE,
        "pages": -(-total // PAGE),
        "next_step": "pass handle to read_licence_scan; it returns the next handle",
    }
# endregion: open_scan


# region: read_scan
@mcp.tool(annotations={"readOnlyHint": True, "idempotentHint": True})
def read_licence_scan(handle: str) -> dict:
    """Read the next page of a scan and get the handle for the page after it.

    Re-reading the same handle returns the same page: the position is in the
    handle you were given, not on the server. That is what makes a retry after a
    dropped connection safe.

    Args:
        handle: the handle from open_licence_scan, or from the previous call.
    """
    state = handles.read(handle, SCAN)
    rows = _page(state["title_id"], state["territory"], state["after"])

    done = len(rows) < PAGE
    return {
        "licences": rows,
        "returned": len(rows),
        "done": done,
        "handle": None
        if done
        else handles.mint(
            SCAN,
            {
                "title_id": state["title_id"],
                "territory": state["territory"],
                "after": rows[-1]["id"],
            },
        ),
    }
# endregion: read_scan
