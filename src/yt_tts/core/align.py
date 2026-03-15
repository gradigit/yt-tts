"""Local audio transcription for word-level timestamps.

Uses faster-whisper to transcribe audio and locate phrases,
bypassing YouTube's caption API entirely.
"""

import logging
import subprocess
import tempfile
from pathlib import Path

from yt_tts.exceptions import CaptionFetchError
from yt_tts.types import TimeRange

logger = logging.getLogger(__name__)

# Module-level model cache — load once, reuse across calls
_model = None
_model_size = None


def _get_model(model_size: str = "base"):
    """Get or create the Whisper model (cached)."""
    global _model, _model_size
    if _model is not None and _model_size == model_size:
        return _model

    from faster_whisper import WhisperModel

    logger.info("Loading Whisper model '%s' (first use, may download)...", model_size)
    _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    _model_size = model_size
    return _model


def transcribe_and_locate(
    video_id: str,
    phrase: str,
    estimated_start_ms: int,
    estimated_end_ms: int,
    config=None,
) -> TimeRange | None:
    """Download audio around the estimated position, transcribe it with
    Whisper, and find the exact timestamps for the phrase.

    Args:
        video_id: YouTube video ID.
        phrase: The phrase to locate.
        estimated_start_ms: Rough start position from index estimation.
        estimated_end_ms: Rough end position from index estimation.
        config: Config object.

    Returns:
        TimeRange with precise timestamps, or None if phrase not found.
    """
    from yt_tts.core.extract import get_stream_url

    # Download a generous window around the estimate.
    # Scale padding with the estimate span — wider estimates need more context.
    # For a short video (20s), ±5s is plenty. For a 3min+ video, use ±15s.
    estimate_span_ms = estimated_end_ms - estimated_start_ms
    padding_ms = max(5000, min(15000, estimate_span_ms * 2))
    dl_start_ms = max(0, estimated_start_ms - padding_ms)
    dl_end_ms = estimated_end_ms + padding_ms
    dl_duration_s = (dl_end_ms - dl_start_ms) / 1000.0
    # Cap at 60s to keep Whisper fast
    if dl_duration_s > 60:
        dl_duration_s = 60
        dl_end_ms = dl_start_ms + 60000

    # Get stream URL (this still works — not rate limited)
    try:
        stream_url = get_stream_url(video_id)
    except Exception as e:
        logger.warning("Failed to get stream URL for %s: %s", video_id, e)
        return None

    # Download the audio segment
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{dl_start_ms / 1000.0:.3f}",
            "-i", stream_url,
            "-t", f"{dl_duration_s:.3f}",
            "-ar", "16000",  # Whisper expects 16kHz
            "-ac", "1",      # mono
            tmp_path.as_posix(),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.warning("ffmpeg failed: %s", result.stderr[-200:])
            return None

        # Transcribe with Whisper
        model = _get_model("base")
        segments, info = model.transcribe(
            tmp_path.as_posix(),
            word_timestamps=True,
            language="en",
        )

        # Collect all words with timestamps
        all_words = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    all_words.append({
                        "word": w.word.strip().lower(),
                        "start": w.start,
                        "end": w.end,
                        "probability": w.probability,
                    })

        if not all_words:
            logger.warning("Whisper produced no words for %s", video_id)
            return None

        logger.debug(
            "Whisper transcribed %d words: %s",
            len(all_words),
            " ".join(w["word"] for w in all_words[:20]) + "...",
        )

        # Find the phrase in the whisper output
        phrase_words = phrase.lower().split()
        match = _find_phrase_in_words(phrase_words, all_words)

        if match is None:
            # Try fuzzy match (whisper might transcribe slightly differently)
            match = _find_phrase_fuzzy(phrase_words, all_words)

        if match is None:
            logger.warning(
                "Phrase '%s' not found in Whisper output for %s. Got: %s",
                phrase, video_id,
                " ".join(w["word"] for w in all_words[:30]),
            )
            return None

        start_idx, end_idx = match
        # Convert local timestamps back to video timestamps
        local_start_s = all_words[start_idx]["start"]
        local_end_s = all_words[end_idx]["end"]
        video_start_ms = dl_start_ms + int(local_start_s * 1000)
        video_end_ms = dl_start_ms + int(local_end_s * 1000)

        confidence = sum(
            all_words[i]["probability"] for i in range(start_idx, end_idx + 1)
        ) / (end_idx - start_idx + 1)

        logger.info(
            "Whisper located '%s' at %d-%dms (confidence: %.2f)",
            phrase, video_start_ms, video_end_ms, confidence,
        )

        return TimeRange(
            start_ms=video_start_ms,
            end_ms=video_end_ms,
            confidence=confidence,
        )

    finally:
        tmp_path.unlink(missing_ok=True)


def _normalize_word(w: str) -> str:
    """Strip punctuation for matching."""
    import re
    return re.sub(r"[^\w']", "", w.lower())


def _find_phrase_in_words(
    phrase_words: list[str], all_words: list[dict]
) -> tuple[int, int] | None:
    """Exact sliding window match."""
    n = len(phrase_words)
    normalized_phrase = [_normalize_word(w) for w in phrase_words]

    for i in range(len(all_words) - n + 1):
        window = [_normalize_word(all_words[i + j]["word"]) for j in range(n)]
        if window == normalized_phrase:
            return (i, i + n - 1)
    return None


def _find_phrase_fuzzy(
    phrase_words: list[str], all_words: list[dict]
) -> tuple[int, int] | None:
    """Fuzzy match — allow minor differences (e.g., 'gonna' vs 'going to')."""
    n = len(phrase_words)
    normalized_phrase = [_normalize_word(w) for w in phrase_words]
    best_score = 0
    best_match = None

    for i in range(len(all_words) - n + 1):
        window = [_normalize_word(all_words[i + j]["word"]) for j in range(n)]
        score = sum(1 for a, b in zip(window, normalized_phrase) if a == b)
        # Require at least 70% of words to match
        if score > best_score and score >= max(1, int(n * 0.7)):
            best_score = score
            best_match = (i, i + n - 1)

    return best_match
