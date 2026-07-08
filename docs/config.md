# Configuration Dictionary

## 1. Usage

The setup script (`setup.py`) includes a scaffoleded `config.toml` in the `.tools/` directory of the target repo. You can edit this, and the build script (`build.py`) will respect preferences.

## 2. Keys for the website builder

### 2.1. `[site-layout]` section

Used to configure layout options.

- `nav`: sidebar navigation mode. One of `"none"`, `"browse"`, or `"readme"`. Defaults to `"none"`. Any other value fails the build. See section 2.1.1 below.
- `front = str` : override the homepage (README) title.

#### 2.1.1. `nav` modes

- `"none"`: no sidebar is rendered.
- `"browse"`: a single sidebar, shared by every page, presenting the whole site as a collapsible tree that mirrors the folder structure. Files are listed alphabetically by title; folders are collapsible and remember their open/closed state across page loads.
- `"readme"`: the sidebar is scoped rather than global. Root-level pages (the homepage and any markdown file next to the root README) show a global sidebar: those root pages at the top, followed by one link per top-level directory that contains its own `README.md`. Each such link points at that directory's README and is labeled by its title (frontmatter `title`, then first H1, then filename). Directories without a README are omitted. Opening a directory's README (or any page inside that directory) swaps the sidebar for a `browse`-style tree scoped to that directory alone, topped with a Home link back to the site root. A README nested deeper than a top-level directory gets no special treatment; it appears as an ordinary file within its parent directory's scoped tree.

### 2.2. `[header]` section

Renders a static bar of outbound links at the top of the homepage (the repo-level README), aligned with the body text. The bar sits in normal document flow rather than being pinned, so it scrolls away as the visitor reads. It appears only on the homepage and is independent of the sidebar.

- `show`: whether to render the bar. The section is ignored if this is absent or false.
- `[[header.link]]`: one entry per link, each with a `name` and a `url`. 

If `show` is true but no links are given, no bar is rendered.

### 2.3. `[copyright]` section

A copyright footer is generated if section is present. When present, all three keys are required; a missing key fails the build.

- `author`
- `year`
- `tag`: something like "C.C. by 4.0" or "All rights reserved."

Output: "Copyright <year>, <author>. <tag>"

## 3. Keys for file merging

## 4. Keys for TOC building

### 4.1. `[toc-builder]` section

Options for the standalone TOC builder (`toc.py`), which inserts a table of contents into each `.md` file in place (under the topmost H1, or at the top below YAML frontmatter if there is no H1). Re-running rewrites the existing TOC rather than stacking a new one. This is separate from the website build.

- `max_depth`: deepest heading level to list. Defaults to 6.
- `slug_style`: anchor scheme. `"site"` (default) matches the slugs the website builder generates, so links work on the built site. `"github"` matches GitHub's raw `.md` rendering instead. They differ mainly on duplicate headings (`_1` vs `-1`).
- `toc_title`: heading text for the generated TOC. Defaults to "Table of Contents".
