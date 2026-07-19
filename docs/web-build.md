# How the Website Build Works

## 1. Build Process

Conversion uses the `markdown` library with the `meta`, `toc`, `footnotes`, `tables`, and `fenced_code` extensions. The `toc` extension gives headings IDs so that `#anchor` links resolve.

The root `README.md` becomes the homepage, `index.html`. Every other `.md` file becomes a matching `.html` file, mirroring the source folder structure. Non-markdown files such as images are copied through, preserving their structure.

Internal links are rewritten on the rendered HTML (the `href` attribute) rather than the raw markdown, so links inside code blocks are left alone and reference-style links are covered. Links become root-absolute, like `/notes/methods.html`, so navigation works from any folder depth. A link that resolves to the root `README.md` maps to `/index.html`.

Page titles, used for the `<title>` tag and for nav link text, resolve in priority order: the frontmatter `title` field, then the first `# H1` heading, then the filename.

Under the `"toc"` sidebar mode, a page's TOC block is lifted out of the markdown before rendering and becomes that page's sidebar. See the [configuration docs](config.md) for the mode itself.

## 2. Guarantees

The pipeline never modifies your source files. All rewriting happens on in-memory HTML and is written only under `.public/`.

Every build is a full clean rebuild: `.public/` is deleted and regenerated from scratch, so renamed or deleted sources leave no orphan HTML behind. For this reason you should never put hand-authored files in `.public/`.

The rebuild happens only once the build is certain to succeed. Every check that can refuse (the config sections, the template and its placeholders, the presence of `style.css` and `robots.txt`, and every page's TOC block) runs before `.public/` is touched, and all pages are rendered in memory before any of them are written. A refused build therefore leaves the previous one standing rather than deleting a working site and then erroring out.

## 3. Crawler Protection and Deployment
### 3.1. robots.txt

`robots.txt` lives in `src/` and is copied to the build output root on every build, so it stays versioned with the source rather than hand-maintained. It blocks all crawlers by default and, following Codeberg's approach, also disallows a list of known AI and search crawlers by name as a belt-and-suspenders layer over the wildcard.

### 3.2. noindex meta tag

The template at `src/template.html` carries `<meta name="robots" content="noindex, nofollow">`, so every generated page is marked no-index. Like `robots.txt`, this is part of the build rather than a separate system.
