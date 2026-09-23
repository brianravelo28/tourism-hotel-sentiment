"""Aspect-based sentiment for hotel reviews (English + Spanish).

Each review is split into sentences. Every sentence gets:
  * an aspect (staff, cleanliness, location, ...) by cosine similarity between its multilingual
    embedding and EN+ES seed phrases for each aspect, and
  * a sentiment distribution from a small multilingual sentiment model.

Review-level sentiment is the length-weighted mean of its sentence sentiments.

Outputs (in --out, default data/interim):
  review_sentiment.csv   one row per review
  aspect_mentions.csv    one row per aspect-tagged sentence

Usage:  python src/aspect_sentiment.py --frac 0.25
"""
import argparse
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from transformers import pipeline

EMBED_MODEL = 'paraphrase-multilingual-MiniLM-L12-v2'
SENTIMENT_MODEL = 'lxyuan/distilbert-base-multilingual-cased-sentiments-student'
ASPECT_THRESHOLD = 0.45
MIN_SENTENCE_CHARS = 12

# English + Spanish seed phrases per aspect (averaged into one prototype vector per aspect).
ASPECT_SEEDS = {
    'staff': ['The staff were friendly and helpful', 'El personal fue amable y servicial',
              'front desk, reception, service'],
    'cleanliness': ['The room was clean', 'La habitacion estaba limpia y ordenada', 'dirty, stains, smell'],
    'location': ['Great location close to everything', 'Excelente ubicacion cerca de todo',
                 'near the airport, beach, shopping'],
    'price': ['Good value for the price', 'Buena relacion calidad precio', 'expensive, overpriced, fees'],
    'room': ['The room and bed were comfortable', 'La habitacion y la cama eran comodas',
             'bathroom, view, amenities'],
    'noise': ['It was very noisy', 'Habia mucho ruido', 'quiet, loud, thin walls'],
    'food': ['The breakfast and restaurant were good', 'El desayuno y el restaurante estaban buenos',
             'food, bar, drinks'],
    'amenities': ['The pool and rooftop were great', 'La piscina y la terraza eran geniales', 'pool, gym, spa'],
}


def split_sentences(text):
    parts = re.split(r'(?<=[.!?])\s+|\n+', str(text))
    return [p.strip() for p in parts if len(p.strip()) >= MIN_SENTENCE_CHARS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frac', type=float, default=1.0, help='fraction of reviews to process (stratified by language)')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    root = Path(__file__).parent.parent
    out = Path(args.out) if args.out else root / 'data' / 'interim'
    out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(torch.get_num_threads() * 2)

    df = pd.read_csv(root / 'data' / 'raw_reviews.csv')
    if args.frac < 1.0:
        df = df.groupby('language', group_keys=False).sample(frac=args.frac, random_state=args.seed)
    df = df.reset_index(drop=True)
    print(f'Reviews: {len(df)} | languages: {df.language.value_counts().to_dict()}')

    rows = [(i, s) for i, text in enumerate(df.review_text) for s in split_sentences(text)]
    sents = [s for _, s in rows]
    print(f'Sentences: {len(sents)}')

    t0 = time.time()
    embedder = SentenceTransformer(EMBED_MODEL, device='cpu')
    emb = embedder.encode(sents, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    names = list(ASPECT_SEEDS)
    protos = np.stack([embedder.encode(ASPECT_SEEDS[a], normalize_embeddings=True).mean(0) for a in names])
    protos /= np.linalg.norm(protos, axis=1, keepdims=True)
    sim = emb @ protos.T
    best = sim.argmax(1)
    aspect = [names[j] if sim[i, j] >= ASPECT_THRESHOLD else None for i, j in enumerate(best)]
    aspect_sim = sim.max(1)
    print(f'Aspect assignment done in {time.time() - t0:.0f}s '
          f'({100 * np.mean([a is not None for a in aspect]):.0f}% of sentences tagged)')

    t0 = time.time()
    clf = pipeline('text-classification', model=SENTIMENT_MODEL, top_k=None, device=-1,
                   truncation=True, max_length=128)
    raw = clf(sents, batch_size=32)
    probs = np.array([[{d['label'].lower(): d['score'] for d in o}.get(k, 0.0)
                       for k in ('positive', 'neutral', 'negative')] for o in raw])
    print(f'Sentiment done in {time.time() - t0:.0f}s')

    sent_df = pd.DataFrame({
        'review_idx': [i for i, _ in rows], 'sentence': sents, 'aspect': aspect, 'aspect_sim': aspect_sim,
        'p_pos': probs[:, 0], 'p_neu': probs[:, 1], 'p_neg': probs[:, 2]})
    sent_df['score'] = sent_df.p_pos + 0.5 * sent_df.p_neu  # 0 = negative, 1 = positive
    sent_df['label'] = probs.argmax(1)
    sent_df['label'] = sent_df['label'].map({0: 'positive', 1: 'neutral', 2: 'negative'})
    sent_df['w'] = sent_df.sentence.str.len()

    # Review level: length-weighted mean of sentence scores
    g = sent_df.groupby('review_idx')
    review_score = (sent_df.score * sent_df.w).groupby(sent_df.review_idx).sum() / g.w.sum()
    df['sentiment_score'] = review_score.reindex(range(len(df)))
    df['sentiment_label'] = pd.cut(df.sentiment_score, [-0.01, 0.4, 0.6, 1.01],
                                   labels=['negative', 'neutral', 'positive']).astype(str)
    keep = ['review_id', 'hotel_id', 'hotel_name', 'city', 'review_text', 'rating', 'language',
            'is_machine_translated', 'trip_type', 'published_date', 'sentiment_score', 'sentiment_label']
    df[keep].to_csv(out / 'review_sentiment.csv', index=False, encoding='utf-8')

    mentions = sent_df[sent_df.aspect.notna()].copy()
    meta = df[['review_id', 'hotel_id', 'hotel_name', 'city', 'language', 'published_date']]
    mentions = mentions.join(meta, on='review_idx').drop(columns=['review_idx', 'w'])
    mentions.to_csv(out / 'aspect_mentions.csv', index=False, encoding='utf-8')

    print(f'\nSaved to {out}')
    print(f'  review_sentiment.csv: {len(df)} reviews')
    print(f'  aspect_mentions.csv: {len(mentions)} aspect-tagged sentences')
    print('\nReview sentiment by language:')
    print(df.groupby('language').sentiment_score.agg(['count', 'mean']).query('count >= 5').round(3))
    print('\nAspect mentions (share of reviews mentioning) and mean sentence score, by language:')
    for lang in ('en', 'es'):
        m = mentions[mentions.language == lang]
        n = (df.language == lang).sum()
        t = m.groupby('aspect').agg(reviews=('review_id', 'nunique'), mean_score=('score', 'mean'))
        t['share_of_reviews'] = (t.reviews / n).round(3)
        print(f'\n[{lang}] n={n}')
        print(t.sort_values('share_of_reviews', ascending=False).round(3).to_string())


if __name__ == '__main__':
    main()
