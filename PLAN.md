# MCP Servers: Zero to Hero — Build Plan

Working plan for a practical book on building MCP servers. This file is the contract
between chapters and code; it changes when the shape of the book changes, not when a
chapter gets written.

---

## 1. Decisions already made

| Question | Decision |
|---|---|
| Language | Python only. FastMCP 4.x as the teaching stack; the raw SDK (`mcp` 2.x) shown where the abstraction hides something worth seeing. |
| Chapter format | Hand-authored HTML in `book/chapters/`, one file per chapter, from a shared template. No site generator to install. |
| Code shape | One running project that grows chapter by chapter, plus a small number of standalone labs for topics the spine can't host naturally. |
| Reader | Senior engineers and architects. Assumes Python, async, HTTP, auth, and production instincts. The basics get one part, not five. |
| Repo | This one. |
| Distribution | Public GitHub repo from the start, built book served by GitHub Pages. Nothing held back for a gated edition. |
| Licence | Code: Apache-2.0 (already in place). Prose: open question — see §10.1. |
| Commits | Every reasonably sized artefact lands as its own commit. No `Co-Authored-By` trailer. |

## 2. What this book is, and what it is not

**Is:** a book about the engineering problems that appear *after* your MCP server works —
context economics, statelessness, tool surface design, failure modes, and the operational
reality of a server that several agents hit at once.

**Is not:** a tour of the SDK. There is good reference documentation for that and it will
be linked, not restated. Chapters 3–7 exist to get everyone to the same starting line,
then the book spends its budget on the hard half.

**The through-line:** an MCP server is a prompt. Every tool name, description, schema and
result is text that lands in a context window you don't control, priced per token, read by
a model that will make bad decisions if you make bad ones. Most of the "scale" problems in
this book are that fact wearing different clothes.

## 3. Timing note — the protocol moved

The book targets **protocol revision `2026-07-28`**, which is the largest break since MCP
launched. This is a feature, not a hazard: most existing MCP writing on the internet is now
describing a protocol that no longer exists, and a book written against the current one has
a real reason to exist.

What changed that the book must teach correctly:

- **Sessions are gone.** No `Mcp-Session-Id`. Servers needing cross-call state mint explicit
  handles and pass them as ordinary tool arguments. This is the backbone of the state
  management chapters.
- **No `initialize` handshake.** Every request carries protocol version and client
  capabilities in `_meta`. `server/discover` is the new up-front probe.
- **MRTR replaces server-initiated requests.** A server that needs more input returns
  `resultType: "input_required"`; the client retries with `inputResponses`.
- **Roots, Sampling and Logging are deprecated.** Twelve-month window. New servers should
  not adopt them — the book teaches the migrations instead (tool params / resource URIs;
  provider APIs; stderr + OpenTelemetry).
- **No SSE resumability.** A broken stream loses the in-flight request. Retry design is now
  the reader's problem, and gets a chapter.
- **Caching is explicit.** `ttlMs` and `cacheScope` on every list result; deterministic
  `tools/list` ordering for prompt-cache hits.

Corollary for the writing process: **verify every protocol claim against the spec at the
time of writing**, and pin exact library versions in `code/`. A `docs/protocol-notes.md`
tracks anything that shifts while the book is in progress.

## 4. The spine project

**`ledger`** — an MCP server over a media rights catalogue. A licensing operation with:

- a relational store of titles, licences, territories, rights windows and royalty lines
  (large enough that naive tool results blow the context window — this is the point),
- a document store of contract PDFs with nested amendments (unstructured, deeply
  hierarchical — the natural home for progressive disclosure),
- a recompute job that takes minutes (long-running work, the tasks extension),
- multiple studios as tenants (identity, scoping, per-tenant tool surface).

Why this domain: every problem the book needs shows up for an honest reason rather than a
contrived one. A "big result set" chapter needs a genuinely big result set; a "progressive
disclosure" chapter needs a corpus with real structure to disclose.

The spine ships a seeded synthetic dataset (`data/`) so every measurement in the book is
reproducible by the reader.

**Chapter ↔ code linkage:** each chapter that changes the spine gets a git tag,
`ch12-state-handles`, so a reader can check out the project exactly as it stands at the end
of any chapter. Chapters state their starting tag in the header.

## 5. Chapter outline

Roughly 24 chapters across six parts. Sizes are indicative: a chapter is 2,500–4,000 words
plus code.

### Part 0 — Orientation (2)

1. **What MCP actually is** — protocol vs. framework vs. plugin system. Where it sits next
   to plain function calling and an API gateway. The honest case against it.
2. **The protocol in one chapter** — the wire, read directly. Stateless core, `server/discover`,
   `_meta` conventions, `resultType`, MRTR, Streamable HTTP. Reader ends able to speak MCP
   with `curl`.

