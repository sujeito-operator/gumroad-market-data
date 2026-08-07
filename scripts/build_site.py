#!/usr/bin/env python3
"""Generate every published surface from the data, so they cannot drift apart.

WHY THIS EXISTS. The recurring defect in this project is two surfaces describing the
same thing differently. On 2026-08-07 the README said 70 subscription products, 42
searches and a median of $29.70, while the landing page said 57, 27 and $34.89 — both
published, both claiming to describe the same file. Neither was right, because both
were computed across mixed currencies (see normalize.py).

So the README, the landing page, the per-category pages and the sitemap are all
*generated* from data/summary.json and data/gumroad-latest.csv. Editing them by hand
is how the drift starts; edit this file instead and re-run:

    python3 scripts/normalize.py && python3 scripts/build_site.py
"""
import collections, csv, json, pathlib, re, urllib.parse

import build_guides
import build_sellers
import build_taxonomy

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://sujeito-operator.github.io/gumroad-market-data"
REPO = "https://github.com/sujeito-operator/gumroad-market-data"
RAW = "https://raw.githubusercontent.com/sujeito-operator/gumroad-market-data/main"
# Concept DOI: always resolves to the newest version. v1.0 (…104) had the
# mixed-currency error; v1.1 (…635) corrects it. Cite the concept DOI, not a version.
DOI = "10.5281/zenodo.21830103"

# The price is set in next.md, which is the single source of truth for it. It has
# changed twice, and a stale price on a money surface is this project's most frequent
# defect — change it in one place, here, and re-run the build.
PRICE = "$79"
BUY = "https://sujeitooperator.gumroad.com/l/bylafq"
# The same free CSV, mirrored as a $0 Gumroad product. Not a second paywall and not a
# lead magnet: gumroad.com already ranks where this site does not, so it is a download
# location that search engines will actually find. Keep it $0 with a $0 minimum.
FREE_MIRROR = "https://sujeitooperator.gumroad.com/l/gumroad-market-data"

# Tagged release. `main` moves; a release tag does not, so this is the URL to cite or to
# link from anywhere that needs the exact bytes a claim was computed from. It is also an
# indexable page on github.com, which is worth more than one on this domain.
VERSION = "1.1"
RELEASE = f"{REPO}/releases/tag/v{VERSION}"
RELEASE_CSV = f"{REPO}/releases/download/v{VERSION}/gumroad-latest.csv"

CSS = """:root{--ink:#1a1a1a;--mut:#666;--line:#ddd;--acc:#8a7a5c;--bg:#faf9f6}
*{box-sizing:border-box}
body{font:17px/1.65 Georgia,serif;color:var(--ink);background:var(--bg);margin:0;padding:0 20px}
main{max-width:820px;margin:0 auto;padding:56px 0 80px}
h1{font-size:2.3rem;line-height:1.15;margin:0 0 8px;letter-spacing:-.5px}
.sub{color:var(--mut);font-size:1rem;margin-bottom:34px}
h2{font-size:1.25rem;margin:44px 0 12px;border-bottom:2px solid var(--ink);padding-bottom:6px}
.lede{background:#f2efe7;border-left:4px solid var(--acc);padding:18px 22px;margin:26px 0;font-size:1.05rem}
table{border-collapse:collapse;width:100%;font-size:.86rem;margin:14px 0;background:#fff}
th{text-align:left;border-bottom:2px solid var(--ink);padding:9px 7px;font-family:system-ui,sans-serif;font-size:.7rem;text-transform:uppercase;letter-spacing:.5px}
td{padding:8px 7px;border-bottom:1px solid var(--line)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:hover{background:#f7f5ef}
.buy{background:#fff;border:2px solid var(--ink);padding:22px 24px;margin:34px 0;border-radius:3px}
.buy a{display:inline-block;background:var(--ink);color:#fff;text-decoration:none;padding:11px 22px;border-radius:3px;font-family:system-ui,sans-serif;font-size:.92rem;margin-top:10px}
code{background:#eee;padding:1px 5px;border-radius:3px;font-size:.85em}
footer{color:var(--mut);font-size:.85rem;border-top:1px solid var(--line);margin-top:48px;padding-top:16px}
li{margin-bottom:8px}
.kv{display:flex;flex-wrap:wrap;gap:0;margin:22px 0;background:#fff;border:1px solid var(--line)}
.kv div{flex:1 1 33%;padding:14px 16px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.kv b{display:block;font:600 1.5rem/1.2 system-ui,sans-serif;font-variant-numeric:tabular-nums}
.kv span{color:var(--mut);font-size:.78rem;font-family:system-ui,sans-serif;text-transform:uppercase;letter-spacing:.5px}
.bar{background:var(--acc);height:11px;display:inline-block;vertical-align:middle}
nav.sib{font-size:.85rem;color:var(--mut);margin:30px 0 0}
nav.sib a{color:var(--ink)}
ul.next{list-style:none;padding:0;margin:0}
ul.next li{border-top:1px solid var(--line);padding:14px 0}
ul.next li:last-child{border-bottom:1px solid var(--line)}
ul.next b{display:block;font-size:1.02rem}
ul.next span{color:var(--mut);font-size:.9rem}
a.home{font-family:system-ui,sans-serif;font-size:.82rem;text-transform:uppercase;letter-spacing:.6px;color:var(--mut)}
p.cite{background:#fff;border:1px solid var(--line);padding:14px 16px;font-size:.88rem;margin:16px 0}"""


def slug(topic):
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def money(v):
    return f"${v:,.2f}"


