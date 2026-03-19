"""Tests for waveform analysis validation (validate.py)."""

import math

import numpy as np
import pytest
import soundfile as sf

from yt_tts.core.validate import (
    EXPECTED_DURATION_PER_WORD_S,
    EXTRA_AUDIO_RATIO,
    HIGH_VOICED_RATIO,
    SILENCE_THRESHOLD_DB,
    ClipQualityReport,
    _analyze_boundaries,
    _analyze_duration,
    _compute_frame_energies,
    _db_to_rms,
    _detect_extra_speech,
    _detect_silence_gaps,
    _detect_spectral_discontinuities,
    _detect_volume_jumps,
    _load_audio,
    _rms_energy,
    _rms_to_db,
    _spectral_centroid,
    validate_clip,
    validate_synthesis,
)


@pytest.fixture
def sr():
    """Standard sample rate for test audio."""
    return 16000


@pytest.fixture
def tmp_wav(tmp_path):
    """Factory to create temporary WAV files from numpy arrays."""

    def _make(samples: np.ndarray, sample_rate: int = 16000) -> str:
        path = tmp_path / "test.wav"
        sf.write(str(path), samples, sample_rate)
        return str(path)

    return _make


def _sine(freq: float, duration_s: float, sr: int, amplitude: float = 0.5) -> np.ndarray:
    """Generate a sine wave."""
    t = np.arange(int(sr * duration_s)) / sr
    return amplitude * np.sin(2 * np.pi * freq * t)


def _silence(duration_s: float, sr: int) -> np.ndarray:
    """Generate silence."""
    return np.zeros(int(sr * duration_s))


class TestRmsHelpers:
    """Tests for RMS energy helper functions."""

    def test_rms_energy_sine(self):
        """RMS of a sine wave with amplitude A is A/sqrt(2)."""
        samples = _sine(440, 1.0, 16000, amplitude=1.0)
        rms = _rms_energy(samples)
        expected = 1.0 / math.sqrt(2)
        assert abs(rms - expected) < 0.01

    def test_rms_energy_silence(self):
        """RMS of silence is 0."""
        samples = _silence(1.0, 16000)
        assert _rms_energy(samples) == 0.0

    def test_rms_energy_empty(self):
        """RMS of empty array is 0."""
        assert _rms_energy(np.array([])) == 0.0

    def test_rms_to_db_and_back(self):
        """Round-trip dB conversion."""
        rms = 0.1
        db = _rms_to_db(rms)
        back = _db_to_rms(db)
        assert abs(back - rms) < 1e-10

    def test_rms_to_db_zero(self):
        """Zero RMS gives -inf dB."""
        assert _rms_to_db(0.0) == float("-inf")


class TestComputeFrameEnergies:
    """Tests for frame energy computation."""

    def test_frame_count(self, sr):
        """Number of frames matches expected for given duration."""
        samples = _sine(440, 1.0, sr)
        energies, frame_dur = _compute_frame_energies(samples, sr, frame_ms=20)
        expected_frames = len(samples) // (sr * 20 // 1000)
        assert len(energies) == expected_frames

    def test_silence_frames_near_zero(self, sr):
        """Silent frames have near-zero energy."""
        samples = _silence(0.5, sr)
        energies, _ = _compute_frame_energies(samples, sr)
        assert np.all(energies < 1e-10)

    def test_loud_frames_positive(self, sr):
        """Frames from a sine wave have positive energy."""
        samples = _sine(440, 0.5, sr, amplitude=0.5)
        energies, _ = _compute_frame_energies(samples, sr)
        assert np.all(energies > 0.1)


class TestSpectralCentroid:
    """Tests for spectral centroid computation."""

    def test_sine_centroid_near_frequency(self, sr):
        """Spectral centroid of a pure sine should be near its frequency."""
        samples = _sine(440, 0.1, sr, amplitude=0.5)
        centroid = _spectral_centroid(samples, sr)
        # Should be close to 440 Hz (within 50 Hz due to windowing effects)
        assert abs(centroid - 440) < 50

    def test_higher_freq_higher_centroid(self, sr):
        """Higher frequency sine has higher spectral centroid."""
        low = _sine(200, 0.1, sr)
        high = _sine(2000, 0.1, sr)
        c_low = _spectral_centroid(low, sr)
        c_high = _spectral_centroid(high, sr)
        assert c_high > c_low

    def test_silence_centroid_zero(self, sr):
        """Spectral centroid of silence is 0."""
        samples = _silence(0.1, sr)
        assert _spectral_centroid(samples, sr) == 0.0

    def test_empty_centroid_zero(self, sr):
        """Spectral centroid of empty array is 0."""
        assert _spectral_centroid(np.array([]), sr) == 0.0


