#!/usr/bin/env python3
"""Collect a snapshot of what is selling on Gumroad Discover.

Captures, per product: search category, price, currency, rating count,
subscription flag and title. Writes CSV + a per-category summary.

Rating count is a PROXY for units sold, not a sales figure — only some buyers
rate and that share differs by category. Use it to rank categories against each
other, never to estimate revenue.
"""
import json, re, csv, sys, urllib.parse, statistics as st
from playwright.sync_api import sync_playwright

from redact import scrub

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

QUERIES = ["notion template","ai prompts","excel dashboard","procreate brushes","lightroom presets",
 "ebook business","course trading","seo tool","chrome extension","vrchat avatar","resume template",
 "meal plan","budget spreadsheet","social media templates","stock photos","font bundle","ui kit",
 "wordpress theme","video luts","sample pack","planner printable","coloring book","canva template",
 "python course","fitness program","language learning","tarot deck","after effects template",
 "davinci resolve","blender addon","unity asset","game assets pixel","midjourney prompts",
 "chatgpt prompts","email templates","pitch deck template","legal contract template","crochet pattern",
 "knitting pattern","sewing pattern","sourdough recipes","yoga program"]

def ratings_to_int(v):
    if not v: return 0
    return int(float(v[:-1]) * 1000) if v.endswith("K") else int(float(v))

def collect():
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        pg = b.new_page(user_agent=UA)
        for q in QUERIES:
            try:
                pg.goto("https://gumroad.com/discover?query=" + urllib.parse.quote(q), timeout=60000)
                pg.wait_for_timeout(5200)
                for el in pg.query_selector_all("article, [role=listitem], .product-card"):
                    t = " ".join((el.inner_text() or "").split())
                    if len(t) < 15: continue
                    price = re.search(r"([£$€])\s?([\d,]+\.?\d*)", t)
                    if not price: continue
                    rating = re.search(r"(\d\.\d)\s*\(([\d.]+K?)\)", t)
                    rows.append({
                        "q": q, "cur": price.group(1),
                        "price": float(price.group(2).replace(",", "")),
                        "nrat": rating.group(2) if rating else None,
                        "n": ratings_to_int(rating.group(2) if rating else None),
                        "recurring": bool(re.search(r"a month|monthly|/mo", t, re.I)),
                        "t": t[:70]})
                print(f"{q:26} ok", file=sys.stderr)
            except Exception as e:
                print(f"{q:26} FAILED {e}", file=sys.stderr)
        b.close()
    return rows

def summarise(rows):
    out = []
    for q in sorted({r["q"] for r in rows}):
        g = [r for r in rows if r["q"] == q]
        prices = sorted(r["price"] for r in g if r["price"] > 0)
        rated = [r for r in g if r["n"] > 0]
        out.append({"topic": q,
            "median": st.median(prices) if prices else 0,
            "p90": prices[int(.9 * len(prices))] if prices else 0,
            "subs": sum(1 for r in g if r["recurring"]),
            "rated_share": round(100 * len(rated) / len(g)) if g else 0,
            "med_ratings": int(st.median([r["n"] for r in rated])) if rated else 0,
            "top_n": max([r["n"] for r in g] or [0])})
    out.sort(key=lambda x: (x["rated_share"], x["med_ratings"]), reverse=True)
    return out

if __name__ == "__main__":
    rows = collect()
    if not rows:
        sys.exit("collected nothing — Gumroad markup may have changed")
    with open("data/gumroad-latest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["q","cur","price","nrat","n","recurring","t"])
        w.writeheader()
        # gumroad-latest.csv is a PUBLISHED file (it is attached to the free
        # Gumroad product), so titles are scrubbed on the way out. See redact.py.
        for r in rows: w.writerow({**r, "t": scrub(r["t"])})
    stats = summarise(rows)
    prices = sorted(r["price"] for r in rows if r["price"] > 0)
    zero = sum(1 for r in rows if r["n"] == 0)
    json.dump({"n": len(rows), "cats": len(stats), "zero": zero,
               "zpct": round(100 * zero / len(rows)),
               "med": round(st.median(prices), 2),
               "p75": round(prices[int(.75 * len(prices))], 2),
               "p90": round(prices[int(.9 * len(prices))], 2),
               "subs": sum(1 for r in rows if r["recurring"]),
               "by_category": stats}, open("data/summary.json", "w"), indent=1)
    print(f"{len(rows)} products / {len(stats)} categories / {round(100*zero/len(rows))}% zero-rated")
