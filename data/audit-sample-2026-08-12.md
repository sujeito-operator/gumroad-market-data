# a-real-storefront.gumroad.com — what a UK/EU buyer is actually charged

> **This is a worked sample of the report, not a report about you.**
>
> It was produced by running the audit against one real Gumroad storefront on
> 2026-08-12 — nine products, walked logged out from a UK address, each page
> loaded cold and each checkout read at the pay step. **Every figure below is
> the figure that was measured.** No price, gap, percentage, median, peer count
> or range has been adjusted.
>
> What has been removed is the seller. Their name and their product titles are
> replaced with `Product 1`, `Product 2` and so on, because they did not ask to
> be an advertisement. Your report names your products.

Walked 2026-08-12 06:04 UTC, logged out, from a UK address, as an ordinary
buyer: each product page loaded cold, the buy control clicked, the pay step read
and nothing submitted. No order was placed and no form was filled in.

**9 product(s) on the storefront. 9 gave a page price the pay step confirms. 9 of those charge the buyer more than the page says.**

The widest gap is **Product 1** — the page shows £71.82, the buyer pays £87.40, 21.7% more.

| product | page says | buyer pays | gap | what the pay step itemised |
|---|---|---|---|---|
| Product 1 | £71.82 | £87.40 | 21.7% more | £14.52 added at the pay step. page shows £71.82, pay step totals £87.40 |
| Product 2 | £71.82 | £87.40 | 21.7% more | £14.52 added at the pay step. page shows £71.82, pay step totals £87.40 |
| Product 3 | £71.82 | £87.40 | 21.7% more | £14.52 added at the pay step. page shows £71.82, pay step totals £87.40 |
| Product 4 | £71.82 | £87.40 | 21.7% more | £14.52 added at the pay step. page shows £71.82, pay step totals £87.40 |
| Product 5 | £71.82 | £87.40 | 21.7% more | £14.52 added at the pay step. page shows £71.82, pay step totals £87.40 |
| Product 6 | £21.47 | £25.80 | 20.2% more | £4.34 added at the pay step. page shows £21.47, pay step totals £25.80 |
| Product 7 | £200.65 | £243.20 | 21.2% more | £40.57 added at the pay step. page shows £200.65, pay step totals £243.20 |
| Product 8 | £51.83 | £63.00 | 21.6% more | £10.48 added at the pay step. page shows £51.83, pay step totals £63.00 |
| Product 9 | £70.34 | £85.00 | 20.8% more | £14.22 added at the pay step. page shows £70.34, pay step totals £85.00 |

## How to read this

Gumroad is the merchant of record and adds VAT on top of the advertised price
for UK and EU buyers rather than inside it. That is not a fault of yours and
there is nothing to fix in your account — the number is set by where the buyer
is, not by you. What you control is whether the page says so. A line in the
description saying tax is added at checkout costs nothing and removes the
surprise at the moment of paying.

You cannot see any of this from inside your own account: the dashboard reports
in your own currency and your own visits are localised to where you are.

A row with no figure is a row where nothing in the pay step confirmed the price
on the page — usually a page priced in one currency that the pay step converts.
Rather than quote a comparison between two different currencies, it is left
blank. Every number above was confirmed against the checkout subtotal.

## What comparable products in your own category charge

**4 product(s) could be compared. 0 are priced below the median of products in the same category with comparable demand.**

| product | you charge | comparable median | difference | peers | your ratings | range |
|---|---|---|---|---|---|---|
| Product 2 | $97.00 | $59.59 | $-37.41 | 6 | 36 | $12.01–$500.00 |
| Product 5 | $97.00 | $59.59 | $-37.41 | 6 | 32 | $12.01–$500.00 |
| Product 1 | $97.00 | $45.06 | $-51.94 | 11 | 11 | $8.01–$500.00 |
| Product 3 | $97.00 | $19.02 | $-77.97 | 6 | 22 | $8.01–$500.00 |

### How this comparison is built, and what it is not

Peers are products in **your own leaf category** whose rating count is between half and double the rating count of the product being compared. The demand window is what makes it a comparison rather than a list of prices: a category median on its own is dominated by products nobody buys.

**Ratings are a lower bound on units sold, not a sales count.** An unknown share of buyers leave one. They order products by demand; they cannot size a market, and nothing here multiplies a price by a rating count.

**This is not advice to raise your price to the median.** It is the distribution you are priced inside. A product can be deliberately cheap. What the number tells you is whether the position is one you chose.

Your own price and rating count above were read from your live product page while this report was being written, not from the category crawl the peers come from — so they are what your page says today even if you changed the price this morning.

**Why some of your products are here and others are not.** The peer set comes from a crawl of Gumroad's own category listings, which rank by popularity, so a product of yours appears above only if it was ranking in its category when that crawl ran. Gumroad publishes no category on the product page itself, so for anything outside the crawl there is no honest way to say what it should be compared against — and it is left out rather than compared against a set it may not belong to. The practical effect is that this section covers your better-selling products and is quiet about the long tail.

### The 5 product(s) with no comparison, and why

- **Product 4** — not in the 2026-08-05 category crawl, so it has no known category or peers
- **Product 6** — not in the 2026-08-05 category crawl, so it has no known category or peers
- **Product 7** — no comparable set: the category is too broad, or fewer than 5 products in it have within half to double this product's rating count, or it is under 10 ratings and has not yet shown the demand that would make its price evidence of anything
- **Product 8** — not in the 2026-08-05 category crawl, so it has no known category or peers
- **Product 9** — not in the 2026-08-05 category crawl, so it has no known category or peers

These are listed rather than dropped. A report that quietly shows fewer rows than your storefront has products is making a claim it did not measure.

## Sources

- https://a-real-storefront.gumroad.com/l/product-1 — read 2026-08-12T06:00:28+00:00
- https://a-real-storefront.gumroad.com/l/product-2 — read 2026-08-12T06:00:40+00:00
- https://a-real-storefront.gumroad.com/l/product-3 — read 2026-08-12T06:00:52+00:00
- https://a-real-storefront.gumroad.com/l/product-4 — read 2026-08-12T06:01:04+00:00
- https://a-real-storefront.gumroad.com/l/product-5 — read 2026-08-12T06:01:16+00:00
- https://a-real-storefront.gumroad.com/l/product-6 — read 2026-08-12T06:01:28+00:00
- https://a-real-storefront.gumroad.com/l/product-7 — read 2026-08-12T06:01:40+00:00
- https://a-real-storefront.gumroad.com/l/product-8 — read 2026-08-12T06:01:51+00:00
- https://a-real-storefront.gumroad.com/l/product-9 — read 2026-08-12T06:02:03+00:00
