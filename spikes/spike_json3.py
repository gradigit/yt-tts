#!/usr/bin/env python3
"""Spike: Validate json3 caption format and tOffsetMs presence.

Tests auto-generated captions from diverse video types to confirm
word-level timestamps (tOffsetMs, acAsrConf) are available.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Diverse test videos (educational, podcast, tech talk, speech)
TEST_VIDEOS = [
    "dQw4w9WgXcQ",  # Music video (likely auto-captions)
    "jNQXAC9IVRw",  # "Me at the zoo" - first YouTube video
    "9bZkp7q19f0",  # PSY - Gangnam Style
]


def fetch_json3(video_id: str) -> dict | None:
    """Fetch json3 captions for a video."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                "yt-dlp",
                "--write-auto-subs",
                "--sub-format", "json3",
                "--sub-lang", "en",
                "--skip-download",
                "--output", f"{tmpdir}/%(id)s",
                "--", video_id,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Find the json3 file
        json3_files = list(Path(tmpdir).glob("*.json3"))
        if not json3_files:
            print(f"  No json3 file generated for {video_id}")
            print(f"  stdout: {result.stdout[:200]}")
            print(f"  stderr: {result.stderr[:200]}")
            return None

        with open(json3_files[0]) as f:
            return json.load(f)


def analyze_json3(video_id: str, data: dict) -> None:
    """Analyze json3 structure and report on tOffsetMs presence."""
    print(f"\n{'='*60}")
    print(f"Video: {video_id}")
    print(f"wireMagic: {data.get('wireMagic', 'MISSING')}")

    events = data.get("events", [])
    print(f"Total events: {len(events)}")

    events_with_segs = 0
    events_without_segs = 0
    total_segs = 0
    segs_with_offset = 0
    segs_without_offset = 0
    segs_with_conf = 0
    whitespace_only = 0

    for event in events:
        segs = event.get("segs")
        if not segs:
            events_without_segs += 1
            continue

        events_with_segs += 1
        for seg in segs:
            total_segs += 1
            text = seg.get("utf8", "")

            if text.strip() == "":
                whitespace_only += 1
                continue

            if "tOffsetMs" in seg:
                segs_with_offset += 1
            else:
                segs_without_offset += 1

            if "acAsrConf" in seg:
                segs_with_conf += 1

    print(f"Events with segs: {events_with_segs}")
    print(f"Events without segs: {events_without_segs}")
    print(f"Total segments: {total_segs}")
    print(f"Segments with tOffsetMs: {segs_with_offset}")
    print(f"Segments without tOffsetMs: {segs_without_offset}")
    print(f"Segments with acAsrConf: {segs_with_conf}")
    print(f"Whitespace-only segments: {whitespace_only}")

    if total_segs > 0:
        pct = segs_with_offset / (total_segs - whitespace_only) * 100 if (total_segs - whitespace_only) > 0 else 0
        print(f"tOffsetMs coverage: {pct:.1f}%")

    # Show first few segments as sample
    print("\nSample segments (first event with segs):")
    for event in events:
        segs = event.get("segs")
        if segs:
            print(f"  tStartMs={event.get('tStartMs')}, dDurationMs={event.get('dDurationMs')}")
            for seg in segs[:5]:
                print(f"    {seg}")
            break


def main():
    print("json3 Caption Format Spike")
    print("=" * 60)

    video_ids = sys.argv[1:] if len(sys.argv) > 1 else TEST_VIDEOS

    for video_id in video_ids:
        try:
            data = fetch_json3(video_id)
            if data:
                analyze_json3(video_id, data)

                # Save for fixture use
                with open(f"spikes/{video_id}.json3", "w") as f:
                    json.dump(data, f, indent=2)
                print(f"\n  Saved to spikes/{video_id}.json3")
        except Exception as e:
            print(f"\n  ERROR for {video_id}: {e}")


if __name__ == "__main__":
    main()
