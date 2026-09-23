"""Turn the raw aspect-sentiment output (data/interim) into the tables the dashboard reads.

Applies two quality rules learned from a hand-check of 80 tagged sentences:
  * keep only aspect tags whose similarity is >= MIN_ASPECT_SIM (aspect accuracy ~79% -> ~90%)
  * treat a sentence as neutral when the sentiment model isn't decisive (|p_pos - p_neg| <= NEUTRAL_BAND)

Writes dashboard/data/processed_reviews.csv and dashboard/data/aspect_mentions.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd

MIN_ASPECT_SIM = 0.55
NEUTRAL_BAND = 0.40
# A 'complaint' is a tagged sentence that is clearly negative AND sits in a review rated <= LOW_RATING stars, or is
# overwhelmingly negative anywhere. Sentence sentiment alone is noisy: half its negatives sit in 5-star reviews.
LOW_RATING = 3
COMPLAINT_P_NEG_LOW_REVIEW = 0.5
COMPLAINT_P_NEG_ANY_REVIEW = 0.85

root = Path(__file__).parent.parent
interim = root / 'data' / 'interim'
out = root / 'dashboard' / 'data'
out.mkdir(parents=True, exist_ok=True)

reviews = pd.read_csv(interim / 'review_sentiment.csv')
mentions = pd.read_csv(interim / 'aspect_mentions.csv')
print(f'Reviews: {len(reviews)} | raw tagged sentences: {len(mentions)}')

mentions = mentions[mentions.aspect_sim >= MIN_ASPECT_SIM].copy()
mentions['aspect'] = mentions.aspect.replace({'pool': 'amenities'})  # older runs used 'pool'
gap = mentions.p_pos - mentions.p_neg
mentions['polarity'] = np.where(gap > NEUTRAL_BAND, 'pos', np.where(gap < -NEUTRAL_BAND, 'neg', 'neu'))
mentions = mentions.merge(reviews[['review_id', 'rating']], on='review_id', how='left')
mentions['is_complaint'] = (((mentions.rating <= LOW_RATING) & (mentions.p_neg >= COMPLAINT_P_NEG_LOW_REVIEW))
                            | (mentions.p_neg >= COMPLAINT_P_NEG_ANY_REVIEW))
print(f'Kept {len(mentions)} tagged sentences at similarity >= {MIN_ASPECT_SIM} ({int(mentions.is_complaint.sum())} complaints)')

mention_cols = ['review_id', 'hotel_id', 'hotel_name', 'city', 'language', 'published_date',
                'aspect', 'sentence', 'score', 'polarity', 'aspect_sim', 'p_pos', 'p_neg', 'rating', 'is_complaint']
mentions = mentions[mention_cols].round({'score': 3, 'aspect_sim': 3, 'p_pos': 3, 'p_neg': 3})
mentions.to_csv(out / 'aspect_mentions.csv', index=False, encoding='utf-8')

reviews = reviews.drop(columns=['is_machine_translated'], errors='ignore').round({'sentiment_score': 3})
reviews.to_csv(out / 'processed_reviews.csv', index=False, encoding='utf-8')
print(f'Wrote {out / "processed_reviews.csv"} and {out / "aspect_mentions.csv"}')

# Hotel metadata from the parser (TripAdvisor's own review totals and rating; contains no reviewer data)
hotels = pd.read_csv(root / 'data' / 'hotels.csv')
hotels.to_csv(out / 'hotels.csv', index=False, encoding='utf-8')
print(f'Wrote {out / "hotels.csv"} ({len(hotels)} hotels)')
