#!/usr/bin/env python3
"""Spike: Test partial audio download via stream URL + ffmpeg.

Compares accuracy of -c copy (keyframe-limited) vs re-encoding.
Tests URL expiry and format availability.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path


def get_stream_url(video_id: str, format_id: str = "140") -> str | None:
    """Get direct stream URL via yt-dlp."""
    result = subprocess.run(
        ["yt-dlp", "-g", "-f", format_id, "--", video_id],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f"  Format {format_id} failed, trying bestaudio...")
        result = subprocess.run(
            ["yt-dlp", "-g", "-f", "bestaudio", "--", video_id],
            capture_output=True,
            text=True,
            timeout=30,
        )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def extract_clip(url: str, start_s: float, duration_s: float, method: str, output_path: str) -> bool:
    """Extract a clip using specified method."""
    if method == "reencode":
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_s),
            "-i", url,
            "-t", str(duration_s),
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
    elif method == "copy":
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_s),
            "-i", url,
            "-t", str(duration_s),
            "-c", "copy",
            output_path,
        ]
    else:
        raise ValueError(f"Unknown method: {method}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.returncode == 0


def get_duration(path: str) -> float | None:
    """Get audio duration via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def main():
    video_id = sys.argv[1] if len(sys.argv) > 1 else "jNQXAC9IVRw"
    start_s = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    duration_s = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0

    print(f"Partial Download Spike")
    print(f"Video: {video_id}, Start: {start_s}s, Duration: {duration_s}s")
    print("=" * 60)

    # Get stream URL
    url = get_stream_url(video_id)
    if not url:
        print("Failed to get stream URL")
        return

    print(f"Stream URL obtained (length: {len(url)} chars)")
    print(f"URL preview: {url[:100]}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test re-encode method
        reencode_path = f"{tmpdir}/reencode.m4a"
        print(f"\n1. Re-encode method (ffmpeg -c:a aac):")
        t0 = time.time()
        ok = extract_clip(url, start_s, duration_s, "reencode", reencode_path)
        t1 = time.time()
        if ok:
            dur = get_duration(reencode_path)
            size = Path(reencode_path).stat().st_size
            print(f"   Success: duration={dur:.2f}s, size={size} bytes, took {t1-t0:.1f}s")
            print(f"   Expected: {duration_s}s, Accuracy: {abs(dur - duration_s):.3f}s off")
        else:
            print("   FAILED")

        # Test copy method
        copy_path = f"{tmpdir}/copy.m4a"
        print(f"\n2. Stream copy method (ffmpeg -c copy):")
        t0 = time.time()
        ok = extract_clip(url, start_s, duration_s, "copy", copy_path)
        t1 = time.time()
        if ok:
            dur = get_duration(copy_path)
            size = Path(copy_path).stat().st_size
            print(f"   Success: duration={dur:.2f}s, size={size} bytes, took {t1-t0:.1f}s")
            print(f"   Expected: {duration_s}s, Accuracy: {abs(dur - duration_s):.3f}s off")
        else:
            print("   FAILED")

    # Test URL expiry
    print(f"\n3. URL expiry test:")
    print(f"   URL obtained at: {time.strftime('%H:%M:%S')}")
    print(f"   Note: URLs typically expire after ~6 hours")


if __name__ == "__main__":
    main()
