#!/usr/bin/env python3
"""Read a Gumroad SKU's price LIVE, anonymously, so a page can show it without typing it.

WHY THIS EXISTS, 2026-08-22.

Every generator in this repository states the same rule, and each one states it as a
reason for showing NOTHING: `build_audit_sample_page.py` ("THIS PAGE CARRIES NO PRICE, ON
PURPOSE"), `build_checkout.py` ("NAMED HERE AND NOWHERE ELSE ON THIS PAGE, AND CARRYING NO
FIGURE"), `build_site.buy_block` for the guarantee window. The reason given is always the
same one and it is a good reason: **a typed price is a surface to keep in sync, and a stale
price on a published surface is the defect this operation has shipped more often than any
other.**

The rule is right. What was wrong is that it was not being applied evenly, and reading it
as "show nothing" cost something nobody had written down. The written report is priced on
541 pages, in the buy block and in its own Product markup, from a TYPED literal in
`build_site.PRICE`. The storefront audit and the checkout monitor — the second of which is
the only recurring SKU here, and the one the recurring revenue target is made of — were
named on their own pages and priced on none of them. So the rule was waived for the one
product with 541 surfaces riding on it and enforced on the two with one each, which is the
opposite of where the risk was.

No figure appears anywhere in this file outside its own test fixtures, and the selftest
asserts that, comments and docstring included. A price written into prose here would be the
same defect one layer down: stale, unread, and quoted by the next session as if it were a
reading.

There is a third option between "type it" and "hide it": **read it live and prove it still
matches.** That is this file. Nothing here invents a figure, and nothing downstream may
quote one it did not get from here.

THE SECOND HALF IS THE PART THAT MAKES IT SAFE, AND IT IS NOT IN THIS FILE. A published
HTML file is a snapshot: a price read live at build time is frozen the moment it is
written, so this module alone converts "stale because somebody typed it" into "stale
because nobody rebuilt". That is an improvement only if something notices.
`sku_price_gate.py` in the operator repo reads the PUBLISHED BYTES off the live site and
the LIVE Gumroad price and refuses when they disagree. **If that gate is ever deleted, put
the prices back behind the links** — the rule above is worth more than the funnel.

WHY NOT `props["price_cents"]`. A Gumroad membership created through the normal form is a
TIERED membership: the product-level `price_cents` stays 0 and the real figure lives on the
tier. The first anonymous read of `zyoqbc` after publishing returned `price_cents=0` — a
product that charges every month reading as free to any caller using the one-off's reader. That
discovery is `gumroad_monitor_sku.live_cents` in the operator repo; this is the same
resolution order, reimplemented here rather than imported, because this repository is
public and a reader has to be able to run it without a private checkout beside it.

WHY THERE IS A CACHE. The build must not need the network to be honest, and it must never
invent a number when the network is down. So a successful read is written to
`data/live-prices.json` with the moment it was taken, and a build that cannot reach Gumroad
falls back to that file and SAYS SO on stdout. A build with neither a live read nor a cache
entry refuses. There is no path through this module that produces a typed literal.

    python3 scripts/live_price.py --selftest
    python3 scripts/live_price.py --refresh          # re-read every SKU, update the cache
    python3 scripts/live_price.py --show
"""
import argparse
import datetime
import html as _html
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "live-prices.json"

STORE = "https://sujeitooperator.gumroad.com/l/"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")

# The SKUs this repository's pages are allowed to price. A permalink not on this list is
# refused rather than read: the point of a short list is that adding a price to a page is a
# decision somebody makes here, not something a caller can do by passing a new string.
KNOWN = {
    "zyoqbc": "checkout monitor, recurring monthly",
    "xlvfeb": "storefront audit, one-off",
    "bylafq": "the written report, one-off",
    # Added 2026-08-26. The entry rung: ONE product page walked, against the storefront
    # audit's every product. It exists because this storefront had nothing between free
    # and $99 and a reader arriving on `/audit-sample.html` had no cheap way to say yes.
    "xmzlkz": "one product page walked as a UK/EU buyer, one-off",
}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def public_props(permalink, timeout=40):
    """Anonymous read of the live product page's Inertia blob. No login, no API key."""
    req = urllib.request.Request(STORE + permalink, headers={"User-Agent": UA})
    page = urllib.request.urlopen(req, timeout=timeout).read().decode("utf8", "replace")
    m = re.search(r'data-page="([^"]+)"', page)
    if not m:
        raise ValueError(f"no Inertia blob on {STORE + permalink} — cannot read a price")
    return json.loads(_html.unescape(m.group(1)))["props"]["product"]


