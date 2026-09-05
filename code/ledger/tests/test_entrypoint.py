"""The server actually starts as a process and speaks MCP over stdio.

Everything else in the suite talks to the server in-process, which is fast and
proves the logic but not the packaging. This one spawns it the way a client
would, so a broken entry point fails here rather than in a reader's editor.
"""

from __future__ import annotations

import os
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def test_server_starts_and_lists_its_tools(catalogue):
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "ledger"],
        env={**os.environ, "LEDGER_DB": str(catalogue)},
    )
    async with Client(transport) as client:
        tools = {t.name for t in await client.list_tools()}
    assert "search_titles" in tools
