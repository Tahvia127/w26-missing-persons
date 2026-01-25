import requests
import pandas
import sqlite3
import fuzzywuzzy   
import json
import os
from typing import *

with sqlite3.connect("podcast.db") as conn:
    STATEMENT = """CREATE TABLE IF NOT EXISTS podcast_results (
                    case_id TEXT,
                    name TEXT,
                    episode_count INT,
                    podcast_names TEXT
                );"""
    cursor = conn.cursor()
    cursor.execute(STATEMENT)
    conn.commit()

#need to find new API for podcast data retrieval
class ListenNotesAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://listen-api.listennotes.com/api/v2"
        self.headers = {"X-ListenAPI-Key": api_key}
    
    def _request(self, endpoint: str, params: Dict[str, Any]|None) -> Dict[str, Any]:
        """Make a GET request to the Listen Notes API."""
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions as e:
            print(f"API request timed out: {e}")
            return {}
    
    def search_podcasts(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for podcasts by query."""
        params = {"q": query, "limit": limit}
        return self._request("/search", params)
    
    def get_podcast(self, podcast_id: str) -> Dict[str, Any]:
        """Get podcast details by ID."""
        return self._request(f"/podcasts/{podcast_id}", None)


api_key = os.getenv("LISTEN_NOTES_API_KEY")
api = ListenNotesAPI(api_key)

with sqlite3.connect("podcast.db") as conn:
    cursor = conn.cursor()
    
    namUS = pandas.read_csv("podcast-data-retrieval/namUS_cases_with_podcasts.csv").to_dict(orient="records")
    for case in namUS:
        podcast_data = api.search_podcasts(case["name"], limit=10)
        if podcast_data:
            cursor.execute(
                "INSERT INTO podcast_results (case_id, name, episode_count, podcast_names) VALUES (?, ?, ?, ?)"
            )
    conn.commit()