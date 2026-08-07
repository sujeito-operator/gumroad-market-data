#!/usr/bin/env python3
"""Generate this repository's GitHub description and topics FROM the published summaries.

Why this exists. The repo description is a sales surface: it is what GitHub search shows,
what every link preview renders, and what a reviewer reads before clicking. It sat at
"1,511 live Gumroad products across 42 categories" until 2026-08-07 ~21:3x UTC — a figure
superseded on 2026-08-07 ~00:xx and corrected on every *generated* surface the same day.
It survived because nothing generated it. That is the third instance of the same class
(the Gumroad titles, the cover image, and now this), so the fix is a generator plus an
assertion, not a note saying to remember.

    python3 scripts/sync_repo_metadata.py           # print what it would set, change nothing
    python3 scripts/sync_repo_metadata.py --write   # PATCH the repo, then re-read and assert

Every figure below is read from data/*.json. Nothing here is typed by hand, so the next
time the data moves this file's output moves with it.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/srv/agents/make-money/scripts")
import envfile  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "sujeito-operator/gumroad-market-data"
HOMEPAGE = "https://sujeito-operator.github.io/gumroad-market-data/"
# Always the CONCEPT DOI, never a version DOI — it resolves to the newest version, so a
# citation made today still points at the current data.
CONCEPT_DOI = "10.5281/zenodo.21830103"

# GitHub truncates hard at 350; search snippets cut a long way before that.
MAX_DESC = 350

TOPICS = [
    "gumroad", "dataset", "open-data", "creator-economy", "digital-products",
    "ecommerce", "market-research", "indie-hackers", "selling-online",
    "product-market-fit",
]


def load(name):
    with open(os.path.join(ROOT, "data", name)) as fh:
        return json.load(fh)


def description():
    tax = load("taxonomy-summary.json")
    sales = load("sales-ratio-summary.json")
    return (
        f"{tax['n']:,} Gumroad products from {tax['sellers']:,} sellers across "
        f"{tax['nodes']} categories, plus {sales['disclosing']} listings publishing a "
        f"real unit-sales count. Measured Aug 2026, prices normalised to USD. "
        f"Free, CC BY 4.0, DOI {CONCEPT_DOI}."
    )


def api(path, token, method="GET", body=None):
    req = urllib.request.Request(
        f"https://api.github.com/{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "sujeito-operator-metadata-sync",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode() or "{}")


def main():
    desc = description()
    print("description:", desc)
    print("length     :", len(desc), f"(max {MAX_DESC})")
    print("homepage   :", HOMEPAGE)
    print("topics     :", ", ".join(TOPICS))
    if len(desc) > MAX_DESC:
        sys.exit(f"FAIL: description is {len(desc)} chars, over GitHub's {MAX_DESC} limit")

    # Any superseded headline must never reappear here. 1,511 and 1,344 are real figures
    # from the 42-search sample; they are simply not what this repo is, and the paid
    # report's own title is where 1,344 legitimately lives.
    for stale in ("1,511", "1511", "42 categories"):
        if stale in desc:
            sys.exit(f"FAIL: superseded figure {stale!r} in the generated description")

    if "--write" not in sys.argv:
        print("\n(dry run — pass --write to apply)")
        return

    token = envfile.load().get("GITHUB_CLASSIC_PAT")
    if not token:
        sys.exit("FAIL: GITHUB_CLASSIC_PAT missing from .env")

    api(f"repos/{REPO}", token, "PATCH", {"description": desc, "homepage": HOMEPAGE})
    api(f"repos/{REPO}/topics", token, "PUT", {"names": TOPICS})

    # Re-read and assert. A script that prints "done" while the surface still shows the
    # old value is exactly the failure this file exists to close.
    live = api(f"repos/{REPO}", token)
    live_topics = api(f"repos/{REPO}/topics", token)["names"]
    ok = True
    if live.get("description") != desc:
        print("MISMATCH description:", repr(live.get("description")))
        ok = False
    if live.get("homepage") != HOMEPAGE:
        print("MISMATCH homepage:", repr(live.get("homepage")))
        ok = False
    if sorted(live_topics) != sorted(TOPICS):
        print("MISMATCH topics:", live_topics)
        ok = False
    if not ok:
        sys.exit("FAIL: live repo does not match what was sent")
    print("\nVERIFIED live:", live["description"])
    print("VERIFIED topics:", ", ".join(sorted(live_topics)))


if __name__ == "__main__":
    main()
