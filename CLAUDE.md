# yt-tts

YouTube Text-to-Speech — turns any text into audio by finding and stitching YouTube clips where those words are spoken. Like Bumblebee speaking through radio clips. An art project giving agents "the voice of the internet."

## Build Commands
```
pip install -e .              # install (includes faster-whisper, curl_cffi, torchaudio)
pip install -e ".[dev]"       # + test deps (pytest, ruff)
pip install -e ".[bootstrap]" # + bootstrap deps (huggingface_hub, pyarrow)
yt-tts "hello world"          # synthesize (requires populated index)
yt-tts --video URL "hello"    # use specific video (no index needed)
yt-tts index init             # download YouTube-Commons (3.15M transcripts)
yt-tts index search "phrase"  # search the index
yt-tts batch phrases.txt -o clips/  # batch mode
pytest                        # run tests (116 unit tests)
ruff check src/yt_tts/        # lint
```

## Project Structure
```
yt-tts/
├── src/yt_tts/
│   ├── config.py             # Config dataclass (all settings)
│   ├── types.py              # WordTimestamp, SearchResult, ClipInfo, ChunkPlan, SynthesisResult
│   ├── exceptions.py         # YtTtsError hierarchy
│   ├── core/
│   │   ├── asr.py            # Cross-platform ASR backend (CUDA/MLX/CPU) + CTC forced alignment
│   │   ├── align.py          # Download audio + align/transcribe + locate phrase
│   │   ├── pipeline.py       # Orchestrator: search → align → extract → verify → stitch
│   │   ├── index.py          # TranscriptIndex (SQLite FTS5, 3.15M transcripts)
│   │   ├── search.py         # FTS5 search + multi-candidate retrieval
│   │   ├── chunk.py          # Bumblebee greedy longest-match + verify-retry resolution
│   │   ├── extract.py        # Clip download (yt-dlp stream URL + ffmpeg) + tightness control
│   │   ├── stitch.py         # Gentle loudnorm (±6 LU window) + concat + crossfade
│   │   ├── bootstrap.py      # YouTube-Commons parquet download + ingest (597 files)
│   │   ├── captions.py       # json3 + transcript-api + page-scrape fetching
│   │   ├── timestamps.py     # json3 parsing, phrase location
│   │   ├── crawl.py          # add-channel, add-video
│   │   ├── cache.py          # CaptionCache + ClipCache
│   │   ├── deps.py           # ffmpeg/yt-dlp dependency checking
│   │   └── ratelimit.py      # RateLimiter, CircuitBreaker, InvocationBudget
│   └── cli/
│       ├── app.py            # CLI entry point (manual arg parsing)
│       ├── commands/          # synthesize, batch, index, cache
│       └── output.py         # JSON formatter
├── tests/unit/               # 116 tests (align, cache, chunk, cli, index, pipeline, ratelimit, stitch, timestamps)
├── spikes/                   # Validation spikes (FTS5, json3, alignment benchmark, phoneme stitching)
├── architect/                # Research findings, alternative sources reference
├── skill/SKILL.md            # Claude Code skill (symlinked to ~/.claude/skills/yt-tts)
├── ytp/                      # YTP video project (renderer, visuals, build scripts)
└── pyproject.toml            # MIT license, hatchling build
```

## Pipeline Architecture
```
search (FTS5, multi-candidate) → estimate position (word-index ratio)
  → download audio (yt-dlp stream URL) → CTC forced alignment (known text → timestamps)
  → extract clip (ffmpeg) → verify with ASR (reject misaligned) → retry next candidate if failed
  → stitch (gentle loudnorm + crossfade) → output MP3/WAV
```

## Key Design Decisions
- **CTC forced alignment over ASR**: We already know the text (from the index), so we skip recognition entirely. ctc_forced_aligner + MMS_FA gives ~30ms boundary accuracy vs ~200ms for Whisper.
- **Verify-then-retry**: After extracting a clip, ASR-verify it matches the expected phrase. If not, try the next search result (up to 5 candidates).
- **Gentle normalization**: ±6 LU window preserves natural volume variation between speakers. Only extreme clips get adjusted. alimiter prevents clipping.
- **Persistent circuit breaker**: After one YouTube 429, skips all caption APIs for 1 hour and goes straight to local alignment.
- **Cross-platform ASR** (asr.py): CUDA (faster-whisper) → MLX (parakeet-mlx/mlx-whisper) → CPU (faster-whisper). Auto-detects at runtime.

## Conventions
- `src/yt_tts/` layout, hatchling build, Python >=3.11
- SQLite FTS5 with `tokenchars "'"` for contraction support (WAL mode, thread-safe)
- No arbitrary limits on input length or clip count
- Lint: ruff (line-length=100, select E,F,W,I)
- Tests: pytest, 116 unit tests, all passing

## Current State (v0.2.0)
- YouTube-Commons bootstrap complete: 3,156,663 transcripts, 58GB database
- 10/10 stress test phrases pass ASR verification
- Phoneme stitching POC: word-level works (4/5 exact), phoneme-level needs PSOLA/vocoder (V2)
- GitHub: https://github.com/gradigit/yt-tts
