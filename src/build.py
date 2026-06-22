#!/usr/bin/env python3
"""
Convert a tree of markdown files into a static HTML site.

Runs from the research repo root as `.tools/build.py`.
Reads `.md` files recursively, renders them, rewrites internal `.md` links to `.html`; 
wraps each in `template.html`, and writes the mirror tree under `.public/`.
Source files are never modified.
"""

import html as htmllib
import posixpath
import re
import shutil
import tomllib  # stdlib, Python 3.11+
from pathlib import Path

import markdown

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent          # repo root when deployed as .tools/build.py
OUTPUT = ROOT / ".public"
TEMPLATE = SCRIPT_DIR / "template.html"
STYLE = SCRIPT_DIR / "style.css"
ROBOTS = SCRIPT_DIR / "robots.txt"
CONFIG = SCRIPT_DIR / "config.toml"

EXTENSIONS = ["meta", "toc", "footnotes", "tables", "fenced_code"]

# Rewrite href="...md" / href="...md#anchor" on rendered HTML.
# Matching the href attribute (not raw markdown) skips code blocks and covers reference links automatically.
LINK_RE = re.compile(r"""(href=["'])([^"']*\.md)((?:#[^"']*)?["'])""")
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def make_md():
    return markdown.Markdown(extensions=EXTENSIONS)


def render(md, text):
    # reset() is mandatory: 
    # footnotes/meta state accumulates on the instance and would leak between files otherwise.
    md.reset()
    return md.convert(text)


def rewrite_links(body, page_rel):
    """
    Rewrite internal `.md` links to root-absolute `.html` URLs.

    page_rel is the page's path relative to the output root (e.g.
    `notes/intro.html`). Each link is resolved relative to the page's folder,
    so `../README.md` from `notes/` lands at the repo root. Root-absolute output
    means no per-page `../` depth to get wrong, matching `/style.css` and the
    nav. The root `README.md` is the homepage, so a link resolving to it maps to
    `/index.html` (it is written as index.html, not README.html).
    """
    page_dir = page_rel.parent.as_posix()

    def repl(m):
        url = m.group(2)
        if re.match(r"[a-z][a-z0-9+.-]*://", url) or url.startswith("//"):
            return m.group(0)  # leave external links alone
        target = posixpath.normpath(posixpath.join(page_dir, url[:-3]))
        href = "/index.html" if target == "README" else "/" + target + ".html"
        return m.group(1) + href + m.group(3)

    return LINK_RE.sub(repl, body)


def pick_title(meta, body, stem):
    if meta.get("title"):
        return meta["title"][0]
    m = H1_RE.search(body)
    if m:
        return TAG_RE.sub("", m.group(1)).strip()
    return stem


def load_config():
    if not CONFIG.exists():
        return {}
    with CONFIG.open("rb") as f:
        return tomllib.load(f)


def build_footer(cfg):
    """
    Copyright footer HTML, or "" if no [copyright] section is configured.

    When the section is present, author/year/tag are all required; a missing key
    is a config error rather than something to paper over with a default.
    """
    c = cfg.get("copyright")
    if c is None:
        return ""
    missing = [k for k in ("author", "year", "tag") if not c.get(k)]
    if missing:
        raise SystemExit(f"[copyright] is missing required key(s): {', '.join(missing)}")
    year = htmllib.escape(str(c["year"]))
    author = htmllib.escape(str(c["author"]))
    tag = htmllib.escape(str(c["tag"]))
    return f"<footer>Copyright {year}, {author}. {tag}</footer>"


