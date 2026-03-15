"""Tests for TranscriptIndex — SQLite FTS5 index and search."""

import tempfile
from pathlib import Path

import pytest

from yt_tts.core.index import TranscriptIndex


@pytest.fixture
def index(tmp_path):
    """Create a TranscriptIndex backed by a temp file."""
    db_path = tmp_path / "test_index.db"
    return TranscriptIndex(db_path)


def test_insert_and_search(index):
    """Insert a transcript, search for a phrase in it, verify found."""
    index.insert(
        video_id="abc123",
        channel_id="ch1",
        channel_name="Test Channel",
        title="Test Video",
        text="the quick brown fox jumps over the lazy dog",
    )
    results = index.search("quick brown fox")
    assert len(results) >= 1
    assert results[0].video_id == "abc123"
    assert results[0].channel_name == "Test Channel"
    assert results[0].matched_text == "quick brown fox"


def test_contraction_search(index):
    """Insert text with contractions, verify FTS5 finds them."""
    index.insert(
        video_id="contr1",
        channel_id="ch1",
        channel_name="Channel",
        title="Contractions",
        text="I can't believe it's not butter and we won't stop",
    )
    results = index.search("can't believe")
    assert len(results) >= 1
    assert results[0].video_id == "contr1"


def test_bulk_insert(index):
    """Bulk insert 100 records and verify count."""
    batch = [
        {
            "video_id": f"vid{i:04d}",
            "channel_id": "ch_bulk",
            "channel_name": "Bulk Channel",
            "title": f"Video {i}",
            "text": f"transcript number {i} with some words for testing purposes",
        }
        for i in range(100)
    ]
    count = index.bulk_insert(batch)
    assert count == 100
    stats = index.stats()
    assert stats["total_transcripts"] == 100


def test_search_no_results(index):
    """Search for a phrase that does not exist returns empty list."""
    index.insert(
        video_id="exist1",
        channel_id="ch1",
        channel_name="Channel",
        title="Existing",
        text="the sun is shining brightly today",
    )
    results = index.search("quantum entanglement")
    assert results == []


def test_fts_sync(index):
    """FTS5 and transcripts table stay in sync on delete."""
    index.insert(
        video_id="sync1",
        channel_id="ch1",
        channel_name="Channel",
        title="Sync Test",
        text="synchronization test phrase unique xylophone melody",
    )
    # Verify we can find it.
    results = index.search("xylophone melody")
    assert len(results) == 1

    # Delete and verify search returns nothing.
    index.delete("sync1")
    results = index.search("xylophone melody")
    assert results == []


def test_stats(index):
    """Insert records and verify stats counts."""
    index.insert(
        video_id="s1",
        channel_id="ch_a",
        channel_name="Channel A",
        title="First",
        text="one two three four five",
    )
    index.insert(
        video_id="s2",
        channel_id="ch_b",
        channel_name="Channel B",
        title="Second",
        text="six seven eight nine ten eleven",
    )
    stats = index.stats()
    assert stats["total_transcripts"] == 2
    assert stats["total_words"] == 11  # 5 + 6
    assert stats["unique_channels"] == 2
    assert stats["db_size_mb"] >= 0


def test_has_video(index):
    """has_video returns True for indexed videos, False otherwise."""
    index.insert(
        video_id="hv1",
        channel_id="ch1",
        channel_name="Channel",
        title="Has Video",
        text="some text here",
    )
    assert index.has_video("hv1") is True
    assert index.has_video("nonexistent") is False


def test_search_channel_filter(index):
    """Search with channel_id filter only returns matching channel."""
    index.insert(
        video_id="cf1",
        channel_id="alpha",
        channel_name="Alpha Channel",
        title="Alpha Video",
        text="the secret password is banana smoothie",
    )
    index.insert(
        video_id="cf2",
        channel_id="beta",
        channel_name="Beta Channel",
        title="Beta Video",
        text="the secret password is banana smoothie too",
    )
    # Search with channel filter.
    results = index.search("banana smoothie", channel_id="alpha")
    assert len(results) == 1
    assert results[0].video_id == "cf1"
    assert results[0].channel_id == "alpha"

    # Without filter, both should appear.
    results = index.search("banana smoothie")
    assert len(results) == 2


def test_duplicate_video_id(index):
    """INSERT OR IGNORE: inserting same video_id twice causes no error."""
    rowid1 = index.insert(
        video_id="dup1",
        channel_id="ch1",
        channel_name="Channel",
        title="Original",
        text="original text content",
    )
    rowid2 = index.insert(
        video_id="dup1",
        channel_id="ch1",
        channel_name="Channel",
        title="Duplicate",
        text="different text content",
    )
    assert rowid1 > 0
    assert rowid2 == 0  # Ignored duplicate.
    # Only one record should exist.
    stats = index.stats()
    assert stats["total_transcripts"] == 1
