#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pygments==2.19.2"]
# ///
"""Build the book.

Chapters are complete, self-contained HTML documents that open straight from the
filesystem. This script does not render them from a template — it regenerates the
regions it owns, in place, and leaves the author's prose alone:

    <!-- BEGIN:title -->   ... <!-- END:title -->
    <!-- BEGIN:sidebar --> ... <!-- END:sidebar -->
    <!-- BEGIN:head -->    ... <!-- END:head -->
    <!-- BEGIN:pager -->   ... <!-- END:pager -->

Inside the body it expands code includes, so no snippet is ever pasted by hand:

    <!-- include: code/ledger/src/ledger/server.py lang=python region=handles -->
    <!-- endinclude -->

    lines=10-30    an explicit line range (1-based, inclusive)
    region=NAME    the block between "region: NAME" and "endregion: NAME" markers
                   in the source file, in whatever comment syntax that file uses
    lang=python    lexer override; otherwise inferred from the file extension
    title=...      caption text; otherwise the file path

Everything is idempotent: running it twice changes nothing, which is what makes
`build.py check` a usable CI gate.

Run it with uv so the Pygments version — and therefore the generated HTML — is
pinned and reproducible:

    uv run scripts/build.py build

Commands:
    build     rewrite chapters and the contents page in place
    site      build, then assemble book/_site/ for publishing
    check     build, then fail if anything changed or any reference is broken
    new SLUG  scaffold a chapter file from the template
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "book"
CHAPTERS = BOOK / "chapters"
SITE = BOOK / "_site"
MANIFEST = BOOK / "book.json"
TEMPLATE = BOOK / "templates" / "chapter.html"

EXT_LANG = {
    ".py": "python", ".json": "json", ".jsonc": "json", ".toml": "toml",
    ".yml": "yaml", ".yaml": "yaml", ".sh": "bash", ".bash": "bash",
    ".sql": "sql", ".ts": "typescript", ".js": "javascript",
    ".html": "html", ".css": "css", ".md": "markdown", ".jq": "text",
}

errors: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)
    print(f"  ! {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    """Tolerated while drafting, fatal in `check`."""
    warnings.append(msg)
    print(f"  ? {msg}", file=sys.stderr)


# --- manifest ------------------------------------------------------------


@dataclass
class Chapter:
    num: str
    slug: str
    title: str
    standfirst: str
    status: str
    part: str
    tag: str | None

    @property
    def path(self) -> Path:
        return CHAPTERS / f"{self.slug}.html"

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    @property
    def label(self) -> str:
        return f"{self.num}. {self.title}"


def load_book() -> tuple[dict, list[Chapter]]:
    book = json.loads(MANIFEST.read_text())
    chapters: list[Chapter] = []
    for part in book["parts"]:
        for c in part["chapters"]:
            chapters.append(
                Chapter(
                    num=str(c["num"]), slug=c["slug"], title=c["title"],
                    standfirst=c.get("standfirst", ""), status=c.get("status", "planned"),
                    part=part["title"], tag=c.get("tag"),
                )
            )
    return book, chapters


# --- region rewriting ----------------------------------------------------


def replace_region(text: str, name: str, body: str, where: str) -> str:
    pattern = re.compile(
        rf"(<!-- BEGIN:{name} -->)(.*?)(<!-- END:{name} -->)", re.DOTALL
    )
    if not pattern.search(text):
        fail(f"{where}: missing BEGIN/END:{name} markers")
        return text
    return pattern.sub(lambda m: m.group(1) + body + m.group(3), text, count=1)


def get_region(text: str, name: str) -> str | None:
    m = re.search(rf"<!-- BEGIN:{name} -->(.*?)<!-- END:{name} -->", text, re.DOTALL)
    return m.group(1) if m else None


# --- code includes -------------------------------------------------------

INCLUDE_RE = re.compile(
    r"(?P<open><!-- include:(?P<args>[^>]*?)-->)(?P<old>.*?)(?P<close><!-- endinclude -->)",
    re.DOTALL,
)


def parse_args(raw: str) -> tuple[str, dict[str, str]]:
    parts = raw.strip().split()
    if not parts:
        return "", {}
    src, opts = parts[0], {}
    for tok in parts[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            opts[k] = v
    return src, opts


def slice_region(lines: list[str], name: str, src: str) -> list[str]:
    start = end = None
    for i, line in enumerate(lines):
        if re.search(rf"\bregion:\s*{re.escape(name)}\b", line) and "endregion" not in line:
            start = i + 1
        elif re.search(rf"\bendregion:\s*{re.escape(name)}\b", line):
            end = i
            break
    if start is None or end is None:
        fail(f"{src}: region '{name}' not found")
        return []
    return lines[start:end]


def dedent(lines: list[str]) -> list[str]:
    pad = min(
        (len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0
    )
    return [l[pad:] if l.strip() else "" for l in lines]


def highlight(code: str, lang: str) -> str:
    try:
        from pygments import highlight as pyg
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import get_lexer_by_name
    except ImportError:  # pragma: no cover
        sys.exit(
            "pygments is required so that highlighting is byte-for-byte reproducible.\n"
            "Run the builder with:  uv run scripts/build.py <command>"
        )
    try:
        lexer = get_lexer_by_name(lang)
    except Exception:
        return html.escape(code)
    return pyg(code, lexer, HtmlFormatter(nowrap=True)).rstrip("\n")


def render_include(args: str, where: str) -> str:
    src, opts = parse_args(args)
    if not src:
        fail(f"{where}: include with no path")
        return "\n"

    path = ROOT / src
    if not path.is_file():
        warn(f"{where}: include target not written yet — {src}")
        return (
            '\n<figure class="snippet"><figcaption><span class="path">'
            f"{html.escape(src)}</span><span>not written yet</span></figcaption>"
            "<pre><code></code></pre></figure>\n"
        )

    lines = path.read_text().splitlines()
    detail = ""

    if "region" in opts:
        lines = slice_region(lines, opts["region"], src)
        detail = f"region {opts['region']}"
    elif "lines" in opts:
        a, _, b = opts["lines"].partition("-")
        lo, hi = int(a), int(b or a)
        lines = lines[lo - 1 : hi]
        detail = f"lines {lo}–{hi}"

    lines = dedent(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    lang = opts.get("lang") or EXT_LANG.get(path.suffix, "text")
    caption = opts.get("title", "").replace("_", " ") or src

    return (
        '\n<figure class="snippet">\n'
        f'<figcaption><span class="path">{html.escape(caption)}</span>'
        f"<span>{html.escape(detail)}</span></figcaption>\n"
        f'<pre class="highlight"><code>{highlight(chr(10).join(lines), lang)}</code></pre>\n'
        "</figure>\n"
    )


def expand_includes(text: str, where: str) -> str:
    return INCLUDE_RE.sub(
        lambda m: m.group("open") + render_include(m.group("args"), where) + m.group("close"),
        text,
    )


# --- heading anchors -----------------------------------------------------

HEADING_RE = re.compile(r"<(h[23])>(.*?)</\1>", re.DOTALL)


def slugify(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


def add_anchors(body: str) -> str:
    seen: set[str] = set()

    def repl(m: re.Match) -> str:
        tag, inner = m.group(1), m.group(2)
        base = slugify(inner)
        sid, n = base, 2
        while sid in seen:
            sid, n = f"{base}-{n}", n + 1
        seen.add(sid)
        return (
            f'<{tag} id="{sid}">{inner}'
            f'<a class="anchor" href="#{sid}" aria-label="Link to this section">#</a>'
            f"</{tag}>"
        )

    # only untouched headings; ones already carrying an id are left alone
    return HEADING_RE.sub(repl, body)


# --- generated regions ---------------------------------------------------


def render_sidebar(book: dict, chapters: list[Chapter], current: Chapter | None) -> str:
    out = ['\n<a class="brand" href="../index.html">' + html.escape(book["title"]) + "</a>"]
    for part in book["parts"]:
        out.append(f'<p class="part">{html.escape(part["title"])}</p>')
        out.append("<ol>")
        for c in part["chapters"]:
            ch = next(x for x in chapters if x.slug == c["slug"])
            num = f'<span class="num">{html.escape(ch.num)}</span>'
            title = html.escape(ch.title)
            if not ch.exists:
                out.append(f'<li><a aria-disabled="true">{num}{title}</a></li>')
            else:
                cur = ' aria-current="page"' if current and ch.slug == current.slug else ""
                out.append(f'<li><a href="{ch.slug}.html"{cur}>{num}{title}</a></li>')
        out.append("</ol>")
    return "\n".join(out) + "\n"


def render_head(book: dict, ch: Chapter) -> str:
    meta = [
        f'<span><b>Status</b> <span class="status status-{ch.status}">'
        f"{html.escape(ch.status)}</span></span>",
        f'<span><b>Protocol</b> <code>{html.escape(book["protocol"])}</code></span>',
    ]
    if ch.tag:
        meta.append(
            f'<span><b>Code</b> <code>git checkout {html.escape(ch.tag)}</code></span>'
        )
    return (
        f'\n<p class="eyebrow">{html.escape(ch.part)} &middot; Chapter {html.escape(ch.num)}</p>\n'
        f"<h1>{html.escape(ch.title)}</h1>\n"
        + (f'<p class="standfirst">{html.escape(ch.standfirst)}</p>\n' if ch.standfirst else "")
        + '<div class="chapter-meta">' + "".join(meta) + "</div>\n"
    )


def render_pager(chapters: list[Chapter], ch: Chapter) -> str:
    live = [c for c in chapters if c.exists]
    i = live.index(ch)
    prev = live[i - 1] if i > 0 else None
    nxt = live[i + 1] if i + 1 < len(live) else None

    def link(c: Chapter, direction: str, cls: str) -> str:
        return (
            f'<a class="{cls}" href="{c.slug}.html">'
            f'<span class="dir">{direction}</span>'
            f'<span class="name">{html.escape(c.label)}</span></a>'
        )

    if not prev and not nxt:
        return "\n"

    parts = [link(prev, "Previous", "prev") if prev else '<span class="spacer"></span>']
    parts.append(link(nxt, "Next", "next") if nxt else '<span class="spacer"></span>')
    return '\n<nav class="pager" aria-label="Chapter">\n' + "\n".join(parts) + "\n</nav>\n"


def render_title(book: dict, ch: Chapter) -> str:
    return f"<title>{html.escape(ch.label)} &mdash; {html.escape(book['title'])}</title>"


# --- contents page -------------------------------------------------------


def render_index(book: dict, chapters: list[Chapter]) -> str:
    rows = []
    for part in book["parts"]:
        rows.append(f'<h2 class="part-title">{html.escape(part["title"])}</h2>')
        if part.get("blurb"):
            rows.append(f'<p class="part-blurb">{html.escape(part["blurb"])}</p>')
        rows.append("<ol>")
        for c in part["chapters"]:
            ch = next(x for x in chapters if x.slug == c["slug"])
            name = html.escape(ch.title)
            link = (
                f'<a href="chapters/{ch.slug}.html">{name}</a>' if ch.exists else f"<span>{name}</span>"
            )
            rows.append(
                f'<li><span class="num">{html.escape(ch.num)}</span>{link}'
                f'<span class="status status-{ch.status}">{html.escape(ch.status)}</span></li>'
            )
        rows.append("</ol>")

    done = sum(1 for c in chapters if c.status in ("reviewed", "done"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(book["title"])}</title>
<meta name="description" content="{html.escape(book["subtitle"])}">
<link rel="stylesheet" href="assets/book.css">
<script src="assets/book.js" defer></script>
</head>
<body>
<button class="theme-toggle" type="button" data-theme-toggle aria-label="Toggle colour theme">&#9680;</button>
<div class="shell">
<main class="content toc">

<header class="chapter-head">
<p class="eyebrow">A practical guide</p>
<h1>{html.escape(book["title"])}</h1>
<p class="standfirst">{html.escape(book["subtitle"])}</p>
<div class="chapter-meta">
<span><b>Protocol</b> <code>{html.escape(book["protocol"])}</code></span>
<span><b>Spine project</b> <code>{html.escape(book["spine"])}</code></span>
<span><b>Progress</b> {done} of {len(chapters)} chapters reviewed</span>
<span><a href="{html.escape(book["repo"])}">Source</a></span>
</div>
</header>

{chr(10).join(rows)}

</main>
</div>
</body>
</html>
"""


