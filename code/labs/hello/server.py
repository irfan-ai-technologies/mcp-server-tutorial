#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fastmcp>=4.0.3,<5"]
# ///
"""The smallest MCP server that is worth running.

    uv run code/labs/hello/server.py

Twelve lines of actual code. Everything else in this book is about what happens
to those twelve lines when a second client shows up.
"""

from fastmcp import FastMCP

mcp = FastMCP("hello")


@mcp.tool
def days_between(start: str, end: str) -> int:
    """Whole days from start to end. Both dates are ISO 8601, e.g. 2026-07-28."""
    from datetime import date

    return (date.fromisoformat(end) - date.fromisoformat(start)).days


if __name__ == "__main__":
    mcp.run()
