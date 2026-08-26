#!/usr/bin/env python3
"""Compare two readings of the same Gumroad product pages and report what moved.

`data/gumroad-sales.csv` is a photograph: one reading, one day. The interesting question
about a unit counter is not what it says today but whether it says something different
next month, and a summary total cannot answer that — a corpus can hold a steady total
while every row underneath has changed. So this joins the two readings **by product URL**
and reports per-row movement.

    python3 scripts/rescan_diff.py                      # the published pair
    python3 scripts/rescan_diff.py OLD.csv NEW.csv
    python3 scripts/rescan_diff.py --json out.json

THREE STATUSES, AND THE MIDDLE ONE IS THE POINT. In the rescan file, `not_disclosed`
means the page read fine and that seller has not switched the unit counter on;
`unread` means the fetch failed and we do not know either way. They are never merged,
because merging them would report our failures as sellers' behaviour. Rows that are not
disclosing at BOTH readings are excluded from the movement denominator and the exclusion
is printed.

PRICES ARE COMPARED IN USD ONLY. The baseline carries `price_usd` with no currency
column; the rescan carries the page's own currency. Comparing across the two would
manufacture movement out of a unit mismatch, so non-USD rows are dropped from the price
comparison and counted out loud.
"""
import argparse
import csv
import datetime as dt
import json
import pathlib
import statistics
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "data" / "gumroad-sales.csv"
RESCAN = ROOT / "data" / "gumroad-sales-rescan-2026-08-26.csv"


def baseline_date(path):
    """-> the date the baseline CSV was last committed here. Never typed: the interval in
    the README is a number a reader can check against this repo's own log."""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%aI", "--",
                              str(path)], capture_output=True, text=True, timeout=30)
    except Exception:                                          # noqa: BLE001
        return None
    return ((out.stdout or "").strip()[:10]) or None


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def read(path, cols):
    out = {}
    with pathlib.Path(path).open(newline="") as fh:
        for r in csv.DictReader(fh):
            u = (r.get("url") or "").strip()
            if u:
                out[u] = {k: fn(r.get(src)) for k, (src, fn) in cols.items()}
    return out


BASE_COLS = {"discloses": ("discloses_sales", lambda v: str(v) == "True"),
             "units": ("sales_count", _int),
             "ratings": ("ratings_count", _int),
             "price": ("price_usd", _float)}
DATE_COL = {"fetched_at": ("fetched_at", lambda v: (v or "").strip())}
NEW_COLS = {"status": ("status", lambda v: (v or "").strip()),
            "units": ("sales_count", _int),
            "ratings": ("ratings_count", _int),
            "price": ("price", _float),
            "currency": ("currency", lambda v: (v or "").strip().upper())}


def diff(old, new, frm=None, to=None, days=None):
    joined = [u for u in old if u in new]
    was = [u for u in joined if old[u]["discloses"] and old[u]["units"] is not None]
    comparable = [u for u in was
                  if new[u]["status"] == "disclosed" and new[u]["units"] is not None]
    deltas = [new[u]["units"] - old[u]["units"] for u in comparable]
    moved = [d for d in deltas if d]
    price_cmp = [u for u in comparable if new[u]["currency"] == "USD"
                 and new[u]["price"] is not None and old[u]["price"] is not None]
    pcts = [100.0 * (new[u]["units"] - old[u]["units"]) / old[u]["units"]
            for u in comparable
            if old[u]["units"] and new[u]["units"] != old[u]["units"]]
    return {
        "from": frm, "to": to, "days": days,
        "joined": len(joined),
        "disclosing_then": len(was),
        "unread_on_rescan": sum(1 for u in joined if new[u]["status"] == "unread"),
        "stopped_disclosing": sum(1 for u in was if new[u]["status"] == "not_disclosed"),
        "comparable": len(comparable),
        "units_moved": len(moved),
        "units_same": len(deltas) - len(moved),
        "units_up": sum(1 for d in moved if d > 0),
        "units_down": sum(1 for d in moved if d < 0),
        "units_moved_pct": round(100.0 * len(moved) / len(comparable), 1) if comparable else None,
        "median_abs_move": int(statistics.median([abs(d) for d in moved])) if moved else None,
        "largest_abs_move": max([abs(d) for d in moved]) if moved else None,
        "ratings_moved": sum(1 for u in comparable
                             if None not in (old[u]["ratings"], new[u]["ratings"])
                             and old[u]["ratings"] != new[u]["ratings"]),
        "price_comparable": len(price_cmp),
        "price_moved": sum(1 for u in price_cmp
                           if abs(new[u]["price"] - old[u]["price"]) >= 0.01),
        "price_excluded_non_usd": len(comparable) - len(price_cmp),
        "median_pct_change": round(statistics.median(pcts), 1) if pcts else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old", nargs="?", default=str(BASELINE))
    ap.add_argument("new", nargs="?", default=str(RESCAN))
    ap.add_argument("--json")
    a = ap.parse_args()
    # The two dates are the RESCAN's own `fetched_at` column and the baseline's publication
    # date, which is this repo's commit for that file. Both are read, never typed.
    new_rows = read(a.new, NEW_COLS)
    stamps = sorted(v["fetched_at"][:10] for v in read(a.new, DATE_COL).values()
                    if v.get("fetched_at"))
    to = stamps[-1] if stamps else None
    frm = baseline_date(a.old)
    days = None
    if frm and to:
        days = (dt.date.fromisoformat(to) - dt.date.fromisoformat(frm)).days
    d = diff(read(a.old, BASE_COLS), new_rows, frm, to, days)
    w = max(len(k) for k in d)
    for k, v in d.items():
        print(f"  {k.ljust(w)}  {v}")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(d, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
