#!/usr/bin/env python3
"""
Convert a tree of markdown files into a static HTML site.

Runs from the repo root as `.tools/build.py`.
Reads `.md` files recursively, renders them, rewrites internal `.md` links to `.html`.
Wraps each in `template.html`, and writes the mirror tree under `.public/`.
Source files are never modified.
"""

import html as htmllib
import posixpath
import re
import shutil
import tomllib
from pathlib import Path

import markdown

ROOT = Path.cwd()                 # run from your repo root; the code may live elsewhere (on PATH)
TOOLS = ROOT / ".tools"           # per-repo content files live here, not next to the code
OUTPUT = ROOT / ".public"
TEMPLATE = TOOLS / "template.html"
STYLE = TOOLS / "style.css"
ROBOTS = TOOLS / "robots.txt"
CONFIG = TOOLS / "config.toml"

# Placeholders build() substitutes; a template missing any is stale or wrong.
TEMPLATE_MARKERS = ("{{title}}", "{{nav}}", "{{content}}", "{{footer}}")

EXTENSIONS = ["meta", "toc", "footnotes", "tables", "fenced_code"]

NAV_MODES = ("none", "browse", "readme")

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
    # Rewrite internal `.md` links to root-absolute `.html` URLs.
    # page_rel    : the page's path relative to the output root. 
    page_dir = page_rel.parent.as_posix()

    def repl(m):
        url = m.group(2)
        if re.match(r"[a-z][a-z0-9+.-]*://", url) or url.startswith("//"):
            return m.group(0)  # leave external links alone
        target = posixpath.normpath(posixpath.join(page_dir, url[:-3]))
        href = "/index.html" if target == "README" else "/" + target + ".html"
        return m.group(1) + href + m.group(3)

    return LINK_RE.sub(repl, body)


def pick_title(meta, body, stem, front=None):
    # front: config override for the homepage (README), wins over everything.
    if front:
        return front
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
    # Copyright footer HTML, or empty string if no [copyright] section is configured.

    c = cfg.get("copyright")
    if c is None:
        return ""
    missing = [k for k in ("author", "year", "tag") if not c.get(k)]
    if missing:
        raise SystemExit(f"[copyright] is missing required key(s): {', '.join(missing)}")
    year = htmllib.escape(str(c["year"]))
    author = htmllib.escape(str(c["author"]))
    # tag goes through markdown so it can carry a link (e.g. a license).
    # markdown.markdown wraps output in <p>; strip it since this is inline.
    tag = markdown.markdown(str(c["tag"])).removeprefix("<p>").removesuffix("</p>")
    return f"<footer>Copyright {year}, {author}. {tag}</footer>"


# Reveal the current page: open the ancestor <details> chain of whichever
# sidebar link matches this URL, leaving every other folder collapsed.
NAV_SCRIPT = """<script>
(function () {
  function norm(p) {
    return decodeURIComponent(p)
      .replace(/\\/+$/, "").replace(/\\.html$/, "").replace(/\\/index$/, "");
  }
  var here = norm(location.pathname);
  var links = document.querySelectorAll(".sidebar a");
  for (var i = 0; i < links.length; i++) {
    if (norm(links[i].getAttribute("href")) === here) {
      var el = links[i].parentElement;
      while (el) {
        if (el.tagName === "DETAILS") el.open = true;
        el = el.parentElement;
      }
      break;
    }
  }
})();
</script>"""


HOME_LINK = '<ul class="nav-home"><li><a href="/index.html">Home</a></li></ul>'


def nav_tree(pages):
    # tree node: {"files": [(title, out)], "dirs": {name: node}}
    tree = {"files": [], "dirs": {}}
    for out, title in pages:
        node = tree
        for part in out.parent.parts:  # () at root, ("notes",), ("notes","sub"), ...
            node = node["dirs"].setdefault(part, {"files": [], "dirs": {}})
        node["files"].append((title, out))
    return tree


def render_tree(node, path):
    # Collapsible tree of a node's files and subfolders. `path` seeds the
    # data-path keys, so a scoped tree's fold-state stays namespaced to its section.
    lines = []
    files = sorted(node["files"], key=lambda t: t[0].lower())
    if files:
        lines.append("<ul>")
        for title, out in files:
            href = "/" + out.as_posix()
            lines.append(f'<li><a href="{href}">{htmllib.escape(title)}</a></li>')
        lines.append("</ul>")
    for name in sorted(node["dirs"]):
        sub = f"{path}/{name}" if path else name
        lines.append(f'<details data-path="{htmllib.escape(sub)}">')
        lines.append(f"<summary>{htmllib.escape(name)}</summary>")
        lines.extend(render_tree(node["dirs"][name], sub))
        lines.append("</details>")
    return lines


