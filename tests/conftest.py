"""Shared test fixtures."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from yt_tts.config import Config


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory."""
    return tmp_path


@pytest.fixture
def config(tmp_path):
    """Provide a Config with temporary paths."""
    return Config(
        db_path=tmp_path / "test.db",
        cache_dir=tmp_path / "cache",
    )


@pytest.fixture
def sample_json3():
    """Sample json3 caption data with word-level timestamps."""
    return {
        "wireMagic": "pb3",
        "events": [
            {
                "tStartMs": 1000,
                "dDurationMs": 3000,
                "segs": [
                    {"utf8": "Hello", "tOffsetMs": 0, "acAsrConf": 200},
                    {"utf8": " world", "tOffsetMs": 500, "acAsrConf": 180},
                    {"utf8": " this", "tOffsetMs": 1000, "acAsrConf": 190},
                ],
            },
            {
                "tStartMs": 4000,
                "dDurationMs": 2000,
                "segs": [
                    {"utf8": "is", "tOffsetMs": 0, "acAsrConf": 210},
                    {"utf8": " a", "tOffsetMs": 300, "acAsrConf": 220},
                    {"utf8": " test", "tOffsetMs": 600, "acAsrConf": 250},
                ],
            },
        ],
    }


@pytest.fixture
def sample_json3_no_offsets():
    """Sample json3 without tOffsetMs (manual captions)."""
    return {
        "wireMagic": "pb3",
        "events": [
            {
                "tStartMs": 1000,
                "dDurationMs": 3000,
                "segs": [
                    {"utf8": "Hello world this"},
                ],
            },
            {
                "tStartMs": 4000,
                "dDurationMs": 2000,
                "segs": [
                    {"utf8": "is a test"},
                ],
            },
        ],
    }
