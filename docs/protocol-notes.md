# Protocol drift log

The specification moves while the book is being written. Anything that changes a factual
claim in a chapter is recorded here, newest first, so a reader can tell what a chapter was
true of and a future revision pass knows what to re-check.

Format: date, what changed, which chapters it touches, and whether they have been updated.

---

## 2026-09-05 — FastMCP 4.0.3 still defaults its HTTP app to sessions

**What.** `FastMCP.http_app()` takes `stateless_http: bool = False`. Left at the default,
the Streamable HTTP app expects the pre-`2026-07-28` session handshake and answers a plain
request with:

```json
{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"Bad Request: Missing session ID"}}
```

This is the per-connection negotiation FastMCP 4 shipped so that older clients keep working
against upgraded servers. It is a compatibility default, not a statement about the
protocol — but it means a server that does nothing special is not speaking the current
specification.

**The trap.** Passing the flag through `mcp.run(transport="http", ...)` does not reach the
app in 4.0.3 — neither `stateless_http=True` nor `stateless=True`. Both are accepted by the
signature and both leave the server demanding a session ID. Only
`mcp.http_app(stateless_http=True)` takes effect. Verified by request, not by reading the
signature.

**What we do.** `ledger.__main__.http_app()` builds the ASGI app explicitly and serves it
with uvicorn. `--sessions` opts back into the legacy app for anyone testing an older client.

**Chapters.** 3 (running it), 11 (going HTTP — this belongs in the text, not a footnote),
12 (why the protocol dropped sessions in the first place).

**Re-check when.** FastMCP changes the default, or forwards the flag through `run()`.

---

## 2026-09-05 — baseline

The book targets revision `2026-07-28`, published as the current specification. No drift
recorded yet.

Reference points as of this date:

| Thing | Version | Note |
|---|---|---|
| Specification | `2026-07-28` | Stateless core; sessions and `initialize` removed |
| FastMCP | 4.0.x | Teaching stack for the book |
| Official Python SDK | `mcp` 2.x | `MCPServer`; used where the seams matter |

Watch list — announced direction, not yet specified, and therefore taught as pattern rather
than protocol:

- **Progressive discovery.** On the roadmap: servers starting with a small tool surface and
  revealing more as the conversation narrows. Chapters 19–21 teach this as an application
  pattern; revisit when it lands in the specification.
- **Tasks.** Currently an official extension (`io.modelcontextprotocol/tasks`), being matured
  for inclusion in the specification. Chapter 15.
- **Agent identity.** DPoP and workload identity federation are direction, not specification.
  Chapter 17 should say so plainly.
- **HTTP-native transport unification.** Local servers over Streamable HTTP on stdio.
  Chapters 3 and 11.
