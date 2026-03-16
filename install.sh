#!/bin/sh
set -e

echo "Installing yt-tts..."

# Install uv if missing
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Install ffmpeg if missing
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Installing ffmpeg..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg
    elif command -v brew >/dev/null 2>&1; then
        brew install ffmpeg
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y ffmpeg
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --noconfirm ffmpeg
    else
        echo "Error: Could not install ffmpeg. Install manually: https://ffmpeg.org/download.html"
        exit 1
    fi
fi

# Install yt-dlp if missing
if ! command -v yt-dlp >/dev/null 2>&1; then
    echo "Installing yt-dlp..."
    uv tool install yt-dlp
fi

# Install yt-tts from GitHub
echo "Installing yt-tts..."
uv tool install "yt-tts[bootstrap] @ git+https://github.com/gradigit/yt-tts.git"

# Install Claude Code skill
REPO_URL="https://raw.githubusercontent.com/gradigit/yt-tts/master/skill/SKILL.md"
CLAUDE_DIR="$HOME/.claude/skills/yt-tts"
AGENTS_DIR="$HOME/.agents/skills/yt-tts"

mkdir -p "$CLAUDE_DIR" "$AGENTS_DIR"
curl -LsSf "$REPO_URL" -o "$CLAUDE_DIR/SKILL.md"
ln -sf "$CLAUDE_DIR/SKILL.md" "$AGENTS_DIR/SKILL.md"
echo "Installed skill → ~/.claude/skills/yt-tts/ + ~/.agents/skills/yt-tts/"

# Bootstrap a starter index (~27K transcripts) so it works immediately
echo ""
echo "Bootstrapping starter index (1 parquet file, ~27K transcripts)..."
yt-tts index init --subset 1

echo ""
echo "yt-tts is ready! Try:"
echo "  yt-tts \"hello world\""
echo ""
echo "For the full index (3.15M transcripts, ~58GB):"
echo "  yt-tts index init"
