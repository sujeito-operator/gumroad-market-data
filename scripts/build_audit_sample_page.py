#!/usr/bin/env python3
"""/audit-sample.html — a worked, redacted sample of the storefront audit report.

WHY THIS PAGE EXISTS. The storefront audit is the product two cold batches sell on
2026-08-13, and before this page a buyer could not see one line of what they would
receive. `/sample.html`, `/sample-50-rows.csv` and the sample PDF all belong to the
written report; the audit had nothing. The ask was "pay for a report" and the answer to
"what does it look like" was on no page any outreach linked.

THE SOURCE IS `data/audit-sample-2026-08-12.md` AND THIS GENERATOR DOES NOT COMPUTE
ANYTHING. Every figure on the page comes out of that file, which is the redacted output of
an actual run against an actual storefront — nine products, walked logged out from a UK
address on 2026-08-12. The redaction is in the operator repo (`build_audit_sample.py`) and
removes the seller: their slug, their product titles and their permalinks. It removes no
number. If this generator ever starts deriving a figure of its own, the page and the
report it advertises can disagree, which is the failure `build_checkout.py` documents at
length for the same reason.

THIS PAGE CARRIED NO PRICE UNTIL 2026-08-22, AND THE REASON WAS ONLY EVER HALF RIGHT.
The reason recorded here was: "a number typed here would be a 542nd surface to keep in
sync, and a stale price on a published surface is the defect this operation has shipped
more often than any other." That is true of a TYPED number and it is still the rule.

What it was used to justify was showing nothing, and the cost of that was never written
down: this page is the worked sample of a paid deliverable, it is linked from ~540 pages,
its reader has self-selected as the buyer — and it could not tell them what the thing
costs, while ~540 pages of the same site priced the written report from a typed literal.
Every figure below now comes out of
`live_price.price()`, which reads the live Gumroad product anonymously at build time and
refuses to invent one, so no number is typed and the rule above is not weakened. The
second half of that guarantee is `sku_price_gate.py` in the operator repo, which compares
the PUBLISHED bytes of this page against the LIVE Gumroad price every session — because a
built page is a snapshot and a snapshot can go stale even when nobody typed anything.
`assert_page` refuses any figure in the call to action that is not the live reading.
"""
import html
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_site as B                                  # noqa: E402
import live_price                                       # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "audit-sample-2026-08-12.md"
OUT = ROOT / "docs" / "audit-sample.html"
PAGE = f"{B.SITE}/audit-sample.html"
PRODUCT = "https://sujeitooperator.gumroad.com/l/xlvfeb"
# THE RECURRING VERSION OF THE SAME WALK, ADDED 2026-08-13, AND IT CARRIES NO PRICE EITHER
# — for exactly the reason the docstring above gives, which applies to it unchanged. It is
# on this page and not on the 542-page buy block because this is the one page whose reader
# has already self-selected as a Gumroad seller looking at their own checkout, and because
# the thing it offers IS the document above, re-run: the monitor's first month is this
# report. Naming it here is not an upsell bolted on, it is the honest second half of the
# sentence "yours is run the day the order lands" — after which, without this, nothing
# happens again ever. On 2026-08-13 the recurring SKU was published and named on no owned
# surface at all, while three one-off offers were named on several.
MONITOR = "https://sujeitooperator.gumroad.com/l/zyoqbc"

TITLE = ("A worked sample of the Gumroad storefront audit — nine products, "
         "every checkout read at the pay step")
DESC = ("The full report a buyer receives, run against one real Gumroad storefront and "
        "redacted. What each product's page advertises, what the checkout actually "
        "charges a UK buyer, and where each price sits against comparable products in "
        "the same category. Every figure is the figure that was measured.")


