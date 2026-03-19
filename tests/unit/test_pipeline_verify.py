"""Tests for pipeline verification, phrase location, and max_chunk_words."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_tts.config import Config
from yt_tts.core.pipeline import _locate_phrase_in_segments, _verify_clip


class TestVerifyClipSkipFunctionWords:
    """Single function words skip verification; content words and multi-word phrases do not."""

    @patch("yt_tts.core.asr.transcribe")
    def test_single_function_word_the(self, mock_transcribe):
        """'the' is a function word -- verification should be skipped (return True)."""
        result = _verify_clip(Path("/tmp/dummy.m4a"), "the")
        assert result is True
        mock_transcribe.assert_not_called()

    @patch("yt_tts.core.asr.transcribe")
    def test_single_function_word_a(self, mock_transcribe):
        result = _verify_clip(Path("/tmp/dummy.m4a"), "a")
        assert result is True
        mock_transcribe.assert_not_called()

    @patch("yt_tts.core.asr.transcribe")
    def test_single_function_word_of(self, mock_transcribe):
        result = _verify_clip(Path("/tmp/dummy.m4a"), "of")
        assert result is True
        mock_transcribe.assert_not_called()

    @patch("yt_tts.core.asr.transcribe")
    def test_single_function_word_in(self, mock_transcribe):
        result = _verify_clip(Path("/tmp/dummy.m4a"), "in")
        assert result is True
        mock_transcribe.assert_not_called()

    @patch("yt_tts.core.asr.transcribe")
    def test_single_function_word_is(self, mock_transcribe):
        result = _verify_clip(Path("/tmp/dummy.m4a"), "is")
        assert result is True
        mock_transcribe.assert_not_called()

    @patch("yt_tts.core.asr.transcribe")
    def test_single_content_word_hello_is_verified(self, mock_transcribe):
        """Content words are NOT skipped — ASR verification should run."""
        mock_result = MagicMock()
        mock_result.text = "hello"
        mock_transcribe.return_value = mock_result

        result = _verify_clip(Path("/tmp/dummy.m4a"), "hello")
        assert result is True
        mock_transcribe.assert_called_once()

    @patch("yt_tts.core.asr.transcribe")
    def test_single_content_word_machine_is_verified(self, mock_transcribe):
        mock_result = MagicMock()
        mock_result.text = "machine"
        mock_transcribe.return_value = mock_result

        result = _verify_clip(Path("/tmp/dummy.m4a"), "machine")
        assert result is True
        mock_transcribe.assert_called_once()

    @patch("yt_tts.core.asr.transcribe")
    def test_multi_word_phrase_always_verified(self, mock_transcribe):
        """Multi-word phrases always get verified regardless of content."""
        mock_result = MagicMock()
        mock_result.text = "the quick"
        mock_transcribe.return_value = mock_result

        result = _verify_clip(Path("/tmp/dummy.m4a"), "the quick")
        assert result is True
        mock_transcribe.assert_called_once()

    @patch("yt_tts.core.asr.transcribe")
    def test_multi_word_all_function_words_still_verified(self, mock_transcribe):
        """Even if every word is a function word, multi-word phrases get verified."""
        mock_result = MagicMock()
        mock_result.text = "is it"
        mock_transcribe.return_value = mock_result

        result = _verify_clip(Path("/tmp/dummy.m4a"), "is it")
        assert result is True
        mock_transcribe.assert_called_once()

    @patch("yt_tts.core.asr.transcribe")
    def test_verification_failure_returns_false(self, mock_transcribe):
        """When ASR hears something completely different, verification fails."""
        mock_result = MagicMock()
        mock_result.text = "completely different words here"
        mock_transcribe.return_value = mock_result

        result = _verify_clip(Path("/tmp/dummy.m4a"), "hello world")
        assert result is False


class TestLocatePhraseInSegments:
    def _make_segments(self, items):
        """Helper: create segment list from (text, start, duration) tuples."""
        return [
            {"text": text, "start": start, "duration": dur}
            for text, start, dur in items
        ]

    def test_single_segment_match(self):
        segments = self._make_segments([
            ("hello world", 1.0, 3.0),
            ("this is a test", 5.0, 4.0),
        ])
        result = _locate_phrase_in_segments("hello world", segments)
        assert result is not None
        assert result.start_ms == 1000
        assert result.end_ms == 4000  # 1.0 + 3.0 = 4.0s

    def test_multi_segment_spanning_match(self):
        segments = self._make_segments([
            ("the quick brown", 1.0, 2.0),
            ("fox jumps over", 3.5, 2.0),
        ])
        # "brown fox" spans two segments
        result = _locate_phrase_in_segments("brown fox", segments)
        assert result is not None
        assert result.start_ms == 1000  # starts in first segment
        assert result.end_ms == 5500  # ends at second segment end (3.5 + 2.0)

    def test_no_match_returns_none(self):
        segments = self._make_segments([
            ("hello world", 1.0, 3.0),
            ("this is a test", 5.0, 4.0),
        ])
        result = _locate_phrase_in_segments("nonexistent phrase", segments)
        assert result is None

    def test_single_segment_confidence_is_0_5(self):
        """Single-segment matches get confidence=0.5 (triggers alignment refinement)."""
        segments = self._make_segments([
            ("hello world", 1.0, 3.0),
        ])
        result = _locate_phrase_in_segments("hello world", segments)
        assert result is not None
        assert result.confidence < 1.0
        assert result.confidence == 0.5

    def test_multi_segment_confidence_is_0_3(self):
        """Multi-segment spanning matches get confidence=0.3."""
        segments = self._make_segments([
            ("the quick brown", 1.0, 2.0),
            ("fox jumps over", 3.5, 2.0),
        ])
        result = _locate_phrase_in_segments("brown fox", segments)
        assert result is not None
        assert result.confidence < 1.0
        assert result.confidence == 0.3

    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        segments = self._make_segments([
            ("Hello World", 1.0, 3.0),
        ])
        result = _locate_phrase_in_segments("hello world", segments)
        assert result is not None

    def test_empty_segments(self):
        result = _locate_phrase_in_segments("hello", [])
        assert result is None


class TestMaxChunkWords:
    """Test that max_chunk_words in the pipeline config interacts with chunk_phrase correctly."""

    def _make_search_fn(self, matches):
        """Helper: build search function from a set of matching phrases."""
        from yt_tts.types import SearchResult

        def search_fn(phrase):
            if phrase in matches:
                return SearchResult(
                    video_id="test123",
                    channel_id="ch1",
                    channel_name="TestChannel",
                    title="Test Video",
                    matched_text=phrase,
                    context_text=f"...{phrase}...",
                    rank_score=-1.0,
                    has_auto_captions=True,
                )
            return None
        return search_fn

    def test_max_chunk_words_zero_no_limit(self):
        """max_chunk_words=0 allows the greedy algorithm to match any length."""
        from yt_tts.core.chunk import chunk_phrase

        matches = {"hello beautiful world"}
        search_fn = self._make_search_fn(matches)
        config = Config(max_chunk_words=0)
        plan = chunk_phrase("hello beautiful world", search_fn, config)
        assert plan.chunks == ["hello beautiful world"]

    def test_max_chunk_words_one_word_by_word(self):
        """max_chunk_words=1 forces single-word chunks even when multi-word matches exist."""
        from yt_tts.core.chunk import chunk_phrase

        matches = {"hello", "beautiful", "world", "hello beautiful world"}
        search_fn = self._make_search_fn(matches)
        config = Config(max_chunk_words=1)
        plan = chunk_phrase("hello beautiful world", search_fn, config)
        assert plan.chunks == ["hello", "beautiful", "world"]
        assert len(plan.missing_words) == 0

    def test_max_chunk_words_three(self):
        """max_chunk_words=3 limits chunks to at most 3 words."""
        from yt_tts.core.chunk import chunk_phrase

        matches = {
            "the quick brown fox jumps",  # 5 words -- too long
            "the quick brown",            # 3 words -- fits
            "fox jumps",                  # 2 words -- fits
            "the", "quick", "brown", "fox", "jumps",
        }
        search_fn = self._make_search_fn(matches)
        config = Config(max_chunk_words=3)
        plan = chunk_phrase("the quick brown fox jumps", search_fn, config)
        # Should match "the quick brown" (3 words) then "fox jumps" (2 words)
        assert plan.chunks == ["the quick brown", "fox jumps"]
        assert len(plan.missing_words) == 0
