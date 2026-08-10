# Hotel Reputation & Sentiment Dashboard — Miami/Orlando

**An end-to-end NLP pipeline that turns raw TripAdvisor reviews into a ranked, interactive
competitor-benchmarking dashboard for the South Florida & Orlando hotel market.**

Scrapes guest reviews → runs multilingual zero-shot sentiment analysis and topic modeling → rolls
everything up into a per-hotel reputation score → serves it all through a live Plotly Dash app.

## Why this exists

Hotel operators and revenue managers care about one question their star rating alone can't answer:
*what, specifically, are guests saying — and how does that stack up against the hotel down the street?*
This project builds a repeatable pipeline to answer that at scale: 898 reviews across 22 hotels,
sentiment-scored, topic-clustered, and ranked within their local competitive set.

## What it does

- **Scrapes** TripAdvisor reviews for a target list of hotels via Apify
- **Sentiment-scores** every review with a multilingual zero-shot NLI model (XLM-RoBERTa-XNLI) —
  built multilingual from the start, not translated after the fact
- **Clusters** reviews into topics with BERTopic to surface recurring praise/complaint themes
- **Computes** a weighted 0-10 reputation score per hotel (sentiment, star rating, review recency,
  review volume) and ranks hotels within their city
- **Visualizes** all of it in a 3-tab interactive dashboard: competitor ranking table, sentiment
  trend lines, and topic frequency breakdown

## Key Findings

- 898 reviews analyzed across 22 hotels (15 Miami, 7 Orlando)
- Sentiment skews strongly positive (812 positive / 83 negative / 3 neutral), consistent with a
  4.6★-average dataset — and cross-validates against star rating independently (see
  [`notebooks/eda.ipynb`](notebooks/eda.ipynb))
- Top-ranked hotel in Miami: **Homewood Suites by Hilton Miami-Airport/Blue Lagoon** (9.50/10)
- Top-ranked hotel in Orlando: **Holiday Inn Orlando International Dr-ICON by IHG** (9.37/10)
- Staff service is the dominant praise driver in both markets — front-desk staff are frequently
  called out by name in positive reviews

## Tech Stack

`Python` · `Transformers` (XLM-RoBERTa-XNLI) · `BERTopic` · `sentence-transformers` · `Pandas` ·
`Plotly Dash` · `Docker` (Hugging Face Spaces deployment)

## Repo Structure

```
├── README.md              this file
├── requirements.txt        full pipeline deps (torch, transformers, bertopic, ...)
├── LICENSE                 MIT
├── .gitignore
├── data/                    acquisition docs + hotel URL list (raw scrapes are gitignored, not committed)
├── src/                     pipeline: scrape parsing -> sentiment/topics -> reputation scoring
├── notebooks/               EDA notebook, executed with output plots
├── dashboard/                the Dash app + its own lean requirements.txt + Dockerfile
└── docs/                    methodology, model citations, data schema + pipeline diagram
```

## Running the Dashboard

The dashboard only needs a lean dependency set (`pandas`, `plotly`, `dash`, `gunicorn`) — it reads
the already-generated CSVs in `dashboard/data/` rather than re-running the ML pipeline.

```bash
cd dashboard
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:7860`.

## Regenerating the Data Pipeline

Requires the full `requirements.txt` at the repo root (`torch`, `transformers`, `bertopic`, ...).

```bash
pip install -r requirements.txt
python src/parse_reviews.py         # data/raw_reviews.json -> data/raw_reviews.csv
python src/sentiment_topics.py      # -> dashboard/data/processed_reviews.csv
python src/reputation_scoring.py    # -> dashboard/data/reputation_scores.csv, sentiment_trends.csv
```

See [`data/README.md`](data/README.md) for how to reproduce the raw scrape itself.

## Methodology & Data

- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) — model choices, the reputation score formula, model
  citations, and two real correctness bugs caught and fixed during development
- [`docs/DATA_SCHEMA.md`](docs/DATA_SCHEMA.md) — table schemas and a pipeline flow diagram
- [`notebooks/eda.ipynb`](notebooks/eda.ipynb) — exploratory analysis with plots

## Limitations

- **Language coverage:** the current dataset is ~99.9% English. A Spanish-language data refresh is
  planned to enable the originally-scoped bilingual comparison of guest priorities.
- **Orlando sample size:** only 7 of 15 targeted Orlando hotels returned reviews from the scraper
  (vs. 15/15 for Miami) — the Orlando ranking should be read as preliminary until the dataset is
  expanded. Full detail in [`data/README.md`](data/README.md#coverage-note).

## License

MIT — see [LICENSE](LICENSE).
