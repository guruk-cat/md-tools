#!/usr/bin/env python3
"""
Insert a table of contents into a markdown file, in place.

    python .tools/toc.py path/to/file.md

Inserts a TOC under the topmost H1 (or at the top, below YAML frontmatter, if
there is no H1), and rewrites it on re-run.

Anchors default to the website builder's scheme (Python-Markdown's `toc`
slugify) so the same links resolve on the built site; set slug_style="github"
in [toc-builder] for raw GitHub/editor viewing instead.
"""

import re
from pathlib import Path

from markdown.extensions.toc import slugify, unique

from shared import TOC_CLOSE, TOC_OPEN, load_config, parse_heading, scan_fences


def github_slug(text):
    s = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"\s+", "-", s)


def assign_ids(headings, slug_style):
    # Assign anchor ids over ALL headings in document order so collisions
    # dedupe exactly as the renderer sees them. Returns a parallel list of ids.
    ids = set()
    out = []
    for _level, text, _idx in headings:
        if slug_style == "github":
            base = github_slug(text)
            sid, i = base, 0
            while sid in ids or not sid:
                i += 1
                sid = f"{base}-{i}"
            ids.add(sid)
        else:
            sid = unique(slugify(text, "-"), ids)
        out.append(sid)
    return out


def parse_headings(lines):
    # ATX headings outside fenced code; skips a leading `---`...`---` frontmatter.
    # Returns ([(level, text, line_index)], content_start_index).
    start = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                start = j + 1
                break
    headings = []
    for idx, (line, fenced) in enumerate(scan_fences(lines[start:]), start):
        if fenced:
            continue
        parsed = parse_heading(line)
        if parsed:
            headings.append((*parsed, idx))
    return headings, start


def strip_existing(lines):
    # Remove a previously generated block (markers inclusive) plus the single
    # blank line we pad it with on each side, so re-runs converge. Returns
    # (remaining_lines, block_index) where block_index is where the block sat
    # (into remaining_lines), or None if absent.
    out, i, n, block_idx = [], 0, len(lines), None
    while i < n:
        if lines[i].strip() == TOC_OPEN:
            # Find the matching close BEFORE consuming anything.
            j = i + 1
            while j < n and lines[j].strip() != TOC_CLOSE:
                j += 1
            if j >= n:
                raise SystemExit(
                    f"unterminated TOC block: found '{TOC_OPEN}' with no matching "
                    f"'{TOC_CLOSE}'. Fix the markers; refusing to write."
                )
            if out and out[-1].strip() == "":
                out.pop()
            block_idx = len(out)
            i = j + 1  # skip past the close marker
            if i < n and lines[i].strip() == "":
                i += 1  # skip trailing pad
            continue
        out.append(lines[i])
        i += 1
    return out, block_idx


def render_block(listed, title):
    if not listed:
        return []
    min_level = min(level for level, _, _ in listed)
    out = [TOC_OPEN, f"## {title}"]
    for level, text, sid in listed:
        indent = "    " * (level - min_level)  # 4 spaces: Python-Markdown needs this to nest lists
        out.append(f"{indent}- [{text}](#{sid})")
    out.append(TOC_CLOSE)
    return out


def build_toc(text, cfg):
    toc_cfg = cfg.get("toc-builder", {})
    max_depth = toc_cfg.get("max_depth", 6)
    slug_style = toc_cfg.get("slug_style", "site")
    title = toc_cfg.get("toc_title", "Table of Contents")

    had_final_nl = text.endswith("\n")
    lines = text.split("\n")
    if had_final_nl:
        lines = lines[:-1]

    lines, block_idx = strip_existing(lines)
    headings, start = parse_headings(lines)

    result = lines
    if headings:
        sids = assign_ids(headings, slug_style)

        # Default placement is under the topmost H1 (excluded from its own TOC);
        # if a block already exists, rewrite it exactly where the user left it.
        insert_idx, title_idx = start, None
        for level, _text, idx in headings:
            if level == 1:
                title_idx, insert_idx = idx, idx + 1
                break
        if block_idx is not None:
            insert_idx = block_idx

        listed = [
            (level, htext, sid)
            for (level, htext, idx), sid in zip(headings, sids)
            if level <= max_depth and idx != title_idx
        ]
        block = render_block(listed, title)
        if block:
            lead = [] if insert_idx == 0 else [""]
            result = lines[:insert_idx] + lead + block + [""] + lines[insert_idx:]

    s = "\n".join(result)
    return s + "\n" if had_final_nl else s