def cta(audit, monitor):
    """The call to action, with both figures read live and neither of them typed.

    A function rather than a module constant because the figures come off the network:
    a constant would make importing this module — for a selftest, for the sitemap — a
    Gumroad request, and an import that touches the network is an import that fails on
    the day the network does.

    ONLY THE AUDIT'S FIGURE GOES HERE, AND THE MONITOR'S DELIBERATELY DOES NOT. Both were
    on this page for about twenty minutes on 2026-08-22 and then the monitor's came off.
    `build_affiliate_pitch.audit_sample_live()` links this page as EVIDENCE from nine cold
    batches that have just asked for the audit's price, and the monitor is cheaper per
    month than the audit is once. That may well be the right ladder —
    `gumroad_monitor_sku.py` argued on 2026-08-13 that the recurring product should be the
    easier way in — but it is a PRICING decision about what nine live letters are worth,
    and it is not one to make as a side effect of a funnel change. The monitor is still
    priced, visibly and with its Product markup, on `checkout.html`, which is its canonical
    page and which `price_sweep.py` already sweeps. See next.md §QP-10.
    """
    return f"""<div class=buy><strong>This is the report, not a summary of it.</strong><br>
The page above is one storefront's audit end to end &mdash; the same document a buyer receives,
with the seller's name and product titles removed and not one figure altered. Yours names
your products, walks every product on your storefront, and is run the day the order lands.
<a href="{PRODUCT}">Order the audit &mdash; {audit['display']}, once &rarr;</a>
<a class=alt href="{MONITOR}">Or have it watched: the same walk every week, and an email the day
a price stops matching the pay step &rarr;</a>
<span class=fine>The watched version is a monthly subscription and its first month is this
report, included rather than added on; after that the walk repeats weekly and you hear from me
when a gap opens, closes or moves. It states its own price on its own page. The number moves on
its own &mdash; it is a function of the day's
exchange rate, the buyer's country, Gumroad's tax handling and your own edits &mdash; so a report is
true on the day it is written and the watching is what keeps it true. The figure above was read
off the Gumroad product page when this page was built ({audit['read_at']}); that page is
where you pay and it is the authority if it ever disagrees with this one.
Prefer to look at the underlying data first? The category crawl behind
the price comparison is <a href="{B.SITE}/">free and openly licensed</a>.</span></div>"""


OWN_GLOB = "own-store-checkout-*.json"

# The date the "every gap below is VAT" sentence came off this page. Named in the copy so
# a reader who saw the old wording is told it changed, rather than finding it quietly gone.
CORRECTED_ON = "2026-08-26"

# The third-party walk this same page renders above, re-read for the residual. Recomputed
# here rather than quoted from any summary — a generator that renders a figure another
# tool wrote will publish that tool's bug (§WO-0d).
TP_SRC = "checkout-audit.json"


def _money(line):
    """-> the float out of a rendered checkout line like 'Subtotal £184.76'."""
    m = re.search(r"([\d,]+\.\d{2})", line or "")
    if not m:
        raise SystemExit(f"cannot read a figure out of {line!r}")
    return float(m.group(1).replace(",", ""))


def _subtotal(r):
    return _money(r["subtotal_line"])


def _residual(r):
    """-> the part of the difference that is NOT the tax line, for one walked row."""
    return round(_subtotal(r) - r["advertised"], 2)


