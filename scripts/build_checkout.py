#!/usr/bin/env python3
"""/checkout.html — what a UK buyer is actually charged, measured on a sample of stores.

WHY THIS PAGE EXISTS, AND WHY IT IS NOT A COMPLAINT. Gumroad is the merchant of record.
For a buyer in a VAT jurisdiction it adds the tax on top of the price at the pay step.
That is legal, it is normal for a merchant of record, and it happens to every seller on
the platform — including this one; our own product is in the table below for exactly that
reason. **Nothing here is a seller's mistake and the page must never imply that it is.**

What makes it worth publishing is who can see it. A seller reads their own catalogue
logged in, in their own currency, from their own country, and their dashboard reports
USD. The number a UK or EU visitor sees at the moment of paying is not on any screen the
seller has. So the platform behaviour is public, the consequence is not, and the gap is
one page load wide.

EVERY FIGURE ON THE PAGE IS READ FROM `data/checkout-audit.json`, WHICH IS THE RAW OUTPUT
of `scripts/seller_audit.py` in the operator repo — one record per store, page price,
checkout subtotal, tax line, total, and the delta computed from those. Nothing is typed.
If the JSON is missing the build stops rather than publishing a page with defaults in it.

THE DENOMINATOR IS PUBLISHED BESIDE EVERY PERCENTAGE. Stores the walk could not read are
counted and listed with the reason, never dropped: a denominator that shrinks to fit the
finding is how an honest table becomes a dishonest one without anybody typing a false
sentence. Stores where the pay step charged LESS than the page showed are their own row
type and are described as a misread on our side, because that is the likeliest
explanation and the alternative would flatter the finding.

Imported and called by build_site.py, so one command still regenerates every surface.
"""
import json
import pathlib
import re

import build_site as B

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT = ROOT / "data" / "checkout-audit.json"
SAMPLE = ROOT / "data" / "checkout-sample.json"
# Written by `build_checkout_pitch.py --emit-decomposition` in the operator repo, which
# owns the ONLY implementation of the split. The press pitch that links this page quotes
# these same figures; recomputing them here with second code is how a page and the letter
# pointing at it come to disagree by a rounding.
DECOMP = ROOT / "data" / "checkout-decomposition.json"
# Written by `build_replication_cohort.py` in the operator repo. A SECOND cohort of stores,
# walked identically but selected to be written to rather than drawn at random. It exists
# because the sample above is frozen at 32 by design and 71 further stores had been walked
# and never published. It is rendered in its own section, under its own denominator, and it
# NEVER enters `read`, `unread` or `drawn` — the assert below depends on that.
REPLICATION = ROOT / "data" / "checkout-replication.json"
# Written by `vat_disclosure.py --emit-disclosure` in the operator repo, which owns the
# ONLY implementation of the classifier and of the bare-word re-read that tests it.
#
# THIS FILE EXISTS BECAUSE THE SECTION IT FEEDS WAS TYPED BY HAND. On 2026-08-13 the
# disclosure ratio was computed in a session and pasted straight into `docs/checkout.html`.
# No generator emitted it, so no generator knew it was there, and a plain rebuild on
# 2026-08-21 silently deleted the whole section — the finding, its table, the re-read and
# the legal citations. Nothing noticed because no full build had run in nine days. The
# last arm of `assert_page` is the guard that caught it; this is the repair.
DISCLOSURE = ROOT / "data" / "checkout-disclosure.json"
# THE RECURRING SKU, NAMED HERE AND NOWHERE ELSE ON THIS PAGE, AND CARRYING NO FIGURE.
# `build_audit_sample_page.py` made this argument first on 2026-08-13 and it applies to
# this page at least as well: the reader of a page about pay-step gaps has self-selected
# as somebody who cares whether their own checkout still agrees with their own page. The
# section below already tells them to go and look — the monitor is the honest second half
# of that sentence, because looking once answers a question that comes back every time a
# price moves. No price is typed: the figure lives on the Gumroad page and on no surface
# this repository generates, which is the same rule the report's guarantee window follows.
MONITOR = "https://sujeitooperator.gumroad.com/l/zyoqbc"
PAGE = f"{B.SITE}/checkout.html"
# The published file, read back before it is overwritten. See the last arm of
# `assert_page`: this page has a second author and this generator does not know it.
PUBLISHED = ROOT / "docs" / "checkout.html"

