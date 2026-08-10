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

`hotel_urls.txt` lists 30 target hotels (15 Miami, 15 Orlando). The scrape run used to build the current
committed dataset returned reviews for **22 of the 30** (15 Miami, 7 Orlando) — the remaining 8 URLs,
mostly Orlando, returned zero reviews, likely due to Apify free-tier scrape limits. See the
[Limitations section of the root README](../README.md#limitations) for how this affects the Orlando
ranking's reliability. A follow-up scrape with a paid Apify plan is planned to close this gap and to add
Spanish-language coverage (the current dataset is ~99.9% English).

## Why raw data isn't committed

`raw_reviews.json` and `raw_reviews.csv` are excluded via `.gitignore` because the raw Apify export
includes reviewer PII (names, usernames, profile links, avatar images) scraped from public TripAdvisor
pages. The pipeline strips all of that out by the time data reaches `processed_reviews.csv` — only
`review_id`, `hotel_id`, review text/rating/date, and derived sentiment/topic fields survive. Those
derived files are small and PII-free, so they're committed under `/dashboard/data`.
