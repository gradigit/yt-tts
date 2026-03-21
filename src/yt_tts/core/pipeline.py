"""Orchestrator: text -> chunks -> clips -> stitch -> output."""

import hashlib
import logging
import sys
from pathlib import Path

from yt_tts.config import Config
from yt_tts.exceptions import (
    BudgetExhaustedError,
)
from yt_tts.types import ClipInfo, SearchResult, SynthesisResult, TimeRange

logger = logging.getLogger(__name__)


def _verify_and_trim_clip(
    clip_path: Path, expected_phrase: str, threshold: float = 0.8
) -> tuple[bool, Path | None]:
    """Verify a clip contains the expected phrase and trim to just those words.

    Uses ASR word-level timestamps to precisely cut the clip down to only
    the target phrase, removing any extra words at the start/end.

    Returns (passed, trimmed_path):
    - (True, None) if clip is clean (no trimming needed)
    - (True, trimmed_path) if clip was trimmed to the target phrase
    - (False, None) if target phrase not found in clip audio
    """
    import re
    import subprocess
    import tempfile

    expected_words = expected_phrase.lower().split()
    _SKIP_VERIFY_WORDS = {"the", "a", "an", "of", "in", "on", "to", "is", "it", "we", "or", "at", "by", "as", "if", "so", "do", "no", "up", "be", "he", "my"}
    if len(expected_words) == 1 and expected_words[0] in _SKIP_VERIFY_WORDS:
        logger.debug("Skipping verification for short function word: '%s'", expected_phrase)
        return True, None

    try:
        from yt_tts.core.asr import transcribe

        # Use 'base' model for verification — 'tiny' is too inaccurate,
        # causing false rejections and missed trimming opportunities.
        # 'base' adds ~200ms but is much more reliable for word matching.
        result = transcribe(str(clip_path), model_size="base", backend="auto")

        if not result.words:
            # No word timestamps — fall back to text-only check
            heard = re.sub(r"[^\w\s']", "", result.text.lower()).split()
            expected_clean = re.sub(r"[^\w\s']", "", expected_phrase.lower()).split()
            if not expected_clean:
                return True, None
            overlap = set(expected_clean) & set(heard)
            recall = len(overlap) / len(expected_clean) if expected_clean else 1
            logger.debug("Verify (no timestamps): recall=%.0f%%", recall * 100)
            return recall >= threshold, None

        # Build clean word list with timestamps from ASR
        asr_words = []
        for w in result.words:
            clean = re.sub(r"[^\w']", "", w.word.lower()).strip()
            if clean:
                asr_words.append((clean, w.start, w.end))

        expected_clean = [re.sub(r"[^\w']", "", w.lower()).strip() for w in expected_words]
        expected_clean = [w for w in expected_clean if w]

        if not expected_clean or not asr_words:
            return True, None

        # Find the best matching window in ASR output using sliding window
        n = len(expected_clean)
        best_score = 0
        best_start_idx = -1
        best_end_idx = -1

        for i in range(len(asr_words)):
            # Try to match expected words starting from position i
            score = 0
            first_match = -1
            last_match = -1
            search_from = i
            for exp_word in expected_clean:
                for j in range(search_from, min(search_from + 4, len(asr_words))):
                    if asr_words[j][0] == exp_word:
                        score += 1
                        if first_match < 0:
                            first_match = j
                        last_match = j
                        search_from = j + 1
                        break

            if score > best_score and first_match >= 0:
                best_score = score
                best_start_idx = first_match  # index of FIRST matched word
                best_end_idx = last_match  # index of LAST matched word

        recall = best_score / len(expected_clean)
        total_asr_words = len(asr_words)
        extra = total_asr_words - len(expected_clean)

        # Check contiguity: matched words should span a compact window,
        # not be scattered across a long clip. If the window contains
        # many more words than expected, the match is probably spurious.
        window_span = best_end_idx - best_start_idx + 1 if best_start_idx >= 0 else 0
        contiguity_ok = window_span <= len(expected_clean) * 2  # allow up to 2x gaps

        logger.debug(
            "Verify clip: expected='%s', heard='%s', recall=%.0f%%, matched %d/%d, extra=%d, window=[%d:%d], span=%d, contiguous=%s",
            expected_phrase,
            result.text.strip()[:60],
            recall * 100,
            best_score, len(expected_clean),
            extra,
            best_start_idx, best_end_idx,
            window_span,
            contiguity_ok,
        )

        if recall < threshold or not contiguity_ok:
            return False, None

        # Always trim to matched word boundaries if we have timestamps
        # This is the key fix: use ASR word timestamps to cut precisely
        if best_start_idx >= 0 and best_end_idx >= 0:
            trim_start = asr_words[best_start_idx][1]  # start time of first matched word
            trim_end = asr_words[best_end_idx][2]  # end time of last matched word

            # Minimal padding to avoid cutting mid-phoneme
            trim_start = max(0, trim_start - 0.02)
            trim_end = trim_end + 0.03

            duration = trim_end - trim_start

            # Only trim if we'd actually remove something meaningful
            clip_duration = asr_words[-1][2] if asr_words else 0
            savings = clip_duration - duration

            if duration > 0.05 and savings > 0.1:
                trim_ext = clip_path.suffix or ".m4a"
                tmp = tempfile.NamedTemporaryFile(
                    suffix=trim_ext, prefix="yt-tts-trim-", delete=False
                )
                tmp.close()
                trimmed = Path(tmp.name)

                # Determine output codec based on input format
                ext = clip_path.suffix.lower()
                if ext in (".mp3",):
                    codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
                elif ext in (".m4a", ".aac"):
                    codec_args = ["-c:a", "aac", "-b:a", "128k"]
                else:
                    codec_args = ["-c:a", "copy"]

                cmd = [
                    "ffmpeg", "-y", "-i", str(clip_path),
                    "-ss", f"{trim_start:.3f}",
                    "-t", f"{duration:.3f}",
                ] + codec_args + [str(trimmed)]
                proc = subprocess.run(cmd, capture_output=True)
                if proc.returncode == 0 and trimmed.exists() and trimmed.stat().st_size > 0:
                    logger.debug(
                        "Trimmed clip %.2f-%.2fs, saved %.1fs (%d extra words removed)",
                        trim_start, trim_end, savings, extra,
                    )
                    return True, trimmed

        return True, None

    except Exception as e:
        logger.warning("Verify clip: ASR failed (%s), accepting clip unverified", type(e).__name__)
        return True, None


