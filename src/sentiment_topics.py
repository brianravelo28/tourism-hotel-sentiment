import pandas as pd
from pathlib import Path
from transformers import pipeline
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
import warnings
import os

os.environ['TOKENIZERS_PARALLELISM'] = 'false'
warnings.filterwarnings('ignore')

# Load raw reviews
data_path = Path(__file__).parent.parent / 'data'
output_path = Path(__file__).parent.parent / 'dashboard' / 'data'
df = pd.read_csv(data_path / 'raw_reviews.csv')

print(f"Loaded {len(df)} reviews")
print(f"Languages: {df['language'].value_counts().to_dict()}")

# Initialize sentiment classifier (XLM-RoBERTa zero-shot)
print("\nLoading XLM-RoBERTa-XNLI model (CPU only)...")
try:
    classifier = pipeline('zero-shot-classification',
                          model='joeddav/xlm-roberta-large-xnli',
                          device=-1,
                          framework='pt')
    print("Model loaded successfully")
except Exception as e:
    print(f"Error loading model: {e}")
    raise

candidate_labels = ['positive', 'negative', 'neutral']

# Sentiment analysis function
def get_sentiment(text):
    try:
        result = classifier(text, candidate_labels, multi_label=False)
        return result['scores'][0], result['labels'][0]
    except Exception as e:
        print(f"  Warning: sentiment failed - {e}")
        return 0.5, 'neutral'

# Run sentiment analysis
print("\nRunning sentiment analysis...")
df['sentiment_score'] = 0.0
df['sentiment_label'] = 'neutral'

for idx, row in df.iterrows():
    if (idx + 1) % 100 == 0:
        print(f"  Processed {idx + 1}/{len(df)}")
    score, label = get_sentiment(row['review_text'])
    df.loc[idx, 'sentiment_score'] = score
    df.loc[idx, 'sentiment_label'] = label

print(f"Sentiment analysis complete")
print(f"Sentiment distribution:\n{df['sentiment_label'].value_counts()}")

# Topic modeling - separate by language
print("\nTopic modeling (English reviews)...")
en_df = df[df['language'] == 'en'].copy()

if len(en_df) > 5:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    vectorizer_model = CountVectorizer(stop_words='english', ngram_range=(1, 2), min_df=2)

    # English BERTopic
    topic_model_en = BERTopic(
        language='english',
        min_topic_size=5,
        nr_topics=8,
        embedding_model=embedding_model,
        vectorizer_model=vectorizer_model,
        verbose=False
    )

    topics_en, probs_en = topic_model_en.fit_transform(en_df['review_text'].tolist())
    en_df['topic_id'] = topics_en
    en_df['topic_name'] = en_df['topic_id'].apply(
        lambda x: topic_model_en.get_topic(x)[0][0] if x >= 0 else 'Unknown'
    )

    print(f"English topics identified: {en_df['topic_id'].max() + 1} topics")
    print(f"Topic distribution:\n{en_df['topic_id'].value_counts().head(10)}")

# Topic modeling - Spanish (if any)
print("\nTopic modeling (Spanish reviews)...")
es_df = df[df['language'] == 'es'].copy()

if len(es_df) >= 5:
    topic_model_es = BERTopic(
        language='spanish',
        min_topic_size=5,
        nr_topics=8,
        verbose=False
    )

    topics_es, probs_es = topic_model_es.fit_transform(es_df['review_text'].tolist())
    es_df['topic_id'] = topics_es
    es_df['topic_name'] = es_df['topic_id'].apply(
        lambda x: topic_model_es.get_topic(x)[0][0] if x >= 0 else 'Unknown'
    )

    print(f"Spanish topics identified: {es_df['topic_id'].max() + 1} topics")
else:
    print(f"Not enough Spanish reviews ({len(es_df)}) for topic modeling (need >= 5)")
    es_df['topic_id'] = -1
    es_df['topic_name'] = 'Insufficient Data'

# Merge back
df_processed = pd.concat([en_df, es_df], ignore_index=True)
df_processed = df_processed.sort_values('review_id').reset_index(drop=True)

# Fill missing topic data for non-English/Spanish reviews
other_reviews = df[~df['language'].isin(['en', 'es'])]
if len(other_reviews) > 0:
    for idx in other_reviews.index:
        df_processed.loc[df_processed['review_id'] == df.loc[idx, 'review_id'], 'topic_id'] = -1
        df_processed.loc[df_processed['review_id'] == df.loc[idx, 'review_id'], 'topic_name'] = 'Other Language'

# Select final columns
output_cols = ['review_id', 'hotel_id', 'hotel_name', 'city', 'review_text',
               'rating', 'language', 'sentiment_score', 'sentiment_label',
               'topic_id', 'topic_name', 'trip_type', 'published_date']

df_processed = df_processed[[col for col in output_cols if col in df_processed.columns]]

# Save
output_file = output_path / 'processed_reviews.csv'
df_processed.to_csv(output_file, index=False, encoding='utf-8')

print(f"\n=== PROCESSING COMPLETE ===")
print(f"Saved to: {output_file}")
print(f"Total reviews: {len(df_processed)}")
print(f"With sentiment scores: {(df_processed['sentiment_score'] > 0).sum()}")
print(f"With topic assignments: {(df_processed['topic_id'] >= 0).sum()}")
print(f"\nSentiment summary:")
print(df_processed.groupby('sentiment_label')['sentiment_score'].agg(['count', 'mean']))
print(f"\nSample output:")
print(df_processed[['hotel_name', 'sentiment_label', 'sentiment_score', 'topic_name']].head(10))
