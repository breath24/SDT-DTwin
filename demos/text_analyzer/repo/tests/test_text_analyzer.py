import pytest
import tempfile
import os
from text_analyzer import (
    TextAnalyzer, TextVisualizer, analyze_file, analyze_multiple_files,
    export_analysis, compare_texts, get_stopwords, simple_stemmer,
    calculate_similarity
)

class TestTextAnalyzer:
    """Test cases for TextAnalyzer class."""
    
    @pytest.fixture
    def sample_text(self):
        return """Hello world! This is a sample text for testing. 
        It contains multiple sentences and paragraphs.
        
        This is the second paragraph. It has different content.
        The text analyzer should handle this properly."""
    
    @pytest.fixture
    def analyzer(self, sample_text):
        return TextAnalyzer(sample_text)
    
    def test_initialization(self, sample_text):
        """Test TextAnalyzer initialization."""
        analyzer = TextAnalyzer(sample_text)
        assert hasattr(analyzer, 'text')
    
    def test_word_frequency(self, analyzer):
        """Test word frequency analysis."""
        freq = analyzer.word_frequency()
        assert isinstance(freq, dict)
        assert len(freq) > 0
        assert all(isinstance(word, str) for word in freq.keys())
        assert all(isinstance(count, int) for count in freq.values())
        assert all(count > 0 for count in freq.values())
    
    def test_character_frequency(self, analyzer):
        """Test character frequency analysis."""
        char_freq = analyzer.character_frequency()
        assert isinstance(char_freq, dict)
        assert len(char_freq) > 0
        # Should contain letters and possibly punctuation
        assert any(c.isalpha() for c in char_freq.keys())
    
    def test_sentence_count(self, analyzer):
        """Test sentence counting."""
        count = analyzer.sentence_count()
        assert isinstance(count, int)
        assert count > 0
        # Sample text should have at least 4 sentences
        assert count >= 4
    
    def test_paragraph_count(self, analyzer):
        """Test paragraph counting."""
        count = analyzer.paragraph_count()
        assert isinstance(count, int)
        assert count >= 2  # Sample text has 2 paragraphs
    
    def test_reading_time(self, analyzer):
        """Test reading time calculation."""
        time = analyzer.reading_time(wpm=200)
        assert isinstance(time, float)
        assert time > 0
        
        # Test different WPM
        time_fast = analyzer.reading_time(wpm=400)
        assert time_fast < time  # Faster reading should take less time
    
    def test_complexity_score(self, analyzer):
        """Test complexity score calculation."""
        score = analyzer.complexity_score()
        assert isinstance(score, float)
        # Flesch score typically ranges from 0-100
        assert 0 <= score <= 100
    
    def test_basic_sentiment(self, analyzer):
        """Test basic sentiment analysis."""
        sentiment = analyzer.basic_sentiment()
        assert sentiment in ['positive', 'negative', 'neutral']
    
    def test_sentiment_score(self, analyzer):
        """Test numerical sentiment scoring."""
        score = analyzer.sentiment_score()
        assert isinstance(score, float)
        assert -1 <= score <= 1
    
    def test_emotion_detection(self, analyzer):
        """Test emotion detection."""
        emotions = analyzer.emotion_detection()
        assert isinstance(emotions, dict)
        expected_emotions = ['joy', 'anger', 'fear', 'sadness', 'surprise', 'disgust']
        assert all(emotion in expected_emotions for emotion in emotions.keys())
        assert all(isinstance(score, float) for score in emotions.values())
    
    def test_find_patterns(self, analyzer):
        """Test regex pattern finding."""
        # Find words starting with 'th'
        patterns = analyzer.find_patterns(r'\bth\w+')
        assert isinstance(patterns, list)
        assert all(isinstance(match, str) for match in patterns)
        # Should find words like "this", "the", "text"
        assert len(patterns) > 0
    
    def test_extract_entities(self, analyzer):
        """Test entity extraction."""
        entities = analyzer.extract_entities()
        assert isinstance(entities, dict)
        expected_types = ['emails', 'urls', 'phone_numbers']
        assert all(entity_type in expected_types for entity_type in entities.keys())
        assert all(isinstance(entity_list, list) for entity_list in entities.values())
    
    def test_keyword_density(self, analyzer):
        """Test keyword density calculation."""
        density = analyzer.keyword_density('text')
        assert isinstance(density, float)
        assert 0 <= density <= 100  # Percentage
        
        # Non-existent word should have 0 density
        zero_density = analyzer.keyword_density('nonexistentword')
        assert zero_density == 0
    
    def test_n_grams(self, analyzer):
        """Test n-gram generation."""
        bigrams = analyzer.n_grams(2)
        assert isinstance(bigrams, list)
        assert all(isinstance(gram, tuple) for gram in bigrams)
        assert all(len(gram) == 2 for gram in bigrams)
        
        trigrams = analyzer.n_grams(3)
        assert all(len(gram) == 3 for gram in trigrams)
    
    def test_clean_text(self, analyzer):
        """Test text cleaning."""
        cleaned = analyzer.clean_text()
        assert isinstance(cleaned, str)
        assert len(cleaned) > 0
    
    def test_remove_stopwords(self, analyzer):
        """Test stopword removal."""
        no_stopwords = analyzer.remove_stopwords()
        assert isinstance(no_stopwords, str)
        # Should be shorter than original (assuming stopwords were present)
        assert len(no_stopwords) <= len(analyzer.text)
    
    def test_stem_words(self, analyzer):
        """Test word stemming."""
        stemmed = analyzer.stem_words()
        assert isinstance(stemmed, str)
        assert len(stemmed) > 0
    
    def test_normalize_case(self, analyzer):
        """Test case normalization."""
        normalized = analyzer.normalize_case()
        assert isinstance(normalized, str)
        assert normalized.islower() or not normalized.isalpha()
    
    def test_average_word_length(self, analyzer):
        """Test average word length calculation."""
        avg_length = analyzer.average_word_length()
        assert isinstance(avg_length, float)
        assert avg_length > 0
        # English words typically average 4-5 characters
        assert 2 <= avg_length <= 10
    
    def test_sentence_length_stats(self, analyzer):
        """Test sentence length statistics."""
        stats = analyzer.sentence_length_stats()
        assert isinstance(stats, dict)
        required_keys = ['min', 'max', 'average']
        assert all(key in stats for key in required_keys)
        assert all(isinstance(stats[key], (int, float)) for key in required_keys)
        assert stats['min'] <= stats['average'] <= stats['max']
    
    def test_vocabulary_richness(self, analyzer):
        """Test vocabulary richness calculation."""
        richness = analyzer.vocabulary_richness()
        assert isinstance(richness, float)
        assert 0 < richness <= 1  # Should be between 0 and 1
    
    def test_text_summary(self, analyzer):
        """Test comprehensive text summary."""
        summary = analyzer.text_summary()
        assert isinstance(summary, dict)
        # Should contain various analysis results
        expected_keys = [
            'word_count', 'sentence_count', 'paragraph_count',
            'reading_time', 'complexity_score', 'sentiment'
        ]
        assert any(key in summary for key in expected_keys)

