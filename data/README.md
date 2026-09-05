# The synthetic catalogue

Everything in this directory is invented. There are no real titles, companies,
agreements or deal terms anywhere in this repository, and any resemblance to a real
catalogue is coincidental. Nothing here is derived from consulting work.

```bash
uv run data/generate.py                 # data/generated/ledger.db  (~7 MB)
uv run data/generate.py --scale small   # a fraction of the rows, used by the tests
```

The database is generated, not committed — `data/generated/` is ignored. The generator is
deterministic, so the same seed produces the same bytes on any machine and every number
printed in the book can be reproduced rather than taken on trust.

## Shape

| Table | Rows (full) | Why the book needs it |
|---|---:|---|
| `titles` | 1,200 | The entity a reader searches for |
| `licensees` | 64 | Tenants, in the multi-tenancy chapters |
| `agreements` | ~470 | Masters with amendments and side letters hanging off them — a real hierarchy to disclose progressively (ch. 21) |
| `licences` | ~13,000 | The join everyone writes naively. The distribution is deliberately long-tailed: most titles carry a handful, a few carry 180 (ch. 8, 10) |
| `royalty_lines` | ~60,000 | Large enough that aggregation has to happen in SQL rather than in the model (ch. 22) |

Money is stored in minor units as integers. There are no floats in this schema, and the
book does not introduce any.

## The long tail is the point

```sql
SELECT title_id, COUNT(*) c FROM licences GROUP BY title_id ORDER BY c DESC LIMIT 5;
```

One title carrying 180 licences is what turns a correct tool into a context-window
failure. Chapter 8 measures it; chapter 10 fixes it.
