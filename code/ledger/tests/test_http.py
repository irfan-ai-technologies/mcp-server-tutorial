"""The HTTP app, exercised the way a load balancer and a client would.

Chapter 3's version of this was a flag. These tests are what make it a
deployment: the health endpoint answers, requests carry an id, and — the one
that actually matters — a call works with no session and no handshake.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from ledger.http import build


@pytest.fixture
def http():
    with TestClient(build(stateless=True)) as client:
        yield client


def test_health_reports_what_operations_needs(http):
    body = http.get("/health").json()
    assert body["status"] == "ok"
    assert body["titles"] > 0


def test_every_response_carries_a_request_id(http):
    assert http.get("/health").headers["x-request-id"]


def test_an_inbound_request_id_is_honoured(http):
    """A gateway upstream may already have issued one. Minting a second id
    breaks the only thread tying a log line to a user's complaint."""
    response = http.get("/health", headers={"x-request-id": "from-the-gateway"})
    assert response.headers["x-request-id"] == "from-the-gateway"


# region: no_session
def test_a_tool_call_works_with_no_session_and_no_handshake(http):
    """The whole point of 2026-07-28, asserted. No initialize, no
    Mcp-Session-Id, nothing carried from any earlier request."""
    response = http.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_title", "arguments": {"title_id": "T-1000"}},
        },
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 200
    assert "Missing session ID" not in response.text
# endregion: no_session


def test_the_session_based_app_still_exists_for_older_clients(http):
    """--sessions is not dead code: it is how you keep a pre-2026-07-28 client
    working while it migrates."""
    with TestClient(build(stateless=False)) as legacy:
        response = legacy.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert "Missing session ID" in response.text
