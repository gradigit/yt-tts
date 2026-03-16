# TODO

## Next Up
- [ ] Phoneme-level stitching: PSOLA/WORLD vocoder for sub-word splicing (V2)
- [ ] Improve long-video position estimation (word-index ratio misses on 5+ min videos)
- [ ] Add GitHub Actions CI (tests + lint)
- [ ] Add CONTRIBUTING.md

## Backlog
- [ ] Batch inference: process multiple clips simultaneously
- [ ] Snap-to-silence / snap-to-zero-crossing at word boundaries
- [ ] Explore alternative datasets (People's Speech, VoxPopuli) for diversity
- [ ] Podcast RSS crawling pipeline (RSS → download → ASR → index)

## Completed
- [x] V1 implementation (Phases 0-7)
- [x] Whisper alignment (bypass YouTube caption API)
- [x] CTC forced alignment (ctc_forced_aligner + MMS_FA, ~30ms accuracy)
- [x] Verify-then-retry pipeline (ASR verification, up to 5 candidates)
- [x] Cookie support (--cookies, --cookies-from-browser)
- [x] Persistent circuit breaker
- [x] Cross-platform ASR backend (CUDA/MLX/CPU auto-detection)
- [x] YouTube-Commons bootstrap (all 597 parquet files, 3,156,663 transcripts)
- [x] Gentle loudness normalization (±6 LU window + alimiter)
- [x] Batch mode (yt-tts batch phrases.txt -o clips/)
- [x] Tightness control (tight/normal/loose/ms)
- [x] 116 unit tests passing
- [x] Ruff linting clean
- [x] README.md with full documentation
- [x] Claude Code skill created
- [x] End-to-end synthesis verified (10/10 stress test phrases)
- [x] MIT license
- [x] Version bump to 0.2.0
