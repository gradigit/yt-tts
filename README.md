# yt-tts

Type any sentence. Get back an audio file where every word is spoken by a different YouTuber — stitched together like Bumblebee speaking through radio clips.

https://github.com/user-attachments/assets/DEMO_PLACEHOLDER

## Install

One command installs everything (uv, ffmpeg, yt-dlp, the CLI, agent skills, and a starter transcript index):

```bash
curl -LsSf https://raw.githubusercontent.com/gradigit/yt-tts/master/install.sh | sh
```

Then:

```bash
yt-tts "the meaning of life"
```

That's it. Each word gets sourced from a different YouTube video and stitched into a single MP3.

## What it does

You give it text. It searches 3.15M YouTube transcripts to find videos where those exact words are spoken, downloads the audio, cuts the precise word boundaries using CTC forced alignment (~30ms accuracy), verifies each clip with ASR, and crossfades them into one file.

```
"I can't believe you've done this"
  → "I can't believe" from a tech review
  → "you've done this" from a cooking vlog
  → stitched into one MP3
```

No YouTube API key. No cloud ASR. Everything runs locally.

## Usage

```bash
# Basic synthesis
yt-tts "hello world"
yt-tts "never gonna give you up" -o output.mp3

# Use a specific video (no index needed)
yt-tts --video "https://youtube.com/watch?v=VIDEO_ID" "phrase from that video"

# JSON output (for agents / programmatic use)
yt-tts --json "the answer is probably not"

# Batch mode
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

## Agent Integration

The installer symlinks the yt-tts skill to `~/.claude/skills/` and `~/.agents/skills/`. Any agent that reads skills from those directories can use yt-tts to generate audio.

```bash
# Agents should use --json for structured output
yt-tts --json "hello world"
```

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
      "confidence": 0.84
    }
  ],
  "missing_words": [],
  "exit_code": 0
}
```

| Exit Code | Meaning |
|-----------|---------|
| 0 | All words found and stitched |
| 1 | Partial — some words missing (silence inserted) |
| 2 | No matches found |
| 3 | System error |

## CLI Reference

```
yt-tts [options] "text to synthesize"

Options:
  --video URL            Use a specific YouTube video (bypass index)
  --voice CHANNEL        Constrain clips to one channel
  -o PATH                Output file ('-' for stdout)
  --format {mp3,wav}     Output format (default: mp3)
  --no-cache             Disable caching
  --no-crossfade         Hard cuts between clips
  --json                 Structured JSON output
  --verbose              Debug logging

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

## How It Works

```
Text → chunk (greedy longest-match)
  → search FTS5 index → download audio (yt-dlp)
  → CTC forced alignment (known text → ~30ms word boundaries)
  → extract clip (ffmpeg) → ASR verify → retry next candidate if wrong
  → stitch (gentle loudnorm ±6 LU + crossfade) → MP3/WAV
```

## Python API

```python
from yt_tts.core.pipeline import synthesize
from yt_tts.config import Config

result = synthesize("hello world", Config())
print(result.output_path)    # Path to MP3
print(result.clips)          # List of ClipInfo
print(result.missing_words)  # Words not found
```

## License

MIT