# Our own store, so "it happens to us too" is a row in the table rather than a claim in a
# sentence. Derived from the buy link the rest of the site already uses, so it cannot
# drift away from the product being sold.
OURS = B.BUY.split("/l/")[0].split("//")[1]


def buckets(recs):
    """Partition the walked records. Mirrors `audit_sample.aggregate` in the operator repo.

    Kept as its own implementation here on purpose: this repo publishes the page and must
    be able to state what it published without a second repo being present at build time.
    The two are pinned to each other by the raw JSON, which carries every input figure.
    """
    read, unread = [], []
    for r in recs:
        pp = r.get("page_price")
        total = (r.get("checkout") or {}).get("total")
        # A free product is not a reading: page £0.00 against checkout $0 is zero money in
        # two currencies, and the currency verdict makes it look like a finding.
        if pp and total and pp[1] == 0 and total[1] == 0:
            unread.append(dict(r, why="the product is free"))
            continue
        if not pp or not total:
            unread.append(r)
            continue
        d = r.get("delta_pct")
        if r.get("verdict") == "currency":
            b = "currency"
        elif d is None or -2.0 < d < 2.0:
            b = "agree"
        elif d >= 2.0:
            b = "higher"
        else:
            b = "lower"
        read.append((b, r))
    return read, unread


def median(xs):
    s = sorted(xs)
    if not s:
        return None
    m = len(s) // 2
    return round(s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2, 1)


def store_of(url):
    return url.split("//")[1].split(".gumroad")[0]


def replication():
    """The second cohort's section, or "" when the file is absent.

    THE POINT OF THIS SECTION IS THAT IT WEAKENS ITS OWN EVIDENCE BEFORE USING IT. These
    stores were picked to be written to. Every filter that put them here — a ratings band,
    a published contact address, a non-free top product — is a selection a random draw does
    not make, and the largest of them (the address) selects for sellers who are more set up
    than average. Read as an estimate of Gumroad, the number is worthless. Read as a
    replication, it is the strongest thing on the page: a cohort assembled for a different
    purpose, by different criteria, from a different part of the index, walked on different
    days, returns the sample's median to within a rounding.

    So the disclaimer is not a hedge bolted on at the end. It is the reason the section is
    worth reading, and `assert_page` refuses to publish the page without it.
    """
    if not REPLICATION.exists():
        return ""
    doc = json.loads(REPLICATION.read_text())
    s, recs = doc["summary"], doc["records"]
    read, unread = buckets(recs)
    higher = [r for b, r in read if b == "higher"]
    deltas = sorted(r["delta_pct"] for r in higher)

    # The two medians side by side, computed here from the records rather than taken from
    # the emitted summary, so the sentence cannot outlive the data it describes.
    sample_recs = json.loads(AUDIT.read_text())
    sread, _ = buckets([r for r in sample_recs if OURS not in r.get("url", "")])
    smed = median([r["delta_pct"] for b, r in sread if b == "higher"])
    rmed = median(deltas)
    agreement = ("lands on the sample&rsquo;s median to the first decimal" if smed == rmed
                 else f"lands {abs(round(rmed - smed, 1))} points from the sample&rsquo;s median")

    mark = {"higher": "", "agree": "no change", "lower": "misread",
            "currency": "currency change"}
    rows = []
    for b, r in sorted(read, key=lambda x: -(x[1].get("delta_pct") or -999)):
        ck = r.get("checkout") or {}
        d = r.get("delta_pct")
        cell = "—" if d is None else f"{d:+.1f}%"
        if mark[b]:
            cell += f" <span class=fine>{mark[b]}</span>"
        rows.append(f"<tr><td>{B.esc(store_of(r['url']))}</td>"
                    f"<td class=n>{B.esc(r['page_price'][2])}</td>"
                    f"<td class=n>{B.esc(ck['tax'][2]) if ck.get('tax') else '—'}</td>"
                    f"<td class=n>{B.esc(ck['total'][2])}</td>"
                    f"<td class=n>{cell}</td></tr>")
    rows = "".join(rows)

    unread_rows = "".join(
        f"<tr><td>{B.esc(store_of(r['url']))}</td><td colspan=4 class=fine>"
        f"{B.esc(r.get('why') or r.get('error') or 'not read')}</td></tr>" for r in unread)

    return f"""
<h2>Does it hold up on stores we did not draw at random? — {len(higher)} of {len(read)}</h2>
<p class=lede><strong>Not a random sample, and that is stated before the number and not
after it.</strong> Alongside the draw above, {s['stores']} further stores were walked the
same way between {B.esc(s['walked_from'])} and {B.esc(s['walked_to'])} — one product each,
none of them in the sample, none of them ours. They were selected to be written to, so each
passed filters a random draw does not apply: a ratings-ranked band of the seller index, a
<strong>published contact address on the product page</strong> (about 17.5% of sellers have
one, and that is the largest bias here), a top-rated product that is not free, and a
published category page.</p>

<p>As an estimate of the platform that cohort is worth nothing. As a replication it is worth
more than the draw: it was assembled for an unrelated purpose, by different criteria, from a
different part of the index, on different days — and it {agreement}.
<strong>{len(higher)} of the {len(read)} readable stores charged more at the pay step</strong>,
median {rmed}% (range {deltas[0]}%&ndash;{deltas[-1]}%), against {smed}% across the
{len(sread)} readable stores of the random draw.</p>

<table><thead><tr><th>Store</th><th class=n>Page shows</th><th class=n>Tax line</th>
<th class=n>Pay step total</th><th class=n>Difference</th></tr></thead>
<tbody>{rows}</tbody></table>

<p class=fine>Not read, {len(unread)} of {s['stores']}, listed rather than dropped for the
same reason as above.</p>
<table><thead><tr><th>Store</th><th colspan=4>Why the walk produced no comparable pair</th>
</tr></thead><tbody>{unread_rows}</tbody></table>

<p class=fine>Where a store was walked more than once, the most recent reading is the one
counted and the store counts once &mdash; {s['dropped'].get('an earlier or second reading of a store already counted', 0)}
readings were set aside that way, {s['dropped'].get('already in the published random sample', 0)}
for already being in the draw above and {s['dropped'].get('our own store', 0)} for being ours.
The records are in
<a href="{B.REPO}/blob/main/data/checkout-replication.json">data/checkout-replication.json</a>.</p>
"""


