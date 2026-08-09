# Correction, 2026-08-09: the same 27 products were filed in 194 of 261 categories

**Everything below was found in this repository's own published data, by grouping
`gumroad-taxonomy.csv` on `url` and counting distinct `node`. Anyone who downloaded the
file could have run it, and it is published here rather than quietly restated because the
finding is worth more than the 5,238 rows it removes.**

## What was wrong

`data/gumroad-taxonomy.csv` recorded **27 products as members of 194 of its 261 non-empty
categories** — 5,238 listing observations, **34.7% of the file**. A Notion productivity
template (`productivesetups/headquarters`) was filed under
`3D > 3D Assets > Accessories > Jewelry`, and so were a tendon-training PDF, a raw vegan
recipe book and a keyboard library for iOS.

They were never category members. The crawler
(`scripts/collect_taxonomy.py`) reads every product card in the page after clicking
"load more", and Gumroad renders a **recommendations module below the category grid** out
of the same markup as a category result. That module is the same on every category page.

## The evidence that this is the right cut, and not a plausible one

Row order settles it. In the **raw** crawl, per node, the block appears as a contiguous run
at the very end — and the length of that run has no middle:

| block rows at the end of a node | number of nodes |
|---|---|
| 0 | 165 |
| 27 | 194 |
| anything else | **0** |

Not one node in 359 carries 3, or 14, or 26. That is a fixed-size module appended to a
page, not a category membership. Checked against the live endpoint the same night, none of
the 27 appears in `?taxonomy=3d/3d-assets/accessories/jewelry`'s server-rendered results.

## The rule now applied, in `scripts/normalize_taxonomy.py`

A product observed in **≥ 33% of the crawled nodes** is the module, not a member
(`block_urls`). Only its **contiguous run at the end of a node's raw row list** is removed
(`strip_block_tail`). The threshold is a share and not a count so it survives a crawl of a
different size, and it sits far above honest cross-listing: **the 99th percentile of real
products is 4 nodes; the block sits at 194.**

The removal is deliberately narrower than the detection, and that matters. `mimiiu/l/ARYIA`
is a VRChat avatar that appears in node `3D` twice — at raw index 3, in the grid, and again
at index 54, in the module. Deleting the URL wholesale would have deleted a true row.
**24 of the 27 keep at least one genuine observation.** The remaining 3 were never seen
outside the module, so this crawl has no evidence of what category they belong to and they
leave the dataset rather than be guessed at.

## What changed, and what did not

| figure | published | corrected |
|---|---|---|
| listing observations | 15,077 | **9,878** |
| distinct products | 8,325 | **8,322** |
| distinct sellers | 4,545 | **4,543** |
| non-empty nodes | 261 | **261** |
| listings with a disclosed unit-sales count | 316 | **316** |
| paid median price | $18.03 | **$18.03** |
| effective per-node crawl cap | 71 | **44** |
| most categories one seller appears in | 194 | **21** |

Two of those deserve saying out loud.

**The per-node cap was never 71.** 192 nodes came back at exactly 71 cards, 27 of which
were the module, so the real sample is **44 listings a node and 191 of 261 nodes sit on
it**. Every per-node figure in this dataset describes the listings Gumroad ranks first in a
category, and that ceiling is lower than previously stated.

**"One seller listed in 194 categories" was the module, not a seller.** The real maximum is
21. Any breadth-of-catalogue reading taken from the old figure was reading the widget.

Per-branch counts were inflated by exactly 27 listings and up to 27 sellers, so thin
branches moved most: **Comics & Graphic Novels** was 71 listings of which 27 were the
module, and its p90 price read **$133.19 against a corrected $45.06**. 3D and Design moved
under 2%.

## What survives

Rank statistics do not move when the same 27 rows are removed from both sides of a
comparison, so the orderings this dataset is used for are unchanged: Design is still the
highest free share of any branch (11.37% → 11.53%), Business & Money is still barely more
than one product per seller (1.20 → 1.21), and a listing priced above 91% of its branch is
still priced above 91% of it.

## The reasoning error, named

`normalize_taxonomy.py` used to justify multi-node rows like this:

> *A product that Gumroad files under three nodes produces three rows, which is data rather
> than noise — being classified broadly is itself a property of a product.*

True of a product Gumroad **files** under three nodes. False of a product a recommendations
widget **printed** under 194. The normaliser had no way to tell those apart because it never
looked at row order, and it did not know it needed to.

## Reproducing it

    python3 scripts/normalize_taxonomy.py     # applies the rule, prints the tail histogram

The detector that found it lives in the operator repository as
`scripts/taxonomy_contamination.py`; it reads the published CSV and exits non-zero on a
contaminated file.
