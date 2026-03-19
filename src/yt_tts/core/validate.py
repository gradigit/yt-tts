"""Waveform analysis validation for synthesized audio clips.

Analyzes audio files (MP3/WAV) to detect quality issues that ASR alone cannot
catch: silence gaps, boundary truncation, spectral discontinuities, extra speech,
and duration anomalies.

Dependencies: numpy, soundfile (both already installed with yt-tts).
"""

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# --- Constants ---

FRAME_MS = 20  # analysis frame size in milliseconds
SILENCE_THRESHOLD_DB = -40.0  # RMS energy below this = silence
SILENCE_GAP_MIN_MS = 200  # minimum gap duration to report
BOUNDARY_WINDOW_MS = 50  # window at start/end for boundary analysis
VOLUME_JUMP_THRESHOLD_DB = 6.0  # minimum dB jump to flag
SPECTRAL_CENTROID_JUMP_HZ = 500.0  # minimum spectral centroid difference to flag
EXPECTED_DURATION_PER_WORD_S = 0.4  # expected seconds per word
EXTRA_AUDIO_RATIO = 2.0  # flag if actual > 2x expected
HIGH_VOICED_RATIO = 0.85  # above this = likely extra speech


@dataclass
class ClipQualityReport:
    """Quality analysis report for an audio clip."""

    duration_s: float = 0.0
    expected_duration_s: float = 0.0
    duration_ratio: float = 0.0
    silence_gaps: list[tuple[float, float]] = field(default_factory=list)
    total_silence_s: float = 0.0
    boundary_start_rms: float = 0.0
    boundary_end_rms: float = 0.0
    volume_jumps: list[tuple[float, float]] = field(default_factory=list)
    spectral_jumps: list[tuple[float, float]] = field(default_factory=list)
    voiced_ratio: float = 0.0
    issues: list[str] = field(default_factory=list)


def _load_audio(audio_path: str) -> tuple[np.ndarray, int]:
    """Load audio file and convert to mono float64 samples.

    Returns:
        Tuple of (samples_array, sample_rate).
    """
    data, sr = sf.read(audio_path, dtype="float64", always_2d=True)
    # Mix to mono by averaging channels
    if data.shape[1] > 1:
        data = np.mean(data, axis=1)
    else:
        data = data[:, 0]
    return data, sr


def _rms_energy(samples: np.ndarray) -> float:
    """Compute RMS energy of a sample array. Returns 0.0 for empty/zero arrays."""
    if len(samples) == 0:
        return 0.0
    rms = np.sqrt(np.mean(samples ** 2))
    return float(rms)


def _rms_to_db(rms: float) -> float:
    """Convert RMS amplitude to dB. Returns -inf for zero."""
    if rms <= 0.0:
        return float("-inf")
    return 20.0 * math.log10(rms)


def _db_to_rms(db: float) -> float:
    """Convert dB to RMS amplitude."""
    return 10.0 ** (db / 20.0)


def _compute_frame_energies(
    samples: np.ndarray, sr: int, frame_ms: int = FRAME_MS
) -> tuple[np.ndarray, float]:
    """Compute RMS energy per frame.

    Returns:
        Tuple of (rms_per_frame array, frame_duration_s).
    """
    frame_size = int(sr * frame_ms / 1000)
    if frame_size == 0:
        return np.array([]), frame_ms / 1000.0

    n_frames = len(samples) // frame_size
    if n_frames == 0:
        return np.array([_rms_energy(samples)]), frame_ms / 1000.0

    # Reshape into frames and compute RMS per frame
    trimmed = samples[: n_frames * frame_size]
    frames = trimmed.reshape(n_frames, frame_size)
    energies = np.sqrt(np.mean(frames ** 2, axis=1))

    return energies, frame_ms / 1000.0


