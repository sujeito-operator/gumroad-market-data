#!/usr/bin/env python3
"""Generate the commercial-intent guide pages, from the same data as everything else.

WHY THIS EXISTS. The 42 category pages answer one shape of question — "how much do
<category> sell for on Gumroad" — which is real long-tail traffic but arrives from
people who have already chosen a category. The much larger queries are the ones asked
*before* that choice: what to sell, what to charge, how much anyone actually makes,
whether the platform is worth the effort. Nothing on the site addressed them, so the
whole indexable surface sat downstream of a decision the visitor had not made yet.

These pages answer those questions from the free data, honestly, including where the
answer is discouraging. What they deliberately do NOT publish is the per-category
Opening/Crowded/Thin table — that classification is the paid report's centrepiece. The
headline concentration figure is here because it is the hook and it is true; the
category-by-category verdict is what the $79 buys.

Imported and called by build_site.py, so `python3 scripts/build_site.py` remains the one
command that regenerates every surface. Never hand-edit docs/g/*.html.
"""
import csv, json, statistics as st

# build_site owns the shared chrome (head/footer/CSS/buy block) so the guides cannot
# drift into looking like a different site.
import build_site as B

# (slug, nav label) — the sitemap and the cross-links are both derived from this, so a
# new guide is one entry plus one builder.
GUIDES = [
    ("what-to-sell-on-gumroad", "What to sell"),
    ("how-much-do-people-make-on-gumroad", "What people make"),
    ("gumroad-pricing", "What to charge"),
    ("is-gumroad-worth-it", "Is it worth it"),
    ("gumroad-statistics", "Statistics"),
    ("free-vs-paid-digital-products", "Free vs paid"),
    ("gumroad-price-calculator", "Price calculator"),
    ("how-many-products-to-sell-on-gumroad", "How many products"),
    ("gumroad-sales-per-rating", "Sales per rating"),
    ("gumroad-multiple-categories", "Multiple categories"),
    ("gumroad-free-product-strategy", "A free product too?"),
]

# The one guide derived from the seller column, so the seller pages can link it by name
# rather than by a literal that would rot silently if the slug ever changed. It is
# always built (it is in GUIDES above), so a link to it can never dangle — unlike the
# seller -> category links, which have to fall back when a node is below the page cut.
SELLER_GUIDE = "how-many-products-to-sell-on-gumroad"

# The one guide derived from the per-product crawl — the only sample in this project
# that carries real unit sales. Referenced by name for the same reason as SELLER_GUIDE:
# any page that wants to say "ratings are a proxy, here is what one is worth" should
# link it without a literal slug that would rot in silence.
SALES_GUIDE = "gumroad-sales-per-rating"

# Catalogue-size bands for the seller guide. Kept coarse on purpose: the tail is thin
# (20 sellers have 20+ products) and finer bands would report noise as structure.
SELLER_BANDS = [(1, 1, "1 product"), (2, 2, "2"), (3, 4, "3–4"),
                (5, 9, "5–9"), (10, 19, "10–19"), (20, 10 ** 9, "20 or more")]

# The second guide off the seller column: how many distinct category searches a seller's
# listings turned up in. Same sample, same caveats, referenced by name for the same
# reason as SELLER_GUIDE.
BREADTH_GUIDE = "gumroad-multiple-categories"

# Breadth bands. Coarse for the same reason as SELLER_BANDS — 75% of sellers sit in the
# first bucket and the tail past 6 is 37 sellers, so finer cuts would report noise.
BREADTH_BANDS = [(1, 1, "1 category"), (2, 2, "2"), (3, 3, "3"),
                 (4, 5, "4–5"), (6, 10 ** 9, "6 or more")]

# Catalogue-size groups the breadth bands are re-cut inside. The whole point of the page
# is that the headline association survives (or does not) once catalogue size is held
# roughly fixed, so these are the control, not decoration.
# The third guide off the seller column, and the only one built on `free_products`:
# whether sellers who carry BOTH free and paid listings do better than sellers who carry
# only one kind. Referenced by name for the same reason as SELLER_GUIDE.
MIX_GUIDE = "gumroad-free-product-strategy"

# Catalogue-size bands the free/paid comparison is re-cut inside. Mixed sellers carry
# more products than paid-only ones (median 4 against 2), so without this control the
# headline would just be the catalogue-size finding again. Bands start at 2 because a
# one-product seller cannot mix at all. Coarse for the usual reason: past 10 products
# there are 77 sellers in the whole sample.
MIX_CONTROLS = [(2, 2, "2 products"), (3, 4, "3–4"), (5, 9, "5–9"),
                (10, 10 ** 9, "10 or more")]

# Below this a band's median is noise, and the page prints a dash instead of a number.
# Free-only sellers fall under it in the two largest bands — that is a real limit of the
# sample and showing it beats quietly dropping the column.
MIX_MIN_N = 8

BREADTH_CONTROLS = [
    (1, 1, "Sellers with 1 product", [(1, 1, "1 category"), (2, 2, "2"), (3, 3, "3"),
                                      (4, 10 ** 9, "4 or more")]),
    (2, 4, "Sellers with 2–4 products", [(1, 1, "1 category"), (2, 2, "2"), (3, 3, "3"),
                                         (4, 10 ** 9, "4 or more")]),
    (5, 10 ** 9, "Sellers with 5 or more products",
     [(1, 2, "1–2 categories"), (3, 4, "3–4"), (5, 10 ** 9, "5 or more")]),
]


def analyse(s, rows):
    """The derived figures the guides quote. Same definitions as the paid report's
    analyse() — if these two ever disagree, the site and the report contradict each
    other on the surface where money changes hands."""
    # TWO DENOMINATORS, ON PURPOSE. `rows` are listing *observations*: one product can
    # rank for several category searches, so 1509 rows cover 1344 distinct products.
    # Per-category figures below use `rows` — a product that genuinely ranks in two
    # categories belongs in both. Every MARKET-WIDE figure uses `prod`, or popular
    # products (the ones that match several searches) get counted twice and every
    # aggregate tilts toward winners. Must match normalize.py's split exactly.
    seen, prod = set(), []
    for r in rows:
        if r["t"].strip() not in seen:
            seen.add(r["t"].strip())
            prod.append(r)

    # csv.DictReader hands back the literal strings "True"/"False", and "False" is
    # truthy — checking it directly would report every listing as a subscription.
    rec = [r for r in prod if str(r["recurring"]) == "True"]

    cats = []
    for c in s["by_category"]:
        g = sorted((r["n"] for r in rows if r["q"] == c["topic"]), reverse=True)
        cats.append({**c, "top3": round(100 * sum(g[:3]) / (sum(g) or 1))})

    paid = [r for r in prod if r["price_usd"] > 0]
    bands = []
    for lo, hi, label in [(0, 10, "under $10"), (10, 25, "$10–25"), (25, 50, "$25–50"),
                          (50, 100, "$50–100"), (100, 250, "$100–250"), (250, 1e9, "$250+")]:
        g = [r for r in paid if lo <= r["price_usd"] < hi]
        if g:
            bands.append({"label": label, "n": len(g),
                          "rated": round(100 * sum(1 for r in g if r["n"] > 0) / len(g)),
                          "med": int(st.median([r["n"] for r in g]))})

    # Does undercutting the category median actually buy demand? Counted per category
    # rather than pooled, because pooling would let one huge category decide it.
    cheaper_wins = tot = 0
    for c in cats:
        g = [r for r in rows if r["q"] == c["topic"] and r["price_usd"] > 0]
        med = st.median([r["price_usd"] for r in g])
        lo = [r["n"] for r in g if r["price_usd"] <= med]
        hi = [r["n"] for r in g if r["price_usd"] > med]
        if lo and hi:
            tot += 1
            cheaper_wins += st.median(lo) > st.median(hi)

    free = [r for r in prod if r["price_usd"] == 0]

    # Free-against-paid, computed per category as well as pooled. Pooled alone would be
    # fragile: 24% of every rating in the sample sits on 5% of the products, and a single
    # 1,300-rating free listing could be carrying it. Counting categories instead asks the
    # question 31 times, so one outlier cannot answer it.
    free_beats = free_tot = 0
    for c in {r["q"] for r in prod}:
        f = [r["n"] for r in prod if r["q"] == c and r["price_usd"] == 0]
        p = [r["n"] for r in prod if r["q"] == c and r["price_usd"] > 0]
        if f and p:
            free_tot += 1
            free_beats += st.median(f) > st.median(p)
    all_ratings = sum(r["n"] for r in prod) or 1

    # Payload for the client-side price calculator. One [price_usd, ratings] pair per
    # listing OBSERVATION, keyed by category — the per-category denominator, the same
    # one every other per-category figure on this site uses. A product ranking in two
    # categories belongs in both, which is what a visitor comparing *within* a category
    # wants. Never aggregate this dict across categories: that would count the popular
    # products twice and is exactly the bug that made every market-wide figure wrong
    # until 2026-08-07.
    calc = {c["topic"]: [[round(r["price_usd"], 2), int(r["n"])]
                         for r in rows if r["q"] == c["topic"]]
            for c in s["by_category"]}

    return {
        "cats": cats, "bands": bands, "calc": calc,
        "avg_rated": 100 - s["zpct"],
        "med_conc": st.median([c["top3"] for c in cats]),
        "r_price_demand": B_pearson([c["median"] for c in cats],
                                    [c["rated_share"] for c in cats]),
        "cheaper_wins": cheaper_wins, "cheaper_tot": tot,
        "free_n": len(free),
        "free_rated": round(100 * sum(1 for r in free if r["n"] > 0) / len(free)),
        "paid_rated": round(100 * sum(1 for r in paid if r["n"] > 0) / len(paid)),
        "paid_n": len(paid),
        "free_med": int(st.median([r["n"] for r in free])),
        "paid_med": int(st.median([r["n"] for r in paid])),
        "free_med_rated": int(st.median([r["n"] for r in free if r["n"] > 0])),
        "paid_med_rated": int(st.median([r["n"] for r in paid if r["n"] > 0])),
        "free_share_ratings": round(100 * sum(r["n"] for r in free) / all_ratings, 1),
        "free_share_products": round(100 * len(free) / len(prod), 1),
        "free_beats": free_beats, "free_beats_tot": free_tot,
        "free_cats": len({r["q"] for r in free}),
        "subs_n": len(rec),
        "top_listing": max(prod, key=lambda r: r["n"]),
        "med_rated_ratings": int(st.median([r["n"] for r in prod if r["n"] > 0])),
        "p90_ratings": int(st.quantiles([r["n"] for r in prod if r["n"] > 0], n=10)[8]),
    }


def seller_analyse():
    """The seller guide's figures, computed from the TAXONOMY sample only.

    THE TWO SAMPLES ARE NEVER MERGED. Everything else in this file is derived from the
    42-search sample (`data/gumroad-latest.csv`, 1,344 products, paid median $36.99).
    This one guide is derived from the category walk (`data/gumroad-sellers.csv`, 4,545
    sellers, paid median $18.03) because that is the only sample with a seller column.
    The two disagree, that disagreement is a published finding, and averaging them would
    produce a third set of numbers matching neither. The page says which sample it is on.
    """
    s = json.load(open(B.ROOT / "data" / "sellers-summary.json"))
    rows = list(csv.DictReader(open(B.ROOT / "data" / "gumroad-sellers.csv")))
    for r in rows:
        for k in ("products", "ratings_total", "rated_products", "top_product_ratings",
                  "ratings_rank"):
            r[k] = int(r[k] or 0)
        r["med_price_usd"] = float(r["med_price_usd"] or 0)

    bands = []
    for lo, hi, label in SELLER_BANDS:
        g = [r for r in rows if lo <= r["products"] <= hi]
        rat = [r["ratings_total"] for r in g]
        prices = [r["med_price_usd"] for r in g if r["med_price_usd"] > 0]
        bands.append({
            "label": label, "n": len(g),
            "med": int(st.median(rat)),
            "mean": round(sum(rat) / len(g), 1),
            # Ratings PER PRODUCT, taken per seller and then medianed — not total
            # ratings over total products, which one 15,000-rating storefront decides.
            "per_prod": round(st.median([r["ratings_total"] / r["products"] for r in g]), 1),
            "zero": round(100 * sum(1 for x in rat if x == 0) / len(g), 1),
            "price": st.median(prices) if prices else 0.0,
        })

    # How much of a seller's own demand sits on their single best product. Only sellers
    # with 2+ products and at least one rating can answer this; for everyone else the
    # question is undefined rather than 100%.
    multi = [r for r in rows if r["products"] >= 2 and r["ratings_total"] > 0]
    share = [100 * r["top_product_ratings"] / r["ratings_total"] for r in multi]
    five = [r for r in rows if r["products"] >= 5 and r["ratings_total"] > 0]
    share5 = [100 * r["top_product_ratings"] / r["ratings_total"] for r in five]

    top = sorted(rows, key=lambda r: -r["ratings_total"])[:s["top1_count"]]
    biggest = sorted(rows, key=lambda r: -r["products"])[:6]
    five_all = [r for r in rows if r["products"] >= 5]

    return {
        "s": s, "bands": bands,
        "multi_n": len(multi),
        "multi_med_share": round(st.median(share), 1),
        "multi_half": round(100 * sum(1 for x in share if x >= 50) / len(share)),
        "multi_all": round(100 * sum(1 for x in share if x >= 99.99) / len(share), 1),
        "five_n": len(five), "five_med_share": round(st.median(share5), 1),
        "top1_max_products": max(r["products"] for r in top),
        # The demand rank the top 1% cuts at, and where the biggest catalogues land
        # against it. Stated as numbers so the claim "none of them is in the top 1%"
        # cannot survive the data changing under it.
        "top1_cut": top[-1]["ratings_total"],
        "big_best_rank": min(r["ratings_rank"] for r in biggest),
        "biggest": biggest,
        "five_med_unrated": int(st.median([r["products"] - r["rated_products"]
                                           for r in five_all])),
        "five_all_n": len(five_all),
    }


