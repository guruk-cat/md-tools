# Merge

## 1. Overview

`merge.py` combines several markdown files into one new file. It concatenates the file bodies in the order you give, then rewrites their headings and footnotes so the result reads as a single document. The tool never edits the inputs; it writes one new file.

It does four things to the merged content:

1. It strips manual heading numbers, so leftover numbering from the source files does not clash.
2. It shifts heading levels, both per file and across the whole merge.
3. It renumbers footnotes into one continuous sequence and gathers every definition at the foot.
4. It optionally prepends fresh nested heading numbers (`1.`, `1.1.`).

## 2. Usage

The basic form lists the files to merge.

```sh
python .tools/merge.py a.md b.md c.md
```

The merged file is written to `merged.md` in the current directory. Use `-o` to choose a different base name. If the target name already exists, a numeric suffix is added (`merged-2.md`, `merged-3.md`, and so on), so an existing file is never overwritten.

```sh
python .tools/merge.py a.md b.md -o combined
```

A shell glob works when every file should take the defaults.

```sh
python .tools/merge.py docs/*.md
```

## 3. Heading levels

Two mechanisms shift heading levels. They add together.

### 3.1. Per-file shift

Suffix a path with `:±N` to shift that file's headings. A positive number promotes the headings toward H1; a negative number demotes them toward H6.

```sh
python .tools/merge.py a.md b.md:+1 c.md:-2
```

Here `b.md` is promoted one level and `c.md` is demoted two. `a.md` is unchanged. Levels are clamped to the H1 to H6 range, so a shift can never push a heading out of bounds.

### 3.2. Merge-wide shift

`--promote N` and `--demote N` shift every heading in the merge. This shift is applied on top of each file's own per-file suffix.

```sh
python .tools/merge.py a.md b.md:+1 c.md --demote 1
```

Every heading drops one level, and `b.md` then climbs back one from its suffix, so its headings end up unchanged while the others drop.

### 3.3. Manual numbers are always stripped

A leading manual number on a heading is removed regardless of any other option, because numbers from different source files will not line up once merged. A number is only recognised when it is followed by a separator and whitespace, so `## 2. Apples` becomes `## Apples` but `## 2 Apples` is left intact. The recognised forms are a dotted number (`1.`, `1.1.`, `2.3.1`) or a number with a single `:` or `)` terminator (`2:`, `1)`).

## 4. Heading numbering

By default the tool does not number headings. Pass `--number` to prepend nested numbers across the merged document.

```sh
python .tools/merge.py a.md b.md --number
```

Numbering anchors at H2 by default, so the first H2 becomes `1.`, its first H3 becomes `1.1.`, and any H1 is left unnumbered. Pass `--number-h1` to include H1 in the hierarchy instead; this also turns on numbering, so `--number` is not needed alongside it.

```sh
python .tools/merge.py a.md b.md --number-h1
```

When a level is skipped, the gap is filled with `1`. A jump straight from H2 to H4 produces `1.` and then `1.1.1.`.

## 5. Footnotes

Each source file numbers its own footnotes independently, so `[^1]` in one file and `[^1]` in another are different notes. After merging, every reference is reassigned a unique number in order of first appearance across the whole document, and all definitions are collected at the foot.

Two edge cases:

| Case | Result |
| --- | --- |
| A reference whose definition is absent from its source file | The reference is kept and its bracket text becomes the definition (`[^Oh, yes!]` becomes `[^1]` plus `[^1]: Oh, yes!`). |
| A definition that is never referenced | It is kept at the foot under a `[^no-ref-N]` label. |

Every surviving reference is rewritten to a freshly minted number in the same pass, so no original label lingers in the body to alias a reassigned one. That is what keeps a literal label from colliding with a reassigned number, whether the reference had a definition or not. 

## 6. Not merged

Front matter is not read. If a source file begins with a YAML front-matter block (delimited by `---`), that block is dropped before merging, and only the body is used. Fenced code blocks are tracked throughout, so a `#` inside a code fence is never mistaken for a heading.

## 7. Notes

The footnote logic lives in `notes.py` and the heading numbering in `headings.py`. Both are standalone tools (see the README), and `merge.py` imports them.

The tool ships with a self-check covering the footnote round-trip, number stripping, heading shifts, and nested numbering. Run it against the script directly in the tools checkout:

```sh
python src/merge.py --selfcheck
```
