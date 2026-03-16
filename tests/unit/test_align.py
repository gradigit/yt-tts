"""Tests for the alignment module (Whisper-based phrase location)."""

from unittest.mock import patch

from yt_tts.core.align import _normalize_word, _find_phrase_in_words, _find_phrase_fuzzy
from yt_tts.core.asr import detect_backend


class TestDetectDevice:
    def test_returns_string(self):
        """detect_backend() returns a backend string."""
        result = detect_backend()
        assert isinstance(result, str)
        assert result in ("cpu", "cuda", "mlx")

    def test_forced_backend(self):
        """Can force a specific backend."""
        result = detect_backend("faster-whisper")
        assert result in ("cpu", "cuda")


class TestNormalizeWord:
    def test_lowercase(self):
        assert _normalize_word("Hello") == "hello"

    def test_strips_punctuation(self):
        assert _normalize_word("world,") == "world"
        assert _normalize_word("world.") == "world"
        assert _normalize_word("world!") == "world"
        assert _normalize_word("world?") == "world"

    def test_strips_quotes(self):
        assert _normalize_word('"hello"') == "hello"

    def test_preserves_apostrophe(self):
        assert _normalize_word("can't") == "can't"
        assert _normalize_word("you've") == "you've"

    def test_empty_string(self):
        assert _normalize_word("") == ""

    def test_only_punctuation(self):
        assert _normalize_word("...") == ""


class TestFindPhraseInWords:
    def _make_word_list(self, words):
        """Helper: create list of word dicts from plain strings."""
        return [{"word": w, "start": i * 0.5, "end": (i + 1) * 0.5, "probability": 0.9}
                for i, w in enumerate(words)]

    def test_exact_match_single_word(self):
        all_words = self._make_word_list(["hello", "world", "test"])
        result = _find_phrase_in_words(["world"], all_words)
        assert result == (1, 1)

    def test_exact_match_multi_word(self):
        all_words = self._make_word_list(["the", "quick", "brown", "fox"])
        result = _find_phrase_in_words(["quick", "brown"], all_words)
        assert result == (1, 2)

    def test_no_match(self):
        all_words = self._make_word_list(["hello", "world"])
        result = _find_phrase_in_words(["goodbye"], all_words)
        assert result is None

    def test_case_insensitive(self):
        all_words = self._make_word_list(["Hello", "World"])
        result = _find_phrase_in_words(["hello", "world"], all_words)
        assert result == (0, 1)

    def test_match_at_start(self):
        all_words = self._make_word_list(["hello", "world", "test"])
        result = _find_phrase_in_words(["hello"], all_words)
        assert result == (0, 0)

    def test_match_at_end(self):
        all_words = self._make_word_list(["hello", "world", "test"])
        result = _find_phrase_in_words(["test"], all_words)
        assert result == (2, 2)

    def test_empty_phrase(self):
        all_words = self._make_word_list(["hello", "world"])
        result = _find_phrase_in_words([], all_words)
        # Empty phrase matches at position 0
        assert result == (0, -1)

    def test_empty_words(self):
        result = _find_phrase_in_words(["hello"], [])
        assert result is None


class TestFindPhraseFuzzy:
    def _make_word_list(self, words):
        """Helper: create list of word dicts from plain strings."""
        return [{"word": w, "start": i * 0.5, "end": (i + 1) * 0.5, "probability": 0.9}
                for i, w in enumerate(words)]

    def test_exact_match_also_works(self):
        all_words = self._make_word_list(["hello", "beautiful", "world"])
        result = _find_phrase_fuzzy(["hello", "beautiful", "world"], all_words)
        assert result == (0, 2)

    def test_fuzzy_match_with_one_mismatch(self):
        """With 70% threshold, 3-word phrase allows 1 mismatch (needs 2/3 = 67% -> int(3*0.7)=2)."""
        all_words = self._make_word_list(["hello", "gorgeous", "world"])
        # Searching for "hello beautiful world" -- "gorgeous" != "beautiful" but 2/3 match
        result = _find_phrase_fuzzy(["hello", "beautiful", "world"], all_words)
        assert result == (0, 2)

    def test_no_match_below_threshold(self):
        """All words different should not match."""
        all_words = self._make_word_list(["alpha", "beta", "gamma"])
        result = _find_phrase_fuzzy(["hello", "beautiful", "world"], all_words)
        assert result is None

    def test_single_word_fuzzy(self):
        """Single word needs exact match (threshold: max(1, int(1*0.7)) = 1)."""
        all_words = self._make_word_list(["hello", "world"])
        result = _find_phrase_fuzzy(["world"], all_words)
        assert result == (1, 1)

    def test_single_word_no_match(self):
        all_words = self._make_word_list(["hello", "world"])
        result = _find_phrase_fuzzy(["goodbye"], all_words)
        assert result is None

    def test_best_match_selected(self):
        """When multiple windows qualify, the best scoring one wins."""
        all_words = self._make_word_list(["the", "cat", "sat", "the", "cat", "sat"])
        # "the cat ran" has 2/3 match in both windows, but they tie, so first is returned
        result = _find_phrase_fuzzy(["the", "cat", "ran"], all_words)
        assert result is not None
        start, end = result
        assert end - start == 2  # 3-word window
