"""Orchestrator: text -> chunks -> clips -> stitch -> output."""

import hashlib
import logging
import sys
import tempfile
from pathlib import Path

from yt_tts.config import Config
from yt_tts.exceptions import (
    BudgetExhaustedError,
    CaptionFetchError,
    ClipExtractionError,
    YtTtsError,
)
from yt_tts.types import ClipInfo, SearchResult, SynthesisResult, TimeRange

logger = logging.getLogger(__name__)


def _make_output_path(text: str, config: Config) -> Path:
    """Generate default output path from input text hash."""
    if config.output_path:
        return config.output_path
    normalized = " ".join(text.lower().split())
    hash_prefix = hashlib.sha256(normalized.encode()).hexdigest()[:8]
    ext = config.output_format
    return Path(f"yt-tts-{hash_prefix}.{ext}")


def _build_search_fn(config: Config):
    """Build the search function based on config (index or live video)."""
    if config.video_url:
        from yt_tts.core.search import search_live_video

        def search_fn(phrase: str) -> SearchResult | None:
            return search_live_video(phrase, config.video_url)
        return search_fn
    else:
        from yt_tts.core.index import TranscriptIndex
        from yt_tts.core.search import search_transcripts

        index = TranscriptIndex(config.db_path)

        def search_fn(phrase: str) -> SearchResult | None:
            return search_transcripts(phrase, index, config)
        return search_fn


