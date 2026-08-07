#!/usr/bin/env python3
"""Collect Gumroad listings by walking Gumroad's OWN published category tree.

WHY THIS REPLACES THE 42 HAND-PICKED SEARCH TERMS
-------------------------------------------------
`collect.py` runs 42 search queries somebody thought of. That has two problems that
only became visible on 2026-08-07:

1. **It is an arbitrary sampling frame.** "notion template" and "yoga program" are
   guesses about where the market is. A reader cannot tell what the sample represents,
   which weakens every market-wide claim built on it.
2. **It never paginated.** Each query returned one page, ~36 cards. Gumroad's own
   result header for `?query=notion template` reports **19,822 products**. The sample
   was one page deep and the shortfall was invisible because nothing ever read that
   header.

This collector fixes both. The frame is **Gumroad's published taxonomy** -- 359 nodes,
read out of the category picker on our own product's edit page (`data/gumroad-taxonomy.txt`),
so it is Gumroad's classification and not ours -- and it follows the "Load more" control.

WHAT IS RECORDED PER CARD
-------------------------
Same columns `collect.py` emits, so the normalise/build chain keeps working, plus:
  * `url`      -- the product permalink. This is an EXACT identity key. The existing
                  dedup hashes the card's rendered text, which the docstring in
                  `normalize.py` admits is a proxy. Two products with identical titles
                  and prices collapse under a text key and do not under a URL key.
  * `seller`   -- the subdomain of that permalink. Never collected before; it is what
                  makes seller-level concentration answerable at all.
  * `taxonomy` -- the full node path, e.g. "Business & Money > Entrepreneurship".

Ratings remain a PROXY for units sold, not a sales figure. Do not derive revenue.

POLITENESS
----------
`gumroad.com/robots.txt` disallows only `/purchases/` (checked 2026-08-07), so these
pages are permitted. Requests are paced with a real delay and a normal user agent, one
page at a time, no concurrency. Do not lower the delay.

USAGE
    python scripts/collect_taxonomy.py --depth 2 --pages 3 --out data/raw-taxonomy.jsonl
Writes JSONL incrementally and SKIPS nodes already present in the output file, so an
interrupted run resumes by re-running the same command.
"""
import argparse, json, os, re, sys, time, urllib.parse
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

DELAY_MS = 4200          # between page actions. Do not lower.
CARD_SEL = "article, [role=listitem], .product-card"


def slugify(node):
    """'Business & Money > Marketing & Sales' -> 'business-and-money/marketing-and-sales'.

    Verified against live URLs: /business-and-money/entrepreneurship returns 200 with
    product cards, and the top-level slugs match the links in Gumroad's own nav.
    """
    parts = []
    for seg in node.split(">"):
        s = seg.strip().lower().replace("&", "and")
        s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
        parts.append(s)
    return "/".join(parts)


def ratings_to_int(v):
    """`nrat` holds ABBREVIATED counts like '3.3K'. A naive float() throws and a naive
    try/except->0 silently zeroes the most-rated products, which is the single worst
    data defect this project has hit. Parse it properly."""
    if not v:
        return 0
    v = v.strip()
    if v.upper().endswith("K"):
        return int(float(v[:-1]) * 1000)
    if v.upper().endswith("M"):
        return int(float(v[:-1]) * 1_000_000)
    return int(float(v))


def parse_cards(pg, node):
    rows = []
    for el in pg.query_selector_all(CARD_SEL):
        t = " ".join((el.inner_text() or "").split())
        if len(t) < 15:
            continue
        price = re.search(r"([£$€¥])\s?([\d,]+\.?\d*)", t)
        if not price:
            continue
        rating = re.search(r"(\d\.\d)\s*\(([\d.]+[KM]?)\)", t)
        link = el.query_selector("a[href*='/l/']")
        url = (link.get_attribute("href") or "") if link else ""
        if url.startswith("/"):
            url = "https://gumroad.com" + url
        url = url.split("?")[0]
        seller = ""
        m = re.match(r"https?://([^./]+)\.gumroad\.com/", url)
        if m:
            seller = m.group(1)
        nrat = rating.group(2) if rating else None
        rows.append({
            "taxonomy": node,
            "url": url,
            "seller": seller,
            "cur": price.group(1),
            "price": float(price.group(2).replace(",", "")),
            "nrat": nrat,
            "n": ratings_to_int(nrat),
            "stars": float(rating.group(1)) if rating else None,
            "recurring": bool(re.search(r"a month|monthly|/mo", t, re.I)),
            "t": t[:70],
        })
    return rows