def head(title, desc, canonical, extra=""):
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name=description content="{esc(desc)}">
<link rel=canonical href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary">
{extra}<style>
{CSS}
</style></head><body><main>"""


def buy_block(scope):
    return f"""<div class=buy><strong>The written report — {PRICE}</strong><br>
{scope} You are paying for the interpretation, not for the rows. The rows are free, above and in the
repository. If the data is all you wanted, take it and skip this.
<br><a href="{BUY}">Read the report — {PRICE}</a></div>"""


FOOTER = f"""<footer>Collected and written by an autonomous AI agent. Prices are converted to USD at
European Central Bank reference rates so categories are comparable; the raw asking price and its
currency are both kept in the data. Method, collector and full data are public in
<a href="{REPO}">this repository</a>. Machine-readable index: <a href="{SITE}/llms.txt">llms.txt</a>.</footer>
</main></body></html>
"""


# ---------------------------------------------------------------- landing page

def demand_rows(cats):
    out = []
    for c in cats:
        out.append(
            f"<tr><td><a href=\"c/{slug(c['topic'])}.html\">{esc(c['topic'])}</a></td>"
            f"<td class=n>{c['rated_share']}%</td><td class=n>{c['med_ratings']:,}</td>"
            f"<td class=n>{c['top_n']:,}</td><td class=n>{money(c['median'])}</td>"
            f"<td class=n>{money(c['p90'])}</td><td class=n>{c['subs']}</td></tr>")
    return "".join(out)


def jsonld(s):
    return json.dumps({
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": f"What Actually Sells on Gumroad: {s['n']:,} live products across {s['cats']} categories (August 2026)",
        "description": (
            f"A measured snapshot of {s['n']:,} live Gumroad products across {s['cats']} category "
            "searches, captured 5 August 2026. Each row carries category, asking price, the currency "
            "it was displayed in, a USD-normalised price, rating count (a proxy for units sold) and a "
            f"subscription flag. {s['zpct']}% of listings have no ratings at all. Includes "
            "per-category aggregates: share of listings rated, median rating count, price quartiles "
            "and subscription counts. Collected directly from Gumroad Discover by an autonomous AI "
            "agent; the collector script is published alongside the data so every figure is "
            "reproducible."),
        "url": SITE + "/",
        "sameAs": REPO,
        "identifier": "https://doi.org/" + DOI,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "keywords": ["Gumroad", "digital products", "creator economy", "e-commerce pricing",
                     "marketplace demand", "indie hackers", "product pricing", "market research"],
        "datePublished": "2026-08-05",
        "temporalCoverage": "2026-08-05",
        "variableMeasured": ["category", "asking price", "currency", "price in USD",
                             "rating count", "subscription flag", "product title"],
        "creator": {"@type": "Organization", "name": "Sujeito Operator",
                    "url": "https://github.com/sujeito-operator"},
        "includedInDataCatalog": {"@type": "DataCatalog", "name": "Zenodo",
                                  "url": "https://zenodo.org/"},
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "name": f"Full dataset ({s['n']:,} rows)",
             "contentUrl": RAW + "/data/gumroad-latest.csv"},
            {"@type": "DataDownload", "encodingFormat": "text/csv", "name": "50-row sample",
             "contentUrl": SITE + "/sample-50-rows.csv"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "name": "Per-category summary", "contentUrl": RAW + "/data/summary.json"},
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "name": "Full dataset (Gumroad mirror, free)", "contentUrl": FREE_MIRROR},
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "name": f"Full dataset, pinned to release v{VERSION}",
             "contentUrl": RELEASE_CSV},
        ],
        "version": VERSION,
    }, indent=2)


def build_index(s, mix, ts, ss):
    top = s["by_category"][0]
    bottom = s["by_category"][-1]
    fx = s["fx_rates_to_usd"]
    extra = f'<script type="application/ld+json">\n{jsonld(s)}\n</script>\n'
    desc = (f"{s['zpct']}% of Gumroad products have zero ratings. Measured data on {s['n']:,} live "
            f"products across {s['cats']} categories: which categories actually transact, real USD "
            f"price anchors, and how rare subscriptions are. Free, CC BY 4.0, DOI {DOI}.")
    return head(f"What Actually Sells on Gumroad — {s['n']:,} products measured (Aug 2026)", desc,
                SITE + "/", extra) + f"""
<h1>What actually sells on Gumroad</h1>
<div class=sub>{s['n']:,} live products measured across {s['cats']} categories &middot; 5 August 2026</div>

<div class=lede><strong>{s['zero']} of the {s['n']:,} products in this sample — {s['zpct']}% — have no
ratings at all.</strong> They are listed, priced, and selling nothing. The gap between the categories
where that happens and the ones where it doesn't runs from <strong>{top['rated_share']}% of listings
rated</strong> at the top to <strong>{bottom['rated_share']}%</strong> at the bottom.</div>

<nav class=sib>Start here: {" &middot; ".join(f'<a href="g/{g}.html">{lab}</a>'
    for g, lab in build_guides.GUIDES)}</nav>

<h2>A second, larger sample — {ts['n']:,} products and {ts['sellers']:,} sellers</h2>
<p>Everything below this section comes from {s['cats']} Discover searches. Since then the
whole of <strong>Gumroad's own category tree</strong> has been walked as a separate
sample — {ts['nodes']} categories, <strong>{ts['n']:,} distinct products from
{ts['sellers']:,} distinct sellers</strong> — and it is published in full beside this one.
It is not a replacement: it is a different sampling frame, and where the two disagree the
disagreement is the finding. This one puts the median paid asking price at
{money(s['med'])}; walking the taxonomy puts it at {money(ts['med'])}, because popular
search terms never surface the cheaper depths of the catalogue.</p>
<p>It also records <em>who is selling</em>, which this sample never did.
<strong>{ts['sellers_one_product']:,} of the {ts['sellers']:,} sellers have exactly one
product, and the top tenth of sellers hold {ts['seller_top10_share']}% of every rating
measured.</strong></p>
<p><a href="t/index.html"><strong>Browse all {ts['nodes']} Gumroad categories &rarr;</strong></a>
&nbsp;·&nbsp; <a href="{REPO}/blob/main/data/gumroad-taxonomy.csv">the CSV</a>
({ts['obs']:,} rows, free, CC BY 4.0)</p>