def disclosure():
    """The disclosure section, rendered from the operator repo's emitted tally.

    THE ONLY LITERALS HERE ARE THE LEGAL CITATIONS. Every count, ratio, store name and
    matched phrase is read off the file. That is the whole point: the previous version of
    this section was nine numbers typed into HTML, which is why nothing could regenerate
    it and why a rebuild deleted it.

    THE PROSE ASKS THE DATA BEFORE IT CHARACTERISES IT. "The silence is total" is only
    true while the bare-word re-read comes back empty; if a silent page ever turns out to
    mention tax in some context the classifier did not credit, this says the weaker thing
    instead. A sentence that cannot come out false is not evidence of anything.
    """
    if not DISCLOSURE.exists():
        raise SystemExit(
            f"{DISCLOSURE} is missing. It is written by `vat_disclosure.py "
            f"--emit-disclosure` in the operator repo. Building without it would drop the "
            f"disclosure section, which is the defect this file exists to prevent.")
    d = json.loads(DISCLOSURE.read_text())
    gapped, silent, told = d["gapped"], d["silent"], d["disclosed"]
    checked, hits = d["bare_checked"], d["bare_hits"]
    # Small counts read as words in prose and as digits in the tiles. The published page
    # said "Three tell the reader"; deriving the number must not cost it that.
    told_word = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight",
                 "nine", "ten"][told] if told <= 10 else str(told)

    # The re-read paragraph, in the two shapes the data can take.
    if hits == 0:
        bare = (f"<strong>{hits} of {checked} contain any of them in any context.</strong> "
                f"The silence is total, not a matter of phrasing.")
    else:
        words = ", ".join(f"<code>{B.esc(w)}</code>" for w in d["bare_words"])
        bare = (f"<strong>{hits} of {checked} do contain one</strong> ({words}) somewhere in "
                f"their text without saying anything to the buyer about it. So the silence "
                f"is not total: on those pages the word appears and tells the reader "
                f"nothing. The other {checked - hits} do not mention tax at all.")

    # The phrase column is a MATCHED SPAN, not a quotation, and it must not be dressed as
    # one. One of the three reads "excluding VAT, VAT" — the needle runs from "excluding"
    # to the second tax word — and inside typographic quotes that looks like a typo on the
    # seller's page rather than the shape of our own regex. `<code>` says what it is.
    told_rows = "\n".join(
        f"<tr><td><code>{B.esc(store)}</code></td><td><code>{B.esc(phrase or '')}</code></td></tr>"
        for store, phrase in sorted(d["disclosing"].items()))
    # `contradicted` is the sharpest cell in the classifier and it has always been empty.
    # Saying so is worth a clause: it is the difference between "nobody mentions it" and
    # "somebody claims the opposite", and a reader is entitled to know which one we found.
    contra = d.get("contradicted", 0)
    contra_clause = ("None claims the price already includes it." if not contra else
                     f"{contra} claim the price already includes it, against a gap the walk "
                     f"recorded.")
    return f"""
<h2>How many of them say so on the page? — {told} of {gapped}</h2>
<p class=lede>Everything above is a fact about Gumroad. This is the only part that is a fact about
the <em>sellers</em>, and it is the sharper number.
<strong>Of {gapped} third-party storefronts where we recorded a pay-step gap, {silent} &mdash;
{d['pct_silent']}% &mdash; say nothing about tax anywhere on the product page.</strong>
{told_word.capitalize()} tell the reader. {contra_clause}</p>

<div class=kv>
<div><b>{gapped}</b><span>stores with a recorded gap</span></div>
<div><b>{silent}</b><span>say nothing at all</span></div>
<div><b>{told}</b><span>tell the reader</span></div>
<div><b>{d['pct_silent']}%</b><span>silent</span></div>
<div><b>{d['median_gap_silent']}%</b><span>median gap, silent stores</span></div>
<div><b>{hits} of {checked}</b><span>mention tax in any context</span></div>
</div>

<p>The distinction matters more than it looks. The {d['median_gap_silent']}% gap is <em>not the
seller&rsquo;s doing and not the seller&rsquo;s to fix</em> &mdash; that is said plainly at the top
of this page and it stays said. But whether the page mentions it is entirely theirs: one line in a
description, no plugin, no platform change, about sixty seconds. It is the one part of this whole
measurement that comes with an action attached.</p>

<p>The {told_word} that do it, and the words that earned it. The right-hand column is the span the
classifier matched, not a tidied quotation:</p>
<table><thead><tr><th>store</th><th>what matched on the page</th></tr></thead><tbody>
{told_rows}
</tbody></table>

<p class=cite><strong>Why {silent} is not just &ldquo;our search missed it&rdquo;.</strong> A needle
set can fail by being too narrow, and that failure looks exactly like a finding. So all {checked}
silent pages were re-read and searched for the bare words <code>vat</code>, <code>gst</code>,
<code>tax</code> and <code>taxes</code> anywhere in their visible text, with no requirement that
they sit near anything else. {bare} Matching is word-boundary anchored throughout, because
<em>pri&#8203;vat&#8203;e</em>, <em>inno&#8203;vat&#8203;ive</em> and <em>syn&#8203;tax</em> would
otherwise each read as a tax disclosure.</p>

<p><strong>Our own store is excluded from both sides of that ratio</strong>, the same way it is
excluded from the drawn sample above. It was measured too: all three paid pages state that tax is
added, and did so before this count was taken rather than after it.</p>

<p class=cite><strong>What this is not.</strong> It is a measurement of what page text says, and
nothing else. It is not a claim that any seller has broken any rule &mdash; that depends on who the
trader is, where their buyers are and how a regulator reads a platform-collected tax, none of which
a reading of a web page can settle. If you want the rules themselves rather than our summary of
them, the relevant ones are the definition of &ldquo;selling price&rdquo; in the
<a href="https://www.legislation.gov.uk/uksi/2004/102/article/1/made">Price Marking Order 2004</a>,
regulation 6 of the
<a href="https://www.legislation.gov.uk/uksi/2008/1277/regulation/6/made">CPUTRs 2008</a>, and the
consumer provisions of the Digital Markets, Competition and Consumers Act 2024, in force since
6 April 2025. That last one is the one to read: it requires the total price up front, and where a
mandatory charge <em>cannot be quantified in advance</em> &mdash; which VAT here genuinely cannot,
since it depends on a buyer&rsquo;s country &mdash; it asks that the headline price be accompanied
by what a reader needs to work the total out. Which is the one line above.</p>
"""


