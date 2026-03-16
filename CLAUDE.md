# yt-tts

YouTube Text-to-Speech — turns any text into audio by finding and stitching YouTube clips where those words are spoken. Like Bumblebee speaking through radio clips. An art project giving agents "the voice of the internet."

## Build Commands
```
pip install -e .              # install in dev mode (includes faster-whisper, curl_cffi)
pip install -e ".[dev]"       # + test deps (pytest, ruff)
pip install -e ".[bootstrap]" # + bootstrap deps (huggingface_hub, pyarrow)
yt-tts "hello world"          # basic usage (requires populated index)
yt-tts --video URL "hello"    # use specific video (no index needed)
yt-tts index init             # download YouTube-Commons + build index
yt-tts index search "phrase"  # search the index
yt-tts batch phrases.txt -o clips/  # batch mode
pytest                        # run tests (116 unit tests)
ruff check src/yt_tts/        # lint
```

## Project Structure
```
yt-tts/
├── src/yt_tts/
│   ├── __init__.py           # version
│   ├── config.py             # Config dataclass
│   ├── types.py              # WordTimestamp, SearchResult, ClipInfo, ChunkPlan, SynthesisResult
│   ├── exceptions.py         # YtTtsError hierarchy
│   ├── core/
│   │   ├── index.py          # TranscriptIndex (SQLite FTS5)
│   │   ├── bootstrap.py      # YouTube-Commons download + ingest
│   │   ├── crawl.py          # add-channel, add-video
│   │   ├── search.py         # High-level search (index + live)
│   │   ├── captions.py       # json3 + transcript-api + page-scrape fetching
│   │   ├── timestamps.py     # json3 parsing, phrase location
│   │   ├── extract.py        # Clip download (stream URL + ffmpeg)
│   │   ├── align.py          # Whisper alignment (faster-whisper, GPU auto-detect)
│   │   ├── stitch.py         # loudnorm + concat + crossfade
│   │   ├── chunk.py          # Bumblebee greedy longest-match
│   │   ├── pipeline.py       # Orchestrator: text → audio
│   │   ├── cache.py          # CaptionCache + ClipCache
│   │   ├── deps.py           # External dependency checking
│   │   └── ratelimit.py      # RateLimiter, CircuitBreaker, InvocationBudget
│   └── cli/
│       ├── app.py            # CLI entry point (manual arg parsing)
│       ├── commands/
│       │   ├── synthesize.py # Single synthesis
│       │   ├── batch.py      # Batch synthesis from file
│       │   ├── index.py      # Index management
│       │   └── cache.py      # Cache management
│       └── output.py         # JSON formatter
├── tests/
│   ├── unit/                 # 116 tests, no network/external tools
│   ├── integration/          # Requires network + ffmpeg
│   └── fixtures/
├── skill/SKILL.md            # Claude Code skill (symlinked to ~/.claude/skills/yt-tts)
├── data/starter_channels.json
└── pyproject.toml
```

## Conventions
- `src/yt_tts/` layout with hatchling build
- Python >=3.11, sync + ThreadPoolExecutor for concurrency
- SQLite FTS5 with `tokenchars "'"` for contraction support
- ffmpeg for audio processing, yt-dlp for YouTube interaction
- faster-whisper (tiny model, GPU auto-detect) for timestamp alignment
- Persistent circuit breaker: skips caption APIs after first 429, goes straight to Whisper
- No arbitrary limits on input length or clip count
- Multilingual support (YouTube-Commons has all languages, Whisper auto-detects)
- Lint: ruff (line-length=100, py311)

## Current State
- 116 unit tests passing, lint clean
- YouTube-Commons bootstrap downloading (597 parquet files → ~22.7M transcripts)
- Full CRT pipeline tested in YTP video project (ytp/)
- Claude Code skill installed at ~/.claude/skills/yt-tts
