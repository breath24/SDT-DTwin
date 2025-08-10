# Implement Text Analysis Library

Create a comprehensive text analysis system in `text_analyzer.py` with the following components:

## Core Analysis Functions
1. **`TextAnalyzer` class** - Main analyzer with:
   - `__init__(text: str)` - Initialize with input text
   - `word_frequency()` - Return dictionary of word frequencies
   - `character_frequency()` - Return character frequency analysis
   - `sentence_count()` - Count sentences in text
   - `paragraph_count()` - Count paragraphs
   - `reading_time(wpm=200)` - Estimate reading time in minutes
   - `complexity_score()` - Calculate text complexity (Flesch reading ease)

## Advanced Analysis
1. **Sentiment Analysis**:
   - `basic_sentiment()` - Simple positive/negative/neutral classification
   - `sentiment_score()` - Return numerical sentiment score (-1 to 1)
   - `emotion_detection()` - Detect emotions (joy, anger, fear, etc.)

2. **Language Patterns**:
   - `find_patterns(regex_pattern)` - Find regex patterns in text
   - `extract_entities()` - Extract emails, URLs, phone numbers
   - `keyword_density(keyword)` - Calculate keyword density percentage
   - `n_grams(n=2)` - Generate n-grams from text

## Text Processing
1. **Preprocessing**:
   - `clean_text()` - Remove special characters, normalize whitespace
   - `remove_stopwords(language='english')` - Remove common words
   - `stem_words()` - Basic word stemming
   - `normalize_case()` - Convert to lowercase with proper handling

2. **Statistics**:
   - `average_word_length()` - Average character length of words
   - `sentence_length_stats()` - Min, max, average sentence lengths
   - `vocabulary_richness()` - Unique words / total words ratio
   - `text_summary()` - Return comprehensive analysis dictionary

## File Operations
1. **I/O Functions**:
   - `analyze_file(filepath)` - Analyze text from file
   - `analyze_multiple_files(file_list)` - Batch analysis
   - `export_analysis(output_file, format='json')` - Export results
   - `compare_texts(text1, text2)` - Compare two texts

## Visualization
1. **`TextVisualizer` class** - Generate analysis visualizations:
   - `word_cloud_data()` - Data for word cloud generation
   - `frequency_chart_data()` - Data for frequency charts
   - `sentiment_timeline()` - Sentiment changes over text sections

Include proper error handling, input validation, and support for multiple languages where applicable. Make all tests pass with `python -m pytest`.
