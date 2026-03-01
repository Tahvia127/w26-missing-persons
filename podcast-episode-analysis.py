import sqlite3
import pandas as pd
import re
from collections import defaultdict
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

DB_NAME = 'podcast.db'

keyword_categories = {
        'Demographics - Age': [
            "young", "teen", "teenager", "elderly", "child", "adult", "years old",
            "young woman", "young man", "little girl", "little boy"
        ],
        'Demographics - Race/Ethnicity': [
            "white", "Black", "African American", "Hispanic", "Latino", "Latina",
            "Asian", "Native American", "Indigenous", "biracial", "mixed race"
        ],
        'Demographics - Gender/Family Role': [
            "woman", "man", "girl", "boy", "mother", "father", "daughter", "son",
            "wife", "husband", "sister", "brother", "parent"
        ],
        'Framing - Sympathetic': [
            "beloved", "promising", "bright future", "loving family", "devoted",
            "pillar of the community", "honor student", "everyone loved",
            "beautiful", "smart", "kind", "gentle", "innocent", "vibrant",
            "full of life", "would never", "out of character", "always called",
            "close with family", "good student", "college bound", "dreams of"
        ],
        'Framing - Risk': [
            "troubled", "history of", "struggle", "addiction", "runaway",
            "estranged", "last seen at a bar", "known to", "lifestyle",
            "mental health", "depression", "drugs", "alcohol", "prostitution",
            "transient", "homeless", "hitchhiking", "bad crowd", "boyfriend",
            "domestic", "turbulent", "unstable", "prior disappearance"
        ],
        'Coverage - High Coverage Indicators': [
            "breaking news", "urgent", "amber alert", "massive search",
            "volunteer", "reward", "national attention", "vigil", "billboard",
            "tip line", "press conference", "exhaustive search"
        ],
        'Coverage - Low Coverage Indicators': [
            "cold case", "little coverage", "forgotten", "overlooked", "finally",
            "years later", "no media", "family fought", "ignored"
        ],
        'Sources': [
            "police say", "family believes", "according to", "investigators",
            "spokesperson", "detective", "sheriff", "FBI", "search and rescue",
            "medical examiner", "coroner"
        ]
    }

