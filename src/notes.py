#!/usr/bin/env python3
"""
Renumber a file's footnotes into one continuous sequence and gather all
definitions at the foot, in place.

    python .tools/notes.py FILE

"""

import argparse
import re
from pathlib import Path

REF_RE = re.compile(r"\[\^([^\]]+)\](?!\()")
DEF_RE = re.compile(r"^\[\^([^\]]+)\]:[ \t]?(.*)$")
CONT_RE = re.compile(r"^[ \t]+\S")


def trim_blank(text):
    lines = text.split("\n")
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()
    return "\n".join(lines)


def format_def(label, text_lines):
    out = [f"[^{label}]: {text_lines[0].rstrip()}"]
    for cont in text_lines[1:]:
        out.append("    " + cont)
    return "\n".join(out)


def renumber_footnotes(segments):
    # File-aware: each segment resolves references against its own definitions,
    # so identical labels in different segments are distinct notes. 
    # Every surviving reference is rewritten to a freshly minted number in the same
    # pass, so no original label lingers in the body to alias a reassigned one.
    # A reference with no definition in its segment keeps its bracket text as the
    # synthesized definition; a definition never referenced is kept under a
    # separate [^no-ref-N] label.
    counter = noref_counter = 0
    definitions = []
    out_segments = []
    for seg in segments:
        lines = seg.split("\n")
        defs, order, def_idx = {}, [], set()
        i, n = 0, len(lines)
        while i < n:
            m = DEF_RE.match(lines[i])
            if not m:
                i += 1
                continue
            label, text_lines = m.group(1), [m.group(2)]
            def_idx.add(i)
            j = i + 1
            while j < n and CONT_RE.match(lines[j]):
                text_lines.append(lines[j].lstrip(" \t"))
                def_idx.add(j)
                j += 1
            if label not in defs:
                order.append(label)
            defs[label] = text_lines
            i = j

        prose = "\n".join(lines[k] for k in range(n) if k not in def_idx)
        assigned = {}

        def repl(mo):
            nonlocal counter
            label = mo.group(1)
            if label not in assigned:
                counter += 1
                assigned[label] = counter
                block = defs[label] if label in defs else [label]
                definitions.append(format_def(counter, block))
            return f"[^{assigned[label]}]"

        prose = REF_RE.sub(repl, prose)

        for label in order:
            if label not in assigned:
                noref_counter += 1
                definitions.append(format_def(f"no-ref-{noref_counter}", defs[label]))

        prose = trim_blank(prose)
        if prose.strip():
            out_segments.append(prose)
    return out_segments, definitions


def arrange(text):
    # Single-file arrangement: the whole document is one segment
    # A doc with no footnotes is returned untouched
    has_refs = REF_RE.search(text) is not None
    has_defs = any(DEF_RE.match(line) for line in text.split("\n"))
    if not has_refs and not has_defs:
        return text

    segments, definitions = renumber_footnotes([text])
    body = "\n\n".join(segments)
    if definitions:
        body = body.rstrip() + "\n\n" + "\n".join(definitions) + "\n"
    if not body.endswith("\n"):
        body += "\n"
    return body


def run(argv):
    p = argparse.ArgumentParser(description="Arrange a file's footnotes in place.")
    p.add_argument("file")
    args = p.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        raise SystemExit(f"not a file: {args.file}")

    original = path.read_text(encoding="utf-8")
    result = arrange(original)
    if result == original:
        print(f"notes: no change ({path})")
        return
    path.write_text(result, encoding="utf-8")
    print(f"notes -> {path}")


def selfcheck():
    # Round-trip: two blobs each using [^1]/[^2] must merge to four distinct
    # footnotes in reference order, all defined at the foot.
    a = "Text A[^1] more[^2].\n\n[^1]: def a1\n[^2]: def a2"
    b = "Text B[^1] more[^2].\n\n[^1]: def b1\n[^2]: def b2"
    segs, defs = renumber_footnotes([a, b])
    joined = "\n\n".join(segs)
    assert "Text A[^1] more[^2]." in joined
    assert "Text B[^3] more[^4]." in joined
    assert defs == ["[^1]: def a1", "[^2]: def a2", "[^3]: def b1", "[^4]: def b2"]

    # Reference with no definition keeps its bracket text as the definition;
    # orphan definition is relabeled.
    segs, defs = renumber_footnotes(["see[^x] here\n\n[^y]: orphan"])
    assert segs == ["see[^1] here"]
    assert defs == ["[^1]: x", "[^no-ref-1]: orphan"]

    # Single-file arrange synthesizes a definition from an undefined reference.
    out = arrange("Look here[^Oh, yes!].\n")
    assert "Look here[^1]." in out
    assert "[^1]: Oh, yes!" in out

    # A footnote-free document is returned untouched.
    plain = "# Title\n\nJust prose.\n"
    assert arrange(plain) == plain

    print("selfcheck ok")


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        run(sys.argv[1:])
