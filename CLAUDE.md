# yt-tts

YouTube Text-to-Speech — turns any text into audio by finding and stitching YouTube clips where those words are spoken. Like Bumblebee speaking through radio clips. An art project giving agents "the voice of the internet."

## Build Commands
```
pip install -e .              # install in dev mode
pip install -e ".[dev]"       # install with test deps
pip install -e ".[bootstrap]" # install with bootstrap deps (huggingface_hub, pyarrow)
yt-tts "hello world"          # basic usage (requires populated index)
yt-tts --video URL "hello"    # use specific video (no index needed)
yt-tts index init             # download YouTube-Commons + build index
yt-tts index search "phrase"  # search the index
pytest                        # run tests (66 unit tests)
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
│   │   ├── captions.py       # json3 + transcript-api fetching
│   │   ├── timestamps.py     # json3 parsing, phrase location
│   │   ├── extract.py        # Clip download (stream URL + ffmpeg)
│   │   ├── align.py          # V1 stubs for stable-ts/whisperx
│   │   ├── stitch.py         # loudnorm + concat + crossfade
│   │   ├── chunk.py          # Bumblebee greedy longest-match
│   │   ├── pipeline.py       # Orchestrator: text → audio
│   │   ├── cache.py          # CaptionCache + ClipCache
│   │   └── ratelimit.py      # RateLimiter, CircuitBreaker, InvocationBudget
│   └── cli/
│       ├── app.py            # argparse entry point
│       ├── commands/
│       │   ├── synthesize.py
│       │   ├── index.py
│       │   └── cache.py
│       └── output.py         # JSON formatter
├── tests/
│   ├── unit/                 # 66 tests, no network/external tools
│   ├── integration/          # Requires network + ffmpeg
│   └── fixtures/
├── spikes/                   # Validation spikes (json3, partial download, FTS5)
├── data/starter_channels.json
├── architect/                # Planning artifacts (reference only)
└── pyproject.toml
```

## Conventions
- `src/yt_tts/` layout with hatchling build
- Python >=3.11, sync + ThreadPoolExecutor for concurrency
- SQLite FTS5 with `tokenchars "'"` for contraction support
- ffmpeg for audio processing, yt-dlp for YouTube interaction
- Functional core, classes for state (TranscriptIndex, caches, rate limiters)
- Dataclasses as result types, exceptions only for unexpected failures
- English only for V1

## Current Phase
Phase: V1 implementation complete (Phases 0-7)

## Phase Progress
- [x] Phase 0: Skeleton + spikes (pyproject.toml, all modules, FTS5 spike validated)
- [x] Phase 1: Caption fetching + timestamp extraction
- [x] Phase 2: Clip extraction
- [x] Phase 3: Stitching pipeline
- [x] Phase 4: SQLite FTS5 index + search
- [x] Phase 5: Bumblebee chunking + pipeline orchestrator
- [x] Phase 6: YouTube-Commons bootstrap + incremental crawling
- [x] Phase 7: Polish (alignment stubs, cache subcommands, CLI flags, legal disclaimer)