def cents_from_props(props, permalink="?"):
    """-> (cents, recurring). The tier is resolved BEFORE the product-level field.

    A membership whose monthly tier carries no price is an error, never a 0. Returning 0
    here would put "free" on a page for a product that charges every month, which is the
    one failure this whole module exists to make impossible.
    """
    recurring = bool(props.get("is_tiered_membership") or props.get("is_recurring_billing"))
    if recurring:
        for opt in (props.get("options") or []):
            vals = (opt.get("recurrence_price_values") or {}).get("monthly") or {}
            if vals.get("price_cents"):
                return int(vals["price_cents"]), True
        for r in ((props.get("recurrences") or {}).get("enabled") or []):
            if r.get("recurrence") == "monthly" and r.get("price_cents"):
                return int(r["price_cents"]), True
        raise ValueError(f"{permalink} is a membership with no monthly tier price — a page "
                         "that would read as free")
    cents = props.get("price_cents")
    if not cents:
        raise ValueError(f"{permalink} read as {cents!r} cents — refusing to price a page "
                         "off a figure that is missing or zero")
    return int(cents), False


def display(cents):
    """700 -> '$7'. 1250 -> '$12.50'. Whole dollars lose the '.00', as the site writes.

    The examples are deliberately not any SKU's real figure: a doctest-shaped comment is
    exactly where a stale price hides, because nobody re-reads a docstring for drift.
    """
    if cents % 100 == 0:
        return f"${cents // 100:,}"
    return f"${cents / 100:,.2f}"


def usd(cents):
    """The schema.org form: always two decimals, no separators, no currency symbol."""
    return f"{cents / 100:.2f}"


def _cache():
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


def read_live(permalink):
    if permalink not in KNOWN:
        raise ValueError(f"{permalink} is not a SKU this repository prices — add it to "
                         "live_price.KNOWN deliberately or do not price it")
    cents, recurring = cents_from_props(public_props(permalink), permalink)
    return {"cents": cents, "recurring": recurring, "read_at": _now(),
            "what": KNOWN[permalink]}


_MEMO = {}


def price(permalink, allow_cache=True, quiet=False):
    """-> dict with cents / display / usd / recurring / read_at / source.

    Live if the network allows, cached otherwise, and an exception if neither. There is
    deliberately no third branch.

    Memoised per process, and that is a correctness property rather than a speed one: a
    full build renders the same SKU into more than one page, and two reads seconds apart
    could in principle disagree. One build must publish ONE figure everywhere or the gate
    that compares the site to Gumroad has nothing coherent to compare.
    """
    if permalink in _MEMO:
        return dict(_MEMO[permalink])
    if permalink not in KNOWN:
        raise ValueError(f"{permalink} is not a SKU this repository prices")
    try:
        rec = read_live(permalink)
        rec["source"] = "live"
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        if not allow_cache:
            raise
        cached = _cache().get(permalink)
        if not cached:
            raise SystemExit(
                f"cannot read {permalink} live ({e}) and there is no cached reading in "
                f"{CACHE}. Refusing to publish a page that prices a product off nothing. "
                f"Run `python3 scripts/live_price.py --refresh` on a machine with network.")
        rec = dict(cached)
        rec["source"] = "cache"
        if not quiet:
            print(f"  live_price: {permalink} read from CACHE of {rec['read_at']} "
                  f"({e}) — the published page will carry that reading, and "
                  f"sku_price_gate.py is what will notice if it has moved", file=sys.stderr)
    rec["permalink"] = permalink
    rec["url"] = STORE + permalink
    rec["display"] = display(rec["cents"])
    rec["usd"] = usd(rec["cents"])
    _MEMO[permalink] = dict(rec)
    return rec


