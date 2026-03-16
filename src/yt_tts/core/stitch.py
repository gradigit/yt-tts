"""Audio clip normalization and stitching via ffmpeg."""

import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from yt_tts.config import Config
from yt_tts.exceptions import StitchError

logger = logging.getLogger(__name__)


def _run_ffmpeg(cmd: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run an ffmpeg command and return the result."""
    logger.debug("Running: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _get_duration_ms(path: Path) -> float:
    """Get the duration of an audio file in milliseconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise StitchError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    return float(result.stdout.strip()) * 1000


def normalize_clip(clip_path: Path, config: Config) -> Path:
    """Gentle volume normalization — prevents extreme jumps while keeping variation.

    Instead of forcing all clips to exactly -16 LUFS (which kills natural variation),
    this measures the clip's loudness and only adjusts if it's too far from the target.
    Clips within a ±6 LU window of the target are left alone. Clips outside that
    window are nudged toward the edge of the window, not to the exact target.

    This preserves the "voice of the internet" character — different speakers at
    different volumes — while preventing near-silence or ear-blasting clips.

    Returns:
        Path to the normalized WAV file (in a temp directory).
    """
    target_i = config.loudnorm_target_i  # default -16 LUFS
    window_lu = 6.0  # clips within ±6 LU of target are untouched

    # --- Measure loudness ---
    af_measure = (
        f"loudnorm=I={target_i}:TP={config.loudnorm_target_tp}"
        f":LRA={config.loudnorm_target_lra}:print_format=json"
    )
    cmd_measure = [
        "ffmpeg",
        "-y",
        "-i",
        str(clip_path),
        "-af",
        af_measure,
        "-f",
        "null",
        "/dev/null",
    ]
    result = _run_ffmpeg(cmd_measure)
    if result.returncode != 0:
        raise StitchError(f"loudnorm measurement failed for {clip_path}: {result.stderr.strip()}")

    stderr = result.stderr
    json_match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.DOTALL)
    if not json_match:
        raise StitchError(f"Could not parse loudnorm JSON from ffmpeg output for {clip_path}")
    try:
        measured = json.loads(json_match.group())
    except json.JSONDecodeError as exc:
        raise StitchError(f"Invalid loudnorm JSON for {clip_path}: {exc}") from exc

    input_i_raw = measured["input_i"]
    input_i = float(input_i_raw)

    # Guard against -inf (too short or silent clips) — skip normalization
    import math
    if not math.isfinite(input_i):
        logger.debug("Skipping normalization for %s (input_i=%s)", clip_path.name, input_i_raw)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", prefix="yt-tts-norm-", delete=False)
        tmp.close()
        output_path = Path(tmp.name)
        af = f"alimiter=limit=0.95,aresample={config.sample_rate}"
        cmd_copy = ["ffmpeg", "-y", "-i", str(clip_path), "-af", af, str(output_path)]
        result = _run_ffmpeg(cmd_copy)
        if result.returncode != 0:
            raise StitchError(f"Resample failed for {clip_path}: {result.stderr.strip()}")
        return output_path

    # --- Decide how much to adjust ---
    # If clip is within the window, just resample (no volume change)
    # If too quiet or too loud, nudge to the edge of the window
    diff = input_i - target_i  # negative = quieter than target
    if abs(diff) <= window_lu:
        # Within acceptable range — just resample, no loudness change
        gain_db = 0.0
    elif diff < -window_lu:
        # Too quiet — bring up to lower edge of window
        gain_db = -(diff + window_lu)  # positive gain (louder)
    else:
        # Too loud — bring down to upper edge of window
        gain_db = -(diff - window_lu)  # negative gain (quieter)

    logger.debug(
        "Normalize %s: input=%.1f LUFS, target=%.1f±%.0f, gain=%.1fdB",
        clip_path.name,
        input_i,
        target_i,
        window_lu,
        gain_db,
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", prefix="yt-tts-norm-", delete=False)
    tmp.close()
    output_path = Path(tmp.name)

    # Apply gain + resample + prevent clipping
    af = f"volume={gain_db}dB,alimiter=limit=0.95,aresample={config.sample_rate}"
    cmd_apply = [
        "ffmpeg",
        "-y",
        "-i",
        str(clip_path),
        "-af",
        af,
        str(output_path),
    ]
    result = _run_ffmpeg(cmd_apply)
    if result.returncode != 0:
        raise StitchError(f"Normalize failed for {clip_path}: {result.stderr.strip()}")

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise StitchError(f"Normalized file is empty or missing: {output_path}")

    return output_path


def generate_silence(duration_ms: int, config: Config) -> Path:
    """Generate a silent audio file of the given duration.

    Returns:
        Path to the silence WAV file (in a temp directory).

    Raises:
        StitchError: when ffmpeg fails.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", prefix="yt-tts-silence-", delete=False)
    tmp.close()
    output_path = Path(tmp.name)
    duration_s = duration_ms / 1000.0

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r={config.sample_rate}:cl=mono",
        "-t",
        f"{duration_s:.3f}",
        "-ar",
        str(config.sample_rate),
        str(output_path),
    ]
    result = _run_ffmpeg(cmd)
    if result.returncode != 0:
        raise StitchError(f"Silence generation failed: {result.stderr.strip()}")

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise StitchError(f"Silence file is empty or missing: {output_path}")

    return output_path


def _stitch_pair(a: Path, b: Path, crossfade_ms: int, config: Config) -> Path:
    """Stitch two audio files, optionally with crossfade.

    Returns:
        Path to the stitched output WAV file.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", prefix="yt-tts-pair-", delete=False)
    tmp.close()
    output_path = Path(tmp.name)

    if crossfade_ms > 0:
        cf_s = crossfade_ms / 1000.0
        filter_complex = f"[0:a][1:a]acrossfade=d={cf_s:.3f}:c1=tri:c2=tri[out]"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(a),
            "-i",
            str(b),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-ar",
            str(config.sample_rate),
            str(output_path),
        ]
    else:
        filter_complex = "[0:a][1:a]concat=n=2:v=0:a=1[out]"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(a),
            "-i",
            str(b),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-ar",
            str(config.sample_rate),
            str(output_path),
        ]

    result = _run_ffmpeg(cmd)
    if result.returncode != 0:
        raise StitchError(f"Pairwise stitch failed: {result.stderr.strip()}")

    return output_path


