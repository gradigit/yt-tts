"""Index management commands."""

import sys

from yt_tts.config import Config


def run_index(args) -> int:
    """Dispatch index subcommands."""
    config = Config(
        verbose=getattr(args, "verbose", False),
        json_output=getattr(args, "json_output", False),
    )

    cmd = getattr(args, "index_command", None)

    if cmd == "init":
        config.bootstrap_subset = getattr(args, "subset", None)
        return _index_init(config)
    elif cmd == "stats":
        return _index_stats(config)
    elif cmd == "search":
        return _index_search(args.query, getattr(args, "limit", 10), config)
    elif cmd == "add-channel":
        return _index_add_channel(args.url, config)
    elif cmd == "add-video":
        return _index_add_video(args.url, config)
    elif cmd == "add-starter":
        return _index_add_starter(config)
    else:
        print("Usage: yt-tts index {init|stats|search|add-channel|add-video|add-starter}", file=sys.stderr)
        return 1


def _index_init(config: Config) -> int:
    from yt_tts.core.bootstrap import bootstrap_index
    bootstrap_index(config)
    return 0


def _index_stats(config: Config) -> int:
    from yt_tts.core.index import TranscriptIndex
    index = TranscriptIndex(config.db_path)
    stats = index.stats()
    if config.json_output:
        import json
        print(json.dumps(stats))
    else:
        print(f"Total transcripts: {stats['total_transcripts']:,}")
        print(f"Total words: {stats['total_words']:,}")
        print(f"Unique channels: {stats['unique_channels']:,}")
        print(f"Database size: {stats['db_size_mb']:.1f} MB")
    return 0


def _index_search(query: str, limit: int, config: Config) -> int:
    from yt_tts.core.index import TranscriptIndex
    index = TranscriptIndex(config.db_path)
    results = index.search(query, limit=limit)
    if not results:
        print("No results found.", file=sys.stderr)
        return 1
    if config.json_output:
        import json
        print(json.dumps([
            {"video_id": r.video_id, "title": r.title, "context": r.context_text}
            for r in results
        ]))
    else:
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r.video_id}] {r.title}")
            print(f"   ...{r.context_text}...")
            print()
    return 0


def _index_add_channel(url: str, config: Config) -> int:
    from yt_tts.core.crawl import crawl_channel
    from yt_tts.core.index import TranscriptIndex
    index = TranscriptIndex(config.db_path)
    count = crawl_channel(url, index, config)
    print(f"Added {count} transcripts from channel.")
    return 0


def _index_add_video(url: str, config: Config) -> int:
    from yt_tts.core.crawl import index_video
    from yt_tts.core.index import TranscriptIndex
    from yt_tts.exceptions import CaptionFetchError
    index = TranscriptIndex(config.db_path)
    try:
        index_video(url, index, config)
    except CaptionFetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print("Video transcript added to index.")
    return 0


def _index_add_starter(config: Config) -> int:
    from yt_tts.core.crawl import add_starter_channels
    from yt_tts.core.index import TranscriptIndex
    index = TranscriptIndex(config.db_path)
    count = add_starter_channels(index, config)
    print(f"Added {count} transcripts from starter channels.")
    return 0
