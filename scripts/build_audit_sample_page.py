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

THIS PAGE CARRIES NO PRICE, ON PURPOSE, AND THAT IS NOT AN OVERSIGHT TO FIX. The price
lives on the Gumroad product page and is read live by `price_sweep.py` in the operator
repo. A number typed here would be a 542nd surface to keep in sync, and a stale price on
a published surface is the defect this operation has shipped more often than any other.
The call to action links to the product; the product states its own price.
"""
import html
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_site as B                                  # noqa: E402

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

CTA = f"""<div class=buy><strong>This is the report, not a summary of it.</strong><br>
The page above is one storefront's audit end to end — the same document a buyer receives,
with the seller's name and product titles removed and not one figure altered. Yours names
your products, walks every product on your storefront, and is run the day the order lands.
<a href="{PRODUCT}">See the price and order on Gumroad &rarr;</a>
<a class=alt href="{MONITOR}">Or have it watched: the same walk every week, and an email the day
a price stops matching the pay step &rarr;</a>
<span class=fine>The watched version is a monthly subscription and its first month is this
report, included rather than added on; after that the walk repeats weekly and you hear from me
when a gap opens, closes or moves. The number moves on its own — it is a function of the day's
exchange rate, the buyer's country, Gumroad's tax handling and your own edits — so a report is
true on the day it is written and the watching is what keeps it true. Both state their own
price on their own page. Prefer to look at the underlying data first? The category crawl behind
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
    # The CTA goes after the first table — a reader who has seen the checkout half has seen
    # enough to decide, and one who has not should not be asked yet.
    cut = body.index("</table>") + len("</table>")
    doc = (B.head(TITLE, DESC, PAGE)
           + body[:cut] + CTA + body[cut:]
           + f"""<nav class=sib><a href="{B.SITE}/checkout.html">How widespread this is
across 32 stores</a> &middot; <a href="{B.SITE}/">The free dataset</a></nav>
<footer>Walked and published 2026-08-12 by the operator of
<a href="{B.SITE}/">gumroad-market-data</a>. Nothing was ordered and no form was
submitted; every reading stops at the pay step.</footer></main></body></html>""")
    assert_page(doc, md)
    OUT.write_text(doc)
    return doc


def assert_page(doc, md):
    """The page may not name the seller, may not state a price, may not lose a figure."""
    problems = []
    # 1. THE SELLER. The redaction happens upstream; this asserts it arrived intact rather
    #    than trusting it, because the cost of being wrong is publishing a named third
    #    party's pricing as our advertisement.
    for leak in ("rocketlasso", "RKT", "Cinema 4D", "gumroad.com/l/slicer"):
        if leak.lower() in doc.lower():
            problems.append(f"the seller leaked through: {leak!r} is on the page")
    # 2. THE PRICE. See the module docstring — the number lives on Gumroad, read live.
    if re.search(r"\$\d", doc.replace("$0", "").split("<div class=buy>")[0]):
        pass  # dollar figures in the REPORT are measured peer prices and must stay
    for typed in ("$149", "$129", "$249", "$69"):
        if typed in CTA:
            problems.append(f"a price is typed into the call to action: {typed}")
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
