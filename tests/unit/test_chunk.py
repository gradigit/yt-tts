"""Tests for Bumblebee chunking."""

import pytest

from yt_tts.config import Config
from yt_tts.core.chunk import chunk_phrase, resolve_chunks, _normalize_word
from yt_tts.types import ClipInfo, SearchResult


def make_search_result(video_id: str = "test123", phrase: str = "") -> SearchResult:
    return SearchResult(
        video_id=video_id,
        channel_id="ch1",
        channel_name="TestChannel",
        title="Test Video",
        matched_text=phrase,
        context_text=f"...{phrase}...",
        rank_score=-1.0,
        has_auto_captions=True,
    )


class TestNormalizeWord:
    def test_basic(self):
        assert _normalize_word("Hello") == "hello"

    def test_punctuation(self):
        assert _normalize_word("world,") == "world"
        assert _normalize_word('"hello"') == "hello"

    def test_contraction(self):
        assert _normalize_word("can't") == "can't"
        assert _normalize_word("you've") == "you've"

    def test_leading_trailing(self):
        assert _normalize_word("...hello!") == "hello"


class TestChunkPhrase:
    def test_single_word_match(self):
        def search_fn(phrase):
            if phrase == "hello":
                return make_search_result(phrase=phrase)
            return None

        config = Config()
        plan = chunk_phrase("hello", search_fn, config)
        assert plan.chunks == ["hello"]
        assert len(plan.missing_words) == 0
        assert plan.search_results[0] is not None

    def test_greedy_longest_match(self):
        """Should prefer longer matches."""
        matches = {"hello world": True, "hello": True, "world": True}

        def search_fn(phrase):
            if phrase in matches:
                return make_search_result(phrase=phrase)
            return None

        config = Config()
        plan = chunk_phrase("hello world", search_fn, config)
        # Should match "hello world" as one chunk, not "hello" + "world"
        assert plan.chunks == ["hello world"]
        assert len(plan.missing_words) == 0

    def test_fallback_to_shorter(self):
        """When long phrase doesn't match, try shorter."""
        def search_fn(phrase):
            if phrase == "hello":
                return make_search_result(phrase="hello")
            if phrase == "world":
                return make_search_result(phrase="world")
            return None

        config = Config()
        plan = chunk_phrase("hello world", search_fn, config)
        assert plan.chunks == ["hello", "world"]
        assert len(plan.missing_words) == 0

    def test_missing_word(self):
        """Words with no match at any length are marked missing."""
        def search_fn(phrase):
            if phrase == "hello":
                return make_search_result(phrase="hello")
            return None

        config = Config()
        plan = chunk_phrase("hello xyznonexistent", search_fn, config)
        assert plan.chunks == ["hello", "xyznonexistent"]
        assert "xyznonexistent" in plan.missing_words
        assert plan.search_results[0] is not None
        assert plan.search_results[1] is None

    def test_contraction_handling(self):
        """Contractions should be preserved and matched."""
        def search_fn(phrase):
            if phrase == "can't believe":
                return make_search_result(phrase="can't believe")
            return None

        config = Config()
        plan = chunk_phrase("can't believe", search_fn, config)
        assert plan.chunks == ["can't believe"]
        assert len(plan.missing_words) == 0

    def test_empty_input(self):
        config = Config()
        plan = chunk_phrase("", lambda p: None, config)
        assert plan.chunks == []

    def test_too_long_input_with_limit(self):
        config = Config(max_input_words=5)
        with pytest.raises(ValueError, match="Input too long"):
            chunk_phrase("one two three four five six", lambda p: None, config)

    def test_no_limit_by_default(self):
        """Default config has no word limit."""
        config = Config()
        # Should not raise even with many words
        plan = chunk_phrase("a b c d e f g h i j k l m n o p q r s t", lambda p: None, config)
        assert len(plan.chunks) == 20  # all single words, no matches

    def test_search_cache(self):
        """Same phrase should not be searched twice."""
        call_count = 0

        def search_fn(phrase):
            nonlocal call_count
            call_count += 1
            return None

        config = Config()
        # "a b" will try "a b", then "a", then "b"
        # "a" and "b" are unique, so 3 calls
        chunk_phrase("a b", search_fn, config)
        assert call_count == 3  # "a b", "a", "b"

    def test_max_clips_limit_when_set(self):
        def search_fn(phrase):
            if len(phrase.split()) == 1:
                return make_search_result(phrase=phrase)
            return None

        config = Config(max_clips=3)
        # 5 single words, but max 3 clips
        plan = chunk_phrase("a b c d e", search_fn, config)
        assert len(plan.chunks) == 3
        assert len(plan.missing_words) > 0

    def test_no_clips_limit_by_default(self):
        def search_fn(phrase):
            if len(phrase.split()) == 1:
                return make_search_result(phrase=phrase)
            return None

        config = Config()  # max_clips=0 = no limit
        plan = chunk_phrase("a b c d e f g h i j", search_fn, config)
        assert len(plan.chunks) == 10

    def test_no_matches_at_all(self):
        config = Config()
        plan = chunk_phrase("hello world", lambda p: None, config)
        assert len(plan.chunks) == 2
        assert len(plan.missing_words) == 2


class TestResolveChunks:
    def test_resolve_successful(self):
        from pathlib import Path

        plan = chunk_phrase.__wrapped__ if hasattr(chunk_phrase, '__wrapped__') else None

        # Build a plan manually
        plan = type('ChunkPlan', (), {
            'chunks': ['hello', 'world'],
            'clips': [None, None],
            'missing_words': [],
            'search_results': [
                make_search_result(phrase="hello", video_id="v1"),
                make_search_result(phrase="world", video_id="v2"),
            ],
        })()

        # Use proper ChunkPlan
        from yt_tts.types import ChunkPlan
        plan = ChunkPlan(
            chunks=['hello', 'world'],
            clips=[None, None],
            missing_words=[],
            search_results=[
                make_search_result(phrase="hello", video_id="v1"),
                make_search_result(phrase="world", video_id="v2"),
            ],
        )

        def resolve_fn(phrase, result):
            return ClipInfo(
                video_id=result.video_id,
                video_title="Test",
                phrase=phrase,
                start_ms=0,
                end_ms=1000,
                file_path=Path("/tmp/test.m4a"),
                confidence=0.9,
                timestamp_source="json3",
            )

        config = Config()
        resolved = resolve_chunks(plan, resolve_fn, config)
        assert all(c is not None for c in resolved.clips)
        assert len(resolved.missing_words) == 0

    def test_resolve_partial_failure(self):
        from pathlib import Path
        from yt_tts.types import ChunkPlan

        plan = ChunkPlan(
            chunks=['hello', 'world'],
            clips=[None, None],
            missing_words=[],
            search_results=[
                make_search_result(phrase="hello", video_id="v1"),
                make_search_result(phrase="world", video_id="v2"),
            ],
        )

        def resolve_fn(phrase, result):
            if phrase == "hello":
                return ClipInfo(
                    video_id=result.video_id,
                    video_title="Test",
                    phrase=phrase,
                    start_ms=0,
                    end_ms=1000,
                    file_path=Path("/tmp/test.m4a"),
                    confidence=0.9,
                    timestamp_source="json3",
                )
            return None  # world fails

        config = Config()
        resolved = resolve_chunks(plan, resolve_fn, config)
        assert resolved.clips[0] is not None
        assert resolved.clips[1] is None
        assert "world" in resolved.missing_words
