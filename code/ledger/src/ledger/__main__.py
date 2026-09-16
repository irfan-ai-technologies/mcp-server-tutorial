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


# region: http_app
def http_app(stateless: bool = True):
    """The ASGI app. Chapter 11 moved the detail into ledger.http."""
    from ledger.http import build

    return build(stateless=stateless)
# endregion: http_app


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
