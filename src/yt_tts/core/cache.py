"""Caching for captions and audio clips."""

import json
import shutil
from pathlib import Path


class CaptionCache:
    """Stores json3 caption data on disk.

    Files are stored at {cache_dir}/captions/{video_id}.json3.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir / "captions"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, video_id: str) -> Path:
        return self._dir / f"{video_id}.json3"

    def has(self, video_id: str) -> bool:
        """Check if captions are cached for the given video."""
        return self._path(video_id).is_file()

    def get(self, video_id: str) -> dict | None:
        """Return cached json3 data, or None if not cached."""
        path = self._path(video_id)
        if not path.is_file():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def put(self, video_id: str, data: dict) -> None:
        """Store json3 data in cache."""
        path = self._path(video_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)


class ClipCache:
    """Stores extracted audio clips on disk.

    Files are stored at {cache_dir}/clips/{video_id}_{start_ms}_{end_ms}.m4a.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir / "clips"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, video_id: str, start_ms: int, end_ms: int) -> Path:
        return self._dir / f"{video_id}_{start_ms}_{end_ms}.m4a"

    def has(self, video_id: str, start_ms: int, end_ms: int) -> bool:
        """Check if a clip is cached."""
        return self._path(video_id, start_ms, end_ms).is_file()

    def get(self, video_id: str, start_ms: int, end_ms: int) -> Path | None:
        """Return path to cached clip, or None if not cached."""
        path = self._path(video_id, start_ms, end_ms)
        if not path.is_file():
            return None
        return path

    def put(self, video_id: str, start_ms: int, end_ms: int, source_path: Path) -> Path:
        """Copy source audio file into cache and return the cached path."""
        dest = self._path(video_id, start_ms, end_ms)
        shutil.copy2(source_path, dest)
        return dest


def clear_all_caches(cache_dir: Path) -> int:
    """Delete all cached files under cache_dir. Return count of files deleted."""
    count = 0
    for subdir_name in ("captions", "clips"):
        subdir = cache_dir / subdir_name
        if subdir.is_dir():
            for f in subdir.iterdir():
                if f.is_file():
                    f.unlink()
                    count += 1
    return count


def get_cache_stats(cache_dir: Path) -> dict:
    """Return cache statistics.

    Keys: caption_count, caption_size_mb, clip_count, clip_size_mb, total_size_mb.
    """
    caption_count = 0
    caption_size = 0
    clip_count = 0
    clip_size = 0

    captions_dir = cache_dir / "captions"
    if captions_dir.is_dir():
        for f in captions_dir.iterdir():
            if f.is_file():
                caption_count += 1
                caption_size += f.stat().st_size

    clips_dir = cache_dir / "clips"
    if clips_dir.is_dir():
        for f in clips_dir.iterdir():
            if f.is_file():
                clip_count += 1
                clip_size += f.stat().st_size

    caption_size_mb = round(caption_size / (1024 * 1024), 2)
    clip_size_mb = round(clip_size / (1024 * 1024), 2)

    return {
        "caption_count": caption_count,
        "caption_size_mb": caption_size_mb,
        "clip_count": clip_count,
        "clip_size_mb": clip_size_mb,
        "total_size_mb": round(caption_size_mb + clip_size_mb, 2),
    }
