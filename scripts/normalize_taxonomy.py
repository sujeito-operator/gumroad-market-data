#!/usr/bin/env python3
"""Turn the raw taxonomy crawl into a published CSV and a per-node summary.

WHY THIS EXISTS, AND WHY IT DOES NOT REPLACE normalize.py
---------------------------------------------------------
`normalize.py` normalises the ORIGINAL sample: 42 hand-picked Discover searches, one
page deep, 1,344 distinct products. That sample is published, DOI-archived and cited by
every existing page, so it is not rewritten here.

This file normalises the SECOND sample, collected by `collect_taxonomy.py`, whose frame
is **Gumroad's own published category tree** rather than 42 terms somebody thought of:
359 nodes, up to three pages deep each. It is 6.2x larger by distinct product and it
carries two columns the first sample never had — `url` and `seller`.

`url` matters beyond size. The original dedup key is the rendered card text, which
`normalize.py`'s own docstring concedes is a proxy: two genuinely different products
with the same title and price collapse under it. `url` is Gumroad's identity key, so
the 8,325 figure here is an exact count, not an estimate.

WHAT A ROW IS, AND THE CAP THAT GOVERNS EVERY PER-NODE FIGURE
--------------------------------------------------------------
A row is a **listing observation**: one product under one taxonomy node. A product that
Gumroad *files* under three nodes produces three rows, which is data rather than noise —
being classified broadly is itself a property of a product. Every market-wide figure
therefore counts DISTINCT URLS; only per-node figures count observations.

**THAT SENTENCE USED TO STOP AT "files under three nodes", AND IT IS WHY 5,238 BAD ROWS
GOT PUBLISHED.** It is true of a product Gumroad *files* under three nodes and false of a
product a recommendations widget *printed* under 194, and this file had no way to tell
those apart because it never looked at row ORDER. It does now — see the next section. Any
future reader tempted to treat "appears under many nodes" as a property of the product
should read `data/taxonomy-correction-2026-08-09.md` first.

THE RECOMMENDATIONS STRIP, AND THE ORDER THAT PROVES IT
-------------------------------------------------------
`collect_taxonomy.parse_cards()` takes every product card in the DOM after `load_more()`,
and the "you might also like" module *below* the grid is made of product cards. It is the
same module on every page, so the same 27 products were recorded as members of 194 of the
261 non-empty nodes: 5,238 observations, **34.7% of the raw file**, including a Notion
productivity template filed under `3D > 3D Assets > Accessories > Jewelry`.

`block_urls()` names them — a product observed in >= `BLOCK_SHARE` of the crawled nodes is
furniture, not a member. It is a *share* and not a count so it survives a crawl of a
different size, and it sits far above honest cross-listing: the 99th percentile of real
products is 4 nodes and the block sits at 194.

`strip_block_tail()` is what actually removes them, and it is deliberately narrower than
the detector. It drops only the **contiguous run of block products at the END of a node's
raw row list**, because that is the module's position in the DOM, and the evidence that
this is the right cut is that the per-node tail length has no middle: **165 nodes carry 0
and 194 carry exactly 27.** Nothing in between, in any node.

The narrowness matters and it is not cosmetic. `mimiiu/l/ARYIA` is a VRChat avatar; in
node `3D`'s raw rows it sits at index 3 *and* again at index 54. Index 3 is the grid —
a real membership — and index 54 is the strip. Dropping the URL wholesale would have
deleted a true row; dropping the tail keeps it. **24 of the 27 keep at least one genuine
observation this way.** The other 3 were never seen outside the strip, so the crawl has no
evidence of what category they are in and they leave the file rather than be guessed at.

STRIPPING HAPPENS BEFORE THE WITHIN-NODE DEDUP, WHICH IS THE ONLY ORDER THAT WORKS.
The dedup keeps the first observation, so on the deduped list `ARYIA`'s strip copy is
already gone and node `3D`'s tail reads 26 long instead of 27 — the tail stops being a
clean signal. On raw rows every affected node reads exactly 27.

**The per-node sample is capped by the crawl, not by the category.** The collector took
up to three pages per node and 192 of the 261 non-empty nodes came back at exactly 71
cards. **27 of those 71 were the recommendations module, so the real cap is 44 listings a
node and 191 of the 261 nodes sit on it** — the published `cap`/`nodes_at_cap` read 71/166
before the correction and 44/191 after. So a node's figures describe *the listings Gumroad ranks
first in that category*, not its full population. That is a real limitation and it is
stated on every generated page: it makes nodes comparable to each other and it does not
support any claim about category size. Never publish a per-node count as "how many
products are in this category".

THE SECOND CONTAMINATION, AND IT IS A WHOLE NODE RATHER THAN A STRIP
---------------------------------------------------------------------
The strip rule above removes the "you might also like" module from the BOTTOM of a page.
It cannot see a page that is nothing BUT recommendations, and there were six of those.

`https://gumroad.com/discover?taxonomy=<slug>` does not 404 on a slug it does not know.
**It silently serves the default discover feed.** Measured 2026-08-11, plain HTTP:

    ?taxonomy=fiction-books/children-s-books        -> 36 permalinks
    ?taxonomy=3d/3d-assets/3ds-max                  -> the SAME 36, in the same order
    ?taxonomy=zzz-not-a-real-category-xyz           -> the SAME 36, in the same order
    ?taxonomy=design/graphics/assets-and-templates  -> a different 36  (a node it knows)

The tree is read out of the category picker on a product's EDIT page, and that tree is
not the same tree `discover` routes on. Six nodes in it are unknown to `discover`, so
what got recorded as their listings is the site-wide feed. `Fiction Books > Children's
Books` was published with a $32.05 median and a $134.85 90th percentile computed from a
NinjaTrader indicator, a peptide book and a sales-funnel course. Not one children's book.

**A node is dropped only when two independent witnesses agree**, because a live feed that
rotates must never be able to delete a real category on its own:

  1. LIVE — `scripts/verify_taxonomy_nodes.py` refetches the node and finds >= 80% of it
     in a control fetch of a slug that cannot exist. Written to `data/node-verification.json`.
  2. IN THE CRAWL ITSELF — the node's grid rows end in a run shared with another dropped
     node. The feed's head rotates per request and its tail does not, so the six read a
     common suffix of exactly 36 of their 44 rows, and no other node pair shares five.

`unrecognised_nodes()` requires both and `sys.exit`s on a disagreement rather than
guessing. There is no threshold to tune: witness 1 is a positive match against a control
and witness 2 is an exact shared suffix.

98 of the 359 nodes returned zero rows. They are deep leaves, mostly under
`recorded-music/singles/*` and `films/movie/*`, and the pattern is consistent with
genuinely empty categories but has NOT been confirmed. They are excluded from
everything here rather than reported as zeroes, because "we found nothing" and "there is
nothing" are different claims and only the first one is evidenced.

CURRENCY
--------
Same trap as the first sample and worse: 14,099 of 15,119 observations are displayed in
GBP because Gumroad localises to this box's egress IP. Any median taken across the raw
`price` column mixes units. Prices are converted at the same ECB reference rates and the
same value date as `normalize.py`, so figures from the two samples are comparable, and
the raw price and its currency are both kept so the conversion can be redone.

RATINGS ARE NOT SALES. `n` is a rating count: a floor on buyers, never multiplied by an
invented review rate to manufacture revenue.

USAGE
    python scripts/normalize_taxonomy.py
"""
import collections, csv, json, pathlib, statistics as st, sys

