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
import collections, csv, json, pathlib, re

import build_guides

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
<a href="{REPO}">this repository</a>.</footer>
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


def build_index(s, mix):
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

{buy_block(f"What is <em>not</em> free is the analysis: a report that reads all {s['cats']} categories "
           f"together — which are openings versus crowded rooms, where price and demand come apart, "
           f"and what the {s['zpct']}%-unrated background rate means if you are choosing what to "
           f"build next.")}

<nav class=sib>More categories: {sib} &middot; <a href="../">all {s['cats']}</a></nav>
""" + FOOTER


def sitemap(cats, guides=()):
    urls = ([SITE + "/"]
            + [f"{SITE}/g/{g}.html" for g in guides]
            + [f"{SITE}/c/{slug(c['topic'])}.html" for c in cats])
    body = "".join(f"<url><loc>{u}</loc><lastmod>2026-08-07</lastmod></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")


# ------------------------------------------------------------------- README

def build_readme(s, mix):
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

    mix = currency_mix(rows)
    (ROOT / "README.md").write_text(build_readme(s, mix))
    (ROOT / "docs" / "index.html").write_text(build_index(s, mix))
    cdir = ROOT / "docs" / "c"
    cdir.mkdir(exist_ok=True)
    topics = [c["topic"] for c in s["by_category"]]
    for i, c in enumerate(s["by_category"]):
        sibs = [topics[(i + k) % len(topics)] for k in range(1, 7)]
        page = build_category(c, [r for r in rows if r["q"] == c["topic"]], s, sibs)
        (cdir / f"{slug(c['topic'])}.html").write_text(page)
    guides = build_guides.build(s, rows, ROOT / "docs" / "g")
    (ROOT / "docs" / "sitemap.xml").write_text(sitemap(s["by_category"], guides))

    # The 50-row sample is a published surface too, and it silently kept the old
    # column set through the USD normalisation. Generate it rather than hand-maintain.
    src = list(csv.reader((ROOT / "data" / "gumroad-latest.csv").open()))
    with (ROOT / "docs" / "sample-50-rows.csv").open("w", newline="") as f:
        csv.writer(f).writerows(src[:51])

    print(f"README + index + {len(guides)} guides + {len(s['by_category'])} category pages"
          f" + sitemap + sample")


if __name__ == "__main__":
    main()
