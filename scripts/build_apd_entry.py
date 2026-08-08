#!/usr/bin/env python3
"""Generate the awesomedata/apd-core catalogue entry for this dataset.

WHY THIS EXISTS. `awesomedata/apd-core` is the data repo behind awesome-public-datasets,
and it MERGES — 13 of its last 15 closed PRs, six in the last fortnight. (An earlier
session checked the *parent* `awesome-public-datasets` repo, saw 0 of 15 merged, and
closed the channel on the wrong evidence. They are different repos.) Our PR #553 has
been open there since 2026-08-06, unreviewed rather than rejected.

The entry it carries was hand-written when the 42-search sample was the whole dataset,
and it had rotted in two ways that matter on someone else's repository:

  * it cited the VERSION DOI 10.5281/zenodo.21830104 — the v1 deposit, the one with the
    mixed-currency error and the withdrawn 1,511 count, which this project's own notes
    say never to cite. The concept DOI is the only one that should ever appear.
  * it still advertised "1,511 rows" in the sources block, two correction comments later.

So it is generated now, from the same summaries every other surface reads.

    python3 scripts/build_apd_entry.py            # print
    python3 scripts/build_apd_entry.py --write ../apd-core/core/Economics/...yml
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_site  # noqa: E402  — DOI, REPO, RAW, SITE: one source of truth

ROOT = pathlib.Path(__file__).resolve().parent.parent
METHOD = f"{build_site.REPO}#method-and-what-this-cannot-tell-you"


def load(name):
    return json.loads((ROOT / "data" / name).read_text())


def description(s, ts, sr, ss):
    """One paragraph. Every figure interpolated; the caveats are not optional.

    apd-core entries are read by people deciding whether to spend an hour on a file, so
    the limits go in the same paragraph as the headline rather than behind a link.
    """
    return (
        f"A measured snapshot of the Gumroad digital-product long tail, collected from "
        f"public listing pages in August 2026 with no login and nothing behind "
        f"authentication. Four tables. (1) A category walk covering {ts['n']:,} distinct products "
        f"from {ts['sellers']:,} sellers across {ts['nodes']} categories, in "
        f"{ts['obs']:,} listing observations. (2) An independent sample of {s['n']:,} "
        f"products across {s['cats']} category searches, kept separate because the two "
        f"disagree — median paid price ${ts['med']} against ${s['med']}, and that gap is "
        f"itself the finding about how much a 'typical price' depends on how you looked. "
        f"(3) A seller table, all {ss['sellers']:,} sellers, with catalogue size, category "
        f"breadth and rating totals. (4) A unit-sales subsample — of {sr['fetched']} product "
        f"pages fetched, {sr['disclosing']} ({sr['disclose_pct']}%) publish a real sales "
        f"count, covering {sr['units_observed']:,} units — which lets the rating-count "
        f"demand proxy every study like this relies on be checked against actual sales for "
        f"once (Spearman {sr['spearman_all']}). Rows carry category, asking price, currency, "
        f"rating count, subscription flag and title; prices are normalised to USD at ECB "
        f"reference rates with the original price and currency both retained. "
        f"LIMITS, stated because they change what the file can answer. A seller's product "
        f"count is what the crawl found three pages deep per category, a lower bound rather "
        f"than a catalogue; a category's listing count is a crawl depth, not a category size "
        f"({ts['nodes_at_cap']} of {ts['nodes']} nodes hit the {ts['cap']}-listing cap); and "
        f"the sales-per-rating medians are a lower bound, since the {sr['unrated_n']} "
        f"listings with sales and no ratings are undefined for the ratio and excluded. "
        f"Useful for creator-economy research, digital-goods pricing and long-tail "
        f"marketplace studies. All four CSVs, the summary JSONs and the collector source "
        f"are in the repository, with no login and no paywall."
    )


def entry(s, ts, sr, ss):
    doi_url = f"https://doi.org/{build_site.DOI}"
    return f"""---
title: Gumroad Digital Product Demand - {ts['n']:,} products, {ts['sellers']:,} sellers, {sr['disclosing']} with real unit sales
homepage: {build_site.REPO}
category: Economics
description: {description(s, ts, sr, ss)}
version: {build_site.ZENODO_VERSION}
keywords: creator economy, digital products, e-commerce, marketplace, gumroad, pricing, demand, long tail, unit sales, csv, open data
image:
temporal: {ss['temporal_coverage']} snapshot
spatial: global
access_level: public
copyrights:
accrual_periodicity: irregular
specification: {METHOD}
data_quality: true
data_dictionary: {METHOD}
language: en
license: CC-BY-4.0
publisher:
  - name: Operator
    web: https://github.com/sujeito-operator
organization:
issued_time: 2026.08
sources:
  - name: Archived deposit with DOI (Zenodo, CC BY 4.0) - concept DOI, always resolves to the current version
    access_url: {doi_url}
  - name: Category walk ({ts['n']:,} products, {ts['sellers']:,} sellers, CSV)
    access_url: {build_site.RAW}/data/gumroad-taxonomy.csv
  - name: Seller table (all {ss['sellers']:,} sellers, CSV)
    access_url: {build_site.RAW}/data/gumroad-sellers.csv
  - name: Unit-sales subsample ({sr['disclosing']} listings publishing real sales, CSV)
    access_url: {build_site.RAW}/data/gumroad-sales.csv
  - name: Search sample ({s['n']:,} products across {s['cats']} categories, CSV)
    access_url: {build_site.RAW}/data/gumroad-latest.csv
  - name: Per-category summary (JSON)
    access_url: {build_site.RAW}/data/summary.json
  - name: 50-row raw sample
    access_url: {build_site.RAW}/docs/sample-50-rows.csv
references:
  - title: Citable archive (concept DOI {build_site.DOI})
    reference: {doi_url}
  - title: Collection method and stated limits
    reference: {METHOD}
  - title: Derived pages, with the working shown
    reference: {build_site.SITE}/
  - title: Collector source
    reference: {build_site.REPO}/blob/main/scripts/collect.py
"""


def main():
    s, ts, sr, ss = (load("summary.json"), load("taxonomy-summary.json"),
                     load("sales-ratio-summary.json"), load("sellers-summary.json"))
    text = entry(s, ts, sr, ss)

    # The three defects this file exists to stop coming back.
    assert "21830104" not in text, "version DOI v1 is back in the entry — cite the concept DOI"
    assert "1,511" not in text, "the withdrawn 1,511 count is back in the entry"
    assert build_site.DOI in text
    # The third: this entry publishes a `version:` field to a third-party catalogue, and it
    # sat at 2.3 through v2.4/2.5/2.6/2.7 because it was typed here instead of derived.
    build_site.assert_zenodo_version_current()

    # apd-core entries use plain YAML scalars, so a ": " anywhere in the prose silently
    # ends the scalar and the whole file stops parsing. Caught here rather than by a
    # maintainer, which is the difference between a merge and a closed PR.
    import yaml
    doc = yaml.safe_load(text)
    assert ": " not in doc["description"], "a colon in the description will break the scalar"
    for key in ("title", "homepage", "description", "license", "sources", "references"):
        assert doc.get(key), f"{key} is empty in the generated entry"

    if "--write" in sys.argv:
        dest = pathlib.Path(sys.argv[sys.argv.index("--write") + 1])
        dest.write_text(text)
        print(f"wrote {dest} ({len(text):,} bytes)")
    else:
        print(text)


if __name__ == "__main__":
    main()
