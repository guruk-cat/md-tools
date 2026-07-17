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
TEMPLATE_MARKERS = ("{{title}}", "{{header}}", "{{nav}}", "{{content}}", "{{footer}}")

EXTENSIONS = ["meta", "toc", "footnotes", "tables", "fenced_code"]

SIDEBAR_MODES = ("none", "browse", "readme", "toc")

# Rewrite href="...md" / href="...md#anchor" on rendered HTML.
# Matching the href attribute (not raw markdown) skips code blocks and covers reference links automatically.
# Markers that turn a line into a block (list, heading, quote) when it leads one.
LEADING_BLOCK_RE = re.compile(r"^\s*([#>]+|\d+[.)]|[-+*])(?=\s|$)")

LINK_RE = re.compile(r"""(href=["'])([^"']*\.md)((?:#[^"']*)?["'])""")
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

# Markers and item shape that toc.py writes; 'toc' mode reads the block back out.
TOC_OPEN = "<!-- toc -->"
TOC_CLOSE = "<!-- /toc -->"
TOC_ITEM_RE = re.compile(r"^(\s*)- \[(.+)\]\(#(.+)\)\s*$")
TOC_TITLE_RE = re.compile(r"^##\s+(.*?)\s*#*\s*$")
TOC_INDENT = 4  # toc.py indents one nesting level per 4 spaces


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


def pick_title(meta, body, stem, home=None):
    # home: config override for the homepage (README), wins over everything.
    if home:
        return home
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


def escape_leading(m):
    # A numeric marker needs the backslash on its punctuation ("1\."), the rest
    # on the character itself ("\-").
    tok = m.group(1)
    if tok[0].isdigit():
        return m.group(0).replace(tok, tok[:-1] + "\\" + tok[-1])
    return m.group(0).replace(tok, "\\" + tok[0] + tok[1:])


def inline_md(text):
    # markdown.markdown parses its argument as a block, so a heading numbered
    # "1." arrives as an <ol>, not text. Escaping a leading block marker keeps it
    # literal; inline markup (links, `code`) still renders.
    text = LEADING_BLOCK_RE.sub(escape_leading, str(text))
    return markdown.markdown(text).removeprefix("<p>").removesuffix("</p>")


def build_footer(cfg):
    # Footer HTML from [footer] lines, or "" if no [footer] section is configured.
    # Each [[footer.line]] carries `text` rendered as markdown
    f = cfg.get("footer")
    if f is None:
        return ""
    lines = []
    for line in f.get("line", []):
        text = line.get("text")
        if not text:
            raise SystemExit("[[footer.line]] entries each need a 'text'")
        lines.append(f"<div>{inline_md(text)}</div>")
    if not lines:
        return ""
    return "<footer>" + "".join(lines) + "</footer>"


HEADER_MODES = ("disabled", "home", "not home", "all")


def build_masthead(cfg):
    # (mode, html): mode decides which pages carry the bar 
    # ("home" | "not home" | "all" | "disabled")
    h = cfg.get("header")
    if not h:
        return ("disabled", "")
    mode = h.get("show", "disabled")
    if mode not in HEADER_MODES:
        raise SystemExit(f"[header] show must be one of {', '.join(HEADER_MODES)}; got {mode!r}")
    if mode == "disabled":
        return (mode, "")
    items = []
    for link in h.get("link", []):
        if not link.get("name") or not link.get("url"):
            raise SystemExit("[[header.link]] entries each need both 'name' and 'url'")
        name = htmllib.escape(str(link["name"]))
        url = htmllib.escape(str(link["url"]))
        items.append(f'<a href="{url}">{name}</a>')

    home = h.get("homelink")
    if home is not None and not home.get("name"):
        raise SystemExit("[header.homelink] needs a 'name'")
    if not items and home is None:
        return (mode, "")

    links = f'<nav class="links">{"".join(items)}</nav>' if items else ""
    if home is None:
        return (mode, f'<header class="masthead">{links}</header>')
    name = htmllib.escape(str(home["name"]))
    return (mode, f'<header class="masthead"><a href="/index.html">{name}</a>{links}</header>')


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


def home_link(title):
    return f'<ul class="nav-home"><li><a href="/index.html">{htmllib.escape(title)}</a></li></ul>'