from redact import scrub

# ECB reference rates via frankfurter, value date 2026-08-06 — the SAME date and source
# as normalize.py, so the two samples' price figures are on one scale. JPY is new here:
# the first sample contained no yen listing and normalize.py would have exited on one.
FX_DATE = "2026-08-06"
FX_SOURCE = "European Central Bank reference rates via frankfurter.dev"
TO_USD = {"$": 1.0, "£": 1 / 0.74255, "€": 1 / 0.8664, "¥": 1 / 157.83}

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw-taxonomy.jsonl"
OUT_CSV = ROOT / "data" / "gumroad-taxonomy.csv"
OUT_SUMMARY = ROOT / "data" / "taxonomy-summary.json"

FIELDS = ["node", "slug", "url", "seller", "cur", "price", "price_usd",
          "nrat", "n", "stars", "recurring", "t"]

# A product on more than a third of every category in the tree is not cross-listed, it is
# furniture. Kept identical to scripts/taxonomy_contamination.py's SHARE in the operator
# repo, which is the detector that has to agree with this file.
BLOCK_SHARE = 0.33


def block_urls(records, share=BLOCK_SHARE):
    """-> the set of product URLs observed in >= `share` of the crawled non-empty nodes.

    Counted on DISTINCT nodes, so a product listed twice inside one node still counts once
    toward its own node total and cannot inflate itself into the block.
    """
    nodes = {d["node"] for d in records if d.get("rows")}
    if not nodes:
        return set()
    seen = collections.defaultdict(set)
    for d in records:
        for u in {r["url"] for r in d.get("rows") or []}:
            seen[u].add(d["node"])
    floor = share * len(nodes)
    return {u for u, nd in seen.items() if len(nd) >= floor}


