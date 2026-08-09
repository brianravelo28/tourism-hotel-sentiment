import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, dash_table
from pathlib import Path

# ============================================================
# Load data
# ============================================================
data_path = Path(__file__).parent / 'data'
reputation_df = pd.read_csv(data_path / 'reputation_scores.csv')
trends_df = pd.read_csv(data_path / 'sentiment_trends.csv')
reviews_df = pd.read_csv(data_path / 'processed_reviews.csv')

# Merge hotel_name into trends for readability
trends_df = trends_df.merge(
    reputation_df[['hotel_id', 'hotel_name', 'city']], on='hotel_id', how='left'
)

cities = sorted(reputation_df['city'].unique())
hotel_options = [
    {'label': f"{row.hotel_name} ({row.city})", 'value': row.hotel_id}
    for row in reputation_df.itertuples()
]

# ============================================================
# Summary stats for markdown header
# ============================================================
total_reviews = len(reviews_df)
en_pct = round((reviews_df['language'] == 'en').mean() * 100, 1)
es_pct = round((reviews_df['language'] == 'es').mean() * 100, 1)
date_min = reviews_df['published_date'].min()
date_max = reviews_df['published_date'].max()

summary_text = f"""
**Total reviews analyzed:** {total_reviews:,}  |  **English:** {en_pct}%  |  **Spanish:** {es_pct}%  |  **Date range:** {date_min} to {date_max}

**Key insight:** This dataset is currently English-dominant ({en_pct}% EN); Spanish-language coverage is being expanded in a future data refresh
to support a bilingual comparison of guest priorities across South Florida's diverse traveler base.
"""

# ============================================================
# App setup
# ============================================================
app = Dash(__name__, title="Hotel Reputation Dashboard - Miami/Orlando", suppress_callback_exceptions=True)
server = app.server

app.layout = html.Div([
    html.H1("Hotel Reputation & Sentiment Dashboard", style={'textAlign': 'center'}),
    html.H3("Miami & Orlando Market", style={'textAlign': 'center', 'color': '#666'}),
    dcc.Markdown(summary_text, style={'textAlign': 'center', 'maxWidth': '900px', 'margin': '0 auto 20px auto'}),

    dcc.Tabs(id='tabs', value='tab-1', children=[
        dcc.Tab(label='Competitor Ranking', value='tab-1'),
        dcc.Tab(label='Sentiment Trends', value='tab-2'),
        dcc.Tab(label='Topic Analysis', value='tab-3'),
    ]),
    html.Div(id='tabs-content', style={'padding': '20px'})
])

# ============================================================
# Tab 1: Competitor Ranking
# ============================================================
def render_tab1():
    return html.Div([
        html.Label("Filter by City:"),
        dcc.Dropdown(
            id='city-filter',
            options=[{'label': c, 'value': c} for c in cities],
            value=cities[0],
            clearable=False,
            style={'width': '300px', 'marginBottom': '20px'}
        ),
        dash_table.DataTable(
            id='ranking-table',
            columns=[
                {'name': 'Rank', 'id': 'competitor_rank'},
                {'name': 'Hotel', 'id': 'hotel_name'},
                {'name': 'Reputation Score', 'id': 'reputation_score'},
                {'name': 'EN Reviews', 'id': 'en_count'},
                {'name': 'ES Reviews', 'id': 'es_count'},
                {'name': 'Top Praise', 'id': 'top_praise'},
            ],
            sort_action='native',
            style_cell={'textAlign': 'left', 'padding': '8px'},
            style_header={'fontWeight': 'bold', 'backgroundColor': '#f0f0f0'},
            style_data_conditional=[
                {'if': {'row_index': 0}, 'backgroundColor': '#fff8dc'}
            ],
        )
    ])

# ============================================================
# Tab 2: Sentiment Trends
# ============================================================
def render_tab2():
    default_hotels = reputation_df.nlargest(5, 'reputation_score')['hotel_id'].tolist()
    return html.Div([
        html.Label("Select hotels to compare (3-5 recommended):"),
        dcc.Dropdown(
            id='hotel-selector',
            options=hotel_options,
            value=default_hotels,
            multi=True,
            style={'marginBottom': '20px'}
        ),
        dcc.Graph(id='trends-chart')
    ])

# ============================================================
# Tab 3: Topic Analysis
# ============================================================
def render_tab3():
    topic_counts = reviews_df[reviews_df['topic_id'] >= 0].groupby(
        ['topic_name', 'language']
    ).size().reset_index(name='count')

    top_topics = (
        reviews_df[reviews_df['topic_id'] >= 0]['topic_name']
        .value_counts().head(10).index.tolist()
    )
    topic_counts = topic_counts[topic_counts['topic_name'].isin(top_topics)]

    fig = px.bar(
        topic_counts, y='topic_name', x='count', color='language',
        orientation='h', title='Top 10 Topics by Frequency (EN vs ES)',
        labels={'topic_name': 'Topic', 'count': 'Mention Count'},
        category_orders={'topic_name': top_topics[::-1]}
    )
    fig.update_layout(barmode='stack')

    return html.Div([
        dcc.Graph(figure=fig)
    ])

# ============================================================
# Tab switching callback
# ============================================================
@app.callback(Output('tabs-content', 'children'), Input('tabs', 'value'))
def render_content(tab):
    if tab == 'tab-1':
        return render_tab1()
    elif tab == 'tab-2':
        return render_tab2()
    elif tab == 'tab-3':
        return render_tab3()

# ============================================================
# Tab 1 callback: filter table by city
# ============================================================
@app.callback(Output('ranking-table', 'data'), Input('city-filter', 'value'))
def update_ranking_table(city):
    filtered = reputation_df[reputation_df['city'] == city].sort_values('competitor_rank')
    return filtered.to_dict('records')

# ============================================================
# Tab 2 callback: sentiment trend line chart
# ============================================================
@app.callback(Output('trends-chart', 'figure'), Input('hotel-selector', 'value'))
def update_trends_chart(selected_hotels):
    if not selected_hotels:
        return go.Figure()

    filtered = trends_df[trends_df['hotel_id'].isin(selected_hotels)]
    fig = px.line(
        filtered, x='month', y='avg_sentiment', color='hotel_name',
        markers=True, title='Average Sentiment Over Time',
        labels={'month': 'Month', 'avg_sentiment': 'Avg Sentiment Score', 'hotel_name': 'Hotel'}
    )
    fig.update_yaxes(range=[0, 1])
    return fig

if __name__ == '__main__':
    import os
    debug = os.environ.get('DASH_DEBUG', '0') == '1'
    port = int(os.environ.get('PORT', 7860))
    app.run(debug=debug, host='0.0.0.0', port=port)
