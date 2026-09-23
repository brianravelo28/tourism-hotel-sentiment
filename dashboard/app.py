import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, ctx, dash_table, dcc, html, Input, Output, State
from dash.exceptions import PreventUpdate

# ============================================================
# Data
# ============================================================
DATA = Path(__file__).parent / 'data'
rep = pd.read_csv(DATA / 'reputation_scores.csv')
prof = pd.read_csv(DATA / 'aspect_by_hotel.csv')
ment = pd.read_csv(DATA / 'aspect_mentions.csv')
rev = pd.read_csv(DATA / 'processed_reviews.csv', parse_dates=['published_date'])
lang = pd.read_csv(DATA / 'language_aspects.csv')
trends = pd.read_csv(DATA / 'sentiment_trends.csv')

EN, ES = '#2b6cb0', '#dd6b20'
POS, NEU, NEG = '#2b6cb0', '#cbd5e0', '#c05621'
EVIDENCE_COLOR = {'robust': '#1a365d', 'suggestive': '#63b3ed', 'none': '#a0aec0'}
ASPECT_ORDER = ['staff', 'room', 'location', 'cleanliness', 'food', 'amenities', 'price', 'noise']
MIN_HEATMAP_MENTIONS = 8
TEMPLATE = dict(template='plotly_white', font=dict(family='Inter, Segoe UI, Arial, sans-serif', size=15),
                margin=dict(l=10, r=10, t=40, b=10))

rep['es_pct'] = (rep.es_count / rep.review_count * 100).round(0).astype(int)
rep['top_praise'] = rep.top_praise.fillna('')
rep['top_complaints'] = rep.top_complaints.fillna('').replace('', 'none notable')
cities = sorted(rep.city.unique())

n_reviews = len(rev)
es_pct_all = (rev.language == 'es').mean() * 100
en_pct_all = (rev.language == 'en').mean() * 100
date_min, date_max = rev.published_date.min().date(), rev.published_date.max().date()
score_window = 24

# ============================================================
# Layout
# ============================================================
app = Dash(__name__, title='Hotel Reputation Dashboard - Miami & Orlando', suppress_callback_exceptions=True)
server = app.server


def kpi(label, value, sub=None):
    return html.Div([html.Div(label, className='kpi-label'), html.Div(value, className='kpi-value'),
                     html.Div(sub or '', className='kpi-sub')], className='kpi')


app.layout = html.Div([
    html.Div([
        html.H1('Hotel Reputation Dashboard'),
        html.P('Miami & Orlando hotels, from TripAdvisor guest reviews written in English and Spanish', className='subtitle'),
        html.Div([
            kpi('Reviews analyzed', f'{n_reviews:,}', f'{date_min:%b %Y} - {date_max:%b %Y}'),
            kpi('Hotels', f'{rep.hotel_id.nunique()}', ' / '.join(f'{(rep.city == c).sum()} {c}' for c in cities)),
            kpi('English', f'{en_pct_all:.0f}%', f'{(rev.language == "en").sum():,} reviews'),
            kpi('Spanish', f'{es_pct_all:.0f}%', f'{(rev.language == "es").sum():,} reviews'),
        ], className='kpis'),
    ], className='header'),
    dcc.Tabs(id='tabs', value='rank', children=[
        dcc.Tab(label='Rankings', value='rank'),
        dcc.Tab(label='Hotel detail', value='detail'),
        dcc.Tab(label='English vs Spanish', value='lang'),
        dcc.Tab(label='Trends', value='trends'),
    ]),
    html.Div(id='tab-content', className='content'),
    html.Div([
        'Reviews are public TripAdvisor posts; sentiment and topics are machine-generated and imperfect '
        '(aspect tagging is roughly 90% accurate on a hand check). ',
        html.A('Method and code on GitHub', href='https://github.com/brianravelo28/tourism-hotel-sentiment', target='_blank'),
    ], className='footer'),
], className='page')