def refresh():
    """Re-read every known SKU and rewrite the cache. Refuses to write a partial file."""
    fresh = {}
    for perma in sorted(KNOWN):
        fresh[perma] = read_live(perma)
        print(f"  {perma:8s} {display(fresh[perma]['cents']):>10s}"
              f"{' / month' if fresh[perma]['recurring'] else '':9s}  {KNOWN[perma]}")
    CACHE.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n")
    return fresh


# ------------------------------------------------------------------ the structured data

def product_jsonld(rec, name, description, extra_offer=None):
    """A schema.org Product whose Offer price came out of `price()` and nowhere else.

    ONLY CALL THIS ON A PAGE THAT SHOWS THE SAME FIGURE TO A HUMAN. Google's structured
    data policy is explicit that marked-up content must be visible to the reader, and a
    Product block declaring a price no visitor can see is the shape that loses a rich
    result rather than winning one. Before 2026-08-22 this site had exactly one Product
    block, on `index.html`, declaring the report's price — and no page on the site
    displayed any price at all. So the one piece of commercial markup this repository
    published was already in that condition, and had been since it was written.

    Deliberately absent: `aggregateRating` and `review`. Nothing here has been bought or
    reviewed, and inventing either would be a lie as well as a lost rich result.
    """
    offer = {
        "@type": "Offer",
        "price": rec["usd"],
        "priceCurrency": "USD",
        "availability": "https://schema.org/InStock",
        "url": rec["url"],
        "seller": {"@type": "Organization", "name": "Sujeito Operator",
                   "url": "https://github.com/sujeito-operator"},
    }
    if rec["recurring"]:
        # "that figure, and it recurs every 1 month" — said in the vocabulary rather than in the
        # name, so a parser that ignores the name still bills the reader correctly.
        offer["priceSpecification"] = {
            "@type": "UnitPriceSpecification",
            "price": rec["usd"],
            "priceCurrency": "USD",
            "billingDuration": 1,
            "billingIncrement": 1,
            "unitText": "month",
            "referenceQuantity": {"@type": "QuantitativeValue", "value": 1,
                                  "unitCode": "MON"},
        }
    if extra_offer:
        offer.update(extra_offer)
    return json.dumps({
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": name,
        "description": description,
        "url": rec["url"],
        "isAccessibleForFree": False,
        "brand": {"@type": "Organization", "name": "Sujeito Operator",
                  "url": "https://github.com/sujeito-operator"},
        "offers": offer,
    }, indent=2)


# ---------------------------------------------------------------------------- selftest

