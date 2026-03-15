# Forging Plans Transcript
## Project Context: new project — yt-tts
## Raw Input
I want to make a CLI tool + web tool where user types in any text, and it searches YouTube for a clip that says those exact words. Research the possibility of this. Let's start planning this out and ironing out this idea.
---

## Questionnaire

### Category 1: Core Vision

**What exactly is this?**
Both a clip finder AND a stitcher. Find YouTube clips where specific words/phrases are spoken, AND stitch multiple clips together to construct arbitrary sentences. Also meant to be used by AI agents — agent-first design. Name: yt-tts (YouTube Text-to-Speech).

**Inspiration:** yoink.media (paid Ableton plugin for finding samples). Wanted that but for YouTube, usable as TTS by agents.

**Who is the primary audience?**
All — content creators, developers, general public. Key audience: AI agents that need TTS-like output from real YouTube clips.

**What does success look like?**
Accuracy first — finding the exact words spoken, even if it takes time. Precision over speed.

**Single most important thing?**
Exact phrase match — find clips where the EXACT phrase is spoken, with precise timestamp extraction.

### Category 2: Requirements & Constraints

**Functional requirements:**
Search YouTube captions for exact phrases, extract video clips at timestamps, and stitch multiple clips to form sentences.

**Explicit exclusions:**
- No full video downloads (only clip segments)
- No user accounts / auth / user data storage
- No monetization / ads / paid tiers

**Tech stack:** No preference — whatever works best.

**Integration:** Hybrid — YouTube API for search, yt-dlp for downloads.

### Category 3: Prior Art & Context

**Known prior art:** User hasn't researched. Inspired by yoink.media (paid Ableton plugin).
**Why build new?** YouTube focus + agent integration + open source.
**Prior attempts:** None — fresh idea.

### Category 4: Architecture & Structure

**Architecture:** Monorepo — shared core library + CLI wrapper + web app wrapper.
**Stitching pipeline:** Needs research.
**Data model / caching:** Needs research — depends on YouTube API feasibility.
**Project setup:** Git + full docs from day one.

### Category 5: Edge Cases & Error Handling

**No match found:** Automatically split phrase into smaller word groups, find each separately, stitch together.
**Caption quality:** Prefer manually-written captions, fall back to auto-generated.
**Timing mismatches:** Use speech recognition (audio alignment) to refine clip boundaries after download.

### Category 6: Scale & Performance
Skipped — early-stage tool, no scale requirements yet.

### Category 7: Security & Privacy
Skipped — no user accounts, no PII, no auth, minimal surface.

### Category 8: Integration & Dependencies

**Agent API:** CLI subprocess — agents shell out to the CLI tool.
**Rate limits:** Needs research.
**Output format:** Both video (MP4) and audio-only (MP3/WAV) — user's choice.

### Category 9: Testing & Verification
Skipped — define later once architecture is clearer.

### Category 10: Deployment & Operations
Skipped — CLI is local, web decisions come later.

### Category 11: Trade-offs & Priorities

**Priority ranking:** Accuracy > Speed > Simplicity
**Quality bar:** Production from start — proper error handling, tests, docs.
**Willing to sacrifice:** Speed, coverage, polish — accuracy is king.

### Category 12: Scope & Boundaries

**V1 scope:** CLI + core library. Web comes later.
**Out of scope for V1:**
- Non-English content
- Live streams
- Video editing (no trimming, filters, effects — just raw clips + stitching)

**Fixed decisions (non-negotiable):**
- Name: yt-tts
- Open source
- YouTube only (no other platforms)

## Prior-Art Research

### Existing Solutions

