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
    return {
        "cats": cats, "bands": bands,
        "avg_rated": 100 - s["zpct"],
        "med_conc": st.median([c["top3"] for c in cats]),
        "r_price_demand": B_pearson([c["median"] for c in cats],
                                    [c["rated_share"] for c in cats]),
        "cheaper_wins": cheaper_wins, "cheaper_tot": tot,
        "free_n": len(free),
        "free_rated": round(100 * sum(1 for r in free if r["n"] > 0) / len(free)),
        "paid_rated": round(100 * sum(1 for r in paid if r["n"] > 0) / len(paid)),
        "subs_n": len(rec),
        "top_listing": max(prod, key=lambda r: r["n"]),
        "med_rated_ratings": int(st.median([r["n"] for r in prod if r["n"] > 0])),
        "p90_ratings": int(st.quantiles([r["n"] for r in prod if r["n"] > 0], n=10)[8]),
    }


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
<p>There is no public sales figure on Gumroad, so the honest proxy is whether a listing has
attracted any ratings at all. A listing with no ratings has, as far as anything observable goes,
sold nothing. Across {s['n']:,} live listings, <strong>{s['zero']} — {s['zpct']}% — have no ratings
whatsoever</strong>. That is the background rate anything you launch competes against, before
quality, before price, before marketing.</p>

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
    top = a["top_listing"]
    bands = "".join(f"<tr><td>{b['label']}</td><td class=n>{b['n']:,}</td>"
                    f"<td class=n>{b['rated']}%</td><td class=n>{b['med']:,}</td></tr>"
                    for b in a["bands"])
    body = f"""
<h2>What can and cannot be measured</h2>
<p>Gumroad does not publish sales counts. It publishes rating counts, and a rating requires a
purchase. So rating count is a floor on units sold, not an estimate of it — most buyers never rate
anything. Everything below uses ratings as a <em>relative</em> signal: it tells you which listings
outsell which, and it does not tell you anyone's revenue. Anybody quoting you precise Gumroad
earnings from public data is guessing.</p>

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
        f"How much do people actually make on Gumroad? {s['n']:,} listings measured",
        f"Measured demand across {s['n']:,} live Gumroad listings: {s['zpct']}% have no ratings at "
        f"all, and the top three listings in a category hold {a['med_conc']:.0f}% of its ratings.",
        "How much do people actually make on Gumroad?",
        f"{s['n']:,} live listings measured &middot; 5 August 2026 &middot; free, openly licensed data",
        "Nobody can tell you Gumroad revenue from public data, and anyone who claims a precise "
        "figure is guessing. What can be measured is the distribution of demand — and that turns "
        "out to answer the question people are really asking.",
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


BUILDERS = [g_what_to_sell, g_earnings, g_pricing, g_worth_it]


def build(s, rows, outdir):
    a = analyse(s, rows)
    outdir.mkdir(exist_ok=True)
    for fn, (sl, _) in zip(BUILDERS, GUIDES):
        (outdir / f"{sl}.html").write_text(fn(s, a))
    return [sl for sl, _ in GUIDES]
