from dash import Dash, html, dcc, Input, Output, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

"""
TAB 1: Overview
- Total cases analyzed
- Key finding statistics (3-4 big numbers)
- Project description

TAB 2: Demographic Analysis
- Bar charts by race, gender, age (from Tahvia's analysis)
- Interactive filters

TAB 3: Media Coverage
- Podcast coverage chart (James's data)
- News coverage chart (Ainslie's data)
- Side-by-side comparison

TAB 4: Geographic Patterns
- Interactive US map (your maps)
- State-level drill-down
- Urban vs. rural comparison

TAB 5: Case Browser (Optional)
- Anonymized case statistics
- Filter by demographics/location
"""

STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'DC': 'District of Columbia', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii',
    'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming',
}

app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])

# --- Load data ---
namus_df = pd.read_csv('geo-dash/data/namus_data.csv')
state_summary_df = pd.read_csv('geo-dash/data/state_summary.csv')

# Filter state summary to 50 states + DC only
state_summary_df = state_summary_df[state_summary_df['State'].isin(STATE_NAMES.keys())].copy()
state_summary_df['state_name'] = state_summary_df['State'].map(STATE_NAMES)

# --- Pre-compute overview stats ---
total_cases = len(namus_df)
num_states = namus_df['State'].nunique()
pct_female = (namus_df['Biological Sex'] == 'Female').mean() * 100
non_white_mask = ~namus_df['Race / Ethnicity'].isin(['White / Caucasian'])
pct_non_white = non_white_mask.mean() * 100
namus_df['age_num'] = namus_df['Missing Age'].str.extract(r'(\d+)').astype(float)
median_age = int(namus_df['age_num'].median())

top_state_row = state_summary_df.iloc[0]
top_rate_row = state_summary_df.nlargest(1, 'cases_per_100k').iloc[0]

# --- Case Browser columns ---
BROWSER_COLS = ['Case Number', 'State', 'City', 'Biological Sex', 'Race / Ethnicity', 'Missing Age']
browser_df = namus_df[BROWSER_COLS].copy()

# --- Layout ---
app.layout = dbc.Container([
    html.H1("Missing the Story: Media Bias in Missing Persons Coverage", className="mt-3 mb-1"),
    html.P("Quantifying disparities in how media covers missing persons cases.", className="text-muted mb-3"),

    dbc.Tabs([

        # ── TAB 1: OVERVIEW ──────────────────────────────────────────────────
        dbc.Tab(label="Overview", children=[
            dbc.Row([
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H2(f"{total_cases:,}", className="text-primary fw-bold"),
                    html.P("Total Cases Analyzed", className="mb-0"),
                ]), className="h-100 text-center shadow-sm"), width=3, className="mb-3"),

                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H2(f"{num_states}", className="text-success fw-bold"),
                    html.P("States Covered", className="mb-0"),
                ]), className="h-100 text-center shadow-sm"), width=3, className="mb-3"),

                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H2(f"{pct_female:.0f}%", className="text-info fw-bold"),
                    html.P("Female Cases", className="mb-0"),
                ]), className="h-100 text-center shadow-sm"), width=3, className="mb-3"),

                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H2(f"{pct_non_white:.0f}%", className="text-warning fw-bold"),
                    html.P("Non-White Cases", className="mb-0"),
                ]), className="h-100 text-center shadow-sm"), width=3, className="mb-3"),
            ], className="mt-3"),

            html.Hr(),

            dbc.Row([
                dbc.Col([
                    html.H4("About This Project"),
                    html.P(
                        "Missing persons cases in the United States are not covered equally by the media. "
                        "Research and advocacy have long noted that the race, gender, and socioeconomic "
                        "background of a missing person significantly influence whether their case receives "
                        "news or podcast attention — a phenomenon often called 'Missing White Woman Syndrome.'"
                    ),
                    html.P(
                        "This dashboard explores data from NamUS (National Missing and Unidentified Persons "
                        "System), a federally-funded program that aggregates missing persons reports across "
                        "the country. We pair this with media coverage data to measure and visualize the gap "
                        "between who goes missing and who gets covered."
                    ),
                    html.P(
                        "Use the tabs above to explore geographic patterns, demographic breakdowns, "
                        "media coverage disparities, and individual case records."
                    ),
                ], width=8),

                dbc.Col([
                    html.H4("Key Findings"),
                    html.Ul([
                        html.Li(f"Median missing age: {median_age} years old"),
                        html.Li([
                            f"Most cases reported in: ",
                            html.Strong(f"{top_state_row['state_name']} ({int(top_state_row['total_cases']):,} cases)"),
                        ]),
                        html.Li([
                            "Highest rate per 100k: ",
                            html.Strong(f"{top_rate_row['state_name']} ({top_rate_row['cases_per_100k']:.1f} per 100k)"),
                        ]),
                        html.Li("Data source: NamUS National Missing and Unidentified Persons System"),
                    ]),
                ], width=4),
            ]),
        ]),

        # ── TAB 2: DEMOGRAPHICS (placeholder) ────────────────────────────────
        dbc.Tab(label="Demographics", children=[
            html.H3("Demographic Analysis", className="mt-3"),
            html.P("Content coming soon..."),
        ]),

        # ── TAB 3: MEDIA COVERAGE (placeholder) ──────────────────────────────
        dbc.Tab(label="Media Coverage", children=[
            html.H3("Podcast & News Coverage", className="mt-3"),
            html.P("Content coming soon..."),
        ]),

        # ── TAB 4: GEOGRAPHIC PATTERNS ────────────────────────────────────────
        dbc.Tab(label="Geographic", children=[
            dbc.Row([
                dbc.Col([
                    html.Label("Map Metric", className="fw-bold mt-3"),
                    dcc.Dropdown(
                        id='geo-metric',
                        options=[
                            {'label': 'Total Cases', 'value': 'total_cases'},
                            {'label': 'Cases per 100k Population', 'value': 'cases_per_100k'},
                            {'label': '% Female Cases', 'value': 'pct_female'},
                            {'label': '% Black Cases', 'value': 'pct_black'},
                            {'label': '% Hispanic Cases', 'value': 'pct_hispanic'},
                        ],
                        value='total_cases',
                        clearable=False,
                    ),
                ], width=4),
            ]),

            dcc.Graph(id='choropleth-map'),

            dbc.Row([
                dbc.Col(dcc.Graph(id='top-states-bar'), width=8),
                dbc.Col(dcc.Graph(id='urban-rural-scatter'), width=4),
            ]),
        ]),

        # ── TAB 5: CASE BROWSER ───────────────────────────────────────────────
        dbc.Tab(label="Case Browser", children=[
            dbc.Row([
                dbc.Col([
                    html.Label("State", className="fw-bold"),
                    dcc.Dropdown(
                        id='filter-state',
                        options=[
                            {'label': f"{STATE_NAMES.get(s, s)} ({s})", 'value': s}
                            for s in sorted(browser_df['State'].dropna().unique())
                            if s in STATE_NAMES
                        ],
                        multi=True,
                        placeholder="All states",
                    ),
                ], width=3),

                dbc.Col([
                    html.Label("Sex", className="fw-bold"),
                    dcc.Dropdown(
                        id='filter-sex',
                        options=[
                            {'label': v, 'value': v}
                            for v in sorted(browser_df['Biological Sex'].dropna().unique())
                        ],
                        multi=True,
                        placeholder="All",
                    ),
                ], width=3),

                dbc.Col([
                    html.Label("Race / Ethnicity", className="fw-bold"),
                    dcc.Dropdown(
                        id='filter-race',
                        options=[
                            {'label': v, 'value': v}
                            for v in sorted(browser_df['Race / Ethnicity'].dropna().unique())
                        ],
                        multi=True,
                        placeholder="All",
                    ),
                ], width=4),
            ], className="mt-3 mb-2"),

            html.Div(id='case-count', className="text-muted small mb-2"),

            dash_table.DataTable(
                id='case-table',
                columns=[{'name': c, 'id': c} for c in BROWSER_COLS],
                data=browser_df.to_dict('records'),
                page_size=25,
                sort_action='native',
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'fontSize': 13, 'padding': '6px 10px'},
                style_header={
                    'fontWeight': 'bold',
                    'backgroundColor': '#f8f9fa',
                    'borderBottom': '2px solid #dee2e6',
                },
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#fafafa'},
                ],
            ),
        ]),

    ]),
], fluid=True)