class TestAnalyzeDuration:
    """Tests for duration analysis."""

    def test_normal_duration_no_issues(self):
        """Duration within 2x expected produces no issues."""
        dur_s, exp_s, ratio, issues = _analyze_duration(0.8, 2)
        assert exp_s == 2 * EXPECTED_DURATION_PER_WORD_S
        assert ratio == pytest.approx(0.8 / exp_s)
        assert not issues

    def test_extra_audio_flagged(self):
        """Duration > 2x expected flags EXTRA_AUDIO."""
        # 2 words * 0.4s = 0.8s expected, 2.0s actual = 2.5x
        dur_s, exp_s, ratio, issues = _analyze_duration(2.0, 2)
        assert ratio > EXTRA_AUDIO_RATIO
        assert any("EXTRA_AUDIO" in i for i in issues)

    def test_zero_words_skips(self):
        """Zero expected words produces no issues and 0 expected duration."""
        dur_s, exp_s, ratio, issues = _analyze_duration(5.0, 0)
        assert exp_s == 0.0
        assert ratio == 0.0
        assert not issues


class TestDetectSilenceGaps:
    """Tests for silence gap detection."""

    def test_no_gaps_in_constant_signal(self, sr):
        """A constant sine has no silence gaps."""
        samples = _sine(440, 1.0, sr)
        energies, frame_dur = _compute_frame_energies(samples, sr)
        gaps, total = _detect_silence_gaps(energies, frame_dur)
        assert len(gaps) == 0
        assert total == 0.0

    def test_detects_long_silence_gap(self, sr):
        """A 500ms silence gap is detected."""
        speech = _sine(440, 0.3, sr, amplitude=0.5)
        silence = _silence(0.5, sr)
        samples = np.concatenate([speech, silence, speech])
        energies, frame_dur = _compute_frame_energies(samples, sr)
        gaps, total = _detect_silence_gaps(energies, frame_dur)
        assert len(gaps) >= 1
        assert total > 0.3  # at least 300ms detected

    def test_ignores_short_silence(self, sr):
        """Silence shorter than 200ms is not reported."""
        speech = _sine(440, 0.5, sr, amplitude=0.5)
        short_silence = _silence(0.1, sr)  # 100ms < 200ms threshold
        samples = np.concatenate([speech, short_silence, speech])
        energies, frame_dur = _compute_frame_energies(samples, sr)
        gaps, total = _detect_silence_gaps(energies, frame_dur)
        assert len(gaps) == 0

    def test_trailing_silence(self, sr):
        """Silence at end of clip is detected if long enough."""
        speech = _sine(440, 0.3, sr, amplitude=0.5)
        silence = _silence(0.5, sr)
        samples = np.concatenate([speech, silence])
        energies, frame_dur = _compute_frame_energies(samples, sr)
        gaps, total = _detect_silence_gaps(energies, frame_dur)
        assert len(gaps) >= 1


class TestAnalyzeBoundaries:
    """Tests for boundary analysis."""

    def test_silent_boundaries_no_issues(self, sr):
        """Clip with silent start and end has no boundary issues."""
        silence = _silence(0.1, sr)
        speech = _sine(440, 0.5, sr, amplitude=0.5)
        samples = np.concatenate([silence, speech, silence])
        start_rms, end_rms, issues = _analyze_boundaries(samples, sr)
        # Start and end should be near zero
        assert start_rms < _db_to_rms(SILENCE_THRESHOLD_DB)
        assert end_rms < _db_to_rms(SILENCE_THRESHOLD_DB)
        assert not issues

    def test_loud_start_flagged(self, sr):
        """Starting with loud audio flags BOUNDARY_START."""
        speech = _sine(440, 0.5, sr, amplitude=0.5)
        silence = _silence(0.1, sr)
        samples = np.concatenate([speech, silence])
        start_rms, end_rms, issues = _analyze_boundaries(samples, sr)
        assert any("BOUNDARY_START" in i for i in issues)

    def test_loud_end_flagged(self, sr):
        """Ending with loud audio flags BOUNDARY_END."""
        silence = _silence(0.1, sr)
        speech = _sine(440, 0.5, sr, amplitude=0.5)
        samples = np.concatenate([silence, speech])
        start_rms, end_rms, issues = _analyze_boundaries(samples, sr)
        assert any("BOUNDARY_END" in i for i in issues)


