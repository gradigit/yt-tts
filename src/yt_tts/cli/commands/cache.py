"""Cache management commands."""

import sys

from yt_tts.config import Config


def run_cache(args) -> int:
    """Dispatch cache subcommands."""
    config = Config(
        verbose=getattr(args, "verbose", False),
        json_output=getattr(args, "json_output", False),
    )

    cmd = getattr(args, "cache_command", None)

    if cmd == "clear":
        return _cache_clear(config)
    elif cmd == "stats":
        return _cache_stats(config)
    else:
        print("Usage: yt-tts cache {clear|stats}", file=sys.stderr)
        return 1


def _cache_clear(config: Config) -> int:
    from yt_tts.core.cache import clear_all_caches

    cleared = clear_all_caches(config.cache_dir)
    print(f"Cleared {cleared} cached files.")
    return 0


def _cache_stats(config: Config) -> int:
    from yt_tts.core.cache import get_cache_stats

    stats = get_cache_stats(config.cache_dir)
    if config.json_output:
        import json

        print(json.dumps(stats))
    else:
        print(f"Captions: {stats['caption_count']} files ({stats['caption_size_mb']:.1f} MB)")
        print(f"Clips: {stats['clip_count']} files ({stats['clip_size_mb']:.1f} MB)")
        print(f"Total: {stats['total_size_mb']:.1f} MB")
    return 0
