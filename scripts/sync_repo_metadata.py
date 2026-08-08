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

RELEASES ARE THE FOURTH INSTANCE OF THE SAME CLASS, found 2026-08-08 ~04:5x UTC. The
Releases tab is a published surface — GitHub renders the newest release on the repo
sidebar and its assets are directly downloadable — and `v1.1` was still headlined
"1,511 live Gumroad products across 42 categories" and still shipping a 1,511-row
`gumroad-latest.csv`, with two recorded downloads, long after every generated surface had
moved on. It survived the 2026-08-07 sweep for the usual reason: nothing generated it.

A release cannot be rewritten to track the data — it is an archival artifact, and editing
its body to match today's figures would be falsifying what was published. So the fix is
the one Zenodo already uses for the same problem: leave the body alone and mark it
SUPERSEDED, with a banner that contains NO FIGURES AT ALL, only pointers to the three
surfaces that are regenerated (repo `data/`, the site, the concept DOI). A banner with no
numbers in it cannot go stale, which is the entire design constraint.
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
    # The leading words are load-bearing, not decoration. GitHub's default repo search
    # matches name and description; topics only match under an explicit `in:topics`.
    # Measured 2026-08-08 ~00:0x UTC: `gumroad dataset` returned 9 repos and this one was
    # NOT among them, because the description never said "dataset" or "CSV" — the two
    # words someone looking for this actually types. See SEARCH_WORDS below.
    return (
        f"Free Gumroad dataset (CSV): {tax['n']:,} products from {tax['sellers']:,} "
        f"sellers across {tax['nodes']} categories, plus {sales['disclosing']} listings "
        f"publishing a real unit-sales count. Measured Aug 2026, prices normalised to "
        f"USD. CC BY 4.0, DOI {CONCEPT_DOI}."
    )


# Words a buyer types into GitHub search. Asserted present, lowercased, so a future
# rewrite of description() cannot quietly drop the repo out of the queries again.
SEARCH_WORDS = ("gumroad", "dataset", "csv", "sellers", "products")

# Headlines that were true once and are not the current sample. Checked against the
# generated description AND against every release body.
SUPERSEDED = ("1,511", "1511", "42 categories", "1,344")

# Deliberately figure-free — see the module docstring. Every pointer here is to a surface
# that something regenerates, so this text is correct for as long as the repo exists.
SUPERSEDE_MARK = "> **SUPERSEDED — do not use the files attached to this release.**"
SUPERSEDE_BANNER = f"""{SUPERSEDE_MARK}
> They are kept only so that anything already published from them stays checkable, and the
> body below is left exactly as it was written: it was true for this release and it is not
> true now. For the current rows, the current figures and the current file list, use the
> three surfaces that are regenerated together — the repo's `data/` directory, the site at
> {HOMEPAGE} , and the citable archive at https://doi.org/{CONCEPT_DOI} (a concept DOI, so
> it always resolves to the newest version).

---

"""


def stale_releases(rels):
    """Releases whose body states a superseded headline and carries no banner yet.

    Only a release that actually makes a stale claim is touched. A clean release is left
    alone rather than banner-stamped for tidiness, because the banner is a correction and
    a correction on something that was never wrong is noise.
    """
    out = []
    for r in rels:
        body = r.get("body") or ""
        if SUPERSEDE_MARK in body:
            continue
        if any(s in body for s in SUPERSEDED):
            out.append(r)
    return out


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

    missing = [w for w in SEARCH_WORDS if w not in desc.lower()]
    if missing:
        sys.exit(f"FAIL: description omits search words {missing} — GitHub's default "
                 f"repo search matches description, not topics")

    token = envfile.load().get("GITHUB_CLASSIC_PAT")
    if not token:
        sys.exit("FAIL: GITHUB_CLASSIC_PAT missing from .env")

    # Releases are read in dry-run too. The whole reason this surface rotted for two days
    # is that nothing ever looked at it, so looking must not be gated behind --write.
    rels = api(f"repos/{REPO}/releases", token)
    stale = stale_releases(rels)
    print(f"\nreleases   : {len(rels)} total, {len(stale)} stating a superseded headline")
    for r in stale:
        hits = [s for s in SUPERSEDED if s in (r.get("body") or "")]
        print(f"  {r['tag_name']}: {hits} -> would prepend the SUPERSEDED banner")

    if "--write" not in sys.argv:
        print("\n(dry run — pass --write to apply)")
        return

    for r in stale:
        api(f"repos/{REPO}/releases/{r['id']}", token, "PATCH",
            {"body": SUPERSEDE_BANNER + (r.get("body") or "")})

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

    # Re-read the releases from the API rather than trusting the PATCH responses: the
    # banner is the correction, and a correction that only exists in a 200 we already
    # threw away is the "the script printed done" failure this project keeps hitting.
    live_rels = api(f"repos/{REPO}/releases", token)
    left = stale_releases(live_rels)
    if left:
        print("MISMATCH releases still unbannered:", [r["tag_name"] for r in left])
        ok = False
    for r in live_rels:
        if SUPERSEDE_MARK in (r.get("body") or ""):
            print(f"VERIFIED release {r['tag_name']}: SUPERSEDED banner live")

    if not ok:
        sys.exit("FAIL: live repo does not match what was sent")
    print("\nVERIFIED live:", live["description"])
    print("VERIFIED topics:", ", ".join(sorted(live_topics)))


if __name__ == "__main__":
    main()
