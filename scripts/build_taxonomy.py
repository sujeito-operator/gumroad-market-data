#!/usr/bin/env python3
"""Generate the taxonomy surface: one page per Gumroad category node.

WHY THIS EXISTS. The 42 category pages under /c/ come from 42 search terms somebody
chose. They are the site's long-tail surface and they are capped at 42 by construction.
`collect_taxonomy.py` walked Gumroad's OWN category tree instead — 359 nodes, of which
261 returned listings — so the same page shape now has 261 chances to match a query
instead of 42, and every one of them is a category Gumroad itself publishes rather than
a term we invented.

Traffic is this project's measured binding constraint (23 lifetime views, most of them
our own). This is the largest increase in indexable surface available without anyone's
permission, and it is built from data already collected.

WHAT EVERY PAGE MUST SAY, AND WHY
---------------------------------
The crawl took up to three pages per node, so 166 of the 261 nodes came back at exactly
71 listings. **A node's sample is the listings Gumroad ranks first, not the category's
population.** Every page says so in the method line. Without it, "71 listings" reads as
"this category has 71 products", which is false and would be the third time this project
published a number whose label was wrong.

Nodes below MIN_LISTINGS get a row in the index with their figures but no page of their
own: a page built on nine listings is a thin page, and thin pages are how a site earns a
quality problem rather than traffic.

Imported and called by build_site.py, which owns the shared chrome. Never hand-edit
docs/t/*.html.
"""
import collections, json, re

import build_site as B

# A page needs enough listings for its medians to mean anything. 30 keeps 212 of the
# 261 nodes and drops the tail whose quartiles would be noise.
MIN_LISTINGS = 30


# The collector stores `t` as the card's rendered text truncated to ~70 characters, so
# it carries the title AND the seller name AND a "Top creator" badge AND the rating
# widget AND the price — all of which this page already shows in their own columns.
# Printing it raw reads as scraped junk next to those columns. This trims the trailing
# widgets for DISPLAY ONLY; the CSV keeps the untouched string, so nothing published as
# data is altered by a cosmetic decision here.
_RATING = re.compile(r"\s\d\.\d\s*\((?:[\d.,]+K?)?\)?.*$")
_PRICE_TAIL = re.compile(r"\s*[£$€¥][\d.,]*\+?(?:\s*a\s*mo(?:nth)?)?\s*$")
_BADGE = re.compile(r"\s*Top creator\s*$")


def card_title(t):
    out = _RATING.sub("", t)
    for _ in range(3):
        out = _BADGE.sub("", _PRICE_TAIL.sub("", out))
    return out.strip() or t


def flat(slug):
    """'3d/vrchat/tutorials-and-guides' -> '3d-vrchat-tutorials-and-guides'.

    Gumroad's slugs are already URL-safe; flattening keeps docs/t/ a single directory,
    which GitHub Pages serves without any per-directory index.
    """
    return slug.replace("/", "-")


def leaf(node):
    return node.split(" > ")[-1]


def parent_slug(slug):
    return slug.rsplit("/", 1)[0] if "/" in slug else None


def build_tree(nodes):
    """slug -> record, plus children lists, so each page can link its own neighbourhood."""
    by_slug = {x["slug"]: x for x in nodes}
    children = collections.defaultdict(list)
    for x in nodes:
        p = parent_slug(x["slug"])
        if p in by_slug:
            children[p].append(x)
    for v in children.values():
        v.sort(key=lambda x: -x["n"])
    return by_slug, children


def link(x, has_page, prefix=""):
    """Link a node to its own page if it has one, otherwise to its index row."""
    label = B.esc(leaf(x["node"]))
    if x["slug"] in has_page:
        return f'<a href="{prefix}{flat(x["slug"])}.html">{label}</a>'
    return f'<a href="{prefix}index.html#{flat(x["slug"])}">{label}</a>'


def band_rows(prices):
    return B.buckets(prices)


