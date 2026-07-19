#!/usr/bin/env python3
"""
Convert a tree of markdown files into a static HTML site.

Runs from the repo root as `.tools/build.py`.
Reads `.md` files recursively, renders them, rewrites internal `.md` links to `.html`.
Wraps each in `template.html`, and writes the mirror tree under `.public/`.
Source files are never modified.
"""

import posixpath
import re
import shutil
from html import escape
from pathlib import Path
from typing import NamedTuple

import markdown

from shared import TOC_CLOSE, TOC_OPEN, load_config

ROOT = Path.cwd()                 # run from your repo root; the code may live elsewhere (on PATH)
TOOLS = ROOT / ".tools"           # per-repo content files live here, not next to the code
OUTPUT = ROOT / ".public"
TEMPLATE = TOOLS / "template.html"
STYLE = TOOLS / "style.css"
ROBOTS = TOOLS / "robots.txt"

# Placeholders fill_template() substitutes; a template missing any is stale or wrong.
TEMPLATE_PLACEHOLDERS = ("{{title}}", "{{header}}", "{{nav}}", "{{content}}", "{{footer}}")

MARKDOWN_EXTENSIONS = ["meta", "toc", "footnotes", "tables", "fenced_code"]

SIDEBAR_MODES = ("none", "browse", "readme", "toc")
HEADER_MODES = ("disabled", "home", "not home", "all")

# Matching the href attribute of rendered HTML (rather than raw markdown) skips
# code blocks and covers reference-style links automatically.
MD_HREF_RE = re.compile(r"""(href=["'])([^"']*\.md)((?:#[^"']*)?["'])""")
ABSOLUTE_URL_RE = re.compile(r"[a-z][a-z0-9+.-]*://")

# Markers that turn a line into a block (list, heading, quote) when they lead one.
LEADING_BLOCK_RE = re.compile(r"^\s*([#>]+|\d+[.)]|[-+*])(?=\s|$)")

H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")

# The item shape toc.py writes; 'toc' sidebar mode reads the block back out.
TOC_ITEM_RE = re.compile(r"^(\s*)- \[(.+)\]\(#(.+)\)\s*$")
TOC_HEADING_RE = re.compile(r"^##\s+(.*?)\s*#*\s*$")
TOC_INDENT_WIDTH = 4  # toc.py indents one nesting level per 4 spaces


class RenderedPage(NamedTuple):
    """A page rendered in memory, not yet written to disk."""
    out_path: Path      # absolute, under OUTPUT
    title: str
    body_html: str
    toc_nav_html: str   # 'toc' sidebar mode only; "" otherwise
    header_html: str    # "" where this page does not carry the masthead


class NavEntry(NamedTuple):
    """One page as the sidebar builders see it."""
    out_path: Path      # relative to OUTPUT
    title: str


class Asset(NamedTuple):
    """A non-markdown file to copy through unchanged."""
    source: Path
    out_path: Path      # absolute, under OUTPUT


def make_markdown():
    return markdown.Markdown(extensions=MARKDOWN_EXTENSIONS)


def render_markdown(renderer, text):
    # reset() is mandatory:
    # footnotes/meta state accumulates on the instance and would leak between files otherwise.
    renderer.reset()
    return renderer.convert(text)


def rewrite_md_links(body_html, page_out_path):
    # Point internal `.md` links at the root-absolute `.html` URLs the build produces.
    # page_out_path is relative to the output root, so sibling links resolve.
    page_dir = page_out_path.parent.as_posix()

    def to_html_url(match):
        opening_quote, url, closing_quote = match.groups()
        if ABSOLUTE_URL_RE.match(url) or url.startswith("//"):
            return match.group(0)  # leave external links alone
        without_suffix = url[:-len(".md")]
        target = posixpath.normpath(posixpath.join(page_dir, without_suffix))
        href = "/index.html" if target == "README" else f"/{target}.html"
        return opening_quote + href + closing_quote

    return MD_HREF_RE.sub(to_html_url, body_html)


