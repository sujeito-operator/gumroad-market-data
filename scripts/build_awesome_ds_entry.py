#!/usr/bin/env python3
"""Generate the `academic/awesome-datascience` Datasets bullet for this dataset.

WHY THIS EXISTS. That list is 29,775 stars, its default branch is `live`, and it
MERGES: 8 of its last 15 closed PRs, the most recent closed the day before this was
written. Its Datasets section already carries several entries of exactly our shape —
an independently published niche dataset, CSVs plus a data dictionary, CC BY, a Zenodo
DOI (`College ROI Dataset`, `State of Peptides 2026`, `Verified Supplement Evidence`).
Both recent *rejections* were rejected for one reason only: the author did not fill in
the pull request template. So the entry is cheap and the merge is plausible.

The bullet is generated rather than typed for the same reason every other surface is:
the headline figures have already moved twice, and a stale figure on someone else's
77k-reader list is worse than one on ours. It reads the same summaries as `build_site`
and asserts that no superseded count and no version DOI can reach the output.

    python3 scripts/build_awesome_ds_entry.py                  # print the bullet
    python3 scripts/build_awesome_ds_entry.py --insert PATH     # splice into a README
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_site  # noqa: E402  — SITE, DOI: one source of truth

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The bullet goes immediately after this line, which is the last of the cluster of
# recently added independent datasets. Matched on a substring so a maintainer's
# reformatting of the rest of the line does not silently move our entry to the wrong
# place — if the anchor is gone the script fails instead of guessing.
ANCHOR = "Packrift Packaging Optimization Benchmark Corpus"

NAME = "Gumroad Digital Product Market Data"


def load(name):
    return json.loads((ROOT / "data" / name).read_text())


def bullet():
    ts = load("taxonomy-summary.json")
    sr = load("sales-ratio-summary.json")
    return (
        f"- [{NAME}]({build_site.SITE}/) - "
        f"Marketplace snapshot of {ts['n']:,} Gumroad digital products from "
        f"{ts['sellers']:,} sellers across {ts['nodes']} categories, with asking price, "
        f"currency and rating count, plus publisher-disclosed unit sales for "
        f"{sr['disclosing']} listings ({sr['units_observed']:,} units). Four CSVs with "
        f"data dictionaries, CC BY 4.0, Zenodo DOI."
    )


def main():
    line = bullet()

    # Two figures that must never come back. 1,511 was withdrawn as a count (it was
    # listing observations, not distinct products); ...104 is the v1 version DOI on a
    # deposit whose currency handling was wrong. Only the concept DOI is ever citable.
    assert "1,511" not in line, "the withdrawn 1,511 count is back in the entry"
    assert "21830104" not in line, "version DOI v1 is back in the entry"
    assert "1,344" not in line, "the first sample's count is not the headline any more"
    # House style for this list: one sentence per idea, no superlatives, no pricing.
    for banned in ("best", "biggest", "largest", "$79", "buy", "premium"):
        assert banned not in line.lower(), f"marketing language in the entry: {banned}"
    assert len(line) < 400, f"entry is {len(line)} chars; the section's longest is ~380"

    if "--insert" in sys.argv:
        target = pathlib.Path(sys.argv[sys.argv.index("--insert") + 1])
        text = target.read_text()
        assert line not in text, "entry is already in that README"
        hits = [i for i, l in enumerate(text.split("\n")) if ANCHOR in l]
        assert len(hits) == 1, f"anchor matched {len(hits)} lines, expected exactly 1"
        lines = text.split("\n")
        lines.insert(hits[0] + 1, line)
        out = "\n".join(lines)
        # One line added, nothing else touched: the diff a reviewer wants to see.
        assert out.count("\n") == text.count("\n") + 1
        target.write_text(out)
        print(f"inserted after line {hits[0] + 1} of {target}")
    else:
        print(line)


if __name__ == "__main__":
    main()
