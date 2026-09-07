# Token audit — `ledger`

Counted with **estimate/3.6-chars-per-token**. Characters are exact; tokens are an estimate
unless the method names a real tokenizer. Regenerate with:

```bash
cd code/labs/token-audit && uv run --project ../../ledger python audit.py
```

## The fixed cost

Loaded into every conversation with this server, whether or not anything is called.

<!-- region: fixed_cost -->
| definition | chars | tokens | |
|---|---:|---:|---|
| tool: search_titles | 779 | 216 |  |
| tool: get_title | 539 | 150 |  |
| tool: find_licences | 962 | 267 |  |
| tool: licence_detail | 554 | 154 |  |
| resource template: Title | 198 | 55 |  |
| resource template: Agreement | 296 | 82 |  |
| resource: Catalogue overview | 343 | 95 |  |
| prompt: clearance_check | 656 | 182 |  |
| prompt: window_review | 321 | 89 |  |
| instructions block | 522 | 145 |  |
<!-- endregion: fixed_cost -->

**5,170 characters, about 1,435 tokens** — paid in every conversation, called or not.

## What one call costs

<!-- region: call_cost -->
| call | chars | tokens | |
|---|---:|---:|---|
| get_title on the widest title | 289 | 80 | 1 row(s) |
| find_licences, no filter | 38,879 | 10,800 | 180 row(s) |
| find_licences, one territory | 650 | 181 | 3 row(s) |
| find_licences, active only | 13,573 | 3,770 | 63 row(s) |
| search_titles, 20 results | 2,478 | 688 | 20 row(s) |
| licence_detail, one licence | 618 | 172 | 1 row(s) |
<!-- endregion: call_cost -->

The unfiltered call costs **7.5×** the entire tool
surface, and **60×** the same call narrowed to one
territory.

## A resource, for comparison

| resource | chars | tokens | |
|---|---:|---:|---|
| resource: ledger://catalogue (contents) | 1,148 | 319 |  |
