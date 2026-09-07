# token-audit

Prices `ledger`'s tool surface and the results it returns. Chapter 8 is built on the
committed `reports/naive.md`.

```bash
cd code/labs/token-audit
uv run --project ../../ledger python audit.py     # writes reports/<label>.json and .md
```

Characters are exact. Tokens are an estimate at 3.6 characters per token unless a real
tokenizer is installed — `pip install tiktoken` and re-run for exact counts against
`o200k_base`. The report records which method produced it.

That split is on purpose. There is no single token count for a piece of text: Claude, GPT
and Llama tokenize differently, and a number quoted without naming a tokenizer is folklore.
What survives the difference is the *shape* — a surface costing a couple of thousand
tokens, a single unfiltered call costing seven times that — and the shape is what the
chapters argue from.
