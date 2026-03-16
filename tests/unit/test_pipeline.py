"""Tests for the synthesis pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_tts.config import Config
from yt_tts.types import SynthesisResult


class TestSynthesize:
    def test_empty_input(self):
        from yt_tts.core.pipeline import synthesize
        config = Config()
        result = synthesize("", config)
        assert result.exit_code == 2
        assert result.output_path is None

    def test_too_long_input(self):
        from yt_tts.core.pipeline import synthesize
        config = Config(max_input_words=5)
        result = synthesize("one two three four five six seven", config)
        assert result.exit_code == 2

    @patch("yt_tts.core.pipeline._build_search_fn")
    @patch("yt_tts.core.pipeline._build_resolve_fn")
    def test_no_matches(self, mock_resolve_fn, mock_search_fn):
        from yt_tts.core.pipeline import synthesize

        mock_search_fn.return_value = (lambda phrase: None, lambda phrase: [])
        mock_resolve_fn.return_value = lambda phrase, result: None

        config = Config()
        result = synthesize("hello world", config)
        assert result.exit_code == 2
        assert len(result.missing_words) > 0


class TestMakeOutputPath:
    def test_default_path(self):
        from yt_tts.core.pipeline import _make_output_path
        config = Config()
        path = _make_output_path("hello world", config)
        assert path.suffix == ".mp3"
        assert path.name.startswith("yt-tts-")
        assert len(path.stem.split("-")[-1]) == 8  # hash prefix

    def test_custom_path(self):
        from yt_tts.core.pipeline import _make_output_path
        config = Config(output_path=Path("/tmp/custom.mp3"))
        path = _make_output_path("hello world", config)
        assert path == Path("/tmp/custom.mp3")

    def test_deterministic(self):
        from yt_tts.core.pipeline import _make_output_path
        config = Config()
        path1 = _make_output_path("hello world", config)
        path2 = _make_output_path("hello world", config)
        assert path1 == path2

    def test_wav_format(self):
        from yt_tts.core.pipeline import _make_output_path
        config = Config(output_format="wav")
        path = _make_output_path("hello world", config)
        assert path.suffix == ".wav"