<h2>And a third view: who is selling</h2>
<p>Attributing every listing to its storefront turns the price table into a market
structure, and the structure is the more interesting object.
<strong>The top 1% of Gumroad sellers hold {ss['top1_share']}% of all measured demand —
and the median seller in that 1% has {ss['top1_med_products']} products.</strong>
{ss['top1_solo']} of those {ss['top1_count']} sellers have exactly one. The rank
correlation between how much a seller lists and how much demand they attract is only
{ss['spearman_products_ratings']}, so whatever produces a winner here, listing more of
them is not it.</p>
<p><a href="s/index.html"><strong>All {ss['sellers']:,} sellers, ranked &rarr;</strong></a>
&nbsp;·&nbsp; <a href="{REPO}/blob/main/data/gumroad-sellers.csv">the seller CSV</a>
(one row per seller, free, CC BY 4.0)</p>

<h2>The demand table</h2>
<p>The first column carries most of the information. <strong>% Rated</strong> is the share of listings
in a category with at least one rating — the cleanest available signal for whether products there sell
at all, or simply sit. It is free here in full; nothing is held back from this table. Every category
name links to a page with its full price distribution and every listing measured.</p>
<table><thead><tr><th>Category</th><th class=n>% Rated</th><th class=n>Median ratings</th>
<th class=n>Top product</th><th class=n>Median price</th><th class=n>90th pct</th><th class=n>Subs</th>
</tr></thead><tbody>{demand_rows(s['by_category'])}</tbody></table>

<h2>What the numbers say</h2>
<ul>
<li><strong>A third of everything listed has never sold a measurable unit.</strong> {s['zpct']}% with
zero ratings is the background rate you compete against.</li>
<li><strong>Creative assets dominate volume.</strong> {esc(top['topic'])} is the only category sampled
where every listing has ratings; Procreate brushes carry a median of 136 with a top product at 3,300.</li>
<li><strong>Template and document categories look busy and move slowly.</strong> {esc(bottom['topic'])}
sits at {bottom['rated_share']}% rated with a median of {bottom['med_ratings']} rating(s).</li>
<li><strong>Price and demand are close to unrelated.</strong> The highest-demand categories are among
the cheapest.</li>
<li><strong>Subscriptions are rare:</strong> {s['subs']} of {s['n']:,} products bill recurring.</li>
<li><strong>Price anchors (USD):</strong> median {money(s['med'])}, 75th percentile {money(s['p75'])},
90th {money(s['p90'])}.</li>
</ul>

<h2>Method, and what this cannot tell you</h2>
<p>{s['cats']} searches were run against Gumroad Discover and the top results of each captured with a
headless browser: asking price, the currency it was shown in, subscription flag, rating count, title.
<strong>Rating count is a proxy for units sold, not a sales figure</strong> — only some buyers rate, and
that share differs by category, so use this to rank categories against each other rather than to
estimate revenue. It is one snapshot rather than a trend, and it reflects the visible top of each
category rather than its full population.</p>
<p><strong>On currency.</strong> Gumroad localises the prices it displays, so a single search returns a
mixture: {mix}, with {s['mixed_cats']} of the {s['cats']}
categories containing more than one. Prices here are converted to USD at ECB reference rates for
{s['fx_date']} (£1 = ${fx['£']:.4f}, €1 = ${fx['€']:.4f}); the raw price and its currency are both kept
in the data so the conversion can be checked or redone.</p>

<h2>The full dataset — free, no signup</h2>
<p>All {s['n']:,} rows are public and always will be:
<a href="{REPO}/blob/main/data/gumroad-latest.csv"><code>data/gumroad-latest.csv</code></a> — category,
price, currency, USD price, rating count, subscription flag, product title — together with
<a href="{REPO}/blob/main/scripts/collect.py">the collector that produced it</a>. Every figure on this
page is reproducible from those files, which is the point: check the work rather than trust it. No email
wall, no account, no "request access". Prefer a quick look first?
<a href="sample-50-rows.csv">Download a 50-row sample</a>.</p>
<p><strong>Also mirrored on Gumroad</strong> for anyone who would rather click one button than
clone a repo: <a href="{FREE_MIRROR}">the same CSV, free</a>. It is $0 with a $0 minimum — the
suggested amount is optional and typing zero is the expected case.</p>
<p><strong>Citing a fixed version?</strong> <code>main</code> moves as the data is corrected, so pin to
<a href="{RELEASE}">release v{VERSION}</a> — the exact bytes every figure on this page was computed
from, downloadable at <a href="{RELEASE_CSV}">a URL that will not change</a>. The release notes also
record what changed from v1.0, including the currency error it corrects.</p>
<p><strong>Archived with a DOI:</strong> <a href="https://doi.org/{DOI}">{DOI}</a> — data
<strong>CC BY 4.0</strong>, collector code <strong>MIT</strong>.</p>

{buy_block("What is <em>not</em> free is the analysis: a report that reads the table rather than "
           "prints it — which categories are openings versus crowded rooms, where price and demand "
           "come apart, and what the " + str(s['zpct']) + "%-unrated background rate means if you "
           "are choosing what to build next.")}
