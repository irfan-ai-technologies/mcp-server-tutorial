# hello

The twelve-line server from chapter 3, kept separate from `ledger` so it stays twelve
lines. It has one tool, no dependencies beyond FastMCP, and no database.

```bash
uv run server.py                     # stdio; a client will spawn it this way
```

Its only job is to be small enough that nothing in it is mysterious.
