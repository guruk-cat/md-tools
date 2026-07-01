# Markdown Tools

## 1. About

This repo hosts a set of custom-built tools for managing Markdown files. Its primary purposes are as follows:

1. Convert a bunch of Markdown files into a static website.
2. Merge files that have numbered headings and/or footnotes.
3. Generate and append tables of contents.

A `dummy-repo/` is included here for local testing.

## 2. General Usage

This repo (`md-tools/`) is where the tools are developed; it is not intended as the place where you use them. The code lives in `src/` and is exposed through a single `md-tools` command that you put on your PATH. Each of your own repos keeps only its content files (config, template, styling) under `.tools/`.

### 2.1. Install the command on your PATH

Symlink the dispatcher into a directory that is already on it (`~/.local/bin` is a common one), so `md-tools` works from anywhere:

```sh
ln -s "$(pwd)/src/md-tools" ~/.local/bin/md-tools
```

If `~/.local/bin` is not on your PATH, add this line to your `~/.zshrc` and open a new shell:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

The command runs under the `python3` on your PATH, so that interpreter needs the dependencies installed (`pip install -r src/requirements.txt`).

Because the symlink points back into this checkout, updating the tools is just `git pull` here. Nothing is copied into your repos except their content files.

### 2.2. Set up a repo

From inside the repo you want to publish:

```sh
md-tools setup
```

This scaffolds `.tools/` with the content files (`config.toml`, `template.html`, `style.css`, `robots.txt`, `requirements.txt`) and ensures `.gitignore` excludes `.public/`. Existing files are left untouched, so re-running never clobbers your edits. To pull the latest shipped defaults, use `md-tools setup --override` (all files) or name specific ones, e.g. `md-tools setup --override template.html`.

### 2.3. Expected layout

After setup, your repo will look something like this:

```
repo-root/
    README.md           ← used as homepage content
    some-docs/
        *.md
        *.png           ← non-md assets okay
    some-other-docs/
        *.md
    .tools/             ← per-repo content only (no code)
        config.toml
        template.html
        style.css
        robots.txt
        requirements.txt
    .public/            ← build output, made by `md-tools build`
    .gitignore
```

The `.tools/` and `.public/` directories are dot-prefixed to keep them out of a markdown editor's file view. The executable code is not copied here; only the files a repo owns and may customize live under `.tools/`. The `.gitignore` must exclude `.public/`, such that the output of the website pipeline is never committed. (The intended usage is that the build runs on the server-side, to generate its own `.public` output.) The `md-tools setup` command adds this exclusion for you.

## 3. Website Pipeline
### 3.1. Build

Run from your repo root:

```sh
md-tools build
```

Site preferences (sidebar nav, copyright footer) live in `.tools/config.toml`; see the [configuration docs](docs/config.md). If `template.html` is missing or is an older version that lacks a required placeholder, the build refuses to run and tells you to re-scaffold it. Pass `--selfcheck` (via `python src/build.py --selfcheck` in this repo) to run the pipeline's internal checks without building anything.

### 3.2. Serving locally

```sh
md-tools serve
```

This serves `.public/` (the web root) on port 8000; pass a different port with `md-tools serve 9000`. It serves from inside `.public/` so the root-absolute links resolve, and refuses to start if you have not built the site yet. Then go to http://localhost:8000/

### 3.3. Deploy on a Romote Host (e.g., Netlify, Cloudflare, or your own server)

Set the build command to `pip install -r .tools/requirements.txt && md-tools build` (or invoke the script directly if `md-tools` is not on the build container's PATH). Set the output directory to `.public`, typed exactly.

Dependencies are pinned to exact versions in `requirements.txt`, so the build container cannot silently pull an untested version of the markdown library.

### 3.4. How the build works

See the [relevant documentation](docs/web-build.md).

## 4. File Merger

Run from your repo root:

```sh
md-tools merge path/to/file/1 path/to/file/2 -o path/to/output
```

The script combines several markdown files into one new file. It concatenates the file bodies in the order you give, then rewrites their headings and footnotes so the result reads as a single document. For additional options, see [the docs](docs/merge.md).

## 5. TOC Generator

Run from your repo root:

```sh
md-tools toc path/to/file
```

It will generate a table of contents and append it beneath the H1 heading, if present. If no H1 heading is present, the table will be appended above the text and below the metadata block (if present). For config options, see [configuration docs](docs/config.md).
