import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

data_path = Path(__file__).parent / 'data'
df = pd.read_csv(data_path / 'processed_reviews.csv', parse_dates=['published_date'])

print(f"Loaded {len(df)} processed reviews")

# ============================================================
# 1. Aggregate by hotel
# ============================================================
today = pd.Timestamp.now()

agg = df.groupby(['hotel_id', 'hotel_name', 'city']).agg(
    avg_sentiment=('sentiment_score', 'mean'),
    avg_rating=('rating', 'mean'),
    review_count=('review_id', 'count'),
    en_count=('language', lambda x: (x == 'en').sum()),
    es_count=('language', lambda x: (x == 'es').sum()),
    avg_days_old=('published_date', lambda x: (today - x).dt.days.mean())
).reset_index()

print(f"\nAggregated {len(agg)} hotels")

# ============================================================
# 2. Reputation Score Formula (0-10 scale)
# ============================================================
def recency_factor(days_old):
    factor = 10 - (days_old / 365 * 5)
    return np.clip(factor, 0, 10)

def volume_factor(review_count):
    factor = 1 + np.log(review_count) * 2
    return min(10, factor)

agg['recency_factor'] = agg['avg_days_old'].apply(recency_factor)
agg['volume_factor'] = agg['review_count'].apply(volume_factor)

agg['reputation_score'] = (
    0.40 * agg['avg_sentiment'] * 10 +
    0.30 * (agg['avg_rating'] / 5) * 10 +
    0.15 * agg['recency_factor'] +
    0.15 * agg['volume_factor']
).round(2)

# ============================================================
# 3. Rank hotels within each city
# ============================================================
agg['competitor_rank'] = agg.groupby('city')['reputation_score'].rank(
    ascending=False, method='min'
).astype(int)

agg = agg.sort_values(['city', 'competitor_rank']).reset_index(drop=True)

print("\nReputation scores calculated")
print(agg[['hotel_name', 'city', 'reputation_score', 'competitor_rank']].to_string(index=False))

# ============================================================
# 4. Top 3 complaints and top 3 praise per hotel
# ============================================================
def get_top_topics(hotel_df, sentiment_label, n=3):
    subset = hotel_df[
        (hotel_df['sentiment_label'] == sentiment_label) &
        (hotel_df['topic_id'] >= 0)
    ]
    if len(subset) == 0:
        return ''
    top_topics = subset['topic_name'].value_counts().head(n).index.tolist()
    return '; '.join(top_topics)

complaints = []
praise = []
for hotel_id in agg['hotel_id']:
    hotel_df = df[df['hotel_id'] == hotel_id]
    complaints.append(get_top_topics(hotel_df, 'negative', 3))
    praise.append(get_top_topics(hotel_df, 'positive', 3))

agg['top_complaints'] = complaints
agg['top_praise'] = praise

# ============================================================
# 5. Monthly sentiment trends
# ============================================================
df['month'] = df['published_date'].dt.to_period('M').astype(str)

trends = df.groupby(['hotel_id', 'month']).agg(
    avg_sentiment=('sentiment_score', 'mean'),
    review_count=('review_id', 'count')
).reset_index()

trends = trends.sort_values(['hotel_id', 'month'])

# trend_direction: compare each month's avg_sentiment to the previous month for that hotel
trends['trend_direction'] = trends.groupby('hotel_id')['avg_sentiment'].diff().apply(
    lambda x: 'up' if x > 0.01 else ('down' if x < -0.01 else 'flat')
)
trends['trend_direction'] = trends['trend_direction'].fillna('n/a')

print(f"\nMonthly trends calculated: {len(trends)} hotel-month rows")

# ============================================================
# 6. Save outputs
# ============================================================
reputation_cols = ['hotel_id', 'hotel_name', 'city', 'reputation_score', 'competitor_rank',
                   'avg_sentiment', 'review_count', 'en_count', 'es_count',
                   'top_complaints', 'top_praise']
agg_out = agg[reputation_cols]
agg_out.to_csv(data_path / 'reputation_scores.csv', index=False, encoding='utf-8')

trends_cols = ['hotel_id', 'month', 'avg_sentiment', 'review_count', 'trend_direction']
trends[trends_cols].to_csv(data_path / 'sentiment_trends.csv', index=False, encoding='utf-8')

print(f"\n=== DAY 3 COMPLETE ===")
print(f"Saved reputation_scores.csv: {len(agg_out)} hotels")
print(f"Saved sentiment_trends.csv: {len(trends)} rows")
print(f"\nTop 3 hotels by city:")
for city in agg_out['city'].unique():
    print(f"\n{city}:")
    top3 = agg_out[agg_out['city'] == city].nsmallest(3, 'competitor_rank')
    print(top3[['hotel_name', 'reputation_score', 'competitor_rank']].to_string(index=False))
