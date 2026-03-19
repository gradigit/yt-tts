"""End-to-end integration tests. Require network + ffmpeg + yt-dlp."""

import shutil
import subprocess

import pytest

pytestmark = pytest.mark.integration


requires_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="ffmpeg not installed"
)
requires_ytdlp = pytest.mark.skipif(
    not shutil.which("yt-dlp"), reason="yt-dlp not installed"
)


@requires_ffmpeg
@requires_ytdlp
class TestLiveVideoSynthesis:
    """Tests using --video mode (no index needed)."""

    def test_single_phrase(self, tmp_path):
        """Synthesize a single phrase from a known video."""
        output = tmp_path / "test.mp3"
        result = subprocess.run(
            [
                "yt-tts",
                "--video", "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                "--output", str(output),
                "here we are",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0
        assert output.exists()
        assert output.stat().st_size > 0

    def test_no_match_returns_exit_2(self):
        """Non-existent phrase returns exit code 2."""
        result = subprocess.run(
            [
                "yt-tts",
                "--video", "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                "xyznonexistentphrase",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 2

    def test_json_output(self):
        """--json flag produces valid JSON."""
        import json

        result = subprocess.run(
            [
                "yt-tts",
                "--video", "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                "--json",
                "here we are",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "clips" in data
        assert "exit_code" in data
        assert data["exit_code"] == 0

    def test_wav_format(self, tmp_path):
        """--format wav produces a WAV file."""
        output = tmp_path / "test.wav"
        result = subprocess.run(
            [
                "yt-tts",
                "--video", "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                "--format", "wav",
                "--output", str(output),
                "here we are",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0
        assert output.exists()
        assert output.stat().st_size > 0


@requires_ffmpeg
@requires_ytdlp
class TestIndexWorkflow:
    """Tests for index add-video + search + synthesize."""

    def test_add_video_and_search(self, tmp_path):
        import os
        env = os.environ.copy()
        env["YT_TTS_DB"] = str(tmp_path / "test.db")

        # Add a video
        result = subprocess.run(
            ["yt-tts", "index", "add-video", "https://www.youtube.com/watch?v=jNQXAC9IVRw"],
            capture_output=True, text=True, timeout=60, env=env,
        )
        assert result.returncode == 0

        # Search for it
        result = subprocess.run(
            ["yt-tts", "index", "search", "elephants"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0
        assert "jNQXAC9IVRw" in result.stdout

        # Check stats
        result = subprocess.run(
            ["yt-tts", "index", "stats"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0
        assert "1" in result.stdout  # 1 transcript