### Part 1 — Zero: a server that works (5)

3. **First server** — `ledger` v0, stdio, the Inspector, the shortest useful loop.
4. **Tools** — signatures, JSON Schema 2020-12, `structuredContent`, annotations, and errors
   written for a model rather than a human.
5. **Resources and templates** — when a resource beats a tool, and why most servers get this
   backwards.
6. **Prompts** — the least-used primitive, what it's actually for, when to skip it.
7. **Testing without an LLM** — in-process client, golden transcripts, contract tests over
   the tool surface. Established here because everything after depends on it.

### Part 2 — The client's point of view (3)

8. **What the model actually sees** — token-accounting your own server. A script that prices
   your tool surface; the 67k-tokens-before-you-type problem, measured on `ledger`.
9. **Tool design is prompt engineering** — naming, description budgets, determinism,
   idempotency, and designing a tool the model can recover from.
10. **Result shaping** — content vs. structured output, pagination, truncation strategies,
    and the failure mode where one successful call ends the conversation.

### Part 3 — Scale (7)

11. **Going HTTP** — Streamable HTTP, running stateless behind a load balancer, what
    horizontal scale now actually costs you.
12. **Life after sessions** — server-minted handles: shape, TTL, storage, revocation,
    idempotency keys, and how to keep a handle from becoming a session by another name.
13. **Failure** — timeouts, cancellation, backpressure, concurrency limits, and retry design
    now that streams are not resumable.
14. **Caching and the prompt cache** — `ttlMs`, `cacheScope`, deterministic list ordering,
    and why reordering your tools costs your users money.
15. **Long-running work** — the `io.modelcontextprotocol/tasks` extension, polling with
    `tasks/get`, `tasks/update`, and designing for a client that never comes back.
16. **Observability** — OTel trace propagation via `_meta`, per-request log level, and the
    four numbers worth alerting on.
17. **Identity and multi-tenancy** — OAuth, Client ID Metadata Documents, where DPoP is
    heading, and scoping the tool surface per caller.
18. **Security** — the confused deputy, injection through tool *results*, poisoned tool
    descriptions, egress control, sandboxing anything that executes.

### Part 4 — The context problem (5) — the "hero" part

19. **Progressive disclosure I: shrink the surface** — toolsets, per-identity filtering,
    gateway and proxy patterns. The cheapest wins first.
20. **Progressive disclosure II: search then load** — a `search_tools` meta-tool, deferred
    schemas, the extra-round-trip tax, and what the spec's forthcoming "progressive
    discovery" will and won't hand you.
21. **Progressive disclosure III: resources as the disclosure channel** — a table-of-contents
    resource, drill-down URIs, and shaping a corpus so a model can navigate it without
    reading it.
22. **`jq` as a tool** — hand the model a filter instead of the payload. Tool design,
    sandboxing `jq` safely, streaming large inputs, error messages that teach, and a
    measured before/after on `ledger`. Includes when a bespoke query tool beats `jq`.
23. **Code mode** — when to stop exposing tools and expose a typed SDK plus a sandbox.
    Honest comparison against ch. 20 and 22: what it buys, what it costs, when the model
    quality floor makes it a bad trade.

### Part 5 — Shipping (3)

24. **Packaging and distribution** — stdio vs. hosted, the registry, versioning a tool
    contract, deprecating a tool without breaking agents in the wild.
25. **Evaluating a server** — task-level evals, a regression harness, cost and latency
    budgets per tool.
26. **Anti-patterns and a review checklist** — the one-page artefact most readers will keep.

### Appendices

- A. The same server without FastMCP — raw `mcp` 2.x, for readers who need the seams.
- B. Migrating `2025-11-25` → `2026-07-28`.
- C. `jq` cookbook for agent tool results.
- D. Glossary.

## 6. Repository layout

```
mcp-server-tutorial/
├── PLAN.md                     # this file
├── README.md                   # what the book is, how to read/run it
├── book/
│   ├── index.html              # table of contents
│   ├── templates/chapter.html  # single chapter shell
│   ├── assets/{book.css, book.js, diagrams/}
│   └── chapters/ch01-*.html …
├── code/
│   ├── ledger/                 # the spine project (tagged per chapter)
│   │   ├── pyproject.toml
│   │   ├── src/ledger/
│   │   └── tests/
│   └── labs/                   # standalone, self-contained
│       ├── jq-tool/
│       ├── tool-search/
│       ├── code-mode/
│       └── token-audit/        # the ch.8 measurement script
├── data/                       # synthetic dataset + generator
├── scripts/build.py            # injects nav/TOC/highlighting into chapters
├── docs/protocol-notes.md      # spec drift log while writing
└── .github/workflows/
    ├── ci.yml              # run every code sample, lint every chapter link
    └── pages.yml           # build book/ and publish to GitHub Pages
```

