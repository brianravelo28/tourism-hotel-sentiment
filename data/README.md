# Data Acquisition

Review data is scraped from TripAdvisor with the
[Apify TripAdvisor Reviews actor](https://apify.com/maxcopell/tripadvisor-reviews). Raw exports are **not** committed
(see below); only the derived tables under [`/dashboard/data`](../dashboard/data) are published.

## Reproducing the scrape

1. Create an [Apify](https://apify.com) account and open the actor.
2. For each batch you want (table below), switch the actor input to JSON view and paste the matching
   `apify_input_*.json` file. These inputs request Spanish reviews, keep them untranslated, and set a per-hotel cap.
   Pasting only the URLs from [`hotel_urls.txt`](hotel_urls.txt) would give a shallow, mostly English sample.
3. Export each run as JSON and save it in this folder. Apify's default `dataset_*.json` file name works.
4. Run `python src/parse_reviews.py`. It merges every export in this folder (plus `raw_reviews.json`, the original
   first scrape, if present), dedupes by review ID, and writes `raw_reviews.csv` and `hotels.csv`.

| Input file | Hotels | Cap per hotel | Purpose |
|---|---|---|---|
| `apify_input_spanish_test.json` | 5 Miami | 100 | First test of Spanish scraping |
| `apify_input_spanish_depth_check.json` | 2 Miami | 200 | Check whether the Spanish backlog runs deeper than 100 |
| `apify_input_orlando_check.json` | 1 Orlando (Hilton) | 30 | Check that a hotel that returned nothing earlier now works |
| `apify_input_miami_batch1.json` | 9 Miami | 150 | Main Miami scrape |
| `apify_input_orlando_batch1.json` | 8 Orlando | 150 | Main Orlando scrape |
| `apify_input_orlando_batch2_next_month.json` | 7 Orlando | 150 | **Not run yet** (waiting on next month's Apify credit) |

Every input sets `reviewsLanguages: ["es"]`, `disableMachineTranslations: true` (Spanish reviews arrive in the original
language) and `scrapeReviewerInfo: false` (no reviewer details are collected). In practice the results are a mix of
Spanish and English reviews, and the Spanish count keeps growing as the cap rises, so check the language counts of
each export rather than assuming.

## Coverage note

`hotel_urls.txt` covers 30 target hotels (15 Miami, 15 Orlando) but holds 29 URLs: the URL for Mr. C Miami Coconut
Grove (hotel ID 15809999) wasn't kept, though that hotel is in the data. The published dataset covers **23** hotels
(15 Miami, 8 Orlando).

The very first scrape (`raw_reviews.json`, up to 50 reviews per hotel, no language setting) returned nothing for 8
Orlando hotels, most likely because the free-tier credit ran out mid-run; a later re-run of Hilton Orlando alone worked.
Hilton Orlando is now included. The 7 remaining Orlando hotels are in the batch 2 file and haven't been scraped yet, so
Orlando has a smaller sample than Miami, which the [README](../README.md#limitations) and the dashboard note.

## Why raw data isn't committed

Raw exports (`raw_reviews.json`, `dataset_*.json`) and the intermediates built from them (`raw_reviews.csv`,
`hotels.csv`, `interim/`) stay local through `.gitignore`. The first export, `raw_reviews.json`, includes reviewer
details (names, usernames, profile links, avatar images); the later exports don't, because they set
`scrapeReviewerInfo: false`.

The pipeline never carries reviewer fields forward. The published tables in `dashboard/data` contain only review
text, rating, date, language, trip type, hotel information and derived sentiment and aspect fields. Review and sentence
text is published as written, so it can mention staff or other people by name.