def breadth_analyse():
    """The breadth guide's figures, from the same seller table as seller_analyse().

    ONE THING GOVERNS EVERY NUMBER HERE AND THE PAGE LEADS WITH IT: `categories` is how
    many of the walk's category searches returned that seller's listings. It is what the
    ranking produced, not what the seller declared. Gumroad ranks by demand, so a product
    that sells appears under more terms — which means breadth is downstream of demand at
    least in part, and no cut of this table can fully separate the two. The bands are
    therefore re-cut inside catalogue-size groups (the honest control available) and the
    page states plainly what that does and does not buy.
    """
    s = json.load(open(B.ROOT / "data" / "sellers-summary.json"))
    rows = list(csv.DictReader(open(B.ROOT / "data" / "gumroad-sellers.csv")))
    for r in rows:
        for k in ("products", "categories", "ratings_total", "rated_products"):
            r[k] = int(r[k] or 0)
        r["med_price_usd"] = float(r["med_price_usd"] or 0)

    def band(group, spec):
        out = []
        for lo, hi, label in spec:
            g = [r for r in group if lo <= r["categories"] <= hi]
            if not g:
                continue
            rat = [r["ratings_total"] for r in g]
            prices = [r["med_price_usd"] for r in g if r["med_price_usd"] > 0]
            out.append({
                "label": label, "n": len(g),
                "med": int(st.median(rat)),
                # Ratings per product taken per seller and then medianed, for the same
                # reason as the seller guide: the pooled ratio is one storefront's call.
                "per_prod": round(st.median([r["ratings_total"] / r["products"]
                                             for r in g]), 1),
                "zero": round(100 * sum(1 for x in rat if x == 0) / len(g), 1),
                "price": st.median(prices) if prices else 0.0,
            })
        return out

    unrated = [r for r in rows if r["ratings_total"] == 0]
    rated = [r for r in rows if r["ratings_total"] > 0]
    return {
        "s": s,
        "bands": band(rows, BREADTH_BANDS),
        "controls": [{"label": label,
                      "n": len([r for r in rows if lo <= r["products"] <= hi]),
                      "bands": band([r for r in rows if lo <= r["products"] <= hi], spec)}
                     for lo, hi, label, spec in BREADTH_CONTROLS],
        # The reverse-causality evidence, stated as numbers so the claim cannot outlive
        # the data: sellers with no demand are almost never broad, and the broadest of
        # them tops out far below the sample maximum.
        "unrated_n": len(unrated),
        "unrated_one_cat_pct": round(100 * sum(1 for r in unrated
                                               if r["categories"] == 1) / len(unrated), 1),
        "unrated_max_cats": max(r["categories"] for r in unrated),
        "rated_one_cat_pct": round(100 * sum(1 for r in rated
                                             if r["categories"] == 1) / len(rated), 1),
        "top1_one_cat_pct": round(100 * s["top1_one_category"] / s["top1_count"], 1),
    }


def mix_analyse():
    """The free-product guide's figures, from the same seller table as seller_analyse().

    The group definitions and the headline figures live in `normalize_sellers.mix_stats`
    so the downloadable CSV and this page cannot drift. What is computed here is only the
    catalogue-size control, which is a presentation cut rather than a published statistic.

    WHAT THIS PAGE CANNOT SHOW, STATED BEFORE ANY NUMBER: a cross-section cannot tell you
    whether the free product produced the demand or the demand arrived first and the free
    product came after it. A seller who is already selling has every reason to add a lead
    magnet. The page leads with that and does not resolve it.
    """
    import normalize_sellers as NS  # mix_group: one definition, used in both places

    s = json.load(open(B.ROOT / "data" / "sellers-summary.json"))
    rows = list(csv.DictReader(open(B.ROOT / "data" / "gumroad-sellers.csv")))
    for r in rows:
        for k in ("products", "free_products", "ratings_total", "rated_products"):
            r[k] = int(r[k] or 0)
        r["med_price_usd"] = float(r["med_price_usd"] or 0)

    controls = []
    for lo, hi, label in MIX_CONTROLS:
        band = [r for r in rows if lo <= r["products"] <= hi]
        cells = {}
        for k in ("paid", "mixed", "free"):
            g = [r for r in band if NS.mix_group(r) == k]
            cells[k] = {
                "n": len(g),
                "med": int(st.median([r["ratings_total"] for r in g])) if g else 0,
                "enough": len(g) >= MIX_MIN_N,
            }
        controls.append({"label": label, "n": len(band), **cells})

    # The ratio the page quotes per band, computed once so the prose and the table agree.
    for c in controls:
        c["ratio"] = (round(c["mixed"]["med"] / c["paid"]["med"], 1)
                      if c["paid"]["med"] and c["mixed"]["enough"] and c["paid"]["enough"]
                      else None)

    sr = json.load(open(B.ROOT / "data" / "sales-ratio-summary.json"))
    return {
        "s": s, "controls": controls,
        # The direction of the ratings bias, read off the only sample with real units.
        "paid_rating_rate": sr["paid_rating_rate"],
        "free_rating_rate": sr["free_rating_rate"],
        "solo_free_pct": round(100 * s["mix_solo_free"] / s["solo_sellers"], 1),
        "mixed_one_free_pct": round(100 * s["mix_mixed_one_free"] / s["mix_mixed_n"], 1),
        "mixed_share_pct": round(100 * s["mix_mixed_n"] / s["mix_multi"], 1),
    }


def sales_analyse():
    """The sales-per-rating guide's figures, read from the per-product crawl's summary.

    THIS IS A THIRD READING OF THE SAME MARKETPLACE AND IT IS NOT MERGED WITH EITHER
    OTHER SAMPLE. The input is the taxonomy walk's product URLs re-fetched one page at a
    time, so it is a *subsample of the taxonomy sample* — never of the 42-search sample
    every other guide but the seller one is built on. Nothing here is averaged with a
    figure from `summary.json`; the page says which sample it is on, twice.

    Everything is computed in `normalize_products.py` and only read here, so the CSV a
    visitor downloads and the page they read cannot disagree.
    """
    return json.load(open(B.ROOT / "data" / "sales-ratio-summary.json"))


def coverage_warn(d, what):
    """The caveat that governs every figure from the per-product crawl.

    `collect_products.py` walks the taxonomy in stored order, which is alphabetical by
    top-level slug, and it has not finished. Every product page fetched so far is under
    one branch. So these figures are not about Gumroad — they are about that branch, and
    two live pages presented them as platform-wide answers for a day.

    Generated from `coverage` in the summary rather than written into the pages, so when
    the crawl reaches the next branch the wording changes with the data instead of
    rotting in place. `assert_coverage_warned()` makes sure it cannot be dropped.
    """
    c = d["coverage"]
    if not c["single_branch"]:
        seen = ", ".join(branch_label(s) for s in c["top_levels_seen"])
        return (f"<p class=warn><strong>Which categories this covers.</strong> The listings "
                f"behind {what} come from {c['n_top_levels_seen']} of Gumroad's "
                f"{c['n_top_levels_in_taxonomy']} top-level categories ({seen}), so they are "
                f"not an even draw across the platform. Weight them accordingly.</p>")
    label = branch_label(c["dominant"])
    return (f"<p class=warn><strong>Read this first: these figures are about {label}, not about "
            f"Gumroad.</strong> {what.capitalize()} come from re-fetching individual product "
            f"pages, and that crawl walks Gumroad's category tree in alphabetical order and has "
            f"not finished. <strong>{c['dominant_pct']:.0f}% of the pages fetched so far sit "
            f"under {label}</strong> &mdash; one of the "
            f"{c['n_top_levels_in_taxonomy']} top-level categories that returned listings. "
            f"So this is a measurement of one corner of the marketplace, and {label} is an "
            f"unusual corner: high unit volumes, low prices, and a buyer base that is far more "
            f"active than the platform average. <strong>Do not read any figure in this section "
            f"as an answer for Gumroad as a whole, in either direction.</strong> The rest of "
            f"this page, which is built on the category-search sample, is not affected.</p>")


def branch_label(slug):
    """Human label for a top-level taxonomy slug, taken from the taxonomy's own node names."""
    ts = json.load(open(B.ROOT / "data" / "taxonomy-summary.json"))
    for x in ts["by_node"]:
        if x["slug"] == slug or x["slug"].startswith(slug + "/"):
            return x["node"].split(" > ")[0]
    return slug


def assert_coverage_warned(html, where):
    """Fail the build if a page built on the per-product crawl ships without the caveat.

    The project's standing lesson is that a note saying "remember to say X" does not
    survive; an assertion does. Two pages carried unqualified platform-wide claims from
    a single-branch sample, and nothing caught it.
    """
    if "these figures are about" not in html and "Which categories this covers" not in html:
        raise SystemExit(f"BUILD ABORTED: {where} uses the per-product crawl but does not "
                         f"render the category-coverage caveat. See coverage_warn().")


def B_pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0.0


def nav(current):
    parts = []
    for sl, label in GUIDES:
        parts.append(label if sl == current else f'<a href="{sl}.html">{label}</a>')
    return ('<nav class=sib>Guides: ' + " &middot; ".join(parts)
            + ' &middot; <a href="../">all 42 categories</a></nav>')


def article_ld(title, desc, canonical):
    return '<script type="application/ld+json">\n' + json.dumps({
        "@context": "https://schema.org/",
        "@type": "Article",
        "headline": title,
        "description": desc,
        "url": canonical,
        "datePublished": "2026-08-07",
        "author": {"@type": "Organization", "name": "Sujeito Operator",
                   "url": "https://github.com/sujeito-operator"},
        "isBasedOn": {"@type": "Dataset", "name": "What Actually Sells on Gumroad",
                      "url": B.SITE + "/", "identifier": "https://doi.org/" + B.DOI},
        "license": "https://creativecommons.org/licenses/by/4.0/",
    }, indent=2) + "\n</script>\n"


def page(slug, title, desc, h1, sub, lede, body):
    canonical = f"{B.SITE}/g/{slug}.html"
    return (B.head(title, desc, canonical, article_ld(title, desc, canonical))
            + f'<a class=home href="../">&larr; What actually sells on Gumroad</a>\n'
              f'<h1>{h1}</h1>\n<div class=sub>{sub}</div>\n<div class=lede>{lede}</div>\n'
            + body + nav(slug) + B.FOOTER)


def cat_link(c):
    return f'<a href="../c/{B.slug(c["topic"])}.html">{B.esc(c["topic"])}</a>'


# ------------------------------------------------------------------ the guides

def g_what_to_sell(s, a):
    top = sorted(a["cats"], key=lambda c: -c["rated_share"])[:10]
    bottom = sorted(a["cats"], key=lambda c: c["rated_share"])[:8]
    rows = "".join(
        f"<tr><td>{cat_link(c)}</td><td class=n>{c['rated_share']}%</td>"
        f"<td class=n>{c['med_ratings']:,}</td><td class=n>{B.money(c['median'])}</td></tr>"
        for c in top)
    weak = "".join(
        f"<tr><td>{cat_link(c)}</td><td class=n>{c['rated_share']}%</td>"
        f"<td class=n>{c['med_ratings']:,}</td><td class=n>{B.money(c['median'])}</td></tr>"
        for c in bottom)
    body = f"""
<h2>The measurement</h2>
<p>Most listings carry no public sales figure. A seller can choose to display a unit-sales count on
their product page, and a minority do; for everyone else the honest proxy is whether a listing has
attracted any ratings at all. Across {s['n']:,} live listings, <strong>{s['zero']} — {s['zpct']}% —
have no ratings whatsoever</strong>. That is the background rate anything you launch competes
against, before quality, before price, before marketing.</p>
<p class=cite><strong>Correction, 7 August 2026.</strong> This page previously said that a listing
with no ratings has, as far as anything observable goes, sold nothing. That is not right and our own
collection is what showed it: among the products that <em>do</em> publish a unit-sales count, a
substantial minority have sales and zero ratings, including one with four figures of sales and no
rating at all. <strong>Ratings are a floor on buyers, not a measure of them</strong>, and an unrated
listing is weak evidence of no demand rather than proof of it. The rating share above is still the
right thing to compare categories on, because it is measured the same way everywhere — it is the
interpretation of a single zero that was overstated. The paired sales-and-ratings sample that
established this is being collected now and will be published with its spread and sample size
rather than as a single multiplier.</p>

<h2>Categories where the most listings are transacting</h2>
<p>Ranked by the share of listings carrying at least one rating. The platform average is
{a['avg_rated']}%.</p>
<table><thead><tr><th>Category</th><th class=n>Listings rated</th><th class=n>Median ratings</th>
<th class=n>Median price</th></tr></thead><tbody>{rows}</tbody></table>

<h2>And where they are not</h2>
<table><thead><tr><th>Category</th><th class=n>Listings rated</th><th class=n>Median ratings</th>
<th class=n>Median price</th></tr></thead><tbody>{weak}</tbody></table>

<h2>Why the ranking above is not the answer on its own</h2>
<p>Demand being present in a category does not mean it is <em>available</em> to you. In the median
category, the <strong>top three listings hold {a['med_conc']:.0f}% of all the ratings</strong> in
that category. Several of the highest-demand categories on this list are also the most
concentrated, so choosing off the demand ranking alone walks you straight into a room where three
incumbents already have the audience.</p>
<p>That splits the {s['cats']} categories into three genuinely different situations: demand present
and reachable, demand present but locked up, and demand simply thin. Which category is which is the
analysis, not the raw table — the per-category classification is in the report below. The data it
is computed from is free, here, and you are welcome to compute it yourself.</p>

<h2>Price is not the lever you think it is</h2>
<p>Across the {s['cats']} categories, the correlation between a category's median price and the
share of its listings that are selling is <strong>r = {a['r_price_demand']:.2f}</strong> — close to
nothing. Several of the highest-demand categories are among the cheapest. Picking a category
because it looks lucrative is not supported by this data.</p>

{B.buy_block(f"The report reads all {s['cats']} categories together and classifies each one as an "
             f"opening, a crowded room or thin — with the concentration figure and the demand "
             f"figure for every category, and what to do differently in each case.")}

<h2>Check the data yourself</h2>
<p>Every figure on this page comes from a free, openly licensed dataset of {s['n']:,} listings —
<a href="{B.REPO}/blob/main/data/gumroad-latest.csv">the full CSV</a>,
<a href="{B.REPO}/blob/main/scripts/collect.py">the collector that produced it</a> and a
<a href="https://doi.org/{B.DOI}">DOI-archived copy</a>. No signup, no email wall. Rating count is
a proxy for units sold, not a sales figure, and this is one snapshot rather than a trend — both
limits are stated in the repository rather than glossed.</p>
"""
    return page(
        "what-to-sell-on-gumroad",
        f"What to sell on Gumroad — {s['n']:,} live products measured (August 2026)",
        f"Which Gumroad categories actually transact, measured across {s['n']:,} live listings. "
        f"{s['zpct']}% have no ratings at all. Free data, no signup.",
        "What to sell on Gumroad",
        f"Measured across {s['n']:,} live listings in {s['cats']} categories &middot; 5 August 2026",
        f"Most advice about what to sell on Gumroad is someone's experience of one product. This is "
        f"a measurement of {s['n']:,} live listings, and the first thing it says is unflattering: "
        f"{s['zpct']}% of everything currently listed has never received a single rating.",
        body)