""" + FOOTER


# ------------------------------------------------------------- category pages

def buckets(prices):
    edges = [(0, 10), (10, 25), (25, 50), (50, 100), (100, 250), (250, 10 ** 9)]
    labels = ["under $10", "$10–25", "$25–50", "$50–100", "$100–250", "$250+"]
    counts = [sum(1 for p in prices if lo <= p < hi) for lo, hi in edges]
    top = max(counts) or 1
    rows = []
    for label, c in zip(labels, counts):
        share = round(100 * c / len(prices)) if prices else 0
        rows.append(f"<tr><td>{label}</td><td class=n>{c}</td><td class=n>{share}%</td>"
                    f"<td><span class=bar style=\"width:{round(150 * c / top)}px\"></span></td></tr>")
    return "".join(rows)


def build_category(c, rows, s, siblings):
    topic = c["topic"]
    prices = [r["price_usd"] for r in rows if r["price_usd"] > 0]
    listed = sorted(rows, key=lambda r: -r["n"])
    body_rows = "".join(
        f"<tr><td>{esc(r['t'])}</td><td class=n>{money(r['price_usd'])}</td>"
        f"<td class=n>{r['cur']}{r['price']:,.2f}</td>"
        f"<td class=n>{int(r['n']):,}</td></tr>" for r in listed)
    sib = " &middot; ".join(f'<a href="{slug(x)}.html">{esc(x)}</a>' for x in siblings)
    canonical = f"{SITE}/c/{slug(topic)}.html"
    title = f"How much do {topic} sell for on Gumroad? — {c['n']} listings measured"
    desc = (f"Measured prices and demand for {topic} on Gumroad: median {money(c['median'])}, "
            f"90th percentile {money(c['p90'])}, {c['rated_share']}% of listings have at least one "
            f"rating. {c['n']} live listings, free data, August 2026.")
    ld = json.dumps({
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": f"Gumroad {topic}: {c['n']} live listings with prices and rating counts (August 2026)",
        "description": desc,
        "url": canonical,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "isPartOf": {"@type": "Dataset", "name": "What Actually Sells on Gumroad",
                     "url": SITE + "/", "identifier": "https://doi.org/" + DOI},
        "creator": {"@type": "Organization", "name": "Sujeito Operator",
                    "url": "https://github.com/sujeito-operator"},
        "temporalCoverage": "2026-08-05",
    }, indent=2)
    extra = f'<script type="application/ld+json">\n{ld}\n</script>\n'

    # 10 of the 42 categories contain no free listing at all and 8 contain exactly one,
    # so a single f-string here is wrong or ungrammatical on 18 pages. Branch on the count.
    if c["free"] == 0:
        free_line = f"Nothing in {esc(topic)} is given away — every one of these {c['n']} listings asks for money. "
    elif c["free"] == 1:
        free_line = f"One of the {c['n']} listings here is priced at zero. "
    else:
        free_line = f"{c['free']} of the {c['n']} listings here are priced at zero. "

    avg = 100 - s["zpct"]
    if c["rated_share"] >= 95:
        verdict = ("Effectively every listing sampled here carries ratings, which is as strong a "
                   "demand signal as this dataset produces.")
    elif c["rated_share"] > avg:
        verdict = (f"{c['rated_share']}% of listings carry at least one rating, against a {avg}% "
                   f"average across all {s['cats']} categories — this category transacts more "
                   f"than most.")
    elif c["rated_share"] >= 50:
        verdict = (f"{c['rated_share']}% of listings carry at least one rating, against a {avg}% "
                   f"average across all {s['cats']} categories. A majority sell something, but "
                   f"this category is below the field.")
    else:
        verdict = (f"Only {c['rated_share']}% of listings carry a single rating, against a {avg}% "
                   f"average across all {s['cats']} categories — the majority of what is listed "
                   f"here is not visibly selling at all.")

    return head(title, desc, canonical, extra) + f"""
<a class=home href="../">&larr; What actually sells on Gumroad</a>
<h1>{esc(topic)}</h1>
<div class=sub>{c['n']} live Gumroad listings measured &middot; 5 August 2026 &middot; prices in USD</div>

<div class=lede>{verdict}</div>

<div class=kv>
<div><b>{money(c['median'])}</b><span>Median price</span></div>
<div><b>{c['rated_share']}%</b><span>Listings with a rating</span></div>
<div><b>{c['med_ratings']:,}</b><span>Median ratings, of those rated</span></div>
<div><b>{money(c['p25'])} – {money(c['p75'])}</b><span>Middle half of prices</span></div>
<div><b>{money(c['p90'])}</b><span>90th percentile</span></div>
<div><b>{c['top_n']:,}</b><span>Most-rated listing</span></div>
</div>

<h2>Where the prices sit</h2>
<table><thead><tr><th>Price band</th><th class=n>Listings</th><th class=n>Share</th><th></th></tr>
</thead><tbody>{buckets(prices)}</tbody></table>
<p>{c['free']} of the {c['n']} listings are priced at zero, and {c['subs']} bill on a subscription.
Prices were displayed in {', '.join(c['currencies'])} and are converted to USD at ECB reference rates
for {s['fx_date']}.</p>

<h2>Every listing measured</h2>
<p>The full sample for this category, most-rated first. Rating count is a proxy for units sold, not a
sales figure — use it to rank listings against each other, not to estimate revenue.</p>
<table><thead><tr><th>Listing</th><th class=n>USD</th><th class=n>As shown</th><th class=n>Ratings</th>
</tr></thead><tbody>{body_rows}</tbody></table>

<h2>The data behind this page</h2>
<p>This page is generated from a free, openly licensed dataset of {s['n']:,} Gumroad listings across
{s['cats']} categories — <a href="{REPO}/blob/main/data/gumroad-latest.csv">the full CSV</a>,
<a href="{REPO}/blob/main/scripts/collect.py">the collector</a>, and a
<a href="https://doi.org/{DOI}">DOI-archived copy</a> under CC BY 4.0. No signup, no email wall.</p>

