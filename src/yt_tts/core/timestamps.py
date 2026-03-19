"""Parse json3 captions into word-level timestamps and locate phrases."""

import re
import string

from yt_tts.types import TimeRange, WordTimestamp


def parse_json3(data: dict) -> list[WordTimestamp]:
    """Parse json3 caption data into a list of WordTimestamp objects.

    Iterates events[].segs[]. Skips events without segs and whitespace-only
    segs. Computes start_ms = tStartMs + (tOffsetMs or 0). For end_ms, uses
    the start of the next word, or tStartMs + dDurationMs for the last word
    in the event. Strips leading spaces from the utf8 field. Reads acAsrConf
    (defaults to 0 if missing).
    """
    words: list[WordTimestamp] = []

    for event in data.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue

        t_start_ms = event.get("tStartMs", 0)
        d_duration_ms = event.get("dDurationMs", 0)

        # First pass: collect non-whitespace segments with their start_ms
        seg_entries: list[tuple[str, int, int]] = []  # (text, start_ms, confidence)
        for seg in segs:
            text = seg.get("utf8", "")
            if not text or text.strip() == "":
                continue
            offset = seg.get("tOffsetMs", 0)
            start_ms = t_start_ms + offset
            confidence = seg.get("acAsrConf", 0)
            seg_entries.append((text.lstrip(), start_ms, confidence))

        # Second pass: compute end_ms for each segment
        for i, (text, start_ms, confidence) in enumerate(seg_entries):
            if i + 1 < len(seg_entries):
                end_ms = seg_entries[i + 1][1]
            else:
                # Last word: estimate end from average word duration in this event,
                # capped at event end. Don't use full event duration — it includes
                # silence/pause after the last word.
                event_end_ms = t_start_ms + d_duration_ms
                if len(seg_entries) > 1:
                    # Average ms per word from all previous words
                    first_start = seg_entries[0][1]
                    avg_word_ms = (start_ms - first_start) / (len(seg_entries) - 1)
                    end_ms = min(event_end_ms, start_ms + int(avg_word_ms * 1.2))
                else:
                    end_ms = event_end_ms
            words.append(
                WordTimestamp(
                    word=text,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    confidence=confidence,
                )
            )

    return words


def has_word_level_timing(data: dict) -> bool:
    """Check if json3 data has word-level timing (tOffsetMs fields in segs).

    Auto-generated captions typically have tOffsetMs on individual segments,
    while manual captions do not.
    """
    for event in data.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue
        for seg in segs:
            if "tOffsetMs" in seg:
                return True
    return False


_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")


def _normalize(word: str) -> str:
    """Normalize a word for comparison: lowercase, strip punctuation."""
    return _PUNCT_RE.sub("", word.lower()).strip()


def locate_phrase(
    phrase: str,
    word_timestamps: list[WordTimestamp],
    min_confidence: int = 128,
) -> TimeRange | None:
    """Find a phrase in the word timestamps using sliding window matching.

    Performs normalized comparison (lowercase, stripped punctuation).
    Returns the best match by average confidence, or None if no match found.
    Only matches where all words meet min_confidence are considered.

    Handles contractions by matching normalized forms.
    """
    phrase_words = phrase.split()
    if not phrase_words or not word_timestamps:
        return None

    n = len(phrase_words)
    normalized_phrase = [_normalize(w) for w in phrase_words]

    # Filter out empty normalized words from the phrase
    normalized_phrase = [w for w in normalized_phrase if w]
    n = len(normalized_phrase)
    if n == 0:
        return None

    best_match: TimeRange | None = None
    best_avg_conf = -1.0

    for i in range(len(word_timestamps) - n + 1):
        window = word_timestamps[i : i + n]
        normalized_window = [_normalize(wt.word) for wt in window]

        if normalized_window == normalized_phrase:
            # Check confidence threshold
            if all(wt.confidence >= min_confidence for wt in window):
                avg_conf = sum(wt.confidence for wt in window) / n
                if avg_conf > best_avg_conf:
                    best_avg_conf = avg_conf
                    best_match = TimeRange(
                        start_ms=window[0].start_ms,
                        end_ms=window[-1].end_ms,
                        confidence=avg_conf,
                    )

    return best_match
