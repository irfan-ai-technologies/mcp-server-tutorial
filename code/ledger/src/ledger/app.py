"""The server object itself, and nothing else.

Tools, resources and prompts live in their own modules and register themselves
against this instance. Keeping the instance separate is what stops those modules
importing each other in a circle.

`instructions` is the one piece of free text a client shows the model before any
tool is called. It is worth more than any single tool description: it is where
the model learns what the words in this domain mean.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ledger.caching import DeterministicOrder

mcp = FastMCP(
    name="ledger",
    instructions=(
        "Rights catalogue for a media licensing operation.\n\n"
        "A title is a film, series, documentary or short. A licence grants one "
        "licensee a named right (svod, avod, theatrical, inflight and so on) in "
        "one territory, for a window of time, under an agreement. Agreements "
        "nest: amendments hang off masters, side letters off amendments, and "
        "the terms that apply are the ones nearest the leaf.\n\n"
        "Start from search_titles; every other tool takes an identifier it "
        "returns. Territories are ISO 3166-1 alpha-2 codes. Money is in minor "
        "units."
    ),
)

# Chapter 14: the same order on every instance and every call, so a client's
# prompt cache survives a deploy that happened to reorder an import.
mcp.add_middleware(DeterministicOrder())
