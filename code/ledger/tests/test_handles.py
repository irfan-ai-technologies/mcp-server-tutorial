"""Handles replace sessions, so they have to be as trustworthy as one.

Four properties matter and each has a test: a handle cannot be forged, cannot be
edited, cannot outlive its expiry, and cannot be used for something other than
what it was issued for. Everything else in chapter 12 rests on those.
"""

from __future__ import annotations

import json
import time

import pytest
from fastmcp.exceptions import ToolError

from ledger import handles


def test_a_handle_round_trips():
    token = handles.mint("demo", {"after": "LIC-10000"})
    assert handles.read(token, "demo")["after"] == "LIC-10000"


def test_a_handle_is_readable_but_not_writable():
    """Nothing secret goes inside a handle — a client can decode one. What it
    cannot do is change one and have it still verify."""
    token = handles.mint("demo", {"after": "LIC-10000"})
    kind, payload, signature = token.split(".")

    body = json.loads(handles._unb64(payload))
    assert body["after"] == "LIC-10000"  # readable, on purpose

    body["after"] = "LIC-99999"
    forged = f"{kind}.{handles._b64(json.dumps(body).encode())}.{signature}"
    with pytest.raises(ToolError, match="failed verification"):
        handles.read(forged, "demo")


def test_a_handle_from_another_secret_is_rejected(monkeypatch):
    token = handles.mint("demo", {"after": "LIC-10000"})
    monkeypatch.setenv("LEDGER_HANDLE_SECRET", "a-different-key")
    with pytest.raises(ToolError, match="failed verification"):
        handles.read(token, "demo")


def test_an_expired_handle_says_to_start_again():
    token = handles.mint("demo", {"after": ""}, ttl_seconds=-1)
    with pytest.raises(ToolError, match="expired"):
        handles.read(token, "demo")


def test_a_handle_is_bound_to_its_purpose():
    """A scan handle must not be accepted where an export handle is expected,
    even though both verify. Kind confusion is how one feature's token becomes
    another feature's authorisation."""
    token = handles.mint("licence_scan", {"after": ""})
    with pytest.raises(ToolError, match="handle is needed"):
        handles.read(token, "royalty_export")


def test_the_expiry_is_inside_the_signature():
    token = handles.mint("demo", {"after": ""}, ttl_seconds=60)
    body = handles.read(token, "demo")
    assert body["exp"] > time.time()

    body["exp"] += 86_400
    kind, _, signature = token.split(".")
    extended = f"{kind}.{handles._b64(json.dumps(body).encode())}.{signature}"
    with pytest.raises(ToolError, match="failed verification"):
        handles.read(extended, "demo")