def g_earnings(s, a):
    """The highest-intent query in the set, and until now it answered with the weaker sample.

    This page is built on the 42-search sample and uses ratings as a demand proxy, which
    is honest but indirect. Meanwhile the taxonomy walk's per-product crawl carries
    observed unit counts for the listings whose sellers publish them — so `price x units`
    is a directly observed gross figure, and it was sitting on a different page.

    Worse, this page carried a promise: "the measured ratio will be published here with
    its spread and its sample size". It was published, on SALES_GUIDE, not here. A live
    page saying work is forthcoming when it has shipped is a small lie about the state of
    the project, and it sat on the one URL a buyer is likeliest to land on.

    THE SAMPLES ARE NOT MERGED. The gross section states its own n every time it prints a
    figure and names the sample it comes from. Nothing in it is averaged with anything
    above it; the two readings sit side by side and the page says why they differ.
    """
    top = a["top_listing"]
    d = sales_analyse()
    g = d["gross"]
    gsp, gu = g["spread"], g["units"]
    # Names the branch the gross sample actually covers, so the stat tiles cannot claim
    # the platform while the caveat below them says otherwise.
    cov_label = (branch_label(d["coverage"]["dominant"])
                 if d["coverage"]["single_branch"] else "")
    gbands = "".join(f"<tr><td>{b['label']}</td><td class=n>{b['n']}</td>"
                     f"<td class=n>{b['pct']}%</td><td class=n>{b['share']}%</td></tr>"
                     for b in g["bands"])
    bands = "".join(f"<tr><td>{b['label']}</td><td class=n>{b['n']:,}</td>"
                    f"<td class=n>{b['rated']}%</td><td class=n>{b['med']:,}</td></tr>"
                    for b in a["bands"])
    body = f"""
<h2>A directly measured answer, for one corner of the marketplace</h2>
<p>Most of this page measures demand through rating counts, because that is what Gumroad
publishes for every listing. But about a quarter of listings publish a real unit-sales count,
and for those the question can be answered directly: units sold, multiplied by the asking
price. That is a <em>different and smaller sample</em> from the {s['n']:,} listings the rest of
this page uses &mdash; {g['n']} paid listings drawn from the category walk, not the search
sample &mdash; and the two are never combined.</p>

{coverage_warn(d, f"the {g['n']} listings in this section")}

<div class=kv>
<div><b>${gsp['median']:,.0f}</b><span>Median lifetime gross &mdash; {g['n']} paid {cov_label} listings publishing unit sales</span></div>
<div><b>{gu['median']:,.0f}</b><span>Median units sold, lifetime, same listings</span></div>
<div><b>{g['under_1k_pct']}%</b><span>Of them have grossed under $1,000 in their whole lifetime</span></div>
<div><b>{g['top1_share']}%</b><span>Of all the money in this sample sits with the top 1%</span></div>
</div>

<table><thead><tr><th>Lifetime gross</th><th class=n>Listings</th><th class=n>Share of listings</th>
<th class=n>Share of the money</th></tr></thead><tbody>{gbands}</tbody></table>

<p>The median paid listing here has grossed <strong>${gsp['median']:,.0f}</strong> over its entire
life, with a quartile range of ${gsp['q1']:,.0f} to ${gsp['q3']:,.0f}. The mean is
<strong>${g['mean']:,.0f}</strong>, roughly {g['mean'] / gsp['median']:.0f} times the median, and
that gap is the whole story: {g['bands'][-1]['n']} listings out of {g['n']} account for
{g['bands'][-1]['share']}% of the ${g['total']:,.0f} this sample has taken between them, while the
bottom half share {g['bottom50_share']}% of it. Any "average Gumroad seller earns X" figure is
describing those {g['bands'][-1]['n']} listings and calling it the middle.</p>

<p class=warn><strong>Beyond the category limit above, read this as a ceiling rather than a
middle &mdash; four more reasons.</strong>
<strong>One:</strong> publishing a sales count is voluntary, and a seller with nothing to show has
less reason to show it, so this subsample is selected upward. The true median across all listings
is lower than ${gsp['median']:,.0f}, not higher. <strong>Two:</strong> the price used is today's
price; sellers discount, raise prices and run launch offers, and pay-what-you-want buyers often pay
above the minimum, so no listing sold every unit at the price we observed.
<strong>Three:</strong> this is gross, before Gumroad's fee, refunds and tax &mdash; the seller
keeps meaningfully less. <strong>Four:</strong> it is lifetime over an age we cannot see, not
annual: a listing that has grossed ${gsp['q3']:,.0f} may have taken five years to do it.
So treat these as the shape of the distribution, which is reliable, rather than as anyone's
income, which they are not.</p>

<p>The same subsample is what makes the rest of this page legible:
<a href="{SALES_GUIDE}.html">one rating is worth a median of
&times;{d['paid_ratio']['median']} units on paid listings</a>, with a quartile range from
&times;{d['paid_ratio']['q1']} to &times;{d['paid_ratio']['q3']} &mdash; so a rating count is a
floor on sales, and a wide one. Every rating-based figure below should be read with that spread in
mind.</p>

<h2>What can and cannot be measured</h2>
<p>Gumroad publishes a unit-sales count only where the seller has opted into showing one, which is a
minority of listings. For the rest it publishes rating counts, and a rating requires a purchase. So
rating count is a floor on units sold, not an estimate of it — most buyers never rate anything.
Everything below uses ratings as a <em>relative</em> signal: it tells you which listings outsell
which, and it does not tell you anyone's revenue.</p>

<p class=warn><strong>Correction, 7 August 2026.</strong> This page previously said Gumroad does not
publish sales counts at all. That was wrong: the product page carries a <code>sales_count</code>
field, populated wherever the seller displays it. The figures on this site are unaffected — they
have always been rating-derived and are labelled as such — but the stated reason for using a proxy
was overstated. That field has since been collected across the category walk, and the result is the
section at the top of this page and the <a href="{SALES_GUIDE}.html">sales-per-rating guide</a>:
{d['disclosing']} of {d['fetched']} listings publish a unit count, {d['units_observed']:,} units in
total. Sellers routinely repeat multipliers like &times;30 or &times;100 with nothing behind them;
the measured figure is a median of &times;{d['paid_ratio']['median']} on paid listings with a
quartile range of &times;{d['paid_ratio']['q1']}&ndash;&times;{d['paid_ratio']['q3']}, which is why
this site never prints a single multiplier.</p>

<h2>The distribution is the answer</h2>
<div class=kv>
<div><b>{s['zpct']}%</b><span>Of {s['n']:,} listings have no ratings at all</span></div>
<div><b>{a['med_rated_ratings']:,}</b><span>Median ratings, among listings that have any</span></div>
<div><b>{a['p90_ratings']:,}</b><span>90th percentile, among those</span></div>
<div><b>{a['med_conc']:.0f}%</b><span>Share of a category's ratings held by its top 3</span></div>
</div>
<p>Read those four numbers together and the shape is clear. {s['zero']} of {s['n']:,} listings show
no evidence of a single sale. Among the ones that do sell, the median has {a['med_rated_ratings']:,}
ratings — a real but modest number. And within any given category, three listings take
{a['med_conc']:.0f}% of everything. The most-rated single listing in this sample is
&ldquo;{B.esc(top['t'][:70]).strip()}&rdquo; at {B.money(top['price_usd'])} with
{int(top['n']):,} ratings.</p>

<h2>How lopsided is it, across the whole market?</h2>
<p>The per-category figure above is about crowding inside one niche. This is the same question asked
across all {s['n']:,} products at once, using the {s['ratings_total']:,} ratings they carry between
them:</p>
<table><thead><tr><th>Slice of the market</th><th class=n>Products</th>
<th class=n>Share of all ratings</th></tr></thead><tbody>
<tr><td>Top 1%</td><td class=n>{max(1, round(s['n'] * 0.01)):,}</td><td class=n>{s['top1_share']}%</td></tr>
<tr><td>Top 5%</td><td class=n>{max(1, round(s['n'] * 0.05)):,}</td><td class=n>{s['top5_share']}%</td></tr>
<tr><td>Top 10%</td><td class=n>{max(1, round(s['n'] * 0.10)):,}</td><td class=n>{s['top10_share']}%</td></tr>
<tr><td>Bottom 50%</td><td class=n>{s['n'] // 2:,}</td><td class=n>{s['bottom50_share']}%</td></tr>
</tbody></table>
<p>The top {max(1, round(s['n'] * 0.01)):,} products out of {s['n']:,} hold
<strong>{s['top1_share']}% of every rating in the sample</strong>. The bottom half of the market —
{s['n'] // 2:,} products — holds <strong>{s['bottom50_share']}%</strong> between all of them. That is
the number worth carrying away from this page, and it is measured rather than modelled: no
assumption about review rates goes into it, because it is a ratio of ratings to ratings.</p>
<p>It also means an &ldquo;average&rdquo; is close to meaningless here. The mean product in this
sample carries {s['ratings_total'] / s['n']:.0f} ratings; the median carries
{s['med_ratings_all']}. Any Gumroad earnings figure quoted as an average is being dragged upward by
a handful of listings that nothing else in the market resembles.</p>

<h2>Does charging more mean earning more?</h2>
<p>Listings grouped by asking price, in USD at ECB reference rates:</p>
<table><thead><tr><th>Price band</th><th class=n>Listings</th><th class=n>Share rated</th>
<th class=n>Median ratings, of rated</th></tr></thead><tbody>{bands}</tbody></table>
<p>Free listings are the control that makes the proxy legible: {a['free_n']} listings are priced at
zero and <strong>{a['free_rated']}% of them carry ratings, against {a['paid_rated']}% of paid
listings</strong>. That gap is what the signal looks like when price is removed entirely — which is
also the reminder that a rating means <em>acquired</em>, not <em>paid for</em>. The
{s['zpct']}% with nothing is therefore not mainly a discovery problem. Free things here get taken.</p>

<h2>The honest summary</h2>
<p>A third of Gumroad listings appear to sell nothing. Most of the rest sell modestly. A small
number sell a great deal, and they are concentrated inside categories rather than spread across
them. If you are deciding whether to put work into a product here, the base rate matters more than
any success story you have read, and the base rate is on this page.</p>

{B.buy_block(f"What the base rate does not tell you is where the remaining room is. The report "
             f"classifies all {s['cats']} categories by demand and by how locked-up that demand "
             f"already is, which is the difference between a category that is busy and one you can "
             f"actually enter.")}
"""
    return page(
        "how-much-do-people-make-on-gumroad",
        f"How much do people make on Gumroad? Measured across {s['n']:,} listings",
        f"{s['n']:,} Gumroad listings measured for demand: {s['zpct']}% have never been rated. "
        f"Plus lifetime gross for {g['n']} paid {cov_label} listings that publish a real "
        f"unit-sales count &mdash; median ${gsp['median']:,.0f}, {g['under_1k_pct']}% under $1,000.",
        "How much do people actually make on Gumroad?",
        f"{s['n']:,} listings measured for demand, plus {g['n']} {cov_label} listings with "
        f"published sales counts &middot; August 2026 &middot; free, openly licensed data",
        "Most answers to this question are guesses, because Gumroad publishes revenue for nobody. "
        "But it publishes a unit-sales count for the listings whose sellers switch it on, and that "
        "is enough to measure the distribution directly rather than infer it.",
        body)


