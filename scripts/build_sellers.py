#!/usr/bin/env python3
"""Generate the seller surface: docs/s/index.html plus one page per substantial seller.

WHY THIS EXISTS. Traffic is this project's measured binding constraint, and the seller
column is the only thing in the dataset no competing Gumroad dataset publishes. Every one
of them is a list of products. Attributing listings to sellers turns a price table into a
market structure, and the structure is the interesting part: the top 1% of sellers hold
more than half of all measured demand, and the median seller inside that 1% has two
products. Concentration here is not a catalogue effect.

WHY MIN_PRODUCTS EXISTS, AND WHY IT IS 5. 3,263 of the 4,545 sellers have exactly one
product in the sample. A page about one listing is a thin page, thin pages at volume are
how a site earns a quality problem rather than traffic, and a directory of 4,545 stubs
would be exactly the low-quality volume this project refuses to produce. At 5 the surface
is 274 pages, each carrying between 5 and 89 real measured listings with prices, rating
counts and categories. Every seller is still in `data/gumroad-sellers.csv` and every
seller with a rating is still on the ranked table in the index — the cut governs pages,
never data.

WHAT EVERY PAGE MUST SAY, AND WHY. A seller's product count here is *products found in
this crawl*, not their catalogue: the collector took three pages per category node, so a
seller whose listings rank deep is under-counted. This biases catalogue size DOWN for
everyone and the pages say so, because "dinzee has 89 products" reads as a complete
catalogue otherwise, and that is a claim this data cannot make.

These are public commercial listings under public Gumroad storefront names, linked back to
the storefront they came from. Nothing here is inferred about a person, and there is a
removal line on the index for anyone who wants their storefront out.

Imported and called by build_site.py, which owns the shared chrome. Never hand-edit
docs/s/*.html.
"""
import collections
import csv
import json
import re

import build_site as B
import build_taxonomy as T

# See the module docstring. This governs which sellers get a PAGE, never which are in the
# data and never which appear on the ranked index table.
MIN_PRODUCTS = 5

# The index table is the whole ranked market down to this cut. Below it a row would be
# "0 ratings, 1 product", repeated three thousand times, which informs nobody.
INDEX_ROWS = 300

_SAFE = re.compile(r"[^a-z0-9-]+")


def seller_slug(name):
    """Gumroad storefront names are already a URL subdomain, so they are lowercase
    alphanumerics and hyphens. Re-sanitise anyway: this string becomes a filename."""
    return _SAFE.sub("-", name.lower()).strip("-") or "seller"


def top_cat_link(row, ts):
    """Link a seller's most-used category to its taxonomy page — but only if it HAS one.

    build_taxonomy gives a page to nodes with >= MIN_LISTINGS listings; the rest live as
    rows on the taxonomy index. Sellers cluster in exactly the deep, small nodes that fall
    below that cut, so linking blindly produced 22 dead links on the first build. Fall
    back to the index anchor, which is what build_taxonomy.link() does for the same reason.
    """
    slug = next((x["slug"] for x in ts["by_node"] if x["node"] == row["top_category"]), None)
    label = B.esc(T.leaf(row["top_category"]))
    if slug is None:
        return label
    has_page = any(x["slug"] == slug and x["n"] >= T.MIN_LISTINGS for x in ts["by_node"])
    href = f"../t/{T.flat(slug)}.html" if has_page else f"../t/index.html#{T.flat(slug)}"
    return f'<a href="{href}">{label}</a>'