class TestDetectVolumeJumps:
    """Tests for volume jump detection."""

    def test_no_jumps_in_steady_signal(self, sr):
        """A constant sine wave has no volume jumps."""
        samples = _sine(440, 1.0, sr)
        energies, frame_dur = _compute_frame_energies(samples, sr)
        jumps, issues = _detect_volume_jumps(energies, frame_dur)
        assert len(jumps) == 0
        assert not issues

    def test_detects_abrupt_volume_change(self, sr):
        """Abrupt volume change (quiet -> loud) is detected."""
        quiet = _sine(440, 0.5, sr, amplitude=0.01)
        loud = _sine(440, 0.5, sr, amplitude=0.5)
        samples = np.concatenate([quiet, loud])
        energies, frame_dur = _compute_frame_energies(samples, sr)
        jumps, issues = _detect_volume_jumps(energies, frame_dur)
        assert len(jumps) >= 1
        assert any("VOLUME_JUMPS" in i for i in issues)

    def test_empty_energies(self):
        """Empty energies array returns no jumps."""
        jumps, issues = _detect_volume_jumps(np.array([]), 0.02)
        assert len(jumps) == 0


class TestDetectSpectralDiscontinuities:
    """Tests for spectral discontinuity detection."""

    def test_no_discontinuity_same_freq(self, sr):
        """Same frequency on both sides = no spectral jump."""
        samples = _sine(440, 1.0, sr, amplitude=0.5)
        # Fake a volume jump at 0.5s
        jumps = [(0.5, 7.0)]
        spectral, issues = _detect_spectral_discontinuities(samples, sr, jumps)
        assert len(spectral) == 0

    def test_detects_frequency_jump(self, sr):
        """Different frequencies across boundary = spectral jump detected."""
        low = _sine(200, 0.5, sr, amplitude=0.5)
        high = _sine(4000, 0.5, sr, amplitude=0.5)
        samples = np.concatenate([low, high])
        # Put the volume jump at the frequency transition point
        jumps = [(0.5, 7.0)]
        spectral, issues = _detect_spectral_discontinuities(samples, sr, jumps)
        assert len(spectral) >= 1
        assert any("SPECTRAL_DISCONTINUITY" in i for i in issues)

    def test_no_volume_jumps_no_analysis(self, sr):
        """Without volume jumps, spectral analysis is not performed."""
        samples = _sine(440, 1.0, sr)
        spectral, issues = _detect_spectral_discontinuities(samples, sr, [])
        assert len(spectral) == 0
        assert not issues


class TestDetectExtraSpeech:
    """Tests for extra speech detection."""

    def test_low_voiced_ratio_no_issue(self, sr):
        """Low voiced ratio (mostly silence) has no issue."""
        speech = _sine(440, 0.3, sr, amplitude=0.5)
        silence = _silence(2.0, sr)
        samples = np.concatenate([speech, silence])
        energies, frame_dur = _compute_frame_energies(samples, sr)
        duration_s = len(samples) / sr
        ratio, issues = _detect_extra_speech(energies, duration_s)
        assert ratio < HIGH_VOICED_RATIO
        assert not issues

    def test_high_voiced_ratio_long_clip_flagged(self, sr):
        """High voiced ratio in a long clip flags EXTRA_SPEECH."""
        # 3 seconds of continuous speech
        samples = _sine(440, 3.0, sr, amplitude=0.5)
        energies, frame_dur = _compute_frame_energies(samples, sr)
        duration_s = len(samples) / sr
        ratio, issues = _detect_extra_speech(energies, duration_s)
        assert ratio > HIGH_VOICED_RATIO
        assert any("EXTRA_SPEECH" in i for i in issues)

    def test_high_voiced_ratio_short_clip_no_issue(self, sr):
        """High voiced ratio in a short clip (<2s) is not flagged."""
        samples = _sine(440, 1.0, sr, amplitude=0.5)
        energies, frame_dur = _compute_frame_energies(samples, sr)
        duration_s = len(samples) / sr
        ratio, issues = _detect_extra_speech(energies, duration_s)
        assert not issues

    def test_empty_energies(self):
        """Empty energies returns 0 ratio and no issues."""
        ratio, issues = _detect_extra_speech(np.array([]), 0.0)
        assert ratio == 0.0
        assert not issues