def _spectral_centroid(samples: np.ndarray, sr: int) -> float:
    """Compute spectral centroid of a sample window using numpy FFT.

    Returns the centroid frequency in Hz, or 0.0 for silent/empty input.
    """
    if len(samples) == 0:
        return 0.0

    # Apply Hann window to reduce spectral leakage
    window = np.hanning(len(samples))
    windowed = samples * window

    # Compute magnitude spectrum (positive frequencies only)
    spectrum = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sr)

    # Avoid division by zero
    total_magnitude = np.sum(spectrum)
    if total_magnitude == 0.0:
        return 0.0

    centroid = float(np.sum(freqs * spectrum) / total_magnitude)
    return centroid


def _analyze_duration(
    duration_s: float, expected_words: int
) -> tuple[float, float, float, list[str]]:
    """Analyze clip duration against expected word count.

    Returns:
        (duration_s, expected_duration_s, duration_ratio, issues)
    """
    issues = []
    if expected_words <= 0:
        return duration_s, 0.0, 0.0, issues

    expected_s = expected_words * EXPECTED_DURATION_PER_WORD_S
    ratio = duration_s / expected_s if expected_s > 0 else 0.0

    if ratio > EXTRA_AUDIO_RATIO:
        issues.append(
            f"EXTRA_AUDIO: clip duration ({duration_s:.2f}s) is "
            f"{ratio:.1f}x expected ({expected_s:.2f}s for {expected_words} words)"
        )

    return duration_s, expected_s, ratio, issues


def _detect_silence_gaps(
    frame_energies: np.ndarray, frame_duration_s: float
) -> tuple[list[tuple[float, float]], float]:
    """Find silence gaps longer than SILENCE_GAP_MIN_MS.

    Returns:
        (list of (start_s, end_s) tuples, total_silence_s)
    """
    threshold_rms = _db_to_rms(SILENCE_THRESHOLD_DB)
    silent_mask = frame_energies < threshold_rms

    gaps = []
    total_silence = 0.0
    gap_start = None
    min_frames = int(SILENCE_GAP_MIN_MS / (frame_duration_s * 1000))
    if min_frames < 1:
        min_frames = 1

    i = 0
    while i < len(silent_mask):
        if silent_mask[i]:
            if gap_start is None:
                gap_start = i
        else:
            if gap_start is not None:
                gap_len = i - gap_start
                if gap_len >= min_frames:
                    start_s = gap_start * frame_duration_s
                    end_s = i * frame_duration_s
                    gaps.append((round(start_s, 4), round(end_s, 4)))
                    total_silence += end_s - start_s
                gap_start = None
        i += 1

    # Handle gap that extends to end of clip
    if gap_start is not None:
        gap_len = len(silent_mask) - gap_start
        if gap_len >= min_frames:
            start_s = gap_start * frame_duration_s
            end_s = len(silent_mask) * frame_duration_s
            gaps.append((round(start_s, 4), round(end_s, 4)))
            total_silence += end_s - start_s

    return gaps, round(total_silence, 4)


def _analyze_boundaries(
    samples: np.ndarray, sr: int
) -> tuple[float, float, list[str]]:
    """Measure RMS energy at clip boundaries.

    Returns:
        (boundary_start_rms, boundary_end_rms, issues)
    """
    issues = []
    window_samples = int(sr * BOUNDARY_WINDOW_MS / 1000)

    if len(samples) >= window_samples:
        start_rms = _rms_energy(samples[:window_samples])
    else:
        start_rms = _rms_energy(samples)

    if len(samples) >= window_samples:
        end_rms = _rms_energy(samples[-window_samples:])
    else:
        end_rms = _rms_energy(samples)

    threshold_rms = _db_to_rms(SILENCE_THRESHOLD_DB)

    if start_rms > threshold_rms:
        start_db = _rms_to_db(start_rms)
        issues.append(
            f"BOUNDARY_START: non-silent start ({start_db:.1f}dB), "
            f"clip may begin mid-word"
        )
    if end_rms > threshold_rms:
        end_db = _rms_to_db(end_rms)
        issues.append(
            f"BOUNDARY_END: non-silent end ({end_db:.1f}dB), "
            f"clip may end mid-word"
        )

    return float(start_rms), float(end_rms), issues