def _verify_clip(clip_path: Path, expected_phrase: str, threshold: float = 0.6) -> bool:
    """Verify a clip contains the expected phrase. Legacy wrapper."""
    passed, _ = _verify_and_trim_clip(clip_path, expected_phrase, threshold)
    return passed


def _make_output_path(text: str, config: Config) -> Path:
    """Generate default output path from input text hash."""
    if config.output_path:
        return config.output_path
    normalized = " ".join(text.lower().split())
    hash_prefix = hashlib.sha256(normalized.encode()).hexdigest()[:8]
    ext = config.output_format
    return Path(f"yt-tts-{hash_prefix}.{ext}")


def _build_search_fn(config: Config):
    """Build the search function based on config (index or live video).

    Returns a function that takes a phrase and returns the best SearchResult,
    plus a multi_search function that returns ranked candidates for retry.
    """
    if config.video_url:
        from yt_tts.core.search import search_live_video

        def search_fn(phrase: str) -> SearchResult | None:
            return search_live_video(phrase, config.video_url)

        def multi_search_fn(phrase: str) -> list[SearchResult]:
            r = search_live_video(phrase, config.video_url)
            return [r] if r else []

        return search_fn, multi_search_fn
    else:
        from yt_tts.core.index import TranscriptIndex
        from yt_tts.core.search import search_transcripts, search_transcripts_multi

        index = TranscriptIndex(config.db_path)

        def search_fn(phrase: str) -> SearchResult | None:
            return search_transcripts(phrase, index, config)

        def multi_search_fn(phrase: str) -> list[SearchResult]:
            return search_transcripts_multi(phrase, index, config, limit=10)

        return search_fn, multi_search_fn