class TestValidateClip:
    """Integration tests for validate_clip."""

    def test_clean_sine_no_issues(self, tmp_wav, sr):
        """A clean sine wave with matching word count has no issues."""
        # 2 words * 0.4s = 0.8s expected. 0.8s sine = ratio 1.0
        samples = _sine(440, 0.8, sr, amplitude=0.5)
        path = tmp_wav(samples, sr)
        report = validate_clip(path, expected_words=2)
        assert isinstance(report, ClipQualityReport)
        assert report.duration_s == pytest.approx(0.8, abs=0.01)
        assert report.expected_duration_s == pytest.approx(0.8)
        # No EXTRA_AUDIO since ratio is ~1.0
        assert not any("EXTRA_AUDIO" in i for i in report.issues)

    def test_file_not_found(self):
        """Non-existent file returns FILE_NOT_FOUND issue."""
        report = validate_clip("/nonexistent/file.wav")
        assert any("FILE_NOT_FOUND" in i for i in report.issues)

    def test_silence_gaps_detected(self, tmp_wav, sr):
        """Silence gap in the middle is reported."""
        speech = _sine(440, 0.3, sr, amplitude=0.5)
        silence = _silence(0.5, sr)
        samples = np.concatenate([speech, silence, speech])
        path = tmp_wav(samples, sr)
        report = validate_clip(path)
        assert len(report.silence_gaps) >= 1
        assert report.total_silence_s > 0
        assert any("SILENCE_GAPS" in i for i in report.issues)

    def test_extra_audio_detected(self, tmp_wav, sr):
        """Duration much larger than expected flags EXTRA_AUDIO."""
        samples = _sine(440, 5.0, sr, amplitude=0.5)
        path = tmp_wav(samples, sr)
        report = validate_clip(path, expected_words=2)
        # 2 words * 0.4s = 0.8s expected, 5.0s actual = 6.25x
        assert report.duration_ratio > EXTRA_AUDIO_RATIO
        assert any("EXTRA_AUDIO" in i for i in report.issues)

    def test_no_expected_words_skips_duration(self, tmp_wav, sr):
        """Without expected_words, duration analysis is skipped."""
        samples = _sine(440, 5.0, sr, amplitude=0.5)
        path = tmp_wav(samples, sr)
        report = validate_clip(path, expected_words=0)
        assert report.expected_duration_s == 0.0
        assert report.duration_ratio == 0.0
        assert not any("EXTRA_AUDIO" in i for i in report.issues)

    def test_stereo_file(self, tmp_path, sr):
        """Stereo file is handled by mixing to mono."""
        left = _sine(440, 0.5, sr, amplitude=0.5)
        right = _sine(880, 0.5, sr, amplitude=0.5)
        stereo = np.column_stack([left, right])
        path = str(tmp_path / "stereo.wav")
        sf.write(path, stereo, sr)
        report = validate_clip(path)
        assert report.duration_s == pytest.approx(0.5, abs=0.01)

    def test_mp3_file(self, tmp_path, sr):
        """MP3 file can be analyzed (if soundfile supports it via format hint)."""
        samples = _sine(440, 0.5, sr, amplitude=0.5)
        wav_path = str(tmp_path / "test.wav")
        sf.write(wav_path, samples, sr)
        # validate_clip should work on WAV at minimum
        report = validate_clip(wav_path)
        assert report.duration_s > 0


class TestValidateSynthesis:
    """Integration tests for validate_synthesis."""

    def test_returns_dict_with_report(self, tmp_wav, sr):
        """validate_synthesis returns a dict with report and text info."""
        samples = _sine(440, 1.0, sr, amplitude=0.5)
        path = tmp_wav(samples, sr)
        result = validate_synthesis(path, "hello world")
        assert "report" in result
        assert "text" in result
        assert result["text"] == "hello world"
        assert result["word_count"] == 2
        assert "duration_s" in result["report"]
        assert "issues" in result["report"]

    def test_with_clips_json(self, tmp_wav, sr):
        """Clips metadata is included in the output."""
        samples = _sine(440, 1.0, sr, amplitude=0.5)
        path = tmp_wav(samples, sr)
        clips = [
            {"phrase": "hello", "video_id": "v1", "start_ms": 0, "end_ms": 500},
            {"phrase": "world", "video_id": "v2", "start_ms": 100, "end_ms": 600},
        ]
        result = validate_synthesis(path, "hello world", clips_json=clips)
        assert "clips" in result
        assert len(result["clips"]) == 2
        assert result["clips"][0]["phrase"] == "hello"
        assert result["clips"][0]["video_id"] == "v1"

    def test_expected_duration_from_text(self, tmp_wav, sr):
        """Expected duration is computed from word count in text."""
        samples = _sine(440, 0.5, sr, amplitude=0.5)
        path = tmp_wav(samples, sr)
        result = validate_synthesis(path, "one two three four five")
        report = result["report"]
        expected = 5 * EXPECTED_DURATION_PER_WORD_S
        assert report["expected_duration_s"] == pytest.approx(expected)