# The live half of the two-witness rule. Produced by scripts/verify_taxonomy_nodes.py.
VERIFICATION = ROOT / "data" / "node-verification.json"

# Witness 2. The default feed's tail is stable across requests while its head rotates, so
# two nodes that are both the feed share a long ordered SUFFIX. Measured: the six share 36
# of 44 and no other pair in 261 nodes shares as many as 5. Anywhere in 5..36 gives the
# same answer, which is the point — it is a gap, not a knob.
SUFFIX_WITNESS = 5


def common_suffix(a, b):
    """-> how many trailing items `a` and `b` share."""
    n = 0
    while n < len(a) and n < len(b) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def unrecognised_nodes(grids, verdicts, suffix=SUFFIX_WITNESS):
    """-> the set of nodes that are the default discover feed wearing a category's name.

    `grids`    {node: [url, ...]} AFTER the tail strip, in crawl order.
    `verdicts` {node: "default_feed" | "real" | "empty" | "error"} from the live refetch.

    Both witnesses are required. A node the live check accuses but the crawl does not
    corroborate is an ERROR, not a judgement call: it means the feed has rotated into
    something this rule cannot read, and the safe move is to stop rather than to delete a
    category on one witness. The reverse — corroborated in the crawl, live says real — is
    the same stop, because it means a node that WAS the feed is now a category, and the
    published rows still came from the feed.
    """
    live = {n for n, v in verdicts.items() if v == "default_feed"}
    corroborated = set()
    for a in grids:
        for b in grids:
            if a != b and common_suffix(grids[a], grids[b]) >= suffix:
                corroborated.add(a)
                break
    if live != corroborated:
        only_live = sorted(live - corroborated)
        only_crawl = sorted(corroborated - live)
        sys.exit(
            "the two witnesses disagree and neither one may drop a node alone.\n"
            f"  live-only (refetch says default feed, crawl does not corroborate): {only_live}\n"
            f"  crawl-only (crawl corroborates, refetch says it is a real node): {only_crawl}\n"
            "  re-run scripts/verify_taxonomy_nodes.py and read both before publishing.")
    return live


def strip_block_tail(rows, bad):
    """-> (rows without the trailing recommendations module, how many were dropped).

    Only the contiguous run of block products at the END is removed. A block product
    sitting anywhere earlier is in the grid and is a real observation; see the module
    docstring for the `ARYIA` case that this distinction exists to protect.
    """
    i = len(rows)
    while i and rows[i - 1]["url"] in bad:
        i -= 1
    return rows[:i], len(rows) - i


def pctile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    return round(sorted_vals[min(int(q * len(sorted_vals)), len(sorted_vals) - 1)], 2)


