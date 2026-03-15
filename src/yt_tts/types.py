"""Core data types for yt-tts."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WordTimestamp:
    """A single word with timing and confidence from json3 captions."""

    word: str
    start_ms: int
    end_ms: int
    confidence: int  # 0-255 from acAsrConf


@dataclass(frozen=True)
class TimeRange:
    """A time range within a video."""

    start_ms: int
    end_ms: int
    confidence: float  # average confidence of matched words


@dataclass(frozen=True)
class SearchResult:
    """A transcript search hit from the FTS5 index."""

    video_id: str
    channel_id: str
    channel_name: str
    title: str
    matched_text: str
    context_text: str  # ~50 chars before/after match for display
    rank_score: float  # FTS5 rank
    has_auto_captions: bool  # prefer for json3 word-level timestamps


@dataclass(frozen=True)
class ClipInfo:
    """Metadata and file path for an extracted audio clip."""

    video_id: str
    video_title: str
    phrase: str
    start_ms: int
    end_ms: int
    file_path: Path
    confidence: float
    timestamp_source: str  # "json3" | "segment"


@dataclass
class ChunkPlan:
    """Result of the Bumblebee chunking phase."""

    chunks: list[str] = field(default_factory=list)
    clips: list[ClipInfo | None] = field(default_factory=list)  # None = missing
    missing_words: list[str] = field(default_factory=list)
    search_results: list[SearchResult | None] = field(default_factory=list)


@dataclass(frozen=True)
class SynthesisResult:
    """Final result of the full synthesis pipeline."""

    output_path: Path | None
    duration_ms: int
    clips: list[ClipInfo]
    missing_words: list[str]
    exit_code: int  # 0=full success, 1=partial, 2=no matches, 3=system error
