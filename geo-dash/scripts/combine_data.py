"""
Combine NamUS missing persons CSV with Census 2020 SQLite data
into a single SQLite database.
"""
import sqlite3
import pandas as pd
from namus import STATE_ABBREV, URBAN_PCT, classify_race

NAMUS_PATH = 'geo-dash/data/namus_data.csv'
CENSUS_DB_PATH = 'geo-dash/data/census_2020_dp.sqlite'
OUTPUT_DB_PATH = 'geo-dash/data/combined.sqlite'


def load_census_data(census_db_path):
    conn = sqlite3.connect(census_db_path)
    states = pd.read_sql('SELECT * FROM states', conn)
    variables = pd.read_sql('SELECT * FROM variables', conn)
    facts = pd.read_sql('SELECT * FROM facts', conn)
    conn.close()

    # Add state abbreviations
    states['state_abbrev'] = states['name'].map(STATE_ABBREV)

    # Pivot facts to wide format: one row per state, one column per variable
    census_wide = facts.pivot_table(
        index='state_fips', columns='var_code', values='value'
    ).reset_index()

    # Merge in state names and abbreviations
    census_wide = census_wide.merge(states, on='state_fips', how='left')

    return states, variables, facts, census_wide


def build_combined_db():
    # --- Load NamUS data ---
    namus = pd.read_csv(NAMUS_PATH)
    namus['age_num'] = namus['Missing Age'].str.extract(r'(\d+)').astype(float)
    namus['race_group'] = namus['Race / Ethnicity'].apply(classify_race)

    # --- Load census data ---
    states, variables, facts, census_wide = load_census_data(CENSUS_DB_PATH)

    # --- Build state summary joining both sources ---
    cases = namus.groupby('State').agg(
        total_cases=('Case Number', 'count'),
        median_age=('age_num', 'median'),
        pct_male=('Biological Sex', lambda x: round((x == 'Male').mean() * 100, 1)),
        pct_female=('Biological Sex', lambda x: round((x == 'Female').mean() * 100, 1)),
    ).reset_index()

    # Race breakdown
    race = namus.groupby('State')['race_group'].value_counts(normalize=True).unstack(fill_value=0)
    race = (race * 100).round(1)
    race.columns = [f'pct_{c.lower().replace(" ", "_").replace("/", "_")}' for c in race.columns]
    cases = cases.merge(race, left_on='State', right_index=True, how='left')

    # Merge census population + demographics onto state summary
    census_for_merge = census_wide[['state_abbrev', 'state_fips', 'name',
                                     'DP1_0001C', 'DP1_0025C', 'DP1_0049C',
                                     'DP1_0078C', 'DP1_0079C', 'DP1_0080C',
                                     'DP1_0081C', 'DP1_0082C', 'DP1_0083C']].copy()
    census_for_merge.columns = [
        'state_abbrev', 'state_fips', 'state_name',
        'census_total_pop', 'census_male_pop', 'census_female_pop',
        'census_white', 'census_black', 'census_native_american',
        'census_asian', 'census_pacific_islander', 'census_other_race',
    ]

    state_summary = cases.merge(census_for_merge, left_on='State', right_on='state_abbrev', how='left')
    state_summary['cases_per_100k'] = (
        state_summary['total_cases'] / state_summary['census_total_pop'] * 100_000
    ).round(2)
    state_summary['urban_pct'] = state_summary['State'].map(URBAN_PCT)

    # --- Write to SQLite ---
    conn = sqlite3.connect(OUTPUT_DB_PATH)

    # Table 1: Raw NamUS cases
    namus.to_sql('namus_cases', conn, if_exists='replace', index=False)

    # Table 2: Census states
    states.to_sql('census_states', conn, if_exists='replace', index=False)

    # Table 3: Census variables (lookup)
    variables.to_sql('census_variables', conn, if_exists='replace', index=False)

    # Table 4: Census facts (long format)
    facts.to_sql('census_facts', conn, if_exists='replace', index=False)

    # Table 5: State summary (the combined view)
    state_summary.to_sql('state_summary', conn, if_exists='replace', index=False)

    conn.close()
    print(f'Combined database saved to {OUTPUT_DB_PATH}')

    # Verify
    conn = sqlite3.connect(OUTPUT_DB_PATH)
    for table in ['namus_cases', 'census_states', 'census_variables', 'census_facts', 'state_summary']:
        count = pd.read_sql(f'SELECT count(*) as n FROM {table}', conn)['n'][0]
        cols = pd.read_sql(f'PRAGMA table_info({table})', conn)['name'].tolist()
        print(f'  {table}: {count} rows, {len(cols)} cols')
    conn.close()


if __name__ == '__main__':
    build_combined_db()
