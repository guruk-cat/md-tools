---
title: Methods & Materials
---

# How the Work Was Done

The frontmatter `title` ("Methods & Materials") must override this H1 for the page title.

## Results

Summary of outcomes. Back to the [introduction](intro.md).

## Data

| Sample | Value | Notes |
| --- | --- | --- |
| A | 0.42 | baseline |
| B | 0.91 | treated[^method] |

```python
def measure(sample):
    return sample.value * 2  # a [link](should-not-rewrite.md) inside code
```

![Pipeline diagram](../assets/diagram.svg)

[^method]: A footnote reusing a different label, local to methods.md.
