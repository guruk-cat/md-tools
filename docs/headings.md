# Heading Numbering

<!-- toc -->
## Table of Contents
- [1. Overview](#1-overview)
- [2. Where the numbering anchors](#2-where-the-numbering-anchors)
- [3. Existing numbers are stripped first](#3-existing-numbers-are-stripped-first)
- [4. What is left alone](#4-what-is-left-alone)
- [5. Excluding headings](#5-excluding-headings)
<!-- /toc -->

## 1. Overview

`headings.py` prepends nested numbers (`1.`, `1.1.`) to a file's headings, rewriting it in place. `merge.py` imports the same logic for its `--number` option, so everything here applies to both.

```sh
python .tools/headings.py path/to/file.md
```

## 2. Where the numbering anchors

Numbering anchors at H2 by default. The first H2 becomes `1.`, its first H3 becomes `1.1.`, and any H1 is left alone, which suits a document whose H1 is its title.

```sh
python .tools/headings.py file.md --number-h1
```

`--number-h1` includes H1 in the hierarchy instead, so the first H1 becomes `1.` and its first H2 becomes `1.1.`. In `merge.py` this flag also turns numbering on, so `--number` is not needed alongside it.

When a level is skipped, the gap is filled with `1`. A jump straight from H2 to H4 produces `1.` and then `1.1.1.`.

## 3. Existing numbers are stripped first

A leading manual number is removed before fresh ones are applied, so a re-run reproduces the same output instead of doubling. In `merge.py` this happens regardless of any other option, because numbers from different source files will not line up once merged.

A number is only recognised when it is followed by a separator and then whitespace. The recognised forms are a dotted number (`1.`, `1.1.`, `2.3.1`) or a number with a single `:` or `)` terminator (`2:`, `1)`).

| Heading | Result |
| --- | --- |
| `## 2. Apples` | `## Apples`, then renumbered |
| `## 2 Apples` | left intact (no separator) |
| `## 1stPlace` | left intact (no whitespace after the digits) |

## 4. What is left alone

Fenced code blocks are tracked throughout, so a `#` inside a fence is never mistaken for a heading. A generated TOC block (between the `<!-- toc -->` markers) is skipped in full, so its own `## Table of Contents` heading stays unnumbered and consumes no counter. An opening marker with no closing one aborts the run rather than producing a half-numbered file.

A line is treated as a heading only when its hashes are followed by whitespace and it carries no leading indent. This is deliberately stricter than the site renderer, which also accepts `#x`, so that a stray `#hashtag` at the start of a line is never rewritten into a heading.

## 5. Excluding headings

Individual headings can be left out by their text, matched after any manual number is stripped. An excluded heading keeps its text as-is and consumes no counter, so its siblings number as if it were not there.

```sh
python .tools/headings.py file.md --exclude "Preface" --exclude "Appendix"
```

The flag is repeatable. The same list can live in `config.toml` under `[exclude-headings]` (see the [configuration docs](config.md)), in which case it applies to every run without the flag. Passing `--exclude` overrides the config list rather than adding to it.