| Solution | URL | Relevance | Quality | Notes |
|----------|-----|-----------|---------|-------|
| CapScript Pro | github.com/serptail/CapScript-Youtube-Subtitle-Search-Tool | High | Accepted | Closest existing tool — searches YouTube captions, downloads clips, stitches. Lacks word-level alignment. |
| videogrep | github.com/antiboredom/videogrep | High | Accepted | Creates supercuts from subtitle search. Local files only, no YouTube download. Uses MoviePy + Vosk. |
| kelciour/playphrase | github.com/kelciour/playphrase | Medium | Accepted | Open-source PlayPhrase.me clone. Searches SRT files, plays via mpv. Local only. |
| PlayPhrase.me | playphrase.me | Medium | Caution | 10M+ indexed phrases from movies/TV. Demonstrates approach at scale. Closed source. |
| GetYarn.io / getyarn.io | getyarn.io | Medium | Caution | Quote search across movies/TV/music. Closed source commercial. |
| Filmot | filmot.com | High | Accepted | 1.53B transcripts indexed. Has Python API via RapidAPI. Could serve as pre-built search backend. |
| yoink.media | yoink.media | Low | Caution | Ableton plugin for sample finding. Different domain but inspiration source. |

### Key Technical Findings

#### 1. YouTube Caption Search: No Native API
- YouTube Data API v3 has NO endpoint for full-text search across captions
- `captions.download` only works for videos YOU OWN (requires edit permission)
- `captions.download` costs 200 of 10,000 daily quota units per call
- **Alternative**: `youtube-transcript-api` (Python) retrieves transcripts from any public video without API key, using undocumented internal YouTube endpoints
- Returns segment-level timestamps (2-5 second chunks), NOT word-level

#### 2. Word-Level Timestamps: json3 Format
- YouTube's internal json3 caption format contains word-level timestamps (`tOffsetMs`) and ASR confidence scores (`acAsrConf`, 0-255)
- Retrieve via: `yt-dlp --skip-download --write-auto-subs --sub-format json3 --sub-lang en VIDEO_URL`
- Word start time = `tStartMs + tOffsetMs` (milliseconds)
- **Only available for auto-generated captions** — manual captions lack `tOffsetMs`
- json3 format is undocumented and could change without notice

#### 3. Auto-Generated Caption Accuracy: 62-95%
- Varies heavily by audio quality, accent, domain vocabulary
- `acAsrConf` confidence score (0-255) can filter low-confidence words
- Manually-created captions are more accurate but lack word-level timing

#### 4. Rate Limits
- **YouTube Data API v3**: 10,000 units/day. search.list = 100 units, captions.list = 50 units
- **youtube-transcript-api**: Inconsistent — some users fetch 10k+ without issues, others blocked after ~250. Cloud IPs blocked more aggressively
- **yt-dlp subtitle downloads**: ~10 rapid requests triggers restrictions. Use `--sleep-interval`

#### 5. Existing Tools Use Pre-Indexed Databases
- Filmot: 1.53B transcripts, 1.35B videos
- PlayPhrase.me: 10M+ phrases
- YouGlish: 30M+ videos (manual captions only)
- TalkSearch: Per-channel, Algolia with sentence-level chunking
- Live search is not viable at scale; crawl-then-index is the standard approach

#### 6. Clip Extraction: Partial Downloads Possible
- `yt-dlp --download-sections` downloads full video then trims (NOT partial)
- **Better**: `yt-dlp --downloader ffmpeg --downloader-args "ffmpeg_i:-ss X -to Y"` does HTTP seeking (near-partial download)
- **Best control**: `yt-dlp -g` to get stream URL, then `ffmpeg -ss X -to Y -i URL -c copy output.mp3`
- `--force-keyframes-at-cuts` needed for frame-accurate cuts but triggers re-encode

#### 7. Audio Alignment: WhisperX is Best Practical Tool
- **WhisperX**: Whisper + wav2vec2 forced alignment. ~94% F1 at 100ms tolerance. 70x realtime batched. pip install, needs GPU.
- **stable-ts**: Modified Whisper timestamp tokens. Good accuracy, fast.
- **whisper-timestamped**: DTW on cross-attention weights. Rounded to ~1s.
- **Montreal Forced Aligner (MFA)**: Higher precision than WhisperX but complex setup.
- Native Whisper word timestamps are unreliable (inference trick, not trained).

#### 8. Stitching Pipeline
- **Normalize sample rates**: ffmpeg `aresample=44100`
- **Normalize audio levels**: ffmpeg `loudnorm` (EBU R128, dual-pass recommended)
- **Concatenate**: ffmpeg `concat` filter (handles different codecs)
- **Optional crossfade**: `acrossfade=d=0.05:c1=tri:c2=tri` (50ms)
- For word-level clips, very short or no crossfade sounds most natural