# ============================================================
# Tab 1: Rankings
# ============================================================
def tab_rank():
    return html.Div([
        html.Div([
            html.Label('City'),
            dcc.Dropdown(id='city', options=[{'label': c, 'value': c} for c in cities], value=cities[0],
                         clearable=False, style={'width': '220px'}),
        ], className='controls'),
        html.P(f'Score = 40% guest sentiment, 30% star rating, 15% recency, 15% TripAdvisor review volume, computed on '
               f'reviews from the last {score_window} months so every hotel is compared over the same period. '
               f'Click a hotel to see its strengths and complaints.', className='note'),
        dcc.Store(id='sel-hotel'),
        html.Div([
            html.Div([dash_table.DataTable(
                id='rank-table',
                columns=[
                    {'name': 'Rank', 'id': 'competitor_rank'}, {'name': 'Hotel', 'id': 'hotel_name'},
                    {'name': 'Score', 'id': 'reputation_score'}, {'name': 'TA rating', 'id': 'ta_rating'},
                    {'name': 'Reviews', 'id': 'review_count'}, {'name': '% ES', 'id': 'es_pct'},
                    {'name': 'hotel_id', 'id': 'hotel_id'},
                ],
                hidden_columns=['hotel_id'],
                tooltip_header={'reputation_score': 'Reputation score, 0-10', 'ta_rating': 'TripAdvisor overall rating',
                                'review_count': f'Reviews analyzed from the last {score_window} months',
                                'es_pct': 'Share of those reviews written in Spanish'},
                sort_action='native', page_size=20,
                style_table={'overflowX': 'auto', 'width': '100%'},
                style_cell={'textAlign': 'left', 'padding': '8px 10px', 'fontFamily': 'inherit', 'fontSize': '15px',
                            'whiteSpace': 'normal', 'height': 'auto', 'cursor': 'pointer'},
                style_header={'fontWeight': '600', 'backgroundColor': '#f1f5f9', 'border': 'none', 'whiteSpace': 'nowrap'},
                style_data={'border': 'none', 'borderBottom': '1px solid #e2e8f0'},
                style_cell_conditional=[
                    {'if': {'column_id': cid}, 'width': f'{w}px', 'minWidth': f'{w}px', 'maxWidth': f'{w}px'}
                    for cid, w in (('competitor_rank', 60), ('hotel_name', 250), ('reputation_score', 75),
                                   ('ta_rating', 115), ('review_count', 100), ('es_pct', 75))],
            )], className='rank-table-col'),
            html.Div(id='hotel-card', className='hotel-card'),
        ], className='rank-split'),
        html.H3('How each hotel is described, by aspect'),
        html.P(f'Average sentence sentiment (0 = negative, 1 = positive) for each aspect guests wrote about. '
               f'Blank cells have fewer than {MIN_HEATMAP_MENTIONS} mentions.', className='note'),
        dcc.Graph(id='heatmap', config={'displayModeBar': False}),
    ])


@app.callback(Output('rank-table', 'data'), Output('rank-table', 'active_cell'), Output('rank-table', 'selected_cells'),
              Input('city', 'value'))
def update_table(city):
    d = rep[rep.city == city].sort_values('competitor_rank')
    cols = ['competitor_rank', 'hotel_name', 'reputation_score', 'ta_rating', 'review_count', 'es_pct', 'hotel_id']
    return d[cols].to_dict('records'), None, []


@app.callback(Output('sel-hotel', 'data'), Input('city', 'value'), Input('rank-table', 'active_cell'),
              State('rank-table', 'derived_virtual_data'))
def pick_hotel(city, active, rows):
    if ctx.triggered_id == 'rank-table' and active and rows:
        return int(rows[active['row']]['hotel_id'])
    return int(rep[rep.city == city].sort_values('competitor_rank').iloc[0].hotel_id)


