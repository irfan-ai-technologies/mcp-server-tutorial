# ledger

The MCP server the book builds, chapter by chapter. Right now it is v0: four tools over
the synthetic rights catalogue, correct and tested, and deliberately naive in the places
later chapters fix.

```bash
uv run ../../data/generate.py        # once — creates the catalogue
uv sync
uv run pytest                        # 13 tests, no LLM involved
uv run ledger                        # stdio
uv run ledger --transport http       # stateless Streamable HTTP on :8000
```

`LEDGER_DB` overrides the catalogue path; the tests use it to point at a small fixture.

## Tools

| Tool | What it does |
|---|---|
| `search_titles` | Find titles by name — the entry point for everything else |
| `get_title` | One title, with a count of the licences hanging off it |
| `find_licences` | Licences for a title, optionally filtered by territory and status |
| `licence_detail` | One licence in full, plus the chain of agreements above it |

## What is deliberately wrong with it

`find_licences` has no limit and returns no total. One title in the catalogue carries 180
licences across 33 territories, and asking about it returns every row. That is not an
oversight — chapter 8 measures what it costs and chapter 10 fixes it, and
`tests/test_naive_on_purpose.py` pins the behaviour so it does not get quietly patched in
between.
