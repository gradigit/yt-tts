#!/bin/sh
set -e

REPO_URL="https://github.com/gradigit/yt-tts.git"
INSTALL_DIR="$HOME/.local/share/yt-tts/repo"

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

# Clone repo
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating yt-tts repo..."
    git -C "$INSTALL_DIR" pull --quiet
else
    echo "Cloning yt-tts..."
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
fi

# Install yt-tts from local clone
uv tool install --from "$INSTALL_DIR[bootstrap]" yt-tts

# Symlink skills from repo
CLAUDE_DIR="$HOME/.claude/skills/yt-tts"
AGENTS_DIR="$HOME/.agents/skills/yt-tts"

mkdir -p "$CLAUDE_DIR" "$AGENTS_DIR"
ln -sf "$INSTALL_DIR/skill/SKILL.md" "$CLAUDE_DIR/SKILL.md"
ln -sf "$INSTALL_DIR/skill/SKILL.md" "$AGENTS_DIR/SKILL.md"
echo "Linked skill → ~/.claude/skills/yt-tts/ + ~/.agents/skills/yt-tts/"

# Bootstrap starter index (~27K transcripts, ~100MB)
echo ""
echo "Bootstrapping starter index (~27K transcripts)..."
yt-tts index init --subset 1

echo ""
echo "yt-tts is ready! Try:"
echo "  yt-tts \"hello world\""
echo ""
echo "For the full index (3.15M transcripts, ~58GB):"
echo "  yt-tts index init"
