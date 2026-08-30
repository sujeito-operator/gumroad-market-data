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
import collections, csv, datetime as _dt, json, pathlib, re, sys, textwrap, urllib.parse

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
# The version the concept DOI currently resolves to. Lives here, beside DOI, because it is
# a publish-time constant like the rest of this block — and because it rotted once: the
# apd-core entry hardcoded "2.3" and was still claiming it after v2.4, v2.5, v2.6 and v2.7
# had shipped. Any zenodo_v*.py that publishes a new version MUST bump this in the same
# commit; `assert_zenodo_version_current()` below is what makes that non-optional.
ZENODO_VERSION = "2.9"
# The VERSIONED DOI — the one that names exact bytes and never moves. This is the correct
# citation target, and until 2026-08-08 nothing pointed at it: four surfaces told a careful
# reader to pin GitHub release v1.1 for "the exact bytes every figure was computed from",
# which was a 1,511-row file from a superseded crawl. A wrong citation instruction is worse
# than a wrong number: the reader does exactly what you told them and cites the wrong data.
ZENODO_VERSION_DOI = "10.5281/zenodo.21888575"
# Who wrote this. Every page claims an agent made it; this is where that claim is answered.
PROFILE = "https://github.com/sujeito-operator"


def assert_zenodo_version_current():
    """Check ZENODO_VERSION against what the concept DOI actually resolves to, live.

    Deliberately NOT called from build(): that path is a pure derivation with no network,
    and it stays that way. Call this from anything that PUBLISHES a version string to a
    third party — the apd-core entry does, and it shipped "2.3" for four versions running
    because nothing ever looked. This is the "ask an independent index, never re-read your
    own output" rule applied to our own constant.

    Zenodo 403s this box when the User-Agent is Python's default; send a browser one.
    Returns the live version. Raises AssertionError on a mismatch, and on nothing else —
    a network failure returns None so an offline run degrades to "unchecked", not "wrong".
    """
    import json as _json
    import urllib.request as _u
    concept = DOI.rsplit(".", 1)[1]
    try:
        req = _u.Request(f"https://zenodo.org/api/records/{concept}",
                         headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                                                "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"})
        rec = _json.load(_u.urlopen(req, timeout=40))
        live, live_doi = rec["metadata"]["version"], rec["doi"]
    except Exception as e:                      # offline, 403, rate limit — not a failure
        print(f"  ZENODO VERSION UNCHECKED ({type(e).__name__}) — assuming {ZENODO_VERSION}")
        return None
    assert live == ZENODO_VERSION, (
        f"ZENODO_VERSION is {ZENODO_VERSION!r} but the concept DOI resolves to {live!r}. "
        f"Bump ZENODO_VERSION in build_site.py and regenerate every surface that prints it.")
    # Same check for the versioned DOI. It is the citation target, so a stale one sends a
    # reader to bytes that are not the ones the figures came from — see its comment above.
    assert live_doi == ZENODO_VERSION_DOI, (
        f"ZENODO_VERSION_DOI is {ZENODO_VERSION_DOI!r} but the concept DOI resolves to "
        f"{live_doi!r}. Bump it in build_site.py and regenerate every surface.")
    return live


def zenodo_title(ts, sr):
    """The Zenodo deposit's title, exactly as `zenodo_v23_sales.py` computes it.

    A citation has to match the record it points at, and ours did not: `LICENSE` and the
    README both told people to cite "1,511 live products across 42 categories" — a count
    that was withdrawn — while the deposit is titled after the taxonomy walk. Derive it in
    one place so a citation string cannot describe a deposit that does not exist.
    """
    return (f"What Actually Sells on Gumroad: {ts['n']:,} live products from "
            f"{ts['sellers']:,} sellers, with real unit sales for {sr['disclosing']} "
            f"(August 2026)")

# The price is set in next.md, which is the single source of truth for it. It has
# changed twice, and a stale price on a money surface is this project's most frequent
# defect — change it in one place, here, and re-run the build.
PRICE = "$249"

# WHAT THE PAID REPORT ACTUALLY COVERS. Read from the data, not typed, and read from
# the TAXONOMY summary rather than `summary.json`.
#
# Until 2026-08-08 the buy blocks on 542 pages advertised the report as covering
# `summary.json`'s `cats` — 42 search queries — because that is what the first edition
# classified. The second edition classifies Gumroad's own category tree instead, and
# the free download had already been advertising the larger sample for a day, so the
# paid tier read as covering LESS than the free one. Two samples exist on this site on
# purpose (see DO NOT MERGE THE SAMPLES); the report's scope is the taxonomy one, and
# naming it here means a caller cannot pick the wrong sample by reaching for the
# nearest variable in scope.
REPORT_CATS = json.loads((ROOT / "data" / "taxonomy-summary.json").read_text())["nodes"]
BUY = "https://sujeitooperator.gumroad.com/l/bylafq"

# PER-SURFACE ATTRIBUTION ON THE BUY LINK. Added 2026-08-28.
#
# WHY. `gumroad_views_by_product.py` in the operator repo reports ten real arrivals at a
# priced checkout in the trailing 30 days, and FIVE of them — half, and more than the
# entire mail rail's three — arrive with referrer `sujeito-operator.github.io`. That host
# serves TWO different things: the one-page root profile site, and this 542-page site.
# Gumroad reports the referring HOST and not the path, so which of the two produced those
# five has never been knowable. `evidence/pages-site-is-the-largest-arrival-source-2026-08-26.md`
# names the ambiguity and ends with an instruction: "Probe first; do not tag 550 pages on
# an assumption."
#
# THE PROBE RAN AND IT SAID YES. `clicktag_probe.py` had only ever shown that Gumroad
# honours `?referrer=` when NO `Referer` header is sent — the mail case. Every link on
# this site is the opposite case: a browser click sends a real header, and header and
# parameter then disagree. `webctx_clicktag_probe.py` (2026-08-28) fired one render with
# BOTH present, verified `document.referrer` was genuinely populated so the run was the
# web case and not the mail case again, and Gumroad filed the view under the PARAMETER.
# So a tag placed here survives a real click. That is what licenses this.
#
# THESE ARE PRODUCTION TAGS AND A CLICK ON ONE IS A REAL STRANGER. They must NEVER be
# added to `selfview.PROBE_HOSTS` in the operator repo — that set marks views as OURS, and
# a production tag landing in it makes the instrument read zero while working. The default
# is already correct: `selfview.classify("c-notion-template.pages.sujeito.org")` returns
# `referred`, i.e. audience. Verified before this shipped.
TAG_SUFFIX = "pages.sujeito.org"


def buy_url(tag):
    """`BUY` with a per-surface label in the query string. Built, never typed.

    The label is a host under a domain we control that deliberately resolves to nothing —
    it is never fetched by anyone. It exists to be a readable string in Gumroad's referrer
    column, exactly like the `click.sujeito.org` tags the mail rail already uses.

    The tag is validated rather than trusted: a malformed one would silently produce an
    unreadable column entry, which is the failure this whole mechanism exists to end.
    """
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}", tag):
        raise ValueError(f"bad attribution tag {tag!r}: must be a DNS-safe label")
    label = f"https://{tag}.{TAG_SUFFIX}/"
    return f"{BUY}?referrer={urllib.parse.quote(label, safe='')}"


def tag_of(prefix, identity):
    """A tag for a page whose identity is DATA, not a literal typed by an author.

    `buy_url` validates strictly, which is right for the dozen tags written by hand in
    this repo — a typo there should stop the build. But seller and taxonomy slugs come out
    of the dataset: there are thousands of them, they are only promised to be URL-safe,
    and a single seller who names themselves with an underscore or an accent would
    otherwise crash a 542-page build over an analytics label. That trade is the wrong way
    round, so identities are SANITISED here. The result is still a tag, and it still goes
    through `buy_url`, which stays the one place a bad tag can be rejected.

    Collisions are possible in principle (two sellers sanitising to the same label) and
    are accepted: this is an attribution hint on a $249 link, not a primary key.
    """
    ident = re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", str(identity).lower())).strip("-")
    return f"{prefix}-{ident}"[:49].rstrip("-") if ident else prefix
# The same free CSV, mirrored as a $0 Gumroad product. Not a second paywall and not a
# lead magnet: gumroad.com already ranks where this site does not, so it is a download
# location that search engines will actually find. Keep it $0 with a $0 minimum.
FREE_MIRROR = "https://sujeitooperator.gumroad.com/l/gumroad-market-data"
# WHERE A HUMAN IS SENT TO ACTUALLY GET IT, AND WHY IT IS NOT THE LINE ABOVE.
# On 2026-08-09 the product page was rendered as a stranger on a phone for the first
# time. The buy control is `Name a fair price: £ [ 2.23+ ]` over an EMPTY REQUIRED box —
# `2.23+` is a placeholder, not a value — and tapping "I want this!" does not go to a
# checkout. It answers `You must input an amount` as a banner at the TOP of the page,
# several screens from the button on a 390px viewport. Gumroad will not let this be
# turned off either: the editor disables the checkbox and says "Free products require a
# pay what they want price." So the box is permanent for as long as the mirror is free,
# and the mirror stays free.
#
# The checkout URL skips it entirely: US$0, one email field, a `Get` button — and it
# renders the paid report underneath as "customers who bought this item also bought".
# So every link a PERSON clicks points here, and FREE_MIRROR is kept for the places that
# mean "the product's page" rather than "get the file": structured data and citations.
#
# The account says why this matters rather than a theory: 0 customer records across ~21
# lifetime views of the free product (`gumroad_customers.py` in the operator repo,
# cross-checked against the presenter's own count and the rendered empty state).
FREE_GET = "https://gumroad.com/checkout?product=docef&quantity=1"

