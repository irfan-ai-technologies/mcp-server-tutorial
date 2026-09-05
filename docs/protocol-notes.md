# Protocol drift log

The specification moves while the book is being written. Anything that changes a factual
claim in a chapter is recorded here, newest first, so a reader can tell what a chapter was
true of and a future revision pass knows what to re-check.

Format: date, what changed, which chapters it touches, and whether they have been updated.

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