def run(target):
    path = Path(target)
    if not path.is_file():
        raise SystemExit(f"not a file: {target}")
    text = path.read_text(encoding="utf-8")
    new = build_toc(text, load_config())
    if new == text:
        print(f"unchanged: {target}")
        return
    path.write_text(new, encoding="utf-8")
    print(f"toc -> {target}")


def selfcheck():
    doc = (
        "---\ntitle: t\n---\n\n"
        "# Title\n\n"
        "## 1. Introduction\ntext\n"
        "### 1.1. Some idea\n\n"
        "```\n# not a heading\n```\n\n"
        "## 2. Whoo\n"
    )
    out = build_toc(doc, {})
    assert "## Table of Contents" in out
    assert "- [1. Introduction](#1-introduction)" in out
    assert "  - [1.1. Some idea](#11-some-idea)" in out
    assert "- [2. Whoo](#2-whoo)" in out
    assert "[Title]" not in out                 # H1 excluded from its own TOC
    assert "not a heading]" not in out          # fenced `#` is not a heading
    assert out.index("Table of Contents") < out.index("## 1. Introduction")
    assert build_toc(out, {}) == out            # idempotent

    # max_depth caps which headings are listed (ids still assigned to all).
    shallow = build_toc(doc, {"toc-builder": {"max_depth": 2}})
    assert "Some idea" not in shallow.split(TOC_CLOSE)[0]

    # Duplicate headings: site uses `_1`, github uses `-1`.
    dup = "# T\n\n## Intro\n\n## Intro\n"
    site = build_toc(dup, {})
    gh = build_toc(dup, {"toc-builder": {"slug_style": "github"}})
    assert "(#intro)" in site and "(#intro_1)" in site
    assert "(#intro)" in gh and "(#intro-1)" in gh

    # No H1: insert at top, below frontmatter, no leading blank growth.
    nohdr = "## A\n\n## B\n"
    o1 = build_toc(nohdr, {})
    assert o1.startswith(TOC_OPEN)
    assert build_toc(o1, {}) == o1

    # custom title
    assert "## Contents" in build_toc(doc, {"toc-builder": {"toc_title": "Contents"}})

    # Existing block is rewritten in place, not yanked back under the H1.
    placed = (
        "# Title\n\nintro kept above\n\n"
        "<!-- toc -->\n## Table of Contents\n- stale\n<!-- /toc -->\n\n"
        "## A\n\n## B\n"
    )
    p = build_toc(placed, {})
    assert p.index("intro kept above") < p.index(TOC_OPEN)  # body stayed on top
    assert "- stale" not in p                               # block refreshed
    assert build_toc(p, {}) == p                            # idempotent in place

    # An open marker with a missing/typo'd close must NOT truncate the file:
    # fail closed instead of swallowing to EOF.
    broken = "# T\n\n<!-- toc -->\n## TOC\n<!--- toc --->\n\n## A\nkeep me\n"
    try:
        build_toc(broken, {})
    except SystemExit:
        pass
    else:
        assert False, "unterminated TOC block should refuse, not truncate"
    print("selfcheck ok")


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        selfcheck()
    elif len(sys.argv) == 2:
        run(sys.argv[1])
    else:
        raise SystemExit("usage: toc.py path/to/file.md")
