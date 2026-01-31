import os
import re
import sqlite3
import pandas as pd
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

YOUTUBE_CLIENT = None

with open('YT_API_KEY.txt', 'r') as f:
    API_KEY = f.read().strip()
DB_NAME = 'podcast.db'

def get_youtube_client():
    """Get or create YouTube API client"""
    global YOUTUBE_CLIENT
    if YOUTUBE_CLIENT is None:
        YOUTUBE_CLIENT = build('youtube', 'v3', developerKey=API_KEY)
    return YOUTUBE_CLIENT

def create_database():
    """Create database schema for storing transcripts and metadata"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
    
        # Videos table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                channel_name TEXT,
                published_date TEXT,
                url TEXT,
                transcript_available INTEGER DEFAULT 0,
                downloaded_date TEXT,
                duration_seconds INTEGER,
                match_reason TEXT,  -- Why this video was included
                match_score INTEGER  -- Fuzzy match score
            )
        ''')
        
        # Transcripts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT,
                full_text TEXT,
                word_count INTEGER,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            )
        ''')
        
        # Extracted entities table (for future data extraction)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extracted_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT,
                entity_type TEXT,
                entity_value TEXT,
                context TEXT,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            )
        ''')
        
        conn.commit()
        print("Database created successfully!")

# Pre-compile regex pattern for faster matching
WORD_PATTERN = re.compile(r'\b\w+\b')

def extract_ngrams(text, max_n=3):
    """
    Efficiently extract word n-grams from text
    
    Args:
        text: Input text
        max_n: Maximum n-gram size (1=words, 2=pairs, 3=triplets)
    
    Returns:
        list of n-grams as strings
    """
    words = WORD_PATTERN.findall(text.lower())
    ngrams = []
    
    for n in range(1, min(max_n + 1, len(words) + 1)):
        for i in range(len(words) - n + 1):
            ngrams.append(' '.join(words[i:i+n]))
    
    return ngrams

def optimized_fuzzy_match(text, keywords, threshold=85, use_partial=True):
    """
    Optimized fuzzy matching using FuzzyWuzzy's extractOne
    
    Args:
        text: Text to search in
        keywords: List of keywords to match
        threshold: Minimum similarity score (0-100)
        use_partial: Whether to use partial ratio (better for substrings)
    
    Returns:
        tuple: (matched, best_keyword, score)
    """
    if not text or not keywords:
        return False, None, 0
    
    text_lower = text.lower()
    
    # Strategy 1: Direct exact substring match (fastest)
    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True, keyword, 100
    
    # Strategy 2: Use process.extractOne for efficient fuzzy matching
    if use_partial:
        # For multi-word keywords, extract n-grams from text
        max_keyword_words = max(len(kw.split()) for kw in keywords)
        ngrams = extract_ngrams(text, max_n=max_keyword_words)
        
        if ngrams:
            # Find best matching ngram for each keyword
            best_overall = (None, None, 0)
            
            for keyword in keywords:
                best_ngram_match = process.extractOne(
                    keyword.lower(),
                    ngrams,
                    scorer=fuzz.ratio
                )
                
                if best_ngram_match and best_ngram_match[1] > best_overall[2]:
                    best_overall = (keyword, best_ngram_match[0], best_ngram_match[1])
            
            if best_overall[2] >= threshold:
                return True, best_overall[0], best_overall[2]
    
    # Strategy 3: Fallback to direct keyword comparison
    best_match = process.extractOne(
        text_lower,
        keywords,
        scorer=fuzz.partial_ratio if use_partial else fuzz.ratio
    )
    
    if best_match and best_match[1] >= threshold:
        return True, best_match[0], best_match[1]
    
    return False, None, 0

def get_channel_videos(channel_url, max_results=50, filter_missing_persons=True, 
                      fuzzy_threshold=85):
    """
    Extract video metadata with fuzzy keyword matching
    
    Args:
        channel_url: YouTube channel URL
        max_results: Maximum number of videos to retrieve
        filter_missing_persons: If True, only return missing persons related videos
        fuzzy_threshold: Similarity threshold (0-100). Higher = stricter matching
    """
    channel_handle = channel_url.split('@')[-1]
    youtube = build('youtube', 'v3', developerKey=API_KEY)

    # Keywords for filtering
    include_keywords = [
        'missing',
        'vanished',
        'disappeared',
        'cold case',
        'unsolved',
        'where is',
        'search for',
        'last seen',
        'missing person',
        'missing child',
        'missing adult',
        'amber alert',
        'silver alert',
        'gone missing',
        'still missing',
        'disappearance'
    ]
    
    exclude_keywords = [
        'trailer',
        'announcement',
        'update on the show',
        'merch',
        'merchandise',
        'patreon',
        'intro',
        'welcome',
        'subscribe'
    ]
    
    # UPDATED FUNCTION - REPLACE THE OLD fuzzy_match_keywords AND should_include_video
    def should_include_video(title, description=''):
        """Optimized video filtering with fuzzy matching"""
        if not filter_missing_persons:
            return True, "No filter applied"
        
        # Check exclude keywords first with stricter threshold
        exclude_matched, exclude_keyword, exclude_score = optimized_fuzzy_match(
            title,
            exclude_keywords,
            threshold=90,
            use_partial=True
        )
        
        if exclude_matched:
            return False, f"Excluded: matched '{exclude_keyword}' (score: {exclude_score})"
        
        # Check include keywords with fuzzy matching
        # Prioritize title, but also check description
        title_matched, title_keyword, title_score = optimized_fuzzy_match(
            title,
            include_keywords,
            threshold=fuzzy_threshold,
            use_partial=True
        )
        
        if title_matched:
            return True, f"Title matched '{title_keyword}' (score: {title_score})"
        
        # Only check description if title didn't match (saves processing)
        if description:
            # Use slightly stricter threshold for description
            desc_matched, desc_keyword, desc_score = optimized_fuzzy_match(
                description[:500],  # Only check first 500 chars
                include_keywords,
                threshold=min(fuzzy_threshold + 5, 95),
                use_partial=True
            )
            
            if desc_matched:
                return True, f"Description matched '{desc_keyword}' (score: {desc_score})"
        
        return False, "No matching keywords found"
    
    try:
        # Get channel ID
        search_response = youtube.search().list(# pylint: disable=no-member
            part='snippet',
            q=channel_handle,
            type='channel',
            maxResults=1
        ).execute()
        
        if not search_response['items']:
            print("Channel not found")
            return []
        
        channel_id = search_response['items'][0]['snippet']['channelId']
        channel_name = search_response['items'][0]['snippet']['title']
        
        # Get uploads playlist
        channel_response = youtube.channels().list( # pylint: disable=no-member
            part='contentDetails',
            id=channel_id
        ).execute()
        
        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Get videos with filtering
        videos = []
        next_page_token = None
        total_checked = 0
        filter_stats = {'included': 0, 'excluded': 0, 'no_match': 0}
        
        videos_to_check = max_results * 3 if filter_missing_persons else max_results
        
        print(f"Searching through videos with optimized fuzzy matching (threshold: {fuzzy_threshold})...")
        
        api_calls = 0  # Track API calls for monitoring
        
        while len(videos) < max_results and total_checked < videos_to_check:
            # Get playlist items
            playlist_response = youtube.playlistItems().list(# pylint: disable=no-member
                part='snippet,contentDetails',
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            api_calls += 1
            
            # OPTIMIZATION: Collect all video IDs from this page
            video_ids_batch = []
            for item in playlist_response['items']:
                video_id = item['snippet']['resourceId']['videoId']
                video_ids_batch.append(video_id)
            
            # Fetch video details in batch
            if video_ids_batch:
                video_details_response = youtube.videos().list(# pylint: disable=no-member
                    part='snippet,contentDetails',
                    id=','.join(video_ids_batch)  # Request up to 50 videos at once
                ).execute()
                api_calls += 1
                
                # Process all videos from the batch
                for video_detail in video_details_response['items']:
                    total_checked += 1
                    video_id = video_detail['id']
                    snippet = video_detail['snippet']
                    title = snippet['title']
                    description = snippet.get('description', '')
                    
                    # Apply fuzzy filter
                    should_include, reason = should_include_video(title, description)
                    
                    if should_include:
                        videos.append({
                            'video_id': video_id,
                            'title': title,
                            'description': description,
                            'channel_name': channel_name,
                            'published_date': snippet['publishedAt'],
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'duration': video_detail['contentDetails']['duration'],
                            'match_reason': reason
                        })
                        filter_stats['included'] += 1
                        
                        # Print match details for first few
                        if len(videos) <= 3:
                            print(f"  ✓ '{title[:50]}...' - {reason}")
                        
                        if len(videos) >= max_results:
                            break
                    else:
                        if 'Excluded' in reason:
                            filter_stats['excluded'] += 1
                        else:
                            filter_stats['no_match'] += 1
            
            next_page_token = playlist_response.get('nextPageToken')
            if not next_page_token:
                break
        
        print(f"\n{'='*60}")
        print(f"Search complete!")
        print(f"Total videos checked: {total_checked}")
        print(f"Included: {filter_stats['included']}")
        print(f"Excluded: {filter_stats['excluded']}")
        print(f"No match: {filter_stats['no_match']}")
        print(f"{'='*60}\n")
        
        return videos
    
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        return []

def parse_duration(duration_str):
    """Convert ISO 8601 duration to seconds"""
    if not duration_str:
        return None
    
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return None
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    
    return hours * 3600 + minutes * 60 + seconds

def save_video_metadata(video_data):
    """Save video metadata to database"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Extract score from match_reason if present
        match_score = None
        if video_data.get('match_reason'):
            import re
            score_match = re.search(r'score: (\d+)', video_data['match_reason'])
            if score_match:
                match_score = int(score_match.group(1))
        
        cursor.execute('''
            INSERT OR REPLACE INTO videos 
            (video_id, title, description, channel_name, published_date, url, 
            duration_seconds, match_reason, match_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            video_data['video_id'],
            video_data['title'],
            video_data.get('description', ''),
            video_data['channel_name'],
            video_data['published_date'],
            video_data['url'],
            parse_duration(video_data.get('duration')),
            video_data.get('match_reason'),
            match_score
        ))
        conn.commit()

def download_and_save_transcript(video_id: str):
    """Download transcript and save to database"""
    try:
        # Get transcript
        transcript_list = YouTubeTranscriptApi.fetch(video_id)
        
        # Combine all text
        full_transcript = ' '.join([entry['text'] for entry in transcript_list])
        word_count = len(full_transcript.split())
        
        # Save to database
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Update video record
        cursor.execute('''
            UPDATE videos 
            SET transcript_available = 1, downloaded_date = ?
            WHERE video_id = ?
        ''', (datetime.now().isoformat(), video_id))
        
        # Insert transcript
        cursor.execute('''
            INSERT OR REPLACE INTO transcripts (video_id, full_text, word_count)
            VALUES (?, ?, ?)
        ''', (video_id, full_transcript, word_count))
        
        conn.commit()
        conn.close()
        
        return True, word_count
        
    except Exception as e:
        return False, str(e)
    
def test_fuzzy_thresholds(channel_url):
    """Test different threshold values to find optimal setting"""
    thresholds = [70, 80, 85, 90, 95]
    
    print("Testing different fuzzy match thresholds...\n")
    
    for threshold in thresholds:
        print(f"\n{'='*60}")
        print(f"THRESHOLD: {threshold}")
        print(f"{'='*60}")
        
        videos = get_channel_videos(
            channel_url,
            max_results=20,
            filter_missing_persons=True,
            fuzzy_threshold=threshold
        )
        
        print(f"\nFound {len(videos)} videos with threshold {threshold}")
        print("\nSample matches:")
        for video in videos[:3]:
            print(f"  - {video['title']}")
            print(f"    Reason: {video.get('match_reason', 'N/A')}")

def analyze_match_quality():
    """Analyze how well videos matched"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
    
        df = pd.read_sql_query('''
            SELECT title, match_reason, match_score
            FROM videos
            WHERE match_score IS NOT NULL
            ORDER BY match_score DESC
        ''', conn)
        
        print("Match Quality Analysis:")
        print(f"\nAverage match score: {df['match_score'].mean():.1f}")
        print(f"Median match score: {df['match_score'].median():.1f}")
        print(f"Min match score: {df['match_score'].min()}")
        print(f"Max match score: {df['match_score'].max()}")
        
        print("\nTop matches:")
        print(df.head(10))
        
        print("\nLowest scoring matches (might be false positives):")
        print(df.tail(5))
    
def main():
    # Create database
    create_database()
    youtube = get_youtube_client()

    # Channel URL
    channel_urls = {"vanishedpodcast8746": "https://www.youtube.com/@vanishedpodcast8746",
                    "TheUnfoundPodcastChannel": "https://www.youtube.com/@TheUnfoundPodcastChannel",
                    "magillfoote": "https://www.youtube.com/@magillfoote",
                    "TraceEvidencePodcast": "https://www.youtube.com/@TraceEvidencePodcast",
                    "ninainnsted9107": "https://www.youtube.com/@ninainnsted9107"}
    
    print("Fetching videos from channels...")
    videos = dict.fromkeys(channel_urls.keys(), [])
    for channel, channel_url in channel_urls.items():
        print(f"\nProcessing channel: {channel}")
        videos[channel] = get_channel_videos(
            channel_url,
            max_results=100,
            filter_missing_persons=True,
            fuzzy_threshold=85
        )
    
    if not any(videos.values()):
        print("No videos found or error occurred")
        return
    
    print(f"\nFound {len(videos)} videos.")
    print("Saving metadata to database...")
    
    # Save all video metadata first
    for video_list in videos.values():
        for video in video_list:
            save_video_metadata(video)
    
    print("Metadata saved! Now downloading transcripts...\n")
    
    successful = 0
    failed = 0
    
    for channel, video_list in videos.items():
        print(f"\nChannel: {channel} - Downloading transcripts")
        for video in video_list:
            success, result = download_and_save_transcript(video['video_id'])
            
            if success:
                print(f"✓ {video['title'][:60]}... ({result} words)")
                successful += 1
            else:
                print(f"✗ {video['title'][:60]}... (Error: {result})")
                failed += 1
    
    print(f"\n{'='*80}")
    print("Download complete!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Data saved to '{DB_NAME}'")

if __name__ == "__main__":
    main()