@app.callback(Output('hotel-card', 'children'), Output('rank-table', 'style_data_conditional'), Input('sel-hotel', 'data'))
def show_card(hotel_id):
    if hotel_id is None:
        raise PreventUpdate
    r = rep[rep.hotel_id == hotel_id].iloc[0]
    p = prof[prof.hotel_id == hotel_id].set_index('aspect')
    city_n = int((rep.city == r.city).sum())
    strengths = [a for a in r.top_praise.split('; ') if a]
    complaints = [a for a in r.top_complaints.split('; ') if a and a != 'none notable']
    m = ment[ment.hotel_id == hotel_id]

    def bullets(items, fmt, empty):
        if not items:
            return html.P(empty, className='note')
        return html.Ul([html.Li(fmt(a)) for a in items], className='bullets')

    card = [
        html.H3(r.hotel_name, style={'marginTop': 0}),
        html.Div(f'{r.city} - #{int(r.competitor_rank)} of {city_n} - score {r.reputation_score:.2f} - '
                 f'{int(r.review_count)} recent reviews ({int(r.es_count)} Spanish)', className='note'),
        html.H4('Strengths'),
        bullets(strengths, lambda a: f'{a.capitalize()}: {p.loc[a, "pct_positive"] * 100:.0f}% positive '
                                     f'({int(p.loc[a, "mentions"])} comments)', 'Not enough comments to say.'),
        html.H4('Complaints'),
        bullets(complaints, lambda a: f'{a.capitalize()}: {int(p.loc[a, "complaint_mentions"])} complaint comments',
                'No repeated complaints found.'),
        html.H4('What guests say'),
        quotes(m, False, 1), quotes(m, True, 1),
        html.P('Full breakdown in the Hotel detail tab.', className='note'),
    ]
    # Dash tints the clicked/selected cell itself, which drifts to the wrong hotel once the table is re-sorted.
    # So: neutralise cell-selection styling, then highlight the selected hotel's whole row by hotel_id.
    row = f'{{hotel_id}} = {int(hotel_id)}'
    neutral = {'backgroundColor': 'transparent', 'border': '1px solid transparent'}
    on = {'backgroundColor': '#ebf4ff', 'border': '1px solid transparent'}
    highlight = [
        {'if': {'state': 'active'}, **neutral},
        {'if': {'state': 'selected'}, **neutral},
        {'if': {'filter_query': row}, 'backgroundColor': '#ebf4ff', 'fontWeight': '600'},
        {'if': {'state': 'active', 'filter_query': row}, **on},
        {'if': {'state': 'selected', 'filter_query': row}, **on},
    ]
    return card, highlight


@app.callback(Output('heatmap', 'figure'), Input('city', 'value'))
def update_heatmap(city):
    hotels = rep[rep.city == city].sort_values('competitor_rank')
    p = prof[(prof.city == city) & (prof.mentions >= MIN_HEATMAP_MENTIONS)]
    z = p.pivot(index='hotel_id', columns='aspect', values='mean_score').reindex(index=hotels.hotel_id, columns=ASPECT_ORDER)
    n = p.pivot(index='hotel_id', columns='aspect', values='mentions').reindex(index=hotels.hotel_id, columns=ASPECT_ORDER)
    fig = go.Figure(go.Heatmap(
        z=z.values, x=[a.capitalize() for a in ASPECT_ORDER], y=list(hotels.hotel_name),
        customdata=n.values, colorscale='Blues', zmin=0.4, zmax=1.0,
        text=z.round(2).astype(str).where(z.notna(), '').values, texttemplate='%{text}',
        hovertemplate='%{y}<br>%{x}: %{z:.2f} (%{customdata:.0f} mentions)<extra></extra>',
        colorbar=dict(title='Sentiment', thickness=12), xgap=2, ygap=2))
    fig.update_yaxes(autorange='reversed')
    fig.update_xaxes(side='top')
    fig.update_layout(height=120 + 34 * len(hotels), **{**TEMPLATE, 'margin': dict(l=10, r=10, t=60, b=10)})
    return fig