class TestTextVisualizer:
    """Test cases for TextVisualizer class."""
    
    @pytest.fixture
    def analyzer(self):
        text = "The quick brown fox jumps over the lazy dog. The dog was sleeping."
        return TextAnalyzer(text)
    
    @pytest.fixture
    def visualizer(self, analyzer):
        return TextVisualizer(analyzer)
    
    def test_visualizer_initialization(self, analyzer):
        """Test TextVisualizer initialization."""
        visualizer = TextVisualizer(analyzer)
        assert hasattr(visualizer, 'analyzer')
    
    def test_word_cloud_data(self, visualizer):
        """Test word cloud data generation."""
        data = visualizer.word_cloud_data(max_words=50)
        assert isinstance(data, dict)
        assert len(data) <= 50
        assert all(isinstance(word, str) for word in data.keys())
        assert all(isinstance(count, int) for count in data.values())
    
    def test_frequency_chart_data(self, visualizer):
        """Test frequency chart data generation."""
        data = visualizer.frequency_chart_data(top_n=10)
        assert isinstance(data, list)
        assert len(data) <= 10
        assert all(isinstance(item, tuple) for item in data)
        assert all(len(item) == 2 for item in data)
        # Should be sorted by frequency (descending)
        frequencies = [item[1] for item in data]
        assert frequencies == sorted(frequencies, reverse=True)
    
    def test_sentiment_timeline(self, visualizer):
        """Test sentiment timeline generation."""
        timeline = visualizer.sentiment_timeline(chunk_size=50)
        assert isinstance(timeline, list)
        assert all(isinstance(item, tuple) for item in timeline)
        assert all(len(item) == 2 for item in timeline)
        assert all(isinstance(item[0], int) for item in timeline)  # Position
        assert all(isinstance(item[1], float) for item in timeline)  # Sentiment

