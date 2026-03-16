"""Dependency checking for external tools."""

import shutil
import sys

from yt_tts.exceptions import DependencyError


def check_ffmpeg() -> None:
    """Verify ffmpeg is installed and accessible."""
    if not shutil.which("ffmpeg"):
        raise DependencyError(
            "ffmpeg is not installed or not on PATH.\n"
            "Install it with:\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  macOS: brew install ffmpeg\n"
            "  Windows: winget install ffmpeg"
        )


def check_ffprobe() -> None:
    """Verify ffprobe is installed and accessible."""
    if not shutil.which("ffprobe"):
        raise DependencyError(
            "ffprobe is not installed or not on PATH.\nIt is usually included with ffmpeg."
        )


def check_ytdlp() -> None:
    """Verify yt-dlp is installed and accessible."""
    if not shutil.which("yt-dlp"):
        raise DependencyError(
            "yt-dlp is not installed or not on PATH.\nInstall it with: pip install yt-dlp"
        )


def check_all() -> None:
    """Check all required external dependencies."""
    errors = []
    for check in (check_ffmpeg, check_ffprobe, check_ytdlp):
        try:
            check()
        except DependencyError as e:
            errors.append(str(e))

    if errors:
        print("Missing dependencies:", file=sys.stderr)
        for err in errors:
            print(f"\n  {err}", file=sys.stderr)
        raise DependencyError("Required external tools are missing.")