def pick_title(meta, body_html, filename_stem, home_override=None):
    # home_override: the config title for the homepage (README), which wins over everything.
    if home_override:
        return home_override
    if meta.get("title"):
        return meta["title"][0]
    first_h1 = H1_RE.search(body_html)
    if first_h1:
        return HTML_TAG_RE.sub("", first_h1.group(1)).strip()
    return filename_stem


def escape_block_marker(match):
    # A numeric marker needs the backslash on its punctuation ("1\."), the rest
    # on the character itself ("\-").
    marker = match.group(1)
    if marker[0].isdigit():
        escaped = marker[:-1] + "\\" + marker[-1]
    else:
        escaped = "\\" + marker
    return match.group(0).replace(marker, escaped)


def render_inline_markdown(text):
    # markdown.markdown parses its argument as a block, so a heading numbered
    # "1." arrives as an <ol>, not text. Escaping a leading block marker keeps it
    # literal; inline markup (links, `code`) still renders.
    escaped = LEADING_BLOCK_RE.sub(escape_block_marker, str(text))
    return markdown.markdown(escaped).removeprefix("<p>").removesuffix("</p>")


def page_link_html(out_path, title):
    return f'<a href="/{out_path.as_posix()}">{escape(title)}</a>'


def build_footer(config):
    # Each [[footer.line]] carries a `text` rendered as markdown.
    footer_config = config.get("footer")
    if footer_config is None:
        return ""
    line_tags = []
    for line in footer_config.get("line", []):
        text = line.get("text")
        if not text:
            raise SystemExit("[[footer.line]] entries each need a 'text'")
        line_tags.append(f"<div>{render_inline_markdown(text)}</div>")
    if not line_tags:
        return ""
    return "<footer>" + "".join(line_tags) + "</footer>"


def build_masthead(config):
    # Returns (mode, html). The mode decides which pages carry the bar; build()
    # applies it per page.
    header_config = config.get("header")
    if not header_config:
        return ("disabled", "")

    mode = header_config.get("show", "disabled")
    if mode not in HEADER_MODES:
        raise SystemExit(f"[header] show must be one of {', '.join(HEADER_MODES)}; got {mode!r}")
    if mode == "disabled":
        return (mode, "")

    link_tags = []
    for link in header_config.get("link", []):
        if not link.get("name") or not link.get("url"):
            raise SystemExit("[[header.link]] entries each need both 'name' and 'url'")
        link_tags.append(f'<a href="{escape(str(link["url"]))}">{escape(str(link["name"]))}</a>')

    homelink = header_config.get("homelink")
    if homelink is not None and not homelink.get("name"):
        raise SystemExit("[header.homelink] needs a 'name'")
    if not link_tags and homelink is None:
        return (mode, "")

    links_html = f'<nav class="links">{"".join(link_tags)}</nav>' if link_tags else ""
    if homelink is None:
        return (mode, f'<header class="masthead">{links_html}</header>')
    home_html = f'<a href="/index.html">{escape(str(homelink["name"]))}</a>'
    return (mode, f'<header class="masthead">{home_html}{links_html}</header>')


def page_carries_masthead(mode, is_homepage):
    return (
        mode == "all"
        or (mode == "home" and is_homepage)
        or (mode == "not home" and not is_homepage)
    )


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


def home_link_html(title):
    return f'<ul class="nav-home"><li><a href="/index.html">{escape(title)}</a></li></ul>'


class TocItem(NamedTuple):
    depth: int          # 0 for the block's topmost level
    label: str
    anchor: str


