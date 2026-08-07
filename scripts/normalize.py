#!/usr/bin/env python3
"""Normalise asking prices to USD and regenerate the summary.

WHY THIS EXISTS. `collect.py` records the price exactly as Gumroad Discover displayed
it, together with the currency symbol. Gumroad localises that display, so a single
search returns a mixture of GBP, USD and EUR listings — in this sample 1239 GBP,
228 USD, 44 EUR, and **40 of the 42 categories contain more than one currency**.

Taking a median across that mixture compares numbers that are not in the same unit.
Every "median price" published before 2026-08-07 was computed that way and was wrong:
the median moved from 29.70 to 39.00 once the units were reconciled. The raw
`price`/`cur` columns are left untouched so the collection is still verifiable; a
`price_usd` column is added alongside, and all statistics are computed from it.

READ THIS BEFORE QUOTING `med`. Every price statistic here — `med`, `p75`, `p90` and
each category's `median`/`p25`/`p75`/`p90` — is computed over **paid listings only**
(`price_usd > 0`), i.e. 1428 of the 1511 rows. That is the right definition for a price
anchor, but it is not "the median listing": including the 83 free listings the overall
median is 35.00, not 39.00. Label it as a paid-listing figure wherever it is published.
`zero`/`zpct` are the opposite kind of number — they count listings with no *ratings*
and are computed over all rows.

READ THIS BEFORE QUOTING `n`. The collection is 42 category *searches*, and one product
can rank for several of them, so a row is a **listing observation, not a product**. 165
rows are the same product seen under a second or third query. Every surface published
before 2026-08-07 called the row count "1,511 products"; there are **1,344 distinct
products** in 1,509 observations. Deduping matters beyond the label, because a product
that ranks for three queries is a *broader, more popular* product — counting it three
times biases every global aggregate toward winners. The paid-listing median moves
39.00 -> 36.99 once it is done.

So there are two denominators and they are both correct for different questions:
  * `n`    = distinct products (1344). Every GLOBAL statistic uses this.
  * `obs`  = listing observations (1509). Kept because the query->product mapping is
             itself data — ranking for three searches is a signal, not noise.
  * per-category `n` counts a product once *within* that category, but a product that
    genuinely ranks in two categories is counted in both. That is the right semantics
    for "what do things in this category sell for".
A further 2 rows were exact duplicates *within the same query* — a collection artifact,
not a real second listing — and are dropped from the CSV entirely (1511 -> 1509).

Dedup key is the exact card text. A normalised key (rating widget and price tokens
stripped) yields the same 1344, so the exact key is not merging distinct products.

DEMAND, NOT REVENUE. `ratings_total` and the `top*_share` fields describe how *ratings*
are distributed across products. Ratings are a floor on buyers, not a sales estimate:
this file never multiplies a rating count by an invented review rate to manufacture a
revenue figure. Say "ratings" when quoting them.

The rate is fixed and recorded rather than fetched at read time, so every figure
published from this file is reproducible from the file itself.
"""
import csv, json, statistics as st, sys, pathlib

from redact import scrub

# ECB reference rates via frankfurter.app, fetched 2026-08-07 for value date 2026-08-06.
FX_DATE = "2026-08-06"
FX_SOURCE = "European Central Bank reference rates via frankfurter.app"
TO_USD = {"$": 1.0, "£": 1 / 0.74255, "€": 1 / 0.8664}

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "gumroad-latest.csv"
SUMMARY = ROOT / "data" / "summary.json"


def to_usd(price, cur):
    return round(price * TO_USD[cur], 2)


