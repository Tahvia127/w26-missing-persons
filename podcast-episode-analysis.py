import sqlite3
import pandas as pd
import re
from collections import defaultdict

DB_NAME = 'podcast.db'

def load_transcripts_from_db():
    """Load all transcripts from database"""
    with sqlite3.connect(DB_NAME) as conn:
        query = '''
            SELECT v.video_id, v.title, v.channel_name, t.full_text, t.word_count
            FROM transcripts t
            JOIN videos v ON t.video_id = v.video_id
            WHERE t.full_text IS NOT NULL
        '''
        df = pd.read_sql_query(query, conn)
    
    print(f"Loaded {len(df)} transcripts from database")
    return df