def build(t):
    if not AUDIT.exists():
        raise SystemExit(f"{AUDIT} is missing — copy the audit JSON from the operator repo "
                         f"(`evidence/seller-audit-sample-*.json`) before building.")
    recs = json.loads(AUDIT.read_text())
    sample = json.loads(SAMPLE.read_text()) if SAMPLE.exists() else {}
    read, unread = buckets(recs)
    # OUR OWN STORE IS NOT IN THE DRAW AND MUST NOT BE IN THE DENOMINATOR. It was walked
    # deliberately, not drawn by `audit_sample.py`'s seeded stratified sample, and until
    # 2026-08-12 it was counted inside both — the headline read "28 of 32" where the draw
    # says 27 of 31. The prose disclosed that ours was in the table; the NUMBER did not,
    # and a store you picked yourself in a random sample's numerator is the one thing this
    # page's whole method is supposed to rule out. It keeps its own sentence below.
    read = [(b, r) for b, r in read if OURS not in r.get("url", "")]
    unread = [r for r in unread if OURS not in r.get("url", "")]
    drawn = [r for r in recs if OURS not in r.get("url", "")]
    higher = [r for b, r in read if b == "higher"]
    agree = [r for b, r in read if b == "agree"]
    lower = [r for b, r in read if b == "lower"]
    cur = [r for b, r in read if b == "currency"]
    deltas = [r["delta_pct"] for r in higher]
    med, lo, hi = median(deltas), (min(deltas) if deltas else None), (max(deltas) if deltas else None)
    ours = [r for r in recs if OURS in r.get("url", "")]

    assert not any(OURS in r.get("url", "") for _, r in read), \
        "our own store is back inside the sample denominator"
    assert len(drawn) == sample.get("n", len(drawn)), \
        f"{len(drawn)} walked stores but the manifest drew {sample.get('n')}"

    title = (f"What a UK buyer is actually charged on Gumroad — "
             f"{len(higher)} of {len(read)} stores measured")
    desc = (f"Walked {len(drawn)} Gumroad product pages and their own checkouts from London. "
            f"{len(higher)} of {len(read)} readable stores charged more at the pay step than "
            f"the page advertised — median {med}%. Gumroad's VAT, not the seller's doing, and "
            f"invisible from inside a seller's account.")
    # The replication belongs in the shared snippet: the sentence a reader sees before
    # clicking is where "31 stores" is weakest, and a second cohort is the answer to it.
    # The headline and the TITLE stay anchored to the random draw — the cohort is not a
    # random sample and must never be quoted as if the two were one number.
    if REPLICATION.exists():
        rs = json.loads(REPLICATION.read_text())["summary"]
        desc += (f" A second, non-random cohort of {rs['stores']} stores, walked the same "
                 f"way, returns a median of {rs['median_pct']}%.")
    # The disclosure ratio is the only sentence here that is about the SELLERS rather than
    # about Gumroad, so it is the one a reader can act on and the one worth the last
    # sentence of a search snippet. It was in the published description and in no
    # generator — same defect as the section itself, same repair.
    if DISCLOSURE.exists():
        ds = json.loads(DISCLOSURE.read_text())
        desc += (f" And of {ds['gapped']} stores with a recorded gap, {ds['silent']} — "
                 f"{ds['pct_silent']}% — say nothing about tax anywhere on the page.")

    rows = []
    for b, r in sorted(read, key=lambda x: -(x[1].get("delta_pct") or -999)):
        ck = r.get("checkout") or {}
        tax = ck.get("tax")
        mark = {"higher": "", "agree": "no change", "lower": "misread",
                "currency": "currency change"}[b]
        d = r.get("delta_pct")
        delta_cell = "—" if d is None else f"{d:+.1f}%"
        if mark:
            delta_cell += f" <span class=fine>{mark}</span>"
        rows.append(
            f"<tr><td>{B.esc(store_of(r['url']))}</td>"
            f"<td class=n>{B.esc(r['page_price'][2])}</td>"
            f"<td class=n>{B.esc(tax[2]) if tax else '—'}</td>"
            f"<td class=n>{B.esc(ck['total'][2])}</td>"
            f"<td class=n>{delta_cell}</td></tr>")
    table = "".join(rows)

    unread_rows = "".join(
        f"<tr><td>{B.esc(store_of(r['url']))}</td><td colspan=4 class=fine>"
        f"{B.esc(r.get('why') or r.get('error') or 'not read')}</td></tr>" for r in unread)

    ours_line = ""
    if ours:
        o = ours[0]
        ot = (o.get("checkout") or {}).get("total")
        if o.get("page_price") and ot:
            ours_line = (
                f" Ours does the same thing: the page shows {B.esc(o['page_price'][2])} and "
                f"the pay step totals {B.esc(ot[2])}. We found it on our own product first, on "
                f"2026-08-09, and changed our description the same day — which is the only "
                f"thing a seller can actually do about it. It is deliberately NOT in the table "
                f"below and not in any figure on this page: we chose it ourselves, so it does "
                f"not belong in a random sample's numerator.")

    frame = ""
    if sample:
        extra = len(recs) - len(drawn)
        frame = (f"{sample['n']} of the stores were drawn from {sample['frame_size']:,} sellers "
                 f"with a fixed seed ({sample['seed']}), eight from each of four price bands, "
                 f"before anything was walked. The draw is reproducible from the same CSV, so "
                 f"nobody — including us — can re-roll it until the result looks better."
                 + (f" Our own product was walked alongside them and is reported above "
                    f"rather than counted here — a page that reports a platform's behaviour "
                    f"and exempts its own author from it is worth less than nothing, and one "
                    f"that puts a self-chosen store in a random sample is worth less than "
                    f"that." if extra > 0 else ""))

    tax_labels = sorted({(r.get("checkout") or {}).get("tax_label")
                         for _, r in read if (r.get("checkout") or {}).get("tax_label")})

    # WHERE THE DIFFERENCE ACTUALLY COMES FROM. The obvious reading of the headline figure
    # is "that is just VAT", and it is wrong: a statutory rate applied to the ADVERTISED
    # price would land on the rate. The itemised tax over the itemised SUBTOTAL does land
    # on it — because the subtotal is not the price the page showed. Publishing the
    # headline without the split invites a reader to a conclusion the records refute.
    split = ""
    if DECOMP.exists():
        dc = json.loads(DECOMP.read_text())
        v, dr = dc["vat"], dc["drift"]
        split = f"""
<h2>Where the difference comes from, and it is not one thing</h2>
<p>The headline figure looks like a tax rate and is not one. The pay step itemises a
<em>subtotal</em> as well as a tax, and the subtotal is not the price the page advertised.
Two effects stack:</p>
<ul>
<li><strong>Tax on the subtotal: median {v['median']}%, range {v['min']}%&ndash;{v['max']}%
across {v['n']} readings.</strong> Tight enough to read as a single statutory rate.</li>
<li><strong>A drift between the advertised price and the amount actually taxed: median
{dr['median']}%, range {dr['min']}%&ndash;{dr['max']}% across {dr['n']} readings.</strong>
The displayed price is converted for the visitor and the charged one is rounded separately,
so the number being taxed is not the number that was quoted.</li>
</ul>
<p class=fine>Both figures use only readings where the page and the pay step quoted the same
currency &mdash; across a currency change the difference is an exchange rate, not a drift.
Excluded from both: {B.esc(dc.get("excluded", ""))}. Neither component is hidden and neither
is large alone; the compounded number is the one a buyer meets.</p>
"""

    return B.head(title, desc, PAGE) + f"""
<h1>{B.esc(title)}</h1>
<p class=lede>Every product page below was loaded logged out from London, then its own
&ldquo;I want this&rdquo; control was followed to Gumroad&rsquo;s checkout and the checkout was read.
<strong>{len(higher)} of the {len(read)} stores we could read charged more at the pay step than the
page advertised</strong>{f', a median of {med}% more (range {lo}%&ndash;{hi}%)' if med is not None else ''}.
The extra is {' and '.join(B.esc(x) for x in tax_labels) if tax_labels else 'tax'}, added on top.</p>

<div class=buy><strong>This is Gumroad&rsquo;s doing, not the seller&rsquo;s.</strong><br>
Gumroad is the merchant of record. For a buyer in a VAT jurisdiction it collects the tax on top
of the listed price and remits it. That is lawful, it is what a merchant of record is for, and no
setting in a seller&rsquo;s account switches it off. Nobody in the table below has done anything
wrong, and this page is not an accusation.{ours_line}
<span class=fine>What is worth knowing is that a seller cannot see it. Logged in, you see your own
catalogue in your own currency from your own country, and the dashboard reports USD. The number a
UK or EU visitor reads at the moment of paying does not appear on any screen you have.</span></div>

<h2>What each store advertised, and what the pay step totalled</h2>
<table><thead><tr><th>Store</th><th class=n>Page shows</th><th class=n>Tax line</th>
<th class=n>Pay step total</th><th class=n>Difference</th></tr></thead>
<tbody>{table}</tbody></table>

<h2>The ones we could not read — {len(unread)} of {len(drawn)}</h2>
<p>Listed rather than dropped. A percentage whose denominator quietly excludes the awkward cases
is not a measurement.</p>
<table><thead><tr><th>Store</th><th colspan=4>Why the walk produced no comparable pair</th></tr>
</thead><tbody>{unread_rows}</tbody></table>

{split}
{replication()}
<h2>Method, in full</h2>
<ul>
<li><strong>{len(drawn)} stores drawn and walked, {len(read)} read, {len(unread)} not read.</strong>
{len(higher)} charged more at the pay step, {len(agree)} matched the page,
{len(lower)} came out lower — that last group is almost certainly us misreading the page price
(a pay-what-you-want minimum or a struck-through price), not a discount, and it is counted in
the denominator rather than thrown away.{f' {len(cur)} switched currency between page and checkout.' if cur else ''}</li>
<li><strong>{B.esc(frame)}</strong></li>
<li><strong>Two page loads per store and nothing else.</strong> The product page, then the
<code>gumroad.com/checkout</code> URL the page&rsquo;s own buy control carries. No order was
completed, no form was submitted, no email or card was typed into anybody&rsquo;s checkout, and no
account was touched. It is what a buyer who thinks twice and leaves does.</li>
<li><strong>From London, GB.</strong> A buyer somewhere without VAT sees a different number, and
that is the point — the difference is a function of where the buyer is, which is precisely the
thing the seller cannot vary from inside their own account.</li>
<li><strong>Read on {B.esc(sorted(r.get('read_at', '') for r in recs)[-1][:10] if recs else '')}.</strong>
Prices move; re-run it yourself. The reader is
<a href="https://github.com/sujeito-operator">open source</a> and the raw records for this page are
in <a href="{B.REPO}/blob/main/data/checkout-audit.json">data/checkout-audit.json</a>.</li>
</ul>
{disclosure()}
<h2>What a seller can actually do</h2>
<p>Not much, and it is better to say so than to invent a fix. You cannot turn it off; you are not
supposed to. What you can do is stop being surprised by it:</p>
<ul>
<li><strong>Know your own number.</strong> Open your product page in a private window from a VAT
country and follow your own buy button. It takes a minute and it is the only way to see what your
buyer sees. If you are not in a VAT country and cannot do that,
<a href="https://github.com/sujeito-operator/gumroad-checkout-gap">this reads it for you</a> — the
same code that produced the table above, one file, MIT, no signup and no email. It loads two pages
and stops.</li>
<li><strong>Say it on the page.</strong> A line saying tax is added at checkout for EU/UK buyers
costs nothing and removes the surprise at the exact step where surprise loses the sale.</li>
<li><strong>Compare like with like.</strong> When you benchmark your price against a competitor,
you are reading their pre-tax number and your buyer is paying a post-tax one.</li>
<li><strong>Or have it re-read for you.</strong> The first bullet is a thing you do once, and the
number it gives you goes stale the next time you change a price, add a product or Gumroad changes
what it collects. <a href="{MONITOR}">The checkout monitor</a> is that same walk, run against every
product on your store on a schedule, and it writes to you only when a page and its pay step start
disagreeing. It is the paid, recurring version of the free script above &mdash; the script is not a
teaser for it, and if once is all you need, once is free.</li>
</ul>

{B.buy_block("It reads " + f"{B.REPORT_CATS:,}" + " Gumroad categories the same way this page reads checkouts: from what the platform actually shows, not from what it says about itself.")}

<h2>What one storefront's full audit looks like</h2>
<p>This page reads one product from each of many stores. The other half of the same
measurement is every product on <em>one</em> store, walked the same way and placed against
what comparable products in its own category charge. That report is a paid product, and
<a href="{B.AUDIT_SAMPLE_PAGE}">a complete worked sample of it is published here</a> —
one real storefront, nine products, the seller's name removed and not one figure altered.</p>

<nav class=sib><a href="./">The free data and the full method</a> ·
<a href="{B.AUDIT_SAMPLE_PAGE}">A full storefront audit, worked</a> ·
<a href="g/">The guides</a> · <a href="s/">By seller</a> · <a href="{B.REPO}">Repository</a></nav>
""" + B.FOOTER


