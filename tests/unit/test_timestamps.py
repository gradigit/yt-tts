"""Tests for timestamps module: parsing and phrase location."""

import pytest

from yt_tts.core.timestamps import has_word_level_timing, locate_phrase, parse_json3
from yt_tts.types import TimeRange, WordTimestamp


class TestParseJson3:
    """Tests for parse_json3."""

    def test_parse_json3(self, sample_json3):
        """Verify correct word extraction with timing from word-level json3."""
        words = parse_json3(sample_json3)

        assert len(words) == 6

        # First word: "Hello" at tStartMs=1000 + tOffsetMs=0
        assert words[0].word == "Hello"
        assert words[0].start_ms == 1000
        # end_ms is start of next word: 1000 + 500 = 1500
        assert words[0].end_ms == 1500
        assert words[0].confidence == 200

        # Second word: "world" at tStartMs=1000 + tOffsetMs=500
        assert words[1].word == "world"
        assert words[1].start_ms == 1500
        assert words[1].end_ms == 2000  # next word start: 1000 + 1000
        assert words[1].confidence == 180

        # Third word: "this" at tStartMs=1000 + tOffsetMs=1000
        assert words[2].word == "this"
        assert words[2].start_ms == 2000
        # Last word in event: tStartMs + dDurationMs = 1000 + 3000 = 4000
        assert words[2].end_ms == 4000
        assert words[2].confidence == 190

        # Fourth word: "is" at tStartMs=4000 + tOffsetMs=0
        assert words[3].word == "is"
        assert words[3].start_ms == 4000
        assert words[3].end_ms == 4300
        assert words[3].confidence == 210

        # Fifth word: "a" at tStartMs=4000 + tOffsetMs=300
        assert words[4].word == "a"
        assert words[4].start_ms == 4300
        assert words[4].end_ms == 4600
        assert words[4].confidence == 220

        # Sixth word: "test" at tStartMs=4000 + tOffsetMs=600
        assert words[5].word == "test"
        assert words[5].start_ms == 4600
        assert words[5].end_ms == 6000  # 4000 + 2000
        assert words[5].confidence == 250

    def test_parse_json3_no_offsets(self, sample_json3_no_offsets):
        """Verify handling of json3 without tOffsetMs (manual captions)."""
        words = parse_json3(sample_json3_no_offsets)

        assert len(words) == 2

        # First segment: "Hello world this" at tStartMs=1000
        assert words[0].word == "Hello world this"
        assert words[0].start_ms == 1000
        assert words[0].end_ms == 4000  # tStartMs + dDurationMs
        assert words[0].confidence == 0  # no acAsrConf

        # Second segment: "is a test" at tStartMs=4000
        assert words[1].word == "is a test"
        assert words[1].start_ms == 4000
        assert words[1].end_ms == 6000  # 4000 + 2000
        assert words[1].confidence == 0

    def test_parse_json3_skips_whitespace_segs(self):
        """Verify whitespace-only segments are skipped."""
        data = {
            "wireMagic": "pb3",
            "events": [
                {
                    "tStartMs": 0,
                    "dDurationMs": 1000,
                    "segs": [
                        {"utf8": "\n"},
                        {"utf8": "  "},
                        {"utf8": "hello", "tOffsetMs": 0, "acAsrConf": 200},
                    ],
                },
            ],
        }
        words = parse_json3(data)
        assert len(words) == 1
        assert words[0].word == "hello"

    def test_parse_json3_skips_events_without_segs(self):
        """Verify events without segs are skipped."""
        data = {
            "wireMagic": "pb3",
            "events": [
                {"tStartMs": 0, "dDurationMs": 1000},
                {
                    "tStartMs": 1000,
                    "dDurationMs": 1000,
                    "segs": [
                        {"utf8": "word", "tOffsetMs": 0, "acAsrConf": 150},
                    ],
                },
            ],
        }
        words = parse_json3(data)
        assert len(words) == 1
        assert words[0].word == "word"


class TestHasWordLevelTiming:
    """Tests for has_word_level_timing."""

    def test_has_word_level_timing_true(self, sample_json3):
        """True for data with tOffsetMs fields."""
        assert has_word_level_timing(sample_json3) is True

    def test_has_word_level_timing_false(self, sample_json3_no_offsets):
        """False for data without tOffsetMs fields."""
        assert has_word_level_timing(sample_json3_no_offsets) is False

    def test_has_word_level_timing_empty(self):
        """False for empty events."""
        assert has_word_level_timing({"events": []}) is False
        assert has_word_level_timing({}) is False


class TestLocatePhrase:
    """Tests for locate_phrase."""

    def test_locate_phrase_exact_match(self, sample_json3):
        """Search for 'hello world' in parsed timestamps."""
        words = parse_json3(sample_json3)
        result = locate_phrase("hello world", words, min_confidence=0)

        assert result is not None
        assert isinstance(result, TimeRange)
        assert result.start_ms == 1000  # Hello starts at 1000
        assert result.end_ms == 2000    # world ends at 2000
        assert result.confidence == (200 + 180) / 2  # avg of Hello, world

    def test_locate_phrase_no_match(self, sample_json3):
        """Search for phrase that does not exist returns None."""
        words = parse_json3(sample_json3)
        result = locate_phrase("nonexistent phrase", words, min_confidence=0)
        assert result is None

    def test_locate_phrase_case_insensitive(self, sample_json3):
        """Search with different case should still match."""
        words = parse_json3(sample_json3)
        result = locate_phrase("HELLO WORLD", words, min_confidence=0)

        assert result is not None
        assert result.start_ms == 1000
        assert result.end_ms == 2000

    def test_locate_phrase_min_confidence_filter(self, sample_json3):
        """Words below min_confidence threshold should be excluded."""
        words = parse_json3(sample_json3)
        # All words have confidence >= 180, so threshold 255 should find nothing
        result = locate_phrase("hello world", words, min_confidence=255)
        assert result is None

    def test_locate_phrase_empty_inputs(self, sample_json3):
        """Empty phrase or empty word list returns None."""
        words = parse_json3(sample_json3)
        assert locate_phrase("", words) is None
        assert locate_phrase("hello", []) is None
        assert locate_phrase("", []) is None

    def test_locate_phrase_multi_word(self, sample_json3):
        """Search for multi-word phrase spanning events."""
        words = parse_json3(sample_json3)
        result = locate_phrase("this is a test", words, min_confidence=0)

        assert result is not None
        assert result.start_ms == 2000   # "this" start
        assert result.end_ms == 6000     # "test" end
        assert result.confidence == (190 + 210 + 220 + 250) / 4

    def test_locate_phrase_single_word(self, sample_json3):
        """Search for a single word."""
        words = parse_json3(sample_json3)
        result = locate_phrase("test", words, min_confidence=0)

        assert result is not None
        assert result.start_ms == 4600
        assert result.end_ms == 6000
        assert result.confidence == 250.0
