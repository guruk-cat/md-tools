# Crawler Protection and Deployment

## 1. Background

The pipeline's intended usage target is a private research and notes repoistory, not a high-sensitivity target. The aim is not authentication as an end in itself but keeping bots and crawlers from scraping or indexing the content. Most of that threat (search engines and AI training crawlers like GPTBot, ClaudeBot, and Bytespider) respects `robots.txt` near-universally, so `robots.txt` plus a per-page `noindex` handles it. Adversarial scrapers ignore `robots.txt`, and that category is the only one that would need an auth wall, which the pipeline tool doesn't handle.

## 2. Primary Defenses
### 2.1. robots.txt

`robots.txt` lives in `src/` and is copied to the build output root on every build, so it stays versioned with the source rather than hand-maintained. It blocks all crawlers by default and, following Codeberg's approach, also disallows a list of known AI and search crawlers by name as a belt-and-suspenders layer over the wildcard.

### 2.3. noindex meta tag

The pipeline template at `src/template.html` carries `<meta name="robots" content="noindex, nofollow">`, so every generated page is marked no-index. Like `robots.txt`, this is part of the build rather than a separate system.