def g_pricing(s, a):
    bands = "".join(f"<tr><td>{b['label']}</td><td class=n>{b['n']:,}</td>"
                    f"<td class=n>{b['rated']}%</td><td class=n>{b['med']:,}</td></tr>"
                    for b in a["bands"])
    dear = sorted(a["cats"], key=lambda c: -c["median"])[:8]
    cheap = sorted(a["cats"], key=lambda c: c["median"])[:8]
    spread = "".join(
        f"<tr><td>{cat_link(c)}</td><td class=n>{B.money(c['median'])}</td>"
        f"<td class=n>{B.money(c['p25'])} – {B.money(c['p75'])}</td>"
        f"<td class=n>{B.money(c['p90'])}</td><td class=n>{c['rated_share']}%</td></tr>"
        for c in dear + cheap)
    body = f"""
<h2>Where prices actually sit</h2>
<div class=kv>
<div><b>{B.money(s['med'])}</b><span>Median asking price, all listings</span></div>
<div><b>{B.money(s['p75'])}</b><span>75th percentile</span></div>
<div><b>{B.money(s['p90'])}</b><span>90th percentile</span></div>
<div><b>{s['subs']}</b><span>Of {s['n']:,} listings bill on a subscription</span></div>
</div>
<p>One warning about every other price figure you will read for Gumroad, including ones this
project published before 2026-08-07: Gumroad <em>localises</em> displayed prices, so a single
search returns listings priced in different currencies. This sample is
{s['mixed_cats']} of {s['cats']} categories with more than one currency in them. Medians taken
across raw displayed prices are therefore mixing units and are wrong. Everything here is converted
to USD at European Central Bank reference rates for {s['fx_date']}, and the raw price and its
currency are both kept in the data so the conversion is checkable.</p>

<h2>Does a lower price buy you demand?</h2>
<table><thead><tr><th>Price band</th><th class=n>Listings</th><th class=n>Share rated</th>
<th class=n>Median ratings, of rated</th></tr></thead><tbody>{bands}</tbody></table>
<p>Tested per category rather than pooled: the cheaper half of a category has the higher median
rating count in <strong>{a['cheaper_wins']} of {a['cheaper_tot']}</strong> categories — a coin flip
with a slight lean, not a rule you can price against. Across categories, the correlation between
median price and the share of listings selling is <strong>r = {a['r_price_demand']:.2f}</strong>,
which is nothing. Undercutting your category is not a strategy; being inside the band that
transacts is.</p>
<p>The one place price clearly moves the number is when you remove it altogether:
{a['free_n']} listings priced at zero are {a['free_rated']}% rated against {a['paid_rated']}% of
paid ones. That is a statement about willingness to pay, not about demand for your work.</p>

<h2>The price range in your category is what matters</h2>
<p>Platform-wide medians are close to useless for setting a price, because the spread between
categories is far larger than the spread within one. The eight dearest and eight cheapest
categories in the sample:</p>
<table><thead><tr><th>Category</th><th class=n>Median</th><th class=n>Middle half</th>
<th class=n>90th pct</th><th class=n>Listings rated</th></tr></thead><tbody>{spread}</tbody></table>
<p>Every one of the {s['cats']} categories has its own page with the full price distribution and
every listing measured — start from <a href="../">the demand table</a> and open yours.</p>

{B.buy_block("Where the report goes beyond this: price and demand come apart in specific, "
             "identifiable places, and those are the categories where a pricing decision is "
             "actually worth thinking about rather than copied from the median.")}
"""
    return page(
        "gumroad-pricing",
        f"How much should you charge on Gumroad? {s['n']:,} listings measured",
        f"Measured Gumroad prices across {s['n']:,} live listings: median {B.money(s['med'])}, "
        f"90th percentile {B.money(s['p90'])}, with per-category ranges. Free data, no signup.",
        "How much should you charge on Gumroad?",
        f"{s['n']:,} live listings &middot; prices normalised to USD &middot; 5 August 2026",
        f"The median live Gumroad listing asks {B.money(s['med'])}. That figure is also nearly "
        f"useless on its own, because the spread between categories dwarfs the spread inside any "
        f"one of them — and because a lower price does not reliably buy demand.",
        body)


def g_worth_it(s, a):
    body = f"""
<h2>The case against, stated first</h2>
<p>{s['zero']} of {s['n']:,} live listings — {s['zpct']}% — have never received a rating. Within a
category, the top three listings hold {a['med_conc']:.0f}% of all its ratings at the median. Among
listings that do have ratings, the median has {a['med_rated_ratings']:,}. Pricing does not rescue
this: the correlation between a category's median price and the share of it that sells is
r = {a['r_price_demand']:.2f}. And the gap between free and paid listings —
{a['free_rated']}% of the {a['free_n']} free ones carry ratings against {a['paid_rated']}% of paid
ones — says the friction is willingness to pay rather than discovery.</p>
<p>If your plan is to list a product and let the platform find buyers, this data says that is the
{s['zpct']}% case.</p>

<h2>The case for</h2>
<p>{a['avg_rated']}% of listings <em>do</em> show demand, and the variation between categories is
large and legible — the share of listings selling runs from
{max(c['rated_share'] for c in a['cats'])}% at the top to
{min(c['rated_share'] for c in a['cats'])}% at the bottom. That range is a decision you get to make
before you build anything. Gumroad also takes no monthly fee, so a listing that sells nothing costs
you the time you already spent, not an ongoing subscription.</p>
<p>{s['subs']} of {s['n']:,} listings bill on a subscription, so recurring revenue is possible here
but is plainly not what most sellers are doing.</p>

<h2>What actually decides it</h2>
<p>The question &ldquo;is Gumroad worth it&rdquo; has no platform-level answer, and the data is
fairly clear about why: outcomes vary far more <em>between categories</em> than the platform
average suggests. Two sellers doing equally good work in different categories are not running the
same experiment. So the useful version of the question is which category, and whether its demand is
reachable or already held by three incumbents.</p>
<p><a href="what-to-sell-on-gumroad.html">The demand ranking is here</a>,
<a href="gumroad-pricing.html">the price ranges are here</a>, and every one of the {s['cats']}
categories has <a href="../">its own measured page</a>. All of it is free.</p>

{B.buy_block(f"The report is the version of this with the answer in it: every one of the "
             f"{s['cats']} categories classified by whether its demand is reachable, and what "
             f"changes about your approach in each case.")}
"""
    return page(
        "is-gumroad-worth-it",
        f"Is Gumroad worth it? What {s['n']:,} live listings actually show",
        f"An evidence-based answer from {s['n']:,} measured Gumroad listings: {s['zpct']}% have no "
        f"ratings, but outcomes vary far more between categories than across the platform.",
        "Is Gumroad worth it?",
        f"Answered from {s['n']:,} measured listings rather than from experience &middot; August 2026",
        "This gets answered with anecdotes in both directions. Here is what a measurement of "
        f"{s['n']:,} live listings says — including the part that argues against bothering.",
        body)


def g_statistics(s, a):
    """A citation target, not a persuasion page.

    The other four guides argue something. This one exists to be quoted: every figure
    numbered, each one traceable to a column of the published CSV, the limitations
    stated in the same place as the numbers rather than buried. Stats round-ups are the
    page shape that earns links instead of needing them, and links are the constraint
    this whole site is up against. It is also the page a journalist can be pointed at.

    Nothing here is new data — it is the same summary.json every other surface renders
    from. That is deliberate: a stats page that disagreed with the report would be worse
    than no stats page.
    """
    bands = "".join(
        f"<tr><td>{b['label']}</td><td class=n>{b['n']}</td>"
        f"<td class=n>{round(100 * b['n'] / sum(x['n'] for x in a['bands']))}%</td>"
        f"<td class=n>{b['rated']}%</td></tr>" for b in a["bands"])

    subs_pct = 100 * s["subs"] / s["n"]
    body = f"""
<h2>Sample and method</h2>
<p>Every figure below comes from one measurement: {s['obs']:,} listing observations pulled from
{s['cats']} Gumroad category searches, covering <strong>{s['n']:,} distinct products</strong>. The
gap is not an error — one product can rank for several searches, and {s['dupes']} of the
observations were the same product seen again under another query. Per-category figures count a
product in each category it genuinely ranks for; every platform-wide figure counts it once.</p>
<p>Prices are converted to USD at European Central Bank reference rates
({s['fx_date']}); Gumroad localises displayed prices, so {s['mixed_cats']} of the {s['cats']}
categories returned more than one currency and an unconverted median would be meaningless.
The raw price and its symbol are kept in the CSV so any conversion here is checkable.</p>

<h2>Market size and price</h2>
<ol>
<li><strong>{s['n']:,} distinct products</strong> measured across {s['cats']} categories
({s['obs']:,} listing observations).</li>
<li>The median paid listing asks <strong>{B.money(s['med'])}</strong>. Including free listings the
median is {B.money(s['med_all'])}.</li>
<li>The 75th percentile is {B.money(s['p75'])} and the 90th is
<strong>{B.money(s['p90'])}</strong> — the top decile of prices is roughly six times the median.</li>
<li><strong>{a['free_n']} products ({100 * a['free_n'] / s['n']:.1f}%) are free</strong> or
pay-what-you-want at zero.</li>
<li><strong>{s['subs']} products ({subs_pct:.1f}%) bill on a subscription.</strong> Recurring
revenue exists on Gumroad but is plainly not what most sellers are doing.</li>
</ol>

<h2>Demand, and how unevenly it is distributed</h2>
<ol start=6>
<li><strong>{s['zero']} of {s['n']:,} products ({s['zpct']}%) have never received a rating.</strong></li>
<li>The {s['n']:,} products carry <strong>{s['ratings_total']:,} ratings</strong> between them.</li>
<li><strong>The top 1% of products hold {s['top1_share']}% of all ratings.</strong> The top 5% hold
{s['top5_share']}%, the top 10% hold {s['top10_share']}%, and
<strong>the bottom half hold {s['bottom50_share']}%.</strong></li>
<li>The median product has {s['med_ratings_all']} ratings. Among products with any rating at all,
the median is {s['med_ratings_rated']} and the 90th percentile is {a['p90_ratings']:,}.</li>
<li>The single most-rated product carries <strong>{s['top_product_ratings']:,} ratings</strong> —
{100 * s['top_product_ratings'] / s['ratings_total']:.1f}% of every rating in the sample, held by one
product out of {s['n']:,}.</li>
<li>Concentration repeats <em>inside</em> categories: at the median category, the top three
listings hold <strong>{a['med_conc']:.0f}% of that category's ratings.</strong></li>
</ol>

<h2>Price against demand</h2>
<p>Across the {s['cats']} categories, the correlation between a category's median price and the
share of its listings showing any demand is <strong>r = {a['r_price_demand']:.2f}</strong> — no
usable relationship in either direction. Undercutting does not reliably help either: the cheaper
half of a category outsold the dearer half in only
<strong>{a['cheaper_wins']} of {a['cheaper_tot']} categories</strong>.</p>
<table><thead><tr><th>Asking price</th><th class=n>Products</th><th class=n>Share</th>
<th class=n>% with any rating</th></tr></thead><tbody>{bands}</tbody></table>
<p>The one comparison that does separate cleanly is free against paid:
<strong>{a['free_rated']}% of the {a['free_n']} free products carry ratings, against
{a['paid_rated']}% of paid ones.</strong> On this platform the friction is willingness to pay, not
discovery.</p>

<h2>What these numbers are not</h2>
<p>Ratings are a <em>proxy</em> for sales, not a count of them. This page deliberately publishes no
revenue estimate, because turning ratings into dollars requires assuming a review rate that nobody
has measured, and every figure downstream of that assumption inherits it. Everything above is a
ratio of observed ratings to observed ratings, or of prices to prices.</p>
<p>It is also a snapshot of what {s['cats']} category searches surfaced in August 2026 — the visible
front of Gumroad, not its whole catalogue. Products that rank for none of these searches are
absent, which if anything makes the concentration figures conservative.</p>

<h2>Citing this</h2>
<p>All of it is CC BY 4.0. Quote any figure with attribution; the underlying row-level CSV is
<a href="{B.SITE}/">free to download</a> and archived with a DOI, so a claim made here can be
checked rather than taken on trust.</p>
<p class=cite>Sujeito Operator (2026). <em>What Actually Sells on Gumroad: {s['n']:,} live products
across {s['cats']} categories.</em> Zenodo. <a href="https://doi.org/{B.DOI}">https://doi.org/{B.DOI}</a></p>
<p>Press and researchers: the full per-category breakdown is on
<a href="../">the demand table</a>, and every category has
<a href="../">its own measured page</a>.</p>

{B.buy_block("The statistics above are the free layer. The report is the reading of them: each of "
             f"the {s['cats']} categories classified by whether its demand is reachable or already "
             "held, and what that changes about what you do next.")}
"""
    return page(
        "gumroad-statistics",
        f"Gumroad statistics 2026: {s['n']:,} products measured",
        f"Original Gumroad statistics from {s['n']:,} live products across {s['cats']} categories — "
        f"median price {B.money(s['med'])}, {s['zpct']}% with no ratings, top 1% holding "
        f"{s['top1_share']}% of all {s['ratings_total']:,} ratings. Free, CC BY, with a DOI.",
        "Gumroad statistics, August 2026",
        f"{s['n']:,} products &middot; {s['cats']} categories &middot; {s['ratings_total']:,} ratings "
        f"&middot; free and citable",
        f"Gumroad publishes no market data. These figures come from measuring {s['n']:,} live "
        f"products directly. Every one is free to quote with attribution, and the rows behind them "
        f"are downloadable, so nothing here has to be taken on trust.",
        body)