def parse_toc_block(text, source):
    # Pull toc.py's block out of the markdown source: 'toc' mode shows it in the
    # sidebar instead of the body, so it must not render twice.
    # Returns (text_without_block, title, [(level, label, sid)]); no block -> unchanged text.
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.strip() == TOC_OPEN), None)
    if start is None:
        return text, "", []
    end = next((j for j in range(start + 1, len(lines)) if lines[j].strip() == TOC_CLOSE), None)
    if end is None:
        raise SystemExit(
            f"{source}: unterminated TOC block: found '{TOC_OPEN}' with no matching "
            f"'{TOC_CLOSE}'. Fix the markers; refusing to build."
        )
    title, items = "", []
    for line in lines[start + 1:end]:
        m = TOC_ITEM_RE.match(line)
        if m:
            items.append((len(m.group(1)) // TOC_INDENT, m.group(2), m.group(3)))
            continue
        t = TOC_TITLE_RE.match(line)
        if t and not title:
            title = t.group(1)
    return "\n".join(lines[:start] + lines[end + 1:]), title, items


def toc_tree(items):
    # Flat (level, label, sid) list -> nested nodes. A level that skips a rung
    # (H2 straight to H4) just nests one level; the TOC is for navigating, not
    # for reproducing the heading arithmetic.
    root = []
    stack = [(-1, root)]
    for level, label, sid in items:
        node = {"label": label, "sid": sid, "kids": []}
        while stack[-1][0] >= level:
            stack.pop()
        stack[-1][1].append(node)
        stack.append((level, node["kids"]))
    return root


def render_toc_nodes(nodes, top):
    # Only first-level sections fold; everything under one renders with it.
    lines = ["<ul>"]
    for n in nodes:
        link = f'<a href="#{htmllib.escape(n["sid"])}">{inline_md(n["label"])}</a>'
        if top and n["kids"]:
            lines.append(f"<li><details><summary>{link}</summary>")
            lines.extend(render_toc_nodes(n["kids"], False))
            lines.append("</details></li>")
        else:
            lines.append(f"<li>{link}")
            if n["kids"]:
                lines.extend(render_toc_nodes(n["kids"], False))
            lines.append("</li>")
    lines.append("</ul>")
    return lines


def build_toc_nav(title, items):
    # "" when the page carries no TOC: that page simply gets no sidebar.
    if not items:
        return ""
    head = [f'<div class="toc-title">{htmllib.escape(title)}</div>'] if title else []
    body = render_toc_nodes(toc_tree(items), True)
    return "\n".join(['<nav class="sidebar toc">', *head, *body, "</nav>"])


def nav_tree(pages):
    # tree node: {"files": [(title, out)], "dirs": {name: node}}
    tree = {"files": [], "dirs": {}}
    for out, title in pages:
        node = tree
        for part in out.parent.parts:  # () at root, ("notes",), ("notes","sub"), ...
            node = node["dirs"].setdefault(part, {"files": [], "dirs": {}})
        node["files"].append((title, out))
    return tree


def render_tree(node):
    # Collapsible tree of a node's files and subfolders.
    lines = []
    files = sorted(node["files"], key=lambda t: t[0].lower())
    if files:
        lines.append("<ul>")
        for title, out in files:
            href = "/" + out.as_posix()
            lines.append(f'<li><a href="{href}">{htmllib.escape(title)}</a></li>')
        lines.append("</ul>")
    for name in sorted(node["dirs"]):
        lines.append("<details>")
        lines.append(f"<summary>{htmllib.escape(name)}</summary>")
        lines.extend(render_tree(node["dirs"][name]))
        lines.append("</details>")
    return lines


def wrap_nav(lines):
    return "\n".join(['<nav class="sidebar">', *lines, "</nav>", NAV_SCRIPT])


def build_browse_nav(pages):
    # One shared sidebar: the whole site as a collapsible tree.
    return wrap_nav(render_tree(nav_tree(pages)))


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

    # Back-home link reuses the homepage's own title (which already carries the
    # `home` config override), so it matches the pinned entry in the global nav.
    home_title = next((t for o, t in root_files if o == Path("index.html")), "Home")

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
            section = [f"<ul><li>{link}", *render_tree(siblings), "</li></ul>"]
            section_items.append(f"<li>{link}</li>")
        else:
            section = render_tree(node)
        scoped[name] = wrap_nav([home_link(home_title), *section])

    if section_items:
        lines.append("<ul>" + "".join(section_items) + "</ul>")
    return wrap_nav(lines), scoped


def build():
    cfg = load_config()
    sidebar = cfg.get("sidebar", {}).get("mode", "none")
    if sidebar not in SIDEBAR_MODES:
        raise SystemExit(f"[sidebar] mode must be one of {', '.join(SIDEBAR_MODES)}; got {sidebar!r}")
    home = cfg.get("site-layout", {}).get("home")
    footer_html = build_footer(cfg)
    header_mode, masthead_html = build_masthead(cfg)

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
    rendered = []  # (out_path, title, body, toc_nav)
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
            text = path.read_text(encoding="utf-8")
            toc_nav = ""
            if sidebar == "toc":
                text, toc_title, toc_items = parse_toc_block(text, rel)
                toc_nav = build_toc_nav(toc_title, toc_items)
            body = rewrite_links(render(md, text), out.relative_to(OUTPUT))
            show_masthead = masthead_html and (
                header_mode == "all"
                or (header_mode == "home" and is_readme)
                or (header_mode == "not home" and not is_readme)
            )
            page_header = masthead_html if show_masthead else ""
            title = pick_title(md.Meta, body, path.stem, home if is_readme else None)
            rendered.append((out, title, body, toc_nav, page_header))
        else:
            # Non-md asset: copy through, preserving structure.
            asset_out = OUTPUT / rel
            asset_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, asset_out)

    pages = [(out.relative_to(OUTPUT), title) for out, title, *_ in rendered]
    global_nav, scoped = "", {}
    if sidebar == "browse":
        global_nav = build_browse_nav(pages)
    elif sidebar == "readme":
        global_nav, scoped = build_readme_navs(pages)

    # Write pages, each with its sidebar injected. 'toc' mode is per-page (built
    # above, "" where a page has no TOC). In 'readme' mode a page inside a top-level
    # directory gets that section's scoped nav; anything else (root pages, and every
    # page in 'browse'/'none') gets global_nav.
    for out, title, body, toc_nav, page_header in rendered:
        if sidebar == "toc":
            nav_html = toc_nav
        else:
            nav_html = scoped.get(out.relative_to(OUTPUT).parts[0], global_nav)
        page = (
            template.replace("{{title}}", htmllib.escape(title))
            .replace("{{header}}", page_header)
            .replace("{{nav}}", nav_html)
            .replace("{{content}}", body)
            .replace("{{footer}}", footer_html)
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")

    shutil.copy2(STYLE, OUTPUT / "style.css")
    shutil.copy2(ROBOTS, OUTPUT / "robots.txt")
    print(f"built -> {OUTPUT}" + (f" (sidebar: {sidebar})" if sidebar != "none" else ""))


def selfcheck():
    doc = (
        "# Title\n\n"
        "<!-- toc -->\n## Table of Contents\n"
        "- [1. Intro](#1-intro)\n"
        "    - [1.1. The `code` bit](#11-the-code-bit)\n"
        "- [2. Flat](#2-flat)\n"
        "<!-- /toc -->\n\n"
        "## 1. Intro\n"
    )
    body, title, items = parse_toc_block(doc, "t.md")
    assert TOC_OPEN not in body and "1. Intro](#" not in body  # block left the body
    assert "# Title" in body and "## 1. Intro" in body         # rest of the page survived
    assert title == "Table of Contents"
    assert items == [(0, "1. Intro", "1-intro"),
                     (1, "1.1. The `code` bit", "11-the-code-bit"),
                     (0, "2. Flat", "2-flat")]

    nav = build_toc_nav(title, items)
    assert "<details><summary>" in nav          # section with children folds
    assert "<code>code</code>" in nav           # inline markdown in a heading renders
    assert nav.count("<details>") == 1          # childless section stays a plain link
    assert "open" not in nav                    # folded by default

    # A page with no TOC gets no sidebar at all, and its body is untouched.
    plain = "# Just a page\n\n## A\n"
    b, t, i = parse_toc_block(plain, "p.md")
    assert (b, t, i) == (plain, "", [])
    assert build_toc_nav(t, i) == ""

    # Unterminated block must refuse rather than swallow the page.
    try:
        parse_toc_block("# T\n\n<!-- toc -->\n- [A](#a)\n\n## Body\n", "b.md")
    except SystemExit:
        pass
    else:
        assert False, "unterminated TOC block should refuse to build"

    link = {"name": "Blog", "url": "https://b.me"}
    # No homelink: a bar of links only, nothing pointing at the site root.
    _, bar = build_masthead({"header": {"show": "all", "link": [link]}})
    assert "Blog" in bar
    assert "/index.html" not in bar

    # Homelink: pinned left of the links, pointing at the site root.
    _, bar = build_masthead({"header": {"show": "all", "link": [link],
                                        "homelink": {"name": "My Notes"}}})
    assert bar.index('href="/index.html"') < bar.index("Blog")

    # A homelink alone is still a bar; nothing configured at all is not.
    _, bar = build_masthead({"header": {"show": "all", "homelink": {"name": "N"}}})
    assert "<header" in bar
    assert build_masthead({"header": {"show": "all"}}) == ("all", "")

    # A homelink without a name is a config error, not a nameless link.
    try:
        build_masthead({"header": {"show": "all", "homelink": {}}})
    except SystemExit:
        pass
    else:
        assert False, "[header.homelink] without a name should refuse to build"
    print("selfcheck ok")


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        build()
