#!/usr/bin/env python3
"""Generate the `eferrares/awesome-startup-resources` Market Research bullet.

WHY THIS LIST. Chosen on merge evidence before anything was submitted, by the method
in `merge_rate.py`: it merges 10 of its last 15 closed PRs, and all five of the
"rejections" in that window carry the same maintainer comment — *"conteúdo aplicado
manualmente em 3cae736 (conflito de merge)"*, i.e. the content was accepted and applied
by hand, the PR was merely closed. So the real acceptance rate in that window is 15/15,
and the whole batch was worked on 2026-08-02, five days before this was written.

WHY THE FIT IS REAL. Its `## Market Research` section already carries an entry of
exactly our shape — *WP Goldmine: "finds abandoned or unsupported plugins that still
have large active-install bases, surfacing product gaps you could rebuild and capture"*
— which is the same job our snapshot does for Gumroad. The section is not free-only
(Statista, SimilarWeb, Compass sit in it), so a page with a paid report further down is
in keeping; the PR discloses that CTA anyway and offers to repoint the link.

CONTRIBUTING asks for three things and this satisfies all three: a short description,
placement in the most relevant existing category, and a live, actively maintained
resource.

Generated rather than typed because the headline figures have already moved twice and a
stale figure on someone else's list is worse than one on ours.

    python3 scripts/build_startup_resources_entry.py                 # print the bullet
    python3 scripts/build_startup_resources_entry.py --insert PATH   # splice into README
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_site  # noqa: E402  — SITE, DOI: one source of truth

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Last line of the `## Market Research` section. Matched on a substring so that a
# maintainer reformatting the rest of the line does not silently move our entry into a
# different section — if the anchor is gone the script fails rather than guessing.
ANCHOR = "[EnrichAnything]"

NAME = "Gumroad Market Data"


def load(name):
    return json.loads((ROOT / "data" / name).read_text())


def bullet():
    ts = load("taxonomy-summary.json")
    sr = load("sales-ratio-summary.json")
    return (
        f"- [{NAME}]({build_site.SITE}/) — Free CSVs covering {ts['n']:,} Gumroad "
        f"digital products from {ts['sellers']:,} sellers across {ts['nodes']} "
        f"categories: asking price, rating count, and publisher-disclosed unit sales "
        f"for {sr['disclosing']} listings. For sizing demand and pricing before you "
        f"build. CC BY 4.0, Zenodo DOI."
    )


def main():
    line = bullet()

    # Figures that must never come back. 1,511 was withdrawn as a count (listing
    # observations, not distinct products); ...104 is the v1 version DOI, on a deposit
    # whose currency handling was wrong. Only the concept DOI is ever citable.
    assert "1,511" not in line, "the withdrawn 1,511 count is back in the entry"
    assert "21830104" not in line, "version DOI v1 is back in the entry"
    assert "1,344" not in line, "the first sample's count is not the headline any more"
    # House style for this section: one plain sentence of what it is, no superlatives,
    # no pricing. The $79 belongs in the PR body as a disclosure, not in the list.
    for banned in ("best", "biggest", "largest", "$79", "buy now", "premium"):
        assert banned not in line.lower(), f"marketing language in the entry: {banned}"
    # The section's longest existing line (WP Goldmine) is ~230 chars.
    assert len(line) < 340, f"entry is {len(line)} chars; the section's longest is ~230"
    assert line.startswith("- ["), "section style is a plain markdown link bullet"

    if "--insert" in sys.argv:
        target = pathlib.Path(sys.argv[sys.argv.index("--insert") + 1])
        text = target.read_text()
        assert line not in text, "entry is already in that README"
        lines = text.split("\n")
        hits = [i for i, l in enumerate(lines) if ANCHOR in l]
        assert len(hits) == 1, f"anchor matched {len(hits)} lines, expected exactly 1"
        # Belt and braces: confirm the anchor really sits under Market Research and not
        # under some later section a maintainer moved it to.
        heads = [i for i, l in enumerate(lines) if l.startswith("#")]
        head = max(i for i in heads if i < hits[0])
        assert "Market Research" in lines[head], (
            f"anchor is now under {lines[head]!r}, not Market Research"
        )
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
