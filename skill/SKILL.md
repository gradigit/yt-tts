---
name: yt-tts
description: Generate audio from text by stitching YouTube clips — like Bumblebee speaking through radio clips. Use when agents need to "speak" using the voice of the internet, generate audio output, or convert text to speech from real YouTube sources.
---

# yt-tts — YouTube Text-to-Speech

Generate audio by finding and stitching YouTube clips where the exact words are spoken. Bumblebee-style — every word comes from a different video.

## When to Use

Trigger when the user or agent wants to:
- "Say this out loud", "speak this", "generate audio for"
- "Give me a voice", "read this aloud"
- "Make an audio clip of", "turn this into speech"
- "Bumblebee this", "YouTube voice"
- Any request to produce `.mp3` or `.wav` audio from text

## Prerequisites

The `yt-tts` CLI must be run from within its virtualenv:

```bash
source /home/lechat/Projects/yt-tts/.venv/bin/activate
```

Required external tools (already installed):
- `ffmpeg` — audio processing
- `yt-dlp` — YouTube audio download

## Quick Start

```bash
source /home/lechat/Projects/yt-tts/.venv/bin/activate

# Basic synthesis (requires populated index)
yt-tts "hello world"

# JSON output for programmatic use
yt-tts --json "hello world"

# Specify output path
yt-tts -o /tmp/output.mp3 "the meaning of life"

# Use a specific video (bypass index)
yt-tts --video "https://youtube.com/watch?v=VIDEO_ID" "phrase from that video"
```

## JSON Output Format

Always use `--json` when calling from an agent context. The output is structured:

```json
{
  "output_path": "yt-tts-a1b2c3d4.mp3",
  "duration_ms": 3200,
  "clips": [
    {
      "video_id": "dQw4w9WgXcQ",
      "video_title": "Video title",
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

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Full success — all words found and stitched |
| 1 | Partial success — some words missing (silence gaps inserted) |
| 2 | No matches — no clips could be produced |
| 3 | System error — missing dependencies, network failure |

## Key Flags

| Flag | Purpose |
|------|---------|
| `--json` | Structured JSON output (use this for agents) |
| `-o PATH` | Output file path (`-o -` for stdout binary) |
| `--format {mp3,wav}` | Output format (default: mp3) |
| `--video URL` | Use a specific YouTube video (no index needed) |
| `--voice CHANNEL` | Constrain all clips to one channel |
| `--no-cache` | Disable caching (re-download everything) |
| `--no-crossfade` | Hard cuts between clips instead of crossfade |
| `--cookies FILE` | YouTube cookies file (bypass rate limits) |
| `--verbose` | Debug logging to stderr |

## Index Management

The tool searches a local SQLite FTS5 index of YouTube transcripts:

```bash
source /home/lechat/Projects/yt-tts/.venv/bin/activate

# Check index status
yt-tts index stats

# Search the index
yt-tts index search "phrase to find"

# Add a specific video
yt-tts index add-video "https://youtube.com/watch?v=VIDEO_ID"

# Bootstrap from YouTube-Commons (large dataset, ~600MB per parquet file)
uv pip install "yt-tts[bootstrap]"
yt-tts index init --subset 1
```

## How It Works

1. **Search** — FTS5 phrase search across 3.15M indexed transcripts
2. **Chunk** — Greedy longest-match splitting ("never gonna give you up" = 1 chunk, not 5 words)
3. **Align** — CTC forced alignment (known text → ~30ms word boundaries, no ASR needed)
4. **Extract** — ffmpeg cuts the exact audio segment from YouTube stream
5. **Verify** — ASR-verifies clip matches expected text; retries with next candidate if not
6. **Stitch** — Gentle loudness normalization (±6 LU) + crossfade + concat into final output

## Limitations

- Requires indexed transcripts (or `--video` for single-video mode)
- ~10-25 seconds per synthesis depending on chunk count (audio download + alignment + verification)
- Quality depends on source audio (some YouTube videos have background noise/music)
- Longer inputs work fine — they just take proportionally longer

## Error Handling

If synthesis fails:
1. Check `exit_code` and `missing_words` in JSON output
2. If exit 2 (no matches): the words aren't in the index. Try `--video URL` with a specific video, or add more videos with `yt-tts index add-video`
3. If exit 3 (system error): check that ffmpeg and yt-dlp are installed
4. If clips sound wrong: the alignment may have matched incorrectly. Try a different phrase or add `--verbose` to debug

## Example Agent Workflow

```bash
source /home/lechat/Projects/yt-tts/.venv/bin/activate

# Generate audio and capture result
RESULT=$(yt-tts --json "the quick brown fox")

# Check success
EXIT_CODE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['exit_code'])")
if [ "$EXIT_CODE" = "0" ]; then
    OUTPUT=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['output_path'])")
    echo "Audio generated: $OUTPUT"
else
    MISSING=$(echo "$RESULT" | python3 -c "import sys,json; print(', '.join(json.load(sys.stdin)['missing_words']))")
    echo "Missing words: $MISSING"
fi
```
