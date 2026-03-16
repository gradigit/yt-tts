"""CLI entry point for yt-tts."""

import logging
import signal
import sys
import tempfile
from pathlib import Path

from yt_tts import __version__

LEGAL_DISCLAIMER = (
    "DISCLAIMER: This tool downloads short audio clips from YouTube for "
    "transformative remix purposes. Users are responsible for ensuring their "
    "use complies with YouTube's Terms of Service and applicable copyright law. "
    "This is an art/research project — not a piracy tool."
)


def _cleanup_temp_files(signum, frame):
    """Clean up temp files on Ctrl+C."""
    # Clean yt-tts temp files
    tmp = Path(tempfile.gettempdir())
    for pattern in (
        "yt-tts-clip-*",
        "yt-tts-norm-*",
        "yt-tts-out-*",
        "yt-tts-stitch-*",
        "yt-tts-silence-*",
        "yt-tts-pair-*",
    ):
        for p in tmp.glob(pattern):
            try:
                if p.is_dir():
                    import shutil

                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
            except OSError:
                pass
    print("\nInterrupted.", file=sys.stderr)
    sys.exit(130)


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGINT, _cleanup_temp_files)

    args = argv if argv is not None else sys.argv[1:]

    # Detect subcommand vs synthesis mode.
    # If first arg is a known subcommand, route to it.
    # Otherwise, treat everything as synthesis.
    subcommands = {"index", "cache", "batch"}
    command = args[0] if args else None

    if command == "--help" or command == "-h" or not args:
        _print_help()
        return 0
    if command == "--version":
        print(f"yt-tts {__version__}")
        return 0

    if command in subcommands:
        return _dispatch_subcommand(args)
    else:
        return _dispatch_synthesize(args)


def _print_help():
    print(f"""yt-tts {__version__} — Turn text into audio by stitching YouTube clips.

Usage:
  yt-tts "hello world"                    Synthesize text to audio
  yt-tts --video URL "hello world"        Use a specific YouTube video
  yt-tts --voice CHANNEL "hello world"    Constrain to a channel
  yt-tts index init [--subset N]          Build transcript index
  yt-tts index search "phrase"            Search the index
  yt-tts index add-video URL              Add a video to index
  yt-tts index add-channel URL            Add channel to index
  yt-tts index stats                      Show index statistics
  yt-tts batch phrases.txt -o clips/       Batch generate clips
  yt-tts cache stats                      Show cache statistics
  yt-tts cache clear                      Clear all caches

Synthesis options:
  --video URL          Use a specific video (bypass index)
  --voice CHANNEL      Constrain clips to a channel
  --output PATH, -o    Output file (default: auto-named, '-' for stdout)
  --format {{mp3,wav}}   Output format (default: mp3)
  --tightness MODE     Clip tightness: tight, normal (default), loose, or ms value
  --asr-backend NAME   ASR backend: auto (default), faster-whisper, mlx
  --asr-model SIZE     ASR model: tiny (default), base, small, medium, large-v3
  --no-cache           Disable caching
  --no-crossfade       Disable crossfade between clips
  --cookies-from-browser BROWSER  Use cookies from browser (chrome, firefox, etc.)
  --cookies FILE       Use Netscape-format cookies file
  --json               Output structured JSON
  --verbose            Debug logging to stderr
  --version            Show version
  --help, -h           Show this help

{LEGAL_DISCLAIMER}""")


def _dispatch_subcommand(args: list[str]) -> int:
    command = args[0]
    rest = args[1:]

    if command == "index":
        return _dispatch_index(rest)
    elif command == "cache":
        return _dispatch_cache(rest)
    elif command == "batch":
        return _dispatch_batch(rest)
    return 1