def wrap_nav(lines):
    return "\n".join(['<nav class="sidebar">', *lines, "</nav>", NAV_SCRIPT])


def build_browse_nav(pages):
    # One shared sidebar: the whole site as a collapsible tree.
    return wrap_nav(render_tree(nav_tree(pages), ""))


def build_readme_navs(pages):
    # 'readme' mode. Returns (global_nav, {section: scoped_nav}).
    # Global nav (shown on root-level pages): root file links, then a link to each
    # top-level directory's README (directories without one are omitted).
    # Scoped nav (shown on a page inside a top-level directory): that directory's
    # own subtree browsed in full, with a Home link back to the site root on top.
    root_files, sections = [], {}
    for out, title in pages:
        if len(out.parts) == 1:
            root_files.append((out, title))
        else:
            sections.setdefault(out.parts[0], []).append((out, title))

    lines, section_items, scoped = [], [], {}
    if root_files:
        # Homepage pinned first; the rest of the root files follow alphabetically.
        home = [p for p in root_files if p[0] == Path("index.html")]
        rest = sorted((p for p in root_files if p[0] != Path("index.html")),
                      key=lambda x: x[1].lower())
        items = "".join(
            f'<li><a href="/{o.as_posix()}">{htmllib.escape(t)}</a></li>'
            for o, t in home + rest
        )
        lines.append(f"<ul>{items}</ul>")

    for name in sorted(sections):
        node = nav_tree(sections[name])["dirs"][name]  # every page here shares `name` as parts[0]
        readme_out = Path(name) / "README.html"
        readme = next((f for f in node["files"] if f[1] == readme_out), None)
        if readme:
            # README heads the section; its siblings nest one level beneath it.
            title, out = readme
            siblings = {"files": [f for f in node["files"] if f[1] != readme_out],
                        "dirs": node["dirs"]}
            link = f'<a href="/{out.as_posix()}">{htmllib.escape(title)}</a>'
            section = [f"<ul><li>{link}", *render_tree(siblings, name), "</li></ul>"]
            section_items.append(f"<li>{link}</li>")
        else:
            section = render_tree(node, name)
        scoped[name] = wrap_nav([HOME_LINK, *section])

    if section_items:
        lines.append("<ul>" + "".join(section_items) + "</ul>")
    return wrap_nav(lines), scoped


def build():
    cfg = load_config()
    nav = cfg.get("site-layout", {}).get("nav", "none")
    if nav not in NAV_MODES:
        raise SystemExit(f"[site-layout] nav must be one of {', '.join(NAV_MODES)}; got {nav!r}")
    front = cfg.get("site-layout", {}).get("front")
    footer_html = build_footer(cfg)

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    if not TEMPLATE.exists():
        raise SystemExit(f"missing {TEMPLATE}. Run 'md-tools setup' in this repo first.")
    template = TEMPLATE.read_text(encoding="utf-8")
    stale = [m for m in TEMPLATE_MARKERS if m not in template]
    if stale:
        raise SystemExit(
            f"{TEMPLATE} is missing placeholder(s) {', '.join(stale)}; it may be from an "
            f"older version. Run 'md-tools setup --override template.html'. Refusing to build."
        )
    md = make_md()

    # Render every page and collect (output path, title) before writing
    rendered = []  # (out_path, title, body)
    for path in ROOT.rglob("*"):
        # Skip dot-dirs (.tools, .public, .git, ...)
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        if path.is_dir():
            continue

        rel = path.relative_to(ROOT)
        if path.suffix == ".md":
            out = OUTPUT / rel.with_suffix(".html")
            is_readme = rel == Path("README.md")
            if is_readme:
                out = OUTPUT / "index.html"
            body = rewrite_links(
                render(md, path.read_text(encoding="utf-8")),
                out.relative_to(OUTPUT),
            )
            title = pick_title(md.Meta, body, path.stem, front if is_readme else None)
            rendered.append((out, title, body))
        else:
            # Non-md asset: copy through, preserving structure.
            asset_out = OUTPUT / rel
            asset_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, asset_out)

    pages = [(out.relative_to(OUTPUT), title) for out, title, _ in rendered]
    global_nav, scoped = "", {}
    if nav == "browse":
        global_nav = build_browse_nav(pages)
    elif nav == "readme":
        global_nav, scoped = build_readme_navs(pages)

    # Write pages, each with its nav injected. In 'readme' mode a page inside a
    # top-level directory gets that section's scoped nav; anything else (root pages,
    # and every page in 'browse'/'none') gets global_nav.
    for out, title, body in rendered:
        nav_html = scoped.get(out.relative_to(OUTPUT).parts[0], global_nav)
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
    print(f"built -> {OUTPUT}" + (f" (nav: {nav})" if nav != "none" else ""))


