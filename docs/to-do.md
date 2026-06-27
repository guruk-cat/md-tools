# TODO

## 1. Easy stuff

1. nav bar drop down folds
2. footnote tooltips

## 2. Server-side

Netlify supports HTTP Basic Auth via a `_headers` file at the site root on the free tier, unlike its dashboard password toggle which requires the Pro plan (~$19/mo). The form is:

```
/*
  Basic-Auth: username:password
```

Netlify's docs frame this as casual or temporary protection rather than a polished access flow, and the password lives in plaintext in the repo, which is acceptable here since the git repo itself is already private. This would be a nice-to-have for protection against adversarial scrapers that ignore `robots.txt`. 