<h2>Next</h2>
<ul class=next>
<li><b><a href="../g/gumroad-price-calculator.html#{urllib.parse.quote(topic)}">Price
a {esc(topic)} against these {c['n']} listings</a></b>
<span>Type your number and the calculator opens on this category: which percentile it lands in,
how many listings sit within &plusmn;30% of it, and whether anyone is testing that price at
all.</span></li>
<li><b><a href="../g/gumroad-pricing.html">What to charge on Gumroad</a></b>
<span>The same question across all {s['cats']} categories, and why price and demand turn out to be
close to unrelated — the reason this page's median is a starting point rather than an answer.</span></li>
<li><b><a href="../g/free-vs-paid-digital-products.html">Free versus paid</a></b>
<span>{free_line}Market-wide, free listings are far better at attracting ratings than paid ones, and
the page explains why that is not the endorsement of free it looks like.</span></li>
<li><b><a href="../g/what-to-sell-on-gumroad.html">What to sell</a></b>
<span>Which of the {s['cats']} categories show demand and which are mostly unsold inventory, ranked
by the same rated-share figure quoted at the top of this page.</span></li>
</ul>

{buy_block(f"What is <em>not</em> free is the analysis: a report that reads all {s['cats']} categories "
           f"together — which are openings versus crowded rooms, where price and demand come apart, "
           f"and what the {s['zpct']}%-unrated background rate means if you are choosing what to "
           f"build next.")}

<nav class=sib>More categories: {sib} &middot; <a href="../">all {s['cats']}</a></nav>
<nav class=sib>Guides: {" &middot; ".join(f'<a href="../g/{g}.html">{lab}</a>'
    for g, lab in build_guides.GUIDES)}</nav>
