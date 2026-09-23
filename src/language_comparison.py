"""English vs Spanish: what do guests talk about?

Metric: for each language, the share of all aspect-tagged sentences that belong to each aspect ("share of aspect
talk"). This is independent of review length (Spanish reviews are much shorter, so raw mention rates mislead).

Hotel control: Spanish reviews cluster in particular hotels, so the English shares are re-weighted to the
Spanish hotel mix ("if English guests stayed at the same hotels as Spanish guests"). Confidence intervals come
from a bootstrap that resamples reviews within each hotel x language cell.

Reads dashboard/data/processed_reviews.csv and aspect_mentions.csv; writes language_aspects.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd

N_BOOT = 2000
MIN_SPANISH_SENTENCES_PER_HOTEL = 30   # hotels used for the direction-consistency check
CI_MARGIN = 0.002        # 'robust' needs the interval to clear zero by at least 0.2 percentage points
MIN_CONSISTENCY = 0.75   # ...and the same direction in at least 75% of the hotels compared
MIN_SHARE = 0.05         # ...and a topic that is at least 5% of aspect talk in one language (not a rare topic)

data_path = Path(__file__).parent.parent / 'dashboard' / 'data'
reviews = pd.read_csv(data_path / 'processed_reviews.csv')
reviews = reviews[reviews.language.isin(['en', 'es'])].reset_index(drop=True)
mentions = pd.read_csv(data_path / 'aspect_mentions.csv')
mentions = mentions[mentions.language.isin(['en', 'es'])]

aspects = sorted(mentions.aspect.unique())
# review x aspect matrix of tagged-sentence counts, aligned to `reviews`
counts = (mentions.groupby(['review_id', 'aspect']).size().unstack(fill_value=0)
          .reindex(columns=aspects).reindex(reviews.review_id).fillna(0).to_numpy())

hotels = reviews.hotel_id.unique()
cells = {(h, lang): counts[((reviews.hotel_id == h) & (reviews.language == lang)).to_numpy()]
         for h in hotels for lang in ('en', 'es')}


def cell_sums(rng=None):
    en, es = [], []
    for h in hotels:
        for lang, out in (('en', en), ('es', es)):
            c = cells[(h, lang)]
            if rng is not None and len(c):
                c = c[rng.integers(0, len(c), len(c))]
            out.append(c.sum(0) if len(c) else np.zeros(len(aspects)))
    return np.array(en), np.array(es)


def shares(sums_en, sums_es):
    es_share = sums_es.sum(0) / sums_es.sum()
    w = sums_es.sum(1) / sums_es.sum()                                       # Spanish hotel mix
    en_within = sums_en / np.maximum(sums_en.sum(1, keepdims=True), 1)       # English share inside each hotel
    return es_share, (w[:, None] * en_within).sum(0), sums_en.sum(0) / sums_en.sum()


es_share, en_adj, en_raw = shares(*cell_sums())
rng = np.random.default_rng(1)
boot = np.array([np.subtract(*shares(*cell_sums(rng))[:2]) for _ in range(N_BOOT)])   # ES - EN_adj
lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)

# direction consistency across hotels with enough Spanish talk
big = [h for h in hotels if cells[(h, 'es')].sum() >= MIN_SPANISH_SENTENCES_PER_HOTEL]
per_hotel = np.array([cells[(h, 'es')].sum(0) / cells[(h, 'es')].sum() - cells[(h, 'en')].sum(0) / cells[(h, 'en')].sum()
                      for h in big])

out = pd.DataFrame({
    'aspect': aspects,
    'en_share': en_raw, 'en_share_hotel_adjusted': en_adj, 'es_share': es_share,
    'raw_diff': es_share - en_raw, 'adjusted_diff': es_share - en_adj,
    'ci_low': lo, 'ci_high': hi,
})
out['reliable'] = (out.ci_low > 0) | (out.ci_high < 0)
out['hotels_same_direction'] = [(per_hotel[:, i] > 0).sum() if es_share[i] > en_adj[i] else (per_hotel[:, i] < 0).sum()
                                for i in range(len(aspects))]
out['hotels_compared'] = len(big)
consistent = out.hotels_same_direction / out.hotels_compared >= MIN_CONSISTENCY
clears = (out.ci_low > CI_MARGIN) | (out.ci_high < -CI_MARGIN)
common = np.maximum(out.en_share_hotel_adjusted, out.es_share) >= MIN_SHARE
out['evidence'] = np.where(clears & consistent & common, 'robust', np.where(out.reliable, 'suggestive', 'none'))
out['en_reviews'] = (reviews.language == 'en').sum()
out['es_reviews'] = (reviews.language == 'es').sum()
out['en_tagged'] = int(counts[(reviews.language == 'en').to_numpy()].sum())
out['es_tagged'] = int(counts[(reviews.language == 'es').to_numpy()].sum())
out = out.sort_values('adjusted_diff', ascending=False)
out.round(4).to_csv(data_path / 'language_aspects.csv', index=False, encoding='utf-8')

print(f'Reviews: en {out.en_reviews.iloc[0]}, es {out.es_reviews.iloc[0]} | hotels compared for consistency: {len(big)}')
print(out[['aspect', 'en_share', 'en_share_hotel_adjusted', 'es_share', 'adjusted_diff', 'ci_low', 'ci_high',
           'evidence', 'hotels_same_direction']].round(3).to_string(index=False))
