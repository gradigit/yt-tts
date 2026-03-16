"""Phoneme-level audio stitching proof-of-concept.

Tests whether we can construct words that do NOT exist verbatim in source audio
by stitching sub-word (phoneme-level) segments from different clips. Verifies
results with ASR (faster-whisper) to check recognizability.

Sources used:
  - src3: "interesting animals" (from YouTube video GKByD6R7E-w, mantis shrimp)
  - src5: "striking the prey" (same video, different segment)

Results summary (faster-whisper 'small' model):

  WORD-LEVEL STITCHING (baseline):
    [EXACT  ] 'striking animals' -> 'Striking animals'
    [EXACT  ] 'animal prey'      -> 'animal prey'
    [EXACT  ] 'interesting strike' -> 'Interesting strike'
    [CLOSE  ] 'the animals strike' -> 'The animal strike'

  TRUNCATION (sub-word from single source):
    [EXACT  ] 'strike' (from 'striking') -> 'Strike'

  PHONEME-LEVEL (cross-boundary stitching):
    [MISS   ] 'stray' (str+ey)    -> 'straight'  <-- semantically close!
    [MISS   ] 'sting' (st+ing)    -> 'Shrestha'
    [MISS   ] 'string' (str+ing)  -> 'Shristened'
    [MISS   ] 'primal' (pr+i+mal) -> 'An animal'

Key findings:
  1. Word-level stitching works reliably across sources (4/5 exact matches)
  2. Truncation works well (extracting 'strike' from 'striking')
  3. Phoneme-level stitching creates recognizable speech but ASR maps to
     different words -- 'stray' consistently heard as 'straight' (very close!)
  4. The splice artifact manifests as an "sh" sound in many cases
  5. Crossfade method (linear vs cosine) and duration (5-50ms) made little
     difference for phoneme-level quality
  6. Same-source vs cross-source phoneme splicing had similar results
  7. Zero-crossing alignment did not significantly improve quality

Conclusion:
  Phoneme-level stitching produces audio that sounds like real speech to ASR
  (it never outputs garbage), but the spectral discontinuity at splice points
  shifts perception to nearby but different words. For yt-tts V1, word-level
  stitching is the right approach. Phoneme-level would need spectral smoothing
  (e.g., PSOLA, WORLD vocoder) to work reliably.
"""

import sys
import numpy as np
import soundfile as sf


def energy_profile(audio, sr=16000, frame_ms=10, hop_ms=5):
    """Compute RMS energy in short frames."""
    frame_n = int(frame_ms / 1000 * sr)
    hop_n = int(hop_ms / 1000 * sr)
    frames = []
    for i in range(0, len(audio) - frame_n, hop_n):
        frames.append(np.sqrt(np.mean(audio[i : i + frame_n] ** 2)))
    return np.array(frames)