""" + FOOTER


def sitemap(cats, guides=(), taxo=(), sellers=()):
    urls = ([SITE + "/"]
            + [f"{SITE}/g/{g}.html" for g in guides]
            + [f"{SITE}/c/{slug(c['topic'])}.html" for c in cats]
            + [f"{SITE}/t/index.html"]
            + [f"{SITE}/t/{t}.html" for t in taxo]
            + [f"{SITE}/s/index.html"]
            + [f"{SITE}/s/{x}.html" for x in sellers])
    body = "".join(f"<url><loc>{u}</loc><lastmod>2026-08-07</lastmod></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")


def llms_txt(s, cats, guides, ts=None):
    """/llms.txt — the one indexable surface this site did not have.

    robots.txt already allows every AI crawler, but an assistant that lands here has to
    infer the structure from HTML. llms.txt states it in the format they read: what the
    dataset is, how it was measured, what each page answers, and where the raw file is.

    Generated, like every other surface here. The figures come from summary.json, so
    this cannot drift the way the README and the landing page did on 2026-08-07.

    It carries the free/paid split and the observations-vs-products distinction on
    purpose: those are exactly the two things a summariser gets wrong unprompted, and a
    wrong figure repeated by an assistant is not correctable later.
    """
    top = cats[0]
    lines = [
        "# Gumroad Market Data",
        "",
        f"> An open dataset of {s['n']:,} Gumroad product listings across {s['cats']} "
        f"categories, collected from public search result pages and normalised to "
        f"{s['currency']}. Median price {money(s['med_all'])}; "
        f"{s['zpct']}% of listings have no ratings at all. "
        f"CC BY 4.0. DOI {DOI}.",
        "",
        "## How to read the numbers",
        "",
        f"- A row is a listing *observation*, not a product: one product can rank for "
        f"several category searches. {s['obs']:,} observations cover {s['n']:,} distinct "
        f"products ({s['dupes']:,} duplicates). Per-category figures count a product in "
        f"each category it ranks for; every market-wide figure counts it once.",
        f"- Prices are converted to {s['currency']} at European Central Bank reference "
        f"rates for {s['fx_date']}. Mixing currencies without converting was a real "
        f"error in an earlier version of this dataset and it moved the medians.",
        f"- Rating counts are a floor on units sold, not a sales figure. Gumroad does "
        f"publish a per-product `sales_count` on product pages where the seller opted "
        f"into showing it, but it is absent on most listings, and absent does not mean "
        f"zero. The sales-per-rating ratio is not published here because the sample that "
        f"carries both fields is still too small to state one.",
        f"- {s['free']} listings are free and {s['zero']:,} are unrated. Both distort any "
        f"average taken across the whole file; the medians above exclude neither, so "
        f"quote them as medians.",
        "",
        "## Data",
        "",
        f"- [Full CSV, tagged release]({RELEASE_CSV}): the exact bytes every figure here "
        f"was computed from. `main` moves; this tag does not.",
        f"- [50-row sample]({SITE}/sample-50-rows.csv): the column shape, no download.",
        f"- [summary.json]({RAW}/data/summary.json): every published figure as JSON.",
        f"- [Repository]({REPO}): collection and normalisation scripts.",
        f"- [Zenodo record](https://doi.org/{DOI}): citable, versioned archive.",
        "",
        "## Guides",
        "",
    ]
    lines += [f"- [{lab}]({SITE}/g/{g}.html)" for g, lab in guides]
    lines += [
        "",
        "## Category pages",
        "",
        f"One page per category with the price distribution, rating spread and "
        f"subscription share. Largest is {top['topic']} ({top['n']} listings, median "
        f"{money(top['median'])}).",
        "",
    ]
    lines += [f"- [{c['topic']}]({SITE}/c/{slug(c['topic'])}.html)" for c in cats]
    if ts:
        import build_taxonomy as T
        lines += [
            "",
            "## Second sample: Gumroad's own category taxonomy",
            "",
            f"> A larger, independently collected sample whose frame is Gumroad's "
            f"published category tree rather than 42 chosen search terms: "
            f"**{ts['n']:,} distinct products from {ts['sellers']:,} distinct sellers "
            f"across {ts['nodes']} categories**, in {ts['obs']:,} listing observations. "
            f"Median paid asking price {money(ts['med'])}; {ts['zpct']}% of products "
            f"carry no ratings.",
            "",
            "Read these two samples as two frames on one marketplace, not as one "
            "superseding the other. They disagree, and the disagreement is the finding: "
            f"the search-term sample puts the median paid price at {money(s['med'])} and "
            f"the taxonomy walk at {money(ts['med'])}, because popular search terms never "
            "surface the cheaper depths of the catalogue.",
            "",
            f"- Products are keyed on product URL, an exact identity key. "
            f"{ts['multi']:,} products are filed by Gumroad under more than one category.",
            f"- **A category's listing count is a crawl depth, not a category size.** "
            f"Each node was taken up to three pages deep, capping it at {ts['cap']} "
            f"listings; {ts['nodes_at_cap']} of {ts['nodes']} nodes hit that cap. Never "
            f"quote it as the number of products in a category.",
            f"- {ts['nodes_empty']} of the {ts['nodes_crawled']} crawled nodes returned no "
            f"listings and are excluded rather than reported as zeroes.",
            f"- Seller concentration, measurable here for the first time: the top 1% of "
            f"sellers hold {ts['seller_top1_share']}% of all ratings and the top 10% hold "
            f"{ts['seller_top10_share']}%. {ts['sellers_one_product']:,} of the "
            f"{ts['sellers']:,} sellers have exactly one product in the sample.",
            "",
            f"- [Taxonomy CSV]({RAW}/data/gumroad-taxonomy.csv): "
            f"{ts['obs']:,} rows with category, product URL, seller, price, currency, "
            f"USD price, rating count, star rating, subscription flag, title.",
            f"- [taxonomy-summary.json]({RAW}/data/taxonomy-summary.json): every "
            f"per-category figure as JSON.",
            f"- [All {ts['nodes']} categories, ranked]({SITE}/t/index.html)",
            "",
        ]
        lines += [f"- [{x['node']}]({SITE}/t/{T.flat(x['slug'])}.html)"
                  for x in ts["by_node"] if x["n"] >= T.MIN_LISTINGS]

        # Third unit of observation. Kept out of the two product sections above on
        # purpose: a seller-level figure is not a listing-level figure and must not be
        # quoted as one.
        import build_sellers as S
        ss = json.loads((ROOT / "data" / "sellers-summary.json").read_text())
        srows = list(csv.DictReader((ROOT / "data" / "gumroad-sellers.csv").open()))
        lines += [
            "",
            "## Third view: who is selling",
            "",
            f"> Derived from the same taxonomy file, one row per seller instead of one "
            f"per listing: **{ss['sellers']:,} distinct Gumroad sellers behind "
            f"{ss['products']:,} products**. The top 1% ({ss['top1_count']} sellers) hold "
            f"**{ss['top1_share']}% of all {ss['ratings_total']:,} ratings measured**; the "
            f"top 10% hold {ss['top10_share']}%.",
            "",
            f"- **The concentration is not a catalogue effect.** Rank correlation between "
            f"catalogue size and demand is only {ss['spearman_products_ratings']}. The "
            f"median seller inside the top 1% has {ss['top1_med_products']} products and "
            f"{ss['top1_solo']} of the {ss['top1_count']} have exactly one.",
            f"- {ss['solo_sellers']:,} of {ss['sellers']:,} sellers "
            f"({ss['solo_share_pct']}%) have a single product in the sample; as a class "
            f"they hold {ss['solo_ratings_share']}% of all ratings.",
            f"- {ss['sellers_zero_ratings']:,} sellers "
            f"({round(100 * ss['sellers_zero_ratings'] / ss['sellers'])}%) have no ratings "
            f"at all across their whole measured catalogue.",
            f"- **A seller's product count is a crawl lower bound, not a catalogue.** The "
            f"collector took three pages per category node, so sellers whose listings rank "
            f"deep are under-counted. Never quote it as catalogue size.",
            "",
            f"- [Seller CSV]({RAW}/data/gumroad-sellers.csv): all {ss['sellers']:,} "
            f"sellers with product count, categories, rating total, demand rank, share of "
            f"all ratings, price median and range, and their most-rated listing.",
            f"- [sellers-summary.json]({RAW}/data/sellers-summary.json): every figure "
            f"above as JSON.",
            f"- [Seller concentration, ranked]({SITE}/s/index.html)",
            "",
        ]
        lines += [f"- [{r['seller']}]({SITE}/s/{S.seller_slug(r['seller'])}.html)"
                  for r in srows if int(r["products"]) >= S.MIN_PRODUCTS]
    lines += [
        "",
        "## Optional",
        "",
        f"- [What Actually Sells on Gumroad]({BUY}): paid report, {PRICE}. The analysis, "
        f"not the data — the data above is free and complete.",
        f"- [Free CSV mirror on Gumroad]({FREE_MIRROR}): the same file, $0.",
        "",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------- README

def build_readme(s, mix, ts, ss):
    top, bottom = s["by_category"][0], s["by_category"][-1]
    fx = s["fx_rates_to_usd"]
    tbl = "\n".join(
        f"| [{c['topic']}]({SITE}/c/{slug(c['topic'])}.html) | {c['rated_share']}% | "
        f"{c['med_ratings']:,} | {c['top_n']:,} | {money(c['median'])} | {money(c['p90'])} | "
        f"{c['subs']} |" for c in s["by_category"])
    hi = ", ".join(f"{c['topic']} ({c['rated_share']}%)" for c in s["by_category"][:3])
    lo = ", ".join(f"{c['topic']} ({c['rated_share']}%)" for c in s["by_category"][-3:])
    return f"""# What actually sells on Gumroad — measured

**{s['n']:,} live Gumroad products across {s['cats']} categories, collected 5 August 2026.**

> **{s['zero']} of the {s['n']:,} products in this sample — {s['zpct']}% — have no ratings at all.**
> They are listed, priced, and selling nothing. The gap between categories where that happens
> and ones where it doesn't runs from **{top['rated_share']}% of listings rated** at the top to
> **{bottom['rated_share']}%** at the bottom.

Highest demand: {hi}. Lowest: {lo}.

**Start with a question:**
{" &middot; ".join(f"[{lab}]({SITE}/g/{g}.html)" for g, lab in build_guides.GUIDES)}

**Or browse a category** for its full price distribution and every listing measured:
<{SITE}/>

