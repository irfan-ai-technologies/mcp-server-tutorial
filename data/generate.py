#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Generate the synthetic rights catalogue the book is built on.

Everything here is invented. There are no real titles, companies, agreements or
deal terms in this repository, and any resemblance to a real catalogue is
coincidental. The generator is deterministic — the same seed produces the same
database on any machine — so every measurement printed in the book can be
reproduced by the reader rather than taken on trust.

    uv run data/generate.py                  # data/generated/ledger.db
    uv run data/generate.py --scale small    # a fraction of the rows, for tests

The shape matters more than the size. Three things the book needs from it:

  * `licences` is wide enough that the obvious query returns far more rows than
    belong in a context window (chapters 8 and 10),
  * `royalty_lines` is large enough that aggregation has to happen in SQL rather
    than in the model (chapter 22),
  * `agreements` nests — amendments hang off masters, which hang off masters —
    so there is a real hierarchy to disclose progressively (chapter 21).
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import unicodedata
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "generated" / "ledger.db"
SEED = 20260728  # the protocol revision the book targets; no deeper meaning

SCALES = {
    "small": {"titles": 40, "licensees": 6, "periods": 4},
    "full": {"titles": 1200, "licensees": 64, "periods": 20},
}

# --- invented vocabulary -------------------------------------------------

ADJECTIVES = """salt hollow bright winter iron quiet distant amber crooked northern
copper silent glass burning pale restless golden narrow tidal wandering""".split()

NOUNS = """meridian archive harbour signal orchard mercy circuit lantern passage
foundry cadence threshold ledger monsoon lighthouse cartograph interval reef
almanac quarry""".split()

SERIES_SUFFIX = ["", "", "", ": Second Season", ": Third Season", ": The Reckoning"]

COMPANY_HEADS = """northwind kestrel bramble halcyon vantage ferrous lumen ostrel
cardinal driftwood saltmarsh tessera magpie hollowbrook verity pinion""".split()

COMPANY_TAILS = [
    "Broadcasting", "Media Group", "Streaming", "Networks", "Pictures",
    "Entertainment", "Distribution", "Channels", "Rights", "Studios",
]

TERRITORIES = [
    "AE", "AR", "AU", "BR", "CA", "CH", "DE", "DK", "ES", "FI", "FR", "GB",
    "ID", "IE", "IN", "IT", "JP", "KR", "MX", "MY", "NL", "NO", "NZ", "PH",
    "PL", "PT", "SE", "SG", "TH", "TR", "US", "VN", "ZA",
]

RIGHTS = ["svod", "avod", "fast", "ppv", "theatrical", "linear", "inflight"]
LICENSEE_KINDS = ["broadcaster", "streamer", "airline", "hotel", "distributor"]
TITLE_KINDS = ["film", "series", "documentary", "short"]
LANGUAGES = ["en", "es", "fr", "de", "ja", "ko", "hi", "pt", "ta", "sv"]
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "INR"]

SCHEMA = """
CREATE TABLE titles (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL,
    release_year    INTEGER NOT NULL,
    original_language TEXT NOT NULL,
    runtime_minutes INTEGER,
    synopsis        TEXT NOT NULL
);

CREATE TABLE licensees (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL,
    home_territory  TEXT NOT NULL
);

CREATE TABLE licences (
    id              TEXT PRIMARY KEY,
    title_id        TEXT NOT NULL REFERENCES titles(id),
    licensee_id     TEXT NOT NULL REFERENCES licensees(id),
    territory       TEXT NOT NULL,
    rights          TEXT NOT NULL,
    exclusive       INTEGER NOT NULL,
    window_start    TEXT NOT NULL,
    window_end      TEXT NOT NULL,
    status          TEXT NOT NULL,
    agreement_id    TEXT NOT NULL REFERENCES agreements(id)
);

CREATE TABLE agreements (
    id              TEXT PRIMARY KEY,
    licensee_id     TEXT NOT NULL REFERENCES licensees(id),
    kind            TEXT NOT NULL,          -- master | amendment | side_letter
    parent_id       TEXT REFERENCES agreements(id),
    reference       TEXT NOT NULL,
    signed_on       TEXT NOT NULL
);

CREATE TABLE royalty_lines (
    id              INTEGER PRIMARY KEY,
    licence_id      TEXT NOT NULL REFERENCES licences(id),
    period          TEXT NOT NULL,          -- YYYY-Qn
    gross_minor     INTEGER NOT NULL,       -- minor units, never floats
    currency        TEXT NOT NULL,
    rate_bps        INTEGER NOT NULL        -- basis points
);

CREATE INDEX idx_licences_title      ON licences(title_id);
CREATE INDEX idx_licences_territory  ON licences(territory);
CREATE INDEX idx_licences_licensee   ON licences(licensee_id);
CREATE INDEX idx_licences_window     ON licences(window_start, window_end);
CREATE INDEX idx_royalty_licence     ON royalty_lines(licence_id);
CREATE INDEX idx_royalty_period      ON royalty_lines(period);
CREATE INDEX idx_agreements_parent   ON agreements(parent_id);
"""


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def make_titles(rng: random.Random, n: int) -> list[tuple]:
    seen: set[str] = set()
    rows = []
    while len(rows) < n:
        name = f"The {rng.choice(ADJECTIVES).title()} {rng.choice(NOUNS).title()}"
        kind = rng.choices(TITLE_KINDS, weights=[50, 30, 15, 5])[0]
        if kind == "series":
            name += rng.choice(SERIES_SUFFIX)
        if name in seen:
            continue
        seen.add(name)
        year = rng.randint(1998, 2026)
        runtime = rng.randint(74, 168) if kind == "film" else rng.randint(22, 58)
        rows.append((
            f"T-{len(rows) + 1000}",
            name,
            kind,
            year,
            rng.choices(LANGUAGES, weights=[45, 10, 8, 7, 8, 6, 6, 4, 3, 3])[0],
            runtime,
            f"A {kind} from {year}. Synopsis text is generated and carries no meaning.",
        ))
    return rows


