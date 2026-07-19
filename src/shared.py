#!/usr/bin/env python3
"""
Definitions the tools must agree on: the config file, the TOC markers, and what
counts as a fence or a heading.
"""

import re
import tomllib
from pathlib import Path

CONFIG = Path.cwd() / ".tools" / "config.toml"

TOC_OPEN = "<!-- toc -->"
TOC_CLOSE = "<!-- /toc -->"

FENCE_RE = re.compile(r"^\s*(```+|~~~+)")

# ATX heading: 1-6 hashes, then whitespace, then text, optional trailing hashes.
# Deliberately stricter than Python-Markdown, which also accepts `#x`: widening
# this would let a stray `#hashtag` at the start of a line be rewritten as a heading.
ATX_RE = re.compile(r"^(#{1,6})(?=[ \t])(.*)$")


def load_config():
    if not CONFIG.exists():
        return {}
    with CONFIG.open("rb") as f:
        return tomllib.load(f)


def scan_fences(lines):
    # Yield (line, is_fenced) per line. A fence marker itself reports True, so
    # callers pass it through untouched without parsing it as content.
    fence = None
    for line in lines:
        m = FENCE_RE.match(line)
        if m:
            tok = m.group(1)[0]
            fence = tok if fence is None else (None if tok == fence else fence)
            yield line, True
        else:
            yield line, fence is not None


def parse_heading(line):
    # (level, text) for an ATX heading, else None. Text keeps any manual number;
    # headings.py strips that itself. Fence tracking is the caller's job.
    m = ATX_RE.match(line)
    if not m:
        return None
    text = re.sub(r"#+$", "", m.group(2).strip()).strip()
    return len(m.group(1)), text


def selfcheck():
    assert parse_heading("## A") == (2, "A")
    assert parse_heading("## A ##") == (2, "A")
    assert parse_heading("## 2. A") == (2, "2. A")   # number kept, not stripped
    assert parse_heading("#x") is None               # no space: not a heading
    assert parse_heading("   ## A") is None          # indented: renders as prose
    assert parse_heading("#") is None
    assert parse_heading("####### A") is None        # 7 hashes

    lines = ["a", "```", "# not a heading", "```", "# yes"]
    assert [f for _, f in scan_fences(lines)] == [False, True, True, True, False]

    # Mismatched fence tokens do not close each other.
    assert [f for _, f in scan_fences(["```", "~~~", "x"])] == [True, True, True]
    print("selfcheck ok")


if __name__ == "__main__":
    selfcheck()