## Two samples, published side by side

This repository now holds **two independently collected samples of the same
marketplace**, and they are kept apart on purpose rather than merged into a third set of
numbers matching neither.

| | Discover searches | Gumroad's category tree |
|---|---:|---:|
| Sampling frame | {s['cats']} chosen search terms | {ts['nodes_crawled']} published categories |
| Distinct products | {s['n']:,} | **{ts['n']:,}** |
| Listing observations | {s['obs']:,} | {ts['obs']:,} |
| Distinct sellers | not recorded | **{ts['sellers']:,}** |
| Identity key | card text | **product URL** |
| Median paid asking price | {money(s['med'])} | {money(ts['med'])} |
| Products with no ratings | {s['zpct']}% | {ts['zpct']}% |
| Data | [`gumroad-latest.csv`](data/gumroad-latest.csv) | [`gumroad-taxonomy.csv`](data/gumroad-taxonomy.csv) |

**Where they disagree, the disagreement is the finding.** The taxonomy walk reaches parts
of the catalogue that popular search terms never surface, and those parts are cheaper and
sell less. It is also the first version of this dataset that records **who** is selling:
{ts['sellers_one_product']:,} of the {ts['sellers']:,} sellers have exactly one product in
the sample, while the top 10% of sellers hold **{ts['seller_top10_share']}% of every
rating measured**.

**One caveat governs every per-category figure in the taxonomy sample.** Each node was
crawled up to three pages deep, which caps it at {ts['cap']} listings, and
{ts['nodes_at_cap']} of the {ts['nodes']} categories hit that cap. A category's listing
count is therefore a **crawl depth, not a category size** — never quote it as the number
of products in a category. {ts['nodes_empty']} nodes returned nothing and are excluded
rather than reported as zeroes.

→ [**All {ts['nodes']} categories, ranked**]({SITE}/t/index.html)

## A third view: who is selling

Attributing every listing to its storefront gives a third unit of observation and the
strongest finding in the dataset. Every other public Gumroad dataset is a list of products;
this one has **{ss['sellers']:,} sellers behind {ss['products']:,} products**.

> **The top 1% of sellers — {ss['top1_count']} of them — hold {ss['top1_share']}% of all
> {ss['ratings_total']:,} ratings measured. The median seller inside that 1% has
> {ss['top1_med_products']} products, and {ss['top1_solo']} of them have exactly one.**

- **Concentration is not a catalogue effect.** Rank correlation between catalogue size and
  demand is **{ss['spearman_products_ratings']}** — real, weak, and not the mechanism.
- **{ss['solo_sellers']:,} of {ss['sellers']:,} sellers ({ss['solo_share_pct']}%) have a
  single product**, and as a class hold {ss['solo_ratings_share']}% of all ratings.
- **{ss['sellers_zero_ratings']:,} sellers ({round(100 * ss['sellers_zero_ratings'] / ss['sellers'])}%)
  have no ratings at all** across their entire measured catalogue. That is the modal outcome.
- Top 10% of sellers: {ss['top10_share']}% of ratings. Bottom half: {round(100 - ss['top50_share'], 1)}%.

**The caveat that governs every count here:** a seller's product count is *what this crawl
found*, three pages deep per category node — a **lower bound**, not a catalogue, biased
down for the sellers whose listings rank deepest.

Data: [`data/gumroad-sellers.csv`](data/gumroad-sellers.csv) (one row per seller),
[`data/sellers-summary.json`](data/sellers-summary.json), derived by
[`scripts/normalize_sellers.py`](scripts/normalize_sellers.py) from the listing table, so
the two can never disagree.

→ [**All {ss['sellers']:,} sellers, ranked**]({SITE}/s/index.html)

## The demand table

The first column carries most of the information. **% Rated** is the share of listings in a
category with at least one rating — the cleanest available signal for whether products there
sell at all, or simply sit. It is free here in full; nothing is held back from this table.

| Category | % Rated | Median ratings | Top product | Median price | 90th pct | Subs |
|---|---:|---:|---:|---:|---:|---:|
{tbl}

## What the numbers say

- **A third of everything listed has never sold a measurable unit.** {s['zpct']}% with zero ratings is
  the background rate you compete against — and it held steady as the sample grew from 468 to
  {s['n']:,} products, so it is not an artefact of a small sample.
- **Game and 3D assets top the demand table.** {top['topic']} is the only category where every listing
  sampled has ratings.
- **Document, template and craft-pattern categories look busy and move slowly.** {bottom['topic']} sits
  at {bottom['rated_share']}% rated with a median of {bottom['med_ratings']} rating(s).
- **Price and demand are close to unrelated.** The highest-demand categories are among the cheapest.
- **Subscriptions are rare:** {s['subs']} of {s['n']:,} products bill recurring.
- **Price anchors (USD):** median {money(s['med'])}, 75th percentile {money(s['p75'])},
  90th {money(s['p90'])}.

## Method, and what this cannot tell you

{s['cats']} searches were run against Gumroad Discover and the top results of each captured with a
headless browser: asking price, the currency it was displayed in, subscription flag, rating count,
title.

**Rating count is a proxy for units sold, not a sales figure** — only some buyers rate, and that
share differs by category. Use this to rank categories against each other rather than to estimate
revenue. It is one snapshot rather than a trend, and reflects the visible top of each category
rather than its full population.

**On currency.** Gumroad localises displayed prices, so a single search returns a mixture —
{mix}, with {s['mixed_cats']} of the {s['cats']} categories containing more than one. Every price here is converted to USD at ECB reference rates for {s['fx_date']}
(£1 = ${fx['£']:.4f}, €1 = ${fx['€']:.4f}). The raw price and its currency are both kept in the CSV,
so the conversion can be checked or redone. Figures published before 2026-08-07 did not do this and
were computed across mixed units; they are superseded by these.

[**50-row raw sample**](docs/sample-50-rows.csv) — the exact shape of the data.

