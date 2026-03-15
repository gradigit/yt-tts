"""Caption fetching from YouTube videos."""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from yt_tts.core.cache import CaptionCache
from yt_tts.exceptions import CaptionFetchError

if TYPE_CHECKING:
    from yt_tts.config import Config

logger = logging.getLogger(__name__)


def _ytdlp_cookie_args(config: "Config | None" = None) -> list[str]:
    """Build yt-dlp cookie arguments from config."""
    if config is None:
        return []
    args = []
    if config.cookies_from_browser:
        args.extend(["--cookies-from-browser", config.cookies_from_browser])
    elif config.cookies_file:
        args.extend(["--cookies", str(config.cookies_file)])
    return args


def fetch_json3(video_id: str, cache_dir: Path | None = None, config: "Config | None" = None) -> dict:
    """Fetch json3 captions for a YouTube video using yt-dlp.

    Tries --write-auto-subs first (word-level timing), then --write-subs
    (manual captions). Writes to a temp dir, reads the json3 file, and
    returns parsed JSON.

    If cache_dir is provided, checks cache first and stores result on
    successful fetch.

    Raises CaptionFetchError if fetching fails or the json3 data is invalid.
    """
    # Check cache first
    if cache_dir is not None:
        cache = CaptionCache(cache_dir)
        cached = cache.get(video_id)
        if cached is not None:
            return cached

    cookie_args = _ytdlp_cookie_args(config)

    # Try auto-subs first (word-level timing), then manual subs
    for sub_flag in ("--write-auto-subs", "--write-subs"):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "yt-dlp",
                *cookie_args,
                sub_flag,
                "--sub-format", "json3",
                "--sub-lang", "en",
                "--skip-download",
                "--no-warnings",
                "--output", f"{tmpdir}/%(id)s.%(ext)s",
                "--", video_id,
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except FileNotFoundError:
                raise CaptionFetchError("yt-dlp is not installed or not on PATH")
            except subprocess.TimeoutExpired:
                raise CaptionFetchError(f"yt-dlp timed out fetching captions for {video_id}")

            # Find the json3 file
            json3_files = list(Path(tmpdir).glob("*.json3"))
            if not json3_files:
                logger.debug("No json3 with %s for %s, trying next", sub_flag, video_id)
                continue

            json3_path = json3_files[0]
            with open(json3_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate wireMagic
            if data.get("wireMagic") != "pb3":
                logger.debug("Invalid wireMagic in json3 for %s", video_id)
                continue

            # Store in cache
            if cache_dir is not None:
                cache = CaptionCache(cache_dir)
                cache.put(video_id, data)

            return data

    raise CaptionFetchError(f"No json3 caption file found for {video_id}")


def _load_cookies_into_session(session, cookies_file: Path | None) -> None:
    """Load a Netscape-format cookies.txt into a curl_cffi session."""
    if not cookies_file or not cookies_file.is_file():
        return
    with open(cookies_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                domain, _, path, secure, _, name, value = parts[:7]
                session.cookies.set(name, value, domain=domain, path=path)


def fetch_json3_via_page(video_id: str, cache_dir: Path | None = None,
                         config: "Config | None" = None) -> dict:
    """Fetch json3 captions by scraping the watch page.

    The watch page embeds caption track URLs in ytInitialPlayerResponse.
    Uses curl_cffi for browser impersonation. When a cookies file is provided,
    loads it into the session to authenticate (bypasses rate limits).
    """
    if cache_dir is not None:
        cache = CaptionCache(cache_dir)
        cached = cache.get(video_id)
        if cached is not None:
            return cached

    try:
        from curl_cffi import requests as cf_requests
    except ImportError:
        raise CaptionFetchError("curl_cffi not installed (pip install curl_cffi)")

    # Create session with browser impersonation + cookies
    session = cf_requests.Session(impersonate="chrome")
    if config:
        _load_cookies_into_session(session, config.cookies_file)
    resp = session.get(f"https://www.youtube.com/watch?v={video_id}")
    if resp.status_code != 200:
        raise CaptionFetchError(f"Watch page returned {resp.status_code} for {video_id}")

    # Extract ytInitialPlayerResponse
    import re
    match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+?\});", resp.text)
    if not match:
        raise CaptionFetchError(f"No ytInitialPlayerResponse found for {video_id}")

    player_data = json.loads(match.group(1))
    tracks = (
        player_data
        .get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
    )

    # Find English track
    en_url = None
    for track in tracks:
        if track.get("languageCode") == "en":
            en_url = track.get("baseUrl")
            break

    if not en_url:
        raise CaptionFetchError(f"No English caption track found for {video_id}")

    # Fetch the json3 using the same session (shares cookies/TLS state)
    cap_resp = session.get(en_url + "&fmt=json3")
    if cap_resp.status_code != 200:
        raise CaptionFetchError(
            f"Caption fetch returned {cap_resp.status_code} for {video_id}"
        )

    data = cap_resp.json()
    if data.get("wireMagic") != "pb3":
        raise CaptionFetchError(f"Invalid json3 wireMagic for {video_id}")

    if cache_dir is not None:
        cache = CaptionCache(cache_dir)
        cache.put(video_id, data)

    return data


def fetch_transcript(video_id: str) -> list[dict]:
    """Fetch transcript segments using youtube_transcript_api.

    Returns a list of dicts with keys: text, start, duration.

    Raises CaptionFetchError if fetching fails.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise CaptionFetchError("youtube-transcript-api is not installed")

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=["en"])
    except Exception as e:
        raise CaptionFetchError(
            f"Failed to fetch transcript for {video_id}: {e}"
        ) from e

    return [
        {
            "text": snippet.text,
            "start": snippet.start,
            "duration": snippet.duration,
        }
        for snippet in transcript
    ]


def fetch_transcript_via_ytdlp(video_id: str) -> list[dict]:
    """Fetch transcript segments using yt-dlp as a fallback when
    youtube-transcript-api is IP-blocked.

    Fetches SRT subs via yt-dlp and parses them into segment dicts.

    Returns a list of dicts with keys: text, start, duration.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        for sub_flag in ("--write-auto-subs", "--write-subs"):
            cmd = [
                "yt-dlp",
                sub_flag,
                "--sub-format", "srv1",
                "--sub-lang", "en",
                "--skip-download",
                "--no-warnings",
                "--output", f"{tmpdir}/%(id)s.%(ext)s",
                "--", video_id,
            ]

            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

            srv1_files = list(Path(tmpdir).glob("*.srv1"))
            if not srv1_files:
                continue

            return _parse_srv1(srv1_files[0])

    raise CaptionFetchError(f"yt-dlp failed to fetch transcript for {video_id}")


def _parse_srv1(path: Path) -> list[dict]:
    """Parse YouTube srv1 (XML) subtitle format into segment dicts."""
    import xml.etree.ElementTree as ET

    tree = ET.parse(path)
    root = tree.getroot()
    segments = []

    for text_elem in root.iter("text"):
        start = float(text_elem.get("start", "0"))
        dur = float(text_elem.get("dur", "0"))
        content = text_elem.text or ""
        if content.strip():
            segments.append({
                "text": content.replace("\n", " ").strip(),
                "start": start,
                "duration": dur,
            })

    return segments