# --- commands ------------------------------------------------------------


def cmd_build() -> None:
    book, chapters = load_book()
    touched = 0

    for ch in chapters:
        if not ch.exists:
            continue
        original = ch.path.read_text()
        text = original

        text = replace_region(text, "title", render_title(book, ch), ch.slug)
        text = replace_region(text, "sidebar", render_sidebar(book, chapters, ch), ch.slug)
        text = replace_region(text, "head", render_head(book, ch), ch.slug)
        text = replace_region(text, "pager", render_pager(chapters, ch), ch.slug)

        body = get_region(text, "body")
        if body is None:
            fail(f"{ch.slug}: missing BEGIN/END:body markers")
        else:
            new_body = add_anchors(expand_includes(body, ch.slug))
            text = replace_region(text, "body", new_body, ch.slug)

        if text != original:
            ch.path.write_text(text)
            touched += 1
            print(f"  ~ {ch.path.relative_to(ROOT)}")

    index = BOOK / "index.html"
    rendered = render_index(book, chapters)
    if not index.is_file() or index.read_text() != rendered:
        index.write_text(rendered)
        touched += 1
        print(f"  ~ {index.relative_to(ROOT)}")

    live = sum(1 for c in chapters if c.exists)
    print(f"build: {live}/{len(chapters)} chapters written, {touched} file(s) updated")