## The full dataset — free, no signup

All {s['n']:,} rows are in this repo and always will be:
[`data/gumroad-latest.csv`](data/gumroad-latest.csv) — category, price, currency, USD price, rating
count, subscription flag, product title. The collector that produced it is
[`scripts/collect.py`](scripts/collect.py), and the USD normalisation is
[`scripts/normalize.py`](scripts/normalize.py). Every figure above is reproducible from those files,
which is the point: check the work rather than trust it.

No email wall, no account, no "request access". Use it for anything, with or without credit.

**Prefer a one-click download?** The same CSV is mirrored as a free Gumroad product:
[**Gumroad Market Data 2026 — free CSV**]({FREE_MIRROR}). $0 with a $0 minimum; the suggested
amount is optional and typing zero is the expected case.

**Citing this?** `main` moves as the data is corrected. Pin to
[**release v{VERSION}**]({RELEASE}) instead — the exact bytes every figure above was computed from,
at [a download URL that will not change]({RELEASE_CSV}). The release notes record what changed
from v1.0, including the mixed-currency error it corrects.

**Archived with a DOI:** [{DOI}](https://doi.org/{DOI}) (CC BY 4.0). Cite it as:

> Sujeito Operator (2026). *What Actually Sells on Gumroad: {s['n']:,} live products across
> {s['cats']} categories (August 2026)* [Data set]. Zenodo. https://doi.org/{DOI}

**Licence:** the data is **CC BY 4.0**, the collector code is **MIT**. See [`LICENSE`](LICENSE).

## The written report — {PRICE}

What is **not** free is the analysis: a report that reads the table rather than prints it —
which categories are openings versus crowded rooms, where price and demand come apart, and
what the {s['zpct']}%-unrated background rate means if you are choosing what to build next.

You are paying for the interpretation, not for the rows. The rows are above, free. If the
data is all you wanted, take it and skip this.

→ **[Read the report — {PRICE}]({BUY})**

---

Collected and written by an autonomous AI agent, and generated from the data by
[`scripts/build_site.py`](scripts/build_site.py) so that no published surface can drift away from
the file it describes.
"""


def currency_mix(rows):
    """'1,239 listings in GBP, 228 in USD and 44 in EUR' — computed, never typed."""
    names = {"£": "GBP", "$": "USD", "€": "EUR"}
    counts = collections.Counter(r["cur"] for r in rows)
    parts = [f"{n:,} in {names[c]}" for c, n in counts.most_common()]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def main():
    s = json.loads((ROOT / "data" / "summary.json").read_text())
    rows = list(csv.DictReader((ROOT / "data" / "gumroad-latest.csv").open()))
    for r in rows:
        r["price"] = float(r["price"])
        r["price_usd"] = float(r["price_usd"])
        r["n"] = float(r["n"] or 0)

    ts = json.loads((ROOT / "data" / "taxonomy-summary.json").read_text())

    # The seller table is a PURE derivation of data/gumroad-taxonomy.csv — no network, no
    # new collection — so it is regenerated here rather than left to be run by hand. A
    # derived file that only updates when somebody remembers is exactly how a published
    # figure drifts away from the file it describes, which this whole script exists to
    # prevent. The collectors and the two listing normalisers are NOT called here: those
    # do touch the network.
    import normalize_sellers
    normalize_sellers.main()
    ss = json.loads((ROOT / "data" / "sellers-summary.json").read_text())

    mix = currency_mix(rows)
    (ROOT / "README.md").write_text(build_readme(s, mix, ts, ss))
    (ROOT / "docs" / "index.html").write_text(build_index(s, mix, ts, ss))
    cdir = ROOT / "docs" / "c"
    cdir.mkdir(exist_ok=True)
    topics = [c["topic"] for c in s["by_category"]]
    for i, c in enumerate(s["by_category"]):
        sibs = [topics[(i + k) % len(topics)] for k in range(1, 7)]
        page = build_category(c, [r for r in rows if r["q"] == c["topic"]], s, sibs)
        (cdir / f"{slug(c['topic'])}.html").write_text(page)
    guides = build_guides.build(s, rows, ROOT / "docs" / "g")

    # Second sample, second surface. Kept as its own tree under docs/t/ rather than
    # merged into docs/c/: the two samples have different frames and merging them would
    # produce a third set of figures matching neither published file.
    trows = list(csv.DictReader((ROOT / "data" / "gumroad-taxonomy.csv").open()))
    for r in trows:
        r["price"] = float(r["price"])
        r["price_usd"] = float(r["price_usd"])
        r["n"] = float(r["n"] or 0)
    taxo = build_taxonomy.build(ts, trows, ROOT / "docs" / "t")

    # Third surface, third unit of observation: one row per SELLER. Same source file as
    # docs/t/, so it cannot disagree with it; its own directory because a seller-level
    # figure averaged across listing rows would be weighted by how many categories
    # Gumroad filed each product under.
    sellers = build_sellers.build(ts, trows, ROOT / "docs" / "s")

    (ROOT / "docs" / "sitemap.xml").write_text(
        sitemap(s["by_category"], guides, taxo, sellers))
    (ROOT / "docs" / "llms.txt").write_text(
        llms_txt(s, s["by_category"], build_guides.GUIDES, ts))

    # The 50-row sample is a published surface too, and it silently kept the old
    # column set through the USD normalisation. Generate it rather than hand-maintain.
    src = list(csv.reader((ROOT / "data" / "gumroad-latest.csv").open()))
    with (ROOT / "docs" / "sample-50-rows.csv").open("w", newline="") as f:
        csv.writer(f).writerows(src[:51])

    print(f"README + index + {len(guides)} guides + {len(s['by_category'])} category pages"
          f" + {len(taxo)} taxonomy pages + taxonomy index + {len(sellers)} seller pages"
          f" + seller index + sitemap + sample")


if __name__ == "__main__":
    main()
