#!/usr/bin/env python3
"""Derive the published sales-disclosure table from the per-product crawl.

WHY THIS FILE EXISTS
--------------------
Every other figure in this repository uses *ratings* as a demand proxy, because a
Gumroad search card shows a rating count and nothing else. `collect_products.py`
re-fetched individual product pages and found that a minority of sellers opt into
publishing `sales_count` — an actual unit-sales number — alongside their ratings.

That subset is the only place in this project where the proxy can be checked against
the thing it proxies for. Two questions become answerable:

1. **Is the proxy any good?** (Spearman between ratings and sales, over the products
   that publish both.)
2. **What does one rating actually represent?** Sellers repeat "×30" and "×100" to each
   other with nothing behind either number. This file publishes the measured
   distribution instead, split free from paid, with n and the interquartile range, so
   the spread is visible rather than collapsed into one figure.

WHAT THE SAMPLE IS, AND IS NOT
------------------------------
The input is the taxonomy walk's product URLs, re-fetched one page at a time. So this
is a SUBSAMPLE OF THE TAXONOMY SAMPLE — not a third population, and never to be merged
with the 42-search sample (`data/gumroad-latest.csv`), which disagrees with the
taxonomy walk on price by a wide margin. That disagreement is a published finding.

The ratio is measured only on products that (a) opt into displaying a sales count and
(b) have at least one rating. Both conditions bias it, and the direction of each is
stated on every surface built from this file:

- **Opt-in.** A seller who switches the counter on is likelier to have something worth
  showing. That pushes the observed multiplier's inputs up, not the ratio itself, but it
  means the sample is not a random draw of Gumroad products.
- **At least one rating.** Products with sales and no rating are excluded because the
  ratio is undefined for them, and they are exactly where under-rating is worst. The
  published medians are therefore a **lower bound** on sales per rating.
- **Mechanical censoring at the bottom.** With ratings >= 1, the ratio can never exceed
  the sales count, so a product with 6 sales cannot show a multiplier above 6. Bands cut
  by *sales* are censored by construction; bands cut by *ratings count* are not, and the
  same upward trend survives there. Both are published so the reader can see it.

NO NEW COLLECTION HAPPENS HERE. This reads `data/raw-products.jsonl` and nothing else.

Writes `data/gumroad-sales.csv` (one row per distinct product successfully fetched,
whether or not it discloses sales) and `data/sales-ratio-summary.json`.
"""
import csv
import json
import pathlib
import statistics as st

from redact import scrub

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw-products.jsonl"
OUT_CSV = ROOT / "data" / "gumroad-sales.csv"
OUT_JSON = ROOT / "data" / "sales-ratio-summary.json"

FIELDS = [
    "url", "permalink", "title", "seller", "seller_url", "price_usd", "is_free",
    "discloses_sales", "sales_count", "ratings_count", "ratings_avg",
    "sales_per_rating", "seller_products", "seller_ratings_total", "top_category",
]

# Bands cut by SALES. Censored by construction (see module docstring) and published
# with that said out loud, because the censoring is itself the answer to "can I apply
# a multiplier to a product with four ratings?" — no.
SALES_BANDS = [(1, 9, "1–9 sales"), (10, 49, "10–49"), (50, 199, "50–199"),
               (200, 499, "200–499"), (500, 1999, "500–1,999"), (2000, 10 ** 9, "2,000+")]

# Bands cut by RATINGS. Not censored the same way, so this is the honest test of
# whether the multiplier really rises with size or only appears to.
RATING_BANDS = [(1, 2, "1–2 ratings"), (3, 9, "3–9"), (10, 49, "10–49"),
                (50, 10 ** 9, "50 or more")]

PRICE_BANDS = [(0.01, 10, "under $10"), (10, 25, "$10–25"), (25, 50, "$25–50"),
               (50, 10 ** 9, "$50+")]


def load():
    """Distinct successfully-fetched products, keyed on URL.

    `ok: false` rows are failures, not products, and are dropped. The crawler is
    resumable and flushes per row, so the same URL can legitimately appear twice; last
    write wins.
    """
    seen = {}
    for line in RAW.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("ok"):
            seen[r["url"]] = r
    return [seen[k] for k in sorted(seen)]


def spread(xs):
    """Median, quartiles and n. Never returns a bare average: the distribution is the
    finding, and one 1,418× outlier moves a mean by more than it should."""
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    q = st.quantiles(xs, n=4) if n >= 4 else [xs[0], st.median(xs), xs[-1]]
    d = {"n": n, "median": round(st.median(xs), 1),
         "q1": round(q[0], 1), "q3": round(q[2], 1),
         "min": round(xs[0], 1), "max": round(xs[-1], 1)}
    if n >= 10:
        dec = st.quantiles(xs, n=10)
        d["p10"], d["p90"] = round(dec[0], 1), round(dec[8], 1)
    return d


def spearman(a, b):
    """Rank correlation with ties averaged. Rank rather than Pearson because both
    variables are heavy-tailed counts and a single 30,000-sale listing would otherwise
    decide the answer."""
    def rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        rk = [0.0] * len(x)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk

    ra, rb = rank(a), rank(b)
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return round(num / den, 3) if den else 0.0


def banded(pairs, bands, key):
    out = []
    for lo, hi, label in bands:
        g = [r for r in pairs if lo <= key(r) <= hi]
        if len(g) >= 5:          # below five the quartiles describe nothing
            s = spread([r["ratio"] for r in g])
            out.append({"label": label, **s})
    return out


