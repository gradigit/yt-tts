"""Tests for audio clip extraction — padding resolution and cache key behavior."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_tts.config import Config
from yt_tts.core.extract import _resolve_padding


class TestResolvePadding:
    def test_tight(self):
        config = Config(tightness="tight")
        assert _resolve_padding(config) == 30

    def test_normal(self):
        config = Config(tightness="normal")
        assert _resolve_padding(config) == 100

    def test_loose(self):
        config = Config(tightness="loose")
        assert _resolve_padding(config) == 250

    def test_int_passthrough(self):
        config = Config(tightness=42)
        assert _resolve_padding(config) == 42

    def test_int_zero(self):
        config = Config(tightness=0)
        assert _resolve_padding(config) == 0

    def test_unknown_string_defaults_to_100(self):
        config = Config(tightness="snug")
        assert _resolve_padding(config) == 100


class TestExtractClipCacheKey:
    """Verify that extract_clip uses padded boundaries for cache keys."""

    @patch("yt_tts.core.extract.get_stream_url")
    @patch("yt_tts.core.extract.validate_clip")
    @patch("yt_tts.core.extract.subprocess.run")
    def test_cache_key_uses_padded_boundaries(self, mock_run, mock_validate, mock_url):
        """Cache.get and Cache.put are called with padded start/end, not raw."""
        from yt_tts.core.extract import extract_clip

        mock_url.return_value = "https://example.com/stream"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_validate.return_value = True

        cache = MagicMock()
        cache.get.return_value = None  # cache miss

        config = Config(tightness="tight")  # padding = 30ms
        start_ms = 1000
        end_ms = 2000

        padded_start = start_ms - 30  # 970
        padded_end = end_ms + 30  # 2030

        extract_clip("vid123", start_ms, end_ms, config, cache=cache)

        cache.get.assert_called_once_with("vid123", padded_start, padded_end)
        cache.put.assert_called_once()
        put_args = cache.put.call_args[0]
        assert put_args[0] == "vid123"
        assert put_args[1] == padded_start
        assert put_args[2] == padded_end

    @patch("yt_tts.core.extract.get_stream_url")
    @patch("yt_tts.core.extract.validate_clip")
    @patch("yt_tts.core.extract.subprocess.run")
    def test_different_tightness_produces_different_cache_keys(
        self, mock_run, mock_validate, mock_url
    ):
        """Changing tightness changes the padded boundaries, busting the cache."""
        from yt_tts.core.extract import extract_clip

        mock_url.return_value = "https://example.com/stream"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_validate.return_value = True

        start_ms = 1000
        end_ms = 2000

        # Tight: padding 30ms => padded_start=970, padded_end=2030
        cache_tight = MagicMock()
        cache_tight.get.return_value = None
        config_tight = Config(tightness="tight")
        extract_clip("vid123", start_ms, end_ms, config_tight, cache=cache_tight)
        tight_get_args = cache_tight.get.call_args[0]

        # Loose: padding 250ms => padded_start=750, padded_end=2250
        cache_loose = MagicMock()
        cache_loose.get.return_value = None
        config_loose = Config(tightness="loose")
        extract_clip("vid123", start_ms, end_ms, config_loose, cache=cache_loose)
        loose_get_args = cache_loose.get.call_args[0]

        assert tight_get_args != loose_get_args

    @patch("yt_tts.core.extract.get_stream_url")
    def test_cache_hit_returns_immediately(self, mock_url):
        """When cache.get returns a path, extract_clip returns it without downloading."""
        from yt_tts.core.extract import extract_clip

        cached_path = Path("/tmp/cached_clip.m4a")
        cache = MagicMock()
        cache.get.return_value = cached_path

        config = Config(tightness="tight")
        result = extract_clip("vid123", 1000, 2000, config, cache=cache)

        assert result == cached_path
        mock_url.assert_not_called()  # should not download

    @patch("yt_tts.core.extract.get_stream_url")
    @patch("yt_tts.core.extract.validate_clip")
    @patch("yt_tts.core.extract.subprocess.run")
    def test_padded_start_clamped_to_zero(self, mock_run, mock_validate, mock_url):
        """When start_ms < padding, padded_start should be clamped to 0."""
        from yt_tts.core.extract import extract_clip

        mock_url.return_value = "https://example.com/stream"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_validate.return_value = True

        cache = MagicMock()
        cache.get.return_value = None

        config = Config(tightness="normal")  # padding = 100ms
        # start_ms=50, so padded_start = max(0, 50-100) = 0
        extract_clip("vid123", 50, 2000, config, cache=cache)

        cache.get.assert_called_once_with("vid123", 0, 2100)
