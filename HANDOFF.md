# Handoff — yt-tts

## Session Summary (2026-03-16)

Built yt-tts from scratch — a CLI tool that turns text into audio by stitching YouTube clips where those words are spoken. Bumblebee-style "voice of the internet."

### What was built
- Full synthesis pipeline: FTS5 search → CTC forced alignment → ffmpeg extraction → ASR verification → retry → stitch
- YouTube-Commons dataset indexed: 3,156,663 transcripts, 58GB SQLite FTS5 database
- Cross-platform ASR backend: CUDA (faster-whisper) / MLX (parakeet-mlx) / CPU auto-detection
- CLI with subcommands: synthesize, batch, index, cache
- 116 unit tests, lint clean, MIT license
- Claude Code skill at `skill/SKILL.md`
- YTP video project: "The Token's Dilemma" — NGE-inspired CRT effects, datamosh, generative visuals

### Key Architecture
Pipeline: `search → estimate → download → CTC align (known text) → extract → verify → retry next candidate → stitch`

The critical insight: since we already know the transcript text (from the index), we skip ASR entirely and use CTC forced alignment (ctc_forced_aligner + MMS_FA). This gives ~30ms word boundary accuracy vs ~200ms for Whisper, with zero hallucination risk.

### What works
- 10/10 stress test phrases pass ASR verification
- Verification catches misaligned clips and retries with alternate search results
- Gentle volume normalization (±6 LU window, preserves natural variation)
- Batch mode for generating many clips efficiently
- Tightness control (tight/normal/loose/ms)

### What doesn't work yet
- Phoneme-level stitching: word-level is reliable (4/5 exact), phoneme splicing creates "sh" artifacts. Needs PSOLA/WORLD vocoder (V2)
- Some long-video estimation is still off — the word-position estimation can miss by minutes on 5+ minute videos
- `torchaudio.functional.forced_align` is deprecated in 2.8, removed in 2.9 — needs migration

### Unfinished / Deferred
- People's Speech dataset: 2.12 TB, utterance-level only — too large for now
- YODAS dataset: ~17 TB — way too large
- Podcast RSS crawling: needs full ASR pipeline per episode
- YouTube channel RSS monitoring: tested, works but intermittent 404s
- Social media sources (TikTok, Twitch): ToS concerns
- Residential proxy crawling for fresh YouTube content ($240-600/month)

### Files of note
- `src/yt_tts/core/asr.py` — cross-platform ASR + CTC forced alignment
- `src/yt_tts/core/pipeline.py` — main orchestrator with verify-retry
- `architect/research-findings.md` — synthesized research on ASR, data sources, prior art
- `architect/alternative-sources.md` — reference for future data expansion
- `spikes/spike_alignment_benchmark.py` — WhisperX vs CTC-forced-aligner benchmark
- `spikes/spike_phoneme_stitching.py` — phoneme stitching POC results

### GitHub
https://github.com/gradigit/yt-tts