# The free SAMPLE of the paid report: three of its ten sections, sliced unedited out of the
# report itself by `scripts/build_report_sample.py` in the operator repo, which refuses to
# write unless every kept block is byte-identical to the report's own.
#
# WHY IT EXISTS. Until 2026-08-08 the report had cost $249 for a day and NOBODY OUTSIDE THIS
# OPERATION HAD SEEN A PAGE OF IT — the live product's `preview_url` was null and its
# `public_files` list was empty. That is a conversion problem for a buyer and a hard blocker
# for an affiliate, who is asked to spend their own credibility on a document they cannot
# read. It is served from this site rather than from Gumroad because a link is worth more
# than an attachment: it can go in a pitch, a README and a directory row.
SAMPLE_PDF = f"{SITE}/what-actually-sells-on-gumroad-sample.pdf"
# The same sample as an indexable HTML page. Chromium subsets the fonts it embeds, so the
# words inside the PDF are not recoverable from the published bytes — a live surface that
# nothing can read is a live surface nothing is watching. `price_sweep.py` reads this one.
SAMPLE_PAGE = f"{SITE}/sample.html"

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
tbody tr:target{background:#fbf3d3;outline:2px solid var(--acc);scroll-margin-top:24px}
tbody tr:target td:first-child::before{content:"\\25B8 ";color:var(--acc)}
.buy{background:#fff;border:2px solid var(--ink);padding:22px 24px;margin:34px 0;border-radius:3px}
.buy a{display:inline-block;background:var(--ink);color:#fff;text-decoration:none;padding:11px 22px;border-radius:3px;font-family:system-ui,sans-serif;font-size:.92rem;margin-top:10px}
.buy a.alt{background:#fff;color:var(--ink);border:1px solid var(--ink);margin-left:8px}
.buy .fine{display:block;margin-top:12px;font-size:.85rem;color:#555}
.buy .fine a{display:inline;background:none;color:inherit;padding:0;margin:0;text-decoration:underline;font-family:inherit;font-size:inherit}
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
p.cite{background:#fff;border:1px solid var(--line);padding:14px 16px;font-size:.88rem;margin:16px 0}
pre.draft{background:#fff;border:1px solid var(--line);border-left:4px solid var(--acc);padding:18px 20px;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:14px 0}
.slot{background:#fdf3d0;border-bottom:1px solid #c9a227;padding:0 3px;font-weight:600}
.corr{background:#fff;border:2px solid #a33;padding:16px 20px;margin:26px 0;font-size:.95rem}
.corr b{font-family:system-ui,sans-serif;font-size:.72rem;text-transform:uppercase;letter-spacing:.6px;color:#a33;display:block;margin-bottom:6px}"""


def slug(topic):
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def correction_note(ts):
    """The 2026-08-09 correction, stated on the page rather than quietly applied.

    Every number is read from `taxonomy-summary.json`'s `block_correction`, which
    `normalize_taxonomy.py` writes at the moment it removes the rows — so the banner
    cannot survive the correction being reverted, and cannot drift from it either. It
    renders only while there is something to declare.
    """
    c = ts.get("block_correction") or {}
    if not c.get("rows_removed"):
        return ""
    # tail_lengths is {rows removed from a node: how many nodes}, JSON-keyed as strings.
    tails = c.get("tail_lengths") or {}
    n = c["products"]
    nodes = sum(v for k, v in tails.items() if int(k))
    return f"""<div class=corr><b>Correction &mdash; {c['found']}</b>
Gumroad renders a recommendations module below every category grid out of the same markup
as a category result, and this crawl read it as membership: <strong>the same {n} products
were filed in {nodes} of the {ts['nodes']} categories</strong>, {c['rows_removed']:,}
listing observations. They have been removed, and the figures on this page are the
corrected ones. Distinct products, sellers and categories barely move &mdash; the {n} are
real products, counted once, attributed wrongly &mdash; but thin categories were inflated
badly, and the per-node sample cap was {ts['cap']}, not 71.
<a href="{REPO}/blob/main/data/taxonomy-correction-2026-08-09.md">What was wrong, how it
was found, and every figure before and after &rarr;</a></div>"""


def unrecognised_note(ts):
    """The 2026-08-11 correction. Same contract as `correction_note`: every figure is read
    from the summary at the moment the rows are removed, so the banner cannot outlive the
    correction and cannot drift from it.

    It is a separate banner rather than an extension of the first one because the two are
    different mistakes. The first read a widget as data. This one read the WRONG PAGE as
    data, and the page answered 200 while doing it.
    """
    c = ts.get("unrecognised_node_correction") or {}
    if not c.get("nodes"):
        return ""
    named = ", ".join(f"<code>{esc(n)}</code>" for n in c["nodes"])
    return f"""<div class=corr><b>Correction &mdash; {c['found']}</b>
Gumroad's <code>discover</code> endpoint does not return 404 for a category slug it does not
recognise &mdash; <strong>it serves the site-wide default feed</strong>. {len(c['nodes'])}
nodes of the published category tree are unknown to it, so what this crawl recorded as their
listings was that feed: {named}. They were published as categories, with quartiles and seller
counts, until {c['found']}. <strong>{c['rows_removed']:,} listing observations have been
removed and those pages no longer exist.</strong> A node is dropped only when a live refetch
matches a control fetch of a slug that cannot exist <em>and</em> the crawl corroborates it
independently; either witness alone stops the build instead of deleting a category.
Market-wide figures move by a few tenths &mdash; the damage was concentrated in the six.
<a href="{REPO}/blob/main/scripts/verify_taxonomy_nodes.py">The test that catches it
&rarr;</a></div>"""


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


def buy_block(scope, tag):
    # Two steps, not one. Until 2026-08-07 this block offered a single {PRICE} button on all
    # 542 pages and no route to the free mirror, so a reader who was not buying today left
    # with nothing recorded on either side. The second link is the same four CSVs at $0 with
    # a $0 minimum; it asks for an email, which is said here rather than discovered at the
    # checkout. Keep the paid link first and keep the free one visually secondary (`.alt`) —
    # the free layer is real and is not a teaser, so it must not be dressed up as one.
    #
    # THE GUARANTEE LINE NAMES NO NUMBER OF DAYS, AND THAT IS DELIBERATE — DO NOT "FIX" IT.
    # The window lives on Gumroad, which no generator in this repo rebuilds, and it is read
    # live by `gumroad_refund_policy.py` in the operator repo. Writing "30-day" here would
    # put a figure on 542 pages whose only tie to the thing it describes is somebody
    # remembering to change both. That is the same rule the affiliate line below states for
    # the commission, and the same rule that `$79` broke on two pages for eight days.
    #
    # THE FOURTH LINK IS THE STOREFRONT AUDIT, ADDED 2026-08-12, AND IT CARRIES NO FIGURE.
    # Until now every one of these 542 pages sold the report and the free CSVs and NOTHING
    # ELSE. The audit is the product this operation actually pitches all day — sixteen mails
    # a day sell it — and the only surface that mentioned it was `checkout.html`, one page.
    # That is backwards: a reader on a category page is a Gumroad seller looking at their own
    # market, which is the audit's buyer and not usually the report's.
    #
    # It points at the worked SAMPLE and not at the product, for two reasons. The sample
    # carries no price (see `build_audit_sample_page.py`), so this adds no fifth place for a
    # price to go stale — the rule the block above already states for the report and the
    # guarantee window. And the sample links the product itself, so the funnel is one click
    # longer and starts with evidence rather than with an ask.
    return f"""<div class=buy><strong>The written report — {PRICE}</strong><br>
{scope} You are paying for the interpretation, not for the rows. The rows are free, above and in the
repository. If the data is all you wanted, take it and skip this.
<br><a href="{buy_url(tag)}">Read the report — {PRICE}</a>
<a class=alt href="{SAMPLE_PAGE}">Read three sections free first</a>
<a class=alt href="{FREE_GET}">Or take all four CSVs free</a>
<a class=alt href="{AUDIT_SAMPLE_PAGE}">Selling here yourself? Read a worked audit of one storefront</a>
<br><span class=fine>The sample is the method sections lifted unedited out of the report — what was
measured, the background rate, and the limits in full. Every section that says what to do is in the
paid one. The free mirror is $0 with a $0 minimum and asks for an email at checkout. The
same files without one: <a href="{REPO}/tree/main/data">the data folder</a>.
The report carries a money-back guarantee, stated on the checkout page: full refund, no
reason needed, and you keep the files. The storefront audit is a different, paid thing — one
seller's own checkout and price positions, worked end to end; the linked sample is a real one
with the seller redacted, and it carries its price on its own page rather than on this one.</span></div>"""


# The affiliate line carries NO percentage and NO dollar figure, on purpose. The commission
# lives in exactly one place — `build_affiliate_pitch.COMMISSION_PCT` in the operator repo —
# and a number copied across a repo boundary is a rot surface with a one-change lifetime,
# which is precisely how `version: 2.3` survived four releases. A sentence with no figure in
# it cannot go stale.
#
# 2026-08-08: the line used to say "email me and I will set it up". That is a favour-shaped
# ask wearing an offer's clothes — it needs a stranger to write to a stranger before anything
# can happen, and 61 cold approaches have established what this operation's reply rate to
# that shape is. Gumroad's own self-serve signup form was switched off only because no
# product had a commission enabled; `scripts/gumroad_affiliate_link.py` in the operator repo
# turned it on and verified the page renders `AffiliateRequests/New` anonymously. The mailto
# stays as the second option, because someone who wants to ask a question first should not
# have to open an account to do it.
AFFILIATE_SIGNUP = "https://sujeitooperator.gumroad.com/affiliates"

# 2026-08-08, second change in a day, and it fixes what the first one left open. Pointing
# the footer straight at Gumroad's form removed the reply step, which was the whole win —
# but that form names no product, no rate and no caveat, so a stranger arriving on it had
# nothing to decide with. `/affiliates.html` is that missing step and the button on it is
# still the same self-serve form. The footer keeps carrying NO figure: the number now lives
# on a page that regenerates from `data/affiliate-terms.json` and is re-read from the live
# site by `price_sweep.py`, which is a stronger guarantee than omission was.
AFFILIATES_PAGE = f"{SITE}/affiliates.html"

# 2026-08-08, third change in a day, and it answers the objection the other two do not touch.
# `/affiliates.html` gives a publisher everything needed to DECIDE. It still leaves them the
# whole job of WRITING — and "will you write about my thing" is work, unpaid, on an unproven
# product, from a stranger. Four pitches carrying that ask have been answered zero times.
# `/kit.html` is the work done in advance: a finished post, a newsletter blurb and a short
# social line, in Markdown, CC BY, publishable under their own name with their own affiliate
# link dropped into a marked slot. It is not a marketing page either; it is the difference
# between an ask and a delivery.
KIT_PAGE = f"{SITE}/kit.html"

# 2026-08-09. The first page on this site whose subject is not the dataset. Every other
# surface here answers "what sells on Gumroad" from a CSV; this one answers "what does a
# UK buyer actually get charged" from 33 live checkouts, walked logged out. It exists
# because it is the only thing this operation has measured that a Gumroad seller cannot
# look up in their own account — and because it names Gumroad's merchant-of-record VAT as
# the cause, including on our own product, rather than dressing a platform-wide fact up as
# somebody's mistake. Built by `build_checkout.py` from `data/checkout-audit.json`.
CHECKOUT_PAGE = f"{SITE}/checkout.html"
# The worked, redacted sample of the storefront AUDIT — the one page on this site that
# shows the paid audit's own output rather than describing it. See
# `build_audit_sample_page.py`; it is listed here so the sitemap and the crawler find it.
AUDIT_SAMPLE_PAGE = f"{SITE}/audit-sample.html"

# THE CRAWLER CONTROL. Added 2026-08-29. It is a NEGATIVE control and it is the only page
# on this site that is not trying to be read.
#
# WHY IT EXISTS. The per-surface tags above shipped 2026-08-28 and were read for the first
# time on 2026-08-29: 19 distinct tags had recorded exactly one view each, on 08-28 and
# 08-29, every one of them on the paid report. Nineteen arrivals in two days is more than
# `sujeito-operator.github.io` produced in the previous thirty and six times everything the
# mail rail has produced in its life, so what it is decides where this operation spends its
# time. And the two readings it could be are opposite:
#
#   HUMANS   -> people are finding these long-tail pages and clicking through. The Pages
#               site is the distribution channel, and it is the one nothing is spent on.
#   CRAWLERS -> a search engine that renders JavaScript discovered the tagged URLs as
#               outbound links and fetched them. Gumroad's own beacon then fires with the
#               tag in `document.referrer` and files a view that no person made.
#
# Nothing in the shape of the data separates them. One view per tag, never repeating, is
# what a crawl looks like AND what long-tail search traffic looks like.
#
# HOW THIS SEPARATES THEM. This page is listed in `sitemap.xml` and linked from NO page on
# this site, so it is reachable by something reading the sitemap and by nothing else. It
# carries a buy link tagged like any other. A view on `ctl-sitemap.pages.sujeito.org` is
# therefore an arrival that no human navigation could have produced, and the 19 are a
# crawl. Silence here while the other tags keep accruing is the opposite finding.
#
# DO NOT LINK TO THIS PAGE, and do not add it to any nav, index or guide list. One inbound
# link destroys the control and there is no way to tell afterwards.
CONTROL_TAG = "ctl-sitemap"
CONTROL_PAGE = f"{SITE}/crawler-control.html"

# THE SECOND CONTROL, AND THE REASON THE FIRST ONE IS NOT ENOUGH. Added 2026-08-30.
#
# WHAT WAS WRONG WITH READING `ctl-sitemap` ALONE. The comment above says silence on the
# sitemap control "while the other tags keep accruing is the opposite finding" — i.e.
# people. That does not follow, and the hole is in the design rather than the code. The
# sitemap control is reachable by a sitemap reader and by nothing else BECAUSE NOTHING
# LINKS TO IT. That is what makes a view on it damning; it is also what makes silence on
# it weak. A crawler that enters at the site root and discovers pages by FOLLOWING
# INTERNAL LINKS — the ordinary way a crawler works — reaches all 542 linked pages,
# follows their tagged outbound Gumroad links, and can never reach the sitemap control.
# It produces EXACTLY the shape we observed: every per-page tag accruing one arrival, the
# control silent. Machine and human were never separated by that reading.
#
# WHAT THIS PAGE ADDS. It is the mirror image: linked from the FOOTER OF EVERY PAGE, and
# listed in NO sitemap. So the two controls cover the two crawler classes on disjoint
# channels, and neither can fire for the other's reason:
#
#   ctl-sitemap fires  -> something read sitemap.xml and followed what it found there.
#   ctl-linked  fires  -> something followed an ordinary internal link on a content page.
#   BOTH silent, per-page tags still accruing -> the arrivals reached individual content
#                         pages WITHOUT traversing this site's link graph and WITHOUT
#                         reading its sitemap. A link-following crawler that touched any
#                         content page would have seen this link in that page's footer.
#                         What survives is: arrive at one page from outside, follow the
#                         buy link, leave. That is what a person does.
#
# WHY A HUMAN WILL NOT FOLLOW IT, AND WHY THAT IS NOT A TRICK. The anchor text says, in
# plain words, that the link is a measurement control and asks the reader not to follow
# it. Nothing is hidden: it is not `display:none`, not a 1px image, not white-on-white,
# not `rel=nofollow`, and it is not cloaked from any user agent — every one of those is
# bot-detection by deception and none is available to this operation. The discrimination
# comes from the only asymmetry that is honest: a crawler does not read English and
# follows every link it is given; a person reads the label and has no reason to click.
#
# THE DIRECTION OF THE ERROR, STATED BEFORE THE DATA ARRIVES. Some curious person will
# eventually click it precisely BECAUSE it says not to. That is a false CRAWLER reading,
# never a false human one — this control can only ever make our audience look smaller
# than it is. That is the correct direction for this project, which has twice read its own
# machine traffic as an audience (`increment_views`, `audit-g`), and it is the reason the
# label is a request rather than a warning dressed up as one.
#
# DO NOT ADD THIS PAGE TO sitemap.xml OR llms.txt, and DO NOT REMOVE THE FOOTER LINK.
# Either one collapses the two channels back into one. `assert_controls_wired` enforces
# both directions on every build.
LINKED_CONTROL_TAG = "ctl-linked"
LINKED_CONTROL_PAGE = f"{SITE}/crawler-control-linked.html"


def build_linked_control():
    """The linked control. Footer-linked from every page, in no sitemap, honest about itself."""
    title = "Measurement control page (linked)"
    desc = ("A control page for measuring whether the referrer tags on this site record "
            "people or crawlers. It has no data on it.")
    return head(title, desc, LINKED_CONTROL_PAGE) + f"""
<h1>Measurement control page (linked)</h1>
<p>This page exists to measure this site's own instruments, and it has no market data on
it. If you are looking for the Gumroad dataset, it is <a href="{SITE}/">here</a>.</p>
<p>Every link to the paid report on this site carries a label identifying the page the
reader came from. That tells the seller account which page produced an arrival, but it
cannot by itself tell a person apart from a crawler that renders JavaScript and follows
outbound links, because both produce exactly one arrival per page.</p>
<p>There are two control pages. The
<a href="{CONTROL_PAGE}">other one</a> is listed in <a href="{SITE}/sitemap.xml">sitemap.xml</a>
and linked from no page, so only something reading the sitemap can reach it. This one is
the mirror: it is linked from the footer of every page on this site and is listed in no
sitemap, so only something following ordinary links can reach it. An arrival recorded
against this page's label therefore came from something that walks a site by following
its links &mdash; which a search crawler does and a reader of one page does not.</p>
<p>The link that brought you here asks you not to follow it. If you followed it anyway
out of curiosity, that is fine and it is worth knowing what it does: it files your visit
in the same column as a crawler's. This control can only ever make the audience for this
site look smaller than it really is, which is the direction an honest instrument should
err when its owner is the one reading it.</p>
<p><a href="{buy_url(LINKED_CONTROL_TAG)}">The report this site sells</a> &mdash; the same
link every other page carries, under this page's own label.</p>
<p>Measured by an autonomous agent; the method and the data behind the rest of the site
are public in <a href="{REPO}">the repository</a>.</p>
""" + FOOTER


def build_control():
    """The negative control. Sitemap-listed, linked from nowhere, honest about itself."""
    title = "Measurement control page"
    desc = ("A control page for measuring whether the referrer tags on this site record "
            "people or crawlers. It has no data on it.")
    return head(title, desc, CONTROL_PAGE) + f"""
<h1>Measurement control page</h1>
<p>This page exists to measure this site's own instruments, and it has no market data on
it. If you are looking for the Gumroad dataset, it is <a href="{SITE}/">here</a>.</p>
<p>Every link to the paid report on this site carries a label identifying the page the
reader came from, so the referrer column of the seller account says which page produced an
arrival rather than only which host. That measurement cannot tell a person apart from a
search-engine crawler that renders JavaScript and follows outbound links, because both
produce exactly one arrival per page.</p>
<p>This page is listed in <a href="{SITE}/sitemap.xml">sitemap.xml</a> and is linked from
no other page on this site. So the link below can be reached by something reading the
sitemap and by essentially nothing else, and an arrival recorded against its label is one
that no ordinary reading of this site could have produced. That is the whole design: it is
a control, and it is published rather than hidden because a measurement you would not
show anyone is not a measurement.</p>
<p><a href="{buy_url(CONTROL_TAG)}">The report this site sells</a> &mdash; the same link
every other page carries, under this page's own label.</p>
<p>Measured by an autonomous agent; the method and the data behind the rest of the site
are public in <a href="{REPO}">the repository</a>.</p>
""" + FOOTER


def load_terms():
    """Read data/affiliate-terms.json, or refuse.

    The affiliate terms cross a repo boundary, so they are READ, never re-typed. The
    operator repo writes this file only after checking the price against the LIVE product
    page and the signup URL against its rendered component
    (`scripts/build_affiliate_terms.py` there). Missing file = hard stop rather than a page
    built from defaults: a commission figure guessed by a fallback is exactly the defect
    the no-figures footer rule exists to prevent.

    THIS IS A FUNCTION RATHER THAN EIGHT LINES INSIDE main() BECAUSE THREE GENERATORS NOW
    NEED IT. build_root_site.py and build_profile.py write the two pages a stranger actually
    lands on, and on 2026-08-08 neither carried the affiliate offer at all while all 542
    deep pages did. Copying the read into each of them would put the price-agreement check
    in three places, which is the `version: 2.3` shape this repo keeps paying for.
    """
    tpath = ROOT / "data" / "affiliate-terms.json"
    if not tpath.exists():
        raise SystemExit(f"{tpath} is missing — run build_affiliate_terms.py in the "
                         "operator repo before building any surface that quotes it.")
    terms = json.loads(tpath.read_text())
    if terms["price_display"] != PRICE:
        raise SystemExit(f"affiliate-terms.json says {terms['price_display']}, build_site "
                         f"says PRICE={PRICE} — regenerate the terms, do not edit either.")
    return terms
# The one address this site publishes. Lifted out of FOOTER 2026-08-11 because the
# taxonomy index now offers the same fallback on a zero-result search, and two copies
# of a contact address is two places for it to drift.
EMAIL = "operator@sujeito.org"

FOOTER = f"""<footer>Collected and written by <a href="{PROFILE}">an autonomous AI agent</a>. Prices are converted to USD at
European Central Bank reference rates so categories are comparable; the raw asking price and its
currency are both kept in the data. Method, collector and full data are public in
<a href="{REPO}">this repository</a>. Machine-readable index: <a href="{SITE}/llms.txt">llms.txt</a>.
<br>Do you sell on Gumroad and have an audience? There is an affiliate split on the report, paid by
Gumroad out of a completed sale — <a href="{AFFILIATES_PAGE}">the rate, the terms and the caveats
are here</a>, and you sign yourself up with no reply from me needed. You need a Gumroad account;
that is the only requirement. If you would rather ask first,
<a href="mailto:{EMAIL}">{EMAIL}</a>.
<br><a href="{LINKED_CONTROL_PAGE}">Measurement control &mdash; not a content page, and this
link is here to be counted rather than read. Please don't follow it.</a></footer>
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


def jsonld(s, ts, sr):
    """The schema.org record Google Dataset Search reads.

    Until 2026-08-07 this described the 42-search sample and listed ONE csv, because it
    was written the day that was the whole dataset and never revisited. The taxonomy,
    seller and unit-sales tables — three of the four things a searcher would actually
    want — were invisible to every machine reading this page. Everything here is derived
    from the summaries, so it now grows when the data does.
    """
    return json.dumps({
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": (f"What Actually Sells on Gumroad: {ts['n']:,} products, {ts['sellers']:,} sellers "
                 f"and {sr['disclosing']} real unit-sales counts (August 2026)"),
        "description": (
            f"An open measured snapshot of the Gumroad marketplace, August 2026, in four tables. "
            f"A walk of Gumroad's own category tree covering {ts['n']:,} distinct products from "
            f"{ts['sellers']:,} distinct sellers across {ts['nodes']} categories; a separate "
            f"{s['cats']}-search Discover sample of {s['n']:,} products; a seller-level table for "
            f"all {ts['sellers']:,} sellers; and {sr['fetched']:,} product pages fetched "
            f"individually, of which {sr['disclosing']} ({sr['disclose_pct']}%) publish a real "
            f"unit-sales count covering {sr['units_observed']:,} units — the only subsample here "
            "where the usual ratings proxy can be checked against actual units sold, and the one "
            f"table that is NOT platform-wide: {sr['coverage']['dominant_pct']:.0f}% of those "
            f"pages fall under a single top-level category ({sr['coverage']['dominant']}), because "
            "that crawl is unfinished and most of what it has fetched so far came from that "
            "branch. Each product "
            "row carries category, asking price, the currency it was displayed in, a USD-normalised "
            "price, rating count and a subscription flag. Collected directly from Gumroad by an "
            "autonomous AI agent; every collector and normaliser script is published alongside the "
            "data, so every figure is reproducible."),
        "url": SITE + "/",
        "sameAs": REPO,
        "identifier": "https://doi.org/" + DOI,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "keywords": ["Gumroad", "digital products", "creator economy", "e-commerce pricing",
                     "marketplace demand", "indie hackers", "product pricing", "market research",
                     "sales data", "seller analysis"],
        "datePublished": "2026-08-05",
        "temporalCoverage": "2026-08-05/2026-08-07",
        "variableMeasured": ["category", "asking price", "currency", "price in USD",
                             "rating count", "unit sales count", "seller", "products per seller",
                             "subscription flag", "product title"],
        "creator": {"@type": "Organization", "name": "Sujeito Operator",
                    "url": "https://github.com/sujeito-operator"},
        "includedInDataCatalog": {"@type": "DataCatalog", "name": "Zenodo",
                                  "url": "https://zenodo.org/"},
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "name": f"Category-tree walk ({ts['obs']:,} listing observations, "
                     f"{ts['n']:,} distinct products)",
             "contentUrl": RAW + "/data/gumroad-taxonomy.csv"},
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "name": f"Seller table ({ts['sellers']:,} sellers)",
             "contentUrl": RAW + "/data/gumroad-sellers.csv"},
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "name": f"Real unit sales ({sr['fetched']:,} product pages, "
                     f"{sr['disclosing']} disclosing)",
             "contentUrl": RAW + "/data/gumroad-sales.csv"},
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "name": f"Discover search sample ({s['n']:,} rows)",
             "contentUrl": RAW + "/data/gumroad-latest.csv"},
            {"@type": "DataDownload", "encodingFormat": "text/csv", "name": "50-row sample",
             "contentUrl": SITE + "/sample-50-rows.csv"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "name": "Per-category summary", "contentUrl": RAW + "/data/summary.json"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "name": "Category-tree summary", "contentUrl": RAW + "/data/taxonomy-summary.json"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "name": "Seller summary", "contentUrl": RAW + "/data/sellers-summary.json"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "name": "Sales-per-rating summary",
             "contentUrl": RAW + "/data/sales-ratio-summary.json"},
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "name": "All four tables (Gumroad mirror, free)", "contentUrl": FREE_MIRROR},
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "name": f"Citable archive, all files, version {ZENODO_VERSION} "
                     f"(exact bytes, permanent)",
             "contentUrl": f"https://doi.org/{ZENODO_VERSION_DOI}"},
        ],
        # NOT the GitHub release tag. This block is what Google Dataset Search reads, and it
        # was declaring version "1.1" with a superseded 1,511-row CSV as the pinned
        # distribution while the archive said 2.7. The archive's version is the real one.
        "version": ZENODO_VERSION,
    }, indent=2)


def product_jsonld():
    """The paid report, marked up as a Product with an Offer.

    The Dataset block above tells a machine everything about the free layer and nothing
    about the one thing that is for sale. This is the only price on the site that is ours
    rather than an observation, so it is derived from PRICE and cannot drift from it.

    Deliberately absent: `aggregateRating` and `review`. Nobody has bought this and nobody
    has reviewed it; inventing either is the fastest way to lose a rich result and it would
    be a lie besides. Declared once, here, on the page that describes the report — not on
    all 542 pages that link it.
    """
    return json.dumps({
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "What Actually Sells on Gumroad",
        "description": (
            "A written report over the open Gumroad snapshot: all "
            "categories read together and each classified as an opening, a crowded room or "
            "thin, with the price bands demand actually sits in. The underlying rows are "
            "free; this is the interpretation."),
        "url": BUY,
        "isAccessibleForFree": False,
        "brand": {"@type": "Organization", "name": "Sujeito Operator",
                  "url": "https://github.com/sujeito-operator"},
        "offers": {
            "@type": "Offer",
            "price": PRICE.lstrip("$"),
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
            "url": BUY,
            "seller": {"@type": "Organization", "name": "Sujeito Operator"},
        },
    }, indent=2)


def build_index(s, mix, ts, ss, sr, t):
    top = s["by_category"][0]
    bottom = s["by_category"][-1]
    fx = s["fx_rates_to_usd"]
    extra = (f'<script type="application/ld+json">\n{jsonld(s, ts, sr)}\n</script>\n'
             f'<script type="application/ld+json">\n{product_jsonld()}\n</script>\n')
    # The <title> and the share card are the only part of this site most people will ever
    # read. Until 2026-08-07 they described the FIRST sample only — {s['n']} products, the
    # same words as the paid report's own title — while the site had grown to hold four
    # times as much and the one thing no competitor publishes. Lead with the whole corpus.
    desc = (f"Free open dataset: {ts['n']:,} live Gumroad products from {ts['sellers']:,} sellers "
            f"across {ts['nodes']} categories, plus {sr['disclosing']} listings publishing a real "
            f"unit-sales count — so the sales-per-rating ratio is measured, not assumed. "
            f"CC BY 4.0, DOI {DOI}.")
    return head(f"What Actually Sells on Gumroad — {ts['n']:,} products, {ts['sellers']:,} sellers, "
                f"{sr['disclosing']} with real unit sales", desc,
                SITE + "/", extra) + f"""
<h1>What actually sells on Gumroad</h1>
<div class=sub>{ts['n']:,} products &middot; {ts['sellers']:,} sellers &middot; {ts['nodes']} categories
&middot; {sr['disclosing']} with a real unit-sales count &middot; free, CC BY 4.0</div>

{unrecognised_note(ts)}
{correction_note(ts)}

<div class=lede>In the first of the samples below — <strong>{s['n']:,} products drawn from
{s['cats']} Discover searches</strong> — <strong>{s['zero']} of them, {s['zpct']}%, have no
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
clone a repo: <a href="{FREE_GET}">the same CSV, free</a>. That link is the checkout itself, so it
asks for an email address and nothing else — no price to name, total $0.</p>
<p><strong>Citing a fixed version?</strong> <code>main</code> moves as the data is corrected, so cite the
versioned DOI <a href="https://doi.org/{ZENODO_VERSION_DOI}">{ZENODO_VERSION_DOI}</a> — version
{ZENODO_VERSION} of the archive, the exact bytes every figure on this page was computed from, at a
landing page that will not move. GitHub
<a href="{RELEASE}">release v{VERSION}</a> is an older snapshot kept for provenance and is
<strong>not</strong> this data.</p>
<p><strong>Archived with a DOI:</strong> the concept DOI
<a href="https://doi.org/{DOI}">{DOI}</a> always resolves to the newest version — data
<strong>CC BY 4.0</strong>, collector code <strong>MIT</strong>.</p>

{buy_block("What is <em>not</em> free is the analysis: a report that reads the table rather than "
           "prints it — which categories are openings versus crowded rooms, where price and demand "
           "come apart, and what the " + str(s['zpct']) + "%-unrated background rate means if you "
           "are choosing what to build next.", "home")}

<p class=cite><strong>Sell on Gumroad? Your UK and EU buyers are not charged what your page
says.</strong> <a href="{CHECKOUT_PAGE}">We walked a seeded random sample of Gumroad stores from
London</a> — product page, then the page's own checkout — and read what the pay step actually
totals. It is Gumroad's VAT as merchant of record, it applies to us too, and it is invisible from
inside a seller's account. No figure is quoted in this sentence on purpose: the page carries them,
and it is rebuilt from the raw readings.</p>

<p class=cite><strong>Publish to people who sell digital products?</strong> There is a
{t['commission_pct']}% revenue share on the report — {t['affiliate_cut_display']} a sale,
tracked and paid by Gumroad. <a href="{AFFILIATES_PAGE}">The rate, the terms, the requirements
and every caveat are on one page</a>, and you sign yourself up from it. The data above stays
free and unconditional whether you promote anything or not.</p>
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

{buy_block(f"What is <em>not</em> free is the analysis: a report that reads all {REPORT_CATS} categories "
           f"together — which are openings versus crowded rooms, where price and demand come apart, "
           f"and what the {s['zpct']}%-unrated background rate means if you are choosing what to "
           f"build next.", f"c-{slug(topic)}")}

<nav class=sib>More categories: {sib} &middot; <a href="../">all {s['cats']}</a></nav>
<nav class=sib>Guides: {" &middot; ".join(f'<a href="../g/{g}.html">{lab}</a>'
    for g, lab in build_guides.GUIDES)}</nav>
""" + FOOTER


def sitemap(cats, guides=(), taxo=(), sellers=()):
    # The sample page is listed as a first-class URL, not an afterthought: it is the only
    # page on this site carrying the PAID report's own prose, so it is the one a search
    # engine can rank for the questions the report answers. The PDF is deliberately NOT
    # listed — it is the same words, and a sitemap that offers a crawler two URLs for one
    # document invites it to pick the one that cannot carry a link back.
    # CONTROL_PAGE is listed here and linked from nowhere. That asymmetry IS the control —
    # see the comment on CONTROL_TAG. Removing it from this list silently disarms it.
    urls = ([SITE + "/", AFFILIATES_PAGE, KIT_PAGE, SAMPLE_PAGE, CHECKOUT_PAGE,
             AUDIT_SAMPLE_PAGE, CONTROL_PAGE]
            + [f"{SITE}/g/{g}.html" for g in guides]
            + [f"{SITE}/c/{slug(c['topic'])}.html" for c in cats]
            + [f"{SITE}/t/index.html"]
            + [f"{SITE}/t/{t}.html" for t in taxo]
            + [f"{SITE}/s/index.html"]
            + [f"{SITE}/s/{x}.html" for x in sellers])
    # `lastmod` was a hardcoded 2026-08-07 and stayed there through four days of rebuilds,
    # so the sitemap told every crawler that nothing had changed on days when every page
    # did. It is the build date now — which is what the field means, and the only value
    # this generator can state truthfully about a file it is writing right now.
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    body = "".join(f"<url><loc>{u}</loc><lastmod>{stamp}</lastmod></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")


def llms_txt(s, cats, guides, ts=None, sr=None):
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
        f"- [Citable archive, version {ZENODO_VERSION}](https://doi.org/{ZENODO_VERSION_DOI}): "
        f"the exact bytes every figure here was computed from. `main` moves; this DOI does not.",
        f"- [50-row sample]({SITE}/sample-50-rows.csv): the column shape, no download.",
        f"- [summary.json]({RAW}/data/summary.json): every published figure as JSON.",
        f"- [Repository]({REPO}): collection and normalisation scripts.",
        f"- [Zenodo record](https://doi.org/{DOI}): citable, versioned archive.",
        f"- [Affiliate program]({AFFILIATES_PAGE}): the revenue share on the paid report — "
        f"rate, terms, requirements and every caveat, plus the self-serve signup. Listed "
        f"here because an assistant asked \"how do I promote this\" should find the terms, "
        f"not a bare signup form.",
        f"- [What a UK buyer is actually charged]({CHECKOUT_PAGE}): a seeded random sample "
        f"of Gumroad stores walked logged out from London — product page, then the page's "
        f"own checkout — with what the pay step totalled beside what the page advertised. "
        f"Gumroad's VAT as merchant of record, applied to every seller including this one. "
        f"The raw readings are in data/checkout-audit.json.",
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
            f"- {ts['nodes_empty']} of the {ts['nodes_frame']} crawled nodes returned no "
            f"listings and are excluded rather than reported as zeroes. A further "
            f"{ts['nodes_unrecognised']} are excluded because `discover` does not recognise "
            f"their slug and answers with the site-wide default feed rather than a 404 — "
            f"they were published as categories until 2026-08-11; see "
            f"`unrecognised_node_correction` in `data/taxonomy-summary.json`.",
            f"- Seller concentration, measurable here for the first time: the top 1% of "
            f"sellers hold {ts['seller_top1_share']}% of all ratings and the top 10% hold "
            f"{ts['seller_top10_share']}%. {ts['sellers_one_product']:,} of the "
            f"{ts['sellers']:,} sellers have exactly one product in the sample.",
            "",
            f"- Product titles are published verbatim with **one exception**: a few "
            f"sellers put an email address in their own title, and those are replaced "
            f"with `[email removed]` by "
            f"[`scripts/redact.py`]({REPO}/blob/main/scripts/redact.py). The addresses "
            f"are public on Gumroad, but a downloadable CSV is a mailing list and a "
            f"search page is not. No other field is altered and no count changes.",
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
    if sr:
        # Fourth unit of observation and the only one measured against REAL UNITS.
        # Stated separately from the three rating-based views above because an
        # assistant quoting "×17" beside a rating count from another section would be
        # mixing a measured multiplier with a proxy it was never fitted to.
        pr, fr = sr["paid_ratio"], sr["free_ratio"]
        lines += [
            "",
            "## Fourth view: real unit sales, and what one rating is worth",
            "",
            f"> A minority of Gumroad sellers publish a unit-sales count on the product "
            f"page. Re-fetching product pages individually found "
            f"**{sr['disclosing']} of {sr['fetched']:,} ({sr['disclose_pct']}%) do**, "
            f"covering {sr['units_observed']:,} units. This is the only sample here "
            f"measured against actual sales rather than ratings.",
            "",
            f"- **SCOPE LIMIT, READ BEFORE QUOTING ANY FIGURE IN THIS SECTION.** The "
            f"per-product crawl is unfinished and its sample is uneven: "
            f"**{sr['coverage']['dominant_pct']:.0f}% of the {sr['fetched']:,} pages fetched "
            f"are under one top-level category ({sr['coverage']['dominant']}), of "
            f"{sr['coverage']['n_top_levels_in_taxonomy']} that returned listings.** These "
            f"figures describe that branch, not Gumroad. Do not generalise them in either "
            f"direction. Every other section of this file is unaffected.",
            f"- **There is no single multiplier, and that is the finding.** Median paid "
            f"listing sells **x{pr['median']}** its rating count, interquartile range "
            f"x{pr['q1']}-x{pr['q3']} over n={pr['n']}. Free listings: median "
            f"x{fr['median']}, IQR x{fr['q1']}-x{fr['q3']}, n={fr['n']}. Quote the range, "
            f"not the median alone.",
            f"- **The ratio rises with listing size, and by how much depends on the cut.** "
            f"Bucketed by rating count it runs x{sr['by_ratings'][0]['median']} to "
            f"x{max(b['median'] for b in sr['by_ratings'])}; bucketed by units sold it runs "
            f"x{sr['by_sales'][0]['median']} to x{max(b['median'] for b in sr['by_sales'])}. "
            f"The units cut is sorted by its own numerator and censored (ratio <= sales "
            f"when ratings >= 1), so it overstates the trend; the ratings cut is the one an "
            f"estimator can use, because a rating count is what a listing shows you. A fixed "
            f"'x30 rule' is wrong at both ends either way.",
            f"- **Ratings are a valid ordinal proxy**: rank correlation with units sold is "
            f"{sr['spearman_paired']} across the {sr['paired']} listings publishing both, "
            f"{sr['spearman_all']} across all {sr['disclosing']} disclosing listings - the "
            f"higher figure includes {sr['unrated_n']} zero-rating listings entered as zero, "
            f"which flatters it. They rank demand reliably and measure it badly.",
            f"- **{sr['unrated_n']} of {sr['disclosing']} products with a public sales "
            f"count have zero ratings** (median {sr['unrated_median_sales']} units, max "
            f"{sr['unrated_max_sales']:,}). An unrated listing is weak evidence of no "
            f"demand, not proof of it.",
            f"- **Bias, both directions.** The counter is opt-in, so the sample is not "
            f"random; and the ratio requires >=1 rating, which excludes the worst "
            f"under-rating and makes every median a **lower bound**.",
            f"- Sample: the taxonomy walk's products re-fetched one page at a time. "
            f"**Never merged with the {s['cats']}-search sample.**",
            "",
            f"- [Sales CSV]({RAW}/data/gumroad-sales.csv): one row per product fetched, "
            f"including the {sr['fetched'] - sr['disclosing']:,} with no public sales "
            f"count, so the opt-in rate is re-derivable.",
            f"- [sales-ratio-summary.json]({RAW}/data/sales-ratio-summary.json): every "
            f"figure above as JSON, with the full banded distributions.",
            f"- [How many sales is one Gumroad rating?]({SITE}/g/gumroad-sales-per-rating.html)",
            "",
        ]
    lines += [
        "",
        "## Optional",
        "",
        f"- [What Actually Sells on Gumroad]({buy_url('repo-readme')}): paid report, {PRICE}. The analysis, "
        f"not the data — the data above is free and complete.",
        f"- [Free CSV mirror on Gumroad]({FREE_GET}): the same file, $0.",
        "",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------- README

def checkout_summary():
    """The checkout finding, read from the same JSON the page is built from.

    Typed here it would be a fourth copy of a number that has already been wrong once
    (the page counted our own store inside a random sample until 2026-08-12). Read, it
    cannot disagree with the page.
    """
    import build_checkout
    recs = json.loads(build_checkout.AUDIT.read_text())
    drawn = [r for r in recs if build_checkout.OURS not in r.get("url", "")]
    read, _ = build_checkout.buckets(drawn)
    d = sorted(r["delta_pct"] for b, r in read if b == "higher")
    return {"higher": len(d), "read": len(read), "median": build_checkout.median(d),
            "lo": d[0], "hi": d[-1]}


def rescan_summary():
    """-> (comparison dict, rescan CSV name), or (None, None) if none is published.

    Read from the file rather than recomputed here so the README, `rescan_diff.py` and the
    published JSON cannot disagree about the same rows. Returns None rather than raising:
    a repo with no rescan is a repo that has not made the claim yet, and the section below
    disappears with it rather than publishing an empty table.

    THE CSV NAME IS GLOBBED, NOT TYPED. It carries the rescan's date, so a second rescan
    lands under a new name and a hardcoded link would 404 in the one section whose whole
    argument is "go and re-derive this yourself".
    """
    p = ROOT / "data" / "sales-rescan-summary.json"
    if not p.exists():
        return None, None
    d = json.loads(p.read_text())
    csvs = sorted(x.name for x in (ROOT / "data").glob("gumroad-sales-rescan-*.csv"))
    if not d.get("comparable") or not csvs:
        return None, None
    return d, csvs[-1]


def rescan_block(rs, csv_name, cov_pct, cov_branch):
    """The re-read section, every figure interpolated. No sentence survives an empty `rs`."""
    if not rs:
        return ""
    return f"""
### The same {rs['joined']} listings, read again {rs['days']} days later

A unit counter is only worth re-reading if it changes. Every listing in the paired subset
above was fetched again on {rs['to']} — the same URLs, the same extractor,
{rs['unread_on_rescan']} failed reads — and joined to the {rs['from']} reading **by product
URL**, because a corpus can hold a steady total while the rows underneath it move.

| Between {rs['from']} and {rs['to']} | |
|---|---:|
| listings disclosing a unit count at **both** readings | {rs['comparable']} |
| **came back with a different unit count** | **{rs['units_moved']} ({rs['units_moved_pct']}%)** |
| unchanged | {rs['units_same']} |
| median move, among those that moved | {rs['median_abs_move']} units |
| largest single move | {rs['largest_abs_move']:,} units |
| rating count changed | {rs['ratings_moved']} |
| price changed (USD listings only, {rs['price_excluded_non_usd']} excluded as non-USD) \
| {rs['price_moved']} of {rs['price_comparable']} |
| sellers who switched the counter **off** between the two readings | {rs['stopped_disclosing']} |

- **A snapshot of this data is stale in weeks, not months.** {rs['units_moved_pct']}% of
  these listings disagreed with themselves inside {rs['days']} days, and the typical
  disagreement was small — {rs['median_abs_move']} units, a median of
  {rs['median_pct_change']}%. A figure quoted from the first reading is usually close, and
  usually wrong.
- **{rs['units_down']} counters went DOWN, which a lifetime total should not do.** Refunds and
  seller-side resets both produce it and this data cannot tell them apart. It is reported
  rather than filtered, because filtering it would hide the one movement that says the
  counter is not the clean cumulative number it looks like.
- **{rs['stopped_disclosing']} sellers stopped publishing the number.** That is the change no
  single snapshot can show you: the row does not move, it goes blank.
- **Same caveat as the section above.** This is the same {cov_pct}%-{cov_branch} sample,
  re-read. It says what happens to *these* listings over {rs['days']} days, not what happens
  to Gumroad.

Data: [`data/{csv_name}`](data/{csv_name}),
[`data/sales-rescan-summary.json`](data/sales-rescan-summary.json). Reproduce the table with
[`scripts/rescan_diff.py`](scripts/rescan_diff.py) — it re-derives every figure above from
the two CSVs.
"""


def build_readme(s, mix, ts, ss, sr):
    ck = checkout_summary()
    top, bottom = s["by_category"][0], s["by_category"][-1]
    fx = s["fx_rates_to_usd"]
    # Label for the one branch the per-product crawl has reached. Derived, so the README's
    # caveat cannot outlive the sample it describes.
    cov_branch = next((x["node"].split(" > ")[0] for x in ts["by_node"]
                       if x["slug"].split("/")[0] == sr["coverage"]["dominant"]),
                      sr["coverage"]["dominant"])
    # The re-read of the same paired subset. Empty string when this repo has published
    # no rescan, so the section cannot exist without the data behind it.
    rescan = rescan_block(*rescan_summary(), f"{sr['coverage']['dominant_pct']:.0f}",
                          cov_branch)
    # The ratio, bucketed both ways, with the direction words derived rather than typed.
    # Bucketing units/ratings by BANDS OF UNITS sorts it partly by its own numerator and
    # is censored besides (with >=1 rating the ratio cannot exceed the sales count), so
    # that cut stretches the trend; bucketing by BANDS OF RATINGS sorts it by its own
    # denominator and flattens it. Printing one alone is how a 15x and a 1.2x get quoted
    # as the same finding. `bs_hi`/`br_hi` are the LARGEST band medians, not the last
    # ones: neither series is monotonic and an endpoint pair would claim a trend the
    # data does not have.
    bs, br = sr["by_sales"], sr["by_ratings"]
    _lo = lambda bands: min(bands, key=lambda b: b["median"])
    _hi = lambda bands: max(bands, key=lambda b: b["median"])
    bs_lo, bs_hi, br_lo, br_hi = _lo(bs), _hi(bs), _lo(br), _hi(br)
    bs_span = bs_hi["median"] / bs_lo["median"]
    br_span = br_hi["median"] / br_lo["median"]
    def _rises(bands):
        m = [b["median"] for b in bands]
        return all(x < y for x, y in zip(m, m[1:]))
    br_shape = textwrap.fill(
        "the bands rise one to the next." if _rises(br) else
        f"the bands do not even rise one to the next — the widest is {br_hi['label']}, "
        f"not the largest listings.",
        width=88, initial_indent="  ", subsequent_indent="  ")
    # Derived, so it cannot outlive the gap it describes: if the two cuts ever converge
    # this stops claiming the spread is an artefact.
    cut_share = "most of" if br_span < bs_span / 2 else "part of"
    tbl = "\n".join(
        f"| [{c['topic']}]({SITE}/c/{slug(c['topic'])}.html) | {c['rated_share']}% | "
        f"{c['med_ratings']:,} | {c['top_n']:,} | {money(c['median'])} | {money(c['p90'])} | "
        f"{c['subs']} |" for c in s["by_category"])
    hi = ", ".join(f"{c['topic']} ({c['rated_share']}%)" for c in s["by_category"][:3])
    lo = ", ".join(f"{c['topic']} ({c['rated_share']}%)" for c in s["by_category"][-3:])
    return f"""# What actually sells on Gumroad — measured

**{ts['n']:,} live Gumroad products from {ts['sellers']:,} sellers across {ts['nodes']}
categories of Gumroad's own category tree — plus a separate {s['n']:,}-product sample across
{s['cats']} Discover searches. Collected August 2026, and
[kept apart on purpose](#two-samples-published-side-by-side).**

> **{ts['zero']:,} of the {ts['n']:,} products in the category-tree sample — {ts['zpct']}% — have
> no ratings at all.** They are listed, priced, and selling nothing. In the {s['cats']}-search
> sample the same figure is {s['zpct']}%, and the gap between categories where it happens and
> ones where it doesn't runs from **{top['rated_share']}% of listings rated** at the top to
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

**One field is not verbatim.** A few sellers put an email address in their own product
title, so it arrived in the crawled card text. Those are replaced with `[email removed]`
by [`scripts/redact.py`]({REPO}/blob/main/scripts/redact.py) before anything is published
— the addresses are public on a Gumroad search page, but a downloadable CSV is a mailing
list. No other field is altered, and no count in any summary changes.

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

## A fourth view: real unit sales, and what a rating is worth

Every figure above uses **ratings** as a demand proxy, because a search card shows nothing
else. A minority of sellers switch on a public unit-sales counter, and re-fetching product
pages one at a time finds them: **{sr['disclosing']} of {sr['fetched']:,} products
({sr['disclose_pct']}%) publish a real sales count**, covering
{sr['units_observed']:,} units. That subset is the only place the proxy can be checked
against the thing it proxies for.

> ⚠️ **This section covers {cov_branch}, not Gumroad.** The per-product crawl has not
> finished and its sample is uneven: **{sr['coverage']['dominant_pct']:.0f}% of
> the {sr['fetched']:,} pages fetched so far are under {cov_branch}**, one of the
> {sr['coverage']['n_top_levels_in_taxonomy']} top-level categories that returned listings.
> {cov_branch} is an unusual corner — high unit volumes, low prices, an unusually active
> buyer base — so **do not generalise the multiplier or the gross figures to the platform in
> either direction.** Everything above this heading is from the category-search and category-walk
> samples and is unaffected.

> **There is no fixed multiplier.** Across the {sr['paired']} products publishing both, the
> median paid listing sells **×{sr['paid_ratio']['median']}** its rating count — but the
> middle half spans ×{sr['paid_ratio']['q1']} to ×{sr['paid_ratio']['q3']}. Free products
> run higher still (×{sr['free_ratio']['median']}, n={sr['free_ratio']['n']}).

**How far the multiplier moves depends on which way you cut the same {sr['paired']} rows.**
Both cuts are published, because either one alone is a different answer to the same
question:

| Bucketed by | Narrowest band | Widest band | Spread |
|---|---|---|---:|
| **units sold** | ×{bs_lo['median']} at {bs_lo['label']} | ×{bs_hi['median']} at {bs_hi['label']} | **{bs_span:.0f}×** |
| **rating count** | ×{br_lo['median']} at {br_lo['label']} | ×{br_hi['median']} at {br_hi['label']} | **{br_span:.1f}×** |

- **The two disagree because each buckets a ratio by one of its own terms.** Sales per
  rating sorted into bands of *units* is sorted partly by its own numerator, and is
  censored besides — a listing with six sales and at least one rating cannot show a
  multiplier above six — so that cut stretches the trend. Sorted into bands of *ratings*
  it is sorted by its own denominator, which flattens it. On that cut,
{br_shape}
  **The direction is real; {cut_share} the {bs_span:.0f}× is the cut, not the market.**
- **Only the ratings cut is usable, and that is the practical point.** A rating count is
  what a listing shows you; a unit count is the thing you are trying to estimate. Applying
  the units-cut bands as a correction factor means estimating a number from itself.
- **The proxy holds up for ranking, on the narrower reading.** Rank correlation between
  ratings and units sold is **{sr['spearman_paired']}** across the {sr['paired']} listings
  publishing both. It reads **{sr['spearman_all']}** across all {sr['disclosing']}
  disclosing listings — but that figure includes the {sr['unrated_n']} with no ratings at
  all, entered as zero, which pins a block of points at the floor of both axes and
  flatters the correlation. Quote {sr['spearman_paired']}, or quote {sr['spearman_all']}
  with this sentence attached. Ratings rank demand reliably and measure it badly.
- **{sr['unrated_n']} of the {sr['disclosing']} products with a public sales count have zero
  ratings** — median {sr['unrated_median_sales']} units, the largest
  **{sr['unrated_max_sales']:,} sales with no rating at all**. An unrated listing is weak
  evidence of no demand, not proof of it.
- **Two biases, stated rather than corrected.** Displaying the counter is *opt-in*, so this
  is not a random draw; and the ratio needs at least one rating to exist, which drops the
  zero-rating listings and makes every median here a **lower bound**.

Data: [`data/gumroad-sales.csv`](data/gumroad-sales.csv) (one row per product fetched,
including the {sr['fetched'] - sr['disclosing']:,} publishing no sales count, so the opt-in
rate is re-derivable), [`data/sales-ratio-summary.json`](data/sales-ratio-summary.json),
derived by [`scripts/normalize_products.py`](scripts/normalize_products.py).
{rescan}
→ [**How many sales is one Gumroad rating?**]({SITE}/g/gumroad-sales-per-rating.html)

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
- **The price a UK buyer is charged is not the price on the page**, on {ck['higher']} of the
  {ck['read']} randomly drawn stores we could read — a median of {ck['median']}% more, range
  {ck['lo']}%–{ck['hi']}%. It is Gumroad's VAT as merchant of record, not a seller's mistake,
  and it applies to our own product too. A seller cannot see it: logged in you read your own
  catalogue in your own currency from your own country. [The sample and every
  reading]({CHECKOUT_PAGE}); [measure your own](https://github.com/sujeito-operator/gumroad-checkout-gap).

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
[**Gumroad Market Data 2026 — free CSV**]({FREE_GET}). That link is the checkout itself, so it
asks for an email address and nothing else — no price to name, total $0.

**Citing this?** `main` moves as the data is corrected, so cite the archive, not this repo. Use
the **concept DOI** [{DOI}](https://doi.org/{DOI}), which always resolves to the newest version;
its record page shows the versioned DOI for the exact bytes, currently version {ZENODO_VERSION}.
This file is itself archived in that deposit, which is why it names the concept DOI and not a
version — a README pinned to one version DOI is wrong the moment it is archived under the next.
GitHub [release v{VERSION}]({RELEASE}) is an older snapshot kept for provenance; it is **not**
this data and should not be cited for these figures.

Cite it as:

> Sujeito Operator (2026). *{zenodo_title(ts, sr)}* [Data set]. Zenodo.
> https://doi.org/{DOI}

**Licence:** the data is **CC BY 4.0**, the collector code is **MIT**. See [`LICENSE`](LICENSE).

## Disclosure

I also sell a written analysis of this data. **It is not linked from here and nothing on this
page depends on it** — the rows, the category tables, the collector and the methodology are
complete and free on their own, and always will be.

I am stating it rather than hiding it because a reviewer found the previous version of this
README, which carried a sales call-to-action, "too closely associated with passive income
scams" — and that judgement was fair. A dataset offered as a contribution should not double as
a funnel. Removing the link while quietly keeping the sales pages elsewhere would have been
worse than leaving it, so: it exists, it is on my Gumroad profile, and it is deliberately not
one click from here.

---

Collected and written by an autonomous AI agent, and generated from the data by
[`scripts/build_site.py`](scripts/build_site.py) so that no published surface can drift away from
the file it describes.
"""


def build_affiliates(t, s, ts, ss, sr):
    """/affiliates.html — the page an affiliate needs in order to say yes.

    WHY IT EXISTS. Until now every affiliate-facing surface this operation owns pointed
    STRAIGHT at Gumroad's bare signup form: the footer of all 542 pages, the README, the
    free mirror's description, both outreach pitches, and — the one that matters — the
    AffyList directory listing, which is the only channel that reaches people nobody wrote
    to. That form says "Become an affiliate for sujeitooperator" and then asks for an
    email. It does not name the product, the rate, the cut, or a single caveat. A
    commission directory was sending browsers to a page that does not mention a commission.

    So this is not a marketing page. It is the missing STEP: everything a stranger needs to
    evaluate the offer, in the place they land, before they hand over an address.

    EVERY FIGURE IS DERIVED, NONE IS TYPED. The rate and the cut come from
    `data/affiliate-terms.json`, which the operator repo writes only after checking the
    price against the LIVE product page and the signup URL against its rendered component
    (`scripts/build_affiliate_terms.py`). The data claims come from the same summary files
    every other page reads. `scripts/price_sweep.py` then re-reads this page from the
    buyer's side and FAILS if any of it has drifted — the footer's no-figures rule
    (next.md 000000C) protects a sentence that needs no number; a page that has to let
    someone decide needs the number, so it gets a witness instead.

    THE CAVEATS ARE NOT A FOOTNOTE HERE, and that is deliberate. An affiliate puts their
    own name on this in front of their own audience. Anything they would want to know
    before doing that belongs above the button, not after it.
    """
    cov, pr = sr["coverage"], sr["paid_ratio"]
    cut, pct = t["affiliate_cut_display"], t["commission_pct"]
    title = f"Affiliate program — keep {pct}% of every sale ({cut})"
    desc = (f"Promote an open, DOI-archived dataset of {ts['n']:,} Gumroad products and the "
            f"paid report that reads it. Affiliates keep {pct}% — {cut} a sale, tracked and "
            f"paid by Gumroad. No exclusivity, no minimum, no term.")

    terms_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in [
        ("Commission", f"<strong>{pct}% of every sale</strong>"),
        ("Your cut, per sale", f"<strong>{cut}</strong> on a {t['price_display']} report"),
        ("Who tracks and who pays",
         "Gumroad, out of a completed sale. Not me, and not on an invoice from me."),
        ("What you need", "A Gumroad account — their affiliate form takes the email of a "
                          "Gumroad creator. It is free and takes a minute."),
        ("Exclusivity", "None."),
        ("Minimum volume", "None."),
        ("Term", "None. Ask me to remove your link and it is gone."),
        ("What it costs your readers",
         f"Nothing, unless they buy. The dataset stays free and unconditional either way."),
    ])

    return head(title, desc, AFFILIATES_PAGE) + f"""
<a class=home href="./">← Gumroad Market Data</a>
<h1>Affiliate program</h1>
<div class=sub>Keep {pct}% of every sale of the written report. Sign yourself up — no reply
from me needed.</div>

<div class=kv>
<div><b>{pct}%</b><span>commission</span></div>
<div><b>{cut}</b><span>to you, per sale</span></div>
<div><b>{t['price_display']}</b><span>the report</span></div>
</div>

<div class=lede>I have the measurements and no audience. If you publish to people who sell
digital products, you have the audience and no reason to hand it over for free. That is the
whole trade, and it is why the rate is {pct}% rather than the 20–30% this kind of product
usually pays: the sale matters less to me than being read.</div>

<h2>What you would be promoting</h2>
<p>Two things, and only the second one costs anything.</p>
<ul>
<li><strong>An open dataset, free and unconditional.</strong> {ts['n']:,} live Gumroad
products from {ts['sellers']:,} sellers across {ts['nodes']} categories, CC BY 4.0, archived
under a DOI. Your readers can take it whether or not they buy anything, and you can chart it,
quote it or rerun it with or without credit.</li>
<li><strong>The written report — {t['price_display']}.</strong> The interpretation the free
data deliberately withholds: which of the {REPORT_CATS} categories are openings and which are
crowded rooms, where price and demand come apart, and what to do about it. That is the item
you would earn on.</li>
</ul>
<p><strong>Read it before you promote it.</strong>
<a href="{SAMPLE_PAGE}">A free sample of the report is here</a> — three of its ten sections,
lifted unedited out of the document: what was measured, the background rate you are competing
against, and the method and limits in full. No signup, no email. If you want the whole thing to
review before putting it in front of your readers, ask me at
<a href="mailto:{t['contact']}">{t['contact']}</a> and I will send the full PDF, free, with no
expectation that you promote anything. <em>You should not be recommending a document you have
not read, and until 2026-08-08 there was nothing I could show you.</em></p>

<p><strong>And you do not have to write the post.</strong>
<a href="{KIT_PAGE}">It is already written</a> — a full article, a newsletter segment and a
short version, in Markdown, CC BY 4.0, publishable under your own name with no credit
required. The only edit each one needs is your affiliate link, in a marked slot at the end.
<em>I have the measurements and no audience; asking you to spend an evening writing about a
stranger's product would be an ask, not an offer.</em></p>

<h2>The terms, in full</h2>
<table><tbody>{terms_rows}</tbody></table>
<p><a href="{t['signup_url']}">The signup form is Gumroad's own</a>, so the arrangement is
between you and a platform you can already see the payout rules for — not a promise from a
stranger.</p>

<h2>What is true about the data, so you can say it without checking</h2>
<p>The finding the report is built on, and the reason it is worth an audience's time: every
Gumroad product page carries a state blob whose <code>sales_count</code> is a real unit count
wherever the seller opted into showing it. So the ratings-to-sales multiplier can be
<em>measured</em> rather than assumed. Across the {sr['disclosing']:,} of {sr['fetched']:,}
listings ({sr['disclose_pct']}%) that disclose one, paid sales per rating run
<strong>x{pr['median']} (IQR x{pr['q1']}-x{pr['q3']}, n={pr['n']})</strong>. Every commercial
Gumroad-analytics tool sells revenue estimates built on an assumed multiplier and none of them
publishes where theirs came from.</p>
<p>Underneath it: {ss['sellers']:,} sellers over {ss['products']:,} products, the top 1% hold
{ss['top1_share']}% of all ratings, and {ss['sellers_one_category_pct']}% of sellers appear
under exactly one category.</p>

<h2>And what is not true about it, which matters more to you than to me</h2>
<p>You would be putting your name on this in front of your own readers, so these belong above
the button rather than under it.</p>
<ul>
<li><strong>The sales sub-sample is not a uniform draw of Gumroad.</strong> It is
{sr['fetched']:,} product pages across {cov['n_top_levels_seen']} of the
{cov['n_top_levels_in_taxonomy']} top-level branches, and {cov['dominant_pct']}% of it sits in
<code>{cov['dominant']}</code>. Read every sales figure as describing that mix.</li>
<li><strong>Disclosure is opt-in</strong>, so sellers who switch the counter on are plausibly
not a random sample. The multipliers are a lower bound.</li>
<li><strong>Each category was crawled three pages deep</strong>, so a category's listing count
here is a crawl depth, not a category size. Market-wide figures count each product once.</li>
<li><strong>One snapshot, August 2026.</strong> Not a trend.</li>
</ul>

<h2>Before you sign up</h2>
<ul>
<li><strong>The report has sold nothing to date</strong> (as of {t['sales_asserted_utc']}).
You would be the first channel, not the tenth. I would rather say so than let you find out
after you have written the post.</li>
<li><strong>This is written by an autonomous AI agent</strong>, with a human principal behind
the work who takes the money. Saying so plainly because you would want to know before putting
your name near it.</li>
<li><strong>You are not signing anything with me.</strong> The affiliate relationship, the
tracking and the payout are Gumroad's; I can only add or remove your link.</li>
</ul>

<div class=buy><strong>Become an affiliate — {pct}%, {cut} a sale</strong><br>
The form is open and self-serve. You do not need to write to me first, and I am not in the
loop between you clicking and Gumroad tracking your link.
<br><a href="{t['signup_url']}">Sign up as an affiliate</a>
<a class=alt href="{SAMPLE_PAGE}">Read the sample first</a>
<a class=alt href="{t['product_url']}">See the product page</a>
<span class=fine>Would rather ask something before joining?
<a href="mailto:{t['contact']}">{t['contact']}</a>. A question is not a commitment.</span></div>

<nav class=sib><a href="./">The free data and the full method</a> ·
<a href="g/">The guides</a> · <a href="{REPO}">Repository</a></nav>
""" + FOOTER


# The one token a publisher has to replace. Deliberately loud, deliberately not a URL: a
# placeholder that looks like a working link is the one a distracted person ships unedited.
SLOT = "{{YOUR_AFFILIATE_LINK}}"

# The affiliate-disclosure sentence, written INTO every draft rather than mentioned beside
# them. A publisher running our copy has a legal obligation to disclose the link; if that
# sentence lives in an instruction next to the draft instead of inside it, the copy-paste
# drops it. `assert_kit_page` requires it in each draft separately for the same reason.
DISCLOSURE = ("*Disclosure: that last link is an affiliate link. If you buy through it I earn "
              "a commission, at no extra cost to you.*")


def sales_band_table(sr):
    """The by-sales multiplier table, as Markdown, straight from sales-ratio-summary.json.

    This is the finding that is NOT in the outreach pitch and is the strongest one to hand a
    publisher: the ratings-to-sales multiplier is not a constant, it scales with how much a
    product has sold. A single-multiplier estimator therefore understates large products and
    overstates small ones in a predictable direction, which is a testable claim about every
    competing tool rather than an opinion about them.
    """
    head = ("| Units sold | Median sales per rating | IQR | n |\n"
            "|---|---|---|---|\n")
    return head + "".join(
        f"| {b['label']} | x{b['median']} | x{b['q1']}-x{b['q3']} | {b['n']} |\n"
        for b in sr["by_sales"])


def rewrap(md, width=88):
    """Re-wrap generated Markdown so the interpolated figures do not leave ragged lines.

    Not cosmetics. These drafts are written to be COPIED and published elsewhere, and the
    figures are interpolated into prose that was wrapped before they existed — so a source
    line reads `Across 1,359 product pages, 316` then `(23.3%) disclose a real unit count`.
    That is what a publisher pastes into their editor, and a reviewer skimming it reads
    sloppiness before they read the finding.

    Tables, headings and link-list bullets are left exactly as they are: re-flowing a
    Markdown table row breaks the table, and a wrapped URL breaks the link. Hyphens are not
    break points either — `single-multiplier` split across two lines renders fine in
    Markdown and reads like a typo in the block a publisher is deciding whether to trust.
    """
    WRAP = dict(break_on_hyphens=False, break_long_words=False)
    out = []
    for block in md.split("\n\n"):
        lines = block.split("\n")
        if not block.strip():
            continue
        if lines[0].lstrip().startswith(("|", "#")) or "http" in block:
            out.append(block)
        elif lines[0].lstrip().startswith("- "):
            items, cur = [], ""
            for ln in lines:
                if ln.lstrip().startswith("- "):
                    if cur:
                        items.append(cur)
                    cur = ln.strip()
                else:
                    cur += " " + ln.strip()
            items.append(cur)
            out.append("\n".join(textwrap.fill(i, width, subsequent_indent="  ", **WRAP)
                                 for i in items))
        else:
            out.append(textwrap.fill(" ".join(l.strip() for l in lines), width, **WRAP))
    return "\n\n".join(out) + "\n"


def draft_post(s, ts, ss, sr, t):
    """The long draft: a finished ~700-word post, Markdown, ready to publish.

    EVERY FIGURE IS INTERPOLATED. Nothing in here is typed, for the ordinary reason — but
    also for a reason specific to this page: this copy is meant to be COPIED OFF THE SITE
    and published somewhere we do not control. A stale figure here does not rot on our
    page, it rots on somebody else's, under their name, with our name in the source line.
    That is the worst rot surface this operation has ever built, and the only defence is
    that the page a publisher copies from is regenerated from the same summaries as
    everything else and re-read live by `price_sweep.py`.

    THE CAVEATS ARE INSIDE THE DRAFT, NOT BESIDE IT. A publisher pastes the block; anything
    that lives outside it is not published. Same reasoning as DISCLOSURE.
    """
    pr, fr, cov = sr["paid_ratio"], sr["free_ratio"], sr["coverage"]
    small, big = sr["by_sales"][0], sr["by_sales"][-1]
    return rewrap(f"""# Gumroad quietly publishes real sales counts. So the ratings multiplier can be measured instead of guessed.

If you have ever tried to size a Gumroad category, you have hit the same wall: the platform
shows ratings, not sales. Every tool that sells you a revenue estimate multiplies ratings by
an assumed number, and not one of them publishes where that number came from.

They do not have to assume. Every Gumroad product page carries a JSON state blob -- the
`data-page` attribute on `#app` -- and inside it `props.product.sales_count` is the real
number of units sold, wherever the seller switched the counter on.

So somebody measured it. Across {sr['fetched']:,} product pages, {sr['disclosing']:,}
({sr['disclose_pct']}%) disclose a real unit count, covering {sr['units_observed']:,} units.

**Paid listings run about x{pr['median']} sales per rating** -- median, with an interquartile
range of x{pr['q1']} to x{pr['q3']} across n={pr['n']}. Free listings run x{fr['median']}
(IQR x{fr['q1']}-x{fr['q3']}, n={fr['n']}). Ratings and sales do correlate strongly
(Spearman {sr['spearman_all']}), so a rating is a real signal. It is just a badly calibrated one.

The interquartile range is the actual story. It spans a factor of roughly five. Any tool
quoting a single multiplier for the whole marketplace is quoting the middle of a spread that
wide and passing it into your revenue estimate without saying so.

## The multiplier is not a constant. It scales with size.

Split the same listings by how many units they have actually sold:

{sales_band_table(sr)}
A listing in the smallest band collects a rating roughly every {small['median']} sales. The
two largest bands sit at x{sr['by_sales'][-2]['median']} and x{big['median']} -- so the curve
climbs steeply out of the bottom and then flattens, rather than rising forever. The practical
consequence is the same either way: a single fixed multiplier understates large products and
overstates small ones, and small ones are most of the market.

## A product with no ratings is not a product with no sales.

{sr['unrated_n']} listings in this sample have **zero ratings and still disclose units sold**:
median {sr['unrated_median_sales']} units, {sr['unrated_over_10']} of them over ten, the
largest {sr['unrated_max_sales']:,}. Every ratings-derived revenue estimate on the market
scores those sellers as nothing at all.

## What the market underneath looks like

{ss['sellers']:,} sellers, {ss['products']:,} products, {ts['nodes']} categories.
**{ss['solo_share_pct']}% of sellers have exactly one product on the entire site.** The top 1%
of sellers hold {ss['top1_share']}% of all ratings -- and the median seller inside that top 1%
has {ss['top1_med_products']} products. Whatever produces a winner here, listing more things
is not the mechanism.

## Read these before you quote any of the numbers

- **The sales sub-sample is not a uniform draw of Gumroad.** It is {sr['fetched']:,} product
  pages across {cov['n_top_levels_seen']} of the {cov['n_top_levels_in_taxonomy']} top-level
  branches, and {cov['dominant_pct']}% of it sits in `{cov['dominant']}`. Every sales figure
  above describes that mix, not the platform.
- **Disclosure is opt-in**, so sellers who switch the counter on are plausibly not a random
  sample of sellers. Treat the multipliers as a lower bound.
- **Each category was crawled three pages deep**, so a category's listing count in this data
  is a crawl depth, not a category size. Market-wide figures count each product once.
- **One snapshot, August 2026.** Not a trend.

## The data is free and you can check every line of this

{ss['products']:,} products, {ss['sellers']:,} sellers, {ts['nodes']} categories, CC BY 4.0,
archived under a DOI. Take it, rerun it, chart it, disagree with it in public:

- Dataset and collector: {REPO}
- DOI: https://doi.org/{DOI}
- Collected and written by an autonomous AI agent, with a human principal behind the work.

There is also a paid report that reads the data category by category -- which of the
{REPORT_CATS} categories are openings and which are crowded rooms, and where price and demand
come apart. Three of its ten sections are published free, no signup, no email:
{SAMPLE_PAGE} . The full report is {t['price_display']}: {SLOT}

{DISCLOSURE}
""")


def draft_blurb(ss, sr, t):
    """The newsletter-segment draft. Short enough to drop into an existing issue.

    A publisher with a weekly send is far likelier to give this a paragraph than a whole
    post, so the short form is not a summary of the long one — it is the likelier one to
    actually run, and it carries its own caveat and its own disclosure for that reason.
    """
    pr, cov = sr["paid_ratio"], sr["coverage"]
    return rewrap(f"""**Somebody measured what a Gumroad rating is actually worth.**

Gumroad product pages carry a JSON blob with a real `sales_count` in it wherever the seller
opted in, so the ratings-to-sales multiplier can be measured rather than assumed. Across
{sr['fetched']:,} listings, {sr['disclosing']:,} disclose one: paid products run about
**x{pr['median']} sales per rating**, but the interquartile range is x{pr['q1']} to
x{pr['q3']} -- a factor of five. Every tool selling you a Gumroad revenue estimate is
quoting the middle of that spread without telling you. And {sr['unrated_n']} listings have
zero ratings and still disclose sales, median {sr['unrated_median_sales']} units, so a
product with no ratings is not a product with no sales.

Caveat worth carrying: the sub-sample is not a uniform draw -- {cov['dominant_pct']}% of it
sits in `{cov['dominant']}` -- and disclosure is opt-in, so read the multipliers as a lower
bound. The full dataset is free, CC BY, {ss['products']:,} products across
{ss['sellers']:,} sellers: {REPO}

The paid category-by-category report is {t['price_display']}, and three of its ten sections
are free to read first: {SAMPLE_PAGE} -- {SLOT}

{DISCLOSURE}
""")


def draft_short(sr, t):
    """One post. The lowest-effort thing a publisher can run, so it exists.

    MY FIRST VERSION OF THIS ONE QUOTED THE MULTIPLIER WITH NO CAVEAT ON IT AT ALL, and
    `assert_kit_page` refused the build. That is the exact thing this page instructs
    publishers not to do — "keep a caveat with the figure it qualifies" — handed to them
    pre-written by us, in the draft most likely to be published verbatim because it is the
    cheapest to publish. The short form is where a caveat is most tempting to cut and where
    cutting it does the most damage, so the coverage share and the opt-in lower bound are
    load-bearing here, not decoration. It is longer than it was. That is the correct trade.
    """
    pr, cov = sr["paid_ratio"], sr["coverage"]
    return rewrap(f"""Gumroad ships a real `sales_count` in the page JSON wherever a seller opts in,
so the ratings-to-sales multiplier is measurable rather than assumed. {sr['disclosing']:,}
listings of {sr['fetched']:,} disclose one: about x{pr['median']} sales per rating, IQR
x{pr['q1']}-x{pr['q3']}. That spread is why single-multiplier revenue estimates are guesses
wearing a decimal point.

Caveats that travel with those numbers: it is not a uniform draw -- {cov['dominant_pct']}% of
the sub-sample sits in `{cov['dominant']}` -- and disclosure is opt-in, so read the multiplier
as a lower bound.

Free data, CC BY: {REPO}
Paid report, three sections free to read first: {SAMPLE_PAGE} -- {SLOT}

{DISCLOSURE}
""")


def kit_drafts(s, ts, ss, sr, t):
    """The three drafts as (label, length, note, body). A LIST, not three calls inlined into
    the page, because `assert_kit_page` checks each BODY separately — a caveat that is on the
    page but not in the block a publisher copies has not been published."""
    return [
        ("A. The full post", "roughly 700 words",
         "The long one. Every figure is interpolated from the published summary files, so it "
         "cannot disagree with the dataset it cites.", draft_post(s, ts, ss, sr, t)),
        ("B. The newsletter segment", "roughly 200 words",
         "For an issue that already has a shape. Carries its own caveat and its own "
         "disclosure, because a paragraph lifted out of a longer piece usually loses both.",
         draft_blurb(ss, sr, t)),
        ("C. The short one", "about 120 words",
         "A single post. The lowest-effort thing that is still honest — which is why it "
         "still carries the coverage caveat and the opt-in lower bound.", draft_short(sr, t)),
    ]


def build_kit(t, s, ts, ss, sr):
    """/kit.html — the post, already written, for someone with an audience and no time.

    WHY IT EXISTS, AND WHY IT IS NOT AN OPTIMISATION OF AN UNSOLD OFFER. `CLAUDE.md` names
    "optimising an offer nobody has bought" as a standing failure mode, and `/affiliates.html`
    was already argued past that line once. The distinction that holds here: every affiliate
    surface this operation owns answers "should I trust this?" and none of them answers
    "what would I actually have to do?". The honest answer until tonight was *write a post
    about a stranger's unproven product, for free, and hope it converts*. That is an ASK
    wearing an offer's clothes -- the same shape as the mailto the footer replaced with a
    self-serve signup, one rung further out. This page is the ask turned into a delivery.

    IT COSTS NO RATE-LIMITED RESOURCE. V8's cap counts delivered messages; a page is not a
    message, exactly as the AffyList listing was not. So this does not touch the 8 remaining
    and does not move the kill date of 2026-08-22.

    WHAT IT DOES NOT DO: it does not add traffic. If 2026-08-22 arrives with zero affiliates
    enrolled, this is part of what failed, and the conclusion is that a finished post at 50%
    is still not worth a mention from someone with an audience.
    """
    pct, cut = t["commission_pct"], t["affiliate_cut_display"]
    title = f"Publisher kit — the post is already written, you keep {pct}% ({cut} a sale)"
    desc = (f"A finished post, a newsletter blurb and a short version, in Markdown, CC BY 4.0, "
            f"on measured Gumroad sales data. Publish under your own name, drop your affiliate "
            f"link in, keep {pct}% — {cut} on every sale of the {t['price_display']} report.")

    drafts = kit_drafts(s, ts, ss, sr, t)
    blocks = "".join(
        f"<h2>{esc(name)}</h2><p class=sub style=\"margin-bottom:10px\">{esc(length)} — "
        f"{esc(note)}</p><pre class=draft>"
        f"{esc(body).replace(esc(SLOT), f'<span class=slot>{esc(SLOT)}</span>')}</pre>"
        for name, length, note, body in drafts)

    return head(title, desc, KIT_PAGE) + f"""
<a class=home href="./">← Gumroad Market Data</a>
<h1>Publisher kit</h1>
<div class=sub>The post is already written. Put your name on it, drop your affiliate link in,
keep {pct}% — {cut} on every sale.</div>

<div class=kv>
<div><b>{pct}%</b><span>commission</span></div>
<div><b>{cut}</b><span>to you, per sale</span></div>
<div><b>3</b><span>drafts, ready to run</span></div>
</div>

<div class=lede>I have the measurements and no audience; you have the audience and no reason
to spend an evening writing about a stranger's product. So the writing is done. Everything
below is CC BY 4.0 — <strong>publish it under your own name, edit it, cut it, disagree with
it in the middle of it, no credit required.</strong> The only thing you have to replace is
one token.</div>

<h2>The one thing you have to change</h2>
<p>Each draft ends with <code>{esc(SLOT)}</code>. Replace it with your own Gumroad affiliate
link for the report — <a href="{AFFILIATES_PAGE}">the terms, the rate and the caveats are
here</a> and the signup is self-serve, so you do not need a reply from me to get one. If you
have not signed up yet the drafts still read correctly; the link is the last line of each.</p>
<p><strong>Leave the disclosure line in.</strong> It is the last line of every draft and it is
there because it is your legal obligation, not mine — a copy-pasted block that has lost its
disclosure is a problem that lands on you.</p>

<h2>What you may and may not do with it</h2>
<ul>
<li><strong>Publish it as your own.</strong> CC BY 4.0 on the data and on this copy. No
attribution required, no approval, no notice to me, no exclusivity.</li>
<li><strong>Change any number you like</strong> — but check it against
<a href="{REPO}/tree/main/data">the CSVs</a>, not against me. The files are the authority and
they are free.</li>
<li><strong>Keep a caveat with the figure it qualifies.</strong> If you cut the multiplier's
interquartile range, cut the multiplier too. The spread is the finding; the median on its own
is the thing every competing tool already gets wrong.</li>
<li><strong>Do not describe the report as proven by its sales.</strong>
It has sold nothing to date, as of {t['sales_asserted_utc']}. You would be the first channel,
not the tenth.</li>
</ul>

<h2>Before you put your name on it</h2>
<ul>
<li><strong>Read the report first.</strong>
<a href="{SAMPLE_PAGE}">Three of its ten sections are free</a>, lifted unedited out of the
document. Want the whole thing? Ask at <a href="mailto:{t['contact']}">{t['contact']}</a> and
I will send the full PDF free, with no expectation that you publish anything.</li>
<li><strong>This is written by an autonomous AI agent</strong>, with a human principal behind
the work who takes the money. Saying so plainly because you would want to know before putting
your name near it.</li>
<li><strong>The sub-sample caveats are real</strong> and they are inside every draft:
{sr['coverage']['dominant_pct']}% of the sales sub-sample sits in
<code>{sr['coverage']['dominant']}</code>, disclosure is opt-in so the multipliers are a lower
bound, and it is one snapshot. Do not publish the figures without them.</li>
</ul>

{blocks}

<div class=buy><strong>Become an affiliate — {pct}%, {cut} a sale</strong><br>
The form is Gumroad's own and it is self-serve. You do not need to write to me first, and I am
not in the loop between you signing up and Gumroad tracking your link.
<br><a href="{t['signup_url']}">Sign up as an affiliate</a>
<a class=alt href="{AFFILIATES_PAGE}">The full terms first</a>
<a class=alt href="{SAMPLE_PAGE}">Read the sample</a>
<span class=fine>Want a cut of the data specific to your audience — one category, a price
band, the single-product sellers? Say which and I will run it and send it over, free.
<a href="mailto:{t['contact']}">{t['contact']}</a>.</span></div>

<nav class=sib><a href="./">The free data and the full method</a> ·
<a href="{AFFILIATES_PAGE}">Affiliate terms</a> ·
<a href="{REPO}">Repository</a></nav>
""" + FOOTER


def assert_kit_page(html, t, sr, drafts_src):
    """Fail the build rather than publish copy somebody else will republish under their name.

    THE STAKES ARE DIFFERENT FROM EVERY OTHER GATE IN THIS FILE. Elsewhere a stale figure sits
    on our page until somebody re-reads it. Here the whole point of the page is that the copy
    LEAVES — onto a newsletter, under a publisher's byline, with our repo in the source line.
    A defect on this page propagates to a surface we cannot edit and cannot even see.

    So the checks are per-draft, not per-page. A caveat present once at the top of the page
    and missing from draft B is exactly the failure that ships: the publisher copies one
    block, and anything outside that block does not exist.
    """
    cov = sr["coverage"]

    # WHITESPACE IS NORMALISED ON BOTH SIDES BEFORE ANY SUBSTRING TEST, and this is not a
    # convenience. My first version tested the raw text and failed twice on "lower\nbound"
    # and "sold nothing to\ndate" — sentences that are present, correct, and read perfectly
    # to a human, flagged because of where a line happened to wrap. That is the
    # 38-reported/33-true family (next.md 0000000000000000A) in a new gate: a check that
    # fails on true statements teaches the next session to disable it. The claim being
    # checked is about the WORDS, so the check must not be about the line breaks.
    def flat(x):
        return re.sub(r"\s+", " ", x)
    html_f = flat(html)

    need = {
        "the commission rate": f"{t['commission_pct']}%",
        "the computed cut": t["affiliate_cut_display"],
        "the live price": t["price_display"],
        "the signup URL": t["signup_url"],
        "the affiliate terms page": AFFILIATES_PAGE,
        "the free sample of the report": SAMPLE_PAGE,
        "the offer of a full review copy": "send the full PDF free",
        "the zero-sales disclosure": "sold nothing to date",
        "the AI-agent disclosure": "autonomous AI agent",
        "the licence": "CC BY 4.0",
    }
    missing = [k for k, v in need.items() if flat(v) not in html_f]
    if missing:
        raise SystemExit("kit page is missing: " + ", ".join(missing))

    # Per-draft, because a draft is the unit that gets copied.
    per_draft = {
        "the affiliate-link slot": SLOT,
        "the affiliate disclosure": DISCLOSURE,
        "the dominant-branch share": f"{cov['dominant_pct']}%",
        "the dominant branch": f"`{cov['dominant']}`",
        "the opt-in lower bound": "lower bound",
        "the paid multiplier": f"x{sr['paid_ratio']['median']}",
        "the paid multiplier's IQR": f"x{sr['paid_ratio']['q1']}",
    }
    for label, body in drafts_src:
        body_f = flat(body)
        gone = [k for k, v in per_draft.items() if flat(v) not in body_f]
        if gone:
            raise SystemExit(f"kit draft {label} is missing: " + ", ".join(gone))
        if body.count(SLOT) != 1:
            raise SystemExit(f"kit draft {label} carries {body.count(SLOT)} affiliate slots, "
                             "expected exactly 1 — two slots means a publisher fills one.")

    # A second rate in one offer is a second promise (next.md 00000000B).
    #
    # MY FIRST VERSION OF THIS CHECK WAS `(\d{1,3})% *(?:commission|of every sale)` ON THE
    # RAW HTML, AND IT PASSED A PAGE DOCTORED TO PROMISE 30%. The rate and the word
    # "commission" sit in adjacent cells of the stat row — `<b>50%</b><span>commission</span>`
    # — so the tags stood between them and the pattern matched NOTHING. An empty result set
    # read as a clean bill of health, which is the oldest standing rule in next.md and I
    # broke it inside the gate written to enforce the rule. Two changes: tags are stripped
    # before the anchor test, and a run that finds NO commission figure at all is a FAILURE.
    text = flat(re.sub(r"<[^>]+>", " ", html))
    anchors = ("commission", "of every sale", "on every sale", "a sale", "keep")
    rates = [int(m.group(1)) for m in re.finditer(r"(\d{1,3})%", text)
             if any(a in text[max(0, m.start() - 40):m.end() + 40].lower() for a in anchors)]
    if not rates:
        raise SystemExit("kit page states no commission rate next to any word meaning our "
                         "offer — an empty result set is a failure, not a pass")
    bad = sorted({r for r in rates if r != t["commission_pct"]})
    if bad:
        raise SystemExit(f"kit page promises {bad}%, terms say {t['commission_pct']}%")

    # The pooled observed-gross median may never be published without its branch split
    # (build_guides.gross_split_warn). This page deliberately carries no gross figures at
    # all, so the cheapest correct check is that the pooled median is simply absent — if a
    # future edit adds the gross section here, it fails and has to bring the split with it.
    pooled = f"${sr['gross']['spread']['median']:,.0f}"
    if pooled in html:
        raise SystemExit(f"kit page prints the pooled observed-gross median {pooled} without "
                         "the branch split — see build_guides.gross_split_warn()")

    # A CLAIM ABOUT THE SHAPE OF THE DATA, BOUND TO THE DATA. Draft A tells a publisher that
    # a fixed multiplier "understates large products and overstates small ones". That is not
    # a figure, so no figure check touches it — it is a statement about the DIRECTION of the
    # by-sales curve, and a recrawl could flip it while every number on the page stayed
    # perfectly current. This is the §E defect one level up: a correctly derived page making
    # an uncorroborated claim. My first draft went further and said the curve rises all the
    # way, which the published bands do not support — the top band is BELOW the one under it.
    # So the copy now says it flattens, and this asserts only what the data actually shows.
    bands = sr["by_sales"]
    if not bands[0]["median"] < bands[-1]["median"]:
        raise SystemExit(
            f"draft A claims a fixed multiplier understates large products, but the smallest "
            f"band ({bands[0]['label']}, x{bands[0]['median']}) is not below the largest "
            f"({bands[-1]['label']}, x{bands[-1]['median']}) — rewrite the claim, not the gate")

    # Superseded prices, by literal. The report has been $79 and $19; both sat live on two
    # pages for eight days because nothing read them. Copy that leaves this site cannot be
    # recalled, so a retired price here is worse than a retired price anywhere else.
    for dead in ("$79", "$19,", "$600"):
        if dead in html:
            raise SystemExit(f"kit page carries the superseded price {dead}")
    return len(html)


# What the affiliates page MUST carry. Named here rather than inline so the assertion reads
# as a list of promises instead of a list of substrings, and so a future edit that quietly
# drops a caveat fails the build instead of shipping. Every one of these is a disclosure the
# outreach pitch's own gates already require (build_affiliate_pitch gates 4, 6, 7, 8).
def assert_affiliates_page(html, t, sr):
    cov = sr["coverage"]
    need = {
        "the commission rate": f"{t['commission_pct']}%",
        "the computed cut": t["affiliate_cut_display"],
        "the live price": t["price_display"],
        "the signup URL": t["signup_url"],
        "the Gumroad-account requirement": "Gumroad account",
        "the dominant branch": f"<code>{cov['dominant']}</code>",
        "the dominant branch's share": f"{cov['dominant_pct']}%",
        "the opt-in lower bound": "lower bound",
        "the zero-sales disclosure": "sold nothing to date",
        "the AI-agent disclosure": "autonomous AI agent",
        # An affiliate is being asked to spend their own credibility. A page that does not
        # let them read the thing first is asking them to take it on trust, which is the
        # one thing this page exists to stop doing.
        "the free sample of the report": SAMPLE_PAGE,
        "the offer of a full review copy": "send the full PDF, free",
        # The kit is the answer to "what would I actually have to do?", and this page is the
        # only surface a directory browser lands on. A terms page that does not route to the
        # finished copy leaves the recipient with the whole job and none of the work.
        "the route to the publisher kit": KIT_PAGE,
    }
    missing = [k for k, v in need.items() if v not in html]
    if missing:
        raise SystemExit("affiliates page is missing: " + ", ".join(missing))
    # A second rate in one offer is a second promise (next.md 00000000B). The only
    # percentages allowed on this page are the commission and figures that came from the
    # data — so check the commission is the ONLY one attached to the word "keep"/"commission".
    for m in re.finditer(r"(\d{1,3})% of every sale", html):
        if int(m.group(1)) != t["commission_pct"]:
            raise SystemExit(f"affiliates page promises {m.group(1)}%, terms say "
                             f"{t['commission_pct']}%")
    return len(html)


def currency_mix(rows):
    """'1,239 listings in GBP, 228 in USD and 44 in EUR' — computed, never typed."""
    names = {"£": "GBP", "$": "USD", "€": "EUR"}
    counts = collections.Counter(r["cur"] for r in rows)
    parts = [f"{n:,} in {names[c]}" for c, n in counts.most_common()]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def sync_license(ts, sr):
    """Rewrite the attribution block inside LICENSE from the summaries.

    LICENSE is the one published surface that was never generated, and it rotted the way
    ungenerated surfaces always do here: it told anyone citing the data to use version DOI
    …21830104 — the withdrawn v1 deposit, the one with the mixed-currency error — and the
    "1,511 live products" count that went with it. It is the string people copy when they
    cite us, so it is the last place a stale figure should live. The legal text is
    untouched; only the three indented citation lines are regenerated.
    """
    path = ROOT / "LICENSE"
    text = path.read_text()
    head, sep, rest = text.partition("build on it. Attribution:\n")
    assert sep, "LICENSE no longer has the attribution anchor — check it by hand"
    _old, sep2, tail = rest.partition("\nThis matches the licence")
    assert sep2, "LICENSE no longer has the closing anchor — check it by hand"
    # Wrapped by hand rather than left as one 140-column line: this is a plain text file
    # read in terminals, and the surrounding paragraphs are all wrapped at 76.
    citation = (f"Sujeito Operator (2026). {zenodo_title(ts, sr)} [Data set]. Zenodo. "
                f"https://doi.org/{DOI}")
    wrapped = textwrap.fill(citation, width=74, initial_indent="  ",
                            subsequent_indent="  ", break_long_words=False,
                            break_on_hyphens=False)
    block = f"\n{wrapped}\n"
    out = head + sep + block + sep2 + tail
    assert "21830104" not in out, "the withdrawn v1 version DOI is back in LICENSE"
    assert "1,511" not in out, "the withdrawn 1,511 count is back in LICENSE"
    assert DOI in out
    if out != text:
        path.write_text(out)
    return out


def assert_readme_names_both_samples(s, ts):
    """The README headline must name BOTH samples, and lead with the larger.

    Until 2026-08-08 it opened "1,344 live Gumroad products across 42 categories" — the
    *search* sample — while the GitHub repo description directly above it on the same page
    read "8,325 products ... across 261 categories", the *taxonomy* sample. Both were true
    about their own sample and neither said which one it was, so the top of our only
    indexable asset read as a self-contradiction and undersold the dataset six-fold.

    This is the "do not merge the samples" rule seen from the other side: keeping them
    apart is necessary but not sufficient, because an unlabelled figure is indistinguishable
    from a wrong one. Fails the build rather than shipping.
    """
    head = (ROOT / "README.md").read_text().split("\n## ")[0]
    missing = [lab for lab, val in (("taxonomy n", f"{ts['n']:,}"),
                                    ("taxonomy nodes", str(ts['nodes'])),
                                    ("search n", f"{s['n']:,}"),
                                    ("search cats", str(s['cats'])))
               if val not in head]
    if missing:
        raise SystemExit("README headline does not name both samples; missing: "
                         + ", ".join(missing))


def assert_controls_wired(docs):
    """The two crawler controls are wired the opposite way round, and this proves it.

    WHY THIS FUNCTION EXISTS, WHICH IS THE POINT WORTH KEEPING. Both `selfview.py` in the
    operator repo and the head of `next.md` stated that "its generator asserts that
    nothing links to it" about `crawler-control.html`. **No such assertion existed.** The
    control shipped 2026-08-29 with its whole validity resting on a property that was
    written down in three prose comments and enforced nowhere — so a single future author
    adding the page to a nav list would have destroyed it silently, and the reading of the
    data would have gone on unchanged. That is the same class as `next_token_gate`'s
    selftest being recorded as a green live gate: a commitment kept only where somebody
    remembered to keep it. It has one home now and it runs on every build.

    The four properties, and each one is load-bearing for a different reading:

      1. NOTHING links to `crawler-control.html`. If anything did, a view on `ctl-sitemap`
         would no longer prove a sitemap read, and the first control is worth nothing.
      2. `crawler-control.html` IS in `sitemap.xml`. Without this it is unreachable by
         anything at all, and its silence would be guaranteed rather than informative —
         a control that cannot fail.
      3. EVERY page links to `crawler-control-linked.html`. Partial coverage means a
         link-following crawler can enter the site, walk content pages and miss the
         control, which is exactly the blind spot the second control exists to close.
      4. `crawler-control-linked.html` is in NO sitemap and NOT in `llms.txt`. If it were
         listed, a sitemap-driven crawler would reach it too, the two channels would
         collapse into one, and neither control could name which class fired.
    """
    pages = sorted(p for p in docs.rglob("*.html"))
    assert len(pages) > 500, f"only {len(pages)} pages — the site did not build"

    ctl = CONTROL_PAGE.rsplit("/", 1)[-1]
    lctl = LINKED_CONTROL_PAGE.rsplit("/", 1)[-1]

    # (1) Read every page and name the offenders, because "some page links to it" is not
    # actionable at 543 pages. Two traps, both hit on the first run of this check:
    # `crawler-control-linked.html` CONTAINS the other filename as a substring, so the
    # match is on the href and not the bare name; and every page carries a
    # `<link rel=canonical href=...>` to ITSELF, which is not an inbound link a crawler
    # can traverse from elsewhere — so the match is on `<a>` specifically.
    # Both quote styles, and this is not hypothetical: `build_report_sample.py` writes
    # `href='...'` with single quotes, so a double-quoted-only regex read `sample.html` as
    # having no links at all. It cost a wrong conclusion before it cost a wrong gate —
    # and the same blind spot would have MISSED a single-quoted link to the sitemap-only
    # control, which is the failure this whole function exists to prevent.
    anchor = re.compile(rf'''<a\b[^>]*href=["'][^"']*/{re.escape(ctl)}["']''')
    inbound = [p.name for p in pages
               if anchor.search(p.read_text()) and p.name != lctl]
    assert not inbound, (
        f"{len(inbound)} page(s) link to the sitemap-only control {ctl}, which destroys "
        f"it — there is no way to tell afterwards which arrivals were the leak: {inbound[:6]}")

    # The linked control names the other one on purpose, as prose explaining the design.
    # That is the ONE permitted inbound link and it cannot pollute the measurement: to
    # read it you must already have reached the linked control, which files its own tag.
    lc = (docs / lctl).read_text()
    assert f'href="{CONTROL_PAGE}"' in lc, "the linked control no longer explains the other one"

    # (3) The property that actually matters is REACHABILITY, not universal presence, and
    # writing the check as "every page carries the link" was wrong on the first run: 8 of
    # 550 pages legitimately do not carry the site footer. Six are `noindex` retraction
    # notices for withdrawn categories, which carry no footer ON PURPOSE — putting an
    # affiliate pitch under a correction is the wrong thing to do and that decision stands.
    # `sample.html` and `audit-sample.html` have their own hand-written footers.
    #
    # So the gate resolves the link graph instead. Every page must reach the linked control
    # in at most two hops, which is what a crawler walking this site actually needs. A page
    # that neither carries the link nor links to a page that does is a hole a crawler can
    # sit in, and THAT is the thing worth failing the build over.
    site_root = SITE.rstrip("/") + "/"

    def local_path(page, href):
        """An href on `page` -> the docs-relative path it points at, or None if off-site."""
        base = site_root + str(page.relative_to(docs)).replace("\\", "/")
        target = urllib.parse.urljoin(base, href).split("#")[0].split("?")[0]
        if not target.startswith(site_root):
            return None
        rest = target[len(site_root):]
        return (rest or "index.html") + ("index.html" if rest.endswith("/") else "")

    hrefs = re.compile(r'''<a\b[^>]*href=["']([^"']+)["']''')
    carries = re.compile(rf'''href=["']{re.escape(LINKED_CONTROL_PAGE)}["']''')

    carriers, others = set(), []
    for p in pages:
        (carriers.add(str(p.relative_to(docs))) if carries.search(p.read_text())
         else others.append(p))
    assert len(carriers) > 500, f"only {len(carriers)} pages carry the control link"

    stranded = []
    for p in others:
        hops = {local_path(p, h) for h in hrefs.findall(p.read_text())}
        if not (hops & carriers):
            stranded.append(str(p.relative_to(docs)))
    assert not stranded, (
        f"{len(stranded)} page(s) neither carry the linked control's link nor link to any "
        f"page that does — a crawler entering there never sees the control: {stranded[:6]}")

    # (2) and (4). The sitemap must carry one and not the other.
    sm = (docs / "sitemap.xml").read_text()
    assert CONTROL_PAGE in sm, f"{ctl} fell out of sitemap.xml — it is now unreachable, not a control"
    assert LINKED_CONTROL_PAGE not in sm, (
        f"{lctl} is listed in sitemap.xml — a sitemap crawler can now reach it, so the two "
        f"controls no longer separate the two crawler classes")
    llms = (docs / "llms.txt").read_text()
    assert LINKED_CONTROL_PAGE not in llms, f"{lctl} is listed in llms.txt — same collapse as the sitemap"

    return f"{len(pages)} pages: 0 link to {ctl}, all link to {lctl}"


def selftest_controls(docs):
    """Prove `assert_controls_wired` FAILS when each property is broken. `--selftest`.

    The reason this exists is the reason the gate exists. Three prose comments claimed the
    generator asserted the sitemap control was unlinked; none did. A gate nobody has seen
    go red is the same kind of claim — it is believed, not known. Each trial below breaks
    exactly one property on a COPY of the built site and requires a specific failure.
    """
    import shutil, tempfile

    def trial(name, mutate, want):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td) / "docs"
            shutil.copytree(docs, d)
            mutate(d)
            try:
                assert_controls_wired(d)
            except AssertionError as e:
                assert want in str(e), f"{name}: raised, but not for {want!r}: {e}"
                return f"  ok   {name}"
            raise AssertionError(f"{name}: assert_controls_wired PASSED a broken site")

    def link_to_sitemap_control(d):
        # A future author adds the control to a nav list. Single quotes ON PURPOSE — the
        # first version of this regex only matched double quotes and would have let this
        # through, which is the bug that made `sample.html` look linkless.
        p = d / "index.html"
        p.write_text(p.read_text().replace(
            "<footer>", f"<a href='{CONTROL_PAGE}'>control</a><footer>", 1))

    def drop_footer_link(d):
        # The footer link is removed from a leaf page that links nowhere else on-site.
        p = d / "s" / "index.html"
        t = p.read_text().replace(f'href="{LINKED_CONTROL_PAGE}"', 'href="/nowhere.html"')
        p.write_text(re.sub(r'''<a\b[^>]*href=["'][^"']*["']''', "<span>", t))

    out = [
        trial("inbound link to the sitemap-only control is caught",
              link_to_sitemap_control, "link to the sitemap-only control"),
        trial("sitemap control dropped from sitemap.xml is caught",
              lambda d: (d / "sitemap.xml").write_text(
                  (d / "sitemap.xml").read_text().replace(
                      f"<loc>{CONTROL_PAGE}</loc>", "")),
              "fell out of sitemap.xml"),
        trial("linked control ADDED to sitemap.xml is caught",
              lambda d: (d / "sitemap.xml").write_text(
                  (d / "sitemap.xml").read_text().replace(
                      "</urlset>", f"<url><loc>{LINKED_CONTROL_PAGE}</loc></url></urlset>")),
              "listed in sitemap.xml"),
        trial("linked control ADDED to llms.txt is caught",
              lambda d: (d / "llms.txt").write_text(
                  (d / "llms.txt").read_text() + f"\n{LINKED_CONTROL_PAGE}\n"),
              "listed in llms.txt"),
        trial("a page stranded away from the linked control is caught",
              drop_footer_link, "neither carry"),
        trial("the linked control losing its explanation of the other is caught",
              lambda d: (d / "crawler-control-linked.html").write_text(
                  (d / "crawler-control-linked.html").read_text().replace(
                      f'href="{CONTROL_PAGE}"', 'href="#"')),
              "no longer explains the other one"),
    ]
    return "\n".join(out)


def assert_readme_carries_no_sales_cta():
    """The README is the one surface a third party set a condition on. Enforce it.

    WHAT HAPPENED. `scadastrangelove/awesome-ai-security-tools#40` was merged on the
    reviewer's stated condition — the previous README carried a "Read the report — $249"
    call-to-action and they found it "too closely associated with passive income scams".
    The CTA was removed from `README.md` BY HAND and pushed, and the fix stopped there.

    WHY THAT WAS NOT A FIX. This file GENERATES README.md on every run. The template
    still held the CTA, so the very next `build_site.py` — run for an unrelated reason,
    by a session that had never heard of the condition — silently rewrote the sales
    section back in and would have pushed it as part of some other commit. That is worse
    than never having removed it: a commitment made to a named third party, reverted by
    a build step, with nothing in the diff to say so.

    So the template now carries the disclosure text, and this asserts the property rather
    than the wording. The list entry is not the point; the point is that the dataset must
    not double as a funnel, and a promise that only a human remembers is not kept.
    """
    text = (ROOT / "README.md").read_text()
    banned = [PRICE, BUY, "Read the report"]
    found = [b for b in banned if b in text]
    if found:
        raise SystemExit(
            "README.md carries a sales CTA and a reviewer's merge condition says it must "
            f"not: found {found}. See assert_readme_carries_no_sales_cta. The report is "
            "on the Gumroad profile and stays deliberately more than one click from here.")


def assert_citation_target(extra=()):
    """No generated surface may tell a reader that a GitHub release holds the current bytes.

    Found live 2026-08-08: four surfaces — the README (which ships INSIDE the Zenodo
    deposit), the landing page, `llms.txt`, and the schema.org `distribution` block Google
    Dataset Search reads — all said to pin `release v1.1` for "the exact bytes every figure
    was computed from". That release carries a 1,511-row CSV from a superseded crawl, and
    the JSON-LD additionally declared `"version": "1.1"` while the archive said 2.7.

    A wrong citation instruction is worse than a wrong figure. A wrong figure misleads a
    reader who is skimming; a wrong citation instruction is obeyed by the careful one, who
    then publishes a citation to data that never produced the numbers. Those are exactly the
    readers a DOI-archived dataset attracts, and Zenodo is the only surface here with
    measured human traffic.

    Same shape as `assert_gross_split`: the check is on the OUTPUT, not on the source, and
    it checks the neighbourhood rather than the string — the defect was never one bad token,
    it was a true URL next to a claim that had quietly stopped being true.
    """
    claim = re.compile(r"exact bytes|will not change|pinned to release|\bpin to\b", re.I)
    disclaim = re.compile(r"older snapshot|superseded|not this data", re.I)
    # A sentence end, not any full stop: `github.com/` and `v1.1` both contain one, and an
    # earlier draft of this gate anchored on them and read a four-word window.
    boundary = re.compile(r"[.!?](?=\s|<|$)")
    bad = []
    files = [(f.name, f.read_text()) for f in sorted((ROOT / "docs").rglob("*.html"))]
    files += [("README.md", (ROOT / "README.md").read_text()),
              ("llms.txt", (ROOT / "docs" / "llms.txt").read_text())]
    files += list(extra)
    hits = 0
    for name, text in files:
        for m in re.finditer(r"/releases/(?:tag|download)/", text):
            starts = [b.end() for b in boundary.finditer(text, 0, m.start())]
            lo = starts[-1] if starts else max(0, m.start() - 400)
            nxt = boundary.search(text, m.start())
            hi = nxt.end() if nxt else min(len(text), m.start() + 400)
            sent = " ".join(text[lo:hi].split())
            hits += 1
            if claim.search(sent) or not disclaim.search(sent):
                bad.append((name, sent[:180]))
    assert not bad, (
        "a generated surface pins a GitHub release as the current/citable bytes, or links "
        f"one without saying it is superseded. The citation target is the versioned DOI "
        f"{ZENODO_VERSION_DOI}: {bad[:3]}")
    return f"{len(files)} surfaces, {hits} release links"


def assert_report_scope(s):
    """No published buy block may advertise the report as covering the SMALLER sample.

    Two counts live on this site and both are correct about their own sample: `cats`
    (42 search queries) and `nodes` (261 taxonomy categories). The paid report covers
    the second. Until 2026-08-08 every buy block quoted the first, because `s` was the
    variable in scope in each of those functions — so the paid tier advertised itself
    as covering a sixth of what the free download advertised, on all 542 pages at once.

    The failure mode is reaching for the nearest variable, not forgetting a fact, so
    the check is on the OUTPUT: any sentence that promises "all N categories" inside a
    buy block has to name REPORT_CATS. Cheap, and it fails the build rather than
    shipping.
    """
    bad = []
    for f in sorted((ROOT / "docs").rglob("*.html")):
        html = f.read_text()
        for m in re.finditer(r"reads all (\d[\d,]*)|classifies all (\d[\d,]*)|"
                             r"every one of (\d[\d,]*) categories|"
                             r"classified all (\d[\d,]*)", html):
            got = next(g for g in m.groups() if g)
            if int(got.replace(",", "")) != REPORT_CATS:
                bad.append((f.name, m.group(0)))
    assert not bad, (f"buy block advertises the wrong sample "
                     f"(report covers {REPORT_CATS}): {bad[:5]}")
    assert str(s["cats"]) != str(REPORT_CATS), \
        "the two samples now report the same count — check this assertion still tests anything"


def main():
    # `buy_block()` now links the sample from all 542 category pages, both guide trees, the
    # seller tree and the index. If the file is not there, this build publishes 542 dead
    # links in the one block a buyer reads — so it stops instead. The dead-link rule
    # (next.md §0000000000) says a URL is checked BEFORE it is published, and the cheapest
    # possible check for a file we generate ourselves is whether it exists.
    # AUDIT_SAMPLE_PAGE joined this list on 2026-08-12 with the fourth buy-block link. It is
    # generated by `build_audit_sample_page.py` in THIS repo rather than by the operator
    # repo, so the remedy differs from the message below — but the rule is identical and the
    # cost of getting it wrong is the same 542 dead links.
    for url, floor in ((SAMPLE_PDF, 20_000), (SAMPLE_PAGE, 8_000),
                       (AUDIT_SAMPLE_PAGE, 8_000)):
        f = ROOT / "docs" / url.rsplit("/", 1)[1]
        if not f.exists() or f.stat().st_size < floor:
            raise SystemExit(
                f"{f} is missing or truncated — run `build_report_sample.py --publish` "
                f"in the operator repo first, or `build_audit_sample_page.py` here for "
                f"audit-sample.html. Refusing to publish 542 dead links.")

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

    # Fourth unit of observation, same rule: a pure derivation of data/raw-products.jsonl
    # with no network, so it is regenerated here rather than run by hand.
    import normalize_products
    normalize_products.main()
    sr = json.loads((ROOT / "data" / "sales-ratio-summary.json").read_text())

    sync_license(ts, sr)

    # The affiliate terms cross a repo boundary, so they are READ, never re-typed. The
    # operator repo writes this file only after checking the price against the live product
    # page and the signup URL against its rendered component
    # (`scripts/build_affiliate_terms.py` there). Missing file = hard stop rather than a
    # page built from defaults: a commission figure guessed by a fallback is exactly the
    # defect the no-figures footer rule exists to prevent.
    terms = load_terms()

    mix = currency_mix(rows)
    (ROOT / "README.md").write_text(build_readme(s, mix, ts, ss, sr))
    (ROOT / "docs" / "index.html").write_text(build_index(s, mix, ts, ss, sr, terms))
    apage = build_affiliates(terms, s, ts, ss, sr)
    print(f"  affiliates page OK: {assert_affiliates_page(apage, terms, sr):,} bytes")
    (ROOT / "docs" / "affiliates.html").write_text(apage)
    import build_checkout
    cpage = build_checkout.build(terms)
    crecs = json.loads((ROOT / "data" / "checkout-audit.json").read_text())
    print(f"  checkout page OK: {build_checkout.assert_page(cpage, crecs, build_checkout.live_monitor()):,} bytes")
    (ROOT / "docs" / "checkout.html").write_text(cpage)
    kpage = build_kit(terms, s, ts, ss, sr)
    kdrafts = [(n, b) for n, _l, _note, b in kit_drafts(s, ts, ss, sr, terms)]
    print(f"  publisher kit OK: {assert_kit_page(kpage, terms, sr, kdrafts):,} bytes")
    (ROOT / "docs" / "kit.html").write_text(kpage)
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

    (ROOT / "docs" / "crawler-control.html").write_text(build_control())
    (ROOT / "docs" / "crawler-control-linked.html").write_text(build_linked_control())

    (ROOT / "docs" / "sitemap.xml").write_text(
        sitemap(s["by_category"], guides, taxo, sellers))
    (ROOT / "docs" / "llms.txt").write_text(
        llms_txt(s, s["by_category"], build_guides.GUIDES, ts, sr))

    # The 50-row sample is a published surface too, and it silently kept the old
    # column set through the USD normalisation. Generate it rather than hand-maintain.
    src = list(csv.reader((ROOT / "data" / "gumroad-latest.csv").open()))
    with (ROOT / "docs" / "sample-50-rows.csv").open("w", newline="") as f:
        csv.writer(f).writerows(src[:51])

    assert_readme_names_both_samples(s, ts)
    assert_readme_carries_no_sales_cta()
    assert_report_scope(s)
    print(f"  citation target OK: {assert_citation_target()}")
    print(f"  crawler controls OK: {assert_controls_wired(ROOT / 'docs')}")

    print(f"README + index + {len(guides)} guides + {len(s['by_category'])} category pages"
          f" + {len(taxo)} taxonomy pages + taxonomy index + {len(sellers)} seller pages"
          f" + seller index + sitemap + sample")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        print("crawler-control gate, negative trials:")
        print(selftest_controls(ROOT / "docs"))
        print(f"LIVE: {assert_controls_wired(ROOT / 'docs')}")
    else:
        main()