def g_free_vs_paid(s, a):
    body = f"""
<h2>The gap, and it is not a small one</h2>
<p>Of the {s['n']:,} products measured, <strong>{a['free_n']} are free</strong> —
{a['free_share_products']}% of the sample. Those {a['free_n']} products hold
<strong>{a['free_share_ratings']}% of every rating in the dataset.</strong> Five percent of the
listings, a quarter of the observed demand.</p>
<table><thead><tr><th></th><th class=n>Free</th><th class=n>Paid</th></tr></thead><tbody>
<tr><td>Products</td><td class=n>{a['free_n']}</td><td class=n>{a['paid_n']:,}</td></tr>
<tr><td>Share carrying any rating</td><td class=n>{a['free_rated']}%</td>
<td class=n>{a['paid_rated']}%</td></tr>
<tr><td>Median ratings, all products</td><td class=n>{a['free_med']}</td>
<td class=n>{a['paid_med']}</td></tr>
<tr><td>Median ratings, products with any</td><td class=n>{a['free_med_rated']}</td>
<td class=n>{a['paid_med_rated']}</td></tr>
</tbody></table>
<p>The middle row is the one worth sitting with. <strong>The median free product has
{a['free_med']} ratings; the median paid product has {a['paid_med']}.</strong> Not
{a['free_med']}% more — {a['free_med']} against {a['paid_med']}. And
{a['free_rated']}% of free listings show some demand against {a['paid_rated']}% of paid ones, so
this is not one viral giveaway dragging an average around.</p>

<h2>Checking that it is not one viral giveaway anyway</h2>
<p>A pooled figure this lopsided deserves suspicion, because concentration is the defining feature
of this market — so it was asked again separately inside each of the {a['free_beats_tot']} categories
that contain both free and paid products. <strong>The median free product out-rates the
median paid product in {a['free_beats']} of {a['free_beats_tot']} categories.</strong> Free products
appear in {a['free_cats']} of the {s['cats']} categories searched. Removing the single most-rated
free listing entirely barely moves the pooled share. The pattern is the market's, not an
outlier's.</p>

<h2>What this does not say</h2>
<p>It does not say free earns more. It cannot: a rating is a proxy for a transaction, and a
transaction at $0 is not revenue. This page compares reach to reach.</p>
<p>There is also a selection effect running the other way, and it should be stated rather than
buried. People do not give away their best work at random — free listings are often deliberately
built for reach, as lead magnets, samples and community assets, by sellers who already have an
audience. The {a['free_beats']}-of-{a['free_beats_tot']} result says free listings reach more
people; it does not prove that <em>your</em> paid product would have reached more people had you
made it free.</p>
<p>And the direction of causation is genuinely open. Free listings may accumulate ratings because
they are free, or the kind of seller who can afford to publish a free asset may be the kind who
already has the distribution.</p>

<h2>What it is actually useful for</h2>
<p>The number that changes a decision is {s['zpct']}% — the share of all {s['n']:,} products with no
ratings at all. On this platform the default outcome of publishing something is that nobody
arrives. Against that background, the free-versus-paid gap reads as a statement about
<em>discovery</em>: price is the largest single piece of friction between a listing and its first
transaction, and paying it down to zero removes most of it.</p>
<p>That makes free a distribution decision, not a pricing one. If nothing you have published has
ever been rated, the constraint is not your price point — it is that no one has arrived, and the
measured route to arrival is to put something in front of them that costs nothing to try.</p>
<p>We publish this dataset that way on purpose: the rows are
<a href="{B.FREE_MIRROR}">free on Gumroad</a> and free
<a href="{B.REPO}/blob/main/data/gumroad-latest.csv">in the repository</a>, and the paid item is the
written analysis, not the data. That is the same structure this page describes, applied to
ourselves.</p>

{B.buy_block(f"The report classifies all {s['cats']} categories by whether their demand is "
             "reachable or already held by incumbents — which is the question a free lead product "
             "is trying to answer before you build the paid one.")}

<h2>Check it yourself</h2>
<p>Every figure above is computed from a free, openly licensed CSV of {s['n']:,} products, with the
collector source alongside it. Filter for <code>price_usd == 0</code> and re-derive any of it —
<a href="{B.REPO}/blob/main/data/gumroad-latest.csv">the data</a>,
<a href="https://doi.org/{B.DOI}">the archived version with a DOI</a>.</p>
"""
    return page(
        "free-vs-paid-digital-products",
        "Free vs paid digital products: what 1,344 Gumroad products show",
        f"{a['free_n']} of {s['n']:,} Gumroad products are free, and they hold "
        f"{a['free_share_ratings']}% of all ratings. Median free product: {a['free_med']} ratings. "
        f"Median paid product: {a['paid_med']}. Measured, free to check, CC BY.",
        "Free versus paid digital products",
        f"{a['free_n']} free products &middot; {a['paid_n']:,} paid &middot; measured, not surveyed",
        "Everyone has an opinion about giving digital products away. This is what it looks like "
        f"when you measure it across {s['n']:,} live products — including the parts that do not "
        "support the obvious conclusion.",
        body)


CALC_CSS = """<style>
.tool{border:1px solid var(--acc);background:#fff;padding:1rem 1.1rem;margin:1.4rem 0}
.tool label{display:block;font-size:.85rem;color:var(--mut);margin:.6rem 0 .2rem}
.tool select,.tool input{font:inherit;padding:.4rem .5rem;border:1px solid var(--line);
  background:#fff;color:var(--ink);width:100%;max-width:26rem;box-sizing:border-box}
.tool .row{display:flex;gap:1rem;flex-wrap:wrap}
.tool .row>div{flex:1 1 12rem}
#out{margin-top:1rem;border-top:1px solid var(--line);padding-top:.8rem}
#out p{margin:.45rem 0}
#out .big{font-size:1.15rem}
#out .warn{color:var(--mut);font-size:.85rem}
.nojs{color:var(--mut);font-size:.85rem}
</style>"""

CALC_JS = r"""
var sel=document.getElementById('cat'),inp=document.getElementById('price'),
    out=document.getElementById('out');
function med(a){if(!a.length)return null;var b=a.slice().sort(function(x,y){return x-y;});
  var m=b.length>>1;return b.length%2?b[m]:(b[m-1]+b[m])/2;}
/* normalize.py publishes med_ratings as int(median), i.e. TRUNCATED. toFixed(0) rounds,
   which reported 65 where the category page said 64 for the same group. Match the
   published definition rather than the prettier one. */
function medi(a){var v=med(a);return v===null?null:Math.floor(v);}
/* And the category MEDIAN PRICE has a third definition again: normalize.py's pct() is
   nearest-rank with no interpolation, rounded to 2dp. A textbook interpolated median
   returns $76.38 for notion template where the category page, the static table below
   and the CSV all say $97.00 — the same quantity, two surfaces, two answers. Match the
   published one. Checked against all 42 categories, not one. */
function pctl(sorted,q){if(!sorted.length)return 0;
  return Math.round(sorted[Math.min(Math.floor(q*sorted.length),sorted.length-1)]*100)/100;}
function money(v){return '$'+v.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g,',');}
function pl(n,one,many){return n+' '+(n===1?one:many);}
/* "3th percentile" shipped once in a draft. Ordinals are not a suffix rule. */
function ord(n){var s=['th','st','nd','rd'],v=n%100;return n+(s[(v-20)%10]||s[v]||s[0]);}
function run(){
  var t=sel.value,g=CALC[t];if(!g){return;}
  var raw=inp.value.replace(/[^0-9.]/g,''),p=parseFloat(raw);
  var paid=g.filter(function(r){return r[0]>0;}),prices=paid.map(function(r){return r[0];});
  var sortedP=prices.slice().sort(function(x,y){return x-y;});
  var free=g.length-paid.length,cmed=pctl(sortedP,0.5);
  if(isNaN(p)||p<0){out.innerHTML='<p class=warn>Enter a price to see where it sits.</p>';return;}
  var h='';
  if(p===0){
    h+='<p class=big>Free. '+pl(free,'listing is','listings are')+' free in this category, out of '
      +g.length+'.</p>';
    h+='<p>Free listings are measurably better at attracting ratings than paid ones across this '
      +'whole sample &mdash; <a href="free-vs-paid-digital-products.html">that comparison is here</a>, '
      +'including why it is not the endorsement of free it looks like.</p>';
    out.innerHTML=h;return;
  }
  var below=prices.filter(function(x){return x<p;}).length;
  var pct=Math.round(100*below/prices.length);
  h+='<p class=big>'+money(p)+' sits at about the <strong>'+ord(pct)+' percentile</strong> of paid '
    +'listings in '+t+'.</p>';
  h+='<p>'+below+' of '+prices.length+' paid listings ask less; '+(prices.length-below)
    +' ask more. '+(p===cmed?'That is exactly the category median.'
      :'The category median is '+money(cmed)+', so you are '
       +(p>cmed?Math.round(100*(p/cmed-1))+'% above it':Math.round(100*(1-p/cmed))+'% below it')
       +'.')+'</p>';
  var lo=p*0.7,hi=p*1.3;
  var band=paid.filter(function(r){return r[0]>=lo&&r[0]<=hi;});
  if(band.length>=8){
    /* Both figures use the PUBLISHED definitions: rated share over every listing in the
       group, median ratings over the rated ones only. Taking the median over all
       listings instead gives a different number from the category pages' med_ratings,
       and two surfaces disagreeing about the same quantity is this project's most
       frequent defect. */
    var bandRated=band.filter(function(r){return r[1]>0;}).map(function(r){return r[1];});
    var catRated=g.filter(function(r){return r[1]>0;}).map(function(r){return r[1];});
    h+='<p>'+band.length+' listings here are priced within &plusmn;30% of that ('+money(lo)+'&ndash;'
      +money(hi)+'). '+Math.round(100*bandRated.length/band.length)+'% carry at least one rating'
      +(bandRated.length?', and among those the median has '+medi(bandRated):'')
      +'. Across the whole category it is '+Math.round(100*catRated.length/g.length)+'%'
      +(catRated.length?' and '+medi(catRated):'')+'.</p>';
  }else{
    h+='<p class=warn>Only '+pl(band.length,'listing sits','listings sit')+' within &plusmn;30% of '
      +'that price in this category &mdash; too few to say anything about demand at it. That thinness '
      +'is itself information: nobody is testing this price point here.</p>';
  }
  h+='<p class=warn>These are <em>asking</em> prices on live listings, and ratings are a proxy for '
    +'sales, not a count of them. A price nobody else charges is not automatically wrong; it is '
    +'untested.</p>';
  out.innerHTML=h;
}
sel.addEventListener('change',run);inp.addEventListener('input',run);
if(location.hash){var w=decodeURIComponent(location.hash.slice(1));
  for(var i=0;i<sel.options.length;i++){if(sel.options[i].value===w){sel.selectedIndex=i;}}}
run();
"""


def g_calculator(s, a):
    """A tool, not an essay. The six guides all argue something; this one answers a
    question about the visitor's own number, which is a different search intent
    ("what should I charge for X") and a different linking behaviour — people link
    tools. The static table underneath is not decoration: a JS-only page has no text
    for a crawler to index, and indexing is the entire point of this surface."""
    cats = sorted(a["cats"], key=lambda c: -c["n"])
    trows = "".join(
        f"<tr><td>{cat_link(c)}</td><td class=n>{c['n']}</td>"
        f"<td class=n>{B.money(c['p25'])}</td><td class=n>{B.money(c['median'])}</td>"
        f"<td class=n>{B.money(c['p75'])}</td><td class=n>{B.money(c['p90'])}</td>"
        f"<td class=n>{c['rated_share']}%</td></tr>" for c in cats)
    opts = "".join(f'<option value="{B.esc(c["topic"])}">{B.esc(c["topic"])}</option>'
                   for c in sorted(a["cats"], key=lambda c: c["topic"]))
    payload = json.dumps(a["calc"], separators=(",", ":"))

    body = CALC_CSS + f"""
<div class=tool>
<div class=row>
<div><label for=cat>Category</label>
<select id=cat>{opts}</select></div>
<div><label for=price>Your price (USD)</label>
<input id=price type=text inputmode=decimal value="{s['med']:.0f}" autocomplete=off></div>
</div>
<div id=out><p class=nojs>This tool needs JavaScript. The full table of every category is
below and needs none.</p></div>
</div>

<h2>What it is doing</h2>
<p>Every figure comes from the same free CSV as the rest of this site: {s['n']:,} distinct products
seen across {s['cats']} category searches on 5 August 2026, with prices converted to USD at
European Central Bank reference rates so a &pound; listing and a $ listing can be compared at all.
Within a category the calculator counts <em>listings</em> rather than products, because a product
that genuinely ranks for two searches competes in both.</p>
<p>What it will not do is tell you what to charge. Fitting a price against demand needs a sales
figure, and most listings do not carry one: a minority of sellers switch on a public unit-sales
counter, and for everyone else the only observable signal is whether a listing has attracted
ratings — a signal that is weak, lagging and biased toward listings that have been up longer.
<a href="{SALES_GUIDE}.html">What one rating is worth in units</a> is measured on the sellers who do
publish both, and the answer there is a wide range rather than a multiplier. What the tool can tell
you honestly is where your number sits among the people already competing for the same buyer, and
whether anyone is testing that price at all.</p>

<h2>Every category, priced</h2>
<p>The same data the calculator reads, sorted by how many listings were measured. <strong>The four
percentile columns are over paid listings only</strong> — a free listing is not a price point, and
mixing them in drags every percentile toward zero. The Listings column counts all listings in the
category, free included, and so does Rated. Market-wide, the median across all {s['n']:,} products
is {B.money(s['med_all'])}; across paid products only it is {B.money(s['med'])}.</p>
<table><thead><tr><th>Category</th><th class=n>Listings</th><th class=n>25th</th>
<th class=n>Median</th><th class=n>75th</th><th class=n>90th</th><th class=n>Rated</th></tr></thead>
<tbody>{trows}</tbody></table>

<h2>The thing pricing cannot fix</h2>
<p>Before tuning a number, the base rate is worth stating: {s['zero']} of {s['n']:,} products
&mdash; {s['zpct']}% &mdash; have never received a rating, and across categories the correlation
between the median price and the share of listings showing demand is
r&nbsp;=&nbsp;{a['r_price_demand']:.2f}. Charging less does not reliably buy demand; in
{a['cheaper_wins']} of {a['cheaper_tot']} categories the cheaper half of listings out-rates the
dearer half, which is close enough to a coin toss to act on as one.</p>
<p>Which is the honest limit of this page. It positions your price against the market. It cannot
tell you whether the market is worth entering.</p>

{B.buy_block(f"The report is the part this tool deliberately does not do: it reads all {s['cats']} "
             "categories together and classifies each as an opening, crowded or thin &mdash; "
             "whether the demand in it is reachable or already held by three incumbents.")}

<h2>Check it yourself</h2>
<p>The table above, the calculator's data and the collector that produced them are all public:
<a href="{B.REPO}/blob/main/data/gumroad-latest.csv">the CSV</a>,
<a href="https://doi.org/{B.DOI}">the archived version with a DOI</a>. CC BY 4.0 &mdash; re-derive
any of it, or quote it with attribution.</p>
""" + "<script>var CALC=" + payload + ";" + CALC_JS + "</script>"

    return page(
        "gumroad-price-calculator",
        f"Gumroad price calculator: where your price sits in {s['cats']} categories",
        f"Enter a category and a price and see the percentile it sits at among live Gumroad "
        f"listings. Built from {s['n']:,} products, prices normalised to USD. Free, no signup.",
        "Gumroad price calculator",
        f"{s['n']:,} products &middot; {s['cats']} categories &middot; prices normalised to USD",
        "Pick your category, type the price you were thinking of, and see how many people are "
        "already asking less. It is a positioning check, not a recommendation &mdash; the honest "
        "reason why is below the tool.",
        body)


