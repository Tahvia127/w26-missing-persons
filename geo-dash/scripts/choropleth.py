import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

SUMMARY_PATH = 'geo-dash/data/state_summary.csv'
GEOJSON_PATH = 'geo-dash/data/usa-geoJson/us-states.json'
OUTPUT_PATH = 'geo-dash/outputs/choropleth_dashboard.html'

# Full state names for hover labels
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


def build_choropleth_dashboard():
    df = pd.read_csv(SUMMARY_PATH)

    # Exclude territories for cleaner maps (PR, GU, VI have no geometry in GeoJSON)
    df = df[df['State'].isin(STATE_NAMES.keys())].copy()
    df['state_name'] = df['State'].map(STATE_NAMES)

    # Determine which demographic columns exist
    demo_cols = {
        'pct_white': 'White', 'pct_black': 'Black', 'pct_hispanic': 'Hispanic',
        'pct_asian': 'Asian', 'pct_native_american': 'Native American',
    }
    available_demo = {k: v for k, v in demo_cols.items() if k in df.columns}

    # Build rich hover text
    hover_parts = [
        '<b>%{customdata[0]}</b> (%{location})',
        'Total cases: %{customdata[1]}',
        'Per 100k: %{customdata[2]}',
        'Urban: %{customdata[3]}%',
        'Male: %{customdata[4]}% | Female: %{customdata[5]}%',
        'Median age: %{customdata[6]}',
    ]
    demo_start = 7
    for i, label in enumerate(available_demo.values()):
        hover_parts.append(f'{label}: %{{customdata[{demo_start + i}]}}%')
    hover_template = '<br>'.join(hover_parts) + '<extra></extra>'

    custom_cols = [
        'state_name', 'total_cases', 'cases_per_100k', 'urban_pct',
        'pct_male', 'pct_female', 'median_age',
    ] + list(available_demo.keys())
    customdata = df[custom_cols].values

    # --- Dashboard with 2 maps ---
    fig = make_subplots(
        rows=1, cols=2,
        specs=[
            [{'type': 'choropleth'}, {'type': 'choropleth'}]
        ],
        subplot_titles=[
            'Total Missing Person Cases',
            'Cases per 100k Population'
        ]
    )

    # 1) Total cases
    fig.add_trace(go.Choropleth(
        locations=df['State'],
        z=df['total_cases'],
        locationmode='USA-states',
        colorscale='YlOrRd',
        colorbar=dict(title='Cases', x=0.45, y=0.78, len=0.35),
        customdata=customdata,
        hovertemplate=hover_template,
    ), row=1, col=1)

    # 2) Cases per 100k
    fig.add_trace(go.Choropleth(
        locations=df['State'],
        z=df['cases_per_100k'],
        locationmode='USA-states',
        colorscale='Reds',
        colorbar=dict(title='Per 100k', x=1.0, y=0.78, len=0.35),
        customdata=customdata,
        hovertemplate=hover_template,
    ), row=1, col=2)

    # Layout
    geo_common = dict(
        scope='usa',
        showlakes=True,
        lakecolor='rgb(220,230,240)',
        bgcolor='rgba(0,0,0,0)',
    )
    fig.update_geos(**geo_common)

    fig.update_layout(
        title=dict(
            text='Missing Persons by State — NamUS Data Dashboard',
            font=dict(size=22),
            x=0.5,
        ),
        height=500,
        width=1400,
        paper_bgcolor='white'
    )

    import os
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    fig.write_html(OUTPUT_PATH, include_plotlyjs='cdn')
    print(f'Dashboard saved to {OUTPUT_PATH}')


if __name__ == '__main__':
    build_choropleth_dashboard()
