---
title: Hotel Reputation Dashboard - Miami/Orlando
emoji: 🏨
colorFrom: blue
colorTo: teal
sdk: docker
app_port: 7860
pinned: false
---

# Hotel Review Sentiment & Reputation Dashboard (Miami/Orlando)

An interactive dashboard analyzing hotel guest reviews in Miami and Orlando using multilingual sentiment
analysis and topic modeling, with a composite reputation score used to rank competitors within each city.

## Methodology

**Data source:** TripAdvisor guest reviews, collected via the [Apify TripAdvisor Reviews scraper](https://apify.com/maxcopell/tripadvisor-reviews)
for 22 hotels across Miami and Orlando.

**Sentiment analysis:** Zero-shot multilingual classification using
[`joeddav/xlm-roberta-large-xnli`](https://huggingface.co/joeddav/xlm-roberta-large-xnli), an XLM-RoBERTa
checkpoint fine-tuned for natural language inference, run against the candidate labels `positive` /
`negative` / `neutral`.

**Topic modeling:** [BERTopic](https://maartengr.github.io/BERTopic/) with `all-MiniLM-L6-v2` sentence
embeddings, English stopword filtering, and unigram/bigram vectorization, fit separately per language.

**Reputation score formula** (0-10 scale, computed per hotel):

```
score = 0.40 * (avg_sentiment * 10)      # guest sentiment
      + 0.30 * (avg_rating / 5 * 10)     # star rating
      + 0.15 * recency_factor            # weight toward recent reviews
      + 0.15 * volume_factor             # confidence from review count
```

Hotels are ranked 1-N separately within Miami and within Orlando.

## Key Findings

- **898 reviews** analyzed across **22 hotels** (15 Miami, 7 Orlando)
- Overall sentiment skews strongly positive: **812 positive / 83 negative / 3 neutral** — consistent with
  a dataset averaging 4.6/5 stars
- Top-ranked hotel in Miami: **Homewood Suites by Hilton Miami-Airport/Blue Lagoon** (9.50/10)
- Top-ranked hotel in Orlando: **Holiday Inn Orlando International Dr-ICON by IHG** (9.37/10)
- Miami's average reputation score (8.88) edges out Orlando's (8.48), though Orlando's ranking is
  based on a smaller, less balanced hotel sample (see Limitations)
- Recurring praise themes center on **staff service** (front-desk staff frequently named individually)
  and general **hotel quality/location**

## Limitations

- **Language coverage:** the current dataset is ~99.9% English-language reviews. A Spanish-language
  data refresh (via an expanded Apify scrape) is planned to enable a bilingual comparison of guest
  priorities, reflecting South Florida's bilingual traveler base.
- **Orlando sample size:** 7 of the 15 originally targeted Orlando hotels returned reviews from the
  scraper (vs. 15/15 for Miami), so the Orlando competitor ranking has a thinner sample and should be
  treated as less statistically robust than Miami's until the dataset is expanded.

## Data Schema

**`data/raw_reviews.csv`** — raw scraped reviews
```
review_id | hotel_id | hotel_name | city | review_text | rating | language | trip_type | published_date | source
```

**`data/processed_reviews.csv`** — reviews with sentiment + topic assigned
```
review_id | hotel_id | hotel_name | city | review_text | rating | language |
sentiment_score | sentiment_label | topic_id | topic_name | trip_type | published_date
```

**`data/reputation_scores.csv`** — one row per hotel
```
hotel_id | hotel_name | city | reputation_score | competitor_rank | avg_sentiment |
review_count | en_count | es_count | top_complaints | top_praise
```

**`data/sentiment_trends.csv`** — monthly time series per hotel
```
hotel_id | month | avg_sentiment | review_count | trend_direction
```

## Running Locally

Two dependency sets are provided:

- **`requirements.txt`** — full pipeline (scraping parsing, sentiment analysis, topic modeling).
  Requires `torch`/`transformers`/`bertopic` and is only needed to regenerate the processed CSVs.
- **`requirements-app.txt`** — lean dependency set to just run the dashboard against the already-generated
  CSVs in `data/`. This is what's used in the deployed Docker image.

```bash
pip install -r requirements-app.txt
python app.py
```

Then open `http://localhost:7860`.

## Regenerating the Data Pipeline

```bash
pip install -r requirements.txt
python parse_reviews.py         # raw_reviews.json -> raw_reviews.csv
python sentiment_topics.py      # raw_reviews.csv -> processed_reviews.csv
python reputation_scoring.py    # processed_reviews.csv -> reputation_scores.csv, sentiment_trends.csv
```

## Stack

Python · Transformers (XLM-RoBERTa-XNLI) · BERTopic · Pandas · Plotly Dash · Docker (Hugging Face Spaces)