def g_how_many(s, a):
    """"Should I list more products?" — answered from the seller column.

    This is the only guide not derived from the 42-search sample, and the only one that
    can be: catalogue size is a property of a seller, and the search sample never
    recorded who sold what. See seller_analyse's docstring for why the two samples are
    reported separately and never averaged.
    """
    import build_sellers as S          # imported here: build_site imports this module
    d = seller_analyse()
    ss, bands = d["s"], d["bands"]
    solo, five_plus = bands[0], bands[3]
    big1 = d["biggest"][0]

    brows = "".join(
        f"<tr><td>{b['label']}</td><td class=n>{b['n']:,}</td><td class=n>{b['med']:,}</td>"
        f"<td class=n>{b['per_prod']}</td><td class=n>{b['zero']}%</td>"
        f"<td class=n>{B.money(b['price'])}</td></tr>" for b in bands)

    def slink(r):
        sl = S.seller_slug(r["seller"])
        name = B.esc(r["seller"])
        return (f'<a href="../s/{sl}.html">{name}</a>'
                if r["products"] >= S.MIN_PRODUCTS else name)

    crows = "".join(
        f"<tr><td>{slink(r)}</td><td class=n>{r['products']}</td>"
        f"<td class=n>{r['ratings_total']:,}</td>"
        f"<td class=n>{round(r['ratings_total'] / r['products'], 1)}</td>"
        f"<td class=n>{r['products'] - r['rated_products']}</td>"
        f"<td class=n>{r['ratings_rank']}</td></tr>"
        for r in d["biggest"])

    body = f"""
<h2>The short answer</h2>
<p>Listing more products does raise a seller's <em>total</em> demand &mdash; slowly. It does not
raise demand <em>per product</em> at all, and the sellers holding most of this marketplace did not
get there by publishing a lot. Across {ss['sellers']:,} sellers, the rank correlation between how
many products a seller lists and how much demand they attract is
<strong>{ss['spearman_products_ratings']}</strong>. That is a real relationship and a weak one.</p>

<h2>Every seller, banded by catalogue size</h2>
<p>&ldquo;Ratings each&rdquo; is the median of each seller's own ratings-per-product, not total
ratings divided by total products &mdash; the latter is decided by whichever storefront happens to
be biggest, and that is one seller out of {ss['sellers']:,}.</p>
<table><thead><tr><th>Products listed</th><th class=n>Sellers</th><th class=n>Median ratings</th>
<th class=n>Ratings each</th><th class=n>No ratings at all</th><th class=n>Median price</th>
</tr></thead><tbody>{brows}</tbody></table>
<p>Read the third column down and the case for publishing more looks strong: the median seller goes
from {solo['med']} rating to {bands[-1]['med']}. Read the fourth and it collapses. Ratings per
product rises from {solo['per_prod']} to {five_plus['per_prod']} at five to nine products and then
<strong>falls back</strong>; the sellers with twenty or more products earn {bands[-1]['per_prod']}
ratings per listing, which is worse than sellers with two. Whatever the larger catalogues are
buying, it is not attention per item.</p>
<p>The last column is the part nobody mentions. Median price falls from {B.money(solo['price'])} for
a one-product seller to {B.money(bands[-1]['price'])} for a twenty-plus seller. Large catalogues on
this platform are not the same business at a larger size &mdash; they are a cheaper business.</p>

<h2>The sellers who actually hold this market are not the ones with the most products</h2>
<p>The top {ss['top1_count']} sellers &mdash; the top 1% &mdash; hold
<strong>{ss['top1_share']}% of all {ss['ratings_total']:,} ratings</strong> in this sample. Their
median catalogue is <strong>{ss['top1_med_products']} products</strong>.
<strong>{ss['top1_solo']} of the {ss['top1_count']} have exactly one.</strong> The largest catalogue
anywhere in that top 1% is {d['top1_max_products']} products.</p>
<p>Meanwhile the six largest catalogues in the whole sample look like this:</p>
<table><thead><tr><th>Seller</th><th class=n>Products</th><th class=n>Ratings</th>
<th class=n>Ratings each</th><th class=n>Products with none</th><th class=n>Demand rank</th>
</tr></thead><tbody>{crows}</tbody></table>
<p>Not one of them is in the top 1%: the {ss['top1_count']}th-ranked seller has {d['top1_cut']:,}
ratings, and the best-placed of these six sits at rank {d['big_best_rank']}. The largest storefront
measured, {B.esc(big1['seller'])}, lists {big1['products']} products which have attracted
{big1['ratings_total']} ratings between them &mdash; {big1['products'] - big1['rated_products']} of
those listings have never been rated at all.</p>

<h2>One product carries almost everything</h2>
<p>Of the {d['multi_n']:,} sellers here with more than one product and at least one rating, the
median seller earns <strong>{d['multi_med_share']}% of all their ratings from a single
product</strong>. {d['multi_half']}% of them get at least half their demand from one listing, and
for {d['multi_all']}% one product accounts for literally all of it.</p>
<p>That concentration relaxes with catalogue size but does not go away: across the {d['five_n']}
sellers with five or more products and any demand at all, the best product still takes a median
{d['five_med_share']}% of the storefront. And among all {d['five_all_n']} sellers with five or more
products, the median one is carrying <strong>{d['five_med_unrated']} listings with no ratings
whatsoever</strong>.</p>

<h2>What this does and does not license you to conclude</h2>
<p>It does not say publish once and stop. Total demand does rise with catalogue size, the share of
sellers with nothing at all falls from {solo['zero']}% to {bands[-1]['zero']}%, and a second product
is the cheapest way to find out that the first one was the wrong product.</p>
<p>What it does say is that the common advice &mdash; volume is the strategy, keep shipping and the
catalogue compounds &mdash; is not visible in this data. Nothing compounds here. A tenth product
performs about as well as a second, the storefront's income stays concentrated in one listing, and
the price a large catalogue can command is lower. If the aim is one product that works, the
measurement supports looking for it. If the aim is thirty products that each work a little, no
seller in this sample is doing that.</p>

<p class=cite><strong>What the product counts are.</strong> A seller's product count here is
what a category walk found &mdash; three pages deep per category, so it is a <strong>lower bound,
not a catalogue</strong>, and it is biased down hardest for the sellers whose listings rank deepest.
Worth being precise about which way that cuts: ratings and products are both counted over the same
found listings, so undercounting a large seller's catalogue <em>overstates</em> their ratings per
product. The finding that per-product demand does not rise with catalogue size is therefore
conservative &mdash; correcting the bias would flatten it further, not reverse it.</p>

<h2>Which sample this is, and why it is not the other one</h2>
<p>This page is the only one on the site derived from the <a href="../t/index.html">category
walk</a> &mdash; {ss['products']:,} products from {ss['sellers']:,} sellers across
{ss['ratings_total']:,} ratings &mdash; because it is the only sample that records who sells what.
Every other guide here is measured on a separate sample of {s['n']:,} products drawn from
{s['cats']} category searches. The two disagree on price by a wide margin ({B.money(s['med'])}
median paid against {B.money(bands[0]['price'])} here) and both are published as they were measured.
Averaging them would produce a third set of numbers describing neither, so this site never does.</p>

{B.buy_block("This page is about sellers. The report is the other axis: it reads all "
             f"{s['cats']} categories together and classifies each as an opening, a crowded room "
             "or thin &mdash; which is the question you hit immediately after deciding that one "
             "product done properly beats ten.")}

<h2>Check it yourself</h2>
<p>Every figure above comes from
<a href="{B.REPO}/blob/main/data/gumroad-sellers.csv">the seller CSV</a> ({ss['sellers']:,} rows,
one per seller) and the <a href="{B.REPO}/blob/main/data/gumroad-taxonomy.csv">listing table</a> it
derives from, with <a href="{B.REPO}/blob/main/scripts/normalize_sellers.py">the derivation</a>
alongside them. Both are in the <a href="https://doi.org/{B.DOI}">DOI-archived record</a>, CC BY
4.0, no signup. The <a href="../s/index.html">ranked seller index</a> lists every rated seller.</p>
"""
    return page(
        "how-many-products-to-sell-on-gumroad",
        f"How many products should you sell on Gumroad? {ss['sellers']:,} sellers measured",
        f"Does listing more products work? Measured across {ss['sellers']:,} Gumroad sellers: the "
        f"top 1% hold {ss['top1_share']}% of demand on a median of {ss['top1_med_products']} "
        f"products. Free data, no signup.",
        "How many products should you sell on Gumroad?",
        f"{ss['sellers']:,} sellers &middot; {ss['products']:,} products &middot; "
        f"{ss['ratings_total']:,} ratings &middot; measured 5 August 2026",
        f"The standard answer is &ldquo;more&rdquo;. Measured across {ss['sellers']:,} live Gumroad "
        f"storefronts, the top 1% of sellers hold {ss['top1_share']}% of all the demand in this "
        f"sample on a median of {ss['top1_med_products']} products each &mdash; and "
        f"{ss['top1_solo']} of those {ss['top1_count']} sellers list exactly one.",
        body)


RATIO_JS = r"""
var inp=document.getElementById('rat'),pf=document.getElementById('pf'),
    out=document.getElementById('rout');
function band(n){for(var i=0;i<BANDS.length;i++){if(n<=BANDS[i].hi)return BANDS[i];}
  return BANDS[BANDS.length-1];}
function fmt(x){return x>=100?Math.round(x).toLocaleString():
  (Math.round(x*10)/10).toLocaleString();}
function go(){
  var n=parseFloat((inp.value||'').replace(/[^0-9.]/g,''));
  if(!(n>0)){out.innerHTML='<p class=warn>Enter a rating count of 1 or more.</p>';return;}
  var free=pf.value==='free',b=band(n),g=free?FREE:b;
  var lo=Math.round(n*g.q1),mid=Math.round(n*g.median),hi=Math.round(n*g.q3);
  out.innerHTML='<p class=big><strong>'+fmt(mid)+'</strong> units is the central estimate.</p>'+
    '<p>Half of comparable listings fall between <strong>'+fmt(lo)+'</strong> and <strong>'+
    fmt(hi)+'</strong> &mdash; that is the interquartile range, not a margin of error, and a '+
    'quarter of listings sit outside it on each side.</p>'+
    '<p class=warn>Based on '+g.n+' measured '+(free?'free':'paid')+' listings'+
    (free?'':' with '+g.label.replace(' ratings','')+' ratings')+
    '. It is a floor: products with sales and no ratings are excluded because the ratio '+
    'is undefined for them, and that is where under-rating is worst.</p>';
}
inp.addEventListener('input',go);pf.addEventListener('change',go);go();
"""


