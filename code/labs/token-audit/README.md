# token-audit

Prices `ledger`'s tool surface and the results it returns. Chapters 8 and 10 are built on
the committed reports.

```bash
cd code/labs/token-audit
uv run --project ../../ledger --with tokenizers --with 'anthropic==0.21.3' \
    python audit.py --label bounded
```

`reports/naive.md` measures the v0 server, before chapter 10 bounded `find_licences`;
`reports/bounded.md` measures it after. Both were counted with the same tokenizer, which is
the only way the comparison means anything.

## Which tokenizer

`--tokenizer` takes `auto` (the default), `claude`, `tiktoken` or `estimate`, and every
report names the one that produced it.

- **`claude`** — the tokenizer Anthropic shipped inside the SDK up to `anthropic==0.21.x`,
  bundled in the wheel rather than downloaded. It is the Claude 2 generation's tokenizer:
  current Claude models use a different one that is not distributed, so these counts are
  close but not exact for whatever you are running today. It is the default because it is
  reproducible offline by anyone who installs the pin.
- **`tiktoken`** — OpenAI's `o200k_base`. Exact, and it downloads its encoding on first
  use, so it needs network access to `openaipublic.blob.core.windows.net`.
- **`estimate`** — 2.2 characters per token. A fallback, not a source. Note how far it is
  from the 4.0 that English prose suggests: dense JSON, full of quoted keys and
  punctuation, tokenizes almost twice as heavily as prose.

Characters are exact under every setting and are reported alongside.

## Why the tokenizer is named everywhere

There is no single token count for a string. Claude, GPT and Llama disagree, sometimes by
a fifth on the same JSON payload. A token count quoted without a tokenizer is folklore, so
the reports name theirs and the chapters argue from ratios between numbers counted the
same way.