def third_party_residual():
    """-> (n_comparable, median_pct, min_pct, max_pct, n_negative) or None.

    Zero-priced pages are EXCLUDED (no percentage is definable) and every remaining row
    is counted, so "all N" below is a real all and not a survivor's N.
    """
    import json
    p = ROOT / "data" / TP_SRC
    if not p.exists():
        return None
    pcts, neg = [], 0
    for r in json.loads(p.read_text()):
        c = r.get("checkout") or {}
        sub, pp = c.get("subtotal"), r.get("page_price")
        if not (sub and pp and pp[1]):
            continue
        res = round(sub[1] - pp[1], 2)
        if abs(res) < 0.01:
            continue
        pcts.append(round(100 * res / pp[1], 1))
        if res < 0:
            neg += 1
    if not pcts:
        return None
    pcts.sort()
    mid = (pcts[len(pcts) // 2] if len(pcts) % 2
           else round((pcts[len(pcts) // 2 - 1] + pcts[len(pcts) // 2]) / 2, 2))
    return (len(pcts), mid, min(pcts), max(pcts), neg)


def own_store_data():
    """The newest first-party walk of OUR OWN store, or None if none is published.

    Globbed rather than pinned to a date, for the reason `pilot_terms_evidence.SCAN_JSON`
    taught: a pinned filename goes stale silently and puts two different measurements on
    one site. Returns None when the file is absent, and `own_store()` then renders NOTHING
    — the section is evidence or it is not there. A placeholder that says "coming soon"
    on a page whose entire argument is "every figure here was measured" is worse than a
    shorter page.
    """
    import json
    files = sorted((ROOT / "data").glob(OWN_GLOB))
    if not files:
        return None
    return json.loads(files[-1].read_text())


PAGECHECK = "https://sujeitooperator.gumroad.com/l/xmzlkz"


def own_store(d, pagecheck=None):
    """"Don't take the redacted sample's word for it — here is my own shop."

    THE WEAKNESS THIS FIXES. Everything above this block is somebody else's storefront
    with the seller removed. That redaction is right and it is not negotiable, and it
    costs the reader the ability to check a single number: they must trust a stranger
    about a shop they cannot look at. Our own store has the opposite property. It is
    public, it is already named on this page, and the reader can reproduce every row
    below in their own browser in under a minute — which is the strongest form the same
    claim can take, and it was sitting unused.

    WHAT IS AND IS NOT CLAIMED. Most of every gap below is a named VAT line, and VAT is
    lawful: Gumroad is the merchant of record and is required to add it. This block says
    so in its own copy, above the table, because a page that let the reader infer
    wrongdoing would be selling on a misunderstanding. The claim is the one the audit
    actually makes — that the seller cannot SEE it from inside their own account — and our
    own store is the proof precisely BECAUSE nothing is wrong with it.

    CORRECTED 2026-08-26 (§WQ). THIS BLOCK SHIPPED SAYING "EVERY GAP BELOW IS VAT" AND
    THAT WAS FALSE, in the flattering direction, on a page that tells the reader to go and
    check. The gap on `bylafq` is £38.63 and the VAT line is £37.04. The missing £1.59 is
    a RESIDUAL: the checkout's own subtotal (£184.76) is not the advertised page figure
    (£183.17), before a penny of tax. It is true of all three compared rows here, and of
    ALL 32 non-zero-priced third-party pages in `checkout-audit.json`, median 0.95% and
    ranging from -28.4% to +49.2%. The old copy was checkable and wrong; a reader who
    added up the column would have caught it. The table now carries the subtotal so the
    decomposition is visible, and `own_store_defects()` asserts
    advertised + residual + tax == charged for every row rather than trusting the file.
    """
    if not d or not d.get("rows"):
        return ""
    tp = third_party_residual()
    if not tp:
        raise SystemExit(
            f"{TP_SRC} is missing or carries no comparable row, and this block's "
            f"correction quotes it. Refusing to publish a corrected claim with nothing "
            f"behind it — the old claim was wrong because nobody checked the data that "
            f"was already here.")
    TP_N, TP_MED, TP_MIN, TP_MAX, TP_NEG = tp
    rows = "".join(
        f"<tr><td>{html.escape(r['product'][:70])}</td>"
        f"<td>{html.escape(r['currency'])}{r['advertised']:.2f}</td>"
        f"<td>{html.escape(r['currency'])}{_subtotal(r):.2f}</td>"
        f"<td>{html.escape(r['tax_line'] or '—')}</td>"
        f"<td>{html.escape(r['currency'])}{r['charged']:.2f}</td>"
        f"<td>+{html.escape(r['currency'])}{r['gap']:.2f} ({r['gap_pct']:.1f}%)</td>"
        f"<td>+{html.escape(r['currency'])}{_residual(r):.2f}</td></tr>"
        for r in d["rows"])
    biggest = d["rows"][0]
    return f"""<h2>And here is the same walk against my own storefront, unredacted</h2>
<div class=lede><p>Everything above is somebody else's shop with the seller removed. You
have to take my word for it. So here is the measurement run against <em>my</em> store,
which is public, which is linked from this page, and which you can check yourself right
now &mdash; open any product below in a private window and click through to the pay
step.</p>
<p><strong>Most of every gap below is VAT, and VAT is lawful.</strong> Gumroad is the
merchant of record and is required to add it. That is exactly the point: there is nothing
wrong with my checkout, and I still cannot see these numbers from inside my own account.
My dashboard reports in my currency, and my own visits are localised to where I am.
Neither shows me what the row below shows.</p>
<p><strong>The gap does not reduce to the tax line, and the last column is the part that
does not.</strong> On the largest row the difference is
{html.escape(biggest['currency'])}{biggest['gap']:.2f} and the VAT line is
{html.escape(biggest['tax_line'] or '—')} &mdash; the remainder is
{html.escape(biggest['currency'])}{_residual(biggest):.2f}, because the checkout's own
subtotal ({html.escape(biggest['currency'])}{_subtotal(biggest):.2f}) is not the figure the
page advertises ({html.escape(biggest['currency'])}{biggest['advertised']:.2f}), before a
penny of tax. This page said &ldquo;every gap below is VAT&rdquo; until {CORRECTED_ON} and
that was wrong in the direction that flattered me. It is a small residual here. It is not
always small: across the {TP_N} other people&rsquo;s pages in the walk above that carry a
non-zero price, <em>all</em> {TP_N} show one, median {TP_MED}%, ranging from {TP_MIN}% to
{TP_MAX}%, and {TP_NEG} of them negative.</p></div>
<table><thead><tr><th>Product</th><th>Page says</th><th>Checkout subtotal</th>
<th>Tax line</th><th>Pay step charges</th><th>Difference</th>
<th>Not explained by tax</th></tr></thead><tbody>{rows}</tbody></table>
<p class=fine>{d['products_walked']} published products walked logged out from
{html.escape(d['walked_from'])} on {d['measured_on']}; {d['products_compared']} are
comparable and {d['excluded']} are excluded ({html.escape(d['excluded_reason'])}). The
largest gap is {html.escape(biggest['currency'])}{biggest['gap']:.2f} on a product whose
page advertises {html.escape(biggest['currency'])}{biggest['advertised']:.2f}. Nothing was
ordered and no form was submitted; every reading stops at the pay step. The walk is the
same instrument that produces the report above, pointed at my own shop instead of a
customer's.</p>""" + (f"""
<div class=buy><strong>That is one page, walked. Want the same reading on one of
yours?</strong><br>
Send me one Gumroad product URL and I walk it logged out from a UK address to the real pay
step, then write back what your page advertises, what the checkout&rsquo;s own subtotal is
before tax, what the tax line is, what you are actually charged, and which part of the
difference is <em>not</em> tax &mdash; the last column above, on your product instead of
mine.
<a href="{PAGECHECK}">One page, walked &mdash; {pagecheck['display']}, once &rarr;</a>
<span class=fine>This is the cheap way in, and it is deliberately narrower than the audit:
one product page, not your storefront. You are buying the reading and not a finding &mdash;
there is nothing wrong with my checkout, there is probably nothing wrong with yours, and a
clean, fully-explained answer is a likely outcome and is what you would be paying to know.
I answer within 24 hours. Refund on request within 30 days, including if you decide
afterwards that a clean answer was not worth it. The figure was read off the Gumroad
product page when this page was built ({pagecheck['read_at']}); that page is where you pay
and it is the authority if it ever disagrees with this one.</span></div>"""
        if pagecheck else "")


# ---------------------------------------------------------------- markdown, the subset
INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"`(.+?)`"), r"<code>\1</code>"),
    (re.compile(r"(?<![\"=])\bhttps://\S+"), lambda m: f'<a href="{m.group(0)}">'
                                                       f"{m.group(0)}</a>"),
]


def inline(s):
    s = html.escape(s, quote=False)
    for pat, rep in INLINE:
        s = pat.sub(rep, s)
    return s


def render(md):
    """The subset the report actually uses: headings, quotes, tables, lists, paragraphs."""
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("#"):
            n = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{n}>{inline(ln[n:].strip())}</h{n}>")
            i += 1
        elif ln.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i].lstrip(">").strip())
                i += 1
            # A blank quoted line is a paragraph break inside the quote. Each paragraph is
            # joined into ONE string before `inline` runs: the source wraps at 78 columns
            # and `**...**` spans line breaks, so marking up line by line leaves literal
            # asterisks on the page — which is what the first render of this page did.
            paras, cur = [], []
            for q in block:
                if q.strip():
                    cur.append(q.strip())
                elif cur:
                    paras.append(" ".join(cur))
                    cur = []
            if cur:
                paras.append(" ".join(cur))
            out.append("<div class=lede>"
                       + "".join(f"<p>{inline(p)}</p>" for p in paras) + "</div>")
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            head = rows[0]
            body = [r for r in rows[1:] if not set("".join(r)) <= set("-: ")]
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            tb = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                         for r in body)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>")
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(
                    r"[#>|]|- ", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


def build():
    md = SRC.read_text()
    body = render(md)
    audit = live_price.price(PRODUCT.rsplit("/", 1)[1])
    monitor = live_price.price(MONITOR.rsplit("/", 1)[1])
    block = cta(audit, monitor)
    # THE PRODUCT MARKUP FOR THE AUDIT IS DECLARED HERE AND ON NO OTHER PAGE. `build_site`
    # states the convention for the report ("declared once, on the page that describes it")
    # and this is that page for the audit: the whole visible page is one worked instance of
    # exactly what the Offer sells. The MONITOR is priced in the call to action above but
    # is NOT marked up here — its Product block lives on `checkout.html`, the page about
    # the thing it watches. Two Product blocks for one SKU is two things to keep true.
    extra = ('<script type="application/ld+json">\n'
             + live_price.product_jsonld(
                 audit, name="Gumroad storefront checkout audit",
                 description=(
                     "Every product on one Gumroad storefront loaded logged out from "
                     "London, each followed through to its own checkout, and the page "
                     "figure, subtotal, tax line, total and gap reported per product — "
                     "the number a seller cannot read from inside their own account. "
                     "A complete worked sample, redacted, is published on this page."))
             + "\n</script>\n")
    # The CTA goes after the first table — a reader who has seen the checkout half has seen
    # enough to decide, and one who has not should not be asked yet.
    # The entry rung is priced LIVE like every other figure on this page. If Gumroad
    # cannot be read and there is no cached reading, `live_price.price` raises and the
    # build stops — an offer block with no price is worse than no offer block.
    pagecheck = live_price.price(PAGECHECK.rsplit("/", 1)[1])
    own = own_store(own_store_data(), pagecheck)
    # The own-store block goes AFTER the ask, not before it. The reader has just been
    # asked to pay a stranger for a measurement; "here is that measurement on my own
    # public shop, go and reproduce it" answers the objection at the moment it arrives.
    cut = body.index("</table>") + len("</table>")
    doc = (B.head(TITLE, DESC, PAGE, extra)
           + body[:cut] + block + own + body[cut:]
           + f"""<nav class=sib><a href="{B.SITE}/checkout.html">How widespread this is
across 32 stores</a> &middot; <a href="{B.SITE}/">The free dataset</a></nav>
<footer>Walked and published 2026-08-12 by the operator of
<a href="{B.SITE}/">gumroad-market-data</a>. Nothing was ordered and no form was
submitted; every reading stops at the pay step.</footer></main></body></html>""")
    assert_page(doc, md, audit, monitor, pagecheck)
    OUT.write_text(doc)
    return doc


def assert_page(doc, md, audit, monitor, pagecheck=None):
    """The page may not name the seller, may not lose a figure, may not TYPE a price.

    Until 2026-08-22 the second clause was "may not state a price". It is now "may not
    state a price it did not read live", which is a different and stronger check: the old
    one was satisfied by a page that said nothing, and a page that says nothing is exactly
    what this file spent ten days publishing.
    """
    problems = []
    # 1. THE SELLER. The redaction happens upstream; this asserts it arrived intact rather
    #    than trusting it, because the cost of being wrong is publishing a named third
    #    party's pricing as our advertisement.
    for leak in ("rocketlasso", "RKT", "Cinema 4D", "gumroad.com/l/slicer"):
        if leak.lower() in doc.lower():
            problems.append(f"the seller leaked through: {leak!r} is on the page")
    # 2. THE PRICE. See the module docstring — every figure in the ask is read live.
    #
    #    The literal list below is NOT the check. It is a tripwire for the specific way
    #    this goes wrong: somebody with a red gate and five minutes hardcodes the number
    #    into the source. It stays even though the arm underneath it is stronger, because
    #    the arm underneath compares against a LIVE read, and a live read is exactly what
    #    is unavailable on the day somebody reaches for a literal.
    src = pathlib.Path(__file__).read_text().split("def assert_page")[0]
    for typed in ("$149", "$129", "$249", "$99", "$69"):
        if typed in src:
            problems.append(f"a price is typed into this generator: {typed}")
    if True:
        # Every dollar figure in the ask must be one of the two live readings. The report
        # above the ask is full of measured peer prices and they are not touched — the
        # split is on `<div class=buy>`, which is where the page stops describing and
        # starts selling.
        ask = doc.split("<div class=buy>", 1)[1].split("</div>", 1)[0] if \
            "<div class=buy>" in doc else ""
        # The monitor's figure is NOT allowed here — see `cta`'s docstring and §QP-10.
        allowed = {audit["display"]}
        for fig in set(re.findall(r"\$\d+(?:,\d{3})*(?:\.\d+)?", ask)):
            if fig not in allowed:
                problems.append(
                    f"the call to action shows {fig}, which is not a live reading "
                    f"(live: {sorted(allowed)}) — a figure in an ask must come from "
                    f"live_price.price() and from nowhere else")
        if audit["display"] not in ask:
            problems.append(f"the audit price {audit['display']} was read live and did "
                            f"not reach the call to action")
        if monitor["display"] in ask:
            problems.append(
                f"the monitor's {monitor['display']} is in the ask. This page is linked as "
                f"EVIDENCE by nine cold batches that have just quoted the audit's price, and "
                f"a cheaper recurring figure here is a pricing decision, not a page edit. "
                f"It belongs on checkout.html. See §QP-10.")
        # The markup and the visible text must agree, because Google's policy is that
        # marked-up content is visible content — and because a Product block that
        # disagrees with the page it sits on is worse than no Product block.
        if f'"price": "{audit["usd"]}"' not in doc:
            problems.append("the Product markup does not carry the live audit price")
        if audit["display"] not in ask:
            problems.append("the audit is marked up with a price the reader cannot see")
    # 3. THE FIGURES. Every number in the source markdown has to survive to the page.
    nums = set(re.findall(r"[£$]\d[\d,]*\.?\d*|\d+\.\d%", md))
    lost = sorted(n for n in nums if html.escape(n, quote=False) not in doc)
    if lost:
        problems.append(f"figures dropped between the report and the page: {lost}")
    # 4. THE CLAIM THE PAGE MAKES ABOUT ITSELF.
    for must in ("worked sample of the report", "has been adjusted",
                 "What has been removed is the seller"):
        if must not in doc:
            problems.append(f"the page no longer says {must!r}")
    if "<table>" not in doc:
        problems.append("no table rendered — the report is the tables")
    # 5. THE OWN-STORE BLOCK. Absent is fine; present and wrong is not.
    problems += own_store_problems(doc, own_store_data())
    problems += pagecheck_problems(doc, pagecheck)
    if problems:
        raise SystemExit("audit-sample.html: " + "; ".join(problems))


def pagecheck_problems(doc, p):
    """The entry rung's block must carry its price, its link and its two honest limits.

    The limits are refusals rather than review notes for the same reason the VAT caveat
    is: this page's reader has self-selected as a Gumroad seller looking at their own
    checkout, and the block sits directly under a table of differences. Without "you are
    buying the reading and not a finding" it reads as an offer to find them a problem, on
    a page whose own data says the problem is usually lawful tax plus a percent of
    rounding. That is the §WI rule — a claim the seller can refute must not reach a buyer
    — applied where the money moves.
    """
    if not p:
        return []
    bad = []
    flat = " ".join(doc.split())
    if p["display"] not in doc:
        bad.append(f"the entry rung's live price {p['display']!r} is not on the page")
    if PAGECHECK not in doc:
        bad.append(f"the entry rung is priced but not linked ({PAGECHECK})")
    for must in ("You are buying the reading and not a finding",
                 "one product page, not your storefront",
                 "Refund on request within 30 days"):
        if " ".join(must.split()) not in flat:
            bad.append(f"the entry-rung block lost a stated limit: {must!r}")
    return bad


def own_store_problems(doc, d):
    """The own-store block must recompute, and must not lose its own caveat.

    Two failure modes, and the second is the one that would actually cost something.

    (a) ARITHMETIC. Every row's difference is RECOMPUTED here from the advertised and
        charged figures rather than trusted from the file, and the recomputed value must
        be the one on the page. This is `velocity_analyse()`'s rule (§WO-0d): a generator
        that renders a summary another tool wrote will publish that tool's bug.

    (b) THE CAVEAT. The block's whole defensibility is the sentence saying the gap is
        VAT and VAT is lawful. Without it a table headed "page says / pay step charges"
        reads as an accusation against Gumroad, published on a page selling a product
        that measures Gumroad. Deleting that sentence must abort the build, exactly as
        deleting the coverage caveat aborts the guides build.
    """
    if not d or not d.get("rows"):
        return []
    bad = []
    for r in d["rows"]:
        want = round(r["charged"] - r["advertised"], 2)
        if abs(want - r["gap"]) > 0.005:
            bad.append(f"own-store row {r['permalink']}: file says the gap is "
                       f"{r['gap']} and {r['charged']} - {r['advertised']} is {want}")
        shown = f"+{r['currency']}{want:.2f}"
        if shown not in doc:
            bad.append(f"own-store row {r['permalink']}: recomputed {shown} is not on "
                       f"the page")
        if r["tax_line"] and html.escape(r["tax_line"]) not in doc:
            bad.append(f"own-store row {r['permalink']}: the line that explains the gap "
                       f"({r['tax_line']!r}) did not reach the page")
        # (c) THE DECOMPOSITION, ADDED 2026-08-26 AND THE REASON THIS BLOCK WAS WRONG.
        #     advertised + residual + tax MUST equal charged. The old gate checked that
        #     the gap arithmetic was self-consistent and that the tax line was PRESENT,
        #     which is true of a page claiming the tax line IS the gap. Nothing compared
        #     the two, so "every gap below is VAT" passed every build for a fortnight.
        res = _residual(r)
        total = round(r["advertised"] + res + _money(r["tax_line"]), 2)
        if abs(total - r["charged"]) > 0.005:
            bad.append(f"own-store row {r['permalink']}: {r['advertised']} + {res} "
                       f"(residual) + {_money(r['tax_line'])} (tax) = {total}, but the "
                       f"pay step charged {r['charged']} — the decomposition this block "
                       f"publishes does not close")
        if f"+{r['currency']}{res:.2f}" not in doc:
            bad.append(f"own-store row {r['permalink']}: the non-tax residual "
                       f"{r['currency']}{res:.2f} is not on the page, so the table "
                       f"implies the tax line explains the whole gap")
    # WHITESPACE-INSENSITIVE, AND THAT IS NOT LAZINESS. The previous form pinned
    # 'merchant of\nrecord', so re-wrapping the paragraph — which this correction had to
    # do — made a caveat gate fail while every caveat was still on the page. A gate that
    # cries wolf on a reflow is a gate somebody deletes. Meaning is pinned; layout is not.
    flat = " ".join(doc.split())

    if "Every gap below is VAT, and VAT is lawful" in flat:
        bad.append("the own-store block has regained the FALSE claim 'Every gap below is "
                   "VAT, and VAT is lawful' — it is refuted by this page's own rows, "
                   "where the gap exceeds the tax line by the checkout subtotal residual")
    for must in ("Most of every gap below is VAT, and VAT is lawful",
                 "merchant of record and is required to add it",
                 "The gap does not reduce to the tax line",
                 "I still cannot see these numbers from inside my own account"):
        if " ".join(must.split()) not in flat:
            bad.append(f"the own-store block lost its caveat: {must!r} is not on the page")
    return bad


if __name__ == "__main__":
    build()
    print("wrote", OUT)
