#!/usr/bin/env python3
"""Derive the seller-level view from the published taxonomy sample.

WHY A SEPARATE FILE RATHER THAN MORE COLUMNS ON THE PRODUCT CSV. The taxonomy CSV is a
listing table: one row per (category, product). Everything below is one row per *seller*,
which is a different unit of observation and a different set of caveats. Keeping it in its
own file means nobody can average a seller-level figure across listing rows and get a
number weighted by how many categories Gumroad happened to file each product under.

WHY IT EXISTS AT ALL. Every third-party Gumroad dataset published anywhere is a list of
products. `gumroad-taxonomy.csv` was the first version of this one to record *who* is
selling, and the seller column turns out to carry the strongest finding in the whole
project: concentration at the top of this marketplace is not a catalogue effect. The
median seller in the top 1% by demand has two products, and fourteen of those forty-five
sellers have exactly one.

NO NEW COLLECTION HAPPENS HERE. This reads `data/gumroad-taxonomy.csv` and nothing else,
so it is exactly as reproducible as that file, and re-running it can never disagree with
the product-level release.

WHAT THE FIGURES ARE AND ARE NOT
--------------------------------
- Ratings are a proxy for *relative* demand. A seller's rating total is a floor on units
  sold, not a sales figure, and the share of buyers who rate differs by category.
- A seller's product count is **products found in this crawl**, not their catalogue. The
  crawl took three pages per category node, so a seller whose products rank deep in a
  large category is under-counted here. This biases every catalogue-size figure DOWN and
  is stated on every page built from this file.
- 1,710 of the sellers have no ratings anywhere in the sample. They are included, not
  dropped: "listed and never rated" is the modal outcome on this marketplace and hiding
  it would flatter the market.

Writes `data/gumroad-sellers.csv` (all sellers) and `data/sellers-summary.json`.
"""
import collections
import csv
import json
import math
import pathlib
import statistics as st

ROOT = pathlib.Path(__file__).resolve().parent.parent

FIELDS = [
    "seller", "profile_url", "products", "observations", "categories", "top_category",
    "ratings_total", "rated_products", "ratings_rank", "ratings_share_pct",
    "med_price_usd", "min_price_usd", "max_price_usd", "free_products", "subs",
    "top_product_url", "top_product_ratings", "top_product_title",
]


def spearman(xs, ys):
    """Rank correlation, ties averaged. Written out rather than pulling in scipy so the
    repo keeps its stdlib-only property — anyone can run this with a bare Python."""
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = rank(xs), rank(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(num / den, 3) if den else 0.0


def load_products():
    """Distinct products, keyed on product URL — the exact identity key the taxonomy
    sample has and the search sample never did. First observation wins; the fields that
    differ between observations are the category ones, which are collected separately."""
    prod, cats = {}, collections.defaultdict(set)
    obs = collections.Counter()
    for r in csv.DictReader((ROOT / "data" / "gumroad-taxonomy.csv").open()):
        r["price_usd"] = float(r["price_usd"])
        r["n"] = float(r["n"] or 0)
        prod.setdefault(r["url"], r)
        cats[r["url"]].add(r["node"])
        obs[r["seller"]] += 1
    return prod, cats, obs


def main():
    prod, cats, obs = load_products()
    by_seller = collections.defaultdict(list)
    for r in prod.values():
        by_seller[r["seller"]].append(r)

    ratings = {s: sum(r["n"] for r in v) for s, v in by_seller.items()}
    total_ratings = sum(ratings.values()) or 1
    order = sorted(by_seller, key=lambda s: (-ratings[s], -len(by_seller[s]), s))
    rank_of = {s: i + 1 for i, s in enumerate(order)}

    out = []
    for s in order:
        v = by_seller[s]
        paid = sorted(r["price_usd"] for r in v if r["price_usd"] > 0)
        node_counts = collections.Counter(n for r in v for n in cats[r["url"]])
        best = max(v, key=lambda r: r["n"])
        out.append({
            "seller": s,
            "profile_url": f"https://{s}.gumroad.com",
            "products": len(v),
            "observations": obs[s],
            "categories": len(node_counts),
            "top_category": node_counts.most_common(1)[0][0],
            "ratings_total": int(ratings[s]),
            "rated_products": sum(1 for r in v if r["n"] > 0),
            "ratings_rank": rank_of[s],
            "ratings_share_pct": round(100 * ratings[s] / total_ratings, 4),
            "med_price_usd": round(st.median(paid), 2) if paid else 0.0,
            "min_price_usd": round(paid[0], 2) if paid else 0.0,
            "max_price_usd": round(paid[-1], 2) if paid else 0.0,
            "free_products": sum(1 for r in v if r["price_usd"] == 0),
            "subs": sum(1 for r in v if r["recurring"] == "True"),
            "top_product_url": best["url"],
            "top_product_ratings": int(best["n"]),
            "top_product_title": best["t"],
        })

    with (ROOT / "data" / "gumroad-sellers.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(out)

    n = len(order)

    def share(pct):
        k = max(1, round(n * pct / 100))
        return round(100 * sum(ratings[s] for s in order[:k]) / total_ratings, 1)

    top1_k = max(1, round(n * 0.01))
    top1 = order[:top1_k]
    solo = [s for s in order if len(by_seller[s]) == 1]
    counts = [len(by_seller[s]) for s in order]

    summary = {
        "sellers": n,
        "products": len(prod),
        "ratings_total": int(total_ratings),
        # Concentration, seller-level. The product-level twins live in taxonomy-summary.json.
        "top1_share": share(1), "top5_share": share(5), "top10_share": share(10),
        "top25_share": share(25), "top50_share": share(50),
        "top1_count": top1_k,
        # The finding: the top of this market is not a catalogue business.
        "top1_solo": sum(1 for s in top1 if len(by_seller[s]) == 1),
        "top1_med_products": int(st.median([len(by_seller[s]) for s in top1])),
        "spearman_products_ratings": spearman(counts, [ratings[s] for s in order]),
        # The floor.
        "sellers_zero_ratings": sum(1 for s in order if ratings[s] == 0),
        "solo_sellers": len(solo),
        "solo_share_pct": round(100 * len(solo) / n, 1),
        "solo_ratings_share": round(100 * sum(ratings[s] for s in solo) / total_ratings, 1),
        # NOT counts[0] — `order` is sorted by ratings, so counts[0] is the catalogue size
        # of the most-rated seller (21), which is a different and much smaller number.
        # That mistake shipped for about a minute and is recorded rather than quietly fixed.
        "largest_catalogue_seller": max(order, key=lambda s: len(by_seller[s])),
        "largest_catalogue_n": max(counts) if counts else 0,
        "med_products": int(st.median(counts)) if counts else 0,
        "mean_products": round(st.mean(counts), 2) if counts else 0,
        "decile_shares": [
            round(100 * sum(ratings[s] for s in order[int(n * i / 10):int(n * (i + 1) / 10)])
                  / total_ratings, 1) for i in range(10)],
        "source": "data/gumroad-taxonomy.csv",
        "temporal_coverage": "2026-08-05",
    }
    (ROOT / "data" / "sellers-summary.json").write_text(json.dumps(summary, indent=1) + "\n")

    print(f"wrote {n:,} sellers / {len(prod):,} products; "
          f"top 1% ({top1_k}) hold {summary['top1_share']}% of ratings, "
          f"{summary['top1_solo']} of them with a single product; "
          f"spearman(catalogue, demand) = {summary['spearman_products_ratings']}")


if __name__ == "__main__":
    main()
