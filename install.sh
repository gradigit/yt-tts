#!/bin/sh
set -e

echo "Installing yt-tts..."

# Check for uv, install if missing
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Check for ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Error: ffmpeg is required. Install it from https://ffmpeg.org/download.html"
    exit 1
fi

# Check for yt-dlp
if ! command -v yt-dlp >/dev/null 2>&1; then
    echo "Error: yt-dlp is required. Install it from https://github.com/yt-dlp/yt-dlp"
    exit 1
fi

uv tool install yt-tts

echo ""
echo "Done! Run: yt-tts \"hello world\""
