# yt-tts: YouTube Text-to-Speech

Build an open-source CLI tool (with a core library) that turns any text input into audio/video output by finding and stitching together YouTube clips where those exact words are spoken. Like Bumblebee from Transformers speaking through radio clips — giving an agent "the voice of the internet." This is an art project, not a precision TTS engine. The clip-stitching aesthetic is the vibe.

## Core Concept

User types: `yt-tts "I can't believe you've done this"`
The tool:
1. Searches a local transcript index for videos where someone says that exact phrase
2. If no single clip matches, splits into natural chunks ("I can't believe" + "you've done this") — not individual words
3. Downloads the precise audio/video segments
4. Stitches clips together with normalized audio levels
5. Outputs a file and prints the path

The result sounds like someone channel-surfing through YouTube to assemble a message. Each clip is a recognizable snippet of human speech — not robotic, not individual words, but phrase-level chunks from different speakers and contexts.

## Architecture

**Monorepo** with three packages:
- `core/` — the library: search, extract, align, stitch
- `cli/` — thin CLI wrapper around core
- `web/` — web interface (V2, out of scope for V1)

**V1 scope**: core library + CLI only.

## Functional Requirements

### 1. Transcript Index

Build and maintain a local full-text search index of YouTube transcripts.

**Bootstrap: YouTube-Commons dataset (day 1)**
- Download YouTube-Commons from HuggingFace (~162GB compressed, ~298GB uncompressed)
- 22.7M transcripts from 2M+ videos across 721K channels (~45 billion words)
- Filter to English transcripts, load into SQLite FTS5
- Schema: video_id, channel_id, channel_name, title, text, language, word_count
- This gives a working searchable index immediately
- **Note**: YouTube-Commons only covers CC-BY videos — skews heavily toward educational/tech content. This is the starting point, not the whole voice.

**Incremental crawling (ongoing)**
- Add channels/videos beyond YouTube-Commons (it only covers CC-BY content)
- Use YouTube Data API v3 `playlistItems.list` (1 unit/call, 50 items/page) to enumerate channel videos
- Fetch transcripts via `youtube-transcript-api` (no API key needed)
- Insert into the same SQLite FTS5 index
- `yt-tts index add-channel <url>` — index all videos from a channel
- `yt-tts index add-video <url>` — index a single video
- `yt-tts index stats` — show index size
- Target: ~2,000 transcripts/hour with rate limiting

**Starter channel list (ship with the tool)**
- Include a curated list of popular/diverse YouTube channels to crawl after init
- Mix of: popular creators, podcasts, news, commentary, memes, pop culture
- `yt-tts index add-starter` — crawl the starter list to fill the "voice of the internet" gap left by CC-BY-only YouTube-Commons
- Community-contributed: users can PR additional channels to the starter list

**Search**
- SQLite FTS5 exact phrase matching across all indexed transcripts
- Returns: video_id, approximate timestamp range, surrounding context text, match confidence
- If index grows beyond ~5M documents and FTS5 gets slow, migrate to Manticore Search (SQL-compatible, proven at 1.7B docs)

**Fallback for videos not in index**
- `--video <url>` or `--channel <url>`: fetch transcript live via youtube-transcript-api, search it, optionally add to index
- YouTube Data API v3 `search.list` (100 units/call) to find candidate videos by keyword, then fetch + search their transcripts

### 2. Phrase Search & Timestamp Extraction

Once a video match is found, get precise timestamps:

**Caption preference strategy:**
1. Fetch auto-generated captions in json3 format via yt-dlp — these contain word-level timestamps (`tStartMs + tOffsetMs` in milliseconds) and ASR confidence scores (`acAsrConf`, 0-255)
2. Also fetch manual captions via youtube-transcript-api for text verification (manual captions are more accurate but lack word-level timing)
3. Use json3 word timestamps to locate exact start/end of the matched phrase
4. Filter by `acAsrConf` confidence — reject words below threshold (configurable, default 128/255)

### 3. Clip Extraction
- Download only the needed segment, NOT full videos
- **Primary method**: `yt-dlp -g` to get stream URL + `ffmpeg -ss X -to Y -i URL` for partial download via HTTP seeking
- **Fallback**: `yt-dlp --download-sections "*START-END"` if stream URL fails (downloads more but more reliable)
- Handle expired/invalid stream URLs: auto-retry with fresh URL
- Support both video (MP4) and audio-only (MP3/WAV) output
- Audio-only is preferred (smaller, faster, more reliable)