class TestFileOperations:
    """Test cases for file operations."""
    
    def test_analyze_file(self):
        """Test file analysis."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a test file. It contains sample text for analysis.")
            temp_file = f.name
        
        try:
            result = analyze_file(temp_file)
            assert isinstance(result, dict)
            assert len(result) > 0
        finally:
            os.unlink(temp_file)
    
    def test_analyze_multiple_files(self):
        """Test batch file analysis."""
        files = []
        try:
            # Create temporary files
            for i in range(2):
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(f"This is test file {i}. It contains different content.")
                    files.append(f.name)
            
            results = analyze_multiple_files(files)
            assert isinstance(results, dict)
            assert len(results) == 2
            assert all(filename in results for filename in files)
        finally:
            for file in files:
                os.unlink(file)
    
    def test_export_analysis(self):
        """Test analysis export."""
        data = {
            'word_count': 100,
            'sentiment': 'positive',
            'complexity_score': 75.5
        }
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            success = export_analysis(data, temp_file, format='json')
            assert success is True
            assert os.path.exists(temp_file)
            
            # Verify exported content
            with open(temp_file, 'r') as f:
                imported_data = json.load(f)
                assert imported_data == data
        finally:
            os.unlink(temp_file)
    
    def test_compare_texts(self):
        """Test text comparison."""
        text1 = "The quick brown fox jumps over the lazy dog."
        text2 = "A quick brown fox leaps over a lazy dog."
        
        comparison = compare_texts(text1, text2)
        assert isinstance(comparison, dict)
        assert 'similarity' in comparison
        assert isinstance(comparison['similarity'], float)
        assert 0 <= comparison['similarity'] <= 1

class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    def test_get_stopwords(self):
        """Test stopwords retrieval."""
        stopwords = get_stopwords('english')
        assert isinstance(stopwords, list)
        assert len(stopwords) > 0
        assert all(isinstance(word, str) for word in stopwords)
        # Common English stopwords
        assert 'the' in stopwords
        assert 'and' in stopwords
        assert 'is' in stopwords
    
    def test_simple_stemmer(self):
        """Test basic stemming."""
        # Test common stemming patterns
        assert simple_stemmer('running').endswith('run')
        assert simple_stemmer('cats').endswith('cat')
        
        # Test word that shouldn't change much
        stemmed = simple_stemmer('cat')
        assert isinstance(stemmed, str)
        assert len(stemmed) > 0
    
    def test_calculate_similarity(self):
        """Test similarity calculation."""
        text1 = "The cat sat on the mat"
        text2 = "A cat sits on a mat"
        text3 = "Dogs are running in the park"
        
        sim1 = calculate_similarity(text1, text2)
        sim2 = calculate_similarity(text1, text3)
        
        assert isinstance(sim1, float)
        assert isinstance(sim2, float)
        assert 0 <= sim1 <= 1
        assert 0 <= sim2 <= 1
        
        # Similar texts should have higher similarity
        assert sim1 > sim2

class TestSpecialCases:
    """Test edge cases and special scenarios."""
    
    def test_empty_text(self):
        """Test analyzer with empty text."""
        analyzer = TextAnalyzer("")
        
        # Should handle empty text gracefully
        assert analyzer.word_frequency() == {}
        assert analyzer.sentence_count() == 0
        assert analyzer.paragraph_count() == 0
        assert analyzer.reading_time() == 0
    
    def test_single_word(self):
        """Test analyzer with single word."""
        analyzer = TextAnalyzer("word")
        
        freq = analyzer.word_frequency()
        assert len(freq) == 1
        assert 'word' in freq
        assert freq['word'] == 1
    
    def test_punctuation_heavy_text(self):
        """Test text with lots of punctuation."""
        text = "Hello!!! How are you??? I'm fine... Really!!!"
        analyzer = TextAnalyzer(text)
        
        # Should handle punctuation properly
        sentence_count = analyzer.sentence_count()
        assert sentence_count > 0
        
        word_freq = analyzer.word_frequency()
        assert len(word_freq) > 0
    
    def test_numeric_text(self):
        """Test text with numbers."""
        text = "There are 123 cats and 456 dogs in the park."
        analyzer = TextAnalyzer(text)
        
        entities = analyzer.extract_entities()
        # Should extract or handle numbers appropriately
        assert isinstance(entities, dict)
    
    def test_very_long_text(self):
        """Test with longer text."""
        # Create a longer text for testing
        long_text = " ".join(["This is sentence number {}.".format(i) for i in range(100)])
        analyzer = TextAnalyzer(long_text)
        
        assert analyzer.sentence_count() == 100
        assert analyzer.reading_time() > 0
        
        summary = analyzer.text_summary()
        assert isinstance(summary, dict)
        assert len(summary) > 0
