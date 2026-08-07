#!/usr/bin/env python3
"""Strip personal contact details out of crawled listing text before publishing.

A handful of sellers put an email address in their own product title, so it arrives in
the card text the crawl reads. That address is public on a Gumroad search page, but a
CSV that anyone can download and a static page that search engines index are a different
kind of exposure — one is a page nobody scrapes, the other is a mailing list. It comes
out of everything this repo publishes.

Deliberately applied at NORMALISE time, not at crawl time: `data/raw-*.jsonl` stays a
faithful record of what was served, and every published artifact is a derivation of it.
Anything that writes a published file must run titles through `scrub()`.

    from redact import scrub
    title = scrub(row["t"])

Run as a script to sanitise an already-published CSV in place:

    python3 scripts/redact.py data/gumroad-latest.csv
"""
import pathlib
import re
import sys

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PLACEHOLDER = "[email removed]"


def scrub(text):
    """Replace any email address in `text`. Safe on None and on non-strings."""
    if not text:
        return text
    return EMAIL.sub(PLACEHOLDER, text)


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    for name in argv:
        p = pathlib.Path(name)
        before = p.read_text(encoding="utf-8")
        after = EMAIL.sub(PLACEHOLDER, before)
        n = len(EMAIL.findall(before))
        if n:
            p.write_text(after, encoding="utf-8")
        print(f"{p}: {n} address(es) replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