# ============================================================
# Tab 2: Hotel detail
# ============================================================
def tab_detail():
    options = [{'label': f'{r.hotel_name} ({r.city}, #{r.competitor_rank})', 'value': int(r.hotel_id)}
               for r in rep.sort_values(['city', 'competitor_rank']).itertuples()]
    return html.Div([
        html.Div([
            html.Div([html.Label('Hotel'), dcc.Dropdown(id='hotel', options=options, value=options[0]['value'],
                                                        clearable=False)], style={'flex': '2'}),
            html.Div([html.Label('Review language'), dcc.RadioItems(
                id='lang-filter', value='all', inline=True,
                options=[{'label': 'All', 'value': 'all'}, {'label': 'English', 'value': 'en'},
                         {'label': 'Spanish', 'value': 'es'}])], style={'flex': '1'}),
        ], className='controls'),
        html.Div(id='hotel-kpis', className='kpis'),
        html.H3('What guests say, by aspect'),
        html.P('Each bar is every sentence in which guests mention that aspect, split by tone.', className='note'),
        dcc.Graph(id='hotel-aspects', config={'displayModeBar': False}),
        html.Div([
            html.Div([html.H3('Most positive comments'), html.Div(id='quotes-pos')], className='col'),
            html.Div([html.H3('Complaints'), html.P('Clearly negative comments, mostly from reviews rated 3 stars or lower.', className='note'), html.Div(id='quotes-neg')], className='col'),
        ], className='cols'),
    ])


def quotes(df, ascending, n=4):
    d = df[df.sentence.str.len().between(35, 220)]
    d = d[d.is_complaint].sort_values('p_neg', ascending=False) if ascending else d.sort_values('p_pos', ascending=False)
    d = d.head(n)
    if d.empty:
        return html.P('No clear complaints in this selection.' if ascending else 'Nothing to show.', className='note')
    return html.Ul([html.Li([html.Span(f'"{r.sentence}"'), html.Span(f'{r.aspect} - {r.language.upper()}', className='tag')])
                    for r in d.itertuples()], className='quotes')


@app.callback(Output('hotel-kpis', 'children'), Output('hotel-aspects', 'figure'),
              Output('quotes-pos', 'children'), Output('quotes-neg', 'children'),
              Input('hotel', 'value'), Input('lang-filter', 'value'))
def update_detail(hotel_id, lang_filter):
    r = rep[rep.hotel_id == hotel_id].iloc[0]
    city_n = (rep.city == r.city).sum()
    kpis = [kpi('Reputation score', f'{r.reputation_score:.2f}', f'#{r.competitor_rank} of {city_n} in {r.city}'),
            kpi('TripAdvisor rating', f'{r.ta_rating:.1f}', f'{int(r.ta_review_count):,} reviews on TripAdvisor'),
            kpi('Reviews analyzed', f'{int(r.reviews_analyzed_total):,}', f'{int(r.es_count)} Spanish in the last {score_window} months'),
            kpi('Avg. sentiment', f'{r.avg_sentiment:.2f}', 'last 24 months, 0 to 1')]
    m = ment[ment.hotel_id == hotel_id]
    if lang_filter != 'all':
        m = m[m.language == lang_filter]
    fig = go.Figure()
    if len(m):
        t = m.groupby(['aspect', 'polarity']).size().unstack(fill_value=0).reindex(columns=['pos', 'neu', 'neg'], fill_value=0)
        t = t.reindex([a for a in ASPECT_ORDER if a in t.index])
        t = t[t.sum(1) >= 3]   # a bar built from 1-2 sentences says nothing
        pct = t.div(t.sum(1), axis=0) * 100
        labels = [f'{a.capitalize()} (n={int(t.loc[a].sum())})' for a in t.index]
        for col, name, color in (('pos', 'Positive', POS), ('neu', 'Neutral', NEU), ('neg', 'Negative', NEG)):
            fig.add_bar(y=labels, x=pct[col], name=name, orientation='h', marker_color=color,
                        hovertemplate='%{y}: %{x:.0f}% ' + name.lower() + '<extra></extra>')
        fig.update_layout(barmode='stack', xaxis=dict(range=[0, 100], ticksuffix='%'), yaxis=dict(autorange='reversed'),
                          height=90 + 38 * len(t), legend=dict(orientation='h', y=1.12), **TEMPLATE)
    else:
        fig.update_layout(height=120, annotations=[dict(text='No aspect mentions for this selection', showarrow=False)], **TEMPLATE)
    return kpis, fig, quotes(m, False), quotes(m, True)


