"""The ASGI app, for when ledger is served over HTTP rather than spawned.

Chapter 3 built this as one function to get past a trap. Chapter 11 is where it
becomes something you would put behind a load balancer: a health endpoint that
means what operations thinks it means, a request id on every call, and the
stateless flag set deliberately rather than inherited.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from ledger import db
from ledger.app import mcp


# region: health
async def health(request):
    """Liveness and readiness in one endpoint, which is usually a mistake.

    Liveness asks "is this process wedged"; readiness asks "can it serve".
    ledger can answer both cheaply because its only dependency is a file, so
    they are the same question here. The moment a dependency can be slow, split
    them: a readiness probe that waits on a database will take your whole fleet
    out of rotation during a blip that liveness would have ridden through.
    """
    try:
        rows = db.one("SELECT COUNT(*) AS n FROM titles")["n"]
    except Exception as exc:  # noqa: BLE001 — the point is to report, not raise
        return JSONResponse(
            {"status": "unready", "reason": type(exc).__name__}, status_code=503
        )
    return JSONResponse({"status": "ok", "titles": rows, "protocol": "2026-07-28"})
# endregion: health


# region: request_id
class RequestId(BaseHTTPMiddleware):
    """Give every request an id, and hand it back in the response.

    Without sessions there is no connection to correlate by, so the id is the
    only thread tying a log line to the call a user is complaining about.
    Honour an inbound one — a client or a gateway may already have issued it —
    rather than always minting your own.
    """

    async def dispatch(self, request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
# endregion: request_id


# region: stateless_note
def build(stateless: bool = True):
    """The app ledger actually serves.

    `stateless_http` must be passed here rather than to `mcp.run()`: in FastMCP
    4.0.3 the flag does not reach the app through run(), and the default keeps
    the pre-2026-07-28 session handshake alive. See docs/protocol-notes.md.
    """
    app = mcp.http_app(stateless_http=stateless)
    app.add_middleware(RequestId)
    app.router.routes.append(Route("/health", health))
    return app
# endregion: stateless_note