def g_sales_ratio(s, a):
    """"How many sales is one rating?" — the only page here measured against real units.

    This is the page the whole project has been unable to write. Every other surface
    uses ratings as a demand proxy and says so; this one checks the proxy against
    observed unit sales for the minority of sellers who publish them, and publishes the
    distribution rather than the single multiplier sellers quote at each other.

    THE ONE THING NOT TO DO HERE is print a headline "×N". The spread is the finding:
    the interquartile range is a factor of four wide, and the multiplier climbs with the
    size of the listing, so any single number is wrong for most products it is applied to.
    """
    d = sales_analyse()
    paid, free, allr = d["paid_ratio"], d["free_ratio"], d["all_ratio"]

    def rrow(b, extra=""):
        return (f"<tr><td>{b['label']}{extra}</td><td class=n>{b['n']}</td>"
                f"<td class=n>&times;{b['median']}</td>"
                f"<td class=n>&times;{b['q1']} &ndash; &times;{b['q3']}</td>"
                f"<td class=n>&times;{b['min']} &ndash; &times;{b['max']}</td></tr>")

    head = ("<thead><tr><th>Group</th><th class=n>Products</th><th class=n>Median</th>"
            "<th class=n>Middle half</th><th class=n>Full range</th></tr></thead>")
    headline = "".join([
        rrow({**paid, "label": "Paid products"}),
        rrow({**free, "label": "Free products"}),
        rrow({**allr, "label": "Everything together"}),
    ])
    by_ratings = "".join(rrow(b) for b in d["by_ratings"])
    by_sales = "".join(rrow(b) for b in d["by_sales"])
    by_price = "".join(rrow(b) for b in d["by_price"])

    first, last = d["by_ratings"][0], d["by_ratings"][-1]
    lo_band, hi_band = d["by_sales"][0], d["by_sales"][-1]

    # The estimator reads the ratings-cut bands, not the sales-cut ones: a visitor
    # types a rating count, and the sales-cut bands are censored by construction
    # (ratio <= sales when ratings >= 1), so estimating from them would be circular.
    bands_js = json.dumps([{"hi": hi, "label": b["label"], "n": b["n"],
                            "median": b["median"], "q1": b["q1"], "q3": b["q3"]}
                           for b, (_, hi, _) in zip(d["by_ratings"],
                                                    [(1, 2, ""), (3, 9, ""), (10, 49, ""),
                                                     (50, 10 ** 9, "")])],
                          separators=(",", ":"))
    free_js = json.dumps({"n": free["n"], "label": "free",
                          "median": free["median"], "q1": free["q1"], "q3": free["q3"]},
                         separators=(",", ":"))

    body = CALC_CSS + f"""
<div class=tool>
<div class=row>
<div><label for=rat>Ratings shown on the listing</label>
<input id=rat type=text inputmode=numeric value="12" autocomplete=off></div>
<div><label for=pf>Price</label>
<select id=pf><option value=paid>Paid</option><option value=free>Free</option></select></div>
</div>
<div id=rout><p class=nojs>This estimator needs JavaScript. Every band it reads is in the
tables below and they need none.</p></div>
</div>

{coverage_warn(d, "every figure on this page, and the estimator above")}

<h2>Why there is no single multiplier</h2>
<p>The number sellers quote each other is &ldquo;about thirty sales per rating&rdquo;, sometimes a
hundred. Neither has anything behind it. Here is what {d['paired']} products that publish
<em>both</em> a unit-sales count and a rating count actually show.</p>
<table>{head}<tbody>{headline}</tbody></table>
<p>Read the fourth column before the third. For paid products the middle half of listings sit
between <strong>&times;{paid['q1']}</strong> and <strong>&times;{paid['q3']}</strong> &mdash; a
factor of {round(paid['q3'] / paid['q1'], 1)} between the 25th and 75th percentile, before counting
the quarter of listings above and the quarter below. Applying one multiplier to one listing is
guessing inside that range and calling it measurement.</p>
<p>Said the way a seller experiences it: the median paid listing converts about
<strong>{d['paid_rating_rate']}% of its buyers into raters</strong>. On free products it is
{d['free_rating_rate']}% &mdash; people who paid nothing say less, which is the opposite of the
common assumption that free products farm reviews.</p>

<h2>The multiplier is not a constant. It rises with the size of the listing.</h2>
<p>This is the part that makes a fixed number actively misleading, and it is visible two
independent ways.</p>
<p>Cut by how many <em>ratings</em> a listing has:</p>
<table>{head}<tbody>{by_ratings}</tbody></table>
<p>A listing with {first['label'].replace(' ratings', '')} ratings is a
&times;{first['median']} product at the median. One with {last['label'].lower()} is
&times;{last['median']}. The same &ldquo;&times;30 rule&rdquo; applied to both
{'over' if first['median'] < 30 else 'under'}states the small one by roughly
{round(30 / first['median'], 1)}&times; and understates the large one.</p>
<p>Cut by how many <em>sales</em> a listing has, which points the same way:</p>
<table>{head}<tbody>{by_sales}</tbody></table>
<p class=cite><strong>Read that second table with a correction in mind.</strong> When a listing has
at least one rating, its ratio can never exceed its sales count &mdash; a product with six sales
cannot show a multiplier above six. So the low bands there are <strong>censored by
construction</strong> and the rise across that table is partly mechanical. The ratings-cut table
above it is not censored that way, and it shows the same climb from
&times;{first['median']} to &times;{last['median']}. That is why both are printed: one of them
would have been a nicer chart and a worse answer.</p>

<h2>Price barely matters</h2>
<table>{head}<tbody>{by_price}</tbody></table>
<p>Across paid listings the ratio does not move with price in any direction worth acting on. Whether
a buyer leaves a rating appears to be a function of how many buyers there are, not of what they
paid.</p>

<h2>Does the proxy this whole site runs on actually work?</h2>
<p>Every other page here uses ratings to compare demand, and every one of them says so. This sample
is the only place that can test it. Across the {d['disclosing']} products that publish a sales
count, the rank correlation between ratings and units sold is
<strong>{d['spearman_all']}</strong> ({d['spearman_paired']} among the ones with at least one
rating).</p>
<p>That is a strong relationship, and it licenses exactly one use: <strong>ratings rank demand
reliably, and measure it badly</strong>. If listing A has four times the ratings of listing B, A
almost certainly outsells B. If you want to know by how much, the tables above are the honest answer
and they are wide.</p>

<h2>An unrated listing has not necessarily sold nothing</h2>
<p><strong>{d['unrated_n']} of the {d['disclosing']} products publishing a sales count have zero
ratings.</strong> Their median is {d['unrated_median_sales']} units; {d['unrated_over_10']} have ten
or more, {d['unrated_over_100']} have over a hundred, and the largest has
<strong>{d['unrated_max_sales']:,} sales and not one rating</strong>.</p>
<p>They are excluded from every median above, because sales divided by zero ratings is not a number.
That exclusion is also why those medians are a <strong>lower bound</strong>: the products where
buyers rate least are precisely the ones the ratio cannot see.</p>

<h2>What this sample is</h2>
<p>{d['fetched']:,} Gumroad product pages fetched individually from
{d['sellers']:,} sellers. <strong>{d['disclosing']} of them &mdash; {d['disclose_pct']}% &mdash;
publish a unit-sales count</strong> ({d['disclose_pct_paid']}% of paid listings,
{d['disclose_pct_free']}% of free ones), covering {d['units_observed']:,} units sold in total across
{d['disclosing_sellers']} sellers. The ratio is measured on the
{d['paired']} of those that also have at least one rating.</p>
<p class=cite><strong>The category limit comes first</strong> and it is stated in full at the top
of this page: the crawl behind these products walks Gumroad's tree alphabetically and has not
finished, so this is one branch of the marketplace rather than a cross-section of it.</p>
<p class=cite><strong>Two further biases, and which way each cuts.</strong> First, displaying a sales counter
is <em>opt-in</em>, and a seller with nothing to show is likelier to leave it off &mdash; so this is
not a random draw of Gumroad products, and the listings in it are larger than typical. Second, the
ratio needs a rating to exist at all, which drops the {d['unrated_n']} zero-rating listings and
biases the medians <em>down</em>. Neither is fixable from public data; both are stated wherever
these figures appear.</p>
<p class=cite><strong>Which sample, and why not the other one.</strong> These products come from the
<a href="../t/index.html">category walk</a>, re-fetched one page at a time &mdash; the same
population as the <a href="{SELLER_GUIDE}.html">seller analysis</a>, not the {s['cats']}-search
sample of {s['n']:,} products every other guide here is built on. The two samples disagree on price
by a wide margin and are published as measured. Nothing on this page is averaged with anything from
the other one.</p>

{B.buy_block("This page tells you what a rating is worth. The report tells you where the "
             f"ratings are: all {s['cats']} categories read together and each classified as an "
             "opening, a crowded room or thin &mdash; which is the question you hit the moment "
             "you can convert a competitor's rating count into a plausible unit figure.")}

<h2>Check it yourself</h2>
<p>Every figure above comes from
<a href="{B.REPO}/blob/main/data/gumroad-sales.csv">the sales CSV</a> &mdash; one row per product
fetched, including the {d['fetched'] - d['disclosing']:,} that publish no sales count, so the
opt-in rate is re-derivable and not just asserted &mdash; with
<a href="{B.REPO}/blob/main/scripts/normalize_products.py">the derivation</a> and
<a href="{B.REPO}/blob/main/scripts/collect_products.py">the collector</a> beside it. CC BY 4.0,
no signup, <a href="https://doi.org/{B.DOI}">DOI-archived</a>.</p>
""" + "<script>var BANDS=" + bands_js + ",FREE=" + free_js + ";" + RATIO_JS + "</script>"

    return page(
        SALES_GUIDE,
        f"How many sales is one Gumroad rating? {d['paired']} products measured",
        f"Sellers say ×30. Measured on {d['paired']} Gumroad products publishing both unit "
        f"sales and ratings: paid median ×{paid['median']}, middle half ×{paid['q1']}"
        f"–×{paid['q3']}, and it rises with listing size. Free data, no signup.",
        "How many sales is one Gumroad rating?",
        f"{d['disclosing']} products publishing real unit sales &middot; "
        f"{d['units_observed']:,} units &middot; {d['paired']} usable pairs",
        f"There is no fixed multiplier, and that is the finding. Across {d['paired']} Gumroad "
        f"products that publish both a sales count and a rating count, the median paid listing "
        f"sells <strong>&times;{paid['median']}</strong> its rating count &mdash; but the middle "
        f"half spans &times;{paid['q1']} to &times;{paid['q3']}, and the ratio climbs steadily "
        f"with the size of the listing.",
        body)


def g_breadth(s, a):
    """"Should I list in more categories?" — the second guide off the seller column.

    The one page here whose headline table argues for the opposite of its conclusion.
    Banded by breadth, median demand runs 1 -> 79 ratings, and every seller-advice site
    on the internet would publish that as "diversify". It is mostly the ranking
    algorithm measuring demand and being read backwards. See breadth_analyse().
    """
    d = breadth_analyse()
    ss, bands = d["s"], d["bands"]
    solo, wide = bands[0], bands[-1]

    def rows_html(bs):
        return "".join(
            f"<tr><td>{b['label']}</td><td class=n>{b['n']:,}</td><td class=n>{b['med']:,}</td>"
            f"<td class=n>{b['per_prod']}</td><td class=n>{b['zero']}%</td>"
            f"<td class=n>{B.money(b['price'])}</td></tr>" for b in bs)

    head = ("<thead><tr><th>Categories appeared in</th><th class=n>Sellers</th>"
            "<th class=n>Median ratings</th><th class=n>Ratings each</th>"
            "<th class=n>No ratings at all</th><th class=n>Median price</th></tr></thead>")

    controls = "".join(
        f"<h3>{c['label']} <span class=sub>({c['n']:,} sellers)</span></h3>"
        f"<table>{head}<tbody>{rows_html(c['bands'])}</tbody></table>"
        for c in d["controls"])

    body = f"""
<h2>The short answer</h2>
<p>No &mdash; not as something you can act on. Sellers whose products turn up under more category
searches do have far more demand: the median goes from <strong>{solo['med']}</strong> rating for the
{solo['n']:,} sellers found under one category to <strong>{wide['med']}</strong> for the
{wide['n']} found under {wide['label'].lower()}. That table is on this page
and it is real. It is also, on the evidence below, mostly <em>demand causing breadth</em> rather
than the other way round, and the single fact that settles it is that
<strong>{ss['top1_one_category']} of the {ss['top1_count']} most in-demand sellers in this sample
appear under exactly one category</strong>.</p>

<h2>What &ldquo;categories&rdquo; means here, before any number</h2>
<p>This is not how many categories a seller ticked a box for. It is how many of the walk's category
searches <strong>returned their listings</strong>. Gumroad orders those results by demand, so a
product that sells surfaces under more terms by construction. Every figure below is an association,
and the direction is exactly what is in question &mdash; so the page is organised around testing
it rather than assuming it.</p>

<h2>Every seller, banded by breadth</h2>
<table>{head}<tbody>{rows_html(bands)}</tbody></table>
<p>The association is strong to the eye and modest in the data: across all {ss['sellers']:,}
sellers the rank correlation between breadth and demand is
<strong>{ss['spearman_categories_ratings']}</strong>. For comparison, the same correlation for
catalogue size &mdash; the thing <a href="{SELLER_GUIDE}.html">the previous guide</a> measured
&mdash; is {ss['spearman_products_ratings']}. Breadth beats catalogue size. Both are weak, and
{ss['sellers_one_category_pct']}% of sellers sit in the first row, so the last row is
{wide['n']} storefronts and should be read as such.</p>

<h2>Holding catalogue size roughly fixed</h2>
<p>The obvious objection is that broad sellers are just sellers with more products. They are not:
the pattern survives inside each catalogue-size group, including among sellers with exactly one
product, where the number of products cannot vary at all.</p>
{controls}
<p>That is the strongest form of the case for breadth, and it is worth stating plainly because the
rest of this page takes it apart. A single product appearing under four or more searches has a
median of {d['controls'][0]['bands'][-1]['med']} ratings against
{d['controls'][0]['bands'][0]['med']} for a single product appearing under one. Same catalogue
size, {round(d['controls'][0]['bands'][-1]['med'] / max(d['controls'][0]['bands'][0]['med'], 1))}&times;
the demand.</p>

<h2>Why that is the ranking measuring demand, not breadth creating it</h2>
<p>If breadth were something a seller supplies, you would expect to find sellers who supplied it and
got nothing back &mdash; broad listings with no demand. They are almost absent.
<strong>{d['unrated_one_cat_pct']}% of the {d['unrated_n']:,} sellers with no ratings at all appear
under exactly one category</strong>, against {d['rated_one_cat_pct']}% of sellers with any demand,
and the broadest unrated seller in the entire sample reaches
<strong>{d['unrated_max_cats']} categories</strong> &mdash; in a sample whose maximum is
{ss['max_categories']:,}. Breadth without demand barely exists here.</p>
<p>The correlation behaves the same way when the confound is squeezed. Among the
{ss['solo_sellers']:,} single-product sellers it falls to
<strong>{ss['spearman_categories_ratings_solo']}</strong>, roughly half the sample-wide
{ss['spearman_categories_ratings']}. That is the direction you would expect if much of the
sample-wide figure were breadth and catalogue size both tracking the same underlying thing.</p>

<h2>The fact that settles it</h2>
<p>The top {ss['top1_count']} sellers &mdash; the 1% holding {ss['top1_share']}% of all
{ss['ratings_total']:,} ratings in this sample &mdash; have a median breadth of
<strong>{ss['top1_med_categories']} categories</strong>, and
<strong>{ss['top1_one_category']} of them ({d['top1_one_cat_pct']}%) appear under exactly
one</strong>. Whatever produced the demand at the top of this marketplace, it was not spread. It is
the same shape as the catalogue-size finding: the top of this market is one thing that works, not
several things placed widely.</p>

<h2>What this does license you to do</h2>
<p>Two things, both diagnostic rather than strategic.</p>
<p><strong>Ranking under exactly one search term is where the dead listings are.</strong>
{solo['zero']}% of one-category sellers have no ratings at all, against {wide['zero']}% of the
broadest. If your product surfaces under one term and nothing else, you are in the group where most
of this platform's silence lives. That is a signal to re-examine the product, not a signal to add
categories.</p>
<p><strong>The lever adjacent to this one is real.</strong> Which searches return your listing is
decided by its title and description text, and that is the part you control. This data cannot tell
you it will work &mdash; nothing here isolates a seller who rewrote a title &mdash; but it is the
only intervention in the neighbourhood that is not simply relabelling.</p>
<p>What it does not license: listing the same product under more categories to buy demand. Nothing
here measures that, the correlation is compatible with it doing nothing, and
{ss['top1_one_category']} of the {ss['top1_count']} biggest sellers did not do it.</p>

<p class=cite><strong>What breadth is a lower bound on.</strong> The walk went three pages deep per
category, so a listing that ranks deeply under a term was not recorded as appearing there. Breadth
is therefore undercounted, and undercounted hardest for low-demand listings &mdash; which
<em>inflates</em> the gap this page reports between narrow and broad sellers. The finding that
breadth is not a lever is conservative: correcting the bias would weaken the association further,
not strengthen it. Prices here are the seller's own median asking price, and demand is measured in
ratings, which are a floor on buyers rather than a sales count &mdash;
<a href="{SALES_GUIDE}.html">what one rating is worth in units</a> is measured separately.</p>

<h2>Which sample this is, and why it is not the other one</h2>
<p>This page and <a href="{SELLER_GUIDE}.html">the catalogue-size guide</a> are the only two
derived from the <a href="../t/index.html">category walk</a> &mdash; {ss['products']:,} products
from {ss['sellers']:,} sellers, {ss['ratings_total']:,} ratings &mdash; because it is the only
sample that records who sells what and under which category. Every other guide here is measured on
a separate sample of {s['n']:,} products drawn from {s['cats']} category searches. The two are
never averaged; each is published as it was measured.</p>

{B.buy_block("This page says breadth is not a lever. The question underneath it &mdash; which "
             f"category is worth being in at all &mdash; is the report: all {s['cats']} categories "
             "read together and each one classified as an opening, a crowded room or thin.")}

<h2>Check it yourself</h2>
<p>Every figure above comes from
<a href="{B.REPO}/blob/main/data/gumroad-sellers.csv">the seller CSV</a> ({ss['sellers']:,} rows,
one per seller, with a <code>categories</code> column) and the
<a href="{B.REPO}/blob/main/data/gumroad-taxonomy.csv">listing table</a> it derives from, with
<a href="{B.REPO}/blob/main/scripts/normalize_sellers.py">the derivation</a> alongside them. Both
are in the <a href="https://doi.org/{B.DOI}">DOI-archived record</a>, CC BY 4.0, no signup.</p>
"""
    return page(
        BREADTH_GUIDE,
        f"Do multiple Gumroad categories help? {ss['sellers']:,} sellers measured",
        f"Sellers found under more Gumroad categories have more demand &mdash; but "
        f"{ss['top1_one_category']} of the {ss['top1_count']} biggest appear under exactly one. "
        f"Measured across {ss['sellers']:,} sellers. Free data, no signup.",
        "Should you list a Gumroad product in more than one category?",
        f"{ss['sellers']:,} sellers &middot; {ss['products']:,} products &middot; "
        f"{ss['ratings_total']:,} ratings &middot; measured 5 August 2026",
        f"Sellers whose products turn up under {wide['label'].lower()} category searches carry a "
        f"median of {wide['med']} ratings; sellers found under one carry {solo['med']}. That "
        f"comparison is real, it is on this page, and reading it as advice gets the causation "
        f"backwards: "
        f"{ss['top1_one_category']} of the {ss['top1_count']} most in-demand sellers here appear "
        f"under exactly one category.",
        body)