# ============================================================
# Tab 3: English vs Spanish
# ============================================================
def tab_lang():
    L = lang.copy()
    n_en, n_es = int(L.en_reviews.iloc[0]), int(L.es_reviews.iloc[0])
    k = int(L.hotels_compared.iloc[0])
    pts = lambda v: f'{v * 100:+.1f} pts'

    def phrase(rows):
        return ', '.join(f'{r.aspect} ({pts(r.adjusted_diff)})' for r in rows.itertuples())
    robust = L[L.evidence == 'robust'].sort_values('adjusted_diff', ascending=False)
    more = robust[robust.adjusted_diff > 0]
    less = robust[robust.adjusted_diff < 0]
    weak = L[L.evidence == 'suggestive']
    none = L[L.evidence == 'none']

    parts = []
    if len(more) or len(less):
        parts.append(f"Holding the hotel constant, Spanish-speaking guests give a larger share of their comments to "
                     f"{phrase(more) or 'nothing'} and a smaller share to {phrase(less) or 'nothing'}.")
    fig_diff = go.Figure()
    for ev in ('robust', 'suggestive', 'none'):
        d = L[L.evidence == ev]
        fig_diff.add_trace(go.Scatter(
            x=d.adjusted_diff * 100, y=[a.capitalize() for a in d.aspect], mode='markers', name={
                'robust': 'Robust', 'suggestive': 'Suggestive', 'none': 'No reliable difference'}[ev],
            marker=dict(color=EVIDENCE_COLOR[ev], size=12),
            error_x=dict(type='data', symmetric=False, array=(d.ci_high - d.adjusted_diff) * 100,
                         arrayminus=(d.adjusted_diff - d.ci_low) * 100, color=EVIDENCE_COLOR[ev], thickness=2),
            hovertemplate='%{y}: %{x:+.1f} pts<extra></extra>'))
    fig_diff.add_vline(x=0, line_width=1, line_color='#718096')
    fig_diff.update_layout(height=380, xaxis=dict(title='Spanish share minus English share (percentage points)', zeroline=False),
                           yaxis=dict(categoryorder='array', categoryarray=[a.capitalize() for a in L.sort_values('adjusted_diff').aspect],
                               ), legend=dict(orientation='h', y=1.12), **TEMPLATE)

    Ls = L.sort_values('en_share', ascending=False)
    fig_share = go.Figure()
    fig_share.add_bar(x=[a.capitalize() for a in Ls.aspect], y=Ls.en_share_hotel_adjusted * 100, name='English', marker_color=EN)
    fig_share.add_bar(x=[a.capitalize() for a in Ls.aspect], y=Ls.es_share * 100, name='Spanish', marker_color=ES)
    fig_share.update_layout(barmode='group', height=340, yaxis=dict(title='% of aspect comments', ticksuffix='%'),
                            legend=dict(orientation='h', y=1.12), **TEMPLATE)

    return html.Div([
        html.Div([html.H3('What differs'), html.P(' '.join(parts), className='lead'),
                  html.P(f'Weaker signals: {phrase(weak)}. No reliable difference: '
                         f'{", ".join(none.aspect)}.', className='note')], className='callout'),
        html.H3('Difference in share of comments, Spanish minus English'),
        html.P(f'Bars are 95% confidence intervals. The English share is re-weighted to the hotels Spanish-speaking '
               f'guests actually stayed at, so this is not just "which hotels each group visits".', className='note'),
        dcc.Graph(figure=fig_diff, config={'displayModeBar': False}),
        html.H3('Where the comments go'),
        html.P('Each language sums to 100%. English is shown re-weighted to the Spanish hotel mix.', className='note'),
        dcc.Graph(figure=fig_share, config={'displayModeBar': False}),
        html.H3('How much to trust this'),
        html.Ul([
            html.Li(f'{n_en:,} English and {n_es:,} Spanish reviews. Spanish reviews are shorter, so the comparison uses '
                    f'share of comments, not how many reviews mention a topic.'),
            html.Li(f'"Robust" means the interval clears zero by a margin, the same direction shows up in at least 75% of '
                    f'the {k} hotels with enough Spanish reviews, and the topic is not rare. "Suggestive" clears zero but not '
                    f'the other tests.'),
            html.Li('This shows what differs, not why. Trip type (family, business) is not yet controlled for.'),
            html.Li('Eight topics were tested, so a borderline result could be chance.'),
        ], className='bullets'),
    ])