def method_note(x, s):
    return (f"<p><strong>What this sample is.</strong> These are the "
            f"{x['n']} listings Gumroad ranked first in "
            f"<em>{B.esc(x['node'])}</em> when the category was crawled on 5 August 2026, "
            f"up to three pages deep. It is <strong>not</strong> a count of everything in "
            f"the category, and nothing here supports a claim about category size — "
            f"{s['nodes_at_cap']} of the {s['nodes']} categories came back at the same "
            f"{s['cap']}-listing crawl cap. What it does support is comparison: every "
            f"category was sampled the same way, from the same ranking, on the same day. "
            f"Prices are converted to USD at ECB reference rates for {s['fx_date']}.</p>")


def node_page(x, rows, s, by_slug, children, has_page):
    lf = leaf(x["node"])
    prices = [r["price_usd"] for r in rows if r["price_usd"] > 0]
    listed = sorted(rows, key=lambda r: -r["n"])
    body_rows = "".join(
        f"<tr><td>{B.esc(card_title(r['t']))}</td><td>{B.esc(r['seller'])}</td>"
        f"<td class=n>{B.money(r['price_usd'])}</td>"
        f"<td class=n>{r['cur']}{r['price']:,.2f}</td>"
        f"<td class=n>{int(r['n']):,}</td></tr>" for r in listed)

    canonical = f"{B.SITE}/t/{flat(x['slug'])}.html"
    title = (f"{x['node']}: {x['n']} Gumroad listings, median "
             f"{B.money(x['median'])} — August 2026")
    desc = (f"Measured prices and demand for {lf} on Gumroad: median "
            f"{B.money(x['median'])}, 90th percentile {B.money(x['p90'])}, "
            f"{x['rated_share']}% of listings carry at least one rating, "
            f"{x['sellers']} distinct sellers. {x['n']} live listings from Gumroad's own "
            f"{B.esc(x['node'])} category. Free data, CC BY 4.0, August 2026.")
    ld = json.dumps({
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": f"Gumroad {x['node']}: {x['n']} live listings with prices, sellers and rating counts (August 2026)",
        "description": desc,
        "url": canonical,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "isPartOf": {"@type": "Dataset",
                     "name": "Gumroad Market Data — full category taxonomy",
                     "url": B.SITE + "/t/index.html",
                     "identifier": "https://doi.org/" + B.DOI},
        "variableMeasured": ["category", "asking price", "currency", "price in USD",
                             "seller", "rating count", "subscription flag", "product title"],
        "creator": {"@type": "Organization", "name": "Sujeito Operator",
                    "url": "https://github.com/sujeito-operator"},
        "temporalCoverage": "2026-08-05",
    }, indent=2)
    extra = f'<script type="application/ld+json">\n{ld}\n</script>\n'

    avg = s["zpct"]
    unrated = 100 - x["rated_share"]
    if x["rated_share"] >= 95:
        verdict = (f"Effectively every listing sampled in {B.esc(lf)} carries at least one "
                   f"rating. That is the strongest demand signal this dataset produces.")
    elif unrated < avg:
        verdict = (f"{unrated}% of {B.esc(lf)} listings have never been rated, against "
                   f"{avg}% across all {s['n']:,} products measured — this category "
                   f"transacts more than the market does.")
    elif unrated == avg:
        verdict = (f"{unrated}% of {B.esc(lf)} listings have never been rated, exactly the "
                   f"{avg}% background rate across all {s['n']:,} products measured.")
    else:
        verdict = (f"{unrated}% of {B.esc(lf)} listings have never been rated, against "
                   f"{avg}% across all {s['n']:,} products measured — more of what is "
                   f"listed here is sitting unsold than in the market at large.")

    # Seller concentration, which the 42-search sample could not answer at all.
    per_seller = collections.Counter(r["seller"] for r in rows)
    solo = sum(1 for v in per_seller.values() if v == 1)
    biggest, biggest_n = per_seller.most_common(1)[0]
    seller_line = (
        f"<p><strong>Who is selling.</strong> The {x['n']} listings come from "
        f"{x['sellers']} distinct sellers; {solo} of them appear exactly once. The "
        f"busiest, <code>{B.esc(biggest)}</code>, holds {biggest_n} of them. "
        f"The top tenth of listings by rating count carry {x['top10_share']}% of every "
        f"rating in this category — concentration is the normal state here, not the "
        f"exception.</p>")

    # Neighbourhood links: parent, children, siblings. The lesson from 2026-08-07 is
    # that a page with no outbound path is a dead end for a crawler and a visitor alike.
    nav_bits = []
    p = parent_slug(x["slug"])
    if p in by_slug:
        nav_bits.append("Up: " + link(by_slug[p], has_page))
    kids = children.get(x["slug"], [])
    if kids:
        nav_bits.append("Inside: " + " &middot; ".join(
            link(k, has_page) for k in kids[:10]))
    if p in by_slug:
        sibs = [k for k in children.get(p, []) if k["slug"] != x["slug"]][:8]
        if sibs:
            nav_bits.append("Alongside: " + " &middot; ".join(
                link(k, has_page) for k in sibs))
    nav_html = "".join(f"<nav class=sib>{b}</nav>" for b in nav_bits)

    return B.head(title, desc, canonical, extra) + f"""
<a class=home href="index.html">&larr; All {s['nodes']} Gumroad categories</a>
<h1>{B.esc(lf)}</h1>
<div class=sub>{B.esc(x['node'])} &middot; {x['n']} live Gumroad listings measured
&middot; 5 August 2026 &middot; prices in USD</div>

<div class=lede>{verdict}</div>

<div class=kv>
<div><b>{B.money(x['median'])}</b><span>Median asking price</span></div>
<div><b>{x['rated_share']}%</b><span>Listings with a rating</span></div>
<div><b>{x['med_ratings']:,}</b><span>Median ratings, of those rated</span></div>
<div><b>{B.money(x['p25'])} – {B.money(x['p75'])}</b><span>Middle half of prices</span></div>
<div><b>{B.money(x['p90'])}</b><span>90th percentile</span></div>
<div><b>{x['sellers']}</b><span>Distinct sellers</span></div>
</div>

<h2>Where the prices sit</h2>
<table><thead><tr><th>Price band</th><th class=n>Listings</th><th class=n>Share</th><th></th></tr>
</thead><tbody>{band_rows(prices)}</tbody></table>
<p>{x['free']} of the {x['n']} listings are priced at zero and {x['subs']} bill on a
subscription. Prices were displayed in {', '.join(x['currencies'])}.</p>

{seller_line}

<h2>Every listing measured</h2>
<p>The full sample for this category, most-rated first. <strong>Rating count is a floor
on units sold, not a sales figure</strong> — only some buyers rate, and that share
differs by category. Use it to rank listings against each other, never to estimate
revenue.</p>
<table><thead><tr><th>Listing</th><th>Seller</th><th class=n>USD</th><th class=n>As shown</th>
<th class=n>Ratings</th></tr></thead><tbody>{body_rows}</tbody></table>

<h2>Method</h2>
{method_note(x, s)}

<h2>The data behind this page</h2>
<p>This page is generated from a free, openly licensed dataset of {s['n']:,} distinct
Gumroad products across {s['nodes']} of Gumroad's own categories, with the seller
recorded for every one —
<a href="{B.REPO}/blob/main/data/gumroad-taxonomy.csv"><code>data/gumroad-taxonomy.csv</code></a>,
<a href="{B.REPO}/blob/main/scripts/collect_taxonomy.py">the collector</a> and
<a href="{B.REPO}/blob/main/scripts/normalize_taxonomy.py">the normaliser</a> are all
public. CC BY 4.0, no signup, no email wall.</p>

<h2>Next</h2>
<ul class=next>
<li><b><a href="../g/gumroad-pricing.html">What to charge on Gumroad</a></b>
<span>Why this category's median is a starting point rather than an answer: across the
whole market price and demand turn out to be close to unrelated.</span></li>
<li><b><a href="../g/what-to-sell-on-gumroad.html">What to sell</a></b>
<span>Which categories show demand and which are mostly unsold inventory, ranked by the
same rated-share figure quoted at the top of this page.</span></li>
<li><b><a href="index.html">All {s['nodes']} categories, ranked</a></b>
<span>The same figures for every category Gumroad publishes, in one table.</span></li>
</ul>

{B.buy_block("What is <em>not</em> free is the analysis: which categories are openings "
             "versus crowded rooms, where price and demand come apart, and what the "
             "background rate of unsold listings means if you are choosing what to "
             "build next.")}

{nav_html}
<nav class=sib>Guides: {" &middot; ".join(f'<a href="../g/{g}.html">{lab}</a>'
    for g, lab in __import__("build_guides").GUIDES)}</nav>
""" + B.FOOTER


