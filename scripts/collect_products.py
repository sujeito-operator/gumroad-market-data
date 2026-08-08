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
import heapq
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


def top_level(nodes):
    """Top-level branch for a product, from the first node it ranks under.

    `nodes` entries are SLUGS (`3d/3d-assets/blender`), not `" > "`-joined labels.
    Splitting on the wrong separator is not a loud failure — it silently reports
    every product as its own top level, which is exactly the blindness this
    function exists to remove. Split on `/`.
    """
    for s in nodes:
        if s:
            return s.split("/", 1)[0]
    return "?"


def already_done(path, retry_failed=True):
    """URLs already collected, and how many USABLE rows fall in each top-level branch.

    Two distinctions here, both of which were wrong in the first version of this and both
    of which bias the sample rather than announcing themselves:

    1. `per_branch` counts only rows with `ok: true`. It feeds `stratify()`, whose job is
       to balance the DATA — counting a timeout as coverage would let a branch that keeps
       failing look well covered and starve it of further attempts.
    2. A failed row does not permanently retire its URL. About one page in five times out
       on a first pass, and treating those as done silently drops them from every future
       run — an invisible ~20% hole, unevenly spread, in exactly the sample whose coverage
       this module is trying to make honest. Pass `retry_failed=False` for the older
       behaviour of never re-attempting anything already written.
    """
    done, per_branch = set(), {}
    p = pathlib.Path(path)
    if not p.exists():
        return done, per_branch
    with p.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue  # a torn final line from a killed run is not fatal
            ok = bool(d.get("ok"))
            if ok or not retry_failed:
                done.add(d["url"])
            if ok:
                b = top_level(d.get("nodes") or [])
                per_branch[b] = per_branch.get(b, 0) + 1
    return done, per_branch


def stratify(todo, per_branch, limit):
    """Order the queue so the budget spreads across branches, poorest-covered first.

    WHY THIS IS NOT A TUNING CHOICE. `raw-taxonomy.jsonl` is stored in crawl order,
    which is alphabetical by top-level slug, so a plain `todo[:limit]` spends the
    entire budget inside whichever branch sorts first. It did: 839 of 839 product
    pages landed in `3d`, one of 15 top-level branches, and every dollar figure
    derived from them described 3D/VRChat assets — high unit volumes, low prices —
    while being labelled as describing Gumroad. The numbers were right and the
    label was not.

    A resumable collector's coverage is a claim about the data. Rather than
    document the imbalance again, take from the branch with the fewest rows
    collected so far at every step, counting rows already on disk. A run of any
    size then produces a balanced sample, and a resumed run repairs one.
    """
    queues = {}
    for u, nodes in todo:
        queues.setdefault(top_level(nodes), []).append((u, nodes))
    # Seed each branch's position with what is already collected, so this run
    # spends itself on the branches the previous runs starved.
    heap = [(per_branch.get(b, 0), b) for b in queues]
    heapq.heapify(heap)
    order, at = [], {b: 0 for b in queues}
    while heap and (not limit or len(order) < limit):
        n, b = heapq.heappop(heap)
        q = queues[b]
        order.append(q[at[b]])
        at[b] += 1
        if at[b] < len(q):
            heapq.heappush(heap, (n + 1, b))
    return order


def scrape(pg, url, nodes):
    pg.goto(url, timeout=45000, wait_until="domcontentloaded")
    pg.wait_for_timeout(1200)
    # The blob is server-rendered into the initial HTML, so if it is not present shortly
    # after domcontentloaded it is not coming. The default 30s timeout made each miss cost
    # more than three successful fetches, and roughly one page in five misses.
    raw = pg.get_attribute("#app", "data-page", timeout=8000)
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
    ap.add_argument("--no-retry-failed", action="store_true",
                    help="never re-attempt a URL that previously failed")
    a = ap.parse_args()

    todo = product_urls(a.src)
    done, per_branch = already_done(a.out, retry_failed=not a.no_retry_failed)
    todo = [(u, n) for u, n in todo if u not in done]
    todo = stratify(todo, per_branch, a.limit)
    print(f"{len(done)} already collected; attempting {len(todo)} this run", flush=True)
    print("  on disk:  " + ", ".join(f"{b}={n}" for b, n in
                                     sorted(per_branch.items(), key=lambda kv: -kv[1])), flush=True)
    plan = {}
    for _, n in todo:
        b = top_level(n)
        plan[b] = plan.get(b, 0) + 1
    print("  this run: " + ", ".join(f"{b}={n}" for b, n in
                                     sorted(plan.items(), key=lambda kv: -kv[1])), flush=True)

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