def main():
    rows = load()
    for r in rows:
        r["price_usd"] = round((r.get("price_cents") or 0) / 100, 2)
        r["discloses"] = r.get("sales_count") is not None
        r["ratio"] = (r["sales_count"] / r["ratings_count"]
                      if r["discloses"] and r.get("ratings_count") else None)

    disc = [r for r in rows if r["discloses"]]
    pairs = [r for r in disc if r["ratio"] is not None]
    paid = [r for r in pairs if r["price_usd"] > 0]
    free = [r for r in pairs if r["price_usd"] == 0]
    # Sales but no rating: the ratio is undefined, so these are excluded from every
    # median above — and they are the direct refutation of "no ratings means it has
    # sold nothing", which this project published on a live page and had to correct.
    unrated = [r for r in disc if not r.get("ratings_count")]

    paid_all = [r for r in rows if r["price_usd"] > 0]
    free_all = [r for r in rows if r["price_usd"] == 0]

    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            nodes = r.get("nodes") or []
            w.writerow({
                "url": r["url"],
                "permalink": r.get("permalink") or "",
                # Six sellers put an email address in their own product title. Every
                # published file in this repo runs titles through scrub(); see redact.py.
                "title": scrub(r.get("name") or ""),
                "seller": scrub(r.get("seller_name") or ""),
                "seller_url": f"https://{r['seller_sub']}.gumroad.com" if r.get("seller_sub") else "",
                "price_usd": f"{r['price_usd']:.2f}",
                "is_free": r["price_usd"] == 0,
                "discloses_sales": r["discloses"],
                "sales_count": r["sales_count"] if r["discloses"] else "",
                "ratings_count": r.get("ratings_count") or 0,
                "ratings_avg": r.get("ratings_avg") if r.get("ratings_avg") is not None else "",
                "sales_per_rating": f"{r['ratio']:.2f}" if r["ratio"] is not None else "",
                "seller_products": r.get("seller_products") or "",
                "seller_ratings_total": r.get("seller_rep_count") or "",
                # First node only: a product ranks under several taxonomy nodes and this
                # column is a label, not a classification. Nothing aggregates on it.
                "top_category": nodes[0] if nodes else "",
            })

    summary = {
        "fetched": len(rows),
        "sellers": len({r.get("seller_sub") for r in rows if r.get("seller_sub")}),
        "disclosing": len(disc),
        "disclose_pct": round(100 * len(disc) / len(rows), 1),
        "disclose_pct_paid": round(100 * sum(1 for r in paid_all if r["discloses"]) / len(paid_all), 1),
        "disclose_pct_free": round(100 * sum(1 for r in free_all if r["discloses"]) / len(free_all), 1),
        "disclosing_sellers": len({r.get("seller_sub") for r in disc if r.get("seller_sub")}),
        "units_observed": sum(r["sales_count"] for r in disc),
        "paired": len(pairs),
        "all_ratio": spread([r["ratio"] for r in pairs]),
        "paid_ratio": spread([r["ratio"] for r in paid]),
        "free_ratio": spread([r["ratio"] for r in free]),
        # 100 / ratio. The share of buyers who leave a rating, which is the same fact
        # said the way a seller experiences it.
        "paid_rating_rate": round(100 / spread([r["ratio"] for r in paid])["median"], 1),
        "free_rating_rate": round(100 / spread([r["ratio"] for r in free])["median"], 1),
        # Demand-weighted, i.e. total sales over total ratings. Published beside the
        # median rather than instead of it: it answers a different question (what does
        # the marketplace's whole rating pile represent) and it is dominated by the
        # largest listings, which is exactly why it is so much higher.
        "paid_pooled": round(sum(r["sales_count"] for r in paid) / sum(r["ratings_count"] for r in paid), 1),
        "all_pooled": round(sum(r["sales_count"] for r in pairs) / sum(r["ratings_count"] for r in pairs), 1),
        "spearman_all": spearman([r.get("ratings_count") or 0 for r in disc],
                                 [r["sales_count"] for r in disc]),
        "spearman_paired": spearman([r["ratings_count"] for r in pairs],
                                    [r["sales_count"] for r in pairs]),
        "by_sales": banded(pairs, SALES_BANDS, lambda r: r["sales_count"]),
        "by_ratings": banded(pairs, RATING_BANDS, lambda r: r["ratings_count"]),
        "by_price": banded(paid, PRICE_BANDS, lambda r: r["price_usd"]),
        "unrated_n": len(unrated),
        "unrated_median_sales": int(st.median([r["sales_count"] for r in unrated])) if unrated else 0,
        "unrated_max_sales": max((r["sales_count"] for r in unrated), default=0),
        "unrated_over_10": sum(1 for r in unrated if r["sales_count"] >= 10),
        "unrated_over_100": sum(1 for r in unrated if r["sales_count"] >= 100),
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"{OUT_CSV.name}: {len(rows)} products, {len(disc)} disclosing "
          f"({summary['disclose_pct']}%), {len(pairs)} with a usable ratio")
    print(f"  paid   median x{summary['paid_ratio']['median']} "
          f"(IQR x{summary['paid_ratio']['q1']}–x{summary['paid_ratio']['q3']}, n={len(paid)})")
    print(f"  free   median x{summary['free_ratio']['median']} "
          f"(IQR x{summary['free_ratio']['q1']}–x{summary['free_ratio']['q3']}, n={len(free)})")
    print(f"  ratings~sales Spearman {summary['spearman_all']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