def load():
    """One record per (node, product). Exact duplicates within a node are a crawl
    artifact — the same card seen on page 1 and again after 'Load more' — and dropped."""
    records = [json.loads(line) for line in RAW.open()]
    bad = block_urls(records)

    # The tail strip first, because the whole-node rule reads the GRID's suffix and the
    # recommendations module would otherwise be the suffix every node shares.
    grids = {}
    for d in records:
        rows, _ = strip_block_tail(d.get("rows") or [], bad)
        if rows:
            grids[d["node"]] = [r["url"] for r in rows]

    if not VERIFICATION.exists():
        sys.exit(f"{VERIFICATION} is missing. Six nodes in this crawl are the default "
                 "discover feed rather than a category, and without the live half of the "
                 "two-witness rule this file would publish them again. Run:\n"
                 "  python3 scripts/verify_taxonomy_nodes.py --out data/node-verification.json")
    ver = json.loads(VERIFICATION.read_text())
    unreal = unrecognised_nodes(grids, {r["node"]: r["verdict"] for r in ver["nodes"]})

    obs, empty, stripped, tails = [], [], 0, collections.Counter()
    for d in records:
        if d["node"] in unreal:
            continue
        rows = d.get("rows") or []
        rows, n_tail = strip_block_tail(rows, bad)
        stripped += n_tail
        if n_tail or any(r["url"] in bad for r in rows):
            tails[n_tail] += 1
        if not rows:
            # A node the crawl returned nothing for and a node the strip emptied are
            # different claims. Only the first is an `empty` node.
            if n_tail:
                sys.exit(f"{d['node']!r} is nothing but the recommendations module "
                         f"({n_tail} rows) — the strip rule is wrong or the crawl is")
            empty.append(d["slug"])
            continue
        seen = set()
        for r in rows:
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            if r["cur"] not in TO_USD:
                sys.exit(f"unknown currency {r['cur']!r} — add a rate before publishing")
            obs.append({
                "node": d["node"], "slug": d["slug"], "url": r["url"],
                "seller": r["seller"], "cur": r["cur"], "price": round(r["price"], 2),
                "price_usd": round(r["price"] * TO_USD[r["cur"]], 2),
                "nrat": r.get("nrat") or "", "n": int(r.get("n") or 0),
                "stars": r.get("stars") if r.get("stars") is not None else "",
                "recurring": bool(r.get("recurring")), "t": scrub(r["t"].strip()),
            })
    return obs, empty, {"block": sorted(bad), "rows_removed": stripped,
                        "tail_lengths": dict(sorted(tails.items())),
                        "unrecognised": sorted(unreal),
                        "unrecognised_slugs": {d["node"]: d["slug"] for d in records
                                               if d["node"] in unreal},
                        "unrecognised_rows": sum(len(grids[n]) for n in unreal),
                        "verification_checked": ver.get("checked")}


def distinct(obs):
    """One record per product, first observation wins. Every market-wide figure."""
    seen, out = set(), []
    for r in obs:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        out.append(r)
    return out


def node_stats(obs):
    nodes = []
    by = collections.defaultdict(list)
    for r in obs:
        by[(r["slug"], r["node"])].append(r)
    for (slug, node), g in by.items():
        prices = sorted(r["price_usd"] for r in g if r["price_usd"] > 0)
        rated = [r for r in g if r["n"] > 0]
        ratings = sorted((r["n"] for r in g), reverse=True)
        total = sum(ratings)
        k = max(1, round(len(ratings) * 0.1))
        nodes.append({
            "slug": slug,
            "node": node,
            "depth": slug.count("/"),
            "n": len(g),
            "sellers": len({r["seller"] for r in g}),
            "median": pctile(prices, .5),
            "p25": pctile(prices, .25),
            "p75": pctile(prices, .75),
            "p90": pctile(prices, .9),
            "free": sum(1 for r in g if r["price_usd"] == 0),
            "subs": sum(1 for r in g if r["recurring"]),
            "rated_share": round(100 * len(rated) / len(g)),
            "med_ratings": int(st.median([r["n"] for r in rated])) if rated else 0,
            "top_n": int(ratings[0]) if ratings else 0,
            "ratings_total": int(total),
            "top10_share": round(100 * sum(ratings[:k]) / total, 1) if total else 0.0,
            "currencies": sorted({r["cur"] for r in g}),
        })
    nodes.sort(key=lambda x: (x["rated_share"], x["med_ratings"]), reverse=True)
    return nodes