def build_nav(pages):
    """
    Sidebar HTML: pages grouped by their output folder, link text = title.

    Each distinct folder is one flat labeled group; a nested folder like
    `notes/sub` is just its own group rather than an indented subtree.
    ponytail: flat groups, go recursive/indented only if the tree gets deep.
    """
    groups = {}
    for out, title in pages:
        groups.setdefault(out.parent, []).append((title, out))
    # Root group (".") first, then folders alphabetically.
    out_lines = ['<nav class="sidebar">']
    for folder in sorted(groups, key=lambda f: (f != Path("."), f.as_posix())):
        if folder != Path("."):
            out_lines.append(f"<h3>{htmllib.escape(folder.as_posix())}</h3>")
        out_lines.append("<ul>")
        for title, out in sorted(groups[folder], key=lambda t: t[0].lower()):
            href = "/" + out.as_posix()
            out_lines.append(
                f'<li><a href="{href}">{htmllib.escape(title)}</a></li>'
            )
        out_lines.append("</ul>")
    out_lines.append("</nav>")
    return "\n".join(out_lines)


def build():
    cfg = load_config()
    nav = cfg.get("site-layout", {}).get("nav", False)
    footer_html = build_footer(cfg)

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    template = TEMPLATE.read_text(encoding="utf-8")
    md = make_md()

    # Phase 1: render every page and collect (output path, title) before writing, 
    # since the nav lists all pages and is identical on each one.
    rendered = []  # (out_path, title, body)
    for path in ROOT.rglob("*"):
        # Skip dot-dirs (.tools, .public, .git, ...) entirely.
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        if path.is_dir():
            continue

        rel = path.relative_to(ROOT)
        if path.suffix == ".md":
            out = OUTPUT / rel.with_suffix(".html")
            if rel == Path("README.md"):
                out = OUTPUT / "index.html"
            body = rewrite_links(
                render(md, path.read_text(encoding="utf-8")),
                out.relative_to(OUTPUT),
            )
            title = pick_title(md.Meta, body, path.stem)
            rendered.append((out, title, body))
        else:
            # Non-md asset: copy through, preserving structure.
            asset_out = OUTPUT / rel
            asset_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, asset_out)

    nav_html = ""
    if nav:
        nav_html = build_nav([(out.relative_to(OUTPUT), title) for out, title, _ in rendered])

    # Phase 2: write pages with the shared nav injected.
    for out, title, body in rendered:
        page = (
            template.replace("{{title}}", htmllib.escape(title))
            .replace("{{nav}}", nav_html)
            .replace("{{content}}", body)
            .replace("{{footer}}", footer_html)
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")

    shutil.copy2(STYLE, OUTPUT / "style.css")
    shutil.copy2(ROBOTS, OUTPUT / "robots.txt")
    print(f"built -> {OUTPUT}" + (" (with nav)" if nav else ""))


def selfcheck():
    md = make_md()
    render(md, "First[^1]\n\n[^1]: alpha")
    second = render(md, "Second[^2]\n\n[^2]: bravo")
    assert "alpha" not in second, "footnote leaked between files (reset broken)"
    assert "bravo" in second
    assert rewrite_links('<a href="foo.md#x">', Path("index.html")) == '<a href="/foo.html#x">'
    assert rewrite_links('<a href="https://x.md">', Path("index.html")) == '<a href="https://x.md">'
    # ../README.md from a nested page resolves to the homepage (index.html).
    assert rewrite_links('<a href="../README.md">', Path("notes/intro.html")) == '<a href="/index.html">'
    # Sibling link from a nested page stays in its folder.
    assert rewrite_links('<a href="methods.md">', Path("notes/intro.html")) == '<a href="/notes/methods.html">'
    nav = build_nav([(Path("index.html"), "Home"), (Path("notes/a.html"), "Alpha")])
    assert '<a href="/notes/a.html">Alpha</a>' in nav
    assert "<h3>notes</h3>" in nav and 'href="/index.html"' in nav
    assert build_footer({}) == ""
    assert build_footer({"copyright": {"year": 2026, "author": "John Doe", "tag": "CC BY 4.0"}}) == \
        "<footer>Copyright 2026, John Doe. CC BY 4.0</footer>"
    try:
        build_footer({"copyright": {"author": "John Doe"}})
    except SystemExit:
        pass
    else:
        assert False, "missing copyright keys should fail the build"
    print("selfcheck ok")


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        build()