def cosine_crossfade_join(a, b, sr=16000, fade_ms=20):
    """Join two audio segments with cosine crossfade."""
    fade_n = int(fade_ms / 1000 * sr)
    a, b = a.copy(), b.copy()
    fade_n = min(fade_n, len(a) // 2, len(b) // 2)
    t = np.linspace(0, np.pi / 2, fade_n)
    a[-fade_n:] *= np.cos(t)
    b[:fade_n] *= np.sin(t)
    overlap = a[-fade_n:] + b[:fade_n]
    return np.concatenate([a[:-fade_n], overlap, b[fade_n:]])


def normalize(audio, target_rms=0.12):
    """Normalize audio to target RMS level."""
    rms = np.sqrt(np.mean(audio ** 2))
    if rms > 0:
        return audio * (target_rms / rms)
    return audio


def run_experiment(src3_path="/tmp/src3.wav", src5_path="/tmp/src5.wav"):
    """Run the full phoneme stitching experiment.

    Requires pre-prepared WAV files (16kHz mono) from yt-tts:
      src3: "interesting animals"
      src5: "striking the prey"
    """
    from faster_whisper import WhisperModel

    audio3, sr = sf.read(src3_path)
    audio5, _ = sf.read(src5_path)

    # Word boundaries from faster-whisper (base model)
    words = {
        "interesting": audio3[int(0.000 * sr) : int(1.260 * sr)],
        "animals": audio3[int(1.260 * sr) : int(1.740 * sr)],
        "striking": audio5[int(0.000 * sr) : int(0.580 * sr)],
        "the": audio5[int(0.580 * sr) : int(0.780 * sr)],
        "prey": audio5[int(0.780 * sr) : int(1.040 * sr)],
    }

    pad = np.zeros(int(0.2 * sr))
    gap = np.zeros(int(0.08 * sr))

    # --- Word-level stitching (baseline) ---
    word_tests = {
        "striking animals": np.concatenate(
            [pad, words["striking"], gap, words["animals"], pad]
        ),
        "animal prey": np.concatenate(
            [pad, normalize(words["animals"]), gap, normalize(words["prey"]), pad]
        ),
        "interesting strike": np.concatenate(
            [
                pad,
                normalize(words["interesting"]),
                gap,
                normalize(words["striking"][: int(0.440 * sr)]),
                pad,
            ]
        ),
    }

    # --- Truncation test ---
    truncation_tests = {
        "strike": np.concatenate(
            [pad, words["striking"][: int(0.440 * sr)], pad]
        ),
    }

    # --- Phoneme-level stitching ---
    # "STRAY" = str(iking) + pr(ey) vowel
    str_part = words["striking"][: int(0.220 * sr)]
    ey_part = words["prey"][int(0.100 * sr) :]
    stray = cosine_crossfade_join(str_part, ey_part, sr=sr, fade_ms=20)

    # "STING" = st(riking) + (interest)ing
    st_part = words["striking"][: int(0.100 * sr)]
    ing_part = words["interesting"][int(0.960 * sr) : int(1.260 * sr)]
    sting = cosine_crossfade_join(st_part, ing_part, sr=sr, fade_ms=5)

    # "STRING" = str(iking) + (interest)ing
    string = cosine_crossfade_join(
        words["striking"][: int(0.200 * sr)],
        words["interesting"][int(0.960 * sr) : int(1.260 * sr)],
        sr=sr,
        fade_ms=8,
    )

    phoneme_tests = {
        "stray": np.concatenate([pad, stray, pad]),
        "sting": np.concatenate([pad, sting, pad]),
        "string": np.concatenate([pad, string, pad]),
        "stray animals": np.concatenate(
            [pad, normalize(stray), gap, normalize(words["animals"]), pad]
        ),
    }

    # --- Run ASR verification ---
    model = WhisperModel("small", device="cpu", compute_type="int8")

    results = {}
    for category, tests in [
        ("WORD-LEVEL", word_tests),
        ("TRUNCATION", truncation_tests),
        ("PHONEME-LEVEL", phoneme_tests),
    ]:
        print(f"\n--- {category} ---")
        for target, audio in tests.items():
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, audio, sr)
                segments, _ = model.transcribe(f.name, word_timestamps=True)
                recognized = " ".join(seg.text for seg in segments).strip()

            exp = target.lower()
            rec = recognized.lower().strip(".,!? ")
            if exp == rec:
                status = "EXACT"
            elif exp in rec or rec in exp:
                status = "CLOSE"
            else:
                exp_words = set(exp.split())
                rec_words = set(rec.split())
                if len(exp_words & rec_words) == len(exp_words):
                    status = "MATCH"
                elif exp_words & rec_words:
                    status = "PARTIAL"
                else:
                    status = "MISS"

            results[target] = (status, recognized)
            print(f"  [{status:7s}] '{target}' -> '{recognized}'")

    return results


if __name__ == "__main__":
    if "--prepare" in sys.argv:
        # Prepare source audio using yt-tts
        import subprocess

        for phrase, output in [
            ("interesting animals", "/tmp/phoneme_src3.mp3"),
            ("striking the prey", "/tmp/phoneme_src5.mp3"),
        ]:
            print(f"Downloading: {phrase}")
            subprocess.run(
                ["yt-tts", "--no-cache", "-o", output, phrase], check=True
            )

        for src, dst in [
            ("/tmp/phoneme_src3.mp3", "/tmp/src3.wav"),
            ("/tmp/phoneme_src5.mp3", "/tmp/src5.wav"),
        ]:
            print(f"Converting: {src} -> {dst}")
            subprocess.run(
                ["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1", dst],
                check=True,
                capture_output=True,
            )

    run_experiment()