def index_page(s, has_page):
    rows = []
    for x in s["by_node"]:
        name = ("&nbsp;&nbsp;" * x["depth"]) + B.esc(leaf(x["node"]))
        cell = (f'<a href="{flat(x["slug"])}.html">{name}</a>'
                if x["slug"] in has_page else name)
        rows.append(
            f'<tr id="{flat(x["slug"])}"><td>{cell}</td>'
            f"<td class=n>{x['n']}</td><td class=n>{x['sellers']}</td>"
            f"<td class=n>{x['rated_share']}%</td><td class=n>{x['med_ratings']:,}</td>"
            f"<td class=n>{B.money(x['median'])}</td><td class=n>{B.money(x['p90'])}</td></tr>")
    # THE PLACEHOLDER IS DERIVED, NOT TYPED. The first hand-written version suggested
    # "notion" and "lightroom" — both real Gumroad niches, neither a node in Gumroad's
    # own category tree, so both would have returned nothing. A search box whose own
    # example finds zero rows teaches the reader the box is broken on their first
    # keystroke. These are picked from the tree itself and re-picked on every build, so
    # a re-crawl that renames a branch cannot leave a dead suggestion behind.
    PLACEHOLDER_WANTED = ["vrchat", "brushes", "music", "course", "photo",
                          "blender", "design", "audio", "template", "font"]
    haystack = " ".join(
        f"{flat(x['slug'])} {leaf(x['node'])}".lower() for x in s["by_node"])
    hits = [w for w in PLACEHOLDER_WANTED if w in haystack][:4]
    if not hits:                       # cannot happen with a populated tree; not a crash
        hits = [leaf(s["by_node"][0]["node"]).lower()]
    placeholder = B.esc(", ".join(hits) + "…")

    canonical = f"{B.SITE}/t/index.html"
    title = (f"Every Gumroad category, measured — {s['n']:,} products, "
             f"{s['sellers']:,} sellers (August 2026)")
    desc = (f"Prices and demand for all {s['nodes']} categories Gumroad publishes: "
            f"{s['n']:,} distinct products from {s['sellers']:,} sellers, median asking "
            f"price {B.money(s['med'])}, {s['zpct']}% of products with no ratings at all. "
            f"Free dataset, CC BY 4.0.")
    ld = json.dumps({
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": f"Gumroad Market Data — full category taxonomy: {s['n']:,} products, {s['sellers']:,} sellers, {s['nodes']} categories (August 2026)",
        "description": desc,
        "url": canonical,
        "sameAs": B.REPO,
        "identifier": "https://doi.org/" + B.DOI,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "keywords": ["Gumroad", "digital products", "creator economy", "marketplace data",
                     "seller concentration", "product pricing", "open dataset"],
        "datePublished": "2026-08-07",
        "temporalCoverage": "2026-08-05",
        "variableMeasured": ["category", "asking price", "currency", "price in USD",
                             "seller", "rating count", "star rating", "subscription flag",
                             "product title", "product URL"],
        "creator": {"@type": "Organization", "name": "Sujeito Operator",
                    "url": "https://github.com/sujeito-operator"},
        "distribution": [{
            "@type": "DataDownload", "encodingFormat": "text/csv",
            "name": f"Taxonomy sample ({s['obs']:,} observations, {s['n']:,} distinct products)",
            "contentUrl": B.RAW + "/data/gumroad-taxonomy.csv"}],
    }, indent=2)
    extra = f'<script type="application/ld+json">\n{ld}\n</script>\n'

    return B.head(title, desc, canonical, extra) + f"""
<a class=home href="../">&larr; What actually sells on Gumroad</a>
<h1>Every category Gumroad publishes, measured</h1>
<div class=sub>{s['n']:,} distinct products &middot; {s['sellers']:,} sellers &middot;
{s['nodes']} categories &middot; 5 August 2026 &middot; prices in USD</div>

<div class=lede><strong>{s['sellers_one_product']:,} of the {s['sellers']:,} sellers here
have exactly one product, and the top tenth of sellers hold
{s['seller_top10_share']}% of every rating in the sample.</strong> This is the first
version of this dataset that records who is selling, so it is the first that can say
that at all.</div>

<div class=kv>
<div><b>{s['n']:,}</b><span>Distinct products</span></div>
<div><b>{s['sellers']:,}</b><span>Distinct sellers</span></div>
<div><b>{s['nodes']}</b><span>Categories with listings</span></div>
<div><b>{B.money(s['med'])}</b><span>Median paid price</span></div>
<div><b>{s['zpct']}%</b><span>Products with no rating</span></div>
<div><b>{s['top1_share']}%</b><span>Ratings held by the top 1% of products</span></div>
</div>

<h2>What this sample says that the first one could not</h2>
<ul>
<li><strong>The market is more concentrated than the earlier sample suggested.</strong>
The top 1% of products carry {s['top1_share']}% of all {s['ratings_total']:,} ratings
measured, and the top 10% carry {s['top10_share']}%.</li>
<li><strong>Sellers, not just products, are concentrated.</strong> The top 1% of sellers
hold {s['seller_top1_share']}% of the ratings; the busiest single seller has
{s['seller_max_products']} listings in this sample while the median seller has
{s['med_products_per_seller']}.</li>
<li><strong>Asking prices are lower than a search-term sample shows.</strong> Median paid
listing {B.money(s['med'])}, 75th percentile {B.money(s['p75'])}, 90th
{B.money(s['p90'])}. Walking the whole taxonomy reaches parts of the catalogue that
popular search terms never surface, and those parts are cheaper.</li>
<li><strong>{s['zpct']}% of products have no ratings at all</strong> — {s['zero']:,} of
{s['n']:,}. That is the background rate you compete against.</li>
<li><strong>Subscriptions stay rare:</strong> {s['subs']} of {s['n']:,} products bill
recurring.</li>
</ul>

<h2>Method, and the one thing this cannot tell you</h2>
<p>The sampling frame is <strong>Gumroad's own published category tree</strong>, read out
of the category picker rather than invented here: {s['nodes_frame']} nodes were
crawled, {s['nodes']} returned listings and {s['nodes_empty']} returned none and are
excluded rather than reported as zeroes — "we found nothing" and "there is nothing" are
different claims and only the first is evidenced. A further
<strong>{s['nodes_unrecognised']} are excluded because Gumroad's discover endpoint does not
recognise them</strong> and answers with the site-wide default feed instead of saying so;
they were published as categories until 2026-08-11 and the six are named, with the test
that catches them, in <code>data/taxonomy-summary.json</code>. Each node was taken up to three pages
deep, which caps a node at {s['cap']} listings; {s['nodes_at_cap']} nodes hit that cap.
<strong>So a category's listing count here is a crawl depth, not a category size</strong>,
and no figure on this site should be read as "how many products are in this category".
What the design does support is comparison between categories, because every one was
sampled identically.</p>
<p>A row in the CSV is a listing observation: {s['obs']:,} observations cover
{s['n']:,} distinct products, because Gumroad files {s['multi']:,} of them under more
than one category. Every market-wide figure above counts a product once, keyed on its
product URL — an exact identity key, unlike the card-text key the earlier sample had to
use. Prices are converted to USD at ECB reference rates for {s['fx_date']}; the raw
price and its currency are both kept in the file.</p>

<h2>Every category</h2>
<p>Ranked by the share of listings carrying at least one rating — the cleanest available
signal for whether a category transacts at all. Indented names are subcategories of the
row above them. Categories with fewer than {MIN_LISTINGS} listings sampled are shown
here but have no page of their own; their quartiles would be noise.</p>
<p id=catfilter hidden><label for=catq><strong>Find yours:</strong></label>
<input id=catq type=search autocomplete=off spellcheck=false
 placeholder="{placeholder}"
 style="padding:.45em .7em;font:inherit;min-width:16em;max-width:100%">
<span id=catn></span></p>
<table><thead><tr><th>Category</th><th class=n>Listings</th><th class=n>Sellers</th>
<th class=n>% Rated</th><th class=n>Median ratings</th><th class=n>Median price</th>
<th class=n>90th pct</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
<script>
/* The filter is INJECTED BY SCRIPT, not rendered visible. A search box that does
   nothing without JS is worse than no search box, so the paragraph ships `hidden`
   and only this line reveals it. Every row stays in the DOM either way, so the
   page degrades to exactly what it was before. */
(function () {{
  var box = document.getElementById('catfilter');
  var q = document.getElementById('catq');
  var n = document.getElementById('catn');
  var rows = [].slice.call(document.querySelectorAll('table tbody tr'));
  if (!box || !q || !rows.length) return;
  /* Match on the row id as well as its text. The visible cell holds only the LEAF
     name — the row for "3D > VRChat > Avatar Systems" reads "Avatar Systems" — so
     text alone would not find a category by its branch. The id is the full path. */
  var hay = rows.map(function (r) {{
    return ((r.id || '') + ' ' + (r.textContent || ''))
      .toLowerCase().replace(/[^a-z0-9]+/g, ' ');
  }});
  var total = rows.length;
  function run() {{
    var terms = q.value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').split(' ')
      .filter(Boolean);
    var shown = 0;
    for (var i = 0; i < rows.length; i++) {{
      var hit = true;
      for (var j = 0; j < terms.length; j++) {{
        if (hay[i].indexOf(terms[j]) === -1) {{ hit = false; break; }}
      }}
      rows[i].hidden = !hit;
      if (hit) shown++;
    }}
    if (!terms.length) {{ n.textContent = ''; return; }}
    if (shown) {{
      n.textContent = '  ' + shown + ' of ' + total +
        (shown === 1 ? ' category' : ' categories');
      return;
    }}
    /* A ZERO-RESULT SEARCH IS THE ONE CASE THE PAGE CANNOT SERVE, so it hands the
       reader the fallback instead of an empty table. This is the same offer the
       outreach makes — Gumroad's tree is what was crawled, and a niche that is not
       a node in it has no page here by construction. */
    n.innerHTML = '  no category here matches that — Gumroad\\'s own tree is what ' +
      'was crawled. <a href="mailto:{B.EMAIL}?subject=' +
      encodeURIComponent('Cut me this category: ') + encodeURIComponent(q.value) +
      '">Email it to me and I will cut it by hand</a>.';
  }}
  q.addEventListener('input', run);
  box.hidden = false;
  /* Deep link: ...t/index.html?q=brushes lands pre-filtered. */
  var m = /[?&]q=([^&]*)/.exec(location.search);
  if (m) {{ q.value = decodeURIComponent(m[1].replace(/\\+/g, ' ')); run(); }}
}})();
</script>

<h2>The data — free, no signup</h2>
<p>All {s['obs']:,} rows:
<a href="{B.REPO}/blob/main/data/gumroad-taxonomy.csv"><code>data/gumroad-taxonomy.csv</code></a>
— category, product URL, seller, asking price, currency, USD price, rating count, star
rating, subscription flag, title. Produced by
<a href="{B.REPO}/blob/main/scripts/collect_taxonomy.py"><code>collect_taxonomy.py</code></a>
and normalised by
<a href="{B.REPO}/blob/main/scripts/normalize_taxonomy.py"><code>normalize_taxonomy.py</code></a>,
with every per-category figure on this page emitted as
<a href="{B.REPO}/blob/main/data/taxonomy-summary.json"><code>taxonomy-summary.json</code></a>.
Data <strong>CC BY 4.0</strong>, code <strong>MIT</strong>. Use it for anything.</p>
<p>The earlier, smaller sample built on 42 Discover searches is still published and still
DOI-archived at <a href="https://doi.org/{B.DOI}">{B.DOI}</a>; it is a different
sampling frame, not a superseded file, and the two are kept side by side rather than
silently merged.</p>

<h2>The same data, one row per seller</h2>
<p>Every listing above carries the storefront that published it, so the same file answers
a question no other public Gumroad dataset can: <strong>the top 1% of
{s['sellers']:,} sellers hold {s['seller_top1_share']}% of every rating measured, and the
median seller in that 1% has two products.</strong> Concentration here is not a catalogue
effect.</p>
<p><a href="../s/index.html"><strong>All {s['sellers']:,} sellers, ranked &rarr;</strong></a>
&nbsp;&middot;&nbsp;
<a href="{B.REPO}/blob/main/data/gumroad-sellers.csv">the seller CSV</a> (free, CC BY 4.0)</p>

{B.buy_block("What is <em>not</em> free is the analysis: which categories are openings "
             "versus crowded rooms, where price and demand come apart, and what the "
             "background rate of unsold listings means if you are choosing what to "
             "build next.")}

<nav class=sib>Guides: {" &middot; ".join(f'<a href="../g/{g}.html">{lab}</a>'
    for g, lab in __import__("build_guides").GUIDES)}</nav>
""" + B.FOOTER


