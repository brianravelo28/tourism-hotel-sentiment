# Data Acquisition

This project's review data is scraped from TripAdvisor using the
[Apify TripAdvisor Reviews actor](https://apify.com/maxcopell/tripadvisor-reviews). Raw scrape output
is **not** committed to this repository (see below) — only the derived, PII-free datasets under
[`/dashboard/data`](../dashboard/data) are published.

## Reproducing the scrape

1. Create an [Apify](https://apify.com) account.
2. Open the [TripAdvisor Reviews actor](https://apify.com/maxcopell/tripadvisor-reviews).
3. Paste the URLs from [`hotel_urls.txt`](hotel_urls.txt) into the actor's input and run it.
4. Export the results as JSON and save as `data/raw_reviews.json`.
5. Run `python src/parse_reviews.py` to clean the export into `data/raw_reviews.csv`.

## Coverage note

`hotel_urls.txt` lists 30 target hotels (15 Miami, 15 Orlando). The published dataset covers **23** of them
(15 Miami, 8 Orlando). The first scrape hit the Apify free-tier limit and returned nothing for 8 Orlando hotels;
a later run with more credit recovered one (Hilton Orlando) and deepened the rest. The 7 remaining Orlando hotels
are in `apify_input_orlando_batch2_next_month.json`. Orlando therefore has a smaller sample than Miami, which the
[README](../README.md#limitations) and the dashboard note.

## Why raw data isn't committed

`raw_reviews.json` and `raw_reviews.csv` are excluded via `.gitignore` because the raw Apify export
includes reviewer PII (names, usernames, profile links, avatar images) scraped from public TripAdvisor
pages. The pipeline strips all of that out by the time data reaches `processed_reviews.csv` — only
`review_id`, `hotel_id`, review text/rating/date, and derived sentiment and aspect fields survive. Those
derived files are small and PII-free, so they're committed under `/dashboard/data`.

## Apify input files

The `apify_input_*.json` files are the exact actor inputs used for each scrape run. All of them set
`reviewsLanguages: ["es"]` (the actor returns English first, then Spanish, so a deep cap is needed to reach
meaningful Spanish volume), `disableMachineTranslations: true` (so Spanish reviews arrive in the original
language), and `scrapeReviewerInfo: false` (so no reviewer PII is collected). `*_batch2_next_month.json`
covers Orlando hotels not yet scraped.
