# Methodology

## Data

3,720 unique TripAdvisor reviews of 23 hotels (15 Miami, 8 Orlando), dated May 2017 to September 2026,
collected with the [Apify TripAdvisor Reviews actor](https://apify.com/maxcopell/tripadvisor-reviews). 2,670
are English (72%), 1,016 Spanish (27%) and 34 in other languages. See [`/data/README.md`](../data/README.md) for
how the scrape was run and why raw exports are not published.

**Language is defined by `originalLanguage`, not `lang`.** TripAdvisor machine-translates some reviews into
English and reports the translated language in `lang`. Labeling by `lang` initially counted 1 Spanish review; the
real number was 45 in the first scrape. Later scrapes disabled machine translation entirely so Spanish reviews
arrive in the original language.

**Getting Spanish volume took deliberate scraping.** The actor returns English reviews first, then other languages,
so shallow scrapes are almost all English. Spanish only appears at depth (roughly past the first 100 reviews per
hotel), which is why the scrape inputs use a cap of 150-200 per hotel.

## Pipeline

| Step | Script | What it does |
|---|---|---|
| 1 | `src/parse_reviews.py` | Merge all Apify exports, dedupe by review ID, clean text, keep hotel metadata |
| 2 | `src/aspect_sentiment.py` | Split reviews into sentences; tag each with an aspect and a sentiment (models below) |
| 3 | `src/build_dashboard_data.py` | Apply quality filters, define "complaint", write dashboard tables |
| 4 | `src/reputation_scoring.py` | Per-hotel scores, aspect profiles, quarterly trends |
| 5 | `src/language_comparison.py` | English vs Spanish comparison with hotel control and bootstrap intervals |

### Aspect tagging

Each sentence (12+ characters) is embedded with
[`paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
and compared by cosine similarity with a prototype vector for each of eight aspects (staff, room, location,
cleanliness, food, amenities, price, noise). Each prototype averages English and Spanish seed phrases written for
the aspect. A sentence gets the best-matching aspect if its similarity is at least 0.45; the dashboard keeps only
tags at 0.55 or above (see validation).

### Sentiment

Each sentence is scored by
[`lxyuan/distilbert-base-multilingual-cased-sentiments-student`](https://huggingface.co/lxyuan/distilbert-base-multilingual-cased-sentiments-student),
a distilled multilingual model returning positive / neutral / negative probabilities. Sentence score =
P(positive) + 0.5 x P(neutral), from 0 (negative) to 1 (positive). **Review sentiment** is the
length-weighted mean of its sentence scores. For aspect polarity, a sentence counts as neutral unless
|P(positive) - P(negative)| exceeds 0.4.

**Complaints** are tagged sentences that are clearly negative (P(negative) >= 0.5) *and* sit in a review rated 3
stars or lower, or that are overwhelmingly negative (>= 0.85) in any review. Sentence sentiment alone was too
noisy for this: about half of its "negative" sentences sat in 5-star reviews and were mostly model errors.

### Reputation score (0-10)

```
score = 0.40 * (avg_sentiment * 10)
      + 0.30 * (avg_rating / 5 * 10)
      + 0.15 * recency_factor
      + 0.15 * volume_factor

recency_factor = clip(10 - days_since_latest_review / 365 * 5, 0, 10)
volume_factor  = clip((log10(tripadvisor_review_count) - 2) / 2 * 10, 0, 10)
```

Sentiment and rating are averaged over the **trailing 24 months** only, so every hotel is compared over the same
period. Volume uses TripAdvisor's own review total for the hotel (298 to 24,951 here), not how many reviews we
scraped. Hotels are ranked within their city. Strengths are the aspects a hotel is most consistently praised for
(at least 8 mentions); complaints are aspects with at least 2 complaint sentences.

### English vs Spanish comparison

The measure is each language's **share of aspect comments** that falls on each aspect (each language sums to
100%). Raw "share of reviews mentioning X" is misleading because Spanish reviews are shorter (median 3 vs 5
sentences) and so mention fewer topics of every kind.

Spanish reviews also cluster in particular hotels, so English shares are **re-weighted to the Spanish hotel mix**:
the question becomes "if English guests stayed at the same hotels as Spanish guests, would the split differ?"
95% intervals come from 2,000 bootstrap resamples of reviews within each hotel x language cell. Each result is
graded:

- **Robust**: interval clears zero by at least 0.2 points, the difference points the same way in at least 75%
  of the 13 hotels with 30+ Spanish tagged sentences, and the topic is at least 5% of comments.
- **Suggestive**: interval excludes zero but fails the other tests.
- **None**: interval includes zero.

## Validation

I hand-checked 80 randomly drawn aspect-tagged sentences (40 English, 40 Spanish) from a 25% pilot run. Aspect
accuracy at the 0.45 threshold was 79% (78% English, 80% Spanish); sentiment accuracy 85% (82% / 88%). Raising the
similarity threshold to 0.55 lifted aspect accuracy to about 90% on the same sentences. The main errors were
generic sentences ("Overall, a wonderful experience") forced into an aspect, and neutral factual sentences scored
as positive or negative.

**Limits of this check:** the labels were made by the AI assistant that helped build the pipeline, not by
independent annotators; 40 sentences per language leaves roughly +/-12 points of uncertainty; and only tagged
sentences were checked, so recall (sentences that should have been tagged but weren't) is unmeasured.

## Corrections made along the way

Each of these was found by checking outputs rather than trusting that the code ran:

1. **Zero-shot sentiment returned random scores.** The base `xlm-roberta-large` checkpoint has no trained
   classification head, so every review scored about 0.33. (Switching to an NLI-tuned checkpoint fixed the scores
   but not the next problem.)
2. **The NLI approach was unusable at scale and gave wrong answers.** Scoring 14 "the X was great/terrible"
   hypotheses per review took 12 seconds per review (about 13 hours for the dataset), and "the price was great"
   scored near 1.0 for any positive review that never mentioned price. Replaced by sentence-level tagging (about
   25 minutes for the whole dataset).
3. **Language was mislabeled** (`lang` vs `originalLanguage`, above).
4. **The reputation score measured scraping depth.** Averaging over every scraped review made recency correlate
   0.81 with the final score, because deeply scraped hotels reached back to 2017; volume saturated at 10 for every
   hotel. Fixed with the 24-month window and TripAdvisor's own review counts.
5. **An early "Spanish reviews are happier" signal was a small-sample artifact** (88% vs 77% 5-star on 500 reviews;
   74% vs 76% on the full data).
6. **Raw mention rates were confounded by review length and by hotel mix.** The apparent amenities and food
   differences disappeared once hotel mix was controlled; see the comparison above.

## Limitations

- **Orlando coverage:** 8 of 15 targeted Orlando hotels are included; the rest are scheduled for the next scrape.
  Orlando has 234 Spanish reviews versus 782 in Miami, so Orlando-specific language comparisons are weaker.
- **Uneven Spanish coverage:** 9 hotels have 50+ Spanish reviews; per-hotel Spanish views are only reliable for those.
- **Complaints are scarce:** about 86% of reviews are 4-5 stars, and only 67 sentences meet the complaint
  definition, so per-hotel complaint lists are short and noise dominates.
- **What, not why:** the comparison shows different emphasis, not its cause. Trip type is not controlled for.
- **Multiple comparisons:** eight aspects were tested with unadjusted intervals, so borderline results may be chance.
- **Mixed sentences:** a sentence praising one thing and criticizing another is tagged with only one aspect.
- **Cross-language sentiment calibration:** Spanish reviews score more positive than English ones (0.78 vs 0.73)
  despite identical star ratings, which may reflect model calibration rather than guest attitudes.

## Citations

- Sanh et al., 2019. [DistilBERT, a distilled version of BERT](https://arxiv.org/abs/1910.01108)
- Reimers & Gurevych, 2019. [Sentence-BERT](https://arxiv.org/abs/1908.10084)
- Reimers & Gurevych, 2020. [Making Monolingual Sentence Embeddings Multilingual using Knowledge Distillation](https://arxiv.org/abs/2004.09813)