def retraction_page(node, slug, c):
    """The page that replaces a category we published and then withdrew.

    A URL that was public for four days does not get to become a 404. Somebody may have
    it open, linked or bookmarked, and "page not found" tells them nothing about why the
    numbers they read are gone — it reads as a broken site rather than as a correction.

    `noindex` because the intent is to retire the URL, not to rank it, and it is left out
    of the sitemap for the same reason. It is generated, not hand-written, so a rebuild
    reproduces it rather than resurrecting the category.
    """
    slug = flat(slug)
    title = f"{node}: withdrawn 2026-08-11 — this was not a category"
    desc = ("This page published price quartiles for a Gumroad category that Gumroad's "
            "discover endpoint does not recognise. The listings on it were the site-wide "
            "default feed. Withdrawn 2026-08-11.")
    return B.head(title, desc, f"{B.SITE}/t/{slug}.html",
                  '<meta name="robots" content="noindex">\n') + f"""
<p><a href="index.html">&larr; Every Gumroad category, measured</a></p>
<h1>{B.esc(node)}</h1>
<div class=corr><b>Withdrawn &mdash; {c['found']}</b>
This page carried a median price, a 90th percentile, a seller count and a rating share for
<code>{B.esc(node)}</code>. <strong>All of it was wrong, and the whole page has been
removed rather than corrected.</strong>
<p>Gumroad's <code>discover</code> endpoint does not return 404 for a category slug it does
not recognise &mdash; it answers 200 and serves the site-wide default feed. This node is one
of {len(c['nodes'])} in the published category tree that it does not recognise, so the
listings recorded here were never in this category. They were other people's products,
identical from one of these pages to the next.</p>
<p>The categories Gumroad does recognise are unaffected and are
<a href="index.html">all here</a>. What went wrong, and the test that now catches it, is in
<a href="{B.REPO}/blob/main/scripts/verify_taxonomy_nodes.py"><code>verify_taxonomy_nodes.py</code></a>;
the six are named in <a href="{B.REPO}/blob/main/data/taxonomy-summary.json"><code>taxonomy-summary.json</code></a>
under <code>unrecognised_node_correction</code>.</p></div>
</main></body></html>"""


def build(s, obs, outdir):
    """Write docs/t/. Returns the flattened slugs that got a page, for the sitemap."""
    outdir.mkdir(parents=True, exist_ok=True)
    by_slug, children = build_tree(s["by_node"])
    has_page = {x["slug"] for x in s["by_node"] if x["n"] >= MIN_LISTINGS}

    rows_by_slug = collections.defaultdict(list)
    for r in obs:
        rows_by_slug[r["slug"]].append(r)

    written = []
    for x in s["by_node"]:
        if x["slug"] not in has_page:
            continue
        page = node_page(x, rows_by_slug[x["slug"]], s, by_slug, children, has_page)
        (outdir / f"{flat(x['slug'])}.html").write_text(page)
        written.append(flat(x["slug"]))
    (outdir / "index.html").write_text(index_page(s, has_page))

    # The withdrawn six. NOT returned for the sitemap — a retraction is a courtesy to a
    # reader who already has the URL, not a page to get indexed.
    c = s.get("unrecognised_node_correction") or {}
    for node in c.get("nodes", []):
        sl = c["slugs"][node]
        (outdir / f"{flat(sl)}.html").write_text(retraction_page(node, sl, c))
    return written
