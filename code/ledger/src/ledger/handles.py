"""Server-minted handles: state after the protocol stopped keeping any.

The 2026-07-28 revision removed protocol-level sessions. A server that needs to
remember anything between two calls mints an explicit handle and takes it back
as an ordinary tool argument.

There are two ways to build one and the choice matters more than the code.

**Signed, self-contained** — the handle *is* the state. Everything needed to
resume is encoded in the token and signed so a client cannot forge or edit it.
No storage, no eviction, no coordination: any instance behind any load balancer
can serve the next call, which is exactly what statelessness was for. The cost
is that the state must be small, and that it describes a *query* rather than a
*snapshot* — rows that change between calls are seen as they are now.

**Stored** — the handle is a key into a shared store holding a materialised
result. That buys snapshot isolation and unbounded size, and it costs you a
shared store, a TTL policy, an eviction story and a new way for one instance to
disagree with another. Chapter 12 argues that most servers reach for this when
they need the first one.

This module implements the signed kind. The token is
``kind.payload.signature``: a URL-safe base64 JSON body with an expiry, and an
HMAC over it. Nothing secret goes inside — a client can read a handle, it simply
cannot change one.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from fastmcp.exceptions import ToolError

# region: secret
DEV_SECRET = "ledger-dev-secret-not-for-anything-real"


def secret() -> bytes:
    """The signing key.

    A per-process random key would be worse than this constant, not better: it
    would invalidate every outstanding handle on deploy and make two instances
    disagree, which is precisely the failure statelessness was meant to remove.
    In production this comes from the environment and is shared by every
    instance, like any other signing key.
    """
    return os.environ.get("LEDGER_HANDLE_SECRET", DEV_SECRET).encode()
# endregion: secret


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# region: mint
def mint(kind: str, data: dict, ttl_seconds: int = 900) -> str:
    """Issue a handle carrying `data`, valid for `ttl_seconds`.

    The expiry is inside the signed body, so it cannot be extended by the holder
    and no server has to remember when this was issued.
    """
    body = {**data, "kind": kind, "exp": int(time.time()) + ttl_seconds}
    payload = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64(hmac.new(secret(), payload.encode(), hashlib.sha256).digest())
    return f"{kind}.{payload}.{signature}"


def read(token: str, expected_kind: str) -> dict:
    """Verify a handle and return what it carries.

    Every failure is a ToolError with a message the model can act on, because
    every one of them is recoverable by starting again — and a model that is
    told "expired, open a new scan" will do that, where one told "invalid
    token" will retry the same token.
    """
    try:
        kind, payload, signature = token.split(".")
    except ValueError:
        raise ToolError(
            "malformed handle; handles come from open_licence_scan and are "
            "passed back unchanged"
        ) from None

    expected = _b64(hmac.new(secret(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ToolError("handle failed verification; open a new scan")

    if kind != expected_kind:
        raise ToolError(
            f"this is a {kind!r} handle, but a {expected_kind!r} handle is needed"
        )

    body = json.loads(_unb64(payload))
    if body["exp"] < time.time():
        raise ToolError(
            "handle expired; open a new scan. Handles last 15 minutes so that "
            "no instance has to remember them"
        )
    return body
# endregion: mint
