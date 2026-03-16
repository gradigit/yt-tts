"""Synthesize command: text -> audio."""

import logging
import sys
from pathlib import Path

from yt_tts.config import Config

logger = logging.getLogger(__name__)


def _resolve_channel_filter(voice: str) -> str:
    """Resolve a --voice value to a channel_id suitable for index search.

    Handles YouTube URLs (channel/UCxxx, @handle) by extracting the ID.
    For @handle URLs, also attempts yt-dlp resolution to a UC... channel ID.
    Plain strings are returned as-is.
    """
    # If it doesn't look like a URL, return as-is (already a channel_id)
    if not ("youtube.com" in voice or "youtu.be" in voice or voice.startswith("@")):
        return voice

    from yt_tts.core.crawl import _extract_channel_id

    try:
        extracted = _extract_channel_id(voice)
    except ValueError:
        logger.warning("Could not parse channel from --voice value: %s", voice)
        return voice

    # If we got a UC... channel ID, we're done
    if extracted.startswith("UC"):
        return extracted

    # extracted is a handle (from @handle URL) -- try yt-dlp to get real channel ID
    try:
        import subprocess

        handle_url = f"https://www.youtube.com/@{extracted}"
        proc = subprocess.run(
            ["yt-dlp", "--print", "channel_id", "--playlist-items", "1", handle_url],
            capture_output=True,
            text=True,
            timeout=30,
        )
        resolved = proc.stdout.strip().split("\n")[0].strip()
        if resolved and resolved.startswith("UC"):
            logger.debug("Resolved @%s -> %s", extracted, resolved)
            return resolved
    except Exception as e:
        logger.debug("yt-dlp channel resolution failed: %s", e)

    # Fall back to the extracted handle
    return extracted


def run_synthesize(args) -> int:
    """Run the synthesize pipeline."""
    # Check dependencies before doing anything
    from yt_tts.core.deps import check_all
    from yt_tts.exceptions import DependencyError

    try:
        check_all()
    except DependencyError:
        return 3

    # Resolve --voice URL to channel_id if needed
    voice = getattr(args, "voice", None)
    if voice:
        voice = _resolve_channel_filter(voice)

    config = Config(
        video_url=getattr(args, "video", None),
        channel_filter=voice,
        output_format=getattr(args, "output_format", "mp3"),
        no_cache=getattr(args, "no_cache", False),
        no_crossfade=getattr(args, "no_crossfade", False),
        json_output=getattr(args, "json_output", False),
        verbose=getattr(args, "verbose", False),
        align_method=getattr(args, "align", None),
        cookies_from_browser=getattr(args, "cookies_from_browser", None),
        cookies_file=Path(args.cookies_file) if getattr(args, "cookies_file", None) else None,
        tightness=getattr(args, "tightness", "normal"),
        asr_backend=getattr(args, "asr_backend", "auto"),
        asr_model=getattr(args, "asr_model", "tiny"),
        max_chunk_words=getattr(args, "max_chunk_words", 0),
    )

    # Handle --output
    output = getattr(args, "output", None)
    if output == "-":
        config.output_stdout = True
    elif output:
        config.output_path = Path(output)

    # Alignment stubs
    if config.align_method:
        print(
            f"WARNING: --align {config.align_method} is not yet implemented (V1 stub).",
            file=sys.stderr,
        )

    from yt_tts.core.pipeline import synthesize

    result = synthesize(args.text, config)

    if result.missing_words:
        print(f"Missing words: {', '.join(result.missing_words)}", file=sys.stderr)

    if config.json_output:
        from yt_tts.cli.output import format_json

        print(format_json(result))
    elif result.output_path:
        print(result.output_path)

    return result.exit_code
