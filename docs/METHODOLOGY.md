# Methodology

## Data Source

Guest reviews for 22 Miami and Orlando hotels, scraped from TripAdvisor via the
[Apify TripAdvisor Reviews actor](https://apify.com/maxcopell/tripadvisor-reviews). See
[`/data/README.md`](../data/README.md) for the full acquisition process and known coverage gaps.

## Sentiment Analysis

**Model:** [`joeddav/xlm-roberta-large-xnli`](https://huggingface.co/joeddav/xlm-roberta-large-xnli) —
an XLM-RoBERTa-large checkpoint fine-tuned for natural language inference (NLI) on XNLI, used here in
zero-shot classification mode.

**Why this model:** zero-shot classification via NLI requires a checkpoint whose classification head was
actually trained for entailment. An earlier iteration of this pipeline used the base `xlm-roberta-large`
checkpoint directly — that model has *no* trained classification head, so the zero-shot pipeline silently
produced near-uniform, meaningless scores (~0.33 across all three labels, i.e. random). Switching to the
XNLI-tuned checkpoint fixed this; see the [correctness check](#correctness-checks) below.

**Candidate labels:** `["positive", "negative", "neutral"]`, single-label (`multi_label=False`).
`sentiment_score` is the model's confidence in the top predicted label; `sentiment_label` is that label.

**Citations:**
- Conneau et al., 2019. [*Unsupervised Cross-lingual Representation Learning at Scale*](https://arxiv.org/abs/1911.02116) (XLM-RoBERTa)
- Conneau et al., 2018. [*XNLI: Evaluating Cross-lingual Sentence Representations*](https://arxiv.org/abs/1809.05053)

## Topic Modeling

**Model:** [BERTopic](https://maartengr.github.io/BERTopic/), using `all-MiniLM-L6-v2` sentence
embeddings, with a `CountVectorizer(stop_words='english', ngram_range=(1,2), min_df=2)` for topic
representation, fit separately per language (English and Spanish are modeled independently; other
languages are excluded from topic assignment).

**Why explicit stopword filtering:** BERTopic's default vectorizer in the version pinned here does not
strip English stopwords automatically when a custom `embedding_model` is supplied. Without the explicit
`vectorizer_model`, topic keywords were dominated by function words ("the", "and", "she") rather than
meaningful terms. Passing an explicit `CountVectorizer` with `stop_words='english'` fixed this.

**Citation:** Grootendorst, 2022. [*BERTopic: Neural topic modeling with a class-based TF-IDF procedure*](https://arxiv.org/abs/2203.05794)

## Reputation Score

Computed per hotel on a 0-10 scale:

```
score = 0.40 * (avg_sentiment * 10)      # guest sentiment (mean sentiment_score, 0-1 -> 0-10)
      + 0.30 * (avg_rating / 5 * 10)     # star rating (1-5 -> 0-10)
      + 0.15 * recency_factor            # recent reviews weighted higher
      + 0.15 * volume_factor             # confidence from review count
```

Where:
```
recency_factor = clip(10 - (avg_days_old / 365 * 5), 0, 10)
volume_factor  = min(10, 1 + ln(review_count) * 2)
```

`avg_days_old` is the mean age (in days, relative to the time the score is computed) of a hotel's
reviews. The `recency_factor` is clipped to `[0, 10]` because the raw formula goes negative for reviews
averaging more than 2 years old, which would otherwise let stale reviews actively subtract from the
score rather than simply contributing nothing.

Hotels are ranked 1-N separately within each city (`competitor_rank`), not pooled across both markets.

## Correctness Checks

Two issues were caught and fixed during development by inspecting actual output rather than trusting
that the pipeline ran without errors:

1. **Degenerate sentiment scores** — all-`~0.333` scores across 898 reviews revealed the base
   `xlm-roberta-large` checkpoint's classification head was randomly initialized (visible in the
   `transformers` load report as `MISSING` weights for `classifier.*`), not loaded from a trained model.
   Fixed by switching to the XNLI-finetuned checkpoint (see above).
2. **Stopword topic keywords** — BERTopic's default vectorizer surfaced "the"/"and"/"she" as top topic
   terms. Fixed with an explicit `CountVectorizer(stop_words='english')`.

## Known Limitations

- **Language skew:** ~99.9% of the current dataset is English-language reviews (897 of 898). Spanish
  coverage is minimal (1 review) — nowhere near enough for the originally planned EN/ES comparative
  analysis. A larger, more deliberately bilingual scrape is planned.
- **Orlando sample size:** only 7 of 15 targeted Orlando hotels returned reviews (vs. 15/15 for Miami),
  so Orlando's competitor ranking rests on a thinner, less balanced sample than Miami's.
- **BERTopic outlier bucket:** ~31% of English reviews (279/897) fall into BERTopic's `-1` outlier topic
  (too unique to cluster) — normal behavior for this algorithm, not a data quality issue, but it means
  topic-level praise/complaint summaries don't cover every review.
