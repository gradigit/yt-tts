"""Tests for the caching module (CaptionCache, ClipCache, utilities)."""

import json
from pathlib import Path

import pytest

from yt_tts.core.cache import CaptionCache, ClipCache, clear_all_caches, get_cache_stats


class TestCaptionCacheRoundtrip:
    def test_put_and_get(self, tmp_path):
        cache = CaptionCache(tmp_path)
        data = {"wireMagic": "pb3", "events": [{"tStartMs": 1000}]}
        cache.put("vid123", data)
        result = cache.get("vid123")
        assert result == data

    def test_get_missing_returns_none(self, tmp_path):
        cache = CaptionCache(tmp_path)
        assert cache.get("nonexistent") is None

    def test_has_returns_true_after_put(self, tmp_path):
        cache = CaptionCache(tmp_path)
        assert cache.has("vid123") is False
        cache.put("vid123", {"key": "value"})
        assert cache.has("vid123") is True

    def test_overwrite(self, tmp_path):
        cache = CaptionCache(tmp_path)
        cache.put("vid123", {"version": 1})
        cache.put("vid123", {"version": 2})
        result = cache.get("vid123")
        assert result == {"version": 2}

    def test_complex_json_data(self, tmp_path):
        cache = CaptionCache(tmp_path)
        data = {
            "wireMagic": "pb3",
            "events": [
                {
                    "tStartMs": 1000,
                    "dDurationMs": 3000,
                    "segs": [
                        {"utf8": "Hello", "tOffsetMs": 0, "acAsrConf": 200},
                        {"utf8": " world", "tOffsetMs": 500, "acAsrConf": 180},
                    ],
                }
            ],
        }
        cache.put("complex_vid", data)
        result = cache.get("complex_vid")
        assert result == data
        assert result["events"][0]["segs"][1]["utf8"] == " world"


class TestClipCacheRoundtrip:
    def test_put_and_get(self, tmp_path):
        cache = ClipCache(tmp_path)
        # Create a dummy audio file
        source = tmp_path / "source.m4a"
        source.write_bytes(b"\x00\x01\x02\x03" * 100)
        dest = cache.put("vid123", 0, 1000, source)
        assert dest.is_file()
        result = cache.get("vid123", 0, 1000)
        assert result is not None
        assert result.is_file()
        assert result.read_bytes() == source.read_bytes()

    def test_get_missing_returns_none(self, tmp_path):
        cache = ClipCache(tmp_path)
        assert cache.get("nonexistent", 0, 1000) is None

    def test_has_returns_true_after_put(self, tmp_path):
        cache = ClipCache(tmp_path)
        assert cache.has("vid123", 0, 1000) is False
        source = tmp_path / "source.m4a"
        source.write_bytes(b"\x00\x01\x02\x03")
        cache.put("vid123", 0, 1000, source)
        assert cache.has("vid123", 0, 1000) is True

    def test_different_timestamps_different_entries(self, tmp_path):
        cache = ClipCache(tmp_path)
        source = tmp_path / "source.m4a"
        source.write_bytes(b"\x00\x01\x02\x03")
        cache.put("vid123", 0, 1000, source)
        cache.put("vid123", 1000, 2000, source)
        assert cache.has("vid123", 0, 1000) is True
        assert cache.has("vid123", 1000, 2000) is True
        assert cache.has("vid123", 2000, 3000) is False


class TestClearCaches:
    def test_clear_empty_cache(self, tmp_path):
        # Create the subdirectories so clear_all_caches has something to scan
        (tmp_path / "captions").mkdir()
        (tmp_path / "clips").mkdir()
        count = clear_all_caches(tmp_path)
        assert count == 0

    def test_clear_populated_cache(self, tmp_path):
        caption_cache = CaptionCache(tmp_path)
        clip_cache = ClipCache(tmp_path)

        caption_cache.put("vid1", {"data": "test1"})
        caption_cache.put("vid2", {"data": "test2"})

        source = tmp_path / "source.m4a"
        source.write_bytes(b"\x00\x01\x02\x03")
        clip_cache.put("vid1", 0, 1000, source)

        count = clear_all_caches(tmp_path)
        assert count == 3

        # Verify caches are empty
        assert caption_cache.get("vid1") is None
        assert caption_cache.get("vid2") is None
        assert clip_cache.get("vid1", 0, 1000) is None

    def test_clear_nonexistent_dirs(self, tmp_path):
        # No subdirectories exist at all
        count = clear_all_caches(tmp_path)
        assert count == 0


class TestCacheStats:
    def test_stats_empty_cache(self, tmp_path):
        (tmp_path / "captions").mkdir()
        (tmp_path / "clips").mkdir()
        stats = get_cache_stats(tmp_path)
        assert "caption_count" in stats
        assert "caption_size_mb" in stats
        assert "clip_count" in stats
        assert "clip_size_mb" in stats
        assert "total_size_mb" in stats
        assert stats["caption_count"] == 0
        assert stats["clip_count"] == 0
        assert stats["total_size_mb"] == 0

    def test_stats_populated_cache(self, tmp_path):
        caption_cache = CaptionCache(tmp_path)
        clip_cache = ClipCache(tmp_path)

        caption_cache.put("vid1", {"data": "test"})
        caption_cache.put("vid2", {"data": "more"})

        source = tmp_path / "source.m4a"
        source.write_bytes(b"\x00" * 1024)
        clip_cache.put("vid1", 0, 1000, source)

        stats = get_cache_stats(tmp_path)
        assert stats["caption_count"] == 2
        assert stats["clip_count"] == 1
        assert stats["caption_size_mb"] >= 0
        assert stats["clip_size_mb"] >= 0
        assert stats["total_size_mb"] == round(stats["caption_size_mb"] + stats["clip_size_mb"], 2)

    def test_stats_keys_present(self, tmp_path):
        stats = get_cache_stats(tmp_path)
        expected_keys = {"caption_count", "caption_size_mb", "clip_count", "clip_size_mb", "total_size_mb"}
        assert set(stats.keys()) == expected_keys
