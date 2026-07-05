# Markdown Tools

## 1. About

This repo hosts a set of custom-built tools for managing Markdown files. Its primary purposes are as follows:

1. Build a static website from a bunch of Markdown files.
2. Arrange numbered headings and footnotes.
3. Merge files that have numbered headings and/or footnotes.
4. Generate and append a table of contents.

A `dummy-repo/` is included here for local testing.

## 2. General Usage

This repo (`md-tools/`) is where the tools are developed; it is not intended as the place where you use them. The tools live in `src/` and get copied into your own repo as `.tools/`, so that a repo carries its own pipeline and can build itself on a remote host. Optionally, you can also expose an `md-tools` command on your PATH as a local convenience.

### 2.1. Set up the tools in your repo

Run, from this checkout:

```sh
python setup.py /path/to/your-repo
```

This copies the pipeline (the scripts, `requirements.txt`, `template.html`, and `robots.txt`) into the target's `.tools/`, refreshing them on every run so a re-run pushes the latest version. The user-edited files (`config.toml` and `style.css`) is written only if absent, so edits are never clobbered; pass `--override` to refresh those to the shipped defaults. It also ensures `.gitignore` excludes `.public/`.

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
        build.py
        toc.py
        merge.py
        notes.py
        headings.py
        requirements.txt
        config.toml
        template.html
        style.css
        robots.txt
    .public/            ← build output, made by build.py
    .gitignore
```

The `.tools/` and `.public/` directories are dot-prefixed to keep them out of a markdown editor's file view. The `.gitignore` must exclude `.public/`, such that the output of the website pipeline is never committed. (The intended usage is that the script is run on the server-side, to generate its own `.public` output.) The `setup.py` script adds this exclusion for you.

### 2.3. Optional: an `md-tools` command on your PATH

For local use, you can drive the pipeline with a single `md-tools` command instead of typing `python .tools/build.py` each time. Symlink the dispatcher into one that is already on it (`~/.local/bin` used in the example below):

```sh
ln -s "$(pwd)/src/md-tools" ~/.local/bin/md-tools
```

Then `md-tools setup`, `md-tools build`, `md-tools serve`, `md-tools toc`, `md-tools merge`, `md-tools notes`, and `md-tools headings` work from any repo root. The command runs under the `python3` on your PATH, so that interpreter needs the dependencies installed (`pip install -r src/requirements.txt`). This is a convenience only; a repo set up by `setup.py` still builds without it (which is what a remote host does).

## 3. Website Pipeline
### 3.1. Build

Run from your repo root:

```sh
python .tools/build.py        # or, with the PATH command: md-tools build
```

Site preferences (sidebar nav, copyright footer) live in `.tools/config.toml`; see the [configuration docs](docs/config.md). If `template.html` is missing or is an older version that lacks a required placeholder, the build refuses to run and tells you to re-scaffold it. Pass `--selfcheck` to run the pipeline's internal checks without building anything.

### 3.2. Serving locally

The site is served from `.public/`, which is the web root. You must serve from inside it so the root-absolute links resolve.

```sh
cd your-repo/.public && python3 -m http.server 8000    # or: md-tools serve
```

`md-tools serve` does the same (default port 8000, override with `md-tools serve 9000`) and refuses to start if you have not built the site yet. Then go to http://localhost:8000/

### 3.3. Deploy on a Romote Host (e.g., Netlify, Cloudflare, or your own server)

Set the build command to `pip install -r .tools/requirements.txt && python .tools/build.py`. Set the output directory to `.public`, typed exactly. The repo carries its own pipeline under `.tools/`, so the host needs nothing installed globally. Dependencies are pinned to exact versions in `requirements.txt`.

### 3.4. How the build works

See the [relevant documentation](docs/web-build.md).

## 4. File Merger

Run from your repo root:

```sh
python .tools/merge.py path/to/file/1 path/to/file/2 -o path/to/output    
# or: md-tools merge ...
```

The script combines several markdown files into one new file. It concatenates the file bodies in the order you give, then rewrites their headings and footnotes so the result reads as a single document. For additional options, see [the docs](docs/merge.md).

## 5. TOC Generator

Run from your repo root:

```sh
python .tools/toc.py path/to/file       # or: md-tools toc path/to/file
```

It will generate a table of contents and append it beneath the H1 heading, if present. If no H1 heading is present, the table will be appended above the text and below the metadata block (if present). For config options, see [configuration docs](docs/config.md).

## 6. Footnote Arranger

Run from your repo root:

```sh
python .tools/notes.py path/to/file     # or: md-tools notes path/to/file
```

It rewrites a single file in place, renumbering every footnote reference into one continuous sequence (by order of first appearance) and gathering all definitions at the foot. A reference whose definition is missing is kept, with its bracket text becoming the definition. A definition that is never referenced is kept under a `[^no-ref-N]` label. A file with no footnotes is left untouched. This is the same logic `merge.py` uses across files.

## 7. Heading Numberer

Run from your repo root:

```sh
python .tools/headings.py path/to/file  # or: md-tools headings path/to/file
```

It rewrites a single file in place, prepending nested numbers (`1.`, `1.1.`) to its headings. Any existing manual numbers are stripped first, so a re-run reproduces the same output instead of doubling. Numbering anchors at H2 by default; pass `--number-h1` to include H1. This is the same logic `merge.py` uses for its `--number` option.
