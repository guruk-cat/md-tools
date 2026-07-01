#!/usr/bin/env python3
"""
Provision a repo's `.tools/` with the pipeline: the scripts plus its content files.

    python setup.py /path/to/repo        # run from this checkout
    md-tools setup                       # run from inside the target repo

The scripts and requirements.txt are refreshed on every run, so a repo always
carries the latest pipeline (and can build itself on a remote host without this
checkout). The content files are written only if absent, so your edits survive;
`--override` refreshes them to the shipped defaults (all, or just the ones you name).
"""

import shutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"

# Refreshed every run; not meant to be hand-edited inside a target repo.
CODE = ["build.py", "toc.py", "merge.py", "requirements.txt"]
# Owned by the repo and customizable; never clobbered unless named in --override.
CONTENT = ["config.toml", "template.html", "style.css", "robots.txt"]


def setup(root, override=None):
    root = Path(root).resolve()
    if not root.is_dir():
        sys.exit(f"target is not a directory: {root}")
    override = set(override or ())

    dest = root / ".tools"
    dest.mkdir(exist_ok=True)

    for name in CODE:
        shutil.copy2(SRC / name, dest / name)
    print(f"refreshed pipeline in {dest}")

    for name in CONTENT:
        target = dest / name
        existed = target.exists()
        if existed and name not in override:
            continue
        shutil.copy2(SRC / name, target)
        print(f"{'overwrote' if existed else 'wrote'} {target}")

    ensure_gitignore(root)


def ensure_gitignore(root):
    # The build output must never be committed; the server regenerates its own.
    gitignore = root / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if ".public/" not in lines:
        with gitignore.open("a", encoding="utf-8") as f:
            if lines and lines[-1].strip():
                f.write("\n")
            f.write(".public/\n")
        print(f"added .public/ to {gitignore}")


def run_cli(argv):
    # Optional leading positional target; defaults to the current repo.
    root = Path.cwd()
    if argv and not argv[0].startswith("-"):
        root, argv = Path(argv[0]), argv[1:]

    override = None
    if argv:
        if argv[0] != "--override":
            sys.exit(f"unknown option: {argv[0]}\n\n{__doc__.strip()}")
        names = argv[1:]
        bad = [n for n in names if n not in CONTENT]
        if bad:
            sys.exit(f"not a content file: {', '.join(bad)}. Choose from: {', '.join(CONTENT)}")
        override = names or CONTENT  # bare --override means all

    setup(root, override)


if __name__ == "__main__":
    run_cli(sys.argv[1:])