def cmd_site() -> None:
    cmd_build()
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    shutil.copytree(BOOK / "assets", SITE / "assets")
    shutil.copytree(CHAPTERS, SITE / "chapters", ignore=shutil.ignore_patterns(".gitkeep"))
    shutil.copy2(BOOK / "index.html", SITE / "index.html")
    (SITE / ".nojekyll").write_text("")
    print(f"site: {SITE.relative_to(ROOT)}")


def check_links() -> None:
    for path in sorted(CHAPTERS.glob("*.html")) + [BOOK / "index.html"]:
        if not path.is_file():
            continue
        for href in re.findall(r'href="([^"#:]+)(?:#[^"]*)?"', path.read_text()):
            if href.startswith(("http", "//", "mailto:")):
                continue
            if not (path.parent / href).resolve().exists():
                fail(f"{path.name}: dead link -> {href}")


def cmd_check() -> None:
    cmd_build()
    check_links()
    errors.extend(warnings)  # a placeholder snippet must not reach a published chapter

    r = subprocess.run(
        ["git", "status", "--porcelain", "book/"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.stdout.strip():
        fail("book/ is not up to date — run scripts/build.py build and commit the result:\n"
             + r.stdout.rstrip())

    if errors:
        print(f"\ncheck: {len(errors)} problem(s)", file=sys.stderr)
        sys.exit(1)
    print("check: clean")


def cmd_new(slug: str) -> None:
    book, chapters = load_book()
    match = [c for c in chapters if c.slug == slug or c.num == slug]
    if not match:
        sys.exit(f"no chapter '{slug}' in book.json")
    ch = match[0]
    if ch.exists:
        sys.exit(f"{ch.path.relative_to(ROOT)} already exists")
    ch.path.write_text(TEMPLATE.read_text())
    print(f"  + {ch.path.relative_to(ROOT)}")
    cmd_build()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("build")
    sub.add_parser("site")
    sub.add_parser("check")
    p_new = sub.add_parser("new")
    p_new.add_argument("slug")
    args = ap.parse_args()

    if args.cmd == "site":
        cmd_site()
    elif args.cmd == "check":
        cmd_check()
    elif args.cmd == "new":
        cmd_new(args.slug)
    else:
        cmd_build()

    if errors and args.cmd != "check":
        print(f"\n{len(errors)} problem(s)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