def _detect_volume_jumps(
    frame_energies: np.ndarray, frame_duration_s: float
) -> tuple[list[tuple[float, float]], list[str]]:
    """Detect sudden volume jumps that indicate stitch boundaries.

    Returns:
        (list of (position_s, jump_db) tuples, issues)
    """
    issues = []
    jumps = []

    if len(frame_energies) < 2:
        return jumps, issues

    for i in range(1, len(frame_energies)):
        prev_rms = frame_energies[i - 1]
        curr_rms = frame_energies[i]

        # Skip if either is zero/near-zero (avoid -inf dB)
        if prev_rms <= 0.0 or curr_rms <= 0.0:
            continue

        prev_db = _rms_to_db(prev_rms)
        curr_db = _rms_to_db(curr_rms)
        jump_db = abs(curr_db - prev_db)

        if jump_db > VOLUME_JUMP_THRESHOLD_DB:
            position_s = i * frame_duration_s
            jumps.append((round(position_s, 4), round(jump_db, 2)))

    if jumps:
        issues.append(
            f"VOLUME_JUMPS: {len(jumps)} volume jump(s) > {VOLUME_JUMP_THRESHOLD_DB}dB detected"
        )

    return jumps, issues


def _detect_spectral_discontinuities(
    samples: np.ndarray,
    sr: int,
    volume_jumps: list[tuple[float, float]],
) -> tuple[list[tuple[float, float]], list[str]]:
    """At each detected volume jump, compare spectral centroid before and after.

    Returns:
        (list of (position_s, centroid_diff_hz) tuples, issues)
    """
    issues = []
    spectral_jumps = []

    # Use a 50ms analysis window on each side of the boundary
    window_samples = int(sr * BOUNDARY_WINDOW_MS / 1000)

    for position_s, _ in volume_jumps:
        center_sample = int(position_s * sr)

        before_start = max(0, center_sample - window_samples)
        before_end = center_sample
        after_start = center_sample
        after_end = min(len(samples), center_sample + window_samples)

        if before_end <= before_start or after_end <= after_start:
            continue

        centroid_before = _spectral_centroid(samples[before_start:before_end], sr)
        centroid_after = _spectral_centroid(samples[after_start:after_end], sr)

        diff = abs(centroid_after - centroid_before)
        if diff > SPECTRAL_CENTROID_JUMP_HZ:
            spectral_jumps.append((round(position_s, 4), round(diff, 1)))

    if spectral_jumps:
        issues.append(
            f"SPECTRAL_DISCONTINUITY: {len(spectral_jumps)} spectral jump(s) "
            f"> {SPECTRAL_CENTROID_JUMP_HZ}Hz detected"
        )

    return spectral_jumps, issues


def _detect_extra_speech(
    frame_energies: np.ndarray, duration_s: float
) -> tuple[float, list[str]]:
    """Compute voiced frame ratio using energy-based voice activity detection.

    Returns:
        (voiced_ratio, issues)
    """
    issues = []
    if len(frame_energies) == 0:
        return 0.0, issues

    threshold_rms = _db_to_rms(SILENCE_THRESHOLD_DB)
    voiced_frames = np.sum(frame_energies >= threshold_rms)
    total_frames = len(frame_energies)
    voiced_ratio = float(voiced_frames / total_frames)

    if voiced_ratio > HIGH_VOICED_RATIO and duration_s > 2.0:
        issues.append(
            f"EXTRA_SPEECH: high voiced ratio ({voiced_ratio:.2f}) in a "
            f"{duration_s:.1f}s clip suggests extra speech beyond target"
        )

    return round(voiced_ratio, 4), issues


