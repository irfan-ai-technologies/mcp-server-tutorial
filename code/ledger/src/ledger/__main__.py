"""Run the server.

    ledger                      # stdio, which is what a local client speaks
    ledger --transport http     # Streamable HTTP on 127.0.0.1:8000

Chapter 11 is where HTTP stops being a flag and starts being a decision.
"""

from __future__ import annotations

import argparse

import uvicorn

from ledger.server import mcp

DEFAULT_PORT = 8000


def http_app(stateless: bool = True):
    """The ASGI app, built explicitly rather than through `mcp.run()`.

    Two reasons, and the second one is a trap worth knowing about.

    First, an HTTP server you intend to operate wants its own app: health
    checks, middleware, and a place to mount things. Chapter 11 adds all three
    here.

    Second, `stateless_http` defaults to False in FastMCP 4.0.3 — the app still
    expects the pre-2026-07-28 session handshake and rejects a plain request
    with "Missing session ID". Passing the flag through `mcp.run()` (as either
    `stateless_http=` or `stateless=`) does not reach the app in that version;
    passing it to `http_app()` does. The current protocol has no sessions at
    all, so a server written against it must opt out, and must check that the
    opt-out actually took effect.
    """
    return mcp.http_app(stateless_http=stateless)


def main() -> None:
    ap = argparse.ArgumentParser(prog="ledger", description=__doc__.splitlines()[0])
    ap.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument(
        "--sessions",
        action="store_true",
        help="serve the legacy session-based HTTP app (pre-2026-07-28 clients)",
    )
    args = ap.parse_args()

    if args.transport == "http":
        uvicorn.run(
            http_app(stateless=not args.sessions),
            host=args.host,
            port=args.port,
            log_level="info",
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
