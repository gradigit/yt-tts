# Forge State
## Current Stage: complete (Mode 1)
## Mode: 1
## Depth: full
## Categories Asked: [1, 2, 3, 4, 5, 8, 11, 12]
## Categories Skipped: [6 — early-stage, 7 — no auth/PII, 9 — define later, 10 — CLI is local]
## Categories Remaining: []
## Key Decisions:
- Art project, not precision TTS — clip-stitching aesthetic is the vibe ("Bumblebee" / "voice of the internet")
- Own index over Filmot — Filmot API is not open-access, CAPTCHA-gated, crawling suspended June 2024
- Bootstrap with YouTube-Commons (22.7M transcripts from HuggingFace)
- SQLite FTS5 to start, Manticore Search as upgrade path
- Bumblebee chunking: greedy longest-match phrase splits (not word-by-word)
- Starter channel list for "voice of the internet" beyond CC-BY content
- Monorepo: core lib + CLI wrapper + web wrapper (V1 = core + CLI only)
- Accuracy over speed — exact phrase match is top priority
- json3 word timestamps as default alignment (no GPU needed)
- stable-ts as opt-in alignment, WhisperX for max precision
- Output: MP4 or audio-only (user choice)
- Agent interface: CLI subprocess, --json flag
- Production quality from start
- English only for V1
- Open source, YouTube only
- Cache everything (index, transcripts, clips)