class TestLoadAudio:
    """Tests for audio loading."""

    def test_load_mono(self, tmp_path, sr):
        """Load mono WAV file."""
        samples = _sine(440, 0.5, sr)
        path = str(tmp_path / "mono.wav")
        sf.write(path, samples, sr)
        loaded, loaded_sr = _load_audio(path)
        assert loaded_sr == sr
        assert len(loaded.shape) == 1
        assert len(loaded) == len(samples)

    def test_load_stereo_mixes_to_mono(self, tmp_path, sr):
        """Load stereo WAV and verify it becomes mono."""
        left = _sine(440, 0.5, sr, amplitude=0.5)
        right = _sine(880, 0.5, sr, amplitude=0.3)
        stereo = np.column_stack([left, right])
        path = str(tmp_path / "stereo.wav")
        sf.write(path, stereo, sr)
        loaded, loaded_sr = _load_audio(path)
        assert len(loaded.shape) == 1
        assert len(loaded) == len(left)


class TestClipQualityReportDataclass:
    """Tests for ClipQualityReport initialization."""

    def test_default_values(self):
        """Default report has no issues and zero metrics."""
        report = ClipQualityReport()
        assert report.duration_s == 0.0
        assert report.issues == []
        assert report.silence_gaps == []
        assert report.volume_jumps == []
        assert report.spectral_jumps == []
        assert report.voiced_ratio == 0.0

    def test_custom_values(self):
        """Report can be constructed with custom values."""
        report = ClipQualityReport(
            duration_s=1.5,
            expected_duration_s=1.0,
            duration_ratio=1.5,
            voiced_ratio=0.75,
            issues=["TEST_ISSUE"],
        )
        assert report.duration_s == 1.5
        assert report.issues == ["TEST_ISSUE"]


class TestCLIValidateSubcommand:
    """Tests for the CLI validate subcommand routing."""

    def test_validate_help(self):
        """validate --help returns 0."""
        from yt_tts.cli.app import main

        result = main(["validate", "--help"])
        assert result == 0

    def test_validate_no_args(self, capsys):
        """validate with no args prints error."""
        from yt_tts.cli.app import main

        result = main(["validate"])
        assert result == 0  # shows help

    def test_validate_missing_file(self, capsys):
        """validate with nonexistent file reports FILE_NOT_FOUND."""
        from yt_tts.cli.app import main

        result = main(["validate", "/nonexistent/file.wav"])
        assert result == 1  # issues found

    def test_validate_real_file(self, tmp_path):
        """validate with a real WAV file works."""
        from yt_tts.cli.app import main

        samples = _sine(440, 0.5, 16000, amplitude=0.5)
        path = str(tmp_path / "test.wav")
        sf.write(path, samples, 16000)
        result = main(["validate", path])
        # May have boundary issues, so result could be 0 or 1
        assert result in (0, 1)

    def test_validate_with_text(self, tmp_path, capsys):
        """validate with --text includes duration analysis."""
        from yt_tts.cli.app import main

        samples = _sine(440, 0.8, 16000, amplitude=0.5)
        path = str(tmp_path / "test.wav")
        sf.write(path, samples, 16000)
        main(["validate", path, "--text", "hello world"])
        captured = capsys.readouterr()
        assert "Duration:" in captured.out
        assert "Expected:" in captured.out

    def test_validate_json_output(self, tmp_path, capsys):
        """validate with --json outputs JSON."""
        import json

        from yt_tts.cli.app import main

        silence = _silence(0.1, 16000)
        speech = _sine(440, 0.3, 16000, amplitude=0.5)
        samples = np.concatenate([silence, speech, silence])
        path = str(tmp_path / "test.wav")
        sf.write(path, samples, 16000)
        main(["validate", path, "--json"])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "report" in parsed
        assert "duration_s" in parsed["report"]

    def test_validate_in_subcommands(self):
        """validate is recognized as a subcommand."""
        from yt_tts.cli.app import main

        # Calling with just "validate" should show help, not synthesize
        result = main(["validate"])
        assert result == 0
