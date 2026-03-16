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

# Install yt-tts
uv tool install yt-tts

# Install Claude Code skill
SKILL_URL="https://raw.githubusercontent.com/gradigit/yt-tts/master/skill/SKILL.md"
SKILL_DIR="$HOME/.claude/skills/yt-tts"
mkdir -p "$SKILL_DIR"
curl -LsSf "$SKILL_URL" -o "$SKILL_DIR/SKILL.md"
echo "Installed Claude Code skill → $SKILL_DIR/SKILL.md"

# Install Agents skill
AGENTS_DIR="$HOME/.agents/skills/yt-tts"
mkdir -p "$AGENTS_DIR"
ln -sf "$SKILL_DIR/SKILL.md" "$AGENTS_DIR/SKILL.md"
echo "Installed Agents skill → $AGENTS_DIR/SKILL.md"

echo ""
echo "Done! Run: yt-tts \"hello world\""
