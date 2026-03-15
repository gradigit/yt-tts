# TODO

## Current Phase: V1 Complete

### Completed
- [x] Phase 0: Project skeleton + risk spikes
  - pyproject.toml with hatchling, all deps, entry point
  - All module files created
  - FTS5 spike validated: contractions work, 10K row search <1.5ms
  - `pip install -e .` works, `yt-tts --help` prints usage
- [x] Phase 1: Caption fetching + timestamp extraction
  - json3 fetching via yt-dlp subprocess
  - youtube-transcript-api fallback for segment-level
  - Word-level timestamp parsing with confidence scores
  - Phrase location via sliding window match
- [x] Phase 2: Clip extraction
  - Stream URL via yt-dlp, format 140 (m4a) preferred
  - ffmpeg re-encode for sub-second accuracy
  - 403/410 retry with fresh URL
  - ClipCache integration
- [x] Phase 3: Stitching pipeline
  - Dual-pass loudnorm normalization (EBU R128)
  - filter_complex concat for <=20 clips
  - Iterative pairwise fallback for >20 clips
  - Crossfade support (acrossfade, tri curves)
  - Silence generation for gaps
- [x] Phase 4: SQLite FTS5 index + search
  - External content mode with dual-insert sync
  - `tokenchars "'"` for contraction support
  - WAL mode, thread-safe connections
  - Post-filter verification, context extraction
  - Channel filter support
- [x] Phase 5: Bumblebee chunking + pipeline orchestrator
  - Greedy longest-match algorithm
  - Parallel resolution via ThreadPoolExecutor (3 workers)
  - InvocationBudget tracking
  - Full pipeline: text → chunks → clips → stitch → output
- [x] Phase 6: Bootstrap + crawl
  - YouTube-Commons Parquet streaming via pyarrow
  - Resumable progress tracking
  - Channel crawling via yt-dlp + transcript-api
  - Starter channels list
- [x] Phase 7: Polish
  - Alignment stubs (stable-ts, whisperx)
  - Cache clear/stats commands
  - All CLI flags wired
  - Legal disclaimer in --help
  - Exit codes 0/1/2/3

### Tests
- 66 unit tests, all passing
- Coverage: chunking, timestamps, index, stitch, pipeline, ratelimit

### V2 Deferrals
- `--align stable-ts` / `--align whisperx` actual implementation
- `--format mp4` video output
- Manticore Search migration
- Non-English, live streams, other platforms
- Web interface