def selftest():
    ok = fail = 0

    def check(what, got, want):
        nonlocal ok, fail
        if got == want:
            ok += 1
        else:
            fail += 1
            print(f"  FAIL {what}: got {got!r} want {want!r}")

    def raises(what, fn):
        nonlocal ok, fail
        try:
            fn()
        except (ValueError, SystemExit):
            ok += 1
            return
        fail += 1
        print(f"  FAIL {what}: returned instead of refusing")

    # The defect this module was written around: a tiered membership whose product-level
    # price_cents is 0. The tier must win, and 0 must never reach a page.
    tiered = {"is_tiered_membership": True, "price_cents": 0,
              "options": [{"recurrence_price_values": {"monthly": {"price_cents": 9900}}}]}
    check("tiered membership reads the tier, not price_cents", cents_from_props(tiered),
          (9900, True))

    # The other shape Gumroad serves memberships in.
    recurrences = {"is_recurring_billing": True, "price_cents": 0,
                   "recurrences": {"enabled": [{"recurrence": "yearly", "price_cents": 99000},
                                               {"recurrence": "monthly", "price_cents": 9900}]}}
    check("recurrences.enabled monthly is found past a yearly tier",
          cents_from_props(recurrences), (9900, True))

    check("a one-off reads price_cents", cents_from_props({"price_cents": 14900}),
          (14900, False))

    # A membership with no monthly figure must RAISE. Returning 0 would publish "free".
    raises("membership with no monthly tier refuses rather than returning 0",
           lambda: cents_from_props({"is_tiered_membership": True, "price_cents": 0,
                                     "options": []}, "zyoqbc"))
    raises("a one-off reading 0 refuses rather than publishing free",
           lambda: cents_from_props({"price_cents": 0}, "xlvfeb"))
    raises("a one-off with no price field refuses", lambda: cents_from_props({}, "xlvfeb"))

    # The allowlist is a gate, not a formality.
    raises("an unknown permalink is refused", lambda: price("nosuch", allow_cache=False))
    raises("read_live refuses an unknown permalink", lambda: read_live("nosuch"))

    check("whole dollars lose the decimals", display(9900), "$99")
    check("part dollars keep them", display(14950), "$149.50")
    check("thousands get a separator", display(124900), "$1,249")
    check("schema price is always two decimals", usd(9900), "99.00")
    check("schema price of a part dollar", usd(14950), "149.50")

    # The markup. A recurring SKU must carry the recurrence in the vocabulary; a one-off
    # must NOT, because a UnitPriceSpecification on a one-off says it bills monthly.
    mrec = {"cents": 9900, "recurring": True, "usd": "99.00",
            "url": STORE + "zyoqbc", "read_at": "x", "permalink": "zyoqbc"}
    m = json.loads(product_jsonld(mrec, "monitor", "d"))
    check("recurring offer carries a UnitPriceSpecification",
          m["offers"]["priceSpecification"]["@type"], "UnitPriceSpecification")
    check("recurring offer bills monthly",
          m["offers"]["priceSpecification"]["unitText"], "month")
    check("recurring offer price matches the live read", m["offers"]["price"], "99.00")
    check("product url is the SKU permalink", m["url"], STORE + "zyoqbc")
    check("no invented rating", "aggregateRating" in m, False)
    check("no invented review", "review" in m, False)

    orec = {"cents": 14900, "recurring": False, "usd": "149.00",
            "url": STORE + "xlvfeb", "read_at": "x", "permalink": "xlvfeb"}
    o = json.loads(product_jsonld(orec, "audit", "d"))
    check("a one-off carries NO recurrence spec",
          "priceSpecification" in o["offers"], False)
    check("one-off offer price matches the live read", o["offers"]["price"], "149.00")

    # NO DOLLAR FIGURE ANYWHERE IN THIS FILE — code, comment or docstring — MAY EQUAL A
    # PRICE THIS REPOSITORY PUBLISHES. Not "no `$` character": the examples in `display`
    # have to read like something. The hazard is specific and it is drift, so the arm is
    # specific: the cheapest way to quiet a red price gate is to type the real number into
    # a comment here, and then the file that exists to stop stale prices carries one.
    body = pathlib.Path(__file__).read_text().split("def selftest()")[0]
    literals = set(re.findall(r"\$\d+(?:,\d{3})*(?:\.\d+)?", body))
    cache = _cache()
    check("the price cache exists, so this arm can actually run", bool(cache), True)
    real = {display(r["cents"]) for r in cache.values()}
    real |= {f"${r['cents'] // 100:,}" for r in cache.values()}
    check("no dollar literal in this file equals a live SKU price",
          sorted(literals & real), [])

    # The cache, if it exists, must only contain SKUs on the allowlist and must carry a
    # reading time for each — a cached price with no timestamp cannot be judged stale.
    for perma, rec in _cache().items():
        check(f"cached {perma} is on the allowlist", perma in KNOWN, True)
        check(f"cached {perma} carries a read_at", bool(rec.get("read_at")), True)
        check(f"cached {perma} carries cents", isinstance(rec.get("cents"), int), True)

    print(f"live_price selftest: {ok} passed, {fail} failed")
    return 1 if fail else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.refresh:
        refresh()
        return 0
    if a.show:
        for perma in sorted(KNOWN):
            r = price(perma)
            print(f"  {perma:8s} {r['display']:>10s}"
                  f"{' / month' if r['recurring'] else '':9s}  {r['source']:5s}  "
                  f"{r['read_at']}  {r['what']}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