def _dispatch_index(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print("""Usage: yt-tts index {init,stats,search,add-channel,add-video,add-starter}

  init [--subset N]    Download YouTube-Commons and build index
  stats                Show index statistics
  search PHRASE        Search the transcript index
  add-channel URL      Add a YouTube channel's transcripts
  add-video URL        Add a single video's transcript
  add-starter          Add curated starter channels""")
        return 0

    subcmd = args[0]
    rest = args[1:]

    from yt_tts.cli.commands.index import run_index

    class Args:
        pass

    a = Args()
    a.index_command = subcmd
    a.verbose = "--verbose" in rest
    a.json_output = "--json" in rest

    if subcmd == "init":
        a.subset = None
        for i, arg in enumerate(rest):
            if arg == "--subset" and i + 1 < len(rest):
                a.subset = int(rest[i + 1])
    elif subcmd == "search":
        non_flag = [x for x in rest if not x.startswith("--")]
        if not non_flag:
            print("Usage: yt-tts index search PHRASE [--limit N]", file=sys.stderr)
            return 1
        a.query = non_flag[0]
        a.limit = 10
        for i, arg in enumerate(rest):
            if arg == "--limit" and i + 1 < len(rest):
                a.limit = int(rest[i + 1])
    elif subcmd in ("add-channel", "add-video"):
        non_flag = [x for x in rest if not x.startswith("--")]
        if not non_flag:
            print(f"Usage: yt-tts index {subcmd} URL", file=sys.stderr)
            return 1
        a.url = non_flag[0]

    return run_index(a)


def _dispatch_cache(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print("""Usage: yt-tts cache {clear,stats}

  clear    Delete all cached clips and captions
  stats    Show cache statistics""")
        return 0

    subcmd = args[0]
    rest = args[1:]

    from yt_tts.cli.commands.cache import run_cache

    class Args:
        pass

    a = Args()
    a.cache_command = subcmd
    a.verbose = "--verbose" in rest
    a.json_output = "--json" in rest

    return run_cache(a)


def _dispatch_batch(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print("""Usage: yt-tts batch INPUT_FILE -o OUTPUT_DIR [options]

  Generate audio clips for each line in the input file.
  Lines starting with # are skipped.

Options:
  -o DIR               Output directory (required)
  --format {mp3,wav}   Output format (default: mp3)
  --no-cache           Disable caching
  --json               Output results as JSON
  --cookies FILE       YouTube cookies file
  --verbose            Debug logging""")
        return 0

    from yt_tts.cli.commands.batch import run_batch

    class Args:
        pass

    a = Args()
    a.input_file = None
    a.output_dir = None
    a.output_format = "mp3"
    a.no_cache = False
    a.json_output = False
    a.verbose = False
    a.cookies_from_browser = None
    a.cookies_file = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-o", "--output") and i + 1 < len(args):
            a.output_dir = args[i + 1]
            i += 2
        elif arg == "--format" and i + 1 < len(args):
            a.output_format = args[i + 1]
            i += 2
        elif arg == "--cookies" and i + 1 < len(args):
            a.cookies_file = args[i + 1]
            i += 2
        elif arg == "--cookies-from-browser" and i + 1 < len(args):
            a.cookies_from_browser = args[i + 1]
            i += 2
        elif arg == "--no-cache":
            a.no_cache = True
            i += 1
        elif arg == "--json":
            a.json_output = True
            i += 1
        elif arg == "--verbose":
            a.verbose = True
            i += 1
        elif not arg.startswith("-") and a.input_file is None:
            a.input_file = arg
            i += 1
        else:
            i += 1

    if not a.input_file:
        print("Error: input file required", file=sys.stderr)
        return 1
    if not a.output_dir:
        print("Error: -o output directory required", file=sys.stderr)
        return 1

    if a.verbose:
        logging.basicConfig(
            level=logging.WARNING, format="%(name)s: %(message)s", stream=sys.stderr
        )
        logging.getLogger("yt_tts").setLevel(logging.DEBUG)

    return run_batch(a)


def _dispatch_synthesize(args: list[str]) -> int:
    # Parse synthesis args manually for full control
    text_parts = []
    video = None
    voice = None
    output = None
    output_format = "mp3"
    no_cache = False
    no_crossfade = False
    align = None
    json_output = False
    verbose = False
    cookies_from_browser = None
    cookies_file = None
    tightness = "normal"
    asr_backend = "auto"
    asr_model = "tiny"

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--video" and i + 1 < len(args):
            video = args[i + 1]
            i += 2
        elif arg == "--voice" and i + 1 < len(args):
            voice = args[i + 1]
            i += 2
        elif arg in ("--output", "-o") and i + 1 < len(args):
            output = args[i + 1]
            i += 2
        elif arg == "--format" and i + 1 < len(args):
            output_format = args[i + 1]
            i += 2
        elif arg == "--align" and i + 1 < len(args):
            align = args[i + 1]
            i += 2
        elif arg == "--tightness" and i + 1 < len(args):
            v = args[i + 1]
            tightness = int(v) if v.isdigit() else v
            i += 2
        elif arg == "--asr-backend" and i + 1 < len(args):
            asr_backend = args[i + 1]
            i += 2
        elif arg == "--asr-model" and i + 1 < len(args):
            asr_model = args[i + 1]
            i += 2
        elif arg == "--cookies-from-browser" and i + 1 < len(args):
            cookies_from_browser = args[i + 1]
            i += 2
        elif arg == "--cookies" and i + 1 < len(args):
            cookies_file = args[i + 1]
            i += 2
        elif arg == "--no-cache":
            no_cache = True
            i += 1
        elif arg == "--no-crossfade":
            no_crossfade = True
            i += 1
        elif arg == "--json":
            json_output = True
            i += 1
        elif arg == "--verbose":
            verbose = True
            i += 1
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}", file=sys.stderr)
            return 1
        else:
            text_parts.append(arg)
            i += 1

    text = " ".join(text_parts)
    if not text:
        print("Error: no text provided.", file=sys.stderr)
        print('Usage: yt-tts [options] "text to synthesize"', file=sys.stderr)
        return 1

    if verbose:
        logging.basicConfig(
            level=logging.WARNING, format="%(name)s: %(message)s", stream=sys.stderr
        )
        logging.getLogger("yt_tts").setLevel(logging.DEBUG)

    class Args:
        pass

    a = Args()
    a.text = text
    a.video = video
    a.voice = voice
    a.output = output
    a.output_format = output_format
    a.no_cache = no_cache
    a.no_crossfade = no_crossfade
    a.align = align
    a.json_output = json_output
    a.verbose = verbose
    a.cookies_from_browser = cookies_from_browser
    a.cookies_file = cookies_file
    a.tightness = tightness
    a.asr_backend = asr_backend
    a.asr_model = asr_model

    from yt_tts.cli.commands.synthesize import run_synthesize

    return run_synthesize(a)


if __name__ == "__main__":
    sys.exit(main())
