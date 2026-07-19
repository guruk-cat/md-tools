# Markdown Tools

<!-- toc -->
## Table of Contents
- [1. About](#1-about)
- [2. General Usage](#2-general-usage)
    - [2.1. Set up the tools in your repo](#21-set-up-the-tools-in-your-repo)
    - [2.2. Expected layout](#22-expected-layout)
    - [2.3. Optional: an `md-tools` command on your PATH](#23-optional-an-md-tools-command-on-your-path)
- [3. Website Pipeline](#3-website-pipeline)
    - [3.1. Build and serve](#31-build-and-serve)
    - [3.2. Deploy on a Remote Host (e.g., Netlify, Cloudflare, or your own server)](#32-deploy-on-a-remote-host-eg-netlify-cloudflare-or-your-own-server)
    - [3.3. How the build works](#33-how-the-build-works)
- [4. File Merger](#4-file-merger)
- [5. TOC Generator](#5-toc-generator)
- [6. Footnote Arranger](#6-footnote-arranger)
- [7. Heading Numberer](#7-heading-numberer)
- [8. Development](#8-development)
<!-- /toc -->

## 1. About

This repo hosts a set of custom-built tools for managing Markdown files. Its primary purposes are:

1. Build a static website from a bunch of Markdown files.
2. Arrange numbered headings and footnotes.
3. Merge files that have numbered headings and/or footnotes.
4. Generate and append a table of contents.

## 2. General Usage

This repo (`md-tools/`) is where the tools are developed; it is not intended as the place where you use them. The tools live in `src/` and get copied into your own repo as `.tools/`, so that a repo carries its own pipeline and can build itself on a remote host. Optionally, you can also expose an `md-tools` command on your PATH as a local convenience.

### 2.1. Set up the tools in your repo

Run, from this checkout:

```sh
python setup.py /path/to/your-repo
```

This copies the pipeline into the target's `.tools/`, refreshing the scripts and `template.html` on every run so a re-run pushes the latest version. The user-edited files (`config.toml` and `style.css`) are written only if absent, so edits are never clobbered; pass `--override` to refresh those to the shipped defaults. The setup script also ensures `.gitignore` excludes `.public/`.

### 2.2. Expected layout

After setup, your repo will look something like this:

```
repo-root/
    README.md           ← used as homepage content
    some-docs/
        *.md
        *.png           ← non-md assets okay
    some-other-docs/
        *.md
    .tools/             ← the pipeline: scripts + content
    .public/            ← build output, made by build.py
    .gitignore
```

The `.tools/` and `.public/` directories are dot-prefixed to keep them out of a markdown editor's file view. The `.gitignore` must exclude `.public/`, such that the output of the website pipeline is never committed. (The intended usage is that the script is run on the server-side, to generate its own `.public` output.) 

### 2.3. Optional: an `md-tools` command on your PATH

For local use, you can drive the pipeline with a single `md-tools` command. Symlink the dispatcher into a directory that is already on your PATH (`~/.local/bin` used in the example below):

```sh
ln -s "$(pwd)/src/md-tools" ~/.local/bin/md-tools
```

Then `md-tools setup`, `build`, `serve`, `toc`, `merge`, `notes`, and `headings` will work from any repo root. The command runs under the `python3` on your PATH, so that interpreter needs the dependencies installed (`pip install -r src/requirements.txt`). This is a convenience only; a repo set up by `setup.py` still builds without it (which is what a remote host will do).

## 3. Website Pipeline
### 3.1. Build and serve

Run from your repo root:

```sh
python .tools/build.py        # or: md-tools build
```

Site preferences (sidebar, header, footer) live in `.tools/config.toml`; see the [configuration docs](docs/config.md). The site is then served from `.public/`, which is the web root. You must serve from inside it so the root-absolute links resolve.

```sh
cd your-repo/.public && python3 -m http.server 8000    # or: md-tools serve
```

`md-tools serve` does the same (default port 8000, override with `md-tools serve 9000`) and refuses to start if you have not built the site yet. Then go to http://localhost:8000/

### 3.2. Deploy on a Remote Host (e.g., Netlify, Cloudflare, or your own server)

Set the build command to `pip install -r .tools/requirements.txt && python .tools/build.py`. Set the output directory to `.public`, typed exactly. The repo carries its own pipeline under `.tools/`, so the host needs nothing installed globally. Dependencies are pinned to exact versions in `requirements.txt`.

### 3.3. How the build works

See the [relevant documentation](docs/web-build.md).

## 4. File Merger

```sh
python .tools/merge.py path/to/file/1 path/to/file/2 -o path/to/output
# or: md-tools merge ...
```

Combines several markdown files into one new file, concatenating the bodies in the order you give and then rewriting their headings and footnotes so the result reads as a single document. For heading shifts and the other options, see [the docs](docs/merge.md).

## 5. TOC Generator

```sh
python .tools/toc.py path/to/file       # or: md-tools toc path/to/file
```

Generates a table of contents and inserts it beneath the H1 heading. If there is no H1, the block goes above the text and below the metadata block (if present). A block that already exists is rewritten where you left it, so a re-run refreshes rather than duplicates. For config options, see the [configuration docs](docs/config.md).

The block it writes is also what the website builder's `"toc"` sidebar mode reads, so running this over your pages is what populates their sidebars.

## 6. Footnote Arranger

```sh
python .tools/notes.py path/to/file     # or: md-tools notes path/to/file
```

Rewrites a single file in place, renumbering every footnote reference into one continuous sequence (by order of first appearance) and gathering all definitions at the foot. A file with no footnotes is left untouched. This is the same logic `merge.py` uses across files; see [the merge docs](docs/merge.md) for how unreferenced and undefined notes are handled.

## 7. Heading Numberer

```sh
python .tools/headings.py path/to/file  # or: md-tools headings path/to/file
```

Rewrites a single file in place, prepending nested numbers (`1.`, `1.1.`) to its headings. Existing manual numbers are stripped first, so a re-run reproduces the same output instead of doubling. See the [heading numbering docs](docs/headings.md) for anchoring, exclusions, and `--number-h1`. This is the same logic `merge.py` uses for its `--number` option.

## 8. Development

Each script carries a self-check covering its own logic. Run them against `src/` in this checkout:

```sh
for f in shared build toc merge notes headings; do python src/$f.py --selfcheck; done
```

`shared.py` holds the definitions the tools must agree on (the config path, the TOC markers, and what counts as a fence or a heading).
