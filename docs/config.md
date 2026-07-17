# Configuration Dictionary

## 1. Usage

The setup script (`setup.py`) includes a scaffoleded `config.toml` in the `.tools/` directory of the target repo. You can edit this, and the build script (`build.py`) will respect preferences.

## 2. Keys for the website builder

### 2.1. `[sidebar]` section

Controls what the build puts in the left gutter.

- `mode`: one of `"none"`, `"browse"`, `"readme"`, or `"toc"`. Defaults to `"none"`. Any other value fails the build. See section 2.1.1 below.

#### 2.1.1. `mode` values

- `"none"`: no sidebar is rendered.
- `"browse"`: a single sidebar, shared by every page, presenting the whole site as a collapsible tree that mirrors the folder structure. Files are listed alphabetically by title. Folders are collapsible, and the folders containing the current page are opened on load; everything else starts closed.
- `"readme"`: the sidebar is scoped rather than global. Root-level pages (the homepage and any markdown file next to the root README) show a global sidebar: those root pages at the top, followed by one link per top-level directory that contains its own `README.md`. Each such link points at that directory's README and is labeled by its title (frontmatter `title`, then first H1, then filename). Directories without a README are omitted. Opening a directory's README (or any page inside that directory) swaps the sidebar for a `browse`-style tree scoped to that directory alone, topped with a Home link back to the site root. A README nested deeper than a top-level directory gets no special treatment; it appears as an ordinary file within its parent directory's scoped tree.
- `"toc"`: the sidebar is the page's own table of contents rather than a map of the site. See section 2.1.2 below.

#### 2.1.2. The `"toc"` mode

The build reads the block that `toc.py` writes (the `<!-- toc -->` ... `<!-- /toc -->` markers) and renders it into the sidebar. The block is taken out of the page body, so the contents appear once on the built page rather than twice. Your source `.md` file is not touched, so the TOC still renders inline when the file is read on GitHub or in an editor.

Presentation follows Wikipedia's sidebar. First-level sections are foldable and start folded, so a long document shows a scannable list of its top-level sections on load. Everything nested beneath a first-level section appears when that section is expanded. Clicking a section both jumps to it and unfolds it.

Which heading level counts as "first-level" is whatever `toc.py` put at the top of the block (H2 in a typical document with a single H1 title). The sidebar does not re-derive this; it reflects the nesting of the block as generated, including the `max_depth` cap from `[toc-builder]`.

A page whose markdown carries no TOC block gets no sidebar, and its content is centered exactly as it would be under `mode = "none"`. A page with an opening marker but no closing one fails the build rather than being rendered with a truncated body.

### 2.2. `[site-layout]` section

- `home = str` : override the homepage (README) title. It is used for the `<title>` tag and, in `"readme"` sidebar mode, for the homepage's pinned entry and the Home link.

### 2.3. `[header]` section

Renders a static bar of links across the top of a page, above both the sidebar and the body. The header, the sidebar, and the body all sit inside one centered container, so the three share the same left and right edges.

The bar sits in normal document flow rather than being pinned, so it scrolls away as the visitor reads. Where a sidebar is present, the sidebar rides down with the header and then sticks to the top of the viewport once the header has scrolled out of view.

- `show`: which pages carry the bar. Defaults to `"disabled"` (also the effect when the section is absent). 
    - `"disabled"`: the bar is never rendered.
    - `"all"`: the bar renders on all pages
    - `"home"`: the bar renders on the homepage (the repo-level README) only.
    - `"not home"`: the bar renders on every page except the homepage.
- `[header.homelink]`: optional, at most one. Takes only a `name`; the build points it at the site root, so no `url` is given. A homelink without a `name` fails the build.
- `[[header.link]]`: one entry per link, each with a `name` and a `url`. A link missing either key fails the build.

With a homelink, it is pinned to the left of the bar and the `[[header.link]]` entries sit to the right. Without one, the links start on the left instead.

If `show` is enabled but neither a homelink nor any links are given, no bar is rendered. A homelink on its own is enough to render one.

### 2.4. `[footer]` section

A footer is generated on every page if the section is present. It holds one or more lines.

- `[[footer.line]]`: one entry per line, each with a `text`. A line missing `text` fails the build.

Each line's `text` is rendered as markdown, so it can mix plain words and inline links (for example, `"Licensed through [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)"`). Lines are stacked in the order given.

## 3. Keys for TOC building

### 3.1. `[toc-builder]` section

- `max_depth`: deepest heading level to list. Defaults to 6.
- `slug_style`: anchor scheme. `"site"` (default) matches the slugs the website builder generates, so links work on the built site. `"github"` matches GitHub's raw `.md` rendering instead. They differ mainly on duplicate headings (`_1` vs `-1`).
- `toc_title`: heading text for the generated TOC. Defaults to "Table of Contents".

## 4. Keys for heading numbering

### 4.1. `[exclude-headings]` section

- `titles`: a list of heading texts (matched without any manual number) to leave out of the numbering. An excluded heading keeps its text as-is and does not consume a counter, so its siblings number as if it were not there. The CLI `--exclude` flag overrides this list when given.
