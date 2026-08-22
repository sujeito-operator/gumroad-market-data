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

    THE ORDER OF THE TWO LINKS IS DELIBERATE AND IT IS NOT THE ORDER OF THE PRICES. The
    monitor is the cheaper of the two and its first month IS this report, so the recurring
    product is the easier way in rather than an upsell bolted onto the one-off. That is
    `gumroad_monitor_sku.py`'s argument and it only reads as honest if both numbers are on
    the page, which until today neither was.
    """
    return f"""<div class=buy><strong>This is the report, not a summary of it.</strong><br>
The page above is one storefront's audit end to end &mdash; the same document a buyer receives,
with the seller's name and product titles removed and not one figure altered. Yours names
your products, walks every product on your storefront, and is run the day the order lands.
<a href="{PRODUCT}">Order the audit &mdash; {audit['display']}, once &rarr;</a>
<a class=alt href="{MONITOR}">Or have it watched &mdash; {monitor['display']} a month, and your
first month is this report &rarr;</a>
<span class=fine>The watched version is a monthly subscription and its first month is this
report, included rather than added on &mdash; so the watched version is the cheaper way in and not
the upsell. After that the walk repeats weekly and you hear from me when a gap opens, closes or
moves. The number moves on its own &mdash; it is a function of the day's
exchange rate, the buyer's country, Gumroad's tax handling and your own edits &mdash; so a report is
true on the day it is written and the watching is what keeps it true. Both figures above were read
off the Gumroad product pages when this page was built ({audit['read_at']}); those pages are
where you pay and they are the authority if they ever disagree with this one.
Prefer to look at the underlying data first? The category crawl behind
the price comparison is <a href="{B.SITE}/">free and openly licensed</a>.</span></div>"""


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
    cut = body.index("</table>") + len("</table>")
    doc = (B.head(TITLE, DESC, PAGE, extra)
           + body[:cut] + block + body[cut:]
           + f"""<nav class=sib><a href="{B.SITE}/checkout.html">How widespread this is
across 32 stores</a> &middot; <a href="{B.SITE}/">The free dataset</a></nav>
<footer>Walked and published 2026-08-12 by the operator of
<a href="{B.SITE}/">gumroad-market-data</a>. Nothing was ordered and no form was
submitted; every reading stops at the pay step.</footer></main></body></html>""")
    assert_page(doc, md, audit, monitor)
    OUT.write_text(doc)
    return doc


def assert_page(doc, md, audit, monitor):
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
        allowed = {audit["display"], monitor["display"]}
        for fig in set(re.findall(r"\$\d+(?:,\d{3})*(?:\.\d+)?", ask)):
            if fig not in allowed:
                problems.append(
                    f"the call to action shows {fig}, which is not a live reading "
                    f"(live: {sorted(allowed)}) — a figure in an ask must come from "
                    f"live_price.price() and from nowhere else")
        for rec, what in ((audit, "audit"), (monitor, "monitor")):
            if rec["display"] not in ask:
                problems.append(f"the {what} price {rec['display']} was read live and did "
                                f"not reach the call to action")
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
    if problems:
        raise SystemExit("audit-sample.html: " + "; ".join(problems))


if __name__ == "__main__":
    build()
    print("wrote", OUT)
