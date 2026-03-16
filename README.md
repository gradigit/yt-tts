# yt-tts

**Turn text into audio by stitching YouTube clips** — like Bumblebee speaking through radio clips.

Every word comes from a different YouTube video. An art project giving AI agents "the voice of the internet."

```bash
yt-tts "the meaning of life"
# → yt-tts-a1b2c3d4.mp3 (clips from 4 different YouTubers)
```

## How It Works

1. **Search** — Finds your phrase in 22.7M YouTube transcripts (SQLite FTS5 index)
2. **Chunk** — Greedy longest-match: "never gonna give you up" = 1 clip, not 5 words
3. **Align** — Downloads audio, runs Whisper locally for word-level timestamps
4. **Extract** — ffmpeg cuts the exact segment from the YouTube stream
5. **Stitch** — Loudness normalization + crossfade into a single MP3

No YouTube API key needed. No rate limits (Whisper runs locally).

## Install

```bash
pip install yt-tts
```

**Requirements:** Python 3.11+, [ffmpeg](https://ffmpeg.org/download.html), [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## Quick Start

```bash
# Build the transcript index (downloads from YouTube-Commons on HuggingFace)
pip install yt-tts[bootstrap]
yt-tts index init --subset 1  # ~27K transcripts from 1 parquet file
yt-tts index init              # full 22.7M transcripts (needs ~120GB disk)

# Synthesize
yt-tts "hello world"
yt-tts "I can't believe you've done this" -o output.mp3
yt-tts --json "the answer is probably not"  # structured JSON output

# Use a specific video (no index needed)
yt-tts --video "https://youtube.com/watch?v=VIDEO_ID" "phrase from that video"

# Batch mode
echo -e "hello world\ngoodbye world" > phrases.txt
yt-tts batch phrases.txt -o clips/

# Search the index
yt-tts index search "machine learning"
yt-tts index stats
```

## CLI Reference

```
yt-tts [options] "text to synthesize"

Options:
  --video URL            Use a specific YouTube video (bypass index)
  --voice CHANNEL        Constrain clips to one channel
  --output PATH, -o      Output file ('-' for stdout)
  --format {mp3,wav}     Output format (default: mp3)
  --cookies FILE         YouTube cookies file (bypass rate limits)
  --cookies-from-browser BROWSER  Use browser cookies (chrome, firefox)
  --no-cache             Disable clip/caption caching
  --no-crossfade         Hard cuts between clips
  --json                 Structured JSON output
  --verbose              Debug logging
  --version              Show version

Subcommands:
  index init [--subset N]     Build transcript index from YouTube-Commons
  index search PHRASE         Search the index
  index stats                 Show index statistics
  index add-video URL         Add a video's transcript
  index add-channel URL       Add a channel's transcripts
  batch FILE -o DIR           Generate clips for each line in file
  cache stats                 Show cache size
  cache clear                 Clear all caches
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All words found and stitched |
| 1 | Partial — some words missing (silence gaps inserted) |
| 2 | No matches found |
| 3 | System error (missing ffmpeg, network failure) |

## JSON Output

```json
{
  "output_path": "yt-tts-a1b2c3d4.mp3",
  "duration_ms": 3200,
  "clips": [
    {
      "video_id": "dQw4w9WgXcQ",
      "phrase": "never gonna give you up",
      "start_ms": 42611,
      "end_ms": 44791,
      "confidence": 0.84,
      "timestamp_source": "whisper"
    }
  ],
  "missing_words": [],
  "exit_code": 0
}
```

## Architecture

```
Text input
  │
  ▼ chunk_phrase() — greedy longest-match
  │  "I can't believe" → MATCH (video A)
  │  "you've done this" → MATCH (video B)
  │
  ▼ Parallel resolution (ThreadPoolExecutor, 3 workers):
  │  For each chunk:
  │  ├─ Search FTS5 index → video_id
  │  ├─ Estimate position from word index
  │  ├─ Download audio segment (yt-dlp stream URL)
  │  ├─ Whisper alignment → precise timestamps
  │  └─ ffmpeg extract clip
  │
  ▼ stitch_clips()
  │  ├─ EBU R128 loudness normalization (dual-pass loudnorm)
  │  ├─ Silence gaps for missing words
  │  └─ Concat + crossfade
  │
  ▼ Output: MP3/WAV
```

## Python API

```python
from yt_tts.core.pipeline import synthesize
from yt_tts.config import Config

result = synthesize("hello world", Config())
print(result.output_path)    # Path to MP3
print(result.clips)          # List of ClipInfo
print(result.missing_words)  # Words not found
print(result.exit_code)      # 0, 1, 2, or 3
```

## How It Avoids Rate Limits

YouTube's caption API aggressively rate-limits. yt-tts has a multi-layer fallback:

1. **YouTube-Commons index** — 22.7M transcripts pre-downloaded from HuggingFace. Zero YouTube API calls for search.
2. **Whisper alignment** — Downloads audio (not rate-limited) and transcribes locally with faster-whisper. No caption API needed.
3. **Persistent circuit breaker** — After one 429, skips all caption APIs for 1 hour and goes straight to Whisper.
4. **Cookie support** — `--cookies` / `--cookies-from-browser` for authenticated sessions if needed.

## GPU Acceleration

yt-tts auto-detects CUDA GPUs for Whisper. With a GPU, synthesis takes ~7s per clip. On CPU, ~12s.

## Disclaimer

This tool downloads short audio clips from YouTube for transformative remix purposes. Users are responsible for ensuring their use complies with YouTube's Terms of Service and applicable copyright law. This is an art/research project — not a piracy tool.

## License

MIT
