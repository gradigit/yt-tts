"""Local audio transcription for word-level timestamps.

Uses the unified ASR backend (faster-whisper/mlx-whisper/parakeet-mlx)
to transcribe audio and locate phrases, bypassing YouTube's caption API.
"""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from yt_tts.types import TimeRange

logger = logging.getLogger(__name__)


def transcribe_and_locate(
    video_id: str,
    phrase: str,
    estimated_start_ms: int,
    estimated_end_ms: int,
    config=None,
    known_text: str | None = None,
) -> TimeRange | None:
    """Download audio around the estimated position, align/transcribe it,
    and find the exact timestamps for the phrase.

    If known_text is provided, uses CTC forced alignment (faster, more accurate).
    Otherwise falls back to ASR transcription.
    """
    from yt_tts.core.extract import get_stream_url

    # Scale download window with estimate span
    estimate_span_ms = estimated_end_ms - estimated_start_ms
    padding_ms = max(5000, min(15000, estimate_span_ms * 2))
    dl_start_ms = max(0, estimated_start_ms - padding_ms)
    dl_end_ms = estimated_end_ms + padding_ms
    dl_duration_s = (dl_end_ms - dl_start_ms) / 1000.0
    if dl_duration_s > 60:
        dl_duration_s = 60
        dl_end_ms = dl_start_ms + 60000

    try:
        stream_url = get_stream_url(video_id)
    except Exception as e:
        logger.warning("Failed to get stream URL for %s: %s", video_id, e)
        return None

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{dl_start_ms / 1000.0:.3f}",
            "-i",
            stream_url,
            "-t",
            f"{dl_duration_s:.3f}",
            "-ar",
            "16000",
            "-ac",
            "1",
            tmp_path.as_posix(),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.warning("ffmpeg failed: %s", result.stderr[-200:])
            return None

        # Use forced alignment if we have known text (better: 30ms vs 200ms accuracy)
        # Fall back to ASR transcription if no known text
        if known_text:
            try:
                from yt_tts.core.asr import forced_align

                asr_result = forced_align(tmp_path.as_posix(), known_text)
                logger.debug("Using CTC forced alignment with known text")
            except Exception as e:
                logger.debug("Forced alignment failed (%s), falling back to ASR", e)
                from yt_tts.core.asr import transcribe

                model_size = config.asr_model if config else "tiny"
                backend = config.asr_backend if config else "auto"
                asr_result = transcribe(tmp_path.as_posix(), model_size=model_size, backend=backend)
        else:
            from yt_tts.core.asr import transcribe

            model_size = config.asr_model if config else "tiny"
            backend = config.asr_backend if config else "auto"
            asr_result = transcribe(tmp_path.as_posix(), model_size=model_size, backend=backend)

        all_words = [
            {
                "word": w.word.strip().lower(),
                "start": w.start,
                "end": w.end,
                "probability": w.probability,
            }
            for w in asr_result.words
            if w.word.strip()
        ]

        if not all_words:
            logger.warning("ASR produced no words for %s", video_id)
            return None

        logger.debug(
            "ASR transcribed %d words: %s",
            len(all_words),
            " ".join(w["word"] for w in all_words[:20]) + "...",
        )

        # Find the phrase in ASR output
        phrase_words = phrase.lower().split()
        match = _find_phrase_in_words(phrase_words, all_words)

        if match is None:
            match = _find_phrase_fuzzy(phrase_words, all_words)

        if match is None:
            logger.warning(
                "Phrase '%s' not found in ASR output for %s. Got: %s",
                phrase,
                video_id,
                " ".join(w["word"] for w in all_words[:30]),
            )
            return None

        start_idx, end_idx = match
        local_start_s = all_words[start_idx]["start"]
        local_end_s = all_words[end_idx]["end"]
        video_start_ms = dl_start_ms + int(local_start_s * 1000)
        video_end_ms = dl_start_ms + int(local_end_s * 1000)

        confidence = sum(all_words[i]["probability"] for i in range(start_idx, end_idx + 1)) / (
            end_idx - start_idx + 1
        )

        logger.info(
            "ASR located '%s' at %d-%dms (confidence: %.2f)",
            phrase,
            video_start_ms,
            video_end_ms,
            confidence,
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
    return re.sub(r"[^\w']", "", w.lower())


def _find_phrase_in_words(phrase_words: list[str], all_words: list[dict]) -> tuple[int, int] | None:
    """Exact sliding window match."""
    n = len(phrase_words)
    normalized_phrase = [_normalize_word(w) for w in phrase_words]

    for i in range(len(all_words) - n + 1):
        window = [_normalize_word(all_words[i + j]["word"]) for j in range(n)]
        if window == normalized_phrase:
            return (i, i + n - 1)
    return None


def _find_phrase_fuzzy(phrase_words: list[str], all_words: list[dict]) -> tuple[int, int] | None:
    """Fuzzy match — allow minor differences."""
    n = len(phrase_words)
    normalized_phrase = [_normalize_word(w) for w in phrase_words]
    best_score = 0
    best_match = None

    for i in range(len(all_words) - n + 1):
        window = [_normalize_word(all_words[i + j]["word"]) for j in range(n)]
        score = sum(1 for a, b in zip(window, normalized_phrase) if a == b)
        if score > best_score and score >= max(1, int(n * 0.7)):
            best_score = score
            best_match = (i, i + n - 1)

    return best_match