# Flatten all keywords into single list
all_keywords = []
for keywords in keyword_categories.values():
    all_keywords.extend(keywords)

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
        list of tuples: (matched_keyword, score, matched_text)
    """
    if not text or not keywords:
        return []
    
    text_lower = text.lower()
    matches = []
    
    # Strategy 1: Direct exact substring match (fastest)
    for keyword in keywords:
        if keyword.lower() in text_lower:
            matches.append((keyword, 100, keyword))
    
    # If we found exact matches, return them
    if matches:
        return matches
    
    # Strategy 2: Use process.extractOne for efficient fuzzy matching
    if use_partial:
        # For multi-word keywords, extract n-grams from text
        max_keyword_words = max(len(kw.split()) for kw in keywords)
        ngrams = extract_ngrams(text, max_n=max_keyword_words)
        
        if ngrams:
            # Find best matching ngram for each keyword
            for keyword in keywords:
                best_ngram_match = process.extractOne(
                    keyword.lower(),
                    ngrams,
                    scorer=fuzz.ratio
                )
                
                if best_ngram_match and best_ngram_match[1] >= threshold:
                    matches.append((keyword, best_ngram_match[1], best_ngram_match[0]))
    
    # Strategy 3: Fallback to direct keyword comparison
    if not matches:
        for keyword in keywords:
            best_match = process.extractOne(
                keyword.lower(),
                [text_lower],
                scorer=fuzz.partial_ratio if use_partial else fuzz.ratio
            )
            
            if best_match and best_match[1] >= threshold:
                matches.append((keyword, best_match[1], best_match[0]))
    
    return matches

def load_transcripts_from_db(limit=None, video_id=None):
    """
    Load transcripts from database
    
    Args:
        limit: Number of transcripts to load (None = all)
        video_id: Specific video ID to load (for testing)
    """
    with sqlite3.connect(DB_NAME) as conn:
        query = '''
            SELECT v.video_id, v.title, v.channel_name, t.full_text, t.word_count
            FROM transcripts t
            JOIN videos v ON t.video_id = v.video_id
            WHERE t.full_text IS NOT NULL
        '''
        
        params = []
        if video_id:
            query += ' AND v.video_id = ?'
            params.append(video_id)
        
        if limit:
            query += f' LIMIT {limit}'
        
        if params:
            df = pd.read_sql_query(query, conn, params=params)
        else:
            df = pd.read_sql_query(query, conn)
    
    print(f"Loaded {len(df)} transcript(s) from database")
    return df

def split_into_sentences(text):
    """Split text into sentences using basic rules"""
    # Replace common abbreviations to avoid false splits
    text = re.sub(r'Mr\.', 'Mr', text)
    text = re.sub(r'Mrs\.', 'Mrs', text)
    text = re.sub(r'Dr\.', 'Dr', text)
    text = re.sub(r'St\.', 'St', text)
    
    # Split on sentence endings
    sentences = re.split(r'[.!?]+\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def find_keyword_with_context_fuzzy(text, keywords, context_sentences=2, fuzzy_threshold=85):
    """
    Find all occurrences of keywords (with fuzzy matching) and extract surrounding context
    
    Args:
        text: Full transcript text
        keywords: List of keywords to search for
        context_sentences: Number of sentences before/after to include
        fuzzy_threshold: Minimum similarity score (0-100) for fuzzy matching
    
    Returns:
        List of dicts with keyword matches
    """
    sentences = split_into_sentences(text)
    results = []
    
    for i, sentence in enumerate(sentences):
        # Use fuzzy matching to find keywords in this sentence
        matches = optimized_fuzzy_match(sentence, keywords, threshold=fuzzy_threshold)
        
        for keyword, score, matched_text in matches:
            # Get surrounding sentences for context
            start_idx = max(0, i - context_sentences)
            end_idx = min(len(sentences), i + context_sentences + 1)
            
            context = ' '.join(sentences[start_idx:end_idx])
            
            results.append({
                'keyword': keyword,
                'matched_text': matched_text,
                'fuzzy_score': score,
                'sentence': sentence,
                'context': context
            })
    
    return results

def search_transcripts_for_keywords(df, keywords, fuzzy_threshold=85):
    """
    Search all transcripts for keywords using fuzzy matching
    
    Args:
        df: DataFrame with transcripts
        keywords: List of keywords to search for
        fuzzy_threshold: Minimum similarity score (0-100)
    
    Returns:
        DataFrame with detailed results
    """
    results = []
    
    total = len(df)
    for idx, row in df.iterrows():
        video_id = row['video_id']
        title = row['title']
        channel = row['channel_name']
        text = row['full_text']
        
        print(f"Processing [{idx+1}/{total}]: {title[:50]}...")
        
        # Use fuzzy matching function
        matches = find_keyword_with_context_fuzzy(text, keywords, 
                                                   context_sentences=2, 
                                                   fuzzy_threshold=fuzzy_threshold)
        
        # Group matches by keyword
        keyword_groups = defaultdict(list)
        for match in matches:
            keyword_groups[match['keyword']].append(match)
        
        # Create results for each keyword
        for keyword, keyword_matches in keyword_groups.items():
            count = len(keyword_matches)
            
            # Combine all context snippets
            context_snippets = [m['context'] for m in keyword_matches]
            
            # Get fuzzy scores
            fuzzy_scores = [m['fuzzy_score'] for m in keyword_matches]
            avg_score = sum(fuzzy_scores) / len(fuzzy_scores)
            
            results.append({
                'video_id': video_id,
                'episode_title': title,
                'channel': channel,
                'keyword': keyword,
                'count': count,
                'avg_fuzzy_score': round(avg_score, 1),
                'context_snippets': ' | '.join(context_snippets)
            })
        
        print(f"  Found {len(matches)} total keyword matches (fuzzy threshold: {fuzzy_threshold})")
    
    results_df = pd.DataFrame(results)
    print(f"\nFound {len(results_df)} unique keyword matches across all episodes")
    return results_df

def create_summary_statistics(results_df, keywords):
    """Create summary statistics showing keyword frequency"""
    summary = []
    
    for keyword in keywords:
        keyword_data = results_df[results_df['keyword'] == keyword]
        
        total_occurrences = keyword_data['count'].sum() if not keyword_data.empty else 0
        episodes_with_keyword = len(keyword_data)
        avg_per_episode = keyword_data['count'].mean() if not keyword_data.empty else 0
        max_in_episode = keyword_data['count'].max() if not keyword_data.empty else 0
        avg_fuzzy_score = keyword_data['avg_fuzzy_score'].mean() if not keyword_data.empty else 0
        
        summary.append({
            'keyword': keyword,
            'total_occurrences': total_occurrences,
            'episodes_containing': episodes_with_keyword,
            'avg_per_episode': round(avg_per_episode, 2),
            'max_in_single_episode': max_in_episode,
            'avg_fuzzy_match_score': round(avg_fuzzy_score, 1)
        })
    
    summary_df = pd.DataFrame(summary)
    summary_df = summary_df.sort_values('total_occurrences', ascending=False)
    
    return summary_df

def create_category_summary(results_df, keyword_categories):
    """
    Create summary grouped by keyword categories
    
    Args:
        results_df: DataFrame with detailed results
        keyword_categories: Dictionary mapping category names to keyword lists
    
    Returns:
        DataFrame with category-level statistics
    """
    category_summary = []
    
    for category, keywords in keyword_categories.items():
        # Filter results for keywords in this category
        category_data = results_df[results_df['keyword'].isin(keywords)]
        
        total_occurrences = category_data['count'].sum() if not category_data.empty else 0
        episodes_with_category = len(category_data['episode_title'].unique()) if not category_data.empty else 0
        unique_keywords_found = len(category_data['keyword'].unique()) if not category_data.empty else 0
        
        category_summary.append({
            'category': category,
            'total_occurrences': total_occurrences,
            'episodes_containing': episodes_with_category,
            'unique_keywords_found': unique_keywords_found,
            'keywords_in_category': len(keywords)
        })
    
    category_df = pd.DataFrame(category_summary)
    category_df = category_df.sort_values('total_occurrences', ascending=False)
    
    return category_df

def compare_sympathetic_vs_risk(results_df, sympathetic_keywords, risk_keywords):
    """
    Compare sympathetic vs risk language usage per episode
    
    Returns:
        DataFrame showing balance of sympathetic vs risk language
    """
    # Get unique episodes
    episodes = results_df['episode_title'].unique()
    
    comparison = []
    
    for episode in episodes:
        episode_data = results_df[results_df['episode_title'] == episode]
        
        sympathetic_count = episode_data[episode_data['keyword'].isin(sympathetic_keywords)]['count'].sum()
        risk_count = episode_data[episode_data['keyword'].isin(risk_keywords)]['count'].sum()
        
        total = sympathetic_count + risk_count
        
        if total > 0:
            sympathetic_ratio = sympathetic_count / total
            
            comparison.append({
                'episode_title': episode,
                'sympathetic_mentions': sympathetic_count,
                'risk_mentions': risk_count,
                'total_mentions': total,
                'sympathetic_ratio': round(sympathetic_ratio, 2),
                'language_bias': 'Sympathetic' if sympathetic_ratio > 0.6 else 'Risk-focused' if sympathetic_ratio < 0.4 else 'Balanced'
            })
    
    comparison_df = pd.DataFrame(comparison)
    comparison_df = comparison_df.sort_values('total_mentions', ascending=False)
    
    return comparison_df

def analyze_coverage_patterns(results_df, coverage_keywords):
    """
    Analyze high vs low coverage indicators
    """
    high_coverage_keywords = [
        "breaking news", "urgent", "amber alert", "massive search",
        "volunteer", "reward", "national attention", "vigil", "billboard",
        "tip line", "press conference", "exhaustive search"
    ]
    
    low_coverage_keywords = [
        "cold case", "little coverage", "forgotten", "overlooked", "finally",
        "years later", "no media", "family fought", "ignored"
    ]
    
    episodes = results_df['episode_title'].unique()
    
    coverage_analysis = []
    
    for episode in episodes:
        episode_data = results_df[results_df['episode_title'] == episode]
        
        high_coverage = episode_data[episode_data['keyword'].isin(high_coverage_keywords)]['count'].sum()
        low_coverage = episode_data[episode_data['keyword'].isin(low_coverage_keywords)]['count'].sum()
        
        if high_coverage > 0 or low_coverage > 0:
            coverage_analysis.append({
                'episode_title': episode,
                'high_coverage_mentions': high_coverage,
                'low_coverage_mentions': low_coverage,
                'coverage_type': 'High Coverage' if high_coverage > low_coverage else 'Low Coverage' if low_coverage > high_coverage else 'Mixed'
            })
    
    coverage_df = pd.DataFrame(coverage_analysis)
    
    return coverage_df

def export_results(results_df, summary_df, category_df=None, comparison_df=None, 
                  coverage_df=None, output_prefix='keyword_analysis'):
    """Export results to CSV files"""
    
    # Export detailed results
    detailed_file = f'{output_prefix}_detailed.csv'
    results_df.to_csv(detailed_file, index=False)
    print(f"\n✓ Detailed results saved to: {detailed_file}")
    
    # Export keyword summary
    summary_file = f'{output_prefix}_summary.csv'
    summary_df.to_csv(summary_file, index=False)
    print(f"✓ Keyword summary saved to: {summary_file}")
    
    # Export category summary if provided
    if category_df is not None:
        category_file = f'{output_prefix}_category_summary.csv'
        category_df.to_csv(category_file, index=False)
        print(f"✓ Category summary saved to: {category_file}")
    
    # Export sympathetic vs risk comparison
    if comparison_df is not None:
        comparison_file = f'{output_prefix}_sympathetic_vs_risk.csv'
        comparison_df.to_csv(comparison_file, index=False)
        print(f"✓ Sympathetic vs Risk comparison saved to: {comparison_file}")
    
    # Export coverage analysis
    if coverage_df is not None:
        coverage_file = f'{output_prefix}_coverage_analysis.csv'
        coverage_df.to_csv(coverage_file, index=False)
        print(f"✓ Coverage analysis saved to: {coverage_file}")
    
    # Print summaries to console
    if category_df is not None:
        print(f"\n{'='*60}")
        print("CATEGORY SUMMARY")
        print(f"{'='*60}")
        print(category_df.to_string(index=False))
    
    print(f"\n{'='*60}")
    print("TOP 20 KEYWORDS BY FREQUENCY")
    print(f"{'='*60}")
    print(summary_df.head(20).to_string(index=False))
    print(f"{'='*60}")

def analyze_transcripts(keywords, keyword_categories=None, output_prefix='keyword_analysis',
                       fuzzy_threshold=85, test_mode=False, test_video_id=None):
    """
    Main function to analyze transcripts for keywords
    
    Args:
        keywords: List of keywords to search for
        keyword_categories: Optional dict mapping category names to keyword lists
        output_prefix: Prefix for output CSV files
        fuzzy_threshold: Similarity threshold for fuzzy matching (0-100)
        test_mode: If True, only analyze one transcript
        test_video_id: Specific video ID to test (if None, uses first transcript)
    """
    print(f"Starting keyword analysis for {len(keywords)} keywords...")
    print(f"Fuzzy matching threshold: {fuzzy_threshold}")
    print(f"Keywords: {', '.join(keywords[:10])}... (showing first 10)\n")
    
    # Load transcripts with test mode support
    if test_mode:
        print("⚠️  TEST MODE: Analyzing only ONE transcript\n")
        transcripts_df = load_transcripts_from_db(limit=1 if not test_video_id else None, 
                                                   video_id=test_video_id)
    else:
        transcripts_df = load_transcripts_from_db()
    
    if transcripts_df.empty:
        print("No transcripts found in database!")
        return None, None, None
    
    # Pass fuzzy_threshold to search function
    results_df = search_transcripts_for_keywords(transcripts_df, keywords, fuzzy_threshold)
    
    if results_df.empty:
        print("No matches found for any keywords!")
        return None, None, None
    
    # Create summary statistics
    summary_df = create_summary_statistics(results_df, keywords)
    
    # Create category summary if categories provided
    category_df = None
    if keyword_categories:
        category_df = create_category_summary(results_df, keyword_categories)
    
    return results_df, summary_df, category_df

def test_single_transcript(fuzzy_threshold=85):
    """
    Test keyword analysis on a single transcript
    """

    print("TEST MODE - SINGLE TRANSCRIPT ANALYSIS")

    results_df, summary_df, category_df = analyze_transcripts(
        keywords=all_keywords,
        keyword_categories=keyword_categories,
        output_prefix='test_single_transcript',
        fuzzy_threshold=fuzzy_threshold,
        test_mode=True  # ENABLE TEST MODE
    )
    
    if results_df is not None:
        print("\n" + "="*80)
        print("TEST RESULTS PREVIEW")
        print("="*80)
        print("\nSample matches with context:")
        for i, row in results_df.head(5).iterrows():
            print(f"\nKeyword: {row['keyword']}")
            print(f"Count: {row['count']}")
            print(f"Fuzzy Score: {row['avg_fuzzy_score']}")
            print(f"Context: {row['context_snippets'][:200]}...")
    
    return results_df, summary_df, category_df

def main():    
    print(f"Analyzing {len(all_keywords)} keywords across {len(keyword_categories)} categories\n")
    
    # Run main analysis
    results_df, summary_df, category_df = analyze_transcripts(
        keywords=all_keywords,
        keyword_categories=keyword_categories,
        output_prefix='comprehensive_analysis'
    )
    
    if results_df.empty:
        print("No results found!")
        return
    
    # Additional specialized analyses
    print("\n" + "="*60)
    print("RUNNING SPECIALIZED ANALYSES...")
    print("="*60)
    
    # Sympathetic vs Risk comparison
    sympathetic_keywords = keyword_categories['Framing - Sympathetic']
    risk_keywords = keyword_categories['Framing - Risk']
    comparison_df = compare_sympathetic_vs_risk(results_df, sympathetic_keywords, risk_keywords)
    
    print(f"\n{'='*60}")
    print("SYMPATHETIC VS RISK LANGUAGE - TOP 10 EPISODES")
    print(f"{'='*60}")
    print(comparison_df.head(10).to_string(index=False))
    
    # Coverage analysis
    coverage_keywords = keyword_categories['Coverage - High Coverage Indicators'] + \
                       keyword_categories['Coverage - Low Coverage Indicators']
    coverage_df = analyze_coverage_patterns(results_df, coverage_keywords)
    
    print(f"\n{'='*60}")
    print("COVERAGE PATTERNS")
    print(f"{'='*60}")
    print(coverage_df.head(10).to_string(index=False))
    
    # Export all results
    export_results(results_df, summary_df, category_df, comparison_df, coverage_df, 
                  output_prefix='comprehensive_analysis')
    
    # Generate insights report
    generate_insights_report(results_df, category_df, comparison_df, coverage_df)
    
    return results_df, summary_df, category_df, comparison_df, coverage_df

def generate_insights_report(results_df, category_df, comparison_df, coverage_df):
    """Generate a text report with key insights"""
    
    report = []
    report.append("="*80)
    report.append("MISSING PERSONS PODCAST ANALYSIS - KEY INSIGHTS")
    report.append("="*80)
    report.append("")
    
    # Overall statistics
    total_episodes = results_df['episode_title'].nunique()
    total_keywords_found = results_df['keyword'].nunique()
    total_mentions = results_df['count'].sum()
    
    report.append(f"OVERALL STATISTICS:")
    report.append(f"  Total episodes analyzed: {total_episodes}")
    report.append(f"  Unique keywords found: {total_keywords_found}")
    report.append(f"  Total keyword mentions: {total_mentions}")
    report.append("")
    
    # Category breakdown
    report.append("CATEGORY BREAKDOWN:")
    for _, row in category_df.iterrows():
        report.append(f"  {row['category']}: {int(row['total_occurrences'])} mentions across {int(row['episodes_containing'])} episodes")
    report.append("")
    
    # Sympathetic vs Risk analysis
    if comparison_df is not None and not comparison_df.empty:
        sympathetic_heavy = len(comparison_df[comparison_df['language_bias'] == 'Sympathetic'])
        risk_heavy = len(comparison_df[comparison_df['language_bias'] == 'Risk-focused'])
        balanced = len(comparison_df[comparison_df['language_bias'] == 'Balanced'])
        
        report.append("FRAMING ANALYSIS:")
        report.append(f"  Sympathetic-heavy episodes: {sympathetic_heavy}")
        report.append(f"  Risk-focused episodes: {risk_heavy}")
        report.append(f"  Balanced episodes: {balanced}")
        
        avg_sympathetic_ratio = comparison_df['sympathetic_ratio'].mean()
        report.append(f"  Average sympathetic ratio: {avg_sympathetic_ratio:.2f}")
        report.append("")
    
    # Coverage analysis
    if coverage_df is not None and not coverage_df.empty:
        high_coverage = len(coverage_df[coverage_df['coverage_type'] == 'High Coverage'])
        low_coverage = len(coverage_df[coverage_df['coverage_type'] == 'Low Coverage'])
        
        report.append("COVERAGE ANALYSIS:")
        report.append(f"  High coverage cases: {high_coverage}")
        report.append(f"  Low coverage cases: {low_coverage}")
        report.append("")
    
    report.append("="*80)
    
    # Print report
    report_text = "\n".join(report)
    print("\n" + report_text)
    
    # Save report to file
    with open('comprehensive_analysis_insights.txt', 'w') as f:
        f.write(report_text)
    
    print("\n✓ Insights report saved to: comprehensive_analysis_insights.txt")

# ============================================================================
# RUN ANALYSIS
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Check for test mode flag
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        # RUN TEST MODE
        print("Running in TEST mode (single transcript)\n")
        test_single_transcript(fuzzy_threshold=85)
    else:
        # RUN FULL ANALYSIS
        print("Running FULL analysis (all transcripts)\n")
        print("To run test mode, use: python script.py test\n")
        
        results_df, summary_df, category_df = main()