def make_licensees(rng: random.Random, n: int) -> list[tuple]:
    rows, seen = [], set()
    while len(rows) < n:
        name = f"{rng.choice(COMPANY_HEADS).title()} {rng.choice(COMPANY_TAILS)}"
        if name in seen:
            continue
        seen.add(name)
        rows.append((
            f"L-{len(rows) + 100}",
            name,
            rng.choice(LICENSEE_KINDS),
            rng.choice(TERRITORIES),
        ))
    return rows


def make_agreements(rng: random.Random, licensees: list[tuple]) -> list[tuple]:
    """Masters with amendments hanging off them, and the odd nested amendment."""
    rows: list[tuple] = []
    for lic_id, *_ in licensees:
        for m in range(rng.randint(1, 3)):
            master_id = f"A-{lic_id[2:]}-{m}"
            signed = date(2019, 1, 1) + timedelta(days=rng.randint(0, 2000))
            rows.append((master_id, lic_id, "master", None,
                         f"MSA/{lic_id[2:]}/{m}", signed.isoformat()))
            for a in range(rng.randint(0, 4)):
                amend_id = f"{master_id}.{a}"
                amend_signed = signed + timedelta(days=rng.randint(30, 900))
                rows.append((amend_id, lic_id, "amendment", master_id,
                             f"AMD/{lic_id[2:]}/{m}/{a}", amend_signed.isoformat()))
                if rng.random() < 0.18:  # an amendment to an amendment
                    rows.append((
                        f"{amend_id}.0", lic_id, "side_letter", amend_id,
                        f"SL/{lic_id[2:]}/{m}/{a}",
                        (amend_signed + timedelta(days=rng.randint(20, 400))).isoformat(),
                    ))
    return rows


def make_licences(rng, titles, licensees, agreements) -> list[tuple]:
    by_licensee: dict[str, list[str]] = {}
    for aid, lid, *_ in agreements:
        by_licensee.setdefault(lid, []).append(aid)

    rows = []
    for title_id, *_ in titles:
        # A popular title is licensed widely; most are not. The long tail is the
        # point: chapter 8 measures what happens when a model asks about one of
        # the few titles carrying two hundred licences.
        count = rng.choices([1, 3, 8, 20, 60, 180], weights=[30, 30, 20, 12, 6, 2])[0]
        for _ in range(count):
            licensee = rng.choice(licensees)
            start = date(2020, 1, 1) + timedelta(days=rng.randint(0, 2100))
            end = start + timedelta(days=rng.choice([365, 730, 1095, 1825]))
            today = date(2026, 9, 1)
            status = ("expired" if end < today
                      else "pending" if start > today
                      else "active")
            rows.append((
                f"LIC-{len(rows) + 10000}",
                title_id,
                licensee[0],
                rng.choice(TERRITORIES),
                rng.choice(RIGHTS),
                int(rng.random() < 0.22),
                start.isoformat(),
                end.isoformat(),
                status,
                rng.choice(by_licensee[licensee[0]]),
            ))
    return rows


def make_royalties(rng, licences, periods: int) -> list[tuple]:
    quarters = [f"{y}-Q{q}" for y in range(2022, 2027) for q in (1, 2, 3, 4)][:periods]
    rows = []
    for lic in licences:
        if lic[8] == "pending":
            continue
        for period in rng.sample(quarters, k=min(len(quarters), rng.randint(1, 8))):
            rows.append((
                len(rows) + 1,
                lic[0],
                period,
                rng.randint(1_00, 4_000_00),
                rng.choice(CURRENCIES),
                rng.choice([500, 750, 1000, 1250, 1500, 2000]),
            ))
    return rows


def build(scale: str, out: Path) -> None:
    cfg = SCALES[scale]
    rng = random.Random(SEED)

    titles = make_titles(rng, cfg["titles"])
    licensees = make_licensees(rng, cfg["licensees"])
    agreements = make_agreements(rng, licensees)
    licences = make_licences(rng, titles, licensees, agreements)
    royalties = make_royalties(rng, licences, cfg["periods"])

    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)

    db = sqlite3.connect(out)
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO titles VALUES (?,?,?,?,?,?,?)", titles)
    db.executemany("INSERT INTO licensees VALUES (?,?,?,?)", licensees)
    db.executemany("INSERT INTO agreements VALUES (?,?,?,?,?,?)", agreements)
    db.executemany("INSERT INTO licences VALUES (?,?,?,?,?,?,?,?,?,?)", licences)
    db.executemany("INSERT INTO royalty_lines VALUES (?,?,?,?,?,?)", royalties)
    db.commit()
    db.execute("ANALYZE")
    db.commit()

    widest = db.execute(
        "SELECT title_id, COUNT(*) c FROM licences GROUP BY title_id "
        "ORDER BY c DESC LIMIT 1"
    ).fetchone()
    db.close()

    size_mb = out.stat().st_size / 1e6
    print(f"{out}  ({scale}, {size_mb:.1f} MB)")
    for name, rowset in (
        ("titles", titles), ("licensees", licensees), ("agreements", agreements),
        ("licences", licences), ("royalty_lines", royalties),
    ):
        print(f"  {name:<14} {len(rowset):>8,}")
    print(f"  widest title   {widest[0]} with {widest[1]:,} licences")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scale", choices=sorted(SCALES), default="full")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    build(args.scale, args.out)


if __name__ == "__main__":
    main()