def selfcheck():
    md = make_md()
    render(md, "First[^1]\n\n[^1]: alpha")
    second = render(md, "Second[^2]\n\n[^2]: bravo")
    assert "alpha" not in second, "footnote leaked between files (reset broken)"
    assert "bravo" in second
    assert pick_title({"title": ["FM"]}, "<h1>H</h1>", "stem", front="Cfg") == "Cfg"
    assert pick_title({"title": ["FM"]}, "<h1>H</h1>", "stem") == "FM"
    assert rewrite_links('<a href="foo.md#x">', Path("index.html")) == '<a href="/foo.html#x">'
    assert rewrite_links('<a href="https://x.md">', Path("index.html")) == '<a href="https://x.md">'
    # ../README.md from a nested page resolves to the homepage (index.html).
    assert rewrite_links('<a href="../README.md">', Path("notes/intro.html")) == '<a href="/index.html">'
    # Sibling link from a nested page stays in its folder.
    assert rewrite_links('<a href="methods.md">', Path("notes/intro.html")) == '<a href="/notes/methods.html">'
    nav = build_browse_nav([
        (Path("index.html"), "Home"),
        (Path("notes/a.html"), "Alpha"),
        (Path("notes/sub/b.html"), "Bravo"),
    ])
    assert '<a href="/notes/a.html">Alpha</a>' in nav
    assert "<summary>notes</summary>" in nav and 'href="/index.html"' in nav
    # Nesting is real: `sub` is a folder inside `notes`, not a flat `notes/sub` label.
    assert "<summary>sub</summary>" in nav and 'data-path="notes/sub"' in nav
    assert "<summary>notes/sub</summary>" not in nav
    # Sidebar reveals the current page instead of persisting fold state.
    assert "location.pathname" in nav and "localStorage" not in nav

    g, scoped = build_readme_navs([
        (Path("index.html"), "Home"),
        (Path("about.html"), "About"),
        (Path("notes/README.html"), "Notes"),
        (Path("notes/intro.html"), "Intro"),
        (Path("notes/deep/README.html"), "Deep"),
        (Path("misc/scratch.html"), "Scratch"),
    ])
    # Global nav: root files + a link to each section's README; a section without
    # a README (misc) is omitted entirely.
    assert 'href="/index.html">Home' in g and 'href="/about.html">About' in g
    assert 'href="/notes/README.html">Notes' in g
    assert "Scratch" not in g and "/misc/" not in g
    # Homepage is pinned to the top, ahead of alphabetically-earlier root files.
    assert g.index("/index.html") < g.index("/about.html")
    # Scoped nav exists for every section, even the README-less one (its pages
    # still need a sidebar when reached directly).
    assert set(scoped) == {"notes", "misc"}
    ns = scoped["notes"]
    assert HOME_LINK in ns                              # back-home link on top
    # The section README heads the scope once; its siblings nest under it.
    assert 'href="/notes/README.html">Notes' in ns and ns.count("/notes/README.html") == 1
    assert 'href="/notes/intro.html">Intro' in ns
    # A nested README is just an ordinary browsable file inside its folder.
    assert 'href="/notes/deep/README.html">Deep' in ns and "<summary>deep</summary>" in ns
    assert "/about.html" not in ns                      # otherwise strictly scoped
    assert build_footer({}) == ""
    assert build_footer({"copyright": {"year": 2026, "author": "John Doe", "tag": "CC BY 4.0"}}) == \
        "<footer>Copyright 2026, John Doe. CC BY 4.0</footer>"
    assert build_footer({"copyright": {"year": 2026, "author": "John Doe",
        "tag": "Licensed under [CC BY-NC 4.0](https://example.com)"}}) == \
        '<footer>Copyright 2026, John Doe. Licensed under <a href="https://example.com">CC BY-NC 4.0</a></footer>'
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
