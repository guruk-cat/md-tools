#!/usr/bin/env python3
"""
Prepend nested numbers to a file's headings, in place.

    python .tools/headings.py FILE [--number-h1]

Existing manual numbers are stripped before fresh ones are applied, so a re-run
reproduces the same output instead of doubling. Numbering anchors at H2 by
default (the first H2 becomes 1., its first H3 becomes 1.1., any H1 is left
alone); --number-h1 includes H1 in the hierarchy. 
"""

import argparse
import re
import tomllib
from pathlib import Path

FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
ATX_RE = re.compile(r"^ {0,3}(#{1,6})(?=[ \t]|$)(.*)$")
TOC_OPEN = "<!-- toc -->"
TOC_CLOSE = "<!-- /toc -->"
CONFIG = Path.cwd() / ".tools" / "config.toml"


def load_exclude():
    if not CONFIG.exists():
        return []
    with CONFIG.open("rb") as f:
        return tomllib.load(f).get("exclude-headings", {}).get("titles", [])


def clamp(n, lo, hi):
    return max(lo, min(hi, n))


def strip_number(text):
    # Remove a leading manual heading number and the whitespace after it.
    # Returns the text unchanged unless a number is immediately followed by
    # whitespace, so "1stPlace" is left alone but "1. Intro" becomes "Intro".
    if not text or not text[0].isdigit():
        return text
    i, n = 0, len(text)
    while i < n and text[i].isdigit():
        i += 1
    while i + 1 < n and text[i] == "." and text[i + 1].isdigit():
        i += 1
        while i < n and text[i].isdigit():
            i += 1
    if i < n and text[i] == ".":
        i += 1
    elif i < n and text[i] in ":)":
        i += 1
    if i < n and text[i] in " \t":
        while i < n and text[i] in " \t":
            i += 1
        return text[i:]
    return text


def parse_heading(line):
    # Returns (level, cleaned_text) for an ATX heading
    # Fence tracking is the caller's job
    m = ATX_RE.match(line)
    if not m:
        return None
    level = len(m.group(1))
    text = m.group(2).strip()
    text = re.sub(r"#+$", "", text).strip()
    return level, strip_number(text)


def advance_counters(counters, depth):
    if depth < len(counters):
        counters[depth] += 1
        del counters[depth + 1:]
    else:
        while len(counters) < depth:
            counters.append(1)
        counters.append(1)
    return ".".join(map(str, counters)) + "."


def number_headings(doc, renumber, number_h1, exclude=()):
    if not renumber:
        return doc
    base = 1 if number_h1 else 2
    exclude = set(exclude)
    out, fence, in_toc, counters = [], None, False, []
    for line in doc.split("\n"):
        fm = FENCE_RE.match(line)
        if fm:
            tok = fm.group(1)[0]
            fence = tok if fence is None else (None if tok == fence else fence)
            out.append(line)
            continue
        if fence:
            out.append(line)
            continue

        # leave a generated TOC block out of the numbering.
        if not in_toc and line.strip() == TOC_OPEN:
            in_toc = True
            out.append(line)
            continue
        if in_toc:
            if line.strip() == TOC_CLOSE:
                in_toc = False
            out.append(line)
            continue
        parsed = parse_heading(line)
        if parsed and parsed[0] >= base and parsed[1] not in exclude:
            level, text = parsed
            num = advance_counters(counters, level - base)
            out.append("#" * level + " " + num + " " + text)
        else:
            out.append(line)
    if in_toc:
        raise SystemExit(
            f"Unterminated TOC block: "
            f"found '{TOC_OPEN}' with no matching '{TOC_CLOSE}'"
            f"Refusing to write."
        )
    return "\n".join(out)


def run(argv):
    p = argparse.ArgumentParser(description="Number a file's headings in place.")
    p.add_argument("file")
    p.add_argument("--number-h1", dest="number_h1", action="store_true")
    p.add_argument("--exclude", action="append", default=None,
                   help="heading text to leave unnumbered; repeatable. "
                        "Overrides [exclude-headings] titles in config.")
    args = p.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        raise SystemExit(f"not a file: {args.file}")

    exclude = args.exclude if args.exclude is not None else load_exclude()
    original = path.read_text(encoding="utf-8")
    result = number_headings(
        original, renumber=True, number_h1=args.number_h1, exclude=exclude
    )
    if result == original:
        print(f"headings: no change ({path})")
        return
    path.write_text(result, encoding="utf-8")
    print(f"headings -> {path}")


def selfcheck():
    assert strip_number("1. Intro") == "Intro"
    assert strip_number("1.1. A") == "A"
    assert strip_number("2.3.1 B") == "B"
    assert strip_number("2: C") == "C"
    assert strip_number("1) D") == "D"
    assert strip_number("1stPlace") == "1stPlace"

    # Nested numbering: H2 then H4 fills the skipped level with 1
    doc = number_headings("## A\n\n#### B", renumber=True, number_h1=False)
    assert doc == "## 1. A\n\n#### 1.1.1. B"

    # numberH1 anchors the hierarchy at H1
    doc = number_headings("# A\n\n## B", renumber=True, number_h1=True)
    assert doc == "# 1. A\n\n## 1.1. B"

    # Idempotent: re-numbering an already-numbered doc reproduces it
    once = number_headings("## Intro\n\n### Detail", renumber=True, number_h1=False)
    assert number_headings(once, renumber=True, number_h1=False) == once

    # TOC block is skipped 
    # Its '## Table of Contents' stays unnumbered and does not consume a counter
    withtoc = "<!-- toc -->\n## Table of Contents\n- [A](#a)\n<!-- /toc -->\n\n## A"
    assert number_headings(withtoc, renumber=True, number_h1=False) == (
        "<!-- toc -->\n## Table of Contents\n- [A](#a)\n<!-- /toc -->\n\n## 1. A"
    )

    # Excluded heading is ignored: not numbered, consumes no counter
    doc = number_headings(
        "## A\n\n## Skip\n\n## B", renumber=True, number_h1=False,
        exclude=["Skip"],
    )
    assert doc == "## 1. A\n\n## Skip\n\n## 2. B"

    print("selfcheck ok")


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        run(sys.argv[1:])