def rank_note(row, s):
    """Where this seller sits, in a sentence a reader can act on."""
    pct = 100 * row["ratings_rank"] / s["sellers"]
    if row["ratings_total"] == 0:
        return (f"<strong>Every listing measured for this seller has zero ratings.</strong> "
                f"That is not unusual and it is the point of publishing it: "
                f"{s['sellers_zero_ratings']:,} of the {s['sellers']:,} sellers in this "
                f"sample — {round(100 * s['sellers_zero_ratings'] / s['sellers'])}% — are in "
                f"the same position across their whole catalogue.")
    if pct <= 1:
        return (f"<strong>This seller is in the top 1% of the marketplace by measured "
                f"demand</strong> — rank {row['ratings_rank']:,} of {s['sellers']:,}. "
                f"That group of {s['top1_count']} sellers holds {s['top1_share']}% of every "
                f"rating in the sample, and its median member has {s['top1_med_products']} "
                f"products.")
    if pct <= 10:
        return (f"<strong>Rank {row['ratings_rank']:,} of {s['sellers']:,} sellers by "
                f"measured demand — the top {round(pct) or 1}%.</strong> The top decile of "
                f"sellers holds {s['top10_share']}% of all ratings measured, so this is the "
                f"part of the market where demand actually lands.")
    return (f"<strong>Rank {row['ratings_rank']:,} of {s['sellers']:,} sellers by measured "
            f"demand</strong>, with {row['ratings_total']:,} ratings across "
            f"{row['products']} listings. The bottom 90% of sellers share "
            f"{round(100 - s['top10_share'], 1)}% of all ratings between them.")