### 4. Word-Level Alignment (optional refinement)
Refine clip boundaries to exact word edges after download.

**Priority chain:**
1. **json3 word timestamps** (default, no extra deps): `tStartMs + tOffsetMs` from auto-generated captions. Millisecond precision. Good enough for most cases.
2. **stable-ts** (opt-in, `--align stable-ts`): Modified Whisper with improved timestamps. No HuggingFace token needed.
3. **WhisperX** (opt-in, `--align whisperx`): wav2vec2 forced alignment. Best accuracy (~94% F1 at 100ms). Requires GPU + HuggingFace token.

Target: ±200ms with json3 (default), ±50ms with stable-ts/WhisperX.

### 5. Stitching Pipeline
- Normalize audio levels across clips: ffmpeg `loudnorm` (EBU R128, dual-pass)
- Normalize sample rates: ffmpeg `aresample` to 44100
- Concatenate: ffmpeg `concat` filter
- Optional short crossfade: `acrossfade=d=0.05` (50ms), enabled by default, disable with `--no-crossfade`
- Output: single MP4 or MP3 file

### 6. Bumblebee Chunking (smart phrase splitting)

When exact phrase not found in a single video, split into **natural speech chunks** — not individual words. The goal is each clip sounds like a recognizable snippet of someone talking, like switching between radio stations.

**Splitting strategy (greedy longest-match):**
1. Try the full input phrase against the index
2. If no match: use greedy bisection — try the first half of the phrase, if that matches take it, then handle the remainder. If the first half doesn't match, try a shorter prefix. Work through the input left-to-right, always taking the longest chunk that matches.
3. No NLP needed — "natural boundaries" emerge from what actually exists in YouTube transcripts. A 4-word chunk that someone actually said will always sound more natural than an algorithmically-split clause.
4. Individual words are the **last resort**, not the default
5. Optimize for fewest clips (prefer longer matches)
6. Each chunk search is independent and can be parallelized (with concurrency limit)

**Example:** "I can't believe you've done this"
- Try: full phrase → no match
- Try: "I can't believe you've" (first 4 words) → no match
- Try: "I can't believe" (first 3 words) → match! Take it.
- Remainder: "you've done this" → match! Take it. Done (2 clips).
- NOT: "I" + "can't" + "believe" + "you've" + "done" + "this" (6 clips — avoid this)

**Bounds and limits:**
- Maximum input length: 100 words (V1)
- Maximum clips in output: 50
- Concurrency limit: 3 parallel searches
- Per-chunk search timeout: 30 seconds
- Total operation timeout: 10 minutes
- If a chunk cannot be found: try splitting it smaller. If individual words still can't be found: insert silence gap (default 200ms) and report missing words to stderr

### 7. Voice/Channel Constraint
- Default: mixed speakers — each chunk can come from any video (the Bumblebee effect)
- `--voice <channel_url>` or `--channel <channel_url>`: constrain all chunks to clips from one YouTube channel
- When constrained: search only that channel's transcripts in the index (or fetch live if not indexed)

### 8. Caching
- **SQLite index** is the primary cache — transcript text is stored permanently
- **Cache downloaded clips** in `~/.cache/yt-tts/clips/` (keyed by video_id + start_ms + end_ms)
- Cache json3 caption data to avoid re-fetching
- `--no-cache` flag to bypass clip cache (index is always used)
- `yt-tts cache clear` subcommand
- `yt-tts cache stats` subcommand

### 9. Rate Limiting
- **youtube-transcript-api**: 2-second sleep between requests. Exponential backoff on HTTP 429: initial=2s, multiplier=2x, max=60s, max_retries=5.
- **yt-dlp**: `--sleep-interval 2 --max-sleep-interval 5` for subtitle and clip downloads.
- **YouTube Data API v3**: Track daily quota usage in SQLite. Warn at 80% (8,000 units). Stop at 95% (9,500 units).
- **Per-invocation budget**: max 50 caption fetches, max 30 clip downloads.
- **Circuit breaker**: After 3 consecutive rate-limit responses from a source, pause that source for 5 minutes.

