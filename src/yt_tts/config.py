"""Configuration dataclass for yt-tts."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """All configuration for a yt-tts invocation."""

    # Paths
    db_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get(
                "YT_TTS_DB", Path.home() / ".local" / "share" / "yt-tts" / "transcripts.db"
            )
        )
    )
    cache_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("YT_TTS_CACHE", Path.home() / ".cache" / "yt-tts")
        )
    )
    output_path: Path | None = None  # None = auto-generate

    # Output
    output_format: str = "mp3"  # mp3 | wav
    output_stdout: bool = False  # --output -

    # Search
    search_limit: int = 20
    min_confidence: int = 128  # 0-255 threshold for word timestamps
    channel_filter: str | None = None  # --voice constraint

    # Chunking (no arbitrary limits — longer input just takes longer)
    max_input_words: int = 0  # 0 = no limit
    max_clips: int = 0  # 0 = no limit
    max_chunk_words: int = 0  # 0 = no limit (greedy longest-match), 1 = word-by-word Bumblebee mode
    chunk_search_timeout_s: float = 30.0
    chunk_resolve_timeout_s: float = 30.0

    # Extraction
    preferred_format: str = "140"  # m4a
    clip_padding_ms: int = 100
    audio_bitrate: str = "128k"

    # Tightness control — how clips are trimmed around word boundaries
    # "tight" = minimal padding, cuts close to word edges
    # "normal" = small padding for natural sound (default)
    # "loose" = generous padding, more context around words
    # Can also be an int (ms of padding around word boundaries)
    tightness: str | int = "normal"

    # ASR backend selection
    # "auto" = CUDA→faster-whisper, MLX→mlx-whisper, CPU→faster-whisper
    # "faster-whisper" = force faster-whisper
    # "mlx" = force mlx-whisper (Apple Silicon only)
    asr_backend: str = "auto"
    asr_model: str = "tiny"  # tiny, base, small, medium, large-v3

    # Stitching
    crossfade_ms: int = 50
    silence_gap_ms: int = 200  # gap for missing words
    loudnorm_target_i: float = -16.0
    loudnorm_target_tp: float = -1.5
    loudnorm_target_lra: float = 11.0
    sample_rate: int = 44100
    no_crossfade: bool = False

    # Rate limiting
    transcript_api_sleep_s: float = 2.0
    ytdlp_sleep_s: float = 2.0
    backoff_initial_s: float = 2.0
    backoff_multiplier: float = 2.0
    backoff_max_s: float = 60.0
    backoff_max_retries: int = 5

    # Circuit breaker
    circuit_breaker_threshold: int = 3
    circuit_breaker_pause_s: float = 300.0

    # Budgets
    max_caption_fetches: int = 50
    max_clip_downloads: int = 30

    # Timeouts
    total_timeout_s: float = 600.0  # 10 minutes

    # Parallelism
    max_workers: int = 3

    # Flags
    no_cache: bool = False
    json_output: bool = False
    verbose: bool = False

    # Live mode
    video_url: str | None = None  # --video

    # Alignment (V1: stubs only)
    align_method: str | None = None  # "stable-ts" | "whisperx"

    # Cookies (bypass rate limits with authenticated session)
    cookies_from_browser: str | None = None  # "chrome", "firefox", etc.
    cookies_file: Path | None = None  # path to Netscape-format cookies.txt

    # Bootstrap
    bootstrap_subset: int | None = None  # --subset N (number of parquet files)
