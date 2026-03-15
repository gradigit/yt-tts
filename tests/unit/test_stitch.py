"""Tests for clip normalization, stitching, and silence generation."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from yt_tts.config import Config
from yt_tts.core.stitch import generate_silence, normalize_clip, stitch_clips

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="ffmpeg not installed"
)


def _make_sine(duration_s: float, freq: int, sample_rate: int, path: Path) -> Path:
    """Generate a sine wave audio file using ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration_s}:sample_rate={sample_rate}",
        "-ar", str(sample_rate),
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"ffmpeg sine generation failed: {result.stderr}"
    return path


def _get_duration_ms(path: Path) -> float:
    """Get audio duration in milliseconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"ffprobe failed: {result.stderr}"
    return float(result.stdout.strip()) * 1000


def _get_sample_rate(path: Path) -> int:
    """Get audio sample rate using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"ffprobe failed: {result.stderr}"
    return int(result.stdout.strip())


@pytest.fixture
def stitch_config(tmp_path):
    """Config with temporary paths for stitching tests."""
    return Config(
        db_path=tmp_path / "test.db",
        cache_dir=tmp_path / "cache",
        sample_rate=44100,
        crossfade_ms=0,
        no_crossfade=True,
        output_format="wav",
    )


@pytest.fixture
def sine_440(tmp_path):
    """A 1-second 440 Hz sine wave."""
    return _make_sine(1.0, 440, 44100, tmp_path / "sine_440.wav")


@pytest.fixture
def sine_880(tmp_path):
    """A 0.5-second 880 Hz sine wave."""
    return _make_sine(0.5, 880, 44100, tmp_path / "sine_880.wav")


class TestNormalizeClip:
    """Tests for normalize_clip."""

    def test_normalize_clip(self, sine_440, stitch_config):
        """Normalize a sine wave and verify output exists with correct sample rate."""
        normalized = normalize_clip(sine_440, stitch_config)

        assert normalized.is_file()
        assert normalized.stat().st_size > 0
        assert normalized.suffix == ".wav"

        actual_rate = _get_sample_rate(normalized)
        assert actual_rate == stitch_config.sample_rate

    def test_normalize_clip_custom_sample_rate(self, sine_440, tmp_path):
        """Normalize with a non-default sample rate."""
        config = Config(
            db_path=tmp_path / "test.db",
            cache_dir=tmp_path / "cache",
            sample_rate=22050,
        )
        normalized = normalize_clip(sine_440, config)

        assert normalized.is_file()
        actual_rate = _get_sample_rate(normalized)
        assert actual_rate == 22050


class TestStitchClips:
    """Tests for stitch_clips."""

    def test_stitch_two_clips(self, sine_440, sine_880, stitch_config):
        """Stitch two clips and verify output is longer than either input."""
        dur_a = _get_duration_ms(sine_440)
        dur_b = _get_duration_ms(sine_880)

        result = stitch_clips([sine_440, sine_880], [0], stitch_config)

        assert result.is_file()
        assert result.stat().st_size > 0

        dur_result = _get_duration_ms(result)
        assert dur_result > dur_a
        assert dur_result > dur_b
        # Combined should be approximately sum of inputs
        expected = dur_a + dur_b
        assert abs(dur_result - expected) < 200  # within 200ms tolerance

    def test_stitch_two_clips_with_gap(self, sine_440, sine_880, stitch_config):
        """Stitch two clips with a 500ms gap between them."""
        dur_a = _get_duration_ms(sine_440)
        dur_b = _get_duration_ms(sine_880)

        result = stitch_clips([sine_440, sine_880], [500], stitch_config)

        assert result.is_file()
        dur_result = _get_duration_ms(result)
        expected = dur_a + dur_b + 500
        assert abs(dur_result - expected) < 200

    def test_stitch_single_clip(self, sine_440, stitch_config):
        """Stitching a single clip just encodes it to output format."""
        result = stitch_clips([sine_440], [], stitch_config)

        assert result.is_file()
        assert result.stat().st_size > 0

    def test_stitch_empty_raises(self, stitch_config):
        """Stitching with no clips raises StitchError."""
        from yt_tts.exceptions import StitchError

        with pytest.raises(StitchError, match="No clips"):
            stitch_clips([], [], stitch_config)

    def test_stitch_gap_count_mismatch_raises(self, sine_440, sine_880, stitch_config):
        """Mismatched gap count raises StitchError."""
        from yt_tts.exceptions import StitchError

        with pytest.raises(StitchError, match="gaps"):
            stitch_clips([sine_440, sine_880], [0, 0], stitch_config)


class TestGenerateSilence:
    """Tests for generate_silence."""

    def test_generate_silence(self, stitch_config):
        """Generate 500ms of silence and verify duration with ffprobe."""
        silence = generate_silence(500, stitch_config)

        assert silence.is_file()
        assert silence.stat().st_size > 0
        assert silence.suffix == ".wav"

        dur = _get_duration_ms(silence)
        # Should be within 50ms of 500ms
        assert abs(dur - 500) < 50

    def test_generate_silence_short(self, stitch_config):
        """Generate 100ms of silence."""
        silence = generate_silence(100, stitch_config)

        assert silence.is_file()
        dur = _get_duration_ms(silence)
        assert abs(dur - 100) < 50

    def test_generate_silence_long(self, stitch_config):
        """Generate 2000ms of silence."""
        silence = generate_silence(2000, stitch_config)

        assert silence.is_file()
        dur = _get_duration_ms(silence)
        assert abs(dur - 2000) < 100
