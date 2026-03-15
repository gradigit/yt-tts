"""Higher-level search functions for yt-tts."""

from __future__ import annotations

from yt_tts.config import Config
from yt_tts.core.index import TranscriptIndex
from yt_tts.types import SearchResult


def search_transcripts(
    phrase: str,
    index: TranscriptIndex,
    config: Config,
) -> SearchResult | None:
    """Search the index for a phrase. Returns the best match or None.

    Applies channel_filter from config if set. Tries multiple results
    if the first one is low quality (very negative rank score).
    """
    results = index.search(
        phrase=phrase,
        channel_id=config.channel_filter,
        limit=config.search_limit,
    )
    if not results:
        return None
    # Return the best-ranked result (FTS5 rank: lower/more-negative = better match).
    return results[0]


def search_live_video(
    phrase: str,
    video_url: str,
) -> SearchResult | None:
    """For --video mode: fetch transcript via youtube_transcript_api,
    search in-memory for the phrase, return a SearchResult if found.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    # Extract video_id from URL.
    video_id = _extract_video_id(video_url)
    if not video_id:
        return None

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en"])
    except Exception:
        return None

    # Combine all segments into full text.
    full_text = " ".join(snippet.text for snippet in fetched)

    phrase_lower = phrase.lower()
    if phrase_lower not in full_text.lower():
        return None

    # Build context.
    idx = full_text.lower().index(phrase_lower)
    start = max(0, idx - 50)
    end = min(len(full_text), idx + len(phrase) + 50)
    context = full_text[start:end]
    if start > 0:
        context = "..." + context
    if end < len(full_text):
        context = context + "..."

    return SearchResult(
        video_id=video_id,
        channel_id="",
        channel_name="",
        title="",
        matched_text=phrase,
        context_text=context,
        rank_score=0.0,
        has_auto_captions=True,
    )


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    import re

    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
