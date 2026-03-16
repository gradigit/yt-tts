# TODO

## Milestone 1: Fix All Bugs + Dependencies
- [ ] Add faster-whisper, curl_cffi to pyproject.toml dependencies
- [ ] Fix --voice flag (resolve channel URL → channel_id)
- [ ] Wire --output - (stdout binary output)
- [ ] Fix --verbose to filter to yt_tts.* loggers only
- [ ] Fix test_too_long_input (limit was removed, test still expects it)
- [ ] Fix all other stale tests
- [ ] Run full test suite, all green

## Milestone 2: Performance Optimization
- [ ] Add batch mode: yt-tts batch phrases.txt -o clips/
- [ ] Skip caption APIs immediately when circuit breaker is tripped (no first-call penalty)
- [ ] Improve Whisper estimation: smarter window sizing, better ♪ handling
- [ ] Add progress bar (tqdm) during synthesis
- [ ] Optimize Whisper: reuse model across batch, tiny model, GPU auto-detect
- [ ] Profile and eliminate bottlenecks

## Milestone 3: Full Dataset Bootstrap
- [ ] Download all 597 YouTube-Commons parquet files
- [ ] Verify resumability (interrupt + restart)
- [ ] Index stats after full load
- [ ] Test search quality at scale

## Milestone 4: Open Source Prep
- [ ] README.md with installation, usage, architecture, examples
- [ ] LICENSE file (choose license)
- [ ] Clean up spikes/ and ytp/ from repo (or .gitignore them)
- [ ] Add ruff linting config + fix all lint issues
- [ ] Add GitHub Actions CI (tests + lint)
- [ ] Add CONTRIBUTING.md
- [ ] Version bump to 0.2.0
- [ ] Update CLAUDE.md to reflect final state
- [ ] Final git commit + tag

## Completed
- [x] V1 implementation (Phases 0-7)
- [x] Whisper alignment (bypass YouTube caption API)
- [x] Cookie support (--cookies, --cookies-from-browser)
- [x] Persistent circuit breaker
- [x] GPU auto-detection for Whisper
- [x] YouTube-Commons bootstrap (1 parquet file, 27K transcripts)
- [x] 68 unit tests passing
- [x] End-to-end synthesis verified
- [x] Claude Code skill created
