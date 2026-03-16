"""Phoneme stitching stress test: construct "purple elephants dance silently".

This test constructs a full sentence that does NOT exist in any YouTube video
by stitching words and sub-word parts from multiple different source clips.
The result is verified with multiple ASR models to measure intelligibility.

Source clips (downloaded from real YouTube videos):
  - GlKvjHkEF2I: "Fringe Feathers Earrings" -> word "purple" at 8.200-8.640s
  - BxHp9_TDmqI: video about elephants -> word "elephants" at 0.000-1.120s
  - 7i7pHQamVRY: "Boatman Dance" -> word "dance" at 9.420-9.780s
  - bkmHnHwD9XM: "Holder of Reconciliation" -> word "silently" at 17.640-18.060s
  - GQqQqKkqf7g: (via yt-tts) -> "really" at 0.000-0.200s (for -ly suffix)
  - Ln6SV05Rm44: (via yt-tts) -> "making" at 0.000-0.300s (for -ing suffix)

Experiments:
  1. Word-level stitching: "purple" + "elephants" + "dance" + "silently"
  2. Sub-word construction: "silent" (from "silently") + "-ly" (from "really")
  3. Sub-word construction: "danc-" (from "dance") + "-ing" (from "making")
  4. Full sentence with cosine crossfade between words
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SR = 16000  # Sample rate for all processing
TARGET_SENTENCE = "purple elephants dance silently"
OUTPUT_DIR = Path("/tmp/phoneme_stress")
FINAL_OUTPUT = Path("/home/lechat/Projects/yt-tts/ytp/phoneme_stress_test.mp3")

# Source audio files (raw 15-20s clips downloaded from YouTube)
RAW_SOURCES = {
    "purple": {
        "wav": OUTPUT_DIR / "raw_purple.wav",
        "video_id": "GlKvjHkEF2I",
        "title": "Fringe Feathers Earrings - Tutorial",
        "word_start": 8.200,
        "word_end": 8.640,
    },
    "elephants": {
        "wav": OUTPUT_DIR / "do_elephants.wav",
        "video_id": "BxHp9_TDmqI",
        "title": "Elephants documentary",
        "word_start": 0.000,
        "word_end": 1.120,
    },
    "dance": {
        "wav": OUTPUT_DIR / "raw_dance_7i7pHQamVRY.wav",
        "video_id": "7i7pHQamVRY",
        "title": "Boatman Dance",
        "word_start": 9.420,
        "word_end": 9.780,
    },
    "silently": {
        "wav": OUTPUT_DIR / "raw_silently_bkmHnHwD9XM.wav",
        "video_id": "bkmHnHwD9XM",
        "title": "Legion's Objects - Holder of Reconciliation",
        "word_start": 17.640,
        "word_end": 18.060,
    },
}

# Additional sources for sub-word experiments
SUBWORD_SOURCES = {
    "really": {
        "wav": OUTPUT_DIR / "really_good.wav",
        "video_id": "GQqQqKkqf7g",
        "word_start": 0.000,
        "word_end": 0.200,
    },
    "making": {
        "wav": OUTPUT_DIR / "making_something.wav",
        "video_id": "Ln6SV05Rm44",
        "word_start": 0.000,
        "word_end": 0.300,
    },
}


# ---------------------------------------------------------------------------
# Audio utilities
# ---------------------------------------------------------------------------
def cosine_crossfade(a: np.ndarray, b: np.ndarray, fade_samples: int) -> np.ndarray:
    """Join two audio arrays with cosine crossfade at the boundary."""
    a, b = a.copy(), b.copy()
    fade_samples = min(fade_samples, len(a) // 2, len(b) // 2)
    if fade_samples < 2:
        return np.concatenate([a, b])
    t = np.linspace(0, np.pi / 2, fade_samples)
    a[-fade_samples:] *= np.cos(t)
    b[:fade_samples] *= np.sin(t)
    overlap = a[-fade_samples:] + b[:fade_samples]
    return np.concatenate([a[:-fade_samples], overlap, b[fade_samples:]])


def normalize_rms(audio: np.ndarray, target_rms: float = 0.1) -> np.ndarray:
    """Normalize audio to target RMS level."""
    rms = np.sqrt(np.mean(audio**2))
    if rms > 1e-8:
        return audio * (target_rms / rms)
    return audio


def find_zero_crossing(audio: np.ndarray, pos: int, search_range: int = 80) -> int:
    """Find nearest zero crossing to the given position."""
    start = max(0, pos - search_range)
    end = min(len(audio), pos + search_range)
    segment = audio[start:end]
    if len(segment) < 2:
        return pos
    signs = np.sign(segment)
    crossings = np.where(np.diff(signs) != 0)[0]
    if len(crossings) == 0:
        return pos
    nearest = crossings[np.argmin(np.abs(crossings - (pos - start)))]
    return start + nearest


def extract_word_audio(
    full_audio: np.ndarray, start_s: float, end_s: float, margin_s: float = 0.015
) -> np.ndarray:
    """Extract a word segment from audio with margin, aligned to zero crossings."""
    start_sample = max(0, int((start_s - margin_s) * SR))
    end_sample = min(len(full_audio), int((end_s + margin_s) * SR))
    start_sample = find_zero_crossing(full_audio, start_sample)
    end_sample = find_zero_crossing(full_audio, end_sample)
    return full_audio[start_sample:end_sample]


def verify_with_asr(wav_path: Path, target: str, model_sizes: list[str] = None) -> list[dict]:
    """Verify audio with multiple Whisper models. Returns list of results."""
    from faster_whisper import WhisperModel

    if model_sizes is None:
        model_sizes = ["tiny", "base", "small"]

    results = []
    for model_name in model_sizes:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(wav_path))
        text = " ".join(seg.text for seg in segments).strip()

        target_words = set(target.lower().split())
        # Clean punctuation from ASR output
        import re
        heard_text = re.sub(r"[.,!?;:'\"-]", "", text.lower()).strip()
        heard_words = set(heard_text.split())
        overlap = target_words & heard_words
        accuracy = len(overlap) / len(target_words) * 100 if target_words else 0

        results.append({
            "model": model_name,
            "text": text,
            "accuracy": accuracy,
            "matching_words": sorted(overlap),
        })
    return results


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------
def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("PHONEME STITCHING STRESS TEST")
    print(f"Target sentence: '{TARGET_SENTENCE}'")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: Verify all source files exist
    # ------------------------------------------------------------------
    print("\n--- Step 1: Checking source files ---")
    all_sources = {**RAW_SOURCES, **SUBWORD_SOURCES}
    missing = [k for k, v in all_sources.items() if not v["wav"].exists()]
    if missing:
        print(f"  ERROR: Missing source files: {missing}")
        print("  Run the source generation steps first.")
        sys.exit(1)
    print("  All source files present.")

    # ------------------------------------------------------------------
    # Step 2: Extract individual words from source audio
    # ------------------------------------------------------------------
    print("\n--- Step 2: Extracting word segments ---")
    word_segments = {}

    for word, info in RAW_SOURCES.items():
        audio, _ = sf.read(str(info["wav"]))
        segment = extract_word_audio(audio, info["word_start"], info["word_end"])
        word_segments[word] = segment
        duration_ms = len(segment) / SR * 1000
        print(f"  {word}: {duration_ms:.0f}ms from {info['video_id']} [{info['word_start']:.3f}-{info['word_end']:.3f}s]")

    # Extract sub-word parts
    # "-ly" from "really" (last ~40% of the word)
    really_audio, _ = sf.read(str(SUBWORD_SOURCES["really"]["wav"]))
    really_word = extract_word_audio(
        really_audio, SUBWORD_SOURCES["really"]["word_start"], SUBWORD_SOURCES["really"]["word_end"], margin_s=0.0
    )
    ly_start = int(len(really_word) * 0.55)
    ly_start = find_zero_crossing(really_word, ly_start)
    word_segments["ly_suffix"] = really_word[ly_start:]
    print(f"  -ly suffix: {len(word_segments['ly_suffix'])/SR*1000:.0f}ms from 'really' ({SUBWORD_SOURCES['really']['video_id']})")

    # "-ing" from "making" (last ~35% of the word)
    making_audio, _ = sf.read(str(SUBWORD_SOURCES["making"]["wav"]))
    making_word = extract_word_audio(
        making_audio, SUBWORD_SOURCES["making"]["word_start"], SUBWORD_SOURCES["making"]["word_end"], margin_s=0.0
    )
    ing_start = int(len(making_word) * 0.60)
    ing_start = find_zero_crossing(making_word, ing_start)
    word_segments["ing_suffix"] = making_word[ing_start:]
    print(f"  -ing suffix: {len(word_segments['ing_suffix'])/SR*1000:.0f}ms from 'making' ({SUBWORD_SOURCES['making']['video_id']})")

    # "silent-" prefix from "silently" (first ~72% of the word)
    silently_audio = word_segments["silently"]
    silent_end = int(len(silently_audio) * 0.72)
    silent_end = find_zero_crossing(silently_audio, silent_end)
    word_segments["silent_prefix"] = silently_audio[:silent_end]
    print(f"  silent- prefix: {len(word_segments['silent_prefix'])/SR*1000:.0f}ms from 'silently'")

    # "danc-" prefix from "dance" (first ~70% of the word)
    dance_audio = word_segments["dance"]
    danc_end = int(len(dance_audio) * 0.70)
    danc_end = find_zero_crossing(dance_audio, danc_end)
    word_segments["danc_prefix"] = dance_audio[:danc_end]
    print(f"  danc- prefix: {len(word_segments['danc_prefix'])/SR*1000:.0f}ms from 'dance'")

    # Save individual word WAVs for inspection
    for name, audio in word_segments.items():
        out = OUTPUT_DIR / f"word_{name}.wav"
        sf.write(str(out), audio, SR)

    # ------------------------------------------------------------------
    # Step 3: Experiment 1 - Word-level stitching (simple concatenation)
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Word-level stitching (concatenation + gaps)")
    print("  purple + elephants + dance + silently")
    print("=" * 70)

    gap = np.zeros(int(0.08 * SR))   # 80ms silence between words
    pad = np.zeros(int(0.15 * SR))   # 150ms padding at edges

    words_order = ["purple", "elephants", "dance", "silently"]
    parts = [pad]
    for i, word in enumerate(words_order):
        segment = normalize_rms(word_segments[word], target_rms=0.1)
        if i > 0:
            parts.append(gap)
        parts.append(segment)
    parts.append(pad)

    exp1_audio = np.concatenate(parts)
    exp1_path = OUTPUT_DIR / "exp1_word_level.wav"
    sf.write(str(exp1_path), exp1_audio, SR)
    print(f"  Output: {exp1_path} ({len(exp1_audio)/SR:.2f}s)")

    exp1_results = verify_with_asr(exp1_path, TARGET_SENTENCE)
    print("\n  ASR Verification:")
    for r in exp1_results:
        print(f"    {r['model']:8s}: '{r['text']}' ({r['accuracy']:.0f}% word accuracy)")
        print(f"             matching: {r['matching_words']}")

    # ------------------------------------------------------------------
    # Step 4: Experiment 2 - Sub-word: "silently" from "silent" + "-ly"
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: Sub-word construction of 'silently'")
    print("  silent- (from 'silently'/bkmHnHwD9XM) + -ly (from 'really'/GQqQqKkqf7g)")
    print("=" * 70)

    silent_part = normalize_rms(word_segments["silent_prefix"], target_rms=0.1)
    ly_part = normalize_rms(word_segments["ly_suffix"], target_rms=0.1)
    constructed_silently = cosine_crossfade(silent_part, ly_part, int(0.008 * SR))

    exp2_audio = np.concatenate([pad, constructed_silently, pad])
    exp2_path = OUTPUT_DIR / "exp2_silently_constructed.wav"
    sf.write(str(exp2_path), exp2_audio, SR)
    print(f"  Constructed 'silently': {len(constructed_silently)/SR*1000:.0f}ms")
    print(f"  Output: {exp2_path}")

    exp2_results = verify_with_asr(exp2_path, "silently")
    print("\n  ASR Verification:")
    for r in exp2_results:
        print(f"    {r['model']:8s}: '{r['text']}' (target: 'silently')")

    # ------------------------------------------------------------------
    # Step 5: Experiment 3 - Sub-word: "dancing" from "danc-" + "-ing"
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EXPERIMENT 3: Sub-word construction of 'dancing'")
    print("  danc- (from 'dance'/7i7pHQamVRY) + -ing (from 'making'/Ln6SV05Rm44)")
    print("=" * 70)

    danc_part = normalize_rms(word_segments["danc_prefix"], target_rms=0.1)
    ing_part = normalize_rms(word_segments["ing_suffix"], target_rms=0.1)
    constructed_dancing = cosine_crossfade(danc_part, ing_part, int(0.005 * SR))

    exp3_audio = np.concatenate([pad, constructed_dancing, pad])
    exp3_path = OUTPUT_DIR / "exp3_dancing_constructed.wav"
    sf.write(str(exp3_path), exp3_audio, SR)
    print(f"  Constructed 'dancing': {len(constructed_dancing)/SR*1000:.0f}ms")
    print(f"  Output: {exp3_path}")

    exp3_results = verify_with_asr(exp3_path, "dancing")
    print("\n  ASR Verification:")
    for r in exp3_results:
        print(f"    {r['model']:8s}: '{r['text']}' (target: 'dancing')")

    # ------------------------------------------------------------------
    # Step 6: Experiment 4 - Full sentence with cosine crossfade
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EXPERIMENT 4: Full sentence with cosine crossfade")
    print("  purple + elephants + dance + silently (5ms crossfade, 80ms gaps)")
    print("=" * 70)

    fade_samples = int(0.005 * SR)  # 5ms crossfade

    normalized_words = []
    for word in words_order:
        normalized_words.append(normalize_rms(word_segments[word], target_rms=0.1))

    # Build with crossfade at gap-word boundaries
    result = pad.copy()
    for i, word_audio in enumerate(normalized_words):
        if i > 0:
            with_gap = np.concatenate([result, gap])
            result = cosine_crossfade(with_gap, word_audio, fade_samples)
        else:
            result = np.concatenate([result, word_audio])
    result = np.concatenate([result, pad])

    exp4_path = OUTPUT_DIR / "exp4_full_crossfade.wav"
    sf.write(str(exp4_path), result, SR)
    print(f"  Output: {exp4_path} ({len(result)/SR:.2f}s)")

    exp4_results = verify_with_asr(exp4_path, TARGET_SENTENCE)
    print("\n  ASR Verification:")
    for r in exp4_results:
        print(f"    {r['model']:8s}: '{r['text']}' ({r['accuracy']:.0f}% word accuracy)")
        print(f"             matching: {r['matching_words']}")

    # ------------------------------------------------------------------
    # Step 7: Experiment 5 - Full sentence with constructed words
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EXPERIMENT 5: Sentence using sub-word-constructed 'silently'")
    print("  purple + elephants + dance + [silent-+ly]")
    print("=" * 70)

    words_exp5 = [
        normalize_rms(word_segments["purple"], target_rms=0.1),
        normalize_rms(word_segments["elephants"], target_rms=0.1),
        normalize_rms(word_segments["dance"], target_rms=0.1),
        normalize_rms(constructed_silently, target_rms=0.1),
    ]

    result5 = pad.copy()
    for i, word_audio in enumerate(words_exp5):
        if i > 0:
            with_gap = np.concatenate([result5, gap])
            result5 = cosine_crossfade(with_gap, word_audio, fade_samples)
        else:
            result5 = np.concatenate([result5, word_audio])
    result5 = np.concatenate([result5, pad])

    exp5_path = OUTPUT_DIR / "exp5_with_constructed_silently.wav"
    sf.write(str(exp5_path), result5, SR)
    print(f"  Output: {exp5_path} ({len(result5)/SR:.2f}s)")

    exp5_results = verify_with_asr(exp5_path, TARGET_SENTENCE)
    print("\n  ASR Verification:")
    for r in exp5_results:
        print(f"    {r['model']:8s}: '{r['text']}' ({r['accuracy']:.0f}% word accuracy)")
        print(f"             matching: {r['matching_words']}")

    # ------------------------------------------------------------------
    # Step 8: Save final MP3 output
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("FINAL OUTPUT")
    print("=" * 70)

    # Use Experiment 4 (crossfaded word-level) as the primary output
    best_wav = exp4_path
    FINAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(best_wav),
            "-c:a", "libmp3lame", "-q:a", "2",
            str(FINAL_OUTPUT),
        ],
        capture_output=True,
        check=True,
    )
    print(f"  Final MP3: {FINAL_OUTPUT}")
    print(f"  Size: {FINAL_OUTPUT.stat().st_size} bytes")

    # ------------------------------------------------------------------
    # Step 9: Comprehensive results table
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("COMPREHENSIVE RESULTS TABLE")
    print("=" * 70)

    experiments = [
        ("Exp1: Word concat", "word", words_order, exp1_results),
        ("Exp2: Constructed silently", "sub-word", ["silently"], exp2_results),
        ("Exp3: Constructed dancing", "sub-word", ["dancing"], exp3_results),
        ("Exp4: Word + crossfade", "word+xfade", words_order, exp4_results),
        ("Exp5: Word + constructed", "hybrid", words_order, exp5_results),
    ]

    print()
    header = f"{'Experiment':<30} {'Type':<12} {'Model':<8} {'ASR Result':<45} {'Accuracy':>8}"
    print(header)
    print("-" * len(header))

    for exp_name, exp_type, _, results in experiments:
        for r in results:
            text_display = r["text"][:43] if len(r["text"]) > 43 else r["text"]
            print(f"  {exp_name:<28} {exp_type:<12} {r['model']:<8} {text_display:<45} {r['accuracy']:>6.0f}%")

    print()
    print("Source videos:")
    all_vids = {}
    for info in RAW_SOURCES.values():
        all_vids[info["video_id"]] = info.get("title", "")
    for info in SUBWORD_SOURCES.values():
        all_vids[info["video_id"]] = ""
    for vid, title in sorted(all_vids.items()):
        title_str = f" ({title})" if title else ""
        print(f"  https://youtube.com/watch?v={vid}{title_str}")

    # ------------------------------------------------------------------
    # Step 10: Quality analysis
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("QUALITY ANALYSIS")
    print("=" * 70)

    # Analyze RMS levels of individual words
    print("\n  RMS levels per word (before normalization):")
    for word in words_order:
        audio = word_segments[word]
        rms = np.sqrt(np.mean(audio**2))
        peak = np.max(np.abs(audio))
        print(f"    {word:12s}: RMS={rms:.4f}, Peak={peak:.4f}, Duration={len(audio)/SR*1000:.0f}ms")

    # Check for clicks/discontinuities in the stitched audio
    print("\n  Discontinuity check (max sample-to-sample jump):")
    for name, path in [("Exp1 (concat)", exp1_path), ("Exp4 (crossfade)", exp4_path)]:
        audio, _ = sf.read(str(path))
        diffs = np.abs(np.diff(audio))
        max_jump = np.max(diffs)
        mean_jump = np.mean(diffs)
        print(f"    {name}: max_jump={max_jump:.4f}, mean_jump={mean_jump:.6f}")

    # Best result summary
    print("\n  BEST RESULT:")
    best = max(
        [(r, exp_name) for exp_name, _, _, results in experiments for r in results],
        key=lambda x: x[0]["accuracy"],
    )
    print(f"    {best[1]}, model={best[0]['model']}: '{best[0]['text']}' ({best[0]['accuracy']:.0f}%)")

    print("\nDone.")


if __name__ == "__main__":
    run()
