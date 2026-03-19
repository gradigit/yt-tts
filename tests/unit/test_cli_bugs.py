"""Tests for CLI bug fixes: voice resolution, stdout output, verbose logging."""

import io
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestResolveChannelFilter:
    """Bug 1: --voice flag should resolve URLs to channel_id."""

    def test_plain_channel_id_passthrough(self):
        """A plain channel_id string is returned as-is."""
        from yt_tts.cli.commands.synthesize import _resolve_channel_filter
        assert _resolve_channel_filter("UCxxxxxxxx") == "UCxxxxxxxx"

    def test_plain_string_passthrough(self):
        """A non-URL string is returned as-is."""
        from yt_tts.cli.commands.synthesize import _resolve_channel_filter
        assert _resolve_channel_filter("some_channel") == "some_channel"

    def test_channel_url_extraction(self):
        """A youtube.com/channel/UCxxx URL extracts the channel ID."""
        from yt_tts.cli.commands.synthesize import _resolve_channel_filter
        result = _resolve_channel_filter("https://youtube.com/channel/UCxxxxxx123")
        assert result == "UCxxxxxx123"

    def test_handle_url_with_ytdlp_success(self):
        """A @handle URL resolves to UC... channel ID via yt-dlp."""
        from yt_tts.cli.commands.synthesize import _resolve_channel_filter
        mock_result = MagicMock()
        mock_result.stdout = "UCresolved123\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = _resolve_channel_filter("https://youtube.com/@testchannel")
        assert result == "UCresolved123"

    def test_handle_url_ytdlp_failure_falls_back(self):
        """When yt-dlp fails, falls back to the extracted handle."""
        from yt_tts.cli.commands.synthesize import _resolve_channel_filter
        with patch("subprocess.run", side_effect=Exception("yt-dlp not found")):
            result = _resolve_channel_filter("https://youtube.com/@mychannel")
        assert result == "mychannel"

    def test_bare_at_handle(self):
        """A bare @handle triggers resolution via yt-dlp."""
        from yt_tts.cli.commands.synthesize import _resolve_channel_filter
        # Starts with "@" so it triggers resolution
        mock_result = MagicMock()
        mock_result.stdout = "UCresolved999\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = _resolve_channel_filter("@mychannel")
        assert result == "UCresolved999"

    def test_bare_at_handle_ytdlp_fails(self):
        """A bare @handle falls back to handle name when yt-dlp fails."""
        from yt_tts.cli.commands.synthesize import _resolve_channel_filter
        with patch("subprocess.run", side_effect=Exception("not found")):
            result = _resolve_channel_filter("@mychannel")
        assert result == "mychannel"

    def test_handle_url_ytdlp_non_uc_result(self):
        """When yt-dlp returns non-UC result, falls back to handle."""
        from yt_tts.cli.commands.synthesize import _resolve_channel_filter
        mock_result = MagicMock()
        mock_result.stdout = "NA\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = _resolve_channel_filter("https://youtube.com/@testchannel")
        assert result == "testchannel"


class TestOutputStdout:
    """Bug 2: --output - should write audio to stdout."""

    @patch("yt_tts.core.pipeline._build_search_fn")
    @patch("yt_tts.core.pipeline._build_resolve_fn")
    @patch("yt_tts.core.stitch.stitch_clips")
    @patch("yt_tts.core.stitch.normalize_clip")
    def test_stdout_writes_bytes(
        self, mock_normalize, mock_stitch, mock_resolve_fn, mock_search_fn, tmp_path
    ):
        """When output_stdout is True, audio bytes go to sys.stdout.buffer."""
        from yt_tts.config import Config
        from yt_tts.core.pipeline import synthesize
        from yt_tts.types import ClipInfo, SearchResult

        # Create a fake audio file
        fake_audio = tmp_path / "fake.mp3"
        fake_audio.write_bytes(b"FAKE_AUDIO_DATA")

        search_result = SearchResult(
            video_id="v1", channel_id="", channel_name="", title="T",
            matched_text="hello", context_text="hello", rank_score=0.0,
            has_auto_captions=True,
        )
        clip = ClipInfo(
            video_id="v1", video_title="T", phrase="hello",
            start_ms=0, end_ms=1000, file_path=tmp_path / "clip.wav",
            confidence=0.9, timestamp_source="json3",
        )

        mock_search_fn.return_value = (lambda phrase: search_result, lambda phrase: [search_result])
        mock_resolve_fn.return_value = lambda phrase, result: clip
        mock_normalize.return_value = tmp_path / "norm.wav"
        mock_stitch.return_value = fake_audio

        config = Config(output_stdout=True)

        buf = io.BytesIO()
        with patch.object(sys, "stdout", new=MagicMock(buffer=buf)):
            result = synthesize("hello", config)

        assert result.output_path is None
        assert result.exit_code == 0
        assert buf.getvalue() == b"FAKE_AUDIO_DATA"


class TestVerboseLogging:
    """Bug 3: --verbose should only set yt_tts loggers to DEBUG."""

    def test_verbose_sets_yt_tts_debug(self):
        """With --verbose, yt_tts loggers are DEBUG, root is WARNING."""
        from yt_tts.cli.app import _dispatch_synthesize

        # We just need to check that logging is configured correctly,
        # not actually run synthesis. We'll patch run_synthesize.
        with patch("yt_tts.cli.commands.synthesize.run_synthesize", return_value=0):
            # Reset logging to defaults first
            root = logging.getLogger()
            old_level = root.level
            old_handlers = root.handlers[:]

            try:
                _dispatch_synthesize(["--verbose", "hello"])

                yt_tts_logger = logging.getLogger("yt_tts")
                assert yt_tts_logger.level == logging.DEBUG

                # Root logger should be WARNING (or the basicConfig level)
                assert root.level == logging.WARNING
            finally:
                root.setLevel(old_level)
                root.handlers = old_handlers
                logging.getLogger("yt_tts").setLevel(logging.NOTSET)

    def test_urllib3_stays_quiet(self):
        """With --verbose, urllib3 logger should NOT be set to DEBUG."""
        from yt_tts.cli.app import _dispatch_synthesize

        with patch("yt_tts.cli.commands.synthesize.run_synthesize", return_value=0):
            root = logging.getLogger()
            old_level = root.level
            old_handlers = root.handlers[:]

            try:
                _dispatch_synthesize(["--verbose", "hello"])

                urllib3_logger = logging.getLogger("urllib3")
                # urllib3 effective level should be WARNING or higher
                assert urllib3_logger.getEffectiveLevel() >= logging.WARNING
            finally:
                root.setLevel(old_level)
                root.handlers = old_handlers
                logging.getLogger("yt_tts").setLevel(logging.NOTSET)