def validate_clip(audio_path: str, expected_words: int = 0) -> ClipQualityReport:
    """Analyze an audio clip for quality issues.

    Args:
        audio_path: Path to an MP3 or WAV file.
        expected_words: Number of words expected in the clip. If 0, duration
            analysis is skipped.

    Returns:
        A ClipQualityReport with all quality metrics and detected issues.
    """
    path = Path(audio_path)
    if not path.is_file():
        report = ClipQualityReport()
        report.issues.append(f"FILE_NOT_FOUND: {audio_path}")
        return report

    try:
        samples, sr = _load_audio(audio_path)
    except Exception as exc:
        report = ClipQualityReport()
        report.issues.append(f"LOAD_ERROR: {exc}")
        return report

    duration_s = len(samples) / sr if sr > 0 else 0.0

    # 1. Duration analysis
    dur_s, expected_s, dur_ratio, dur_issues = _analyze_duration(duration_s, expected_words)

    # 2. Silence detection
    frame_energies, frame_dur_s = _compute_frame_energies(samples, sr)
    silence_gaps, total_silence = _detect_silence_gaps(frame_energies, frame_dur_s)

    # 3. Boundary analysis
    start_rms, end_rms, boundary_issues = _analyze_boundaries(samples, sr)

    # 4. Volume jump detection
    volume_jumps, volume_issues = _detect_volume_jumps(frame_energies, frame_dur_s)

    # 5. Spectral discontinuity detection
    spectral_jumps, spectral_issues = _detect_spectral_discontinuities(
        samples, sr, volume_jumps
    )

    # 6. Extra speech detection
    voiced_ratio, speech_issues = _detect_extra_speech(frame_energies, duration_s)

    # Assemble issues
    all_issues = dur_issues + boundary_issues + volume_issues + spectral_issues + speech_issues
    if silence_gaps:
        all_issues.append(
            f"SILENCE_GAPS: {len(silence_gaps)} gap(s) > {SILENCE_GAP_MIN_MS}ms, "
            f"total {total_silence:.3f}s"
        )

    return ClipQualityReport(
        duration_s=round(dur_s, 4),
        expected_duration_s=round(expected_s, 4),
        duration_ratio=round(dur_ratio, 4),
        silence_gaps=silence_gaps,
        total_silence_s=total_silence,
        boundary_start_rms=start_rms,
        boundary_end_rms=end_rms,
        volume_jumps=volume_jumps,
        spectral_jumps=spectral_jumps,
        voiced_ratio=voiced_ratio,
        issues=all_issues,
    )


def validate_synthesis(
    output_path: str, text: str, clips_json: list[dict] | None = None
) -> dict:
    """Validate a full synthesis result.

    Takes the output MP3/WAV and the original text. Optionally accepts clip
    metadata (list of dicts with at least 'phrase' and 'start_ms'/'end_ms' keys)
    for more detailed per-clip analysis.

    Args:
        output_path: Path to the synthesized audio file.
        text: The original text that was synthesized.
        clips_json: Optional list of clip metadata dicts.

    Returns:
        A dict with 'report' (ClipQualityReport as dict), 'text', 'word_count',
        and optionally 'clips' with per-clip breakdown.
    """
    words = text.strip().split()
    word_count = len(words)

    report = validate_clip(output_path, expected_words=word_count)

    result = {
        "report": {
            "duration_s": report.duration_s,
            "expected_duration_s": report.expected_duration_s,
            "duration_ratio": report.duration_ratio,
            "silence_gaps": report.silence_gaps,
            "total_silence_s": report.total_silence_s,
            "boundary_start_rms": report.boundary_start_rms,
            "boundary_end_rms": report.boundary_end_rms,
            "volume_jumps": report.volume_jumps,
            "spectral_jumps": report.spectral_jumps,
            "voiced_ratio": report.voiced_ratio,
            "issues": report.issues,
        },
        "text": text,
        "word_count": word_count,
    }

    if clips_json:
        clips_analysis = []
        for clip_meta in clips_json:
            phrase = clip_meta.get("phrase", "")
            clip_words = len(phrase.split()) if phrase else 0
            clip_entry = {
                "phrase": phrase,
                "word_count": clip_words,
            }
            # Include any extra metadata from the clip dict
            for key in ("video_id", "start_ms", "end_ms", "confidence"):
                if key in clip_meta:
                    clip_entry[key] = clip_meta[key]
            clips_analysis.append(clip_entry)
        result["clips"] = clips_analysis

    return result
