# Custom MD-to-HTML Pipeline

## 1. Background

I have a research repo (mostly markdown, ~90%, plus some images and a few CLI-tool-related files). Originally explored MkDocs + Material for MkDocs, but decided against it due to:

- MkDocs 1.x unmaintained 18+ months; MkDocs 2.0 is a breaking rewrite (removes plugin system, breaks theme overrides, no migration path).
- Material for MkDocs entered maintenance mode (Nov 2025), security fixes only through ~Nov 2026.
- General discomfort depending on a large theme/plugin ecosystem that's bigger than what this simple repo actually needs.
- A Cloudflare Pages build container running `pip install mkdocs-material` fresh on every build would silently "unfreeze" version pins even if the local dev venv is frozen; defeats the point of pinning unless a requirements.txt is carried into CI too.

Decision: build a minimal custom static site generator instead. Small enough to fully understand and maintain solo, no dependency-churn risk.

## 2. Goal / Requirements

- Convert folders of markdown files into a folders of static HTML files
- `README.md` at repo root acts as the homepage
- Local markdown links (`[text](other.md)`) must be rewritten to point to the corresponding `.html` output file
- Custom CSS (I want to write my own styling, not inherit a theme)
- Maybe: a simple nav/sidebar generated from the folder structure (nice to have, not essential; could also just rely on README's own links)
- Keep it minimal — explicitly avoid scope creep into reimplementing MkDocs/Material features (no search, no versioning, no i18n, etc. unless later explicitly requested)

## 3. Deployment: Local Usage

The present repository (`md-site/`) is the build repository for the tool in question. In other words, this is NOT the research repository wherein the tool will actually be used. The plan is to have, within the present repo, a `src/` directory with all the Python scripts, than can be easily copied to a different directory as `.tools/` whenever needed. A dedicated script for this operation (such that I don't need to worry about file paths and whatnot, things that could result in mistakes) might be good.

If needed, we can later add a "dummy repo" that resembles what a real research repo looks like.

## 4. Deployment Target: Cloudflare Pages

- The actual reserach repo will be hosted on **GitHub, set to Private** 
- Cloudflare Pages connects to the GitHub repo via GitHub's native OAuth App / GitHub integration (standard Cloudflare Pages "Connect to Git" flow); auto-builds and deploys on every push to main
- Cloudflare Pages **build command** will run the custom Python pipeline, e.g.: `pip install -r .tools/requirements.txt && python .tools/build.py`
- Cloudflare Pages **output directory** will be a dot-prefixed folder, e.g. `.public/` (confirmed Cloudflare has no issue with dot-prefixed output dirs; just must be typed exactly into the dashboard's output directory field, and any internal globbing in build.py should reference it by name rather than relying on wildcard expansion, since dotdirs are excluded from default shell globs).
- Beyond the private repo, the **deployed site itself** will also be locked down via Cloudflare Access policy (e.g. email-based one-time PIN, or a shared service token); private repo and "unlisted deployed site" are two separate locks, both planned here.

## 5. Repo structure at usage location (intended)

```
repo-root/
    README.md           ← homepage content
    some-docs/          ← research content lives inside dirs at root, possibly nested folders
        *.md            ← research content
    some-other-docs/
        *.md
    .tools/             ← pipeline code 
                          (dot-prefixed: don't want it cluttering the markdown editor's file view)
        build.py
        requirements.txt
        template.html
        style.css
    .public/            ← build output (dot-prefixed, same reasoning); 
                          Cloudflare would make its own, but I might want a local one, too, for testing
    .gitignore          ← MUST exclude `.public/` 
                          (output is never committed, Cloudflare builds it fresh from source every push)
```

## 6. Build script requirements (for `.tools/build.py`)

1. Walk the markdown source folder (recursively)
2. For each `.md` file, convert to HTML using the **`markdown`** library (mature, pure-Python, stable extension API). Enable extensions: `meta` (frontmatter), `toc` (auto heading IDs so `#anchor` links resolve), `footnotes`, `tables`, `fenced_code`.
3. Rewrite internal links **on the rendered HTML, not the raw markdown**: match `href="...md"` / `href="...md#anchor"` and swap the `.md` extension for `.html`, preserving relative path structure. Doing this on the `href` attribute (rather than regex over markdown source) avoids hitting links inside code blocks and correctly covers reference-style links and footnotes.
4. Wrap converted HTML in a simple template (`template.html`) via plain `str.replace` on placeholders (`{{content}}`, `{{title}}`). No Jinja2.
5. Title resolution, in priority order: frontmatter `title` field (parsed by the `meta` extension, which also strips the block from output) → first `# H1` heading → filename.
6. Preserve folder structure in output (mirror source tree under `.public/`)
7. `README.md` at repo root → `.public/index.html`
8. Copy over any images/static assets referenced by the markdown (don't just convert .md files; non-md assets need to land in `.public/` too)
9. Pin dependencies explicitly in `.tools/requirements.txt` (exact versions, not loose `>=`) so the Cloudflare build container can't silently pull a newer version of the markdown library than what's been tested locally
10. **Never modify the original `.md` source files.** The pipeline is read-only on source; all rewriting happens on the in-memory rendered HTML and is written only under `.public/`.
11. **Footnotes reliability:** call `md.reset()` (or build a fresh `Markdown` instance) before converting each file. The `footnotes` extension accumulates definitions/counters on the instance, so reusing one object across the walk loop leaks footnotes between files and collides IDs. Source uses footnotes heavily — this is mandatory, not optional.

## 7. Things NOT to do / explicitly out of scope for now

- Don't reach for a templating framework (Jinja2 is fine if convenient, but don't pull in something heavy)
- Don't build search, multi-language support, or theming systems
- Don't auto-generate nav until asked; may just rely on README's own links as the "front page index," per original requirement (collaborators only need to browse via README's links, not a generated sitewide nav)
- Avoid scope creep in general; I want to fully understand and own this pipeline, not rebuild MkDocs

## 8. Resolved decisions

- Library: **`markdown`** (chosen over `mistune` for maturity/stability; no perf need).
- Link rewriting: on rendered HTML `href` attributes, not raw markdown.
- Template: `str.replace` placeholders, no Jinja2.
- Title: frontmatter `title` → first H1 → filename.
- Frontmatter: parsed by built-in `meta` extension (no PyYAML dependency).
- Incremental builds: skipped for now (full rebuild is fast enough).
- `setup-tools.py` (copy `src/` → target repo's `.tools/`): deferred until later.
