#!/usr/bin/env python3
"""Convert a tree of markdown files into a static HTML site.

Runs from the research repo root as `.tools/build.py`.
Reads `.md` files recursively, renders them, rewrites internal `.md` links to `.html`, wraps each in `template.html`, and writes the mirror tree under `.public/`.
Source files are never modified.
"""

import html as htmllib
import re
import shutil
from pathlib import Path

import markdown

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent          # repo root when deployed as .tools/build.py
OUTPUT = ROOT / ".public"
TEMPLATE = SCRIPT_DIR / "template.html"
STYLE = SCRIPT_DIR / "style.css"

EXTENSIONS = ["meta", "toc", "footnotes", "tables", "fenced_code"]

# Rewrite href="...md" / href="...md#anchor" on rendered HTML.
# Matching the href attribute (not raw markdown) skips code blocks and covers reference links automatically.
LINK_RE = re.compile(r"""(href=["'])([^"']*\.md)((?:#[^"']*)?["'])""")
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def make_md():
    return markdown.Markdown(extensions=EXTENSIONS)


def render(md, text):
    # reset() is mandatory: footnotes/meta state accumulates on the instance and would leak between files otherwise.
    md.reset()
    return md.convert(text)


def rewrite_links(body):
    def repl(m):
        url = m.group(2)
        if re.match(r"[a-z][a-z0-9+.-]*://", url) or url.startswith("//"):
            return m.group(0)  # leave external links alone
        return m.group(1) + url[:-3] + ".html" + m.group(3)

    return LINK_RE.sub(repl, body)


def pick_title(meta, body, stem):
    if meta.get("title"):
        return meta["title"][0]
    m = H1_RE.search(body)
    if m:
        return TAG_RE.sub("", m.group(1)).strip()
    return stem


def build():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    template = TEMPLATE.read_text(encoding="utf-8")
    md = make_md()

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
            body = rewrite_links(render(md, path.read_text(encoding="utf-8")))
            title = pick_title(md.Meta, body, path.stem)
            page = template.replace("{{title}}", htmllib.escape(title)).replace(
                "{{content}}", body
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(page, encoding="utf-8")
        else:
            # Non-md asset: copy through, preserving structure.
            out = OUTPUT / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)

    shutil.copy2(STYLE, OUTPUT / "style.css")
    print(f"built -> {OUTPUT}")


def selfcheck():
    md = make_md()
    render(md, "First[^1]\n\n[^1]: alpha")
    second = render(md, "Second[^2]\n\n[^2]: bravo")
    assert "alpha" not in second, "footnote leaked between files (reset broken)"
    assert "bravo" in second
    assert rewrite_links('<a href="foo.md#x">') == '<a href="foo.html#x">'
    assert rewrite_links('<a href="https://x.md">') == '<a href="https://x.md">'
    print("selfcheck ok")


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        build()