# ── CALLBACKS ────────────────────────────────────────────────────────────────

METRIC_LABELS = {
    'total_cases': 'Total Cases',
    'cases_per_100k': 'Cases per 100k',
    'pct_female': '% Female',
    'pct_black': '% Black',
    'pct_hispanic': '% Hispanic',
}


@app.callback(
    Output('choropleth-map', 'figure'),
    Output('top-states-bar', 'figure'),
    Output('urban-rural-scatter', 'figure'),
    Input('geo-metric', 'value'),
)
def update_geo(metric):
    label = METRIC_LABELS.get(metric, metric)

    # Choropleth map
    choropleth = px.choropleth(
        state_summary_df,
        locations='State',
        locationmode='USA-states',
        color=metric,
        scope='usa',
        hover_name='state_name',
        hover_data={
            'State': False,
            'total_cases': ':,',
            'cases_per_100k': ':.1f',
        },
        color_continuous_scale='YlOrRd',
        labels={metric: label, 'total_cases': 'Total Cases', 'cases_per_100k': 'Per 100k'},
        title=f'{label} by State',
    )
    choropleth.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=420)

    # Top 10 states horizontal bar chart
    top10 = state_summary_df.nlargest(10, metric).sort_values(metric)
    bar = px.bar(
        top10,
        x=metric,
        y='state_name',
        orientation='h',
        labels={metric: label, 'state_name': 'State'},
        title=f'Top 10 States — {label}',
        color=metric,
        color_continuous_scale='YlOrRd',
    )
    bar.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        height=380,
        margin=dict(l=0, r=10, t=40, b=0),
    )

    # Urban % vs. cases per 100k scatter
    scatter = px.scatter(
        state_summary_df,
        x='urban_pct',
        y='cases_per_100k',
        hover_name='state_name',
        text='State',
        labels={'urban_pct': 'Urban %', 'cases_per_100k': 'Cases per 100k'},
        title='Urban % vs. Case Rate',
    )
    scatter.update_traces(textposition='top center', textfont_size=9, marker_size=7)
    scatter.update_layout(height=380, margin=dict(l=0, r=0, t=40, b=0))

    return choropleth, bar, scatter


@app.callback(
    Output('case-table', 'data'),
    Output('case-count', 'children'),
    Input('filter-state', 'value'),
    Input('filter-sex', 'value'),
    Input('filter-race', 'value'),
)
def filter_cases(states, sexes, races):
    df = browser_df.copy()
    if states:
        df = df[df['State'].isin(states)]
    if sexes:
        df = df[df['Biological Sex'].isin(sexes)]
    if races:
        df = df[df['Race / Ethnicity'].isin(races)]
    count_text = f"Showing {len(df):,} of {len(browser_df):,} cases"
    return df.to_dict('records'), count_text


if __name__ == '__main__':
    app.run(debug=True)