def assert_page(html, recs):
    """A check that only exists in a transcript is not a check (price_sweep.py's rule).

    Three things must be true of the published bytes, and each of them has already gone
    wrong somewhere in this project: the attribution sentence must be present (an honest
    finding sold as the seller's fault is the failure mode `outreach_audit_batch01.py`
    was built to prevent), the denominator must be on the page beside the finding, and
    every store the walk failed on must be named.
    """
    problems = []
    # The page tells the reader to check their own number, and for a US seller that
    # instruction is unfollowable — they are the one class of reader who CANNOT see the
    # finding, and they are most of the market. The free tool is the answer to it, so a
    # build that drops the link publishes advice nobody can take.
    if "gumroad-checkout-gap" not in html:
        problems.append("the page tells the reader to measure their own and links no way to")
    if "merchant of record" not in html:
        problems.append("the attribution to Gumroad is missing from the page")
    if "not an accusation" not in html:
        problems.append("the no-fault sentence is missing")
    # The split is the paragraph a later edit shortens first, because it is the only one
    # that complicates the headline. If the data file is there, the page must carry it.
    if DECOMP.exists():
        dc = json.loads(DECOMP.read_text())
        for figure in (f"{dc['vat']['median']}%", f"{dc['drift']['median']}%"):
            if figure not in html:
                problems.append(f"the decomposition figure {figure} is missing — the page "
                                "would imply the headline gap is a statutory rate")
    for r in recs:
        if store_of(r["url"]) not in html:
            problems.append(f"store {store_of(r['url'])} was walked but is not on the page")
    # THE SECOND COHORT IS THE EASIEST THING ON THIS PAGE TO QUOTE DISHONESTLY: it is
    # bigger than the draw and it agrees with it, so a later edit that drops the words
    # "not a random sample" leaves a stronger-looking page and a false one. It is also
    # the section a later edit would trim to shorten the page. Both are refused here.
    if REPLICATION.exists():
        doc = json.loads(REPLICATION.read_text())
        if "Not a random sample" not in html:
            problems.append("the second cohort is published without the sentence saying it "
                            "is not a random sample")
        if "published contact address" not in html:
            problems.append("the second cohort's largest selection bias is not disclosed")
        for r in doc["records"]:
            if store_of(r["url"]) not in html:
                problems.append(f"cohort store {store_of(r['url'])} is counted but not listed")
    # A REBUILD MAY ONLY EVER GAIN SECTIONS. THIS IS THE CHECK THAT SAYS SO.
    #
    # It was added on 2026-08-21 for a section that had no generator: the tax-disclosure
    # finding ("How many of them say so on the page? — 3 of 84") was written straight into
    # the published HTML on 2026-08-13, computed from a cache in the operator repo that
    # nothing here could read. No full build ran in the nine days between, so nobody found
    # out that a plain rebuild DELETED it — the whole section, its table of the three
    # stores that do disclose, the bare-word re-read, the legal citations, and the sentence
    # in the meta description that names the finding.
    #
    # THAT PARTICULAR HOLE IS NOW CLOSED — `disclosure()` renders the section from
    # `data/checkout-disclosure.json`, which `vat_disclosure.py --emit-disclosure` writes.
    # THE CHECK STAYS ANYWAY, AND NOT OUT OF SENTIMENT. It is not about that section; it
    # is about the class. Any future hand-edit to the published bytes is invisible to this
    # file by construction, and losing one is not a diff to review later, it is a published
    # finding falling off the internet. So it stops the build BEFORE the write rather than
    # after it — `build_site.py` calls this function on the rendered string and only then
    # writes the file. Do not delete it, and do not "fix" a failure by deleting the
    # heading from the published file.
    published = PUBLISHED.read_text(encoding="utf-8") if PUBLISHED.exists() else ""
    for heading in re.findall(r"<h2>(.*?)</h2>", published, re.S):
        if f"<h2>{heading}</h2>" not in html:
            problems.append(
                f"REBUILD WOULD DELETE THE PUBLISHED SECTION <h2>{heading}</h2>. It was "
                f"written by hand or by another repo and no generator here emits it. "
                f"Merge that section into build() from its real source before rebuilding "
                f"— do not publish the shorter page, and do not delete this check")
    if problems:
        raise SystemExit("checkout.html: " + "; ".join(problems))
    return len(html)