# ============================================================
# Tab 4: Trends
# ============================================================
def tab_trends():
    return html.Div([
        html.Div([html.Label('City'), dcc.Dropdown(id='trend-city', options=[{'label': 'Both cities', 'value': 'all'}] +
                                                   [{'label': c, 'value': c} for c in cities], value='all',
                                                   clearable=False, style={'width': '220px'})], className='controls'),
        html.P('Average review sentiment by quarter and language. Quarters with fewer than 15 reviews are hidden.', className='note'),
        dcc.Graph(id='trend-chart', config={'displayModeBar': False}),
    ])


@app.callback(Output('trend-chart', 'figure'), Input('trend-city', 'value'))
def update_trends(city):
    t = trends if city == 'all' else trends[trends.city == city]
    g = t.assign(w=t.avg_sentiment * t.review_count).groupby(['quarter', 'language']).agg(
        w=('w', 'sum'), n=('review_count', 'sum')).reset_index()
    g['sentiment'] = g.w / g.n
    g = g[g.n >= 15]
    # Grouped axis (starting at Q1 of the first year, otherwise Plotly orders sub-labels Q3,Q4,Q1,Q2): small "Q1..Q4" labels with the year centred beneath its quarters. A hidden trace over the full
    # quarter range keeps quarters with too few reviews on the axis (as gaps) instead of collapsing them.
    quarters = [str(q) for q in pd.period_range(g.quarter.min()[:4] + 'Q1', g.quarter.max(), freq='Q')] if len(g) else []
    split = lambda qs: [[q[:4] for q in qs], [f'Q{q[-1]}' for q in qs]]
    fig = go.Figure(go.Scatter(x=split(quarters), y=[None] * len(quarters), showlegend=False, hoverinfo='skip'))
    for code, name, color in (('en', 'English', EN), ('es', 'Spanish', ES)):
        d = g[g.language == code].sort_values('quarter')
        fig.add_trace(go.Scatter(
            x=split(list(d.quarter)), y=d.sentiment, name=name, mode='lines+markers', line=dict(color=color, width=2),
            customdata=[[f'{q[:4]} Q{q[-1]}', int(n)] for q, n in zip(d.quarter, d.n)],
            hovertemplate='%{customdata[0]}: %{y:.2f} (%{customdata[1]} reviews)<extra>' + name + '</extra>'))
    fig.update_xaxes(type='multicategory', tickangle=0, showdividers=True, dividercolor='#cbd5e0', dividerwidth=1,
                     automargin=True)
    fig.update_layout(height=430, yaxis=dict(title='Average sentiment (0-1)', range=[0.4, 1]),
                      legend=dict(orientation='h', y=1.1), **TEMPLATE)
    return fig


# ============================================================
@app.callback(Output('tab-content', 'children'), Input('tabs', 'value'))
def render_tab(tab):
    return {'rank': tab_rank, 'detail': tab_detail, 'lang': tab_lang, 'trends': tab_trends}[tab]()


if __name__ == '__main__':
    app.run(debug=os.environ.get('DASH_DEBUG', '0') == '1', host='0.0.0.0', port=int(os.environ.get('PORT', 7860)))