def summarise(obs, nodes, empty, strip=None):
    prod = distinct(obs)
    prices = sorted(r["price_usd"] for r in prod if r["price_usd"] > 0)
    ratings = sorted((r["n"] for r in prod), reverse=True)
    total = sum(ratings)
    rated_only = [x for x in ratings if x > 0]
    zero = sum(1 for r in prod if r["n"] == 0)

    def share(p):
        k = max(1, round(len(ratings) * p / 100))
        return round(100 * sum(ratings[:k]) / total, 1) if total else 0.0

    # Seller-level concentration. The first sample could not answer this at all: it
    # never recorded who was selling. This is the differentiator, so it is computed
    # explicitly rather than left for a reader to derive.
    per_seller = collections.Counter(r["seller"] for r in prod)
    seller_ratings = collections.Counter()
    for r in prod:
        seller_ratings[r["seller"]] += r["n"]
    sr = sorted(seller_ratings.values(), reverse=True)
    sr_total = sum(sr)
    listings_sorted = sorted(per_seller.values(), reverse=True)

    def seller_share(p):
        k = max(1, round(len(sr) * p / 100))
        return round(100 * sum(sr[:k]) / sr_total, 1) if sr_total else 0.0

    return {
        "n": len(prod),
        "obs": len(obs),
        "multi": len(obs) - len(prod),
        "nodes": len(nodes),
        "nodes_empty": len(empty),
        # `nodes_crawled` is what SURVIVED, and it used to equal the frame because nothing
        # was ever discarded for a third reason. Six now are, so the frame is carried
        # separately: a node that leaves the sample must leave a hole a reader can see,
        # not shrink the denominator and disappear.
        "nodes_crawled": len(nodes) + len(empty),
        "nodes_frame": len(nodes) + len(empty) + len((strip or {}).get("unrecognised", [])),
        "nodes_unrecognised": len((strip or {}).get("unrecognised", [])),
        "sellers": len(per_seller),
        "zero": zero,
        "zpct": round(100 * zero / len(prod)),
        "med": pctile(prices, .5),
        "med_all": round(st.median(sorted(r["price_usd"] for r in prod)), 2),
        "p25": pctile(prices, .25),
        "p75": pctile(prices, .75),
        "p90": pctile(prices, .9),
        "free": sum(1 for r in prod if r["price_usd"] == 0),
        "subs": sum(1 for r in prod if r["recurring"]),
        "ratings_total": int(total),
        "med_ratings_all": int(st.median(ratings)) if ratings else 0,
        "med_ratings_rated": int(st.median(rated_only)) if rated_only else 0,
        "top1_share": share(1),
        "top5_share": share(5),
        "top10_share": share(10),
        "top_product_ratings": int(ratings[0]) if ratings else 0,
        # Seller concentration
        "seller_top1_share": seller_share(1),
        "seller_top5_share": seller_share(5),
        "seller_top10_share": seller_share(10),
        "sellers_one_product": sum(1 for v in listings_sorted if v == 1),
        "seller_max_products": listings_sorted[0] if listings_sorted else 0,
        "med_products_per_seller": int(st.median(listings_sorted)) if listings_sorted else 0,
        "cap": max((x["n"] for x in nodes), default=0),
        "nodes_at_cap": sum(1 for x in nodes if x["n"] == max((y["n"] for y in nodes), default=0)),
        "currency": "USD",
        "fx_date": FX_DATE,
        "fx_source": FX_SOURCE,
        "fx_rates_to_usd": {k: round(v, 5) for k, v in TO_USD.items()},
        "empty_nodes": sorted(empty),
        # The correction, carried in the summary so that every one of the 44 files that
        # reads this JSON can state it rather than have to rediscover it.
        "block_correction": {
            "rule": f"a product observed in >= {BLOCK_SHARE:.0%} of crawled nodes is the "
                    "recommendations module, and only its contiguous run at the end of a "
                    "node's raw rows is removed",
            "products": len((strip or {}).get("block", [])),
            "rows_removed": (strip or {}).get("rows_removed", 0),
            "tail_lengths": (strip or {}).get("tail_lengths", {}),
            "block_urls": (strip or {}).get("block", []),
            "found": "2026-08-09",
            "note": "data/taxonomy-correction-2026-08-09.md",
        },
        # The SECOND correction. A whole node rather than a strip: `discover` serves the
        # site-wide feed for a taxonomy slug it does not recognise, so six nodes were
        # published as categories holding 44 listings of unrelated products.
        "unrecognised_node_correction": {
            "rule": "a node is dropped only when a live refetch matches >= 80% of a "
                    "control fetch of an impossible slug AND the node's grid rows end in "
                    "a run shared with another dropped node; either witness alone stops "
                    "the build instead of dropping anything",
            "nodes": (strip or {}).get("unrecognised", []),
            "slugs": (strip or {}).get("unrecognised_slugs", {}),
            "rows_removed": (strip or {}).get("unrecognised_rows", 0),
            "verified_live": (strip or {}).get("verification_checked"),
            "found": "2026-08-11",
            "instrument": "scripts/verify_taxonomy_nodes.py",
            "machine_record": "data/node-verification.json",
        },
        "by_node": nodes,
    }