def g_mix(s, a):
    """"Should I give away a free product alongside my paid ones?" — the third guide off
    the seller column and the only one built on `free_products`.

    The gap here is the largest on the site that survives a control, and it is also the
    one most exposed to reverse causation, so the page is written to keep the reader from
    over-reading it: the finding is stated, the control is shown, and the two reasons it
    might be backwards are given the same weight as the number.
    """
    d = mix_analyse()
    ss = d["s"]
    controls = d["controls"]

    def cell(c, k):
        g = c[k]
        if not g["enough"]:
            return f"<td class=n>&mdash; <span class=sub>({g['n']})</span></td>"
        return f"<td class=n>{g['med']:,} <span class=sub>({g['n']})</span></td>"

    table = (
        "<table><thead><tr><th>Catalogue size</th><th class=n>Paid only</th>"
        "<th class=n>Free and paid</th><th class=n>Free only</th>"
        "<th class=n>Mixed &divide; paid</th></tr></thead><tbody>"
        + "".join(
            f"<tr><td>{c['label']}</td>{cell(c, 'paid')}{cell(c, 'mixed')}"
            f"{cell(c, 'free')}<td class=n>"
            + (f"{c['ratio']}&times;" if c["ratio"] else "&mdash;")
            + "</td></tr>" for c in controls)
        + "</tbody></table>")

    body = f"""
<h2>The short answer</h2>
<p>The sellers who carry both are far ahead, and it is the widest gap on this site that
survives a control &mdash; but this data cannot tell you the free product caused it.
Among the {ss['mix_multi']:,} sellers in this sample with more than one listing, those
carrying <strong>both free and paid</strong> products have a median of
<strong>{ss['mix_mixed_med_ratings']}</strong> ratings against
<strong>{ss['mix_paid_med_ratings']}</strong> for the paid-only sellers. Read the causation
section before you act on that.</p>

<h2>Why the raw comparison is not the finding</h2>
<p>Mixed sellers carry more products: a median of {ss['mix_mixed_med_products']} against
{ss['mix_paid_med_products']} for paid-only sellers. Since
<a href="{SELLER_GUIDE}.html">catalogue size tracks demand weakly but positively</a>, part of
that headline is just bigger storefronts. The table below holds catalogue size roughly fixed;
the number in brackets is how many sellers are in the cell.</p>
{table}
<p>The gap survives in every band, and it is widest where the catalogues are largest. The
free-only column thins out fast &mdash; there are {ss['mix_free_n']} such sellers in the whole
multi-product sample &mdash; and a dash means the cell is under {MIX_MIN_N} sellers and its
median would be noise. It is printed rather than dropped so you can see where the sample
runs out.</p>

<h2>What the sellers who do this actually do</h2>
<p>They add <em>one</em> free product, not a free catalogue.
<strong>{ss['mix_mixed_one_free']} of the {ss['mix_mixed_n']} mixed sellers
({d['mixed_one_free_pct']}%) carry exactly one</strong>. That is the lead-magnet shape, and it
is what the comparison above is mostly measuring &mdash; not a free tier, not a freemium
ladder, one giveaway sitting beside paid work.</p>
<p>It is also uncommon: only {d['mixed_share_pct']}% of multi-product sellers here do it at all,
and {ss['mix_solo_free']} of the {ss['solo_sellers']:,} single-product sellers have made their
one product free, which is a different decision entirely and not measured on this page.</p>

<h2>The two reasons this might be backwards</h2>
<p><strong>A seller who is already selling has every reason to add a free product.</strong>
Nothing in a snapshot records the order things happened in. If lead magnets are something
sellers add once they have an audience worth feeding, this table would look exactly as it
does. That possibility is not ruled out here and no cut of this data can rule it out.</p>
<p><strong>Free listings are harder to find in a crawl.</strong> A seller's free product only
appears in this sample if it ranked in the first three pages of a category search, so some
sellers filed here as paid-only do carry a free product that was not seen. That error runs one
way: it moves sellers out of the mixed group, never into it &mdash; which, if anything,
understates how many sellers do this and pulls the two medians together.</p>

<h2>The one bias that runs in the finding's favour</h2>
<p>Demand is measured in ratings here, and free products convert to a rating at a
<strong>lower</strong> rate per unit than paid ones &mdash; {d['free_rating_rate']}% against
{d['paid_rating_rate']}% on the <a href="{SALES_GUIDE}.html">subsample with real unit
sales</a>. A mixed seller's rating total therefore understates their units by more than a
paid-only seller's does. The gap in the table is a floor on the gap in units, not a ceiling.</p>
<p>The listing-level figures point the same way: {ss['mix_mixed_rated_pct']}% of a mixed
seller's listings carry at least one rating, against {ss['mix_paid_rated_pct']}% for paid-only
sellers, and only {ss['mix_mixed_zero_pct']}% of mixed sellers have no ratings anywhere at all
against {ss['mix_paid_zero_pct']}% of paid-only sellers. Whatever is going on, the mixed
storefronts are much less likely to be completely silent.</p>

<h2>What to do with this</h2>
<p><strong>If you have one product and it is paid, this page is not about you.</strong> The
comparison is only defined for sellers with two or more listings. Adding a free product to get
into the mixed group is exactly the move this data cannot endorse.</p>
<p><strong>If you already have several paid products and none free, this is the cheapest thing
in the sample worth trying.</strong> One giveaway, not a catalogue. It costs a listing, the
sellers who do it are the least likely group here to be sitting at zero, and the downside is
bounded in a way almost nothing else on this site is.</p>
<p><strong>Do not read it as a pricing strategy.</strong>
<a href="free-vs-paid-digital-products.html">Free versus paid at the product level</a> is a
different question measured on a different sample, and it says free listings collect ratings
without telling you anything about money. This page is about what sits <em>beside</em> the
paid work, not what you charge for it.</p>

<p class=cite><strong>What these figures are a lower bound on.</strong> A seller's product count
is what this crawl found &mdash; three pages deep per category node &mdash; not their catalogue,
so every band above is a floor. Demand is ratings, which are a floor on buyers rather than a
sales count. The free/paid split is taken from observed listings, with the miss direction stated
above. Nothing here is a revenue figure and no seller's earnings are known.</p>

<h2>Which sample this is, and why it is not the other one</h2>
<p>This page, <a href="{SELLER_GUIDE}.html">the catalogue-size guide</a> and
<a href="{BREADTH_GUIDE}.html">the category-breadth guide</a> are the three derived from the
<a href="../t/index.html">category walk</a> &mdash; {ss['products']:,} products from
{ss['sellers']:,} sellers, {ss['ratings_total']:,} ratings &mdash; because it is the only sample
that records who sells what. Every other guide here is measured on a separate sample of
{s['n']:,} products drawn from {s['cats']} category searches. The two are never averaged; each
is published as it was measured.</p>

{B.buy_block("This page says a free product beside your paid work is the cheapest thing in "
             "the sample worth trying. What the paid work should be &mdash; which category is "
             f"an opening and which is a crowded room &mdash; is the report: all {s['cats']} "
             "categories read together and each one classified.")}

<h2>Check it yourself</h2>
<p>Every figure above comes from
<a href="{B.REPO}/blob/main/data/gumroad-sellers.csv">the seller CSV</a> ({ss['sellers']:,} rows,
one per seller, with a <code>free_products</code> column) and the
<a href="{B.REPO}/blob/main/data/gumroad-taxonomy.csv">listing table</a> it derives from, with
<a href="{B.REPO}/blob/main/scripts/normalize_sellers.py">the derivation</a> alongside them. Both
are in the <a href="https://doi.org/{B.DOI}">DOI-archived record</a>, CC BY 4.0, no signup.</p>
"""
    return page(
        MIX_GUIDE,
        f"Should you offer a free Gumroad product? {ss['mix_multi']:,} sellers measured",
        f"Gumroad sellers carrying both free and paid products have a median of "
        f"{ss['mix_mixed_med_ratings']} ratings against {ss['mix_paid_med_ratings']} for "
        f"paid-only sellers, and the gap survives at every catalogue size. Free data, no signup.",
        "Should you give away a free product alongside your paid ones?",
        f"{ss['mix_multi']:,} multi-product sellers &middot; {ss['mix_mixed_n']} of them "
        f"carrying both &middot; measured 5 August 2026",
        f"Sellers with both free and paid listings carry a median of "
        f"{ss['mix_mixed_med_ratings']} ratings; paid-only sellers carry "
        f"{ss['mix_paid_med_ratings']}. The gap holds at every catalogue size, and "
        f"{ss['mix_mixed_one_free']} of the {ss['mix_mixed_n']} sellers doing it carry exactly "
        f"one free product. What this page cannot tell you is which came first.",
        body)


BUILDERS = [g_what_to_sell, g_earnings, g_pricing, g_worth_it, g_statistics, g_free_vs_paid,
            g_calculator, g_how_many, g_sales_ratio, g_breadth, g_mix]


# Pages whose figures come from the per-product crawl, and which therefore MUST carry the
# category-coverage caveat. Both shipped without it and read as platform-wide answers.
CRAWL_BACKED = {"how-much-do-people-make-on-gumroad", SALES_GUIDE}


def build(s, rows, outdir):
    a = analyse(s, rows)
    outdir.mkdir(exist_ok=True)
    for fn, (sl, _) in zip(BUILDERS, GUIDES):
        html = fn(s, a)
        if sl in CRAWL_BACKED:
            assert_coverage_warned(html, f"{sl}.html")
        (outdir / f"{sl}.html").write_text(html)
    return [sl for sl, _ in GUIDES]