def parse_toc_block(text, source_path):
    # Pull toc.py's block out of the markdown source: 'toc' mode shows it in the
    # sidebar instead of the body, so it must not render twice.
    # Returns (text_without_block, block_title, [TocItem]); no block -> text unchanged.
    lines = text.split("\n")
    open_idx = next((i for i, line in enumerate(lines) if line.strip() == TOC_OPEN), None)
    if open_idx is None:
        return text, "", []
    close_idx = next(
        (i for i in range(open_idx + 1, len(lines)) if lines[i].strip() == TOC_CLOSE), None
    )
    if close_idx is None:
        raise SystemExit(
            f"{source_path}: unterminated TOC block: found '{TOC_OPEN}' with no matching "
            f"'{TOC_CLOSE}'. Fix the markers; refusing to build."
        )

    block_title, items = "", []
    for line in lines[open_idx + 1:close_idx]:
        item = TOC_ITEM_RE.match(line)
        if item:
            indent, label, anchor = item.groups()
            items.append(TocItem(len(indent) // TOC_INDENT_WIDTH, label, anchor))
            continue
        heading = TOC_HEADING_RE.match(line)
        if heading and not block_title:
            block_title = heading.group(1)

    remaining = lines[:open_idx] + lines[close_idx + 1:]
    return "\n".join(remaining), block_title, items


class TocNode(NamedTuple):
    label: str
    anchor: str
    children: list


def nest_toc_items(items):
    # Flat TocItems -> nested TocNodes. A depth that skips a rung (H2 straight to
    # H4) just nests one level; the TOC is for navigating, not for reproducing
    # the heading arithmetic.
    roots = []
    open_nodes = [(-1, roots)]  # (depth, sibling list to append into)
    for item in items:
        node = TocNode(item.label, item.anchor, [])
        while open_nodes[-1][0] >= item.depth:
            open_nodes.pop()
        open_nodes[-1][1].append(node)
        open_nodes.append((item.depth, node.children))
    return roots


def render_toc_nodes(nodes):
    # Flat nested list, every level shown; CSS bullets and indent do the styling.
    lines = ["<ul>"]
    for node in nodes:
        link = f'<a href="#{escape(node.anchor)}">{render_inline_markdown(node.label)}</a>'
        lines.append(f"<li>{link}")
        if node.children:
            lines.extend(render_toc_nodes(node.children))
        lines.append("</li>")
    lines.append("</ul>")
    return lines


def build_toc_nav(block_title, items):
    # "" when the page carries no TOC: that page simply gets no sidebar.
    if not items:
        return ""
    heading = [f'<div class="toc-title">{escape(block_title)}</div>'] if block_title else []
    body = render_toc_nodes(nest_toc_items(items))
    return "\n".join(['<nav class="sidebar toc">', *heading, *body, "</nav>"])


def new_tree_node():
    return {"entries": [], "subdirs": {}}


def build_nav_tree(entries):
    # Group NavEntries into nested {"entries": [...], "subdirs": {name: node}}.
    tree = new_tree_node()
    for entry in entries:
        node = tree
        for part in entry.out_path.parent.parts:  # () at root, ("notes",), ("notes","sub"), ...
            node = node["subdirs"].setdefault(part, new_tree_node())
        node["entries"].append(entry)
    return tree


def render_nav_tree(node):
    # Collapsible tree of a node's pages and subfolders.
    lines = []
    entries = sorted(node["entries"], key=lambda entry: entry.title.lower())
    if entries:
        lines.append("<ul>")
        for entry in entries:
            lines.append(f"<li>{page_link_html(entry.out_path, entry.title)}</li>")
        lines.append("</ul>")
    for name in sorted(node["subdirs"]):
        lines.append("<details>")
        lines.append(f"<summary>{escape(name)}</summary>")
        lines.extend(render_nav_tree(node["subdirs"][name]))
        lines.append("</details>")
    return lines


def wrap_sidebar(lines):
    return "\n".join(['<nav class="sidebar">', *lines, "</nav>", NAV_SCRIPT])


def build_browse_nav(entries):
    # One shared sidebar: the whole site as a collapsible tree.
    return wrap_sidebar(render_nav_tree(build_nav_tree(entries)))


HOMEPAGE_OUT_PATH = Path("index.html")


def build_readme_navs(entries):
    # 'readme' mode. Returns (global_nav, {section_name: scoped_nav}).
    # Global nav (shown on root-level pages): root page links, then a link to each
    # top-level directory's README (directories without one are omitted).
    # Scoped nav (shown on a page inside a top-level directory): that directory's
    # own subtree browsed in full, with a Home link back to the site root on top.
    root_entries, sections = [], {}
    for entry in entries:
        if len(entry.out_path.parts) == 1:
            root_entries.append(entry)
        else:
            sections.setdefault(entry.out_path.parts[0], []).append(entry)

    # The back-home link reuses the homepage's own title (which already carries the
    # `home` config override), so it matches the pinned entry in the global nav.
    home_title = next(
        (entry.title for entry in root_entries if entry.out_path == HOMEPAGE_OUT_PATH), "Home"
    )

    global_lines, section_links, scoped_navs = [], [], {}
    if root_entries:
        # Homepage pinned first; the rest of the root pages follow alphabetically.
        homepage = [e for e in root_entries if e.out_path == HOMEPAGE_OUT_PATH]
        others = sorted(
            (e for e in root_entries if e.out_path != HOMEPAGE_OUT_PATH),
            key=lambda entry: entry.title.lower(),
        )
        items = "".join(
            f"<li>{page_link_html(entry.out_path, entry.title)}</li>"
            for entry in homepage + others
        )
        global_lines.append(f"<ul>{items}</ul>")

    for name in sorted(sections):
        # Every page in this section shares `name` as parts[0], so descend once.
        section_node = build_nav_tree(sections[name])["subdirs"][name]
        readme_out_path = Path(name) / "README.html"
        readme = next(
            (e for e in section_node["entries"] if e.out_path == readme_out_path), None
        )
        if readme:
            # The README heads the section; its siblings nest one level beneath it.
            readme_link = page_link_html(readme.out_path, readme.title)
            siblings = {
                "entries": [e for e in section_node["entries"] if e != readme],
                "subdirs": section_node["subdirs"],
            }
            section_lines = [f"<ul><li>{readme_link}", *render_nav_tree(siblings), "</li></ul>"]
            section_links.append(f"<li>{readme_link}</li>")
        else:
            section_lines = render_nav_tree(section_node)
        scoped_navs[name] = wrap_sidebar([home_link_html(home_title), *section_lines])

    if section_links:
        global_lines.append("<ul>" + "".join(section_links) + "</ul>")
    return wrap_sidebar(global_lines), scoped_navs


def read_sidebar_mode(config):
    mode = config.get("sidebar", {}).get("mode", "none")
    if mode not in SIDEBAR_MODES:
        raise SystemExit(f"[sidebar] mode must be one of {', '.join(SIDEBAR_MODES)}; got {mode!r}")
    return mode


def read_template():
    missing = [path for path in (TEMPLATE, STYLE, ROBOTS) if not path.exists()]
    if missing:
        raise SystemExit(
            f"missing {', '.join(str(path) for path in missing)}. "
            f"Run 'md-tools setup' in this repo first."
        )
    template = TEMPLATE.read_text(encoding="utf-8")
    absent = [name for name in TEMPLATE_PLACEHOLDERS if name not in template]
    if absent:
        raise SystemExit(
            f"{TEMPLATE} is missing placeholder(s) {', '.join(absent)}; it may be from an "
            f"older version. Run 'md-tools setup --override template.html'. Refusing to build."
        )
    return template


def iter_source_files():
    # Every file in the repo except those under a dot-directory (.tools, .public, .git, ...).
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part.startswith(".") for part in relative.parts) or path.is_dir():
            continue
        yield path, relative


def fill_template(template, page, nav_html, footer_html):
    return (
        template.replace("{{title}}", escape(page.title))
        .replace("{{header}}", page.header_html)
        .replace("{{nav}}", nav_html)
        .replace("{{content}}", page.body_html)
        .replace("{{footer}}", footer_html)
    )


def build():
    config = load_config()
    sidebar_mode = read_sidebar_mode(config)
    home_title_override = config.get("site-layout", {}).get("home")
    footer_html = build_footer(config)
    header_mode, masthead_html = build_masthead(config)

    # Everything that can fail runs before OUTPUT is touched, so a refused build
    # leaves the previous one standing.
    template = read_template()
    renderer = make_markdown()

    pages, assets = [], []
    for source_path, relative_path in iter_source_files():
        if source_path.suffix != ".md":
            assets.append(Asset(source_path, OUTPUT / relative_path))
            continue

        is_homepage = relative_path == Path("README.md")
        out_path = OUTPUT / (
            HOMEPAGE_OUT_PATH if is_homepage else relative_path.with_suffix(".html")
        )

        text = source_path.read_text(encoding="utf-8")
        toc_nav_html = ""
        if sidebar_mode == "toc":
            text, block_title, toc_items = parse_toc_block(text, relative_path)
            toc_nav_html = build_toc_nav(block_title, toc_items)

        body_html = rewrite_md_links(
            render_markdown(renderer, text), out_path.relative_to(OUTPUT)
        )
        pages.append(RenderedPage(
            out_path=out_path,
            title=pick_title(
                renderer.Meta, body_html, source_path.stem,
                home_title_override if is_homepage else None,
            ),
            body_html=body_html,
            toc_nav_html=toc_nav_html,
            header_html=(
                masthead_html
                if masthead_html and page_carries_masthead(header_mode, is_homepage)
                else ""
            ),
        ))

    nav_entries = [NavEntry(page.out_path.relative_to(OUTPUT), page.title) for page in pages]
    global_nav, scoped_navs = "", {}
    if sidebar_mode == "browse":
        global_nav = build_browse_nav(nav_entries)
    elif sidebar_mode == "readme":
        global_nav, scoped_navs = build_readme_navs(nav_entries)

    # Past every check that can refuse: safe to replace the previous build.
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    for asset in assets:
        asset.out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset.source, asset.out_path)

    for page in pages:
        # 'toc' mode is per-page ("" where a page has no TOC). In 'readme' mode a
        # page inside a top-level directory gets that section's scoped nav; anything
        # else (root pages, and every page in 'browse'/'none') gets the global one.
        if sidebar_mode == "toc":
            nav_html = page.toc_nav_html
        else:
            section_name = page.out_path.relative_to(OUTPUT).parts[0]
            nav_html = scoped_navs.get(section_name, global_nav)
        page.out_path.parent.mkdir(parents=True, exist_ok=True)
        page.out_path.write_text(
            fill_template(template, page, nav_html, footer_html), encoding="utf-8"
        )

    shutil.copy2(STYLE, OUTPUT / "style.css")
    shutil.copy2(ROBOTS, OUTPUT / "robots.txt")
    print(f"built -> {OUTPUT}" + (f" (sidebar: {sidebar_mode})" if sidebar_mode != "none" else ""))


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
    assert items == [TocItem(0, "1. Intro", "1-intro"),
                     TocItem(1, "1.1. The `code` bit", "11-the-code-bit"),
                     TocItem(0, "2. Flat", "2-flat")]

    nav = build_toc_nav(title, items)
    assert "<details" not in nav                # flat list, no folding
    assert "<code>code</code>" in nav           # inline markdown in a heading renders
    assert nav.count("<ul>") == 2               # top list plus the one nested child list

    # A page with no TOC gets no sidebar at all, and its body is untouched.
    plain = "# Just a page\n\n## A\n"
    assert parse_toc_block(plain, "p.md") == (plain, "", [])
    assert build_toc_nav("", []) == ""

    # Unterminated block must refuse rather than swallow the page.
    try:
        parse_toc_block("# T\n\n<!-- toc -->\n- [A](#a)\n\n## Body\n", "b.md")
    except SystemExit:
        pass
    else:
        assert False, "unterminated TOC block should refuse to build"

    # Links are rewritten root-absolute, relative to the linking page's folder.
    body = rewrite_md_links(
        '<a href="sub/other.md">x</a> <a href="../README.md#top">y</a> '
        '<a href="https://ex.com/a.md">z</a>',
        Path("notes/page.html"),
    )
    assert 'href="/notes/sub/other.html"' in body
    assert 'href="/index.html#top"' in body
    assert 'href="https://ex.com/a.md"' in body  # external link untouched

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

    # 'home' shows the masthead on the homepage only; 'not home' is its inverse.
    assert page_carries_masthead("home", True) and not page_carries_masthead("home", False)
    assert page_carries_masthead("not home", False) and not page_carries_masthead("not home", True)
    print("selfcheck ok")


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        build()