def _build_resolve_fn(config: Config):
    """Build the resolve function that turns a search result into a clip."""
    from yt_tts.core.cache import CaptionCache, ClipCache
    from yt_tts.core.captions import fetch_json3, fetch_transcript
    from yt_tts.core.extract import extract_clip
    from yt_tts.core.ratelimit import InvocationBudget, RateLimiter
    from yt_tts.core.timestamps import (
        has_word_level_timing,
        locate_phrase,
        parse_json3,
    )

    caption_cache = None if config.no_cache else CaptionCache(config.cache_dir)
    clip_cache = None if config.no_cache else ClipCache(config.cache_dir)
    budget = InvocationBudget(config.max_caption_fetches, config.max_clip_downloads)
    rate_limiter = RateLimiter(
        base_sleep_s=config.ytdlp_sleep_s,
        backoff_initial_s=config.backoff_initial_s,
        backoff_multiplier=config.backoff_multiplier,
        backoff_max_s=config.backoff_max_s,
        max_retries=config.backoff_max_retries,
    )

    def resolve_fn(phrase: str, result: SearchResult) -> ClipInfo | None:
        video_id = result.video_id

        try:
            budget.use_caption_fetch()
        except BudgetExhaustedError:
            logger.warning("Caption fetch budget exhausted")
            return None

        # Try to get word-level timestamps from json3
        cache_dir = config.cache_dir if not config.no_cache else None
        json3_data = None

        # Method 1: yt-dlp --write-auto-subs / --write-subs
        try:
            rate_limiter.wait()
            json3_data = fetch_json3(video_id, cache_dir=cache_dir, config=config)
            rate_limiter.report_success()
        except Exception as e:
            logger.debug("yt-dlp json3 failed for %s: %s", video_id, e)

        # Method 2: Scrape watch page for caption URLs (bypasses timedtext 429)
        if json3_data is None:
            try:
                from yt_tts.core.captions import fetch_json3_via_page
                json3_data = fetch_json3_via_page(video_id, cache_dir=cache_dir, config=config)
                logger.info("Got json3 via page scrape for %s", video_id)
            except Exception as e:
                logger.debug("Page scrape json3 failed for %s: %s", video_id, e)

        time_range = None
        timestamp_source = "json3"

        if json3_data and has_word_level_timing(json3_data):
            word_timestamps = parse_json3(json3_data)
            time_range = locate_phrase(phrase, word_timestamps, config.min_confidence)

        if time_range is None:
            # Fallback to segment-level timestamps
            timestamp_source = "segment"
            segments = None

            # Try youtube-transcript-api first
            try:
                segments = fetch_transcript(video_id)
            except Exception as e:
                logger.debug("transcript-api failed for %s: %s", video_id, e)

            # Fallback to yt-dlp srv1 subs if transcript-api fails
            if segments is None:
                try:
                    from yt_tts.core.captions import fetch_transcript_via_ytdlp
                    segments = fetch_transcript_via_ytdlp(video_id)
                except Exception as e:
                    logger.debug("yt-dlp transcript also failed for %s: %s", video_id, e)

            if segments is not None:
                time_range = _locate_phrase_in_segments(phrase, segments)

            # Last resort: use Whisper to transcribe audio and locate phrase
            if time_range is None and result.context_text:
                timestamp_source = "whisper"
                est = _estimate_from_index_text(phrase, video_id, result, config)
                if est is not None:
                    try:
                        from yt_tts.core.align import transcribe_and_locate
                        # Try the estimated window first, then shift forward if not found
                        for shift in (0, 15000, 30000):
                            time_range = transcribe_and_locate(
                                video_id, phrase,
                                est.start_ms + shift, est.end_ms + shift,
                                config=config,
                            )
                            if time_range is not None:
                                break
                            logger.debug("Whisper didn't find phrase, shifting +%ds", shift // 1000 + 15)
                    except Exception as e:
                        logger.warning("Whisper alignment failed for %s: %s", video_id, e)

        if time_range is None:
            logger.warning("Could not locate '%s' in video %s", phrase, video_id)
            return None

        # Extract clip
        try:
            budget.use_clip_download()
        except BudgetExhaustedError:
            logger.warning("Clip download budget exhausted")
            return None

        try:
            rate_limiter.wait()
            clip_path = extract_clip(
                video_id, time_range.start_ms, time_range.end_ms, config, clip_cache
            )
            rate_limiter.report_success()
        except Exception as e:
            logger.warning("Clip extraction failed for %s: %s", video_id, e)
            return None

        return ClipInfo(
            video_id=video_id,
            video_title=result.title,
            phrase=phrase,
            start_ms=time_range.start_ms,
            end_ms=time_range.end_ms,
            file_path=clip_path,
            confidence=time_range.confidence,
            timestamp_source=timestamp_source,
        )

    return resolve_fn


def _locate_phrase_in_segments(phrase: str, segments: list[dict]) -> TimeRange | None:
    """Locate a phrase within segment-level transcript data."""
    phrase_lower = phrase.lower().strip()
    # Build full text with segment boundaries
    for seg in segments:
        text = seg.get("text", "").lower()
        if phrase_lower in text:
            start_ms = int(seg["start"] * 1000)
            duration_ms = int(seg.get("duration", 5) * 1000)
            return TimeRange(
                start_ms=start_ms,
                end_ms=start_ms + duration_ms,
                confidence=0.5,  # lower confidence for segment-level
            )

    # Try spanning multiple segments
    full_text = " ".join(seg.get("text", "") for seg in segments).lower()
    if phrase_lower in full_text:
        # Find which segments contain the phrase
        pos = 0
        for seg in segments:
            seg_text = seg.get("text", "")
            seg_start = pos
            pos += len(seg_text) + 1  # +1 for space

            match_pos = full_text.find(phrase_lower)
            if match_pos is not None and seg_start <= match_pos < pos:
                start_ms = int(seg["start"] * 1000)
                # Find end segment
                end_ms = start_ms + int(seg.get("duration", 5) * 1000)
                for seg2 in segments:
                    seg2_pos = full_text.find(seg2.get("text", "").lower())
                    if seg2_pos is not None and seg2_pos + len(seg2.get("text", "")) >= match_pos + len(phrase_lower):
                        end_ms = int((seg2["start"] + seg2.get("duration", 5)) * 1000)
                        break
                return TimeRange(start_ms=start_ms, end_ms=end_ms, confidence=0.3)

    return None


def _estimate_from_index_text(
    phrase: str, video_id: str, result: SearchResult, config: Config
) -> TimeRange | None:
    """Estimate timestamp from word position in the stored transcript.

    Uses video duration and the word-level position of the phrase in the
    transcript to estimate start/end times. Assumes roughly uniform speech
    rate. Extracts a wider clip to compensate for estimation error.
    """
    import subprocess

    # Get video duration via yt-dlp
    try:
        proc = subprocess.run(
            ["yt-dlp", "--print", "duration", "--", video_id],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        video_duration_s = float(proc.stdout.strip())
    except Exception:
        return None

    # Get full transcript from index
    try:
        from yt_tts.core.index import TranscriptIndex
        index = TranscriptIndex(config.db_path)
        conn = index._get_conn()
        row = conn.execute(
            "SELECT text FROM transcripts WHERE video_id = ?", (video_id,)
        ).fetchone()
        if not row:
            return None
        full_text = row["text"]
    except Exception:
        return None

    # Word-based position estimation (much more accurate than character-based)
    # Strip music notation symbols which inflate word count
    import re
    cleaned = re.sub(r'[♪♫🎵🎶]+', '', full_text)
    all_words = cleaned.lower().split()
    phrase_words = phrase.lower().split()
    total_words = len(all_words)
    if total_words == 0:
        return None

    # Find the phrase start word index via sliding window
    phrase_start_idx = None
    for i in range(total_words - len(phrase_words) + 1):
        if all_words[i:i + len(phrase_words)] == phrase_words:
            phrase_start_idx = i
            break

    if phrase_start_idx is None:
        # Fuzzy match: try substring match on joined text
        joined = " ".join(all_words)
        phrase_joined = " ".join(phrase_words)
        char_pos = joined.find(phrase_joined)
        if char_pos == -1:
            return None
        # Count words before this position
        phrase_start_idx = len(joined[:char_pos].split()) - 1
        phrase_start_idx = max(0, phrase_start_idx)

    # Estimate time based on word position fraction
    secs_per_word = video_duration_s / total_words
    start_s = phrase_start_idx * secs_per_word
    phrase_duration_s = len(phrase_words) * secs_per_word

    # Add generous padding (1.5s each side) since this is an estimate
    padding_s = 1.5
    start_ms = int(max(0, (start_s - padding_s)) * 1000)
    end_ms = int(min(video_duration_s, start_s + phrase_duration_s + padding_s) * 1000)

    frac = phrase_start_idx / total_words
    logger.info(
        "Estimated '%s' at %d-%dms (word %d/%d, %.0f%% into %ds video)",
        phrase, start_ms, end_ms, phrase_start_idx, total_words,
        frac * 100, video_duration_s,
    )

    return TimeRange(start_ms=start_ms, end_ms=end_ms, confidence=0.1)


def synthesize(text: str, config: Config) -> SynthesisResult:
    """Main synthesis pipeline: text -> audio file.

    Args:
        text: Input text to synthesize.
        config: Configuration.

    Returns:
        SynthesisResult with output path, duration, clips, missing words, and exit code.
    """
    from yt_tts.core.chunk import chunk_phrase, resolve_chunks
    from yt_tts.core.stitch import normalize_clip, stitch_clips

    # Validate input
    words = text.split()
    if not words:
        return SynthesisResult(
            output_path=None, duration_ms=0, clips=[], missing_words=[], exit_code=2,
        )

    if len(words) > config.max_input_words:
        print(
            f"Input too long: {len(words)} words (max {config.max_input_words})",
            file=sys.stderr,
        )
        return SynthesisResult(
            output_path=None, duration_ms=0, clips=[], missing_words=words, exit_code=2,
        )

    # Build functions
    try:
        search_fn = _build_search_fn(config)
    except Exception as e:
        logger.error("Failed to initialize search: %s", e)
        return SynthesisResult(
            output_path=None, duration_ms=0, clips=[], missing_words=words, exit_code=3,
        )

    resolve_fn = _build_resolve_fn(config)

    # Phase 1: Planning (sequential)
    logger.info("Planning chunks for: %s", text)
    try:
        plan = chunk_phrase(text, search_fn, config)
    except Exception as e:
        logger.error("Chunking failed: %s", e)
        return SynthesisResult(
            output_path=None, duration_ms=0, clips=[], missing_words=words, exit_code=3,
        )

    # Phase 2: Resolution (parallel)
    logger.info("Resolving %d chunks...", len(plan.chunks))
    plan = resolve_chunks(plan, resolve_fn, config)

    # Collect successful clips
    successful_clips = [c for c in plan.clips if c is not None]

    if not successful_clips:
        return SynthesisResult(
            output_path=None,
            duration_ms=0,
            clips=[],
            missing_words=plan.missing_words,
            exit_code=2,
        )

    # Phase 3: Stitching
    logger.info("Stitching %d clips...", len(successful_clips))
    try:
        # Normalize all clips
        normalized_paths = []
        for clip in successful_clips:
            norm_path = normalize_clip(clip.file_path, config)
            normalized_paths.append(norm_path)

        # Build gap list (silence for missing chunks between successful ones)
        gaps = []
        for i in range(len(plan.clips) - 1):
            if plan.clips[i] is None or plan.clips[i + 1] is None:
                gaps.append(config.silence_gap_ms)
            else:
                gaps.append(0)

        # Filter gaps to match normalized_paths (only between successful clips)
        clip_gaps = []
        last_success_idx = None
        for i, clip in enumerate(plan.clips):
            if clip is not None:
                if last_success_idx is not None:
                    # Count missing chunks between last success and this one
                    missing_between = sum(
                        1 for j in range(last_success_idx + 1, i)
                        if plan.clips[j] is None
                    )
                    gap = config.silence_gap_ms * missing_between if missing_between > 0 else 0
                    clip_gaps.append(gap)
                last_success_idx = i

        output_path = _make_output_path(text, config)
        final_path = stitch_clips(normalized_paths, clip_gaps, config)

        # Move to output location
        import shutil
        shutil.move(str(final_path), str(output_path))

        # Calculate duration
        duration_ms = sum(c.end_ms - c.start_ms for c in successful_clips)

        exit_code = 0 if not plan.missing_words else 1

        return SynthesisResult(
            output_path=output_path,
            duration_ms=duration_ms,
            clips=successful_clips,
            missing_words=plan.missing_words,
            exit_code=exit_code,
        )

    except Exception as e:
        logger.error("Stitching failed: %s", e)
        return SynthesisResult(
            output_path=None,
            duration_ms=0,
            clips=successful_clips,
            missing_words=plan.missing_words,
            exit_code=3,
        )
