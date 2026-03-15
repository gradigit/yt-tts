"""Synthesize command: text -> audio."""

import sys
from pathlib import Path

from yt_tts.config import Config


def run_synthesize(args) -> int:
    """Run the synthesize pipeline."""
    # Check dependencies before doing anything
    from yt_tts.core.deps import check_all
    from yt_tts.exceptions import DependencyError
    try:
        check_all()
    except DependencyError:
        return 3

    config = Config(
        video_url=getattr(args, "video", None),
        channel_filter=getattr(args, "voice", None),
        output_format=getattr(args, "output_format", "mp3"),
        no_cache=getattr(args, "no_cache", False),
        no_crossfade=getattr(args, "no_crossfade", False),
        json_output=getattr(args, "json_output", False),
        verbose=getattr(args, "verbose", False),
        align_method=getattr(args, "align", None),
        cookies_from_browser=getattr(args, "cookies_from_browser", None),
        cookies_file=Path(args.cookies_file) if getattr(args, "cookies_file", None) else None,
    )

    # Handle --output
    output = getattr(args, "output", None)
    if output == "-":
        config.output_stdout = True
    elif output:
        config.output_path = Path(output)

    # Alignment stubs
    if config.align_method:
        print(f"WARNING: --align {config.align_method} is not yet implemented (V1 stub).", file=sys.stderr)

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
