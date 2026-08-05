# What actually sells on Gumroad — measured

971 live Gumroad products across 27 categories, collected 2026-08-05.

**32% of products in the sample have zero ratings.** The share of listings carrying any
rating separates categories that transact from ones that don't — 100% for VRChat avatars
down to 39% for Excel dashboards.

- **Full findings and the complete demand table (free):** https://sujeito-operator.github.io/gumroad-market-data/
- **50-row raw sample:** [`docs/sample-50-rows.csv`](docs/sample-50-rows.csv)
- **Full 971-row dataset + PDF report:** https://sujeitooperator.gumroad.com/l/bylafq

## Method

Searches run against Gumroad Discover; top results of each captured with a headless
browser. For each product: asking price, currency, subscription flag, rating count, title.

Rating count is a **proxy for units sold, not a sales figure** — only some buyers rate and
that share varies by category. Use it to rank categories against each other, not to
estimate revenue. One snapshot, not a trend; the visible top of each category, not its
full population.
