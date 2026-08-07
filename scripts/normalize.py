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
(500 of 1511, 33%) and are computed over all rows.

The rate is fixed and recorded rather than fetched at read time, so every figure
published from this file is reproducible from the file itself.
"""
import csv, json, statistics as st, sys, pathlib

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


def load():
    rows = list(csv.DictReader(CSV.open()))
    for r in rows:
        r["price"] = float(r["price"])
        r["n"] = float(r["n"] or 0)
        r["recurring"] = r["recurring"] == "True"
        if r["cur"] not in TO_USD:
            sys.exit(f"unknown currency {r['cur']!r} — add a rate before publishing")
        r["price_usd"] = to_usd(r["price"], r["cur"])
    return rows


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

    prices = sorted(r["price_usd"] for r in rows if r["price_usd"] > 0)
    zero = sum(1 for r in rows if r["n"] == 0)
    return {
        "n": len(rows),
        "cats": len(cats),
        "zero": zero,
        "zpct": round(100 * zero / len(rows)),
        "med": pct(prices, .5),
        "p75": pct(prices, .75),
        "p90": pct(prices, .9),
        "subs": sum(1 for r in rows if r["recurring"]),
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
    print(f"{s['n']} rows / {s['cats']} categories / median ${s['med']} / p90 ${s['p90']}")


if __name__ == "__main__":
    main()
