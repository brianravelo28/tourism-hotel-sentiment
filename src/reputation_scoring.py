"""Hotel-level reputation scores, aspect profiles and sentiment trends.

Score inputs are restricted to the trailing SCORE_WINDOW_MONTHS. Without that, "recency" and "volume" end up
measuring how deep each hotel happened to be scraped (a deep scrape reaches back years) rather than anything
about the hotel. Volume uses TripAdvisor's own review total for the hotel, on a log scale.

Reads dashboard/data/processed_reviews.csv and aspect_mentions.csv (from build_dashboard_data.py).
Writes reputation_scores.csv, aspect_by_hotel.csv and sentiment_trends.csv next to them.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SCORE_WINDOW_MONTHS = 24  # scores use only the trailing window so hotels are compared over the same period
MIN_ASPECT_MENTIONS = 8   # need this many tagged sentences before an aspect can be a strength/complaint
MIN_COMPLAINT_MENTIONS = 2

data_path = Path(__file__).parent.parent / 'dashboard' / 'data'
df = pd.read_csv(data_path / 'processed_reviews.csv', parse_dates=['published_date'])
mentions = pd.read_csv(data_path / 'aspect_mentions.csv')
print(f'Loaded {len(df)} reviews and {len(mentions)} aspect mentions')

# Reference date is the newest review in the dataset (not today's date) so scores are reproducible.
ref_date = df['published_date'].max()
window_start = ref_date - pd.DateOffset(months=SCORE_WINDOW_MONTHS)
hotels = pd.read_csv(data_path / 'hotels.csv')
print(f'Reference date: {ref_date.date()} | score window starts {window_start.date()}')
all_reviews = df
df = df[df.published_date >= window_start]
print(f'{len(df)} of {len(all_reviews)} reviews fall inside the score window')

# ============================================================
# 1. Aggregate by hotel
# ============================================================
agg = df.groupby(['hotel_id', 'hotel_name', 'city']).agg(
    avg_sentiment=('sentiment_score', 'mean'),
    avg_rating=('rating', 'mean'),
    review_count=('review_id', 'count'),
    en_count=('language', lambda x: (x == 'en').sum()),
    es_count=('language', lambda x: (x == 'es').sum()),
    days_since_latest=('published_date', lambda x: (ref_date - x.max()).days),
).reset_index()
agg = agg.merge(hotels[['hotel_id', 'ta_review_count', 'ta_rating']], on='hotel_id', how='left')
agg['reviews_analyzed_total'] = agg.hotel_id.map(all_reviews.groupby('hotel_id').size())
agg['other_count'] = agg.review_count - agg.en_count - agg.es_count

# ============================================================
# 2. Reputation score (0-10): sentiment 40%, rating 30%, recency 15%, volume 15%
# ============================================================
agg['recency_factor'] = np.clip(10 - agg.days_since_latest / 365 * 5, 0, 10)
# TripAdvisor total reviews on a log scale: ~100 -> 0, ~10,000 -> 10
agg['volume_factor'] = np.clip((np.log10(agg.ta_review_count) - 2) / 2 * 10, 0, 10)
agg['reputation_score'] = (
    0.40 * agg.avg_sentiment * 10
    + 0.30 * (agg.avg_rating / 5) * 10
    + 0.15 * agg.recency_factor
    + 0.15 * agg.volume_factor
).round(2)
agg['competitor_rank'] = agg.groupby('city').reputation_score.rank(ascending=False, method='min').astype(int)

# ============================================================
# 3. Aspect profile per hotel, and strengths / complaints derived from it
# ============================================================
prof = mentions.groupby(['hotel_id', 'aspect']).agg(
    mentions=('score', 'size'),
    mean_score=('score', 'mean'),
    pct_positive=('polarity', lambda s: (s == 'pos').mean()),
    pct_negative=('polarity', lambda s: (s == 'neg').mean()),
    negative_mentions=('polarity', lambda s: (s == 'neg').sum()),
    complaint_mentions=('is_complaint', 'sum'),
    en_mentions=('language', lambda s: (s == 'en').sum()),
    es_mentions=('language', lambda s: (s == 'es').sum()),
).reset_index()
prof = prof.merge(agg[['hotel_id', 'hotel_name', 'city']], on='hotel_id')

def top_aspects(hotel_prof, kind):
    eligible = hotel_prof[hotel_prof.mentions >= MIN_ASPECT_MENTIONS]
    if kind == 'praise':
        pick = eligible.sort_values(['pct_positive', 'mentions'], ascending=False).head(3)
    else:  # complaints: aspects with repeated clear complaints (see is_complaint in build_dashboard_data.py)
        pick = hotel_prof[hotel_prof.complaint_mentions >= MIN_COMPLAINT_MENTIONS].sort_values(
            'complaint_mentions', ascending=False).head(3)
    return '; '.join(pick.aspect) if len(pick) else ''

agg['top_praise'] = agg.hotel_id.map(lambda h: top_aspects(prof[prof.hotel_id == h], 'praise'))
agg['top_complaints'] = agg.hotel_id.map(lambda h: top_aspects(prof[prof.hotel_id == h], 'complaints'))

# ============================================================
# 4. Quarterly sentiment trends by city and language (hotel-level series are too sparse)
# ============================================================
tr = all_reviews[all_reviews.language.isin(['en', 'es'])].copy()
tr['quarter'] = tr.published_date.dt.to_period('Q').astype(str)
trends = tr.groupby(['quarter', 'city', 'language']).agg(
    avg_sentiment=('sentiment_score', 'mean'), review_count=('review_id', 'count')).reset_index()

# ============================================================
# 5. Save
# ============================================================
cols = ['hotel_id', 'hotel_name', 'city', 'reputation_score', 'competitor_rank', 'avg_sentiment', 'avg_rating',
        'review_count', 'en_count', 'es_count', 'other_count', 'reviews_analyzed_total', 'ta_review_count', 'ta_rating',
        'recency_factor', 'volume_factor', 'top_praise', 'top_complaints']
agg.sort_values(['city', 'competitor_rank'])[cols].round(
    {'avg_sentiment': 3, 'avg_rating': 2, 'recency_factor': 2, 'volume_factor': 2}).to_csv(data_path / 'reputation_scores.csv', index=False, encoding='utf-8')
prof.round(3).to_csv(data_path / 'aspect_by_hotel.csv', index=False, encoding='utf-8')
trends.round({'avg_sentiment': 3}).to_csv(data_path / 'sentiment_trends.csv', index=False, encoding='utf-8')

print(f'\nSaved reputation_scores.csv ({len(agg)} hotels), aspect_by_hotel.csv ({len(prof)} rows), '
      f'sentiment_trends.csv ({len(trends)} rows)')
for city in sorted(agg.city.unique()):
    print(f'\n{city}:')
    print(agg[agg.city == city].nsmallest(3, 'competitor_rank')[
        ['hotel_name', 'reputation_score', 'competitor_rank', 'top_praise', 'top_complaints']].to_string(index=False))
print(f'\nScore range: {agg.reputation_score.min():.2f} - {agg.reputation_score.max():.2f}')