def stitch_clips(clips: list[Path], gaps: list[int], config: Config) -> Path:
    """Stitch multiple audio clips with silence gaps between them.

    *gaps* is a list of silence durations in milliseconds between consecutive
    clips.  Its length must equal ``len(clips) - 1``.

    For up to 20 clips the function builds a single ffmpeg filter_complex
    graph.  For more than 20, it performs iterative pairwise stitching to
    avoid excessively long filter graphs.

    The output format is determined by ``config.output_format`` (``mp3`` or
    ``wav``).

    Returns:
        Path to the final stitched output file.

    Raises:
        StitchError: on any ffmpeg failure or invalid input.
    """
    if not clips:
        raise StitchError("No clips to stitch")
    if len(gaps) != len(clips) - 1:
        raise StitchError(f"Expected {len(clips) - 1} gaps, got {len(gaps)}")

    if len(clips) == 1:
        # Single clip — just encode to the desired output format
        return _encode_output(clips[0], config)

    use_crossfade = not config.no_crossfade and config.crossfade_ms > 0
    crossfade_ms = config.crossfade_ms if use_crossfade else 0

    if len(clips) <= 20:
        return _stitch_filter_complex(clips, gaps, crossfade_ms, config)
    else:
        return _stitch_iterative(clips, gaps, crossfade_ms, config)


def _encode_output(clip: Path, config: Config) -> Path:
    """Encode a single clip to the desired output format."""
    ext = config.output_format
    tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", prefix="yt-tts-out-", delete=False)
    tmp.close()
    output_path = Path(tmp.name)

    if ext == "mp3":
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(clip),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output_path),
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(clip),
            "-ar",
            str(config.sample_rate),
            str(output_path),
        ]

    result = _run_ffmpeg(cmd)
    if result.returncode != 0:
        raise StitchError(f"Output encoding failed: {result.stderr.strip()}")

    return output_path


def _stitch_filter_complex(
    clips: list[Path],
    gaps: list[int],
    crossfade_ms: int,
    config: Config,
) -> Path:
    """Stitch clips using a single ffmpeg filter_complex graph.

    Interleaves silence segments between clips, then concatenates everything,
    optionally applying crossfade between adjacent clip+silence pairs.
    """
    ext = config.output_format
    tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", prefix="yt-tts-stitch-", delete=False)
    tmp.close()
    output_path = Path(tmp.name)

    # Generate silence files for gaps
    silence_files: list[Path] = []
    for gap_ms in gaps:
        if gap_ms > 0:
            silence_files.append(generate_silence(gap_ms, config))
        else:
            silence_files.append(None)  # type: ignore[arg-type]

    # Build input list: clip0, [silence0, clip1, silence1, clip2, ...]
    inputs: list[Path] = []
    input_args: list[str] = []
    for i, clip in enumerate(clips):
        inputs.append(clip)
        input_args.extend(["-i", str(clip)])
        if i < len(silence_files) and silence_files[i] is not None:
            inputs.append(silence_files[i])
            input_args.extend(["-i", str(silence_files[i])])

    # Build filter_complex: label each input stream and concat them
    n_streams = len(inputs)
    labels = [f"[{i}:a]" for i in range(n_streams)]

    if crossfade_ms > 0 and len(clips) == 2 and all(g == 0 for g in gaps):
        # Special case: two clips, no gap, with crossfade
        cf_s = crossfade_ms / 1000.0
        filter_complex = f"[0:a][1:a]acrossfade=d={cf_s:.3f}:c1=tri:c2=tri[out]"
    else:
        # General case: concat all inputs
        filter_complex = "".join(labels) + f"concat=n={n_streams}:v=0:a=1[out]"

    if ext == "mp3":
        output_args = ["-c:a", "libmp3lame", "-q:a", "2"]
    else:
        output_args = ["-ar", str(config.sample_rate)]

    cmd = (
        ["ffmpeg", "-y"]
        + input_args
        + ["-filter_complex", filter_complex]
        + ["-map", "[out]"]
        + output_args
        + [str(output_path)]
    )

    result = _run_ffmpeg(cmd)
    if result.returncode != 0:
        raise StitchError(f"filter_complex stitch failed: {result.stderr.strip()}")

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise StitchError(f"Stitched output is empty or missing: {output_path}")

    return output_path


def _stitch_iterative(
    clips: list[Path],
    gaps: list[int],
    crossfade_ms: int,
    config: Config,
) -> Path:
    """Stitch clips by iterative pairwise concatenation.

    Used when there are more than 20 clips to avoid excessively long
    filter_complex graphs.
    """
    # First, interleave clips with silence
    segments: list[Path] = [clips[0]]
    for i in range(1, len(clips)):
        gap_ms = gaps[i - 1]
        if gap_ms > 0:
            segments.append(generate_silence(gap_ms, config))
        segments.append(clips[i])

    # Iteratively merge pairs
    current = segments[0]
    for i in range(1, len(segments)):
        # Only apply crossfade between original clip boundaries (not silence)
        current = _stitch_pair(current, segments[i], 0, config)

    return _encode_output(current, config)
