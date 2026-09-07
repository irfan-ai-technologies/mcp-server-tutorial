# Token audit — `ledger` (naive)

Counted with **anthropic/claude-2-legacy**. Characters are exact. Tokens depend on the
tokenizer named above — every ratio below compares two numbers counted the same way.
Regenerate with:

```bash
cd code/labs/token-audit && uv run --project ../../ledger python audit.py --label naive
```

## The fixed cost

Loaded into every conversation with this server, whether or not anything is called.

<!-- region: fixed_cost -->
| definition | chars | tokens | |
|---|---:|---:|---|
| tool: search_titles | 779 | 220 |  |
| tool: get_title | 539 | 151 |  |
| tool: find_licences | 962 | 287 |  |
| tool: licence_detail | 554 | 158 |  |
| resource template: Title | 198 | 57 |  |
| resource template: Agreement | 296 | 81 |  |
| resource: Catalogue overview | 343 | 81 |  |
| prompt: clearance_check | 656 | 161 |  |
| prompt: window_review | 321 | 81 |  |
| instructions block | 522 | 123 |  |
<!-- endregion: fixed_cost -->

**5,170 characters, about 1,400 tokens** — paid in every conversation, called or not.

## What one call costs

<!-- region: call_cost -->
| call | chars | tokens | |
|---|---:|---:|---|
| get_title on the widest title | 289 | 87 | 1 row(s) |
| find_licences, no filter | 38,879 | 15,118 | 180 row(s) |
| find_licences, one territory | 650 | 253 | 3 row(s) |
| find_licences, active only | 13,573 | 5,312 | 63 row(s) |
| search_titles, 20 results | 2,478 | 853 | 20 row(s) |
| licence_detail, one licence | 618 | 252 | 1 row(s) |
<!-- endregion: call_cost -->

The unfiltered call costs **10.8×** the entire tool
surface, and **60×** the same call narrowed to one
territory.

## A resource, for comparison

| resource | chars | tokens | |
|---|---:|---:|---|
| resource: ledger://catalogue (contents) | 1,148 | 418 |  |