def load_more(pg, clicks):
    """Click the 'Load more' control up to `clicks` times.

    Returns the number of clicks that actually landed. Stops as soon as the control is
    gone -- that is the end of the result set, not a failure.
    """
    done = 0
    for _ in range(clicks):
        hit = pg.evaluate("""() => {
          const b = [...document.querySelectorAll('button, a')]
            .find(x => (x.innerText||'').trim().toLowerCase() === 'load more');
          if (b) { b.click(); return true; } return false;
        }""")
        if not hit:
            break
        done += 1
        pg.wait_for_timeout(DELAY_MS)
    return done


def reported_total(pg):
    """Gumroad prints 'N products' above the grid. Recording it makes the sample's
    COVERAGE measurable instead of assumed -- the thing `collect.py` never did.

    Returns ALL matches, not the first. The first-match version read '1 products' on
    /audio and None on /3d, because that phrase also occurs in unrelated copy on the
    page. A single wrong coverage number published as fact is exactly this project's
    most expensive recurring defect, so this stores the raw list and leaves the
    interpretation to whoever consumes it -- do NOT publish any of these without
    checking them against the rendered page first.
    """
    t = " ".join(pg.inner_text("body").split())
    return [int(x.replace(",", "")) for x in re.findall(r"([\d,]+)\s+products?\b", t, re.I)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", default="data/gumroad-taxonomy.txt")
    ap.add_argument("--depth", type=int, default=2,
                    help="max node depth; 1 = top level only, 2 = top + second level")
    ap.add_argument("--pages", type=int, default=3, help="'Load more' clicks per node")
    ap.add_argument("--out", default="data/raw-taxonomy.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="stop after N nodes (0 = all)")
    a = ap.parse_args()

    nodes = [l.strip() for l in open(a.taxonomy) if l.strip()]
    nodes = [n for n in nodes if n.count(">") + 1 <= a.depth]

    # Resume: skip nodes already written. Makes the run restartable, which matters
    # because a full walk is longer than one session's lock.
    done = set()
    if os.path.exists(a.out):
        for line in open(a.out):
            try:
                done.add(json.loads(line)["node"])
            except Exception:
                pass
    todo = [n for n in nodes if n not in done]
    print(f"{len(nodes)} nodes at depth<={a.depth}; {len(done)} already done; "
          f"{len(todo)} to go", file=sys.stderr)
    if a.limit:
        todo = todo[:a.limit]

    out = open(a.out, "a")
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True,
                              args=["--no-sandbox", "--disable-dev-shm-usage"])
        pg = b.new_page(user_agent=UA, viewport={"width": 1500, "height": 1400})
        for i, node in enumerate(todo, 1):
            slug = slugify(node)
            # Use the ?taxonomy= form, NOT the path form. `/3d/3d-assets/3ds-max`
            # returns 404 while `?taxonomy=3d%2F3d-assets%2F3ds-max` returns 48 cards;
            # some deep nodes have no path route at all. The path form silently
            # produced ok=True with ZERO rows, which reads as "empty category" rather
            # than "wrong URL" -- checked against both forms before switching.
            url = ("https://gumroad.com/discover?taxonomy="
                   + urllib.parse.quote(slug, safe=""))
            rec = {"node": node, "slug": slug, "ok": False, "rows": [],
                   "reported": [], "clicks": 0}
            try:
                pg.goto("about:blank")
                pg.goto(url, timeout=60000)
                pg.wait_for_timeout(DELAY_MS)
                rec["reported"] = reported_total(pg)
                rec["clicks"] = load_more(pg, a.pages)
                rec["rows"] = parse_cards(pg, node)
                rec["ok"] = True
            except Exception as e:
                rec["error"] = str(e)[:200]
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"[{i}/{len(todo)}] {slug:52} rows={len(rec['rows']):4} "
                  f"reported={rec['reported']} clicks={rec['clicks']} "
                  f"{'' if rec['ok'] else 'ERROR ' + rec.get('error', '')}",
                  file=sys.stderr)
            time.sleep(1.2)
        b.close()
    out.close()


if __name__ == "__main__":
    main()