def main():
    obs, empty, strip = load()
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in obs:
            w.writerow(r)
    nodes = node_stats(obs)
    s = summarise(obs, nodes, empty, strip)
    OUT_SUMMARY.write_text(json.dumps(s, indent=1) + "\n")
    print(f"recommendations module removed: {len(strip['block'])} products, "
          f"{strip['rows_removed']:,} rows, node tail lengths {strip['tail_lengths']}")
    print(f"{s['n']:,} distinct products / {s['obs']:,} observations / "
          f"{s['sellers']:,} sellers / {s['nodes']} non-empty nodes "
          f"({s['nodes_empty']} empty, excluded) / paid median ${s['med']} / "
          f"top 10% of sellers hold {s['seller_top10_share']}% of ratings")


def selftest():
    """Synthetic records only — no files, no network. `python3 normalize_taxonomy.py -t`.

    The removal rule is the most load-bearing code in this file: it deletes a third of the
    published dataset, and everything downstream of it (both Gumroad pages, the paid report,
    every one-pager) inherits whatever it decides. It shipped without a test on 2026-08-09.

    The cases that matter are the ones where being slightly wrong is invisible in the
    aggregate: a block product that IS a genuine member of one node, a module that is not
    at the end, and a threshold that could quietly swallow honest cross-listing.
    """
    ok = fail = 0

    def chk(name, got, want):
        nonlocal ok, fail
        if got == want:
            ok += 1
        else:
            fail += 1
            print(f"  FAIL {name}: got {got!r} want {want!r}")

    def rec(node, urls):
        return {"node": node, "slug": node.lower(), "rows": [{"url": u} for u in urls]}

    # Ten nodes; M1/M2 are the module and appear in all ten, so at 33% they are the block.
    mod = ["M1", "M2"]
    recs = [rec(f"n{i}", [f"p{i}a", f"p{i}b"] + mod) for i in range(10)]
    bad = block_urls(recs)
    chk("the module is named", sorted(bad), ["M1", "M2"])
    chk("a product in one node of ten is not", "p0a" in bad, False)

    # THE THRESHOLD IS A SHARE, so the same block in a crawl of a different size is still
    # caught — this is why it is not a count.
    big = [rec(f"n{i}", [f"p{i}"] + mod) for i in range(300)]
    chk("the share survives a 300-node crawl", sorted(block_urls(big)), ["M1", "M2"])

    # HONEST CROSS-LISTING MUST SURVIVE. The 99th percentile of real products is 4 nodes.
    cross = [rec(f"n{i}", ([f"p{i}", "X"] if i < 3 else [f"p{i}"])) for i in range(10)]
    chk("a product genuinely in 3 of 10 nodes is kept", block_urls(cross), set())

    # THE ARYIA CASE, and the reason removal is narrower than detection: a block product
    # that also sits in the GRID keeps its grid row and loses only the module copy.
    rows = [{"url": u} for u in ["a", "M1", "b", "M1", "M2"]]
    kept, n = strip_block_tail(rows, {"M1", "M2"})
    chk("only the trailing run is removed", [r["url"] for r in kept], ["a", "M1", "b"])
    chk("and it reports how many it took", n, 2)

    # A module that is not at the end is NOT removed. The rule is deliberately timid: if
    # the order stops looking like an appended widget, it stops trusting itself.
    kept, n = strip_block_tail([{"url": u} for u in ["M1", "M2", "a"]], {"M1", "M2"})
    chk("a block that is not a tail is left alone", n, 0)
    chk("and nothing is dropped from it", len(kept), 3)

    chk("an all-module node empties completely",
        strip_block_tail([{"url": "M1"}], {"M1"})[1], 1)
    chk("an empty node is safe", strip_block_tail([], {"M1"}), ([], 0))
    chk("no block, no removal",
        strip_block_tail([{"url": "a"}, {"url": "b"}], set())[1], 0)

    # AND THE ORDER OF THE TWO OPERATIONS, which is the subtle one. Dedup-then-strip finds
    # a SHORTER tail than strip-then-dedup whenever a block product is also in the grid,
    # which is exactly how the 2026-08-09 measurement read 169 clean tails instead of 194.
    raw = [{"url": u} for u in ["a", "M1", "b", "M1", "M2"]]
    seen, deduped = set(), []
    for r in raw:
        if r["url"] not in seen:
            seen.add(r["url"])
            deduped.append(r)
    chk("dedup first loses the signal", strip_block_tail(deduped, {"M1", "M2"})[1], 1)
    chk("strip first keeps it", strip_block_tail(raw, {"M1", "M2"})[1], 2)

    # ---- THE WHOLE-NODE RULE. Two witnesses, and neither may act alone. ----
    chk("common_suffix: shared tail", common_suffix(list("xxabc"), list("yyabc")), 3)
    chk("common_suffix: nothing shared", common_suffix(list("abc"), list("xyz")), 0)
    chk("common_suffix: a shared HEAD is not a tail",
        common_suffix(list("abcx"), list("abcy")), 0)
    chk("common_suffix: empty", common_suffix([], list("abc")), 0)

    # The real shape: the feed's head rotates per request, its tail does not.
    feed_tail = [f"F{i}" for i in range(9)]
    G = {"A": ["a1", "a2"] + feed_tail,      # both witnesses
         "B": ["b1"] + feed_tail,            # both witnesses
         "C": ["c1", "c2", "c3"],            # a real category
         "D": ["d1", "d2"]}                  # a real category
    V = {"A": "default_feed", "B": "default_feed", "C": "real", "D": "empty"}
    chk("both witnesses agree -> dropped", unrecognised_nodes(G, V), {"A", "B"})
    chk("a real node is untouched", "C" in unrecognised_nodes(G, V), False)

    # ONE WITNESS MUST NOT BE ENOUGH, IN EITHER DIRECTION. A rotating live feed that
    # could delete a category by itself is a worse defect than the one being fixed.
    def exits(g, v):
        try:
            unrecognised_nodes(g, v)
            return False
        except SystemExit:
            return True

    chk("live accuses a node the crawl does not corroborate -> stop",
        exits(G, dict(V, C="default_feed")), True)
    chk("crawl corroborates a node the live check calls real -> stop",
        exits(G, dict(V, B="real")), True)
    chk("live check missing for a corroborated node -> stop",
        exits(G, {"A": "default_feed", "C": "real"}), True)
    chk("no node accused and none corroborated is fine",
        unrecognised_nodes({"C": ["c1"], "D": ["d1"]}, {"C": "real", "D": "real"}), set())

    # The threshold sits in a gap, not on a slope: the six share 36 and no other pair
    # shares 5, so any value in between gives the same answer. Assert the gap exists
    # rather than the constant, because the constant is not the claim.
    chk("suffix witness lands in the gap for 5..9", all(
        unrecognised_nodes(G, V, suffix=k) == {"A", "B"} for k in range(2, 10)), True)

    print(f"selftest: {ok} ok, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv or "-t" in sys.argv:
        sys.exit(selftest())
    main()