def pct(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    return round(sorted_vals[min(int(q * len(sorted_vals)), len(sorted_vals) - 1)], 2)


def dedupe_within_query(rows):
    """Drop exact duplicate cards seen under the SAME query — a collection artifact."""
    seen, out = set(), []
    for r in rows:
        k = (r["q"], r["t"].strip())
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def distinct_products(rows):
    """One row per product, first observation wins. Used for every GLOBAL statistic."""
    seen, out = set(), []
    for r in rows:
        k = r["t"].strip()
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def load():
    rows = list(csv.DictReader(CSV.open()))
    for r in rows:
        r["t"] = scrub(r["t"])
        r["price"] = float(r["price"])
        r["n"] = float(r["n"] or 0)
        r["recurring"] = r["recurring"] == "True"
        if r["cur"] not in TO_USD:
            sys.exit(f"unknown currency {r['cur']!r} — add a rate before publishing")
        r["price_usd"] = to_usd(r["price"], r["cur"])
    return dedupe_within_query(rows)


def summarise(rows):
    cats = []
    for q in sorted({r["q"] for r in rows}):
        g = [r for r in rows if r["q"] == q]
        prices = sorted(r["price_usd"] for r in g if r["price_usd"] > 0)
        rated = [r for r in g if r["n"] > 0]
        curs = sorted({r["cur"] for r in g})
        cats.append({
            "topic": q,
            "n": len(g),
            "median": pct(prices, .5),
            "p25": pct(prices, .25),
            "p75": pct(prices, .75),
            "p90": pct(prices, .9),
            "free": sum(1 for r in g if r["price_usd"] == 0),
            "subs": sum(1 for r in g if r["recurring"]),
            "rated_share": round(100 * len(rated) / len(g)) if g else 0,
            "med_ratings": int(st.median([r["n"] for r in rated])) if rated else 0,
            "top_n": int(max([r["n"] for r in g] or [0])),
            "currencies": curs,
        })
    cats.sort(key=lambda x: (x["rated_share"], x["med_ratings"]), reverse=True)

    # Every GLOBAL figure below is over DISTINCT PRODUCTS, not observations. A product
    # ranking for three queries used to be counted three times, which tilted all of it
    # toward popular products. See the module docstring.
    prod = distinct_products(rows)
    prices = sorted(r["price_usd"] for r in prod if r["price_usd"] > 0)
    zero = sum(1 for r in prod if r["n"] == 0)

    # Demand concentration. Ratings only — never a manufactured revenue estimate.
    ratings = sorted((r["n"] for r in prod), reverse=True)
    total_ratings = sum(ratings)
    rated_only = [x for x in ratings if x > 0]

    def share(p):
        k = max(1, round(len(ratings) * p / 100))
        return round(100 * sum(ratings[:k]) / total_ratings, 1) if total_ratings else 0.0

    return {
        "n": len(prod),
        "obs": len(rows),
        "dupes": len(rows) - len(prod),
        "cats": len(cats),
        "zero": zero,
        "zpct": round(100 * zero / len(prod)),
        "med": pct(prices, .5),
        "med_all": round(st.median(sorted(r["price_usd"] for r in prod)), 2),
        "p75": pct(prices, .75),
        "p90": pct(prices, .9),
        "free": sum(1 for r in prod if r["price_usd"] == 0),
        "ratings_total": int(total_ratings),
        "med_ratings_all": int(st.median(ratings)) if ratings else 0,
        "med_ratings_rated": int(st.median(rated_only)) if rated_only else 0,
        "top1_share": share(1),
        "top5_share": share(5),
        "top10_share": share(10),
        "bottom50_share": round(
            100 * sum(ratings[len(ratings) // 2:]) / total_ratings, 1) if total_ratings else 0.0,
        "top_product_ratings": int(ratings[0]) if ratings else 0,
        "subs": sum(1 for r in prod if r["recurring"]),
        # How many categories mix currencies. Derived, not hand-written: it was pasted
        # into summary.json once and normalize.py never emitted it, so re-running the
        # documented rebuild chain deleted the key and crashed build_site.py.
        "mixed_cats": sum(1 for c in cats if len(c["currencies"]) > 1),
        "currency": "USD",
        "fx_date": FX_DATE,
        "fx_source": FX_SOURCE,
        "fx_rates_to_usd": {k: round(v, 5) for k, v in TO_USD.items()},
        "by_category": cats,
    }


def main():
    rows = load()
    with CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["q", "cur", "price", "price_usd", "nrat", "n", "recurring", "t"])
        w.writeheader()
        for r in rows:
            w.writerow({"q": r["q"], "cur": r["cur"], "price": r["price"],
                        "price_usd": r["price_usd"], "nrat": r["nrat"] or "",
                        "n": r["n"], "recurring": r["recurring"], "t": r["t"]})
    s = summarise(rows)
    SUMMARY.write_text(json.dumps(s, indent=1) + "\n")
    print(f"{s['n']} distinct products in {s['obs']} observations "
          f"({s['dupes']} cross-category repeats) / {s['cats']} categories / "
          f"paid median ${s['med']} / p90 ${s['p90']} / "
          f"top 1% hold {s['top1_share']}% of {s['ratings_total']} ratings")


if __name__ == "__main__":
    main()
