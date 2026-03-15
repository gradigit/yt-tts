"""Exception hierarchy for yt-tts."""


class YtTtsError(Exception):
    """Base exception for all yt-tts errors."""


class ConfigError(YtTtsError):
    """Invalid configuration."""


class DependencyError(YtTtsError):
    """Missing external dependency (ffmpeg, yt-dlp)."""


class IndexError_(YtTtsError):
    """Database or index operation failed."""


class CaptionFetchError(YtTtsError):
    """Failed to fetch captions for a video."""


class ClipExtractionError(YtTtsError):
    """Failed to extract audio clip from a video."""


class StitchError(YtTtsError):
    """Failed to stitch audio clips together."""


class BudgetExhaustedError(YtTtsError):
    """Rate limit or invocation budget exceeded."""


class TimeoutError_(YtTtsError):
    """Operation timed out."""
