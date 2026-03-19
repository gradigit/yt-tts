"""Audio clip extraction from YouTube videos via yt-dlp and ffmpeg."""

import logging
import subprocess
import tempfile
from pathlib import Path

from yt_tts.config import Config
from yt_tts.core.cache import ClipCache
from yt_tts.exceptions import ClipExtractionError

logger = logging.getLogger(__name__)


def _resolve_padding(config: Config) -> int:
    """Resolve tightness setting to padding milliseconds."""
    t = config.tightness
    if isinstance(t, int):
        return t
    return {"tight": 30, "normal": 100, "loose": 250}.get(t, 100)


def get_stream_url(video_id: str, format_id: str = "140") -> str:
    """Get a direct audio stream URL from YouTube using yt-dlp.

    Calls ``yt-dlp -g -f {format_id} -- {video_id}`` and returns the stream
    URL.  Falls back to ``bestaudio`` if *format_id* is unavailable.

    Note: Does NOT use cookies — the android_vr client works without auth
    and cookies can break it by switching to the web client which needs JS solving.

    Raises:
        ClipExtractionError: when yt-dlp fails for both format attempts.
    """
    for fmt in (format_id, "bestaudio"):
        cmd = ["yt-dlp", "-g", "-f", fmt, "--", video_id]
        logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            if url:
                return url
        logger.debug(
            "yt-dlp format %s failed (rc=%d): %s",
            fmt,
            result.returncode,
            result.stderr.strip(),
        )

    raise ClipExtractionError(
        f"Failed to get stream URL for video {video_id} (tried formats: {format_id}, bestaudio)"
    )


def validate_clip(path: Path, expected_duration_ms: int | None = None) -> bool:
    """Validate an extracted clip.

    Checks that *path* exists and is non-zero size.  When
    *expected_duration_ms* is given, verifies (via ffprobe) that the actual
    duration is within 50 % of the expected value.
    """
    if not path.is_file():
        return False
    if path.stat().st_size == 0:
        return False

    if expected_duration_ms is not None:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return False
            actual_duration_ms = float(result.stdout.strip()) * 1000
            lower = expected_duration_ms * 0.5
            upper = expected_duration_ms * 1.5
            if not (lower <= actual_duration_ms <= upper):
                logger.warning(
                    "Clip duration %d ms outside tolerance [%d, %d] for %s",
                    int(actual_duration_ms),
                    int(lower),
                    int(upper),
                    path,
                )
                return False
        except (ValueError, subprocess.TimeoutExpired):
            return False

    return True


def extract_clip(
    video_id: str,
    start_ms: int,
    end_ms: int,
    config: Config,
    cache: ClipCache | None = None,
) -> Path:
    """Extract an audio clip from a YouTube video.

    1. Return immediately if the clip is already cached.
    2. Obtain a stream URL via :func:`get_stream_url`.
    3. Use ffmpeg to extract the segment (re-encoding for sample-accurate
       cuts).  Padding from ``config.clip_padding_ms`` is applied on both
       sides.
    4. On HTTP 403/410 errors, retry once with a fresh URL.
    5. Validate the resulting clip and store it in the cache.

    Returns:
        Path to the clip (may be inside the cache directory).

    Raises:
        ClipExtractionError: on any unrecoverable failure.
    """
    # Compute timing with padding (respects tightness setting)
    padding_ms = _resolve_padding(config)
    padded_start_ms = max(0, start_ms - padding_ms)
    padded_end_ms = end_ms + padding_ms

    # 1. Cache check (keyed on padded boundaries so tightness changes bust cache)
    if cache is not None:
        cached = cache.get(video_id, padded_start_ms, padded_end_ms)
        if cached is not None:
            logger.debug("Cache hit: %s", cached)
            return cached
    duration_ms = padded_end_ms - padded_start_ms

    start_s = padded_start_ms / 1000.0
    duration_s = duration_ms / 1000.0

    # 2. Get stream URL
    url = get_stream_url(video_id, config.preferred_format)

    # 3. Build ffmpeg command and run
    tmp_dir = tempfile.mkdtemp(prefix="yt-tts-clip-")
    output_path = Path(tmp_dir) / f"{video_id}_{start_ms}_{end_ms}.m4a"

    def _run_ffmpeg(stream_url: str) -> subprocess.CompletedProcess:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_s:.3f}",
            "-i",
            stream_url,
            "-t",
            f"{duration_s:.3f}",
            "-c:a",
            "aac",
            "-b:a",
            config.audio_bitrate,
            str(output_path),
        ]
        logger.debug("Running: %s", " ".join(cmd))
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

    result = _run_ffmpeg(url)

    # 4. Retry on 403 / 410
    if result.returncode != 0:
        stderr = result.stderr or ""
        if "403" in stderr or "410" in stderr:
            logger.warning("HTTP 403/410 for %s — retrying with fresh URL", video_id)
            url = get_stream_url(video_id, config.preferred_format)
            result = _run_ffmpeg(url)

    if result.returncode != 0:
        raise ClipExtractionError(
            f"ffmpeg failed for {video_id} [{start_ms}-{end_ms}]: {(result.stderr or '').strip()}"
        )

    # 5. Validate
    if not validate_clip(output_path, expected_duration_ms=duration_ms):
        raise ClipExtractionError(f"Clip validation failed for {video_id} [{start_ms}-{end_ms}]")

    # 6. Cache and return
    if cache is not None:
        return cache.put(video_id, padded_start_ms, padded_end_ms, output_path)

    return output_path