def seller_page(row, prods, s, ts, neighbours):
    name = row["seller"]
    listed = sorted(prods, key=lambda r: -r["n"])
    body_rows = "".join(
        f'<tr><td><a href="{B.esc(r["url"])}" rel="nofollow noopener">'
        f'{B.esc(T.card_title(r["t"]))}</a></td>'
        f"<td>{B.esc(T.leaf(r['node']))}</td>"
        f"<td class=n>{B.money(r['price_usd'])}</td>"
        f"<td class=n>{r['cur']}{r['price']:,.2f}</td>"
        f"<td class=n>{int(r['n']):,}</td></tr>" for r in listed)

    prices = [r["price_usd"] for r in prods if r["price_usd"] > 0]
    cats = collections.Counter(T.leaf(r["node"]) for r in prods)
    unrated = row["products"] - row["rated_products"]

    canonical = f"{B.SITE}/s/{seller_slug(name)}.html"
    title = (f"{name} on Gumroad: {row['products']} products, "
             f"{row['ratings_total']:,} ratings, median {B.money(row['med_price_usd'])} "
             f"— August 2026")
    desc = (f"Measured Gumroad listings for {name}: {row['products']} products across "
            f"{row['categories']} categories, {row['ratings_total']:,} ratings, median "
            f"asking price {B.money(row['med_price_usd'])}, ranked "
            f"{row['ratings_rank']:,} of {s['sellers']:,} sellers by measured demand. "
            f"Free open data, CC BY 4.0.")
    ld = json.dumps({
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": f"Gumroad seller {name}: {row['products']} measured listings (August 2026)",
        "description": desc,
        "url": canonical,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "isPartOf": {"@type": "Dataset",
                     "name": "Gumroad Market Data — seller structure",
                     "url": B.SITE + "/s/index.html",
                     "identifier": "https://doi.org/" + B.DOI},
        "variableMeasured": ["seller", "product count", "asking price", "currency",
                             "price in USD", "rating count", "category"],
        "creator": {"@type": "Organization", "name": "Sujeito Operator",
                    "url": "https://github.com/sujeito-operator"},
        "temporalCoverage": "2026-08-05",
    }, indent=2)
    extra = f'<script type="application/ld+json">\n{ld}\n</script>\n'

    nav = ""
    if neighbours:
        nav = ("<nav class=sib>Sellers ranked either side: " + " &middot; ".join(
            f'<a href="{seller_slug(x)}.html">{B.esc(x)}</a>' for x in neighbours)
            + "</nav>")

    return B.head(title, desc, canonical, extra) + f"""
<a class=home href="index.html">&larr; All {s['sellers']:,} Gumroad sellers, ranked</a>
<h1>{B.esc(name)}</h1>
<div class=sub><a href="{B.esc(row['profile_url'])}" rel="nofollow noopener">{B.esc(row['profile_url'])}</a>
&middot; {row['products']} products measured &middot; 5 August 2026 &middot; prices in USD</div>

<div class=lede>{rank_note(row, s)}</div>

<div class=kv>
<div><b>{row['products']}</b><span>Products measured</span></div>
<div><b>{row['ratings_total']:,}</b><span>Ratings, all products</span></div>
<div><b>{row['rated_products']} of {row['products']}</b><span>With any rating</span></div>
<div><b>{B.money(row['med_price_usd'])}</b><span>Median asking price</span></div>
<div><b>{B.money(row['min_price_usd'])} – {B.money(row['max_price_usd'])}</b><span>Price range</span></div>
<div><b>{row['categories']}</b><span>Categories appeared in</span></div>
</div>

<h2>Every listing measured</h2>
<p>Most-rated first. <strong>Rating count is a floor on units sold, not a sales figure</strong>
— only some buyers rate, and that share differs by category. Use it to rank listings against
each other, never to estimate revenue. {unrated} of these {row['products']} listings carry no
rating at all.</p>
<table><thead><tr><th>Listing</th><th>Category</th><th class=n>USD</th>
<th class=n>As shown</th><th class=n>Ratings</th></tr></thead><tbody>{body_rows}</tbody></table>

<h2>Where the prices sit</h2>
<table><thead><tr><th>Price band</th><th class=n>Listings</th><th class=n>Share</th><th></th></tr>
</thead><tbody>{B.buckets(prices)}</tbody></table>
<p>{row['free_products']} of the {row['products']} listings are priced at zero and
{row['subs']} bill on a subscription. Most-used category:
{top_cat_link(row, ts)}
({cats.most_common(1)[0][1]} of {row['products']} listings).</p>

<h2>Method, and the one thing this cannot tell you</h2>
<p><strong>This is not a catalogue.</strong> These are the listings that appeared while
walking Gumroad's own category tree on 5 August 2026, three pages deep per category — so
a seller whose products rank deep in a large category is under-counted here, and every
product count on this site is a <strong>lower bound</strong>. {ts['nodes_at_cap']} of the
{ts['nodes']} categories came back at the {ts['cap']}-listing crawl cap. Nothing here
supports a claim about how much this seller actually sells, how much they earn, or what
their full catalogue contains.</p>
<p>Prices are the asking price shown on the listing card, converted to USD at ECB
reference rates for {ts['fx_date']}; the raw price and its currency are both kept in the
data. Ratings are counts of public ratings, used as a proxy for relative demand.</p>

<h2>The data behind this page</h2>
<p>One row per seller for all {s['sellers']:,} sellers:
<a href="{B.REPO}/blob/main/data/gumroad-sellers.csv"><code>data/gumroad-sellers.csv</code></a>,
derived by <a href="{B.REPO}/blob/main/scripts/normalize_sellers.py"><code>normalize_sellers.py</code></a>
from the listing-level
<a href="{B.REPO}/blob/main/data/gumroad-taxonomy.csv"><code>gumroad-taxonomy.csv</code></a>.
CC BY 4.0, no signup, no email wall.</p>

{B.buy_block("What is <em>not</em> free is the analysis: which categories are openings "
             "versus crowded rooms, where price and demand come apart, and what the "
             "background rate of unsold listings means if you are choosing what to "
             "build next.")}

{nav}
<nav class=sib>Also: <a href="../g/{__import__("build_guides").SELLER_GUIDE}.html">does listing
more products work?</a> &middot;
<a href="../g/{__import__("build_guides").BREADTH_GUIDE}.html">does listing in more categories
work?</a> &middot; <a href="index.html">seller concentration</a> &middot;
<a href="../t/index.html">all {ts['nodes']} categories</a> &middot;
<a href="../">what actually sells on Gumroad</a></nav>
""" + B.FOOTER


