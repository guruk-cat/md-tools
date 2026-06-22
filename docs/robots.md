# Crawler Protection and Deployment

## 1. Goal

The pipeline's intended usage target is a private research repo, not a high-sensitivity target. The aim is not authentication as an end in itself but keeping bots and crawlers from scraping or indexing the content. Most of that threat (search engines and AI training crawlers like GPTBot, ClaudeBot, and Bytespider) respects `robots.txt` near-universally, so `robots.txt` plus a per-page `noindex` handles it. Only genuinely adversarial scrapers ignore `robots.txt`, and that narrow category is the only one that would need an auth wall.

## 2. Primary Defenses
### 2.1. The Git Repo

The GitHub repo is private. The hosting and crawler-protection details below apply to the deployed public output, not the source.

### 2.2. robots.txt

`robots.txt` lives in `src/` and is copied to the build output root on every build, so it stays versioned with the source rather than hand-maintained. It blocks all crawlers by default and, following Codeberg's approach, also disallows a list of known AI and search crawlers by name (GPTBot, ClaudeBot, Amazonbot, PerplexityBot, Bytespider, and others) as a belt-and-suspenders layer over the wildcard.

### 2.3. noindex meta tag

The pipeline template at `src/template.html` carries `<meta name="robots" content="noindex, nofollow">`, so every generated page is marked no-index. Like `robots.txt`, this is part of the build rather than a separate system.

## 3. Authentication
### 3.1. Netlify

My current choice of hosting service is Netlify, connected to the private GitHub repo with auto-deploy on push to main. It is a standard Netlify "Connect to Git" plus GitHub OAuth flow. The build command runs the Python pipeline in `.tools/` and the publish directory is `.public/`.

Netlify supports HTTP Basic Auth via a `_headers` file at the site root on the free tier, unlike its dashboard password toggle which requires the Pro plan (~$19/mo). The form is:

```
/*
  Basic-Auth: username:password
```

Netlify's docs frame this as casual or temporary protection rather than a polished access flow, and the password lives in plaintext in the repo, which is acceptable here since the repo itself is already private. This is a nice-to-have for belt-and-suspenders protection against adversarial scrapers that ignore `robots.txt`. It is not implemented; I'll add it only if that extra layer is warranted in the future.

### 3.2. History

Deployment started on Cloudflare Pages, which worked technically (git integration, auto-deploy on push) but had two dealbreakers: no simple shared-password lock (only email-based OTP via Cloudflare Access, which added friction), and a dashboard surface too large for a non-expert use case. Netlify replaced it with the same git-push-to-deploy model on a simpler surface.

Cloudflare Pages and Cloudflare Access are not under reconsideration. Netlify's paid dashboard password toggle is also ruled out, since the free-tier `_headers` approach covers the same need at no cost.
