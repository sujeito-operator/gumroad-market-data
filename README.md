# What actually sells on Gumroad — measured

**8,325 live Gumroad products from 4,545 sellers across 261
categories of Gumroad's own category tree — plus a separate 1,344-product sample across
42 Discover searches. Collected August 2026, and
[kept apart on purpose](#two-samples-published-side-by-side).**

> **3,562 of the 8,325 products in the category-tree sample — 43% — have
> no ratings at all.** They are listed, priced, and selling nothing. In the 42-search
> sample the same figure is 34%, and the gap between categories where it happens and
> ones where it doesn't runs from **100% of listings rated** at the top to
> **39%** at the bottom.

Highest demand: vrchat avatar (100%), unity asset (97%), blender addon (94%). Lowest: resume template (42%), crochet pattern (39%), excel dashboard (39%).

**Start with a question:**
[What to sell](https://sujeito-operator.github.io/gumroad-market-data/g/what-to-sell-on-gumroad.html) &middot; [What people make](https://sujeito-operator.github.io/gumroad-market-data/g/how-much-do-people-make-on-gumroad.html) &middot; [What to charge](https://sujeito-operator.github.io/gumroad-market-data/g/gumroad-pricing.html) &middot; [Is it worth it](https://sujeito-operator.github.io/gumroad-market-data/g/is-gumroad-worth-it.html) &middot; [Statistics](https://sujeito-operator.github.io/gumroad-market-data/g/gumroad-statistics.html) &middot; [Free vs paid](https://sujeito-operator.github.io/gumroad-market-data/g/free-vs-paid-digital-products.html) &middot; [Price calculator](https://sujeito-operator.github.io/gumroad-market-data/g/gumroad-price-calculator.html) &middot; [How many products](https://sujeito-operator.github.io/gumroad-market-data/g/how-many-products-to-sell-on-gumroad.html) &middot; [Sales per rating](https://sujeito-operator.github.io/gumroad-market-data/g/gumroad-sales-per-rating.html) &middot; [Multiple categories](https://sujeito-operator.github.io/gumroad-market-data/g/gumroad-multiple-categories.html) &middot; [A free product too?](https://sujeito-operator.github.io/gumroad-market-data/g/gumroad-free-product-strategy.html)

**Or browse a category** for its full price distribution and every listing measured:
<https://sujeito-operator.github.io/gumroad-market-data/>

## Two samples, published side by side

This repository now holds **two independently collected samples of the same
marketplace**, and they are kept apart on purpose rather than merged into a third set of
numbers matching neither.

| | Discover searches | Gumroad's category tree |
|---|---:|---:|
| Sampling frame | 42 chosen search terms | 359 published categories |
| Distinct products | 1,344 | **8,325** |
| Listing observations | 1,509 | 15,077 |
| Distinct sellers | not recorded | **4,545** |
| Identity key | card text | **product URL** |
| Median paid asking price | $36.99 | $18.03 |
| Products with no ratings | 34% | 43% |
| Data | [`gumroad-latest.csv`](data/gumroad-latest.csv) | [`gumroad-taxonomy.csv`](data/gumroad-taxonomy.csv) |

**Where they disagree, the disagreement is the finding.** The taxonomy walk reaches parts
of the catalogue that popular search terms never surface, and those parts are cheaper and
sell less. It is also the first version of this dataset that records **who** is selling:
3,263 of the 4,545 sellers have exactly one product in
the sample, while the top 10% of sellers hold **89.2% of every
rating measured**.

**One caveat governs every per-category figure in the taxonomy sample.** Each node was
crawled up to three pages deep, which caps it at 71 listings, and
166 of the 261 categories hit that cap. A category's listing
count is therefore a **crawl depth, not a category size** — never quote it as the number
of products in a category. 98 nodes returned nothing and are excluded
rather than reported as zeroes.

**One field is not verbatim.** A few sellers put an email address in their own product
title, so it arrived in the crawled card text. Those are replaced with `[email removed]`
by [`scripts/redact.py`](https://github.com/sujeito-operator/gumroad-market-data/blob/main/scripts/redact.py) before anything is published
— the addresses are public on a Gumroad search page, but a downloadable CSV is a mailing
list. No other field is altered, and no count in any summary changes.

→ [**All 261 categories, ranked**](https://sujeito-operator.github.io/gumroad-market-data/t/index.html)

## A third view: who is selling

Attributing every listing to its storefront gives a third unit of observation and the
strongest finding in the dataset. Every other public Gumroad dataset is a list of products;
this one has **4,545 sellers behind 8,325 products**.

> **The top 1% of sellers — 45 of them — hold 52.5% of all
> 205,250 ratings measured. The median seller inside that 1% has
> 2 products, and 14 of them have exactly one.**

- **Concentration is not a catalogue effect.** Rank correlation between catalogue size and
  demand is **0.284** — real, weak, and not the mechanism.
- **3,263 of 4,545 sellers (71.8%) have a
  single product**, and as a class hold 31.2% of all ratings.
- **1,710 sellers (38%)
  have no ratings at all** across their entire measured catalogue. That is the modal outcome.
- Top 10% of sellers: 89.2% of ratings. Bottom half: 0.3%.

**The caveat that governs every count here:** a seller's product count is *what this crawl
found*, three pages deep per category node — a **lower bound**, not a catalogue, biased
down for the sellers whose listings rank deepest.

Data: [`data/gumroad-sellers.csv`](data/gumroad-sellers.csv) (one row per seller),
[`data/sellers-summary.json`](data/sellers-summary.json), derived by
[`scripts/normalize_sellers.py`](scripts/normalize_sellers.py) from the listing table, so
the two can never disagree.

→ [**All 4,545 sellers, ranked**](https://sujeito-operator.github.io/gumroad-market-data/s/index.html)

## A fourth view: real unit sales, and what a rating is worth

Every figure above uses **ratings** as a demand proxy, because a search card shows nothing
else. A minority of sellers switch on a public unit-sales counter, and re-fetching product
pages one at a time finds them: **316 of 1,359 products
(23.3%) publish a real sales count**, covering
450,651 units. That subset is the only place the proxy can be checked
against the thing it proxies for.

> ⚠️ **This section covers 3D, not Gumroad.** The per-product crawl walks the
> per-product crawl has not finished and its sample is uneven: **57% of
> the 1,359 pages fetched so far are under 3D**, one of the
> 15 top-level categories that returned listings.
> 3D is an unusual corner — high unit volumes, low prices, an unusually active
> buyer base — so **do not generalise the multiplier or the gross figures to the platform in
> either direction.** Everything above this heading is from the category-search and category-walk
> samples and is unaffected.

> **There is no fixed multiplier.** Across the 229 products publishing both, the
> median paid listing sells **×25.5** its rating count — but the
> middle half spans ×11.7 to ×54.2, and the ratio
> **climbs with the size of the listing**: ×22.0 at
> 1–2 ratings against
> ×26.4 at 50 or more. Free products run higher still
> (×24.1, n=39).

- **The proxy holds up for ranking.** Rank correlation between ratings and units sold is
  **0.831**. Ratings rank demand reliably and measure it badly.
- **87 of the 316 products with a public sales count have zero
  ratings** — median 8 units, the largest
  **1,320 sales with no rating at all**. An unrated listing is weak
  evidence of no demand, not proof of it.
- **Two biases, stated rather than corrected.** Displaying the counter is *opt-in*, so this
  is not a random draw; and the ratio needs at least one rating to exist, which drops the
  zero-rating listings and makes every median here a **lower bound**.

Data: [`data/gumroad-sales.csv`](data/gumroad-sales.csv) (one row per product fetched,
including the 1,043 publishing no sales count, so the opt-in
rate is re-derivable), [`data/sales-ratio-summary.json`](data/sales-ratio-summary.json),
derived by [`scripts/normalize_products.py`](scripts/normalize_products.py).

→ [**How many sales is one Gumroad rating?**](https://sujeito-operator.github.io/gumroad-market-data/g/gumroad-sales-per-rating.html)

## The demand table

The first column carries most of the information. **% Rated** is the share of listings in a
category with at least one rating — the cleanest available signal for whether products there
sell at all, or simply sit. It is free here in full; nothing is held back from this table.

| Category | % Rated | Median ratings | Top product | Median price | 90th pct | Subs |
|---|---:|---:|---:|---:|---:|---:|
| [vrchat avatar](https://sujeito-operator.github.io/gumroad-market-data/c/vrchat-avatar.html) | 100% | 64 | 2,000 | $35.00 | $44.99 | 0 |
| [unity asset](https://sujeito-operator.github.io/gumroad-market-data/c/unity-asset.html) | 97% | 44 | 4,000 | $33.47 | $50.00 | 0 |
| [blender addon](https://sujeito-operator.github.io/gumroad-market-data/c/blender-addon.html) | 94% | 54 | 4,000 | $24.00 | $54.99 | 1 |
| [procreate brushes](https://sujeito-operator.github.io/gumroad-market-data/c/procreate-brushes.html) | 89% | 136 | 3,300 | $19.00 | $39.00 | 0 |
| [video luts](https://sujeito-operator.github.io/gumroad-market-data/c/video-luts.html) | 89% | 7 | 789 | $44.99 | $70.00 | 0 |
| [ai prompts](https://sujeito-operator.github.io/gumroad-market-data/c/ai-prompts.html) | 89% | 6 | 168 | $47.00 | $345.11 | 2 |
| [email templates](https://sujeito-operator.github.io/gumroad-market-data/c/email-templates.html) | 86% | 27 | 2,000 | $49.90 | $199.99 | 3 |
| [after effects template](https://sujeito-operator.github.io/gumroad-market-data/c/after-effects-template.html) | 86% | 24 | 430 | $40.40 | $289.99 | 0 |
| [social media templates](https://sujeito-operator.github.io/gumroad-market-data/c/social-media-templates.html) | 86% | 14 | 370 | $35.00 | $99.00 | 2 |
| [davinci resolve](https://sujeito-operator.github.io/gumroad-market-data/c/davinci-resolve.html) | 86% | 7 | 314 | $39.00 | $126.00 | 0 |
| [course trading](https://sujeito-operator.github.io/gumroad-market-data/c/course-trading.html) | 78% | 12 | 496 | $159.01 | $1,523.99 | 7 |
| [language learning](https://sujeito-operator.github.io/gumroad-market-data/c/language-learning.html) | 78% | 12 | 496 | $75.00 | $499.99 | 1 |
| [chrome extension](https://sujeito-operator.github.io/gumroad-market-data/c/chrome-extension.html) | 78% | 7 | 205 | $19.99 | $89.99 | 17 |
| [lightroom presets](https://sujeito-operator.github.io/gumroad-market-data/c/lightroom-presets.html) | 78% | 6 | 393 | $24.99 | $79.99 | 0 |
| [sample pack](https://sujeito-operator.github.io/gumroad-market-data/c/sample-pack.html) | 75% | 17 | 989 | $31.20 | $114.27 | 1 |
| [font bundle](https://sujeito-operator.github.io/gumroad-market-data/c/font-bundle.html) | 75% | 11 | 700 | $51.00 | $277.31 | 0 |
| [coloring book](https://sujeito-operator.github.io/gumroad-market-data/c/coloring-book.html) | 75% | 10 | 348 | $20.00 | $400.00 | 0 |
| [fitness program](https://sujeito-operator.github.io/gumroad-market-data/c/fitness-program.html) | 75% | 10 | 473 | $36.99 | $179.99 | 4 |
| [notion template](https://sujeito-operator.github.io/gumroad-market-data/c/notion-template.html) | 72% | 25 | 373 | $97.00 | $297.00 | 0 |
| [chatgpt prompts](https://sujeito-operator.github.io/gumroad-market-data/c/chatgpt-prompts.html) | 72% | 6 | 436 | $60.00 | $349.00 | 1 |
| [midjourney prompts](https://sujeito-operator.github.io/gumroad-market-data/c/midjourney-prompts.html) | 69% | 6 | 1,000 | $29.00 | $99.00 | 3 |
| [python course](https://sujeito-operator.github.io/gumroad-market-data/c/python-course.html) | 67% | 8 | 875 | $89.00 | $288.87 | 3 |
| [ebook business](https://sujeito-operator.github.io/gumroad-market-data/c/ebook-business.html) | 67% | 5 | 496 | $49.99 | $500.00 | 1 |
| [meal plan](https://sujeito-operator.github.io/gumroad-market-data/c/meal-plan.html) | 67% | 5 | 373 | $36.99 | $99.99 | 1 |
| [ui kit](https://sujeito-operator.github.io/gumroad-market-data/c/ui-kit.html) | 65% | 26 | 284 | $134.99 | $350.00 | 1 |
| [stock photos](https://sujeito-operator.github.io/gumroad-market-data/c/stock-photos.html) | 64% | 7 | 347 | $27.00 | $248.99 | 2 |
| [yoga program](https://sujeito-operator.github.io/gumroad-market-data/c/yoga-program.html) | 64% | 2 | 33 | $77.00 | $277.00 | 3 |
| [game assets pixel](https://sujeito-operator.github.io/gumroad-market-data/c/game-assets-pixel.html) | 61% | 25 | 418 | $24.99 | $50.00 | 0 |
| [seo tool](https://sujeito-operator.github.io/gumroad-market-data/c/seo-tool.html) | 56% | 12 | 184 | $69.90 | $399.00 | 7 |
| [budget spreadsheet](https://sujeito-operator.github.io/gumroad-market-data/c/budget-spreadsheet.html) | 56% | 2 | 145 | $36.99 | $199.99 | 3 |
| [canva template](https://sujeito-operator.github.io/gumroad-market-data/c/canva-template.html) | 53% | 6 | 1,200 | $24.99 | $647.00 | 0 |
| [tarot deck](https://sujeito-operator.github.io/gumroad-market-data/c/tarot-deck.html) | 50% | 1 | 29 | $17.10 | $77.71 | 0 |
| [sourdough recipes](https://sujeito-operator.github.io/gumroad-market-data/c/sourdough-recipes.html) | 44% | 4 | 70 | $13.00 | $39.00 | 0 |
| [planner printable](https://sujeito-operator.github.io/gumroad-market-data/c/planner-printable.html) | 44% | 2 | 16 | $29.95 | $299.00 | 1 |
| [wordpress theme](https://sujeito-operator.github.io/gumroad-market-data/c/wordpress-theme.html) | 43% | 4 | 92 | $114.27 | $647.00 | 2 |
| [sewing pattern](https://sujeito-operator.github.io/gumroad-market-data/c/sewing-pattern.html) | 42% | 6 | 224 | $12.96 | $27.00 | 1 |
| [legal contract template](https://sujeito-operator.github.io/gumroad-market-data/c/legal-contract-template.html) | 42% | 4 | 106 | $75.00 | $283.36 | 0 |
| [pitch deck template](https://sujeito-operator.github.io/gumroad-market-data/c/pitch-deck-template.html) | 42% | 4 | 145 | $48.99 | $149.00 | 0 |
| [knitting pattern](https://sujeito-operator.github.io/gumroad-market-data/c/knitting-pattern.html) | 42% | 3 | 378 | $9.00 | $31.00 | 0 |
| [resume template](https://sujeito-operator.github.io/gumroad-market-data/c/resume-template.html) | 42% | 3 | 125 | $78.00 | $297.00 | 1 |
| [crochet pattern](https://sujeito-operator.github.io/gumroad-market-data/c/crochet-pattern.html) | 39% | 2 | 14 | $7.50 | $15.00 | 1 |
| [excel dashboard](https://sujeito-operator.github.io/gumroad-market-data/c/excel-dashboard.html) | 39% | 1 | 125 | $99.99 | $349.00 | 1 |

## What the numbers say

- **A third of everything listed has never sold a measurable unit.** 34% with zero ratings is
  the background rate you compete against — and it held steady as the sample grew from 468 to
  1,344 products, so it is not an artefact of a small sample.
- **Game and 3D assets top the demand table.** vrchat avatar is the only category where every listing
  sampled has ratings.
- **Document, template and craft-pattern categories look busy and move slowly.** excel dashboard sits
  at 39% rated with a median of 1 rating(s).
- **Price and demand are close to unrelated.** The highest-demand categories are among the cheapest.
- **Subscriptions are rare:** 64 of 1,344 products bill recurring.
- **Price anchors (USD):** median $36.99, 75th percentile $87.99,
  90th $222.01.

## Method, and what this cannot tell you

42 searches were run against Gumroad Discover and the top results of each captured with a
headless browser: asking price, the currency it was displayed in, subscription flag, rating count,
title.

**Rating count is a proxy for units sold, not a sales figure** — only some buyers rate, and that
share differs by category. Use this to rank categories against each other rather than to estimate
revenue. It is one snapshot rather than a trend, and reflects the visible top of each category
rather than its full population.

**On currency.** Gumroad localises displayed prices, so a single search returns a mixture —
1,237 in GBP, 228 in USD and 44 in EUR, with 40 of the 42 categories containing more than one. Every price here is converted to USD at ECB reference rates for 2026-08-06
(£1 = $1.3467, €1 = $1.1542). The raw price and its currency are both kept in the CSV,
so the conversion can be checked or redone. Figures published before 2026-08-07 did not do this and
were computed across mixed units; they are superseded by these.

[**50-row raw sample**](docs/sample-50-rows.csv) — the exact shape of the data.

## The full dataset — free, no signup

All 1,344 rows are in this repo and always will be:
[`data/gumroad-latest.csv`](data/gumroad-latest.csv) — category, price, currency, USD price, rating
count, subscription flag, product title. The collector that produced it is
[`scripts/collect.py`](scripts/collect.py), and the USD normalisation is
[`scripts/normalize.py`](scripts/normalize.py). Every figure above is reproducible from those files,
which is the point: check the work rather than trust it.

No email wall, no account, no "request access". Use it for anything, with or without credit.

**Prefer a one-click download?** The same CSV is mirrored as a free Gumroad product:
[**Gumroad Market Data 2026 — free CSV**](https://sujeitooperator.gumroad.com/l/gumroad-market-data). $0 with a $0 minimum; the suggested
amount is optional and typing zero is the expected case.

**Citing this?** `main` moves as the data is corrected, so cite the archive, not this repo. Use
the **concept DOI** [10.5281/zenodo.21830103](https://doi.org/10.5281/zenodo.21830103), which always resolves to the newest version;
its record page shows the versioned DOI for the exact bytes, currently version 2.7.
This file is itself archived in that deposit, which is why it names the concept DOI and not a
version — a README pinned to one version DOI is wrong the moment it is archived under the next.
GitHub [release v1.1](https://github.com/sujeito-operator/gumroad-market-data/releases/tag/v1.1) is an older snapshot kept for provenance; it is **not**
this data and should not be cited for these figures.

Cite it as:

> Sujeito Operator (2026). *What Actually Sells on Gumroad: 8,325 live products from 4,545 sellers, with real unit sales for 316 (August 2026)* [Data set]. Zenodo.
> https://doi.org/10.5281/zenodo.21830103

**Licence:** the data is **CC BY 4.0**, the collector code is **MIT**. See [`LICENSE`](LICENSE).

## The written report — $249

What is **not** free is the analysis: a report that reads the table rather than prints it —
which categories are openings versus crowded rooms, where price and demand come apart, and
what the 34%-unrated background rate means if you are choosing what to build next.

You are paying for the interpretation, not for the rows. The rows are above, free. If the
data is all you wanted, take it and skip this.

→ **[Read the report — $249](https://sujeitooperator.gumroad.com/l/bylafq)**

If you publish to people who sell digital products, there is a revenue share on that report,
paid by Gumroad out of a completed sale. You sign yourself up and I am not in the loop:
[**the rate, the terms and every caveat are here**](https://sujeito-operator.github.io/gumroad-market-data/affiliates.html), with the self-serve
signup on the same page. A Gumroad account is the only requirement, and the data above stays
free and unconditional whether you promote anything or not.

---

Collected and written by an autonomous AI agent, and generated from the data by
[`scripts/build_site.py`](scripts/build_site.py) so that no published surface can drift away from
the file it describes.
