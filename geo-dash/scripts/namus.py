import pandas as pd
import numpy as np

NAMUS_PATH = 'geo-dash/data/namus_data.csv'
POP_PATH = 'geo-dash/data/usa-geoJson/usa_population_2019.csv'
CENSUS_PATH = 'geo-dash/data/census_2020_dp.csv'

# Census 2020 urban % by state (source: U.S. Census Bureau, 2020 Census)
URBAN_PCT = {
    'AL': 59.0, 'AK': 66.0, 'AZ': 89.8, 'AR': 56.2, 'CA': 95.0,
    'CO': 86.2, 'CT': 88.0, 'DE': 83.3, 'DC': 100.0, 'FL': 91.2,
    'GA': 75.1, 'HI': 91.9, 'ID': 70.6, 'IL': 88.5, 'IN': 72.4,
    'IA': 64.0, 'KS': 74.2, 'KY': 58.8, 'LA': 73.2, 'ME': 38.7,
    'MD': 87.2, 'MA': 92.0, 'MI': 74.6, 'MN': 73.3, 'MS': 49.4,
    'MO': 70.4, 'MT': 55.9, 'NE': 73.1, 'NV': 94.2, 'NH': 60.3,
    'NJ': 94.7, 'NM': 77.4, 'NY': 87.9, 'NC': 66.1, 'ND': 59.9,
    'OH': 77.9, 'OK': 66.2, 'OR': 81.0, 'PA': 78.7, 'RI': 90.7,
    'SC': 66.3, 'SD': 56.7, 'TN': 66.4, 'TX': 84.7, 'UT': 90.6,
    'VT': 38.9, 'VA': 75.5, 'WA': 84.1, 'WV': 48.7, 'WI': 70.2,
    'WY': 64.8, 'PR': 93.6, 'GU': 93.7, 'VI': 95.3,
}

STATE_ABBREV = {
    'Alabama': 'AL', 
    'Alaska': 'AK', 
    'Arizona': 'AZ', 
    'Arkansas': 'AR',
    'California': 'CA', 
    'Colorado': 'CO', 
    'Connecticut': 'CT', 
    'Delaware': 'DE',
    'District of Columbia': 'DC', 
    'Florida': 'FL', 
    'Georgia': 'GA', 
    'Hawaii': 'HI',
    'Idaho': 'ID', 
    'Illinois': 'IL', 
    'Indiana': 'IN', 
    'Iowa': 'IA', 
    'Kansas': 'KS',
    'Kentucky': 'KY', 
    'Louisiana': 'LA', 
    'Maine': 'ME', 
    'Maryland': 'MD',
    'Massachusetts': 'MA', 
    'Michigan': 'MI', 
    'Minnesota': 'MN', 
    'Mississippi': 'MS',
    'Missouri': 'MO', 
    'Montana': 'MT', 
    'Nebraska': 'NE', 
    'Nevada': 'NV',
    'New Hampshire': 'NH', 
    'New Jersey': 'NJ', 
    'New Mexico': 'NM', 
    'New York': 'NY',
    'North Carolina': 'NC', 
    'North Dakota': 'ND', 
    'Ohio': 'OH', 
    'Oklahoma': 'OK',
    'Oregon': 'OR', 
    'Pennsylvania': 'PA', 
    'Rhode Island': 'RI',
    'South Carolina': 'SC', 
    'South Dakota': 'SD', 
    'Tennessee': 'TN', 
    'Texas': 'TX',
    'Utah': 'UT', 
    'Vermont': 'VT', 
    'Virginia': 'VA', 
    'Washington': 'WA',
    'West Virginia': 'WV', 
    'Wisconsin': 'WI', 
    'Wyoming': 'WY', 
    'Puerto Rico': 'PR',
}


def load_namus_data(file_path):
    try:
        return pd.read_csv(file_path)
    except Exception as e:
        print(f"Error loading NAMUS data: {e}")
        return None


def classify_race(race_str):
    """Map NamUS race/ethnicity strings to simplified categories."""
    if pd.isna(race_str):
        return 'Unknown'
    r = race_str.strip()
    if r == 'White / Caucasian':
        return 'White'
    elif r == 'Black / African American':
        return 'Black'
    elif r == 'Hispanic / Latino':
        return 'Hispanic'
    elif r == 'Asian':
        return 'Asian'
    elif r == 'American Indian / Alaska Native':
        return 'Native American'
    elif 'Hispanic' in r:
        return 'Hispanic'
    elif 'Black' in r:
        return 'Black'
    elif 'White' in r:
        return 'White'
    elif 'Asian' in r:
        return 'Asian'
    elif r in ('Uncertain', 'Other'):
        return 'Other/Unknown'
    else:
        return 'Other/Unknown'


def build_state_summary(namus, pop_df):
    """Build a state-level summary DataFrame."""
    # --- total cases per state ---
    cases = namus.groupby('State').size().reset_index(name='total_cases')

    # --- merge population ---
    pop_df = pop_df.dropna(subset=['Postal Code']).rename(
        columns={'Postal Code': 'State', 'Total Resident Population': 'population'}
    )[['State', 'population']]
    summary = cases.merge(pop_df, on='State', how='left')
    summary['cases_per_100k'] = (
        summary['total_cases'] / summary['population'] * 100_000
    ).round(2)

    # --- urban % ---
    summary['urban_pct'] = summary['State'].map(URBAN_PCT)

    # --- sex breakdown ---
    sex = namus.groupby('State')['Biological Sex'].value_counts(normalize=True).unstack(fill_value=0)
    sex = (sex * 100).round(1)
    sex.columns = [f'pct_{c.lower()}' for c in sex.columns]
    summary = summary.merge(sex, left_on='State', right_index=True, how='left')

    # --- race/ethnicity breakdown ---
    namus['race_group'] = namus['Race / Ethnicity'].apply(classify_race)
    race = namus.groupby('State')['race_group'].value_counts(normalize=True).unstack(fill_value=0)
    race = (race * 100).round(1)
    race.columns = [f'pct_{c.lower().replace(" ", "_").replace("/", "_")}' for c in race.columns]
    summary = summary.merge(race, left_on='State', right_index=True, how='left')

    # --- median missing age ---
    namus['age_num'] = namus['Missing Age'].str.extract(r'(\d+)').astype(float)
    med_age = namus.groupby('State')['age_num'].median().round(0).astype('Int64')
    med_age.name = 'median_age'
    summary = summary.merge(med_age, left_on='State', right_index=True, how='left')

    summary = summary.sort_values('total_cases', ascending=False).reset_index(drop=True)
    return summary


if __name__ == "__main__":
    namus_data = load_namus_data(NAMUS_PATH)
    pop_data = pd.read_csv(POP_PATH)

    if namus_data is not None:
        summary = build_state_summary(namus_data, pop_data)

        # Display key columns
        display_cols = [
            'State', 'total_cases', 'population', 'cases_per_100k',
            'urban_pct', 'pct_male', 'pct_female', 'median_age',
            'pct_white', 'pct_black', 'pct_hispanic',
            'pct_asian', 'pct_native_american', 'pct_other_unknown',
        ]
        display_cols = [c for c in display_cols if c in summary.columns]
        pd.set_option('display.max_rows', 60)
        pd.set_option('display.width', 200)
        pd.set_option('display.max_columns', 20)
        print(summary[display_cols].to_string(index=False))

        # Save full summary
        out_path = 'geo-dash/data/state_summary.csv'
        summary.to_csv(out_path, index=False)
        print(f"\nSaved full summary to {out_path}")