## CLI Interface

```
# Core usage
yt-tts "any text you want to hear"              # search index, extract, stitch → print file path
yt-tts "hello world" --format mp3               # audio only (default)
yt-tts "hello world" --format mp4               # video
yt-tts "hello world" --output ./output.mp3      # specify output path
yt-tts "hello world" --output -                 # binary to stdout (for piping)
yt-tts "hello world" --json                     # JSON: {path, duration, clips[], missing_words[]}
yt-tts "hello world" --verbose                  # show search/alignment details

# Voice constraint
yt-tts "hello world" --voice <channel_url>      # all chunks from one channel

# Alignment
yt-tts "hello world" --align stable-ts          # opt-in audio alignment
yt-tts "hello world" --align whisperx           # opt-in best-accuracy alignment

# Index management
yt-tts index init                               # download YouTube-Commons + build FTS5 index
yt-tts index add-channel <url>                  # crawl and index a channel's transcripts
yt-tts index add-video <url>                    # index a single video's transcript
yt-tts index stats                              # show index size, channel count, etc.
yt-tts index search "exact phrase"              # search index directly (debug/explore)

# Cache management
yt-tts cache clear                              # clear clip cache
yt-tts cache stats                              # show cache size/hits
yt-tts --no-cache "hello world"                 # skip clip cache for this run
```

**Output behavior:**
- Default: write file to current directory (auto-named `yt-tts-{hash}.mp3`), print file path to stdout
- `--output <path>`: write to specified path, print path to stdout
- `--output -`: write binary to stdout (explicit opt-in for piping)
- `--json`: JSON object to stdout: `{path, duration, clips: [{chunk, video_id, video_title, start_ms, end_ms}], missing_words: []}`
- Progress/logging goes to stderr (never mixed with output)

**Exit codes:**
- 0 = full success (all chunks found and stitched)
- 1 = partial success (output file created but some chunks missing — missing words on stderr, silence gaps inserted)
- 2 = no matches found (no output file created)
- 3 = system error (network, ffmpeg, dependencies)

## Technical Constraints

- **No full video downloads** — only download the clip segment needed
- **No user accounts** — stateless tool, no auth for end users. YouTube API key optional (for channel enumeration), configured via env var.
- **No monetization** — open source, free
- **English only** for V1
- **YouTube only** — no other video platforms
- **Cache everything** — index, transcripts, clips

## Key Technical Decisions (from research)

1. **Own index over Filmot** — Filmot's API is not open-access, requires CAPTCHA for web, and stopped crawling June 2024. YouTube-Commons dataset (22.7M transcripts) bootstraps our own index on day 1.
2. **SQLite FTS5 to start** — zero ops, single file, handles millions of docs with 10-30ms queries. Migrate to Manticore Search if/when needed (SQL-compatible, proven at 1.7B docs, likely what Filmot uses).
3. **json3 format** is the key to word-level timestamps — `tStartMs + tOffsetMs` gives millisecond precision for auto-generated captions. Undocumented YouTube format, could change.
4. **stable-ts over WhisperX as default opt-in** — no HuggingFace token, no external accounts. WhisperX available for users who want max precision.
5. **Bumblebee chunking over word splitting** — phrase-level chunks sound like switching radio stations. Word-by-word sounds like a ransom note. Optimize for longest possible matches.
6. **CapScript Pro** (github.com/serptail/CapScript-Youtube-Subtitle-Search-Tool) is the closest existing tool — study its approach but differentiate with the index, phrase chunking, and agent-friendly CLI.

## Success Criteria

1. `yt-tts index init` downloads YouTube-Commons and builds a searchable index
2. `yt-tts "hello world"` finds a clip, extracts it, and outputs an audio file
3. Longer phrases split into natural chunks — each clip is a recognizable speech snippet, not isolated words
4. Audio levels are consistent across stitched clips
5. Everything is cached (index, transcripts, clips) for fast repeat queries
6. Works without GPU and without external accounts (json3 timestamps as baseline)
7. Agent-friendly: deterministic exit codes, file path on stdout, `--json` for structured output, `--output -` for piping
8. `yt-tts index add-channel <url>` lets users grow the index beyond YouTube-Commons
