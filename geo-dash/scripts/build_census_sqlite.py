import os
import csv
import sqlite3
from typing import List, Dict, Any
import requests

BASE_URL = "https://api.census.gov/data/2020/dec/dp"

DB_PATH = "geo-dash/data/census_2020_dp.sqlite"
CSV_PATH = "geo-dash/data/census_2020_dp.csv"

VARS = [
    "DP1_0001C", # Total population
    "DP1_0002C", # Under 5 years
    "DP1_0003C", # 5 to 9 years
    "DP1_0004C", # 10 to 14 years
    "DP1_0005C", # 15 to 19 years
    "DP1_0006C", # 20 to 24 years
    "DP1_0007C", # 25 to 29 years
    "DP1_0008C", # 30 to 34 years
    "DP1_0009C", # 35 to 39 years
    "DP1_0010C", # 40 to 44 years
    "DP1_0011C", # 45 to 49 years
    "DP1_0012C", # 50 to 54 years
    "DP1_0013C", # 55 to 59 years
    "DP1_0014C", # 60 to 64 years
    "DP1_0015C", # 65 to 69 years
    "DP1_0016C", # 70 to 74 years
    "DP1_0017C", # 75 to 79 years
    "DP1_0018C", # 80 to 84 years
    "DP1_0019C", # 85 years and over
    "DP1_0025C", # Male population
    "DP1_0049C", # Female population
    "DP1_0078C", # White alone
    "DP1_0079C", # Black or African American alone
    "DP1_0080C", # American Indian and Alaska Native alone
    "DP1_0081C", # Asian alone
    "DP1_0082C", # Native Hawaiian and Other Pacific Islander alone
    "DP1_0083C" # Some other race
]


def fetch_census(variables: List[str]) -> List[Dict[str, Any]]:
    params = {
        "get": "NAME," + ",".join(variables),
        "for": "state:*"
    }

    api_key = os.getenv("CENSUS_API_KEY")
    if api_key:
        params["key"] = api_key

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()

    data = response.json()
    headers = data[0]
    rows = data[1:]
    records = [dict(zip(headers, r)) for r in rows]
    
    return records


def fetch_variable_labels(variables: List[str]) -> Dict[str, str]:
    var_url = "https://api.census.gov/data/2020/dec/dp/variables.json"
    response = requests.get(var_url, timeout=30)
    response.raise_for_status()
    
    var_data = response.json().get("variables", {})
    labels = {}
    for v in variables:
        meta = var_data.get(v, {})
        labels[v] = meta.get("label", v)
    return labels


def write_csv_backup(rows: List[Dict[str, Any]], vars_list: List[str]) -> None:
    fieldnames = ["NAME"] + vars_list + ["state"]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS states (
          state_fips TEXT PRIMARY KEY,
          name       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS variables (
          var_code TEXT PRIMARY KEY,
          label    TEXT
        );

        CREATE TABLE IF NOT EXISTS facts (
          year       INTEGER NOT NULL,
          dataset    TEXT NOT NULL,
          state_fips TEXT NOT NULL,
          var_code   TEXT NOT NULL,
          value      REAL,
          PRIMARY KEY (year, dataset, state_fips, var_code),
          FOREIGN KEY (state_fips) REFERENCES states(state_fips),
          FOREIGN KEY (var_code)   REFERENCES variables(var_code)
        );
        """
    )
    conn.commit()


def load_db(conn: sqlite3.Connection, rows: List[Dict[str, Any]], var_labels: Dict[str, str]) -> None:
    cur = conn.cursor()

    # 1) states
    states_payload = [(r["state"], r["NAME"]) for r in rows]
    cur.executemany(
        "INSERT OR REPLACE INTO states (state_fips, name) VALUES (?, ?)",
        states_payload
    )

    # 2) variables metadata
    vars_payload = [(v, var_labels.get(v, v)) for v in VARS]
    cur.executemany(
        "INSERT OR REPLACE INTO variables (var_code, label) VALUES (?, ?)",
        vars_payload
    )

    # 3) facts (long format)
    facts_payload = []
    for r in rows:
        state_fips = r["state"]
        for v in VARS:
            raw = r.get(v)
            # Census returns strings; store numeric where possible
            val = None
            if raw not in (None, "", "null"):
                try:
                    val = float(raw)
                except ValueError:
                    val = None
            facts_payload.append((2020, "dec/dp", state_fips, v, val))
    

    cur.executemany(
        """
        INSERT OR REPLACE INTO facts (year, dataset, state_fips, var_code, value)
        VALUES (?, ?, ?, ?, ?)
        """,
        facts_payload
    )

    conn.commit()


def main() -> None:
    rows = fetch_census(VARS)

    # backup first (so you have something even if db work changes later)
    write_csv_backup(rows, VARS)

    # pull labels so your db is self-documenting
    var_labels = fetch_variable_labels(VARS)

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        load_db(conn, rows, var_labels)
    finally:
        conn.close()

    print(f"Wrote CSV backup: {CSV_PATH}")
    print(f"Built SQLite DB:   {DB_PATH}")
    print(f"Loaded rows:       {len(rows)} states")

if __name__ == "__main__":
    main()