#!/usr/bin/env python3
"""Price a server's tool surface, and the results it hands back.

    uv run --project ../../ledger python audit.py           # table + report.json + report.md

Two numbers per thing measured. **Characters** are exact and anyone can verify
them. **Tokens** are an estimate unless a real tokenizer is installed, and the
report records which was used — see `measure()` below.

That distinction is deliberate rather than a limitation. There is no single
token count for a piece of text: Claude, GPT and Llama tokenize differently, and
a number quoted without a tokenizer is folklore. What is invariant is the shape
of the answer — a surface that costs a few thousand tokens, a result that can
cost twenty times more than the surface that produced it — and that shape is
what the chapters argue from.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from fastmcp import Client

from ledger.server import mcp

HERE = Path(__file__).resolve().parent

# Characters per token for dense JSON and schema text. English prose runs closer
# to 4.0; identifiers, punctuation and quoted keys push JSON denser than that.
# Only used when no tokenizer is available; the report says which applied.
CHARS_PER_TOKEN = 3.6


def tokenizer():
    """A real tokenizer if one is installed, otherwise the estimator.

    Readers on an unrestricted network get exact numbers by installing tiktoken.
    The machine this report was generated on could not reach the encoding file,
    so the committed numbers are estimates — stated, rather than quietly fudged.
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("o200k_base")
        return "tiktoken/o200k_base", lambda s: len(enc.encode(s))
    except Exception:
        return (
            f"estimate/{CHARS_PER_TOKEN}-chars-per-token",
            lambda s: round(len(s) / CHARS_PER_TOKEN),
        )


METHOD, count_tokens = tokenizer()


# region: measuring
@dataclass
class Measurement:
    label: str
    chars: int
    tokens: int
    note: str = ""


def measure(label: str, payload: object, note: str = "") -> Measurement:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return Measurement(label, len(text), count_tokens(text), note)


def as_wire(obj) -> dict:
    """What actually crosses the wire for one definition."""
    return json.loads(obj.model_dump_json(exclude_none=True))
# endregion: measuring


async def collect() -> dict:
    surface: list[Measurement] = []
    results: list[Measurement] = []

    async with Client(mcp) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        prompts = await client.list_prompts()

        for tool in tools:
            surface.append(measure(f"tool: {tool.name}", as_wire(tool)))
        for template in templates:
            surface.append(measure(f"resource template: {template.name}", as_wire(template)))
        for resource in resources:
            surface.append(measure(f"resource: {resource.name}", as_wire(resource)))
        for prompt in prompts:
            surface.append(measure(f"prompt: {prompt.name}", as_wire(prompt)))

        instructions = measure("instructions block", mcp.instructions or "")

        # The specimen: one title carrying more licences than anyone asked for.
        widest = (await client.call_tool(
            "search_titles", {"query": "Winter Cartograph", "limit": 5}
        )).data

        cases = [
            ("get_title on the widest title", "get_title", {"title_id": "T-1152"}),
            ("find_licences, no filter", "find_licences", {"title_id": "T-1152"}),
            ("find_licences, one territory", "find_licences",
             {"title_id": "T-1152", "territory": "GB"}),
            ("find_licences, active only", "find_licences",
             {"title_id": "T-1152", "status": "active"}),
            ("search_titles, 20 results", "search_titles", {"query": "the", "limit": 20}),
            ("licence_detail, one licence", "licence_detail", {"licence_id": "LIC-10000"}),
        ]
        for label, name, args in cases:
            result = await client.call_tool(name, args)
            rows = result.data if isinstance(result.data, list) else [result.data]
            results.append(measure(label, result.data, note=f"{len(rows)} row(s)"))

        overview = measure(
            "resource: ledger://catalogue (contents)",
            (await client.read_resource("ledger://catalogue"))[0].text,
        )

    surface_total = Measurement(
        "TOTAL fixed cost",
        sum(m.chars for m in surface) + instructions.chars,
        sum(m.tokens for m in surface) + instructions.tokens,
        note="paid in every conversation, called or not",
    )

    return {
        "method": METHOD,
        "server": "ledger",
        "titles_measured": [t["id"] for t in widest][:1],
        "surface": [asdict(m) for m in surface],
        "instructions": asdict(instructions),
        "surface_total": asdict(surface_total),
        "results": [asdict(m) for m in results],
        "overview_resource": asdict(overview),
    }


def render(report: dict) -> str:
    def table(rows, header):
        out = [f"| {header} | chars | tokens | |", "|---|---:|---:|---|"]
        for r in rows:
            out.append(
                f"| {r['label']} | {r['chars']:,} | {r['tokens']:,} | {r['note']} |"
            )
        return "\n".join(out)

    total = report["surface_total"]
    naive = next(r for r in report["results"] if r["label"] == "find_licences, no filter")
    narrow = next(
        r for r in report["results"] if r["label"] == "find_licences, one territory"
    )

    return f"""# Token audit — `ledger` ({report.get("label", "current")})

Counted with **{report["method"]}**. Characters are exact; tokens are an estimate
unless the method names a real tokenizer. Regenerate with:

```bash
cd code/labs/token-audit && uv run --project ../../ledger python audit.py --label {report.get("label", "current")}
```

## The fixed cost

Loaded into every conversation with this server, whether or not anything is called.

<!-- region: fixed_cost -->
{table(report["surface"] + [report["instructions"]], "definition")}
<!-- endregion: fixed_cost -->

**{total["chars"]:,} characters, about {total["tokens"]:,} tokens** — {total["note"]}.

## What one call costs

<!-- region: call_cost -->
{table(report["results"], "call")}
<!-- endregion: call_cost -->

The unfiltered call costs **{naive["tokens"] / total["tokens"]:.1f}×** the entire tool
surface, and **{naive["tokens"] / narrow["tokens"]:.0f}×** the same call narrowed to one
territory.

## A resource, for comparison

{table([report["overview_resource"]], "resource")}
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--label",
        default="bounded",
        help="report name under reports/ — the book keeps 'naive' (the v0 "
             "server, chapter 8) and 'bounded' (after chapter 10) side by side",
    )
    args = ap.parse_args()

    report = asyncio.run(collect())
    report["label"] = args.label
    out = HERE / "reports"
    out.mkdir(exist_ok=True)
    (out / f"{args.label}.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / f"{args.label}.md").write_text(render(report))

    print(f"method: {report['method']}\n")
    print(f"{'':44} {'chars':>8} {'tokens':>8}")
    for row in report["surface"] + [report["instructions"], report["surface_total"]]:
        print(f"{row['label']:<44} {row['chars']:>8,} {row['tokens']:>8,}")
    print()
    for row in report["results"]:
        print(f"{row['label']:<44} {row['chars']:>8,} {row['tokens']:>8,}  {row['note']}")


if __name__ == "__main__":
    main()