def index_page(rows, s, ts, has_page):
    shown = [r for r in rows if r["ratings_total"] > 0][:INDEX_ROWS]
    body = "".join(
        f"<tr><td class=n>{r['ratings_rank']:,}</td><td>"
        + (f'<a href="{seller_slug(r["seller"])}.html">{B.esc(r["seller"])}</a>'
           if r["seller"] in has_page else B.esc(r["seller"]))
        + f"</td><td class=n>{r['products']}</td>"
          f"<td class=n>{r['ratings_total']:,}</td>"
          f"<td class=n>{r['ratings_share_pct']:.2f}%</td>"
          f"<td class=n>{B.money(r['med_price_usd'])}</td>"
          f"<td>{B.esc(T.leaf(r['top_category']))}</td></tr>" for r in shown)

    dec = "".join(
        f"<tr><td>{'Top' if i == 0 else ''} {i * 10}–{(i + 1) * 10}%</td>"
        f"<td class=n>{v}%</td><td><span class=bar style=\"width:{round(150 * v / max(s['decile_shares']))}px\"></span></td></tr>"
        for i, v in enumerate(s["decile_shares"]))

    canonical = f"{B.SITE}/s/index.html"
    title = (f"Who actually sells on Gumroad: {s['sellers']:,} sellers measured — "
             f"the top 1% hold {s['top1_share']}% of all demand")
    desc = (f"Seller-level structure of the Gumroad marketplace: {s['sellers']:,} sellers "
            f"behind {s['products']:,} products. The top 1% hold {s['top1_share']}% of "
            f"every rating; {s['solo_sellers']:,} sellers have exactly one product; "
            f"{s['sellers_zero_ratings']:,} have no ratings at all. Free open dataset, "
            f"CC BY 4.0, August 2026.")
    ld = json.dumps({
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": (f"Gumroad Market Data — seller structure: {s['sellers']:,} sellers behind "
                 f"{s['products']:,} products (August 2026)"),
        "description": desc,
        "url": canonical,
        "sameAs": B.REPO,
        "identifier": "https://doi.org/" + B.DOI,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "keywords": ["Gumroad", "sellers", "creator economy", "market concentration",
                     "digital products", "marketplace data", "open dataset"],
        "datePublished": "2026-08-07",
        "temporalCoverage": "2026-08-05",
        "variableMeasured": ["seller", "product count", "rating total", "share of ratings",
                             "median asking price", "price range", "category"],
        "creator": {"@type": "Organization", "name": "Sujeito Operator",
                    "url": "https://github.com/sujeito-operator"},
        "distribution": [{
            "@type": "DataDownload", "encodingFormat": "text/csv",
            "name": f"Seller table ({s['sellers']:,} sellers)",
            "contentUrl": B.RAW + "/data/gumroad-sellers.csv"}],
    }, indent=2)
    extra = f'<script type="application/ld+json">\n{ld}\n</script>\n'

    bottom90 = round(100 - s["top10_share"], 1)
    zero_pct = round(100 * s["sellers_zero_ratings"] / s["sellers"])

    return B.head(title, desc, canonical, extra) + f"""
<a class=home href="../">&larr; What actually sells on Gumroad</a>
<h1>Who actually sells on Gumroad</h1>
<div class=sub>{s['sellers']:,} sellers &middot; {s['products']:,} products &middot;
{s['ratings_total']:,} ratings &middot; 5 August 2026</div>

<div class=lede><strong>The top 1% of Gumroad sellers hold {s['top1_share']}% of all
measured demand — and the median seller in that 1% has {s['top1_med_products']} products.</strong>
{s['top1_solo']} of those {s['top1_count']} sellers have exactly one. Whatever is producing the
concentration at the top of this marketplace, it is not catalogue size.</div>

<div class=kv>
<div><b>{s['sellers']:,}</b><span>Distinct sellers</span></div>
<div><b>{s['top1_share']}%</b><span>Ratings held by the top 1%</span></div>
<div><b>{s['top10_share']}%</b><span>Ratings held by the top 10%</span></div>
<div><b>{s['solo_share_pct']}%</b><span>Sellers with exactly one product</span></div>
<div><b>{zero_pct}%</b><span>Sellers with no ratings at all</span></div>
<div><b>{s['spearman_products_ratings']}</b><span>Rank correlation, catalogue size to demand</span></div>
</div>

<h2>Four things the seller column says that a product table cannot</h2>
<ul>
<li><strong>Demand is more concentrated across sellers than most marketplace commentary
assumes.</strong> The top 1% ({s['top1_count']} sellers) hold {s['top1_share']}% of all
{s['ratings_total']:,} ratings measured; the top 10% hold {s['top10_share']}%; the
remaining {s['sellers'] - round(s['sellers'] * 0.1):,} sellers share {bottom90}% between
them.</li>
<li><strong>It is not a catalogue effect.</strong> The rank correlation between how many
products a seller has and how much demand they attract is
<strong>{s['spearman_products_ratings']}</strong> — real, but weak. The median seller
inside the top 1% has {s['top1_med_products']} products, and {s['top1_solo']} of the
{s['top1_count']} have exactly one. Listing more is not the mechanism.</li>
<li><strong>One-product sellers are the marketplace.</strong> {s['solo_sellers']:,} of
{s['sellers']:,} sellers — {s['solo_share_pct']}% — have a single product here, and as a
class they hold {s['solo_ratings_share']}% of all ratings. The median seller has
{s['med_products']} product; the mean is {s['mean_products']}, which is what a
long tail does to an average.</li>
<li><strong>{zero_pct}% of sellers have never been rated at all</strong> —
{s['sellers_zero_ratings']:,} of {s['sellers']:,}, across their entire measured catalogue.
Not a single listing with a single rating. That is the outcome you are competing
against, and it is the modal one.</li>
</ul>

<h2>How demand is distributed across sellers</h2>
<p>Sellers ranked by total ratings, split into ten equal groups of about
{round(s['sellers'] / 10):,}. Each row is that decile's share of all
{s['ratings_total']:,} ratings measured.</p>
<table><thead><tr><th>Seller decile</th><th class=n>Share of all ratings</th><th></th></tr>
</thead><tbody>{dec}</tbody></table>
<p>Cumulatively: top 1% {s['top1_share']}%, top 5% {s['top5_share']}%, top 10%
{s['top10_share']}%, top 25% {s['top25_share']}%, top half {s['top50_share']}%. The bottom
half of sellers hold {round(100 - s['top50_share'], 1)}% of measured demand between
{round(s['sellers'] / 2):,} of them.</p>

<h2>The {INDEX_ROWS} sellers with the most measured demand</h2>
<p>Ranked by total ratings across every listing found. Sellers with
{MIN_PRODUCTS} or more measured products have a page of their own; the rest are listed
here and are in the CSV in full. <strong>A product count is what this crawl found, not a
catalogue</strong> — see the method note below.</p>
<table><thead><tr><th class=n>#</th><th>Seller</th><th class=n>Products</th>
<th class=n>Ratings</th><th class=n>Share</th><th class=n>Median price</th>
<th>Most-used category</th></tr></thead><tbody>{body}</tbody></table>

<h2>Method, and what this cannot tell you</h2>
<p>Sellers are derived from {s['products']:,} distinct products keyed on product URL,
collected by walking Gumroad's own {ts['nodes_crawled']}-node category tree on 5 August
2026. Each node was taken up to three pages deep, capping it at {ts['cap']} listings, and
{ts['nodes_at_cap']} of the {ts['nodes']} non-empty nodes hit that cap. <strong>So every
product count here is a lower bound on that seller's catalogue</strong>, biased down for
exactly the sellers whose listings rank deepest. Concentration figures are less affected
than counts — a seller missing from the crawl is missing their ratings too — but they are
still measured on what was found, not on the whole marketplace.</p>
<p><strong>Ratings are a proxy for relative demand, not a sales figure.</strong> Only some
buyers rate, that share differs by category, and no revenue estimate anywhere on this site
is derived from them. {ts['nodes_empty']} crawled nodes returned no listings and are
excluded rather than reported as zeroes.</p>
<p>These are public commercial listings, published under public Gumroad storefront names
and linked back to the storefront they came from. Nothing here is inferred about any
person. If you run one of these storefronts and would rather not appear, open an issue on
<a href="{B.REPO}/issues">the repository</a> and it comes out of the next build.</p>

<h2>The data — free, no signup</h2>
<p>One row per seller for all {s['sellers']:,}:
<a href="{B.REPO}/blob/main/data/gumroad-sellers.csv"><code>data/gumroad-sellers.csv</code></a>
— storefront, product count, categories, rating total, demand rank, share of all ratings,
median and range of asking prices, free and subscription counts, and their most-rated
listing. Every figure on this page is emitted as
<a href="{B.REPO}/blob/main/data/sellers-summary.json"><code>sellers-summary.json</code></a>.
Derived by
<a href="{B.REPO}/blob/main/scripts/normalize_sellers.py"><code>normalize_sellers.py</code></a>
from <a href="{B.REPO}/blob/main/data/gumroad-taxonomy.csv"><code>gumroad-taxonomy.csv</code></a>,
so it can never disagree with the product-level release. Data <strong>CC BY 4.0</strong>,
code <strong>MIT</strong>. Use it for anything.</p>

{B.buy_block("What is <em>not</em> free is the analysis: which categories are openings "
             "versus crowded rooms, where price and demand come apart, and what the "
             "background rate of unsold listings means if you are choosing what to "
             "build next.")}

<nav class=sib>Also: <a href="../t/index.html">all {ts['nodes']} categories, ranked</a>
&middot; <a href="../">what actually sells on Gumroad</a></nav>
<nav class=sib>Guides: {" &middot; ".join(f'<a href="../g/{g}.html">{lab}</a>'
    for g, lab in __import__("build_guides").GUIDES)}</nav>
""" + B.FOOTER


