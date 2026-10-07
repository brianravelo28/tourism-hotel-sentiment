# Hotel Reputation Dashboard: Miami & Orlando*

**[Live dashboard](https://hotel-reputation-dashboard.onrender.com/)** (free Render tier - sleeps after 15
minutes idle, so the first load can take about a minute to wake up)

*An active project, more data to come: the Orlando sample and Spanish coverage are still growing, so read the
findings below as preliminary.

**Do English- and Spanish-speaking hotel guests care about different things? An NLP pipeline and interactive
dashboard built on 3,720 TripAdvisor reviews of 23 South Florida and Orlando hotels, 27% of them written in Spanish.**

Scrapes reviews, tags every sentence with an aspect (staff, location, cleanliness, ...) and a sentiment in both
languages, ranks hotels within their city, and tests whether the two language groups emphasize different things
once review length and hotel choice are controlled for.

## What it found

- **Spanish-speaking guests put more of their comments on location and less on cleanliness.** Comparing the same
  hotels, location takes 4.0 percentage points more of Spanish comments (95% CI +1.6 to +6.5) and cleanliness
  3.2 points less (CI -5.0 to -1.4). Cleanliness points the same way in 12 of the 13 hotels with enough Spanish reviews.
- **Star ratings don't show it.** Both groups average 4.48 stars. The difference is in *what they write about*.
- **Most apparent differences weren't real.** Raw mention rates suggested large gaps in staff, cleanliness,
  amenities and food, but Spanish reviews are shorter and cluster in particular hotels. After controlling for both,
  amenities, food and room show no reliable difference, and staff, price and noise are only suggestive.
- **Complaints are rare and mostly about noise** (36 of 67 clear complaints). About 86% of reviews are 4-5 stars.
- **Top-ranked hotels:** InterContinental Miami (9.11/10) in Miami and Hilton Orlando (9.05/10) in Orlando.

The [methodology doc](docs/METHODOLOGY.md) covers how each result was graded, what was hand-validated
(aspect tagging ~90% accurate at the threshold used), and six errors found and fixed along the way, including a
reputation score that turned out to measure how deep each hotel was scraped.

## The dashboard

Four tabs, built with Plotly Dash:

- **Rankings**: hotels ranked within a city on a 0-10 reputation score. Click a hotel to see a card with its
  strengths, complaints and a guest quote, and an aspect heatmap below shows how every hotel is described
- **Hotel Detail**: one hotel's aspect-by-aspect tone with real guest quotes and complaints, filterable by review
  language. The score, rating and sentiment figures recompute for the language you pick
- **English vs Spanish**: the comparison above, with confidence intervals and an honest "how much to trust this" panel
- **Trends**: sentiment by quarter and language

## How it works

| Step | Script | What it does |
|---|---|---|
| 1 | `src/parse_reviews.py` | Merge Apify exports, dedupe, label language by what the guest actually wrote |
| 2 | `src/aspect_sentiment.py` | Split into sentences; tag aspect (multilingual embeddings) and sentiment (distilled multilingual model) |
| 3 | `src/build_dashboard_data.py` | Quality filters, complaint definition, dashboard tables |
| 4 | `src/reputation_scoring.py` | Per-hotel scores over a common 24-month window, aspect profiles, trends |
| 5 | `src/language_comparison.py` | English vs Spanish shares with hotel control and bootstrap intervals |

## Tech stack

`Python` · `Hugging Face Transformers` · `sentence-transformers` · `PyTorch` · `pandas` · `NumPy` ·
`Plotly Dash` · `Render` (a Dockerfile is also included for Docker hosts)

## Repo structure

```
├── README.md
├── requirements.txt        full pipeline dependencies
├── LICENSE                 MIT
├── render.yaml             Render deployment config
├── data/                   scrape inputs and acquisition notes (raw exports are gitignored)
├── src/                    the five pipeline scripts above
├── notebooks/eda.ipynb     exploratory analysis with executed charts
├── dashboard/              Dash app, its lean requirements.txt, Dockerfile, and the published data tables
└── docs/                   METHODOLOGY.md, DATA_SCHEMA.md (with pipeline diagram)
```

## Run the dashboard

The dashboard reads the pre-built tables in `dashboard/data/`, so it needs only a small dependency set:

```bash
cd dashboard
pip install -r requirements.txt
python app.py
```

Then open http://localhost:7860.

## Deploy (Render)

`render.yaml` is a Render Blueprint for the free tier: in Render choose **New + > Blueprint**, pick this repo, and
deploy. It builds from `dashboard/` (Python 3.11, one gunicorn worker) and health-checks `/healthz`. The app uses
about 130 MB of memory, well inside the 512 MB free limit. Free services sleep after 15 minutes idle, so the first
visit after a quiet spell takes about a minute to wake. `dashboard/Dockerfile` is an alternative for Docker hosts
such as Hugging Face Spaces.

## Rebuild the data

Needs the full `requirements.txt` and the raw Apify exports in `data/` (see [`data/README.md`](data/README.md)).

```bash
pip install -r requirements.txt
python src/parse_reviews.py
python src/aspect_sentiment.py       # ~25 min for 3,700 reviews on CPU
python src/build_dashboard_data.py
python src/reputation_scoring.py
python src/language_comparison.py
```

## Limitations

- **Orlando is partial:** 8 of 15 targeted Orlando hotels are in (7 more are queued for the next scrape), and
  Spanish coverage is thinner there (234 reviews vs 782 in Miami).
- **Shows what differs, not why.** Trip type (family, business) is not yet controlled for.
- **Complaints are scarce**, so per-hotel complaint lists are short.
- **Aspect and sentiment labels are machine-generated.** The hand check behind the accuracy figures was done by the
  AI assistant that helped build this, not independent annotators.

More in [docs/METHODOLOGY.md](docs/METHODOLOGY.md#limitations).

## License

MIT, see [LICENSE](LICENSE).
