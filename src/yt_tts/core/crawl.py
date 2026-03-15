"""Incremental crawling: add-channel, add-video, add-starter."""

import json
import logging
import re
from pathlib import Path

from yt_tts.config import Config
from yt_tts.exceptions import CaptionFetchError

logger = logging.getLogger(__name__)

STARTER_CHANNELS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "starter_channels.json"
QUOTA_FILE = Path.home() / ".local" / "share" / "yt-tts" / "api_quota.json"


def _extract_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from: {url}")


def _extract_channel_id(url: str) -> str:
    """Extract channel ID from a YouTube channel URL."""
    patterns = [
        r"channel/([a-zA-Z0-9_-]+)",
        r"@([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract channel ID from: {url}")


def index_video(url: str, index, config: Config) -> None:
    """Fetch transcript for a single video and add to index."""
    from youtube_transcript_api import YouTubeTranscriptApi

    video_id = _extract_video_id(url)

    if index.has_video(video_id):
        logger.info("Video %s already indexed, skipping", video_id)
        return

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en"])
        text = " ".join(snippet.text for snippet in fetched)

        index.insert(
            video_id=video_id,
            channel_id="",
            channel_name="",
            title=f"Video {video_id}",
            text=text,
            language="en",
        )
    except Exception as e:
        raise CaptionFetchError(f"Failed to fetch transcript for {video_id}: {e}") from e


def crawl_channel(url: str, index, config: Config) -> int:
    """Crawl a YouTube channel and add all video transcripts to the index.

    Uses youtube-transcript-api to list and fetch transcripts.
    Returns count of transcripts added.
    """
    import subprocess

    channel_id = _extract_channel_id(url)
    count = 0

    # Use yt-dlp to list channel videos
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--print", "id",
                "--print", "title",
                f"https://www.youtube.com/channel/{channel_id}/videos",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        lines = result.stdout.strip().split("\n")
        # yt-dlp prints id and title on alternating lines
        videos = []
        for i in range(0, len(lines) - 1, 2):
            videos.append({"id": lines[i], "title": lines[i + 1] if i + 1 < len(lines) else ""})

    except Exception as e:
        logger.error("Failed to list channel videos: %s", e)
        return 0

    from youtube_transcript_api import YouTubeTranscriptApi
    from yt_tts.core.ratelimit import RateLimiter

    api = YouTubeTranscriptApi()
    limiter = RateLimiter(base_sleep_s=config.transcript_api_sleep_s)

    for video in videos:
        video_id = video["id"]
        title = video.get("title", "")

        if index.has_video(video_id):
            continue

        try:
            limiter.wait()
            fetched = api.fetch(video_id, languages=["en"])
            text = " ".join(snippet.text for snippet in fetched)

            index.insert(
                video_id=video_id,
                channel_id=channel_id,
                channel_name="",
                title=title,
                text=text,
                language="en",
            )
            count += 1
            limiter.report_success()

        except Exception as e:
            logger.warning("Skipping video %s: %s", video_id, e)
            continue

    return count


def add_starter_channels(index, config: Config) -> int:
    """Add transcripts from curated starter channels."""
    try:
        with open(STARTER_CHANNELS_PATH) as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("Starter channels file not found: %s", STARTER_CHANNELS_PATH)
        return 0

    total = 0
    for channel in data.get("channels", []):
        channel_id = channel["channel_id"]
        name = channel["name"]
        logger.info("Processing starter channel: %s", name)
        try:
            count = crawl_channel(
                f"https://www.youtube.com/channel/{channel_id}",
                index,
                config,
            )
            total += count
            logger.info("Added %d transcripts from %s", count, name)
        except Exception as e:
            logger.warning("Failed to process %s: %s", name, e)

    return total