def _build_resolve_fn(config: Config):
    """Build the resolve function that turns a search result into a clip."""
    from yt_tts.core.cache import ClipCache
    from yt_tts.core.captions import fetch_json3, fetch_transcript
    from yt_tts.core.extract import extract_clip
    from yt_tts.core.ratelimit import InvocationBudget, RateLimiter
    from yt_tts.core.timestamps import (
        has_word_level_timing,
        locate_phrase,
        parse_json3,
    )

    clip_cache = None if config.no_cache else ClipCache(config.cache_dir)
    budget = InvocationBudget(config.max_caption_fetches, config.max_clip_downloads)
    rate_limiter = RateLimiter(
        base_sleep_s=config.ytdlp_sleep_s,
        backoff_initial_s=config.backoff_initial_s,
        backoff_multiplier=config.backoff_multiplier,
        backoff_max_s=config.backoff_max_s,
        max_retries=config.backoff_max_retries,
    )

    # Caption API circuit breaker — persists to disk so we don't waste time
    # on subsequent runs when YouTube is rate-limiting us
    _breaker_file = config.cache_dir / ".caption_api_breaker"

    def _check_breaker() -> bool:
        """Returns True if caption APIs should be skipped."""
        if _breaker_file.is_file():
            import time

            age = time.time() - _breaker_file.stat().st_mtime
            if age < 3600:  # 1 hour expiry
                return True
            _breaker_file.unlink(missing_ok=True)
        return False

    def _trip_breaker():
        _breaker_file.parent.mkdir(parents=True, exist_ok=True)
        _breaker_file.touch()

    caption_api_dead = _check_breaker()
    if caption_api_dead:
        logger.info("Caption API circuit breaker active (tripped <1h ago), using Whisper directly")

    def resolve_fn(phrase: str, result: SearchResult) -> ClipInfo | None:
        nonlocal caption_api_dead
        video_id = result.video_id

        try:
            budget.use_caption_fetch()
        except BudgetExhaustedError:
            logger.warning("Caption fetch budget exhausted")
            return None

        cache_dir = config.cache_dir if not config.no_cache else None
        json3_data = None
        time_range = None
        timestamp_source = "json3"

        # Only try caption APIs if they haven't already failed with 429
        if not caption_api_dead:
            # Method 1: yt-dlp --write-auto-subs / --write-subs
            try:
                json3_data = fetch_json3(video_id, cache_dir=cache_dir, config=config)
            except Exception as e:
                err_str = str(e)
                logger.debug("yt-dlp json3 failed for %s: %s", video_id, e)
                if "429" in err_str or "No json3" in err_str:
                    # Try page scrape once before giving up on APIs
                    try:
                        from yt_tts.core.captions import fetch_json3_via_page

                        json3_data = fetch_json3_via_page(
                            video_id, cache_dir=cache_dir, config=config
                        )
                        logger.info("Got json3 via page scrape for %s", video_id)
                    except Exception as e2:
                        if "429" in str(e2):
                            caption_api_dead = True
                            _trip_breaker()
                            logger.info("Caption APIs 429 — switching to Whisper")
                        else:
                            logger.debug("Page scrape failed for %s: %s", video_id, e2)
        else:
            logger.debug("Skipping caption APIs (429 circuit breaker) for %s", video_id)

        if json3_data and has_word_level_timing(json3_data):
            word_timestamps = parse_json3(json3_data)
            time_range = locate_phrase(phrase, word_timestamps, config.min_confidence)

            # Sanity check: if json3 range is wildly too wide, refine
            if time_range is not None:
                phrase_words = len(phrase.split())
                expected_ms = phrase_words * 500 + 500  # ~0.5s/word + 0.5s buffer
                actual_ms = time_range.end_ms - time_range.start_ms
                if actual_ms > expected_ms * 4:
                    logger.debug(
                        "json3 range too wide (%dms for %d words, expected ~%dms), will refine",
                        actual_ms, phrase_words, expected_ms,
                    )
                    # Keep as estimate, fall through to alignment
                    time_range = None

        if time_range is None and not caption_api_dead:
            # Fallback to segment-level timestamps (also hits timedtext API)
            timestamp_source = "segment"
            segments = None
            seg_range = None

            try:
                segments = fetch_transcript(video_id)
            except Exception as e:
                if "429" in str(e) or "IpBlocked" in str(type(e).__name__):
                    caption_api_dead = True
                    _trip_breaker()
                logger.debug("transcript-api failed for %s: %s", video_id, e)

            if segments is None and not caption_api_dead:
                try:
                    from yt_tts.core.captions import fetch_transcript_via_ytdlp

                    segments = fetch_transcript_via_ytdlp(video_id)
                except Exception as e:
                    if "429" in str(e):
                        caption_api_dead = True
                        _trip_breaker()
                    logger.debug("yt-dlp transcript also failed for %s: %s", video_id, e)

            if segments is not None:
                seg_range = _locate_phrase_in_segments(phrase, segments)
                if seg_range is not None and seg_range.confidence < 1.0:
                    # Segment-level timestamps are too coarse (2-5s segments).
                    # Use them as an estimate for forced alignment instead of
                    # extracting directly — this gives ~30ms word boundaries.
                    logger.debug(
                        "Segment timestamps found (%d-%dms), refining with alignment",
                        seg_range.start_ms, seg_range.end_ms,
                    )
                    # Will fall through to the alignment path below
                elif seg_range is not None:
                    time_range = seg_range

        # Local alignment — runs when caption APIs are dead OR didn't find timestamps
        # Also refines segment-level timestamps that are too coarse
        # Use segment range as alignment estimate if no index context available
        if time_range is None and not result.context_text and seg_range is not None:
            try:
                from yt_tts.core.align import transcribe_and_locate
                time_range = transcribe_and_locate(
                    video_id, phrase,
                    seg_range.start_ms, seg_range.end_ms,
                    config=config, known_text=None,
                )
                if time_range is not None:
                    timestamp_source = "aligned"
            except Exception as e:
                logger.debug("Segment-to-alignment fallback failed: %s", e)

        if time_range is None and result.context_text:
            timestamp_source = "aligned"
            est = _estimate_from_index_text(phrase, video_id, result, config)

            # Get transcript text near the estimated position for forced alignment.
            # We only pass a ~200 word window, not the full transcript, because
            # CTC forced alignment fails if targets are longer than the audio.
            known_text = None
            all_words = []
            word_idx = 0
            window = 100
            total = 0
            try:
                from yt_tts.core.index import TranscriptIndex

                idx = TranscriptIndex(config.db_path)
                conn = idx._get_conn()
                row = conn.execute(
                    "SELECT text FROM transcripts WHERE video_id = ?",
                    (video_id,),
                ).fetchone()
                if row and est:
                    full_text = row["text"]
                    all_words = full_text.split()
                    total = len(all_words)
                    if total > 0:
                        # Estimate which words fall in the download window
                        # Use the same word-position estimation logic
                        import re as _re

                        cleaned = _re.sub(r"[♪♫🎵🎶]+", "", full_text)
                        clean_words = cleaned.split()
                        # Find phrase position in clean text
                        phrase_lower = phrase.lower()
                        joined = " ".join(w.lower() for w in clean_words)
                        pos = joined.find(phrase_lower)
                        if pos >= 0:
                            word_idx = len(joined[:pos].split())
                        else:
                            word_idx = total // 2
                        # Extract ~200 word window around the phrase
                        window = 100
                        start_w = max(0, word_idx - window)
                        end_w = min(total, word_idx + window)
                        known_text = " ".join(all_words[start_w:end_w])
            except Exception:
                pass

            if est is not None:
                try:
                    from yt_tts.core.align import transcribe_and_locate

                    # Try the estimated window first, then search outward
                    # in both directions. Bidirectional because the estimate
                    # can overshoot (music intros, variable speech rate).
                    shifts = [0, 15000, -15000, 30000, -30000, 60000, -60000, 120000, -120000, 180000, -180000]
                    for shift in shifts:
                        # Skip negative shifts that would go before video start
                        if est.start_ms + shift < 0:
                            continue
                        # Recompute known_text window for each shift
                        # (~2.5 words/sec is typical speech rate)
                        if shift != 0 and all_words:
                            shift_words = int(abs(shift) / 1000 * 2.5)
                            if shift > 0:
                                sw = max(0, word_idx - window + shift_words)
                                ew = min(total, word_idx + window + shift_words)
                            else:
                                sw = max(0, word_idx - window - shift_words)
                                ew = min(total, word_idx + window - shift_words)
                            known_text = " ".join(all_words[sw:ew])
                        time_range = transcribe_and_locate(
                            video_id,
                            phrase,
                            est.start_ms + shift,
                            est.end_ms + shift,
                            config=config,
                            known_text=known_text,
                        )
                        if time_range is not None:
                            break
                        logger.debug(
                            "Whisper didn't find phrase, shifting +%ds", shift // 1000 + 15
                        )
                except Exception as e:
                    logger.warning("Whisper alignment failed for %s: %s", video_id, e)

            # Full-video scan fallback: if all shifts failed, scan a large
            # chunk of the video with ASR (no known_text, pure transcription)
            if time_range is None and est is not None:
                logger.info("All shifts failed for '%s', scanning wider range", phrase)
                try:
                    from yt_tts.core.align import transcribe_and_locate

                    # Scan from video start to 2x the estimated position
                    scan_end = min(est.end_ms * 2, est.start_ms + 300000)
                    time_range = transcribe_and_locate(
                        video_id, phrase,
                        0, scan_end,
                        config=config, known_text=None,
                    )
                    if time_range is not None:
                        logger.info("Found '%s' via full scan at %d-%dms",
                                   phrase, time_range.start_ms, time_range.end_ms)
                except Exception as e:
                    logger.debug("Full scan failed: %s", e)

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

        # Verify the clip actually contains the expected phrase
        # Also trim extra words if present
        passed, trimmed_path = _verify_and_trim_clip(clip_path, phrase)
        if not passed:
            logger.warning(
                "Clip verification failed for '%s' from %s — wrong audio",
                phrase,
                video_id,
            )
            return None
        if trimmed_path is not None:
            clip_path = trimmed_path

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
    match_pos = full_text.find(phrase_lower)
    if match_pos != -1:
        match_end = match_pos + len(phrase_lower)
        # Find which segments the match spans
        pos = 0
        start_seg = None
        end_seg = None
        for seg in segments:
            seg_text = seg.get("text", "")
            seg_start = pos
            seg_end = pos + len(seg_text)
            pos = seg_end + 1  # +1 for space

            if start_seg is None and seg_end > match_pos:
                start_seg = seg
            if seg_end >= match_end:
                end_seg = seg
                break

        if start_seg and end_seg:
            start_ms = int(start_seg["start"] * 1000)
            end_ms = int((end_seg["start"] + end_seg.get("duration", 5)) * 1000)
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
            capture_output=True,
            text=True,
            timeout=30,
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

    cleaned = re.sub(r"[♪♫🎵🎶]+", "", full_text)
    all_words = cleaned.lower().split()
    phrase_words = phrase.lower().split()
    total_words = len(all_words)
    if total_words == 0:
        return None

    # Find the phrase start word index via sliding window
    phrase_start_idx = None
    for i in range(total_words - len(phrase_words) + 1):
        if all_words[i : i + len(phrase_words)] == phrase_words:
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
        prefix = joined[:char_pos]
        phrase_start_idx = len(prefix.split()) if prefix.strip() else 0

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
        phrase,
        start_ms,
        end_ms,
        phrase_start_idx,
        total_words,
        frac * 100,
        video_duration_s,
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
            output_path=None,
            duration_ms=0,
            clips=[],
            missing_words=[],
            exit_code=2,
        )

    if config.max_input_words > 0 and len(words) > config.max_input_words:
        print(
            f"Input too long: {len(words)} words (max {config.max_input_words})",
            file=sys.stderr,
        )
        return SynthesisResult(
            output_path=None,
            duration_ms=0,
            clips=[],
            missing_words=words,
            exit_code=2,
        )

    # Build functions
    try:
        search_fn, multi_search_fn = _build_search_fn(config)
    except Exception as e:
        logger.error("Failed to initialize search: %s", e)
        return SynthesisResult(
            output_path=None,
            duration_ms=0,
            clips=[],
            missing_words=words,
            exit_code=3,
        )

    resolve_fn = _build_resolve_fn(config)

    # Phase 1: Planning (sequential)
    logger.info("Planning chunks for: %s", text)
    try:
        plan = chunk_phrase(text, search_fn, config)
    except Exception as e:
        logger.error("Chunking failed: %s", e)
        return SynthesisResult(
            output_path=None,
            duration_ms=0,
            clips=[],
            missing_words=words,
            exit_code=3,
        )

    # Phase 2: Resolution (parallel)
    logger.info("Resolving %d chunks...", len(plan.chunks))
    plan = resolve_chunks(plan, resolve_fn, config, multi_search_fn=multi_search_fn)

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
                        1 for j in range(last_success_idx + 1, i) if plan.clips[j] is None
                    )
                    gap = config.silence_gap_ms * missing_between if missing_between > 0 else 0
                    clip_gaps.append(gap)
                last_success_idx = i

        final_path = stitch_clips(normalized_paths, clip_gaps, config)

        # Calculate duration
        duration_ms = sum(c.end_ms - c.start_ms for c in successful_clips)
        exit_code = 0 if not plan.missing_words else 1

        if config.output_stdout:
            # Write audio bytes to stdout and discard the temp file
            with open(final_path, "rb") as f:
                sys.stdout.buffer.write(f.read())
            final_path.unlink(missing_ok=True)
            return SynthesisResult(
                output_path=None,
                duration_ms=duration_ms,
                clips=successful_clips,
                missing_words=plan.missing_words,
                exit_code=exit_code,
            )

        output_path = _make_output_path(text, config)

        # Move to output location
        import shutil

        shutil.move(str(final_path), str(output_path))

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
