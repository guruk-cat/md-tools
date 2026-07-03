#!/usr/bin/env python3
"""
Merge several markdown files into one, rewriting headings and footnotes.

    python .tools/merge.py a.md b.md c.md -o combined

Concatenates the file bodies in order, applies per-file and merge-wide 
heading shifts, and renumbers footnotes into one continuous sequence with 
all definitions gathered at the foot. Optionally prepends nested heading 
numbers (--number).

Per-file heading shift is a `:±N` suffix on the path (`b.md:+1` promotes b's
headings one level toward H1, `c.md:-2` demotes two toward H6). Merge-wide
shift is --promote/--demote. The output is written to <name>.md in the current
directory, de-duplicated with a numeric suffix if the name is taken.
"""

import argparse
import re
from pathlib import Path

from headings import FENCE_RE, clamp, parse_heading, number_headings
from notes import renumber_footnotes, trim_blank

POS_RE = re.compile(r"^(.*):([+-]\d+)$")


def strip_frontmatter(text):
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                return "\n".join(lines[j + 1:])
    return text


def adjust_segment(body, adjust):
    out, fence = [], None
    for line in body.split("\n"):
        fm = FENCE_RE.match(line)
        if fm:
            tok = fm.group(1)[0]
            fence = tok if fence is None else (None if tok == fence else fence)
            out.append(line)
            continue
        if fence:
            out.append(line)
            continue
        parsed = parse_heading(line)
        if parsed:
            level, text = parsed
            level = clamp(level - adjust, 1, 6)
            out.append("#" * level + " " + text)
        else:
            out.append(line)
    return trim_blank("\n".join(out))


def merge(files, adjust_all, renumber, number_h1):
    segments = []
    for path, adj in files:
        body = strip_frontmatter(Path(path).read_text(encoding="utf-8"))
        seg = adjust_segment(body, adj + adjust_all)
        if seg.strip():
            segments.append(seg)

    prose_segments, definitions = renumber_footnotes(segments)
    doc = number_headings("\n\n".join(prose_segments), renumber, number_h1)

    body = doc
    if definitions:
        body = body.rstrip() + "\n\n" + "\n".join(definitions) + "\n"
    if not body.endswith("\n"):
        body += "\n"
    return body


def parse_positional(token):
    m = POS_RE.match(token)
    if m:
        return m.group(1), int(m.group(2))
    return token, 0


def write_output(name, body):
    out = Path.cwd() / f"{name}.md"
    i = 2
    while out.exists():
        out = Path.cwd() / f"{name}-{i}.md"
        i += 1
    out.write_text(body, encoding="utf-8")
    return out


def run(argv):
    p = argparse.ArgumentParser(description="Merge files into one.")
    p.add_argument("files", nargs="+", metavar="PATH[:±N]")
    p.add_argument("--promote", type=int, default=0, metavar="N")
    p.add_argument("--demote", type=int, default=0, metavar="N")
    p.add_argument("--number", action="store_true")
    p.add_argument("--number-h1", dest="number_h1", action="store_true")
    p.add_argument("-o", "--output", default="merged")
    args = p.parse_args(argv)

    files = [parse_positional(t) for t in args.files]
    for path, _ in files:
        if not Path(path).is_file():
            raise SystemExit(f"not a file: {path}")

    body = merge(
        files,
        adjust_all=args.promote - args.demote,
        renumber=args.number or args.number_h1,
        number_h1=args.number_h1,
    )
    out = write_output(args.output, body)
    print(f"merge -> {out}")


def selfcheck():
    # Round-trip through the shared footnote pass: two blobs each using
    # [^1]/[^2] must merge to four distinct footnotes in reference order.
    a = "Text A[^1] more[^2].\n\n[^1]: def a1\n[^2]: def a2"
    b = "Text B[^1] more[^2].\n\n[^1]: def b1\n[^2]: def b2"
    segs, defs = renumber_footnotes([adjust_segment(a, 0), adjust_segment(b, 0)])
    joined = "\n\n".join(segs)
    assert "Text A[^1] more[^2]." in joined
    assert "Text B[^3] more[^4]." in joined
    assert defs == [
        "[^1]: def a1", "[^2]: def a2", "[^3]: def b1", "[^4]: def b2",
    ]

    # Per-file shift, manual-number strip, and fenced `#` left alone.
    seg = adjust_segment("## 2. Apples\n\n```\n# not a heading\n```\n", 1)
    assert seg.startswith("# Apples")
    assert "# not a heading" in seg

    print("selfcheck ok")


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        run(sys.argv[1:])