#### 9. Legal Considerations
- YouTube ToS explicitly prohibit downloading content outside playback interface
- **Fair use arguments (strong for yt-tts)**:
  - Highly transformative (constructing new sentences from word clips)
  - Tiny amount used (0.5-3s of 5-60min videos)
  - No market substitution
  - Novel purpose unrelated to original content
- **Risk mitigation**: Ephemeral processing (don't cache clips), minimal extraction, user responsibility disclaimer
- Fair use is never guaranteed — always case-by-case judicial determination

### Unverified Claims
- YouTube's json3 format stability — undocumented, could change anytime
- Exact rate limit thresholds for youtube-transcript-api (inconsistent reports)

### Conflicts
- Caption accuracy: Studies disagree (62% vs 95%). Likely depends heavily on audio quality and domain.

## Gap Analysis

### Resolved Gaps

1. **Search strategy**: User prefers live search without building an index. Research and test all available sources (youtube-transcript-api, Filmot API, yt-dlp json3, etc.). If live search proves impossible at acceptable speed, then use external index sources.

2. **GPU dependency**: Graceful fallback. Use WhisperX if GPU available, fall back to YouTube's json3 word timestamps if not. But first: research whether WhisperX is truly the best option — there may be lighter alternatives.

3. **Voice selection**: Both modes. Default is mixed speakers, but offer a `--voice`/`--channel` flag to constrain all words to one source.

4. **Caching**: SQLite cache for word→clip mappings. Speeds up repeat queries.

5. **Legal disclaimer**: Include clear disclaimer in README and CLI output about YouTube ToS and fair use.

### Additional Research (Round 2)

#### Filmot API: Not Viable
- RapidAPI endpoint is live but **not open-access** — need private arrangement with developer
- `api.filmot.org` returns HTTP 523 (down)
- Web search on filmot.com requires CAPTCHA (can't automate)
- Subtitle crawling **suspended June 2024** due to YouTube anti-crawling measures
- Existing 1.53B archive is frozen, no new data being added
- Conclusion: Filmot cannot be our primary backend

#### YouTube-Commons Dataset (the shortcut)
- 22.7M transcripts from 2M+ videos across 721K channels
- ~45 billion words, ~162GB compressed, ~298GB uncompressed (Parquet)
- CC-BY licensed videos only (skews educational/tech)
- Available on HuggingFace (PleIAs/YouTube-Commons, Rijgersberg re-upload fixes column issues)
- Can bootstrap a working search index on day 1

#### Building Our Own Index
- **SQLite FTS5**: handles up to ~5M docs, 10-30ms queries, zero ops
- **Manticore Search**: handles 1.7B+ docs, SQL-compatible, likely what Filmot uses, $20-40/mo VPS
- **Crawling rate**: ~2,000 transcripts/hour with residential proxies ($20-50/mo)
- **YouTube Data API**: playlistItems.list = 1 unit/call (500K video IDs/day/key)
- **Storage**: ~5KB raw transcript per video, ~50GB for 10M videos with index

#### Bumblebee Concept (from user feedback)
- This is an art project — audio quality mismatches are part of the vibe
- Splitting should produce natural speech chunks, not individual words
- Like Bumblebee speaking through radio clips in Transformers
- "Voice of the internet" — giving agents speech made from real YouTube clips

### Sources
- developers.google.com/youtube/v3/docs/captions — Quality: Accepted — Official API docs
- pypi.org/project/youtube-transcript-api/ — Quality: Accepted — Library docs
- github.com/m-bain/whisperX — Quality: Accepted — WhisperX repo
- github.com/serptail/CapScript-Youtube-Subtitle-Search-Tool — Quality: Accepted — CapScript repo
- github.com/antiboredom/videogrep — Quality: Accepted — videogrep repo
- filmot.com — Quality: Accepted — Filmot search engine
- nadimtuhin.com/blog/ytranscript-how-it-works — Quality: Accepted — json3 reverse engineering
- github.com/yt-dlp/yt-dlp — Quality: Accepted — yt-dlp documentation
- arxiv.org/html/2509.09987v1 — Quality: Accepted — Whisper alignment research