**Build:** `scripts/build.py` is deliberately small — it renders chapter bodies into the
template, generates navigation and the TOC, and applies syntax highlighting at build time.
No runtime JS framework; a chapter opens correctly from `file://`. Dark and light both
supported, because readers read at night.

**Publishing:** `book/` is plain HTML, so GitHub Pages serves the built output with no
generator in the loop. `scripts/build.py` writes to `book/_site/`; Pages publishes that
directory. The repo is readable as source and as a site from day one.

**CI:** every code sample in `code/` runs in CI, and any snippet in a chapter is *included*
from a real file rather than pasted. A book whose code rots is worse than no book.

## 7. Working agreement

- **Commit granularity.** One commit per artefact: a chapter, a spine milestone, a lab, a
  build-script change, a dataset. Never one commit for "the book".
- **No `Co-Authored-By` trailer.** Author is Irfan.
- **Message style.** `chapter: ch12 life after sessions`, `ledger: mint scoped handles`,
  `lab: jq tool`, `build: chapter nav`, `docs: protocol notes`.
- **Tags.** `chNN-slug` on the spine after each chapter that changes it.
- **Order of work.** Code for a chapter first, then the chapter. Prose written against code
  that ran is prose that stays true.
- **Voice.** Direct, no hype, no marketing register. Claims carry a number or a citation. If
  a technique has a real cost, the chapter says so in the same paragraph as the benefit.

## 8. Sequence of work

| Phase | Output | Gate |
|---|---|---|
| 0 | Scaffolding: repo layout, chapter template, `build.py`, CI, Pages, README | A dummy chapter builds, opens locally and publishes |
| 1 | `ledger` v0 + dataset generator | `pytest` green, server runs over stdio and HTTP |
| 2 | Part 0 + Part 1 (ch. 1–7) | Seven chapters build; all code in CI |
| 3 | `token-audit` lab + Part 2 (ch. 8–10) | Real measured numbers on `ledger` |
| 4 | Part 3 (ch. 11–18) — the largest phase, likely split | Spine runs stateless, multi-tenant, observable |
| 5 | Part 4 (ch. 19–23) + `jq-tool`, `tool-search`, `code-mode` labs | Before/after token numbers reproduce |
| 6 | Part 5 + appendices | Full book builds, CI green, links clean |
| 7 | Review pass: consistency, protocol drift, cuts | Ship |

## 9. Working in public

The repo is public from the first commit, which changes a few things:

- **Synthetic data only.** Every row, title, contract clause and party name in `data/` is
  invented and generated by a script that ships with the repo. No real agreement text, no
  client names, no material drawn from consulting work — not paraphrased, not
  lightly-renamed. The dataset generator is itself a chapter artefact, so this is
  verifiable rather than a promise.
- **The domain is a teaching fixture, not a case study.** `ledger` models media rights
  because that domain produces the right engineering problems honestly. Chapters describe
  the *shape* of licensing data, never a real deal.
- **No credentials, ever.** The identity and auth chapters (17) run against a local
  authorisation server in docker-compose. Secrets scanning on in CI.
- **The README is the front door.** A public repo is judged by it in ten seconds: what the
  book is, who it's for, the protocol revision it targets, how to read it, how to run the
  code. Written in Phase 0, rewritten in Phase 7.
- **Issues are feedback.** Expect readers to report protocol drift faster than you notice
  it. `docs/protocol-notes.md` is the place that lands, and an issue template points there.
- **Chapters ship as they are written.** Publishing part-by-part gets the corrections early;
  a `STATUS` line in the README and the TOC marks what is draft, reviewed, or code-complete.

## 10. Open decisions

1. **Prose licence.** Apache-2.0 covers the code well and the prose oddly. The usual split
   is code under Apache-2.0 or MIT, text under a Creative Commons licence — CC BY-SA keeps
   derivatives open, CC BY-NC blocks commercial reuse but is awkward alongside an academy
   that is itself commercial, CC BY is the most permissive. This is a call about how you
   want the book reused, not a technical one. Decide before Phase 6; it only changes root
   files.
2. **Spine domain.** Media rights is proposed because it produces the right problems
   honestly, and §9 keeps it clear of real work. If it still reads too close for a public
   repo, a support-desk / ticketing estate is the bland substitute. Decide before Phase 1.
3. **Backing store.** SQLite keeps the reader's setup to zero; Postgres makes the
   multi-tenancy and concurrency chapters truthful. Likely: SQLite by default, Postgres via
   docker-compose from ch. 11.
4. **Client-side coverage.** The book is server-side by design. Ch. 8 and Part 4 need *some*
   client to measure against — decide whether that's a scripted harness or a real agent.
5. **Chapter count.** 26 is at the upper end. Parts 3 and 4 are where cuts should come from
   if the book needs to be shorter, not Part 1.
