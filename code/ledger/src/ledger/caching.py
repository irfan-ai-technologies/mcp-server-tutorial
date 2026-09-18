"""Deterministic list ordering, because your tool order is billed to the user.

A client caches the prompt prefix containing your tool definitions. Everything
up to the first difference is a cache hit; everything after it is paid for
again. So if `tools/list` comes back in a different order on two calls — or on
two instances, or after a deploy that reordered an import — the user pays to
re-process a tool surface that did not change.

FastMCP returns tools in registration order, which is stable within a process
and depends on the order of imports in `ledger.server`. That is a load-bearing
property of a file nobody thinks of as load-bearing. Sorting makes it explicit.

The other half of the revision's caching story cannot be done here:

    ttlMs and cacheScope are required on list results by 2026-07-28, and
    FastMCP 4.0.3 does not emit them. See docs/protocol-notes.md.
"""

from __future__ import annotations

from fastmcp.server.middleware import Middleware


# region: ordering
class DeterministicOrder(Middleware):
    """Sort every list endpoint by name, on every instance, forever.

    Cheap to add, invisible when it works, and the alternative is an ordering
    that changes when someone moves an import line — a diff no reviewer would
    ever flag as a performance regression.
    """

    async def on_list_tools(self, context, call_next):
        return sorted(await call_next(context), key=lambda t: t.name)

    async def on_list_resources(self, context, call_next):
        return sorted(await call_next(context), key=lambda r: str(r.uri))

    async def on_list_resource_templates(self, context, call_next):
        return sorted(await call_next(context), key=lambda t: str(t.uri_template))

    async def on_list_prompts(self, context, call_next):
        return sorted(await call_next(context), key=lambda p: p.name)
# endregion: ordering
