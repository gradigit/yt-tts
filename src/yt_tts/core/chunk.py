"""Bumblebee greedy longest-match chunking."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from yt_tts.config import Config
from yt_tts.types import ChunkPlan, ClipInfo, SearchResult

logger = logging.getLogger(__name__)


def _normalize_word(word: str) -> str:
    """Normalize a word for matching: lowercase, strip surrounding punctuation
    but preserve internal apostrophes for contractions."""
    word = word.lower()
    # Strip leading punctuation
    word = re.sub(r"^[^\w']+", "", word)
    # Strip trailing punctuation
    word = re.sub(r"[^\w']+$", "", word)
    return word


def _tokenize(text: str) -> list[str]:
    """Split text into words, preserving contractions."""
    return text.split()


def chunk_phrase(
    text: str,
    search_fn: Callable[[str], SearchResult | None],
    config: Config,
) -> ChunkPlan:
    """Greedy longest-match chunking of input text.

    Phase 1 (Planning): Sequential left-to-right greedy matching.
    Tries the longest possible phrase first, then shrinks.

    Args:
        text: Input text to chunk.
        search_fn: Function that searches for a phrase and returns SearchResult or None.
        config: Configuration.

    Returns:
        ChunkPlan with chunks, search_results, and missing_words populated.
        clips will be None (filled in during resolution phase).
    """
    words = _tokenize(text)
    if not words:
        return ChunkPlan()

    if config.max_input_words > 0 and len(words) > config.max_input_words:
        raise ValueError(f"Input too long: {len(words)} words (max {config.max_input_words})")

    chunks: list[str] = []
    search_results: list[SearchResult | None] = []
    missing_words: list[str] = []

    # Cache search results within this invocation
    search_cache: dict[str, SearchResult | None] = {}

    i = 0
    while i < len(words):
        matched = False

        # Try longest phrase first, shrinking down
        max_end = len(words) if config.max_chunk_words <= 0 else min(i + config.max_chunk_words, len(words))
        for end in range(max_end, i, -1):
            phrase = " ".join(words[i:end])
            normalized = " ".join(_normalize_word(w) for w in words[i:end])

            if normalized in search_cache:
                result = search_cache[normalized]
            else:
                try:
                    result = search_fn(normalized)
                except Exception as e:
                    logger.warning("Search failed for '%s': %s", normalized, e)
                    result = None
                search_cache[normalized] = result

            if result is not None:
                chunks.append(phrase)
                search_results.append(result)
                i = end
                matched = True
                logger.debug("Matched chunk: '%s' -> video %s", phrase, result.video_id)
                break

        if not matched:
            # Single word with no match
            missing_word = words[i]
            chunks.append(missing_word)
            search_results.append(None)
            missing_words.append(missing_word)
            logger.debug("No match for word: '%s'", missing_word)
            i += 1

    # Enforce max clips limit (0 = no limit)
    if config.max_clips > 0 and len(chunks) > config.max_clips:
        logger.warning("Too many chunks (%d), truncating to %d", len(chunks), config.max_clips)
        extra = chunks[config.max_clips :]
        chunks = chunks[: config.max_clips]
        search_results = search_results[: config.max_clips]
        for c in extra:
            missing_words.extend(_tokenize(c))

    return ChunkPlan(
        chunks=chunks,
        clips=[None] * len(chunks),  # filled during resolution
        missing_words=missing_words,
        search_results=search_results,
    )


def resolve_chunks(
    plan: ChunkPlan,
    resolve_fn: Callable[[str, SearchResult], ClipInfo | None],
    config: Config,
    multi_search_fn: Callable[[str], list[SearchResult]] | None = None,
) -> ChunkPlan:
    """Resolve chunks to clips in parallel.

    If a clip fails to resolve (wrong audio, age-restricted, alignment miss),
    tries the next search result from multi_search_fn (up to 5 candidates).

    Phase 2 (Resolution): Parallel clip extraction for matched chunks.

    Args:
        plan: ChunkPlan from chunk_phrase with search_results populated.
        resolve_fn: Function that takes (phrase, search_result) and returns ClipInfo or None.
        config: Configuration.

    Returns:
        Updated ChunkPlan with clips populated.
    """
    clips: list[ClipInfo | None] = [None] * len(plan.chunks)
    missing_words = list(plan.missing_words)

    # Collect indices that have search results (need resolution)
    to_resolve = [
        (i, plan.chunks[i], plan.search_results[i])
        for i in range(len(plan.chunks))
        if plan.search_results[i] is not None
    ]

    if not to_resolve:
        return ChunkPlan(
            chunks=plan.chunks,
            clips=clips,
            missing_words=missing_words,
            search_results=plan.search_results,
        )

    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        future_to_idx = {}
        for idx, phrase, result in to_resolve:
            future = executor.submit(resolve_fn, phrase, result)
            future_to_idx[future] = (idx, phrase)

        for future in as_completed(future_to_idx):
            idx, phrase = future_to_idx[future]
            try:
                clip = future.result(timeout=config.chunk_resolve_timeout_s)
                clips[idx] = clip
            except Exception as e:
                logger.warning("Resolution failed for '%s': %s", phrase, e)

    # Retry failed chunks with alternate search results (sequential)
    failed_indices = [
        (i, plan.chunks[i])
        for i in range(len(plan.chunks))
        if clips[i] is None and plan.search_results[i] is not None
    ]

    if failed_indices and multi_search_fn:
        for idx, phrase in failed_indices:
            candidates = multi_search_fn(phrase)
            # Skip the first result (already tried)
            tried_ids = {plan.search_results[idx].video_id}
            resolved = False
            for candidate in candidates:
                if candidate.video_id in tried_ids:
                    continue
                tried_ids.add(candidate.video_id)
                logger.info("Retrying '%s' with video %s", phrase, candidate.video_id)
                try:
                    clip = resolve_fn(phrase, candidate)
                    if clip is not None:
                        clips[idx] = clip
                        resolved = True
                        break
                except Exception:
                    continue
            if not resolved:
                missing_words.extend(_tokenize(phrase))
                logger.warning(
                    "Failed to resolve chunk '%s' after %d candidates", phrase, len(tried_ids)
                )
    else:
        # No multi-search available — mark all failed as missing
        for i in range(len(plan.chunks)):
            if clips[i] is None and plan.search_results[i] is not None:
                missing_words.extend(_tokenize(plan.chunks[i]))
                logger.warning("Failed to resolve chunk: '%s'", plan.chunks[i])

    return ChunkPlan(
        chunks=plan.chunks,
        clips=clips,
        missing_words=missing_words,
        search_results=plan.search_results,
    )
