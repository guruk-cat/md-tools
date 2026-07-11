# Configuration Dictionary

## 1. Usage

The setup script (`setup.py`) includes a scaffoleded `config.toml` in the `.tools/` directory of the target repo. You can edit this, and the build script (`build.py`) will respect preferences.

## 2. Keys for the website builder

### 2.1. `[site-layout]` section

Used to configure layout options.

- `nav`: sidebar navigation mode. One of `"none"`, `"browse"`, or `"readme"`. Defaults to `"none"`. Any other value fails the build. See section 2.1.1 below.
- `home = str` : override the homepage (README) title.

#### 2.1.1. `nav` modes

- `"none"`: no sidebar is rendered.
- `"browse"`: a single sidebar, shared by every page, presenting the whole site as a collapsible tree that mirrors the folder structure. Files are listed alphabetically by title; folders are collapsible and remember their open/closed state across page loads.
- `"readme"`: the sidebar is scoped rather than global. Root-level pages (the homepage and any markdown file next to the root README) show a global sidebar: those root pages at the top, followed by one link per top-level directory that contains its own `README.md`. Each such link points at that directory's README and is labeled by its title (frontmatter `title`, then first H1, then filename). Directories without a README are omitted. Opening a directory's README (or any page inside that directory) swaps the sidebar for a `browse`-style tree scoped to that directory alone, topped with a Home link back to the site root. A README nested deeper than a top-level directory gets no special treatment; it appears as an ordinary file within its parent directory's scoped tree.

### 2.2. `[header]` section

Renders a static bar of outbound links at the top of a page, aligned with the body text. The bar sits in normal document flow rather than being pinned, so it scrolls away as the visitor reads. It is independent of the sidebar.

- `show`: which pages carry the bar. One of `"disabled"`, `"home"`, or `"not home"`. Defaults to `"disabled"` (also the effect when the section is absent). Any other value fails the build.
- `[[header.link]]`: one entry per link, each with a `name` and a `url`. A link missing either key fails the build.

The `show` modes are:

- `"disabled"`: the bar is never rendered.
- `"home"`: the bar renders on the homepage (the repo-level README) only.
- `"not home"`: the bar renders on every page except the homepage.

If `show` is enabled but no links are given, no bar is rendered.

### 2.3. `[footer]` section

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