def build(ts, trows, outdir):
    """Write docs/s/. Returns the flattened slugs that got a page, for the sitemap."""
    outdir.mkdir(parents=True, exist_ok=True)
    root = outdir.parent.parent
    s = json.loads((root / "data" / "sellers-summary.json").read_text())
    rows = list(csv.DictReader((root / "data" / "gumroad-sellers.csv").open()))
    for r in rows:
        for k in ("products", "observations", "categories", "ratings_total",
                  "rated_products", "ratings_rank", "free_products", "subs"):
            r[k] = int(r[k])
        for k in ("ratings_share_pct", "med_price_usd", "min_price_usd", "max_price_usd"):
            r[k] = float(r[k])

    # Distinct products per seller, from the listing table. First observation of a URL
    # wins, matching normalize_sellers.py exactly — the two must not diverge.
    seen, by_seller = set(), collections.defaultdict(list)
    for r in trows:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        by_seller[r["seller"]].append(r)

    paged = [r for r in rows if r["products"] >= MIN_PRODUCTS]
    has_page = {r["seller"] for r in paged}

    written = []
    for i, r in enumerate(paged):
        neighbours = [paged[j]["seller"] for j in (i - 2, i - 1, i + 1, i + 2)
                      if 0 <= j < len(paged) and j != i]
        page = seller_page(r, by_seller[r["seller"]], s, ts, neighbours)
        (outdir / f"{seller_slug(r['seller'])}.html").write_text(page)
        written.append(seller_slug(r["seller"]))
    (outdir / "index.html").write_text(index_page(rows, s, ts, has_page))
    return written
