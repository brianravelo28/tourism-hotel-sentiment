import json
import pandas as pd
from pathlib import Path
import re

# Load JSON
data_path = Path(__file__).parent / 'data'
json_file = data_path / 'raw_reviews.json'

with open(json_file, 'r', encoding='utf-8') as f:
    reviews = json.load(f)

print(f"Loaded {len(reviews)} reviews from JSON")

# Parse into DataFrame
rows = []
for review in reviews:
    place_info = review.get('placeInfo', {})
    city = place_info.get('locationString', '').split(', ')[-2] if place_info.get('locationString') else 'Unknown'

    row = {
        'review_id': review.get('id'),
        'hotel_id': review.get('locationId'),
        'hotel_name': place_info.get('name', 'Unknown'),
        'city': city,
        'review_text': review.get('text', ''),
        'rating': review.get('rating'),
        'language': review.get('lang', 'en'),
        'trip_type': review.get('tripType'),
        'published_date': review.get('publishedDate'),
        'source': 'tripadvisor'
    }
    rows.append(row)

df = pd.DataFrame(rows)
print(f"\nInitial count: {len(df)} reviews")
print(f"Columns: {df.columns.tolist()}")

# Data cleaning
# 1. Remove reviews < 20 characters
df = df[df['review_text'].str.len() >= 20].copy()
print(f"After removing short reviews (< 20 chars): {len(df)} reviews")

# 2. Remove duplicates (same hotel + same text)
df = df.drop_duplicates(subset=['hotel_id', 'review_text'], keep='first')
print(f"After removing duplicates: {len(df)} reviews")

# 3. Normalize whitespace
df['review_text'] = df['review_text'].str.replace(r'\s+', ' ', regex=True).str.strip()

# 4. Remove rows with missing critical fields
df = df.dropna(subset=['review_text', 'rating', 'hotel_name'])
print(f"After removing rows with missing critical fields: {len(df)} reviews")

# Summary stats
print(f"\n=== DATA SUMMARY ===")
print(f"Total reviews: {len(df)}")
print(f"Unique hotels: {df['hotel_id'].nunique()}")
print(f"Cities: {df['city'].unique().tolist()}")
print(f"\nRating distribution:")
print(df['rating'].value_counts().sort_index())
print(f"\nLanguage distribution:")
print(df['language'].value_counts())
print(f"\nAverage rating: {df['rating'].mean():.2f}")

# Save to CSV
output_file = data_path / 'raw_reviews.csv'
df.to_csv(output_file, index=False, encoding='utf-8')
print(f"\n✓ Saved to: {output_file}")
print(f"Shape: {df.shape}")
