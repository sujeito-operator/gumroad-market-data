#!/usr/bin/env python3
"""Collect per-product facts from Gumroad product pages, including REAL UNIT SALES.

WHY THIS EXISTS
---------------
Every figure this project has published so far uses *ratings* as a demand proxy, and
every surface says so on the grounds that "Gumroad does not publish unit sales".
**That is wrong.** Each product page carries an Inertia `data-page` JSON blob whose
`props.product` includes `sales_count` — populated for the subset of sellers who opt
into showing it (~14% in a 14-product spot check, 2026-08-07). It is independent of
ratings: one sampled product shows 138 sales against 5 ratings, another 4 sales
against 0.

Two things follow, and they are the point of this script:

1. The published caveat has to be corrected on every live surface that carries it.
2. The opt-in subset lets us CALIBRATE a sales-per-rating ratio from observed data.
   Sellers guess at "×30" or "×100" with nothing behind it. A published, defensible
   multiplier derived from real paired observations is the single most valuable
   number this dataset could carry, and no competitor listed on 2026-08-07
   (InsightRaider, Gumtrends, reavid) shows their working.

The product page also carries `seller_reputation` — the seller's total rating count
and how many products they list — which the search cards never exposed and which
makes seller-level analysis possible for the first time.

USAGE
-----
    cd /srv/agents/gumroad-market-data
    . /home/agents/.local/opbrowser/env.sh
    /home/agents/.local/opbrowser/venv/bin/python scripts/collect_products.py \
        --limit 600 --delay 2.5 \
        --in data/raw-taxonomy.jsonl --out data/raw-products.jsonl

RESUMABLE. It reads `--out` first and skips every URL already recorded, so re-running
the same command continues rather than restarting. Rows that fail are recorded with
`ok: false` so a failure is distinguishable from a product that was never attempted —
the taxonomy crawler's path-form bug (ok=True with zero rows, which read as "empty
category" rather than "wrong URL") is the reason that distinction is explicit here.

PACING MATTERS. Gumroad rate-limited `/login` for eight consecutive sessions in this
project after too many requests in a short window, and that outage blocked the only
payment rail we have. Default delay is deliberately slow. Do not lower it to go faster.
"""
import argparse
import json
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")


def product_urls(path):
    """Ordered, de-duplicated product URLs from the taxonomy crawl.

    Keeps every taxonomy node a URL appeared under. Per-category figures count a
    product once per node it ranks for; market-wide figures count it once. That
    two-denominator rule is load-bearing everywhere in this repo — preserve the
    node list here so the normaliser can still apply it.
    """
    nodes, order = {}, []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            slug = d.get("slug") or d.get("taxonomy") or d.get("node")
            for row in (d.get("rows") or []):
                u = row.get("url")
                if not u:
                    continue
                if u not in nodes:
                    nodes[u] = []
                    order.append(u)
                if slug and slug not in nodes[u]:
                    nodes[u].append(slug)
    return [(u, nodes[u]) for u in order]


def already_done(path):
    done = set()
    p = pathlib.Path(path)
    if not p.exists():
        return done
    with p.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["url"])
            except Exception:
                continue  # a torn final line from a killed run is not fatal
    return done


def scrape(pg, url, nodes):
    pg.goto(url, timeout=45000, wait_until="domcontentloaded")
    pg.wait_for_timeout(1200)
    raw = pg.get_attribute("#app", "data-page")
    if not raw:
        return {"url": url, "ok": False, "err": "no data-page blob", "nodes": nodes}
    pr = json.loads(raw)["props"]["product"]
    seller = pr.get("seller") or {}
    ratings = pr.get("ratings") or {}
    rep = pr.get("seller_reputation") or {}
    pwyw = pr.get("pwyw") or {}
    return {
        "url": url,
        "ok": True,
        "nodes": nodes,
        "permalink": pr.get("permalink"),
        "name": pr.get("name"),
        "seller_id": seller.get("id"),
        "seller_name": seller.get("name"),
        # The subdomain is the stable seller identity key; `name` is a display
        # string the seller can change at any time.
        "seller_sub": url.split("//", 1)[-1].split(".", 1)[0],
        # None means the seller did not opt into showing it. It is NOT zero, and
        # collapsing the two would silently invent a datapoint at the exact place
        # this whole collection is trying to measure.
        "sales_count": pr.get("sales_count"),
        "ratings_count": ratings.get("count"),
        "ratings_avg": ratings.get("average"),
        "seller_rep_avg": rep.get("average"),
        "seller_rep_count": rep.get("count"),
        "seller_products": rep.get("products_count"),
        "price_cents": pr.get("price_cents"),
        "currency": pr.get("currency_code"),
        "pwyw_suggested_cents": pwyw.get("suggested_price_cents"),
        "is_pwyw": bool(pr.get("pwyw")),
        "is_recurring": pr.get("is_recurring_billing"),
        "is_tiered": pr.get("is_tiered_membership"),
        "is_published": pr.get("is_published"),
        "is_physical": pr.get("is_physical"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="data/raw-taxonomy.jsonl")
    ap.add_argument("--out", dest="out", default="data/raw-products.jsonl")
    ap.add_argument("--limit", type=int, default=600)
    ap.add_argument("--delay", type=float, default=2.5)
    a = ap.parse_args()

    todo = product_urls(a.src)
    done = already_done(a.out)
    todo = [(u, n) for u, n in todo if u not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(done)} already collected; attempting {len(todo)} this run", flush=True)

    n_sales = n_ok = 0
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA)
        with open(a.out, "a") as fh:
            for i, (url, nodes) in enumerate(todo, 1):
                pg = ctx.new_page()
                try:
                    rec = scrape(pg, url, nodes)
                except Exception as e:
                    rec = {"url": url, "ok": False, "err": str(e)[:200], "nodes": nodes}
                pg.close()
                fh.write(json.dumps(rec) + "\n")
                fh.flush()          # a killed run must leave usable output
                if rec.get("ok"):
                    n_ok += 1
                    if rec.get("sales_count") is not None:
                        n_sales += 1
                if i % 10 == 0 or i == len(todo):
                    print(f"[{i}/{len(todo)}] ok={n_ok} with_sales={n_sales} "
                          f"({100*n_sales/max(1,n_ok):.1f}% of ok)", flush=True)
                time.sleep(a.delay)
        br.close()
    print(f"DONE ok={n_ok} with_sales={n_sales}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
