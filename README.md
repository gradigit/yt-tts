# yt-tts

**Turn text into audio by stitching YouTube clips** — like Bumblebee speaking through radio clips.

Every word comes from a different YouTube video. An art project giving AI agents "the voice of the internet."

```bash
curl -LsSf https://raw.githubusercontent.com/gradigit/yt-tts/master/install.sh | sh
```

```bash
yt-tts "the meaning of life"
# → yt-tts-a1b2c3d4.mp3 (clips from 4 different YouTubers)
```

## How It Works

1. **Search** — Finds your phrase in 3.15M YouTube transcripts (SQLite FTS5 index)
2. **Chunk** — Greedy longest-match: "never gonna give you up" = 1 clip, not 5 words
3. **Align** — Downloads audio, runs CTC forced alignment (MMS_FA) for ~30ms word boundaries
4. **Extract** — ffmpeg cuts the exact segment from the YouTube stream
5. **Verify** — ASR-verifies the clip matches expected text; retries with next candidate if not
6. **Stitch** — Gentle loudness normalization (±6 LU) + crossfade into a single MP3

No YouTube API key needed. All alignment runs locally.

The one-liner installs all dependencies (uv, ffmpeg, yt-dlp), the CLI tool, agent skills, and a starter index (~27K transcripts, ~100MB) so it works immediately.

## Quick Start

```bash
# Synthesize
yt-tts "hello world"
yt-tts "I can't believe you've done this" -o output.mp3
yt-tts --json "the answer is probably not"  # structured JSON output

# Use a specific video (no index needed)
yt-tts --video "https://youtube.com/watch?v=VIDEO_ID" "phrase from that video"

# Batch mode
echo -e "hello world\ngoodbye world" > phrases.txt
yt-tts batch phrases.txt -o clips/
```

## Transcript Index

The installer bootstraps a starter index (~27K transcripts, ~100MB). For better phrase coverage, download the full index:

```bash
yt-tts index init              # full 3.15M transcripts (~58GB)
```

You can also grow the index incrementally:

```bash
yt-tts index add-video "https://youtube.com/watch?v=VIDEO_ID"
yt-tts index add-channel "https://youtube.com/@ChannelName"
yt-tts index search "phrase to find"
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
      "timestamp_source": "ctc_alignment"
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
  │  ├─ CTC forced alignment (known text → timestamps, ~30ms accuracy)
  │  ├─ ffmpeg extract clip
  │  └─ ASR verify → retry next candidate if mismatch
  │
  ▼ stitch_clips()
  │  ├─ Gentle loudness normalization (±6 LU window)
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

## GPU Acceleration

yt-tts auto-detects the best compute backend:
- **NVIDIA GPU** — faster-whisper (CUDA) for ASR verification
- **Apple Silicon** — parakeet-mlx or mlx-whisper (Metal)
- **CPU** — faster-whisper (int8 quantized)

CTC forced alignment runs on CPU and is fast (~100ms per clip). ASR verification is the GPU-accelerated step.

## Disclaimer

This tool downloads short audio clips from YouTube for transformative remix purposes. Users are responsible for ensuring their use complies with YouTube's Terms of Service and applicable copyright law. This is an art/research project — not a piracy tool.

## License

MIT
