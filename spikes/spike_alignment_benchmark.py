"""Head-to-head benchmark: WhisperX vs ctc-forced-aligner for word-level alignment.

Tests both tools on a 15-second clip from 'Me at the zoo' (jNQXAC9IVRw).
Compares: word detection, timestamp quality, and throughput.

ctc-forced-aligner v1.0.2 uses an ONNX-based pipeline (not the torch-based
`load_alignment_model` from the git HEAD). This benchmark uses the correct
v1.0.2 API: Alignment class + generate_emissions + get_alignments.
"""

import time
import sys
import os
import tempfile

AUDIO_PATH = "/tmp/test_align.wav"
KNOWN_TEXT = (
    "All right so here we are in front of the elephants "
    "the cool thing about these guys is that they have "
    "really really really long trunks"
)

# --------------------------------------------------------------------------- #
# WhisperX
# --------------------------------------------------------------------------- #
def run_whisperx(audio_path: str, device: str = "cuda"):
    """Run WhisperX transcription + alignment. Returns (words, elapsed, model, model_a, metadata)."""
    import whisperx

    audio = whisperx.load_audio(audio_path)

    t0 = time.perf_counter()
    model = whisperx.load_model("tiny", device, compute_type="int8")
    result = model.transcribe(audio, batch_size=16)
    model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device)
    t1 = time.perf_counter()

    words = _extract_whisperx_words(result)
    return words, t1 - t0, model, model_a, metadata


def run_whisperx_warm(audio_path: str, device: str, model, model_a, metadata):
    """Run WhisperX with model already loaded (warm run)."""
    import whisperx

    audio = whisperx.load_audio(audio_path)

    t0 = time.perf_counter()
    result = model.transcribe(audio, batch_size=16)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device)
    t1 = time.perf_counter()

    words = _extract_whisperx_words(result)
    return words, t1 - t0


def _extract_whisperx_words(result):
    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            start = w.get("start")
            end = w.get("end")
            word = w.get("word", "")
            if start is not None and end is not None:
                words.append({"start": float(start), "end": float(end), "text": word})
            else:
                words.append({"start": None, "end": None, "text": word})
    return words


# --------------------------------------------------------------------------- #
# ctc-forced-aligner (v1.0.2 ONNX path)
# --------------------------------------------------------------------------- #
def run_ctc_onnx(audio_path: str, known_text: str):
    """Run ctc-forced-aligner v1.0.2 ONNX pipeline with known text."""
    from ctc_forced_aligner import (
        Alignment,
        ensure_onnx_model,
        MODEL_URL,
        load_audio,
        generate_emissions,
        preprocess_text,
        get_alignments,
        get_spans,
        postprocess_results,
    )

    # Determine model path (same as library default)
    model_dir = os.path.join(os.path.expanduser("~"), ".cache", "ctc_forced_aligner")
    model_path = os.path.join(model_dir, "model.onnx")

    t0 = time.perf_counter()
    ensure_onnx_model(model_path, MODEL_URL)
    alignment = Alignment(model_path)
    session = alignment.alignment_model
    tokenizer = alignment.alignment_tokenizer

    audio_waveform = load_audio(audio_path, ret_type="np")
    emissions, stride = generate_emissions(session, audio_waveform, batch_size=8)
    tokens_starred, text_starred = preprocess_text(
        known_text, romanize=True, language="eng"
    )
    segments, scores, blank_id = get_alignments(emissions, tokens_starred, tokenizer)
    spans = get_spans(tokens_starred, segments, blank_id)
    word_timestamps = postprocess_results(text_starred, spans, stride, scores)
    t1 = time.perf_counter()

    words = _extract_ctc_words(word_timestamps)
    return words, t1 - t0, alignment


def run_ctc_onnx_warm(audio_path: str, known_text: str, alignment):
    """Run ctc-forced-aligner ONNX pipeline with model already loaded."""
    from ctc_forced_aligner import (
        load_audio,
        generate_emissions,
        preprocess_text,
        get_alignments,
        get_spans,
        postprocess_results,
    )

    session = alignment.alignment_model
    tokenizer = alignment.alignment_tokenizer

    t0 = time.perf_counter()
    audio_waveform = load_audio(audio_path, ret_type="np")
    emissions, stride = generate_emissions(session, audio_waveform, batch_size=8)
    tokens_starred, text_starred = preprocess_text(
        known_text, romanize=True, language="eng"
    )
    segments, scores, blank_id = get_alignments(emissions, tokens_starred, tokenizer)
    spans = get_spans(tokens_starred, segments, blank_id)
    word_timestamps = postprocess_results(text_starred, spans, stride, scores)
    t1 = time.perf_counter()

    words = _extract_ctc_words(word_timestamps)
    return words, t1 - t0


# --------------------------------------------------------------------------- #
# ctc-forced-aligner torch path (get_word_stamps)
# --------------------------------------------------------------------------- #
def run_ctc_torch(audio_path: str, known_text: str):
    """Run ctc-forced-aligner torch-based get_word_stamps pipeline."""
    from ctc_forced_aligner import get_word_stamps

    # get_word_stamps needs a transcript file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(known_text)
        transcript_path = f.name

    try:
        t0 = time.perf_counter()
        word_timestamps, model, lyrics_lines = get_word_stamps(
            audio_path, transcript_path, model_type="MMS_FA"
        )
        t1 = time.perf_counter()
    finally:
        os.unlink(transcript_path)

    words = _extract_ctc_torch_words(word_timestamps)
    return words, t1 - t0, model


def run_ctc_torch_warm(audio_path: str, known_text: str, model):
    """Run ctc-forced-aligner torch pipeline with model already loaded."""
    from ctc_forced_aligner import get_word_stamps

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(known_text)
        transcript_path = f.name

    try:
        t0 = time.perf_counter()
        word_timestamps, _, _ = get_word_stamps(
            audio_path, transcript_path, model=model, model_type="MMS_FA"
        )
        t1 = time.perf_counter()
    finally:
        os.unlink(transcript_path)

    words = _extract_ctc_torch_words(word_timestamps)
    return words, t1 - t0


def _extract_ctc_words(word_timestamps):
    """Extract word dicts from ctc-forced-aligner ONNX output."""
    words = []
    for entry in word_timestamps:
        if isinstance(entry, list):
            for w in entry:
                words.append({
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                    "text": w.get("text", w.get("word", "")),
                })
        elif isinstance(entry, dict):
            words.append({
                "start": float(entry["start"]),
                "end": float(entry["end"]),
                "text": entry.get("text", entry.get("word", "")),
            })
    return words


def _extract_ctc_torch_words(word_timestamps):
    """Extract word dicts from ctc-forced-aligner torch output."""
    words = []
    for entry in word_timestamps:
        if isinstance(entry, dict):
            words.append({
                "start": float(entry.get("start", entry.get("start_time", 0))),
                "end": float(entry.get("end", entry.get("end_time", 0))),
                "text": entry.get("text", entry.get("word", "")),
            })
        elif isinstance(entry, (list, tuple)):
            for w in entry:
                if isinstance(w, dict):
                    words.append({
                        "start": float(w.get("start", w.get("start_time", 0))),
                        "end": float(w.get("end", w.get("end_time", 0))),
                        "text": w.get("text", w.get("word", "")),
                    })
    return words


# --------------------------------------------------------------------------- #
# Comparison / Reporting
# --------------------------------------------------------------------------- #
def print_words(label: str, words: list[dict]):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    for w in words:
        s = f"{w['start']:.3f}" if w["start"] is not None else "  ?  "
        e = f"{w['end']:.3f}" if w["end"] is not None else "  ?  "
        print(f"  {s}s - {e}s  {w['text']}")


def print_side_by_side(label_a, words_a, label_b, words_b):
    print(f"\n{'='*78}")
    print(f"  SIDE-BY-SIDE: {label_a} vs {label_b}")
    print(f"{'='*78}")
    print(f"  {label_a:<35} | {label_b:<35}")
    print(f"  {'-'*35}-+-{'-'*35}")

    max_len = max(len(words_a), len(words_b))
    for i in range(max_len):
        if i < len(words_a):
            w = words_a[i]
            s = f"{w['start']:.3f}" if w["start"] is not None else "  ?  "
            e = f"{w['end']:.3f}" if w["end"] is not None else "  ?  "
            col_a = f"{s}-{e} {w['text']}"
        else:
            col_a = ""

        if i < len(words_b):
            w = words_b[i]
            s = f"{w['start']:.3f}" if w["start"] is not None else "  ?  "
            e = f"{w['end']:.3f}" if w["end"] is not None else "  ?  "
            col_b = f"{s}-{e} {w['text']}"
        else:
            col_b = ""

        print(f"  {col_a:<35} | {col_b:<35}")


def compute_stats(words):
    """Compute timing statistics for word list."""
    valid = [w for w in words if w["start"] is not None and w["end"] is not None]
    if not valid:
        return {"count": len(words), "valid": 0, "avg_dur": 0, "min_dur": 0, "max_dur": 0, "total_span": 0}
    durations = [w["end"] - w["start"] for w in valid]
    return {
        "count": len(words),
        "valid": len(valid),
        "avg_dur": sum(durations) / len(durations),
        "min_dur": min(durations),
        "max_dur": max(durations),
        "total_span": valid[-1]["end"] - valid[0]["start"] if valid else 0,
    }


def gap_analysis(words):
    valid = [w for w in words if w["start"] is not None and w["end"] is not None]
    gaps = []
    overlaps = []
    for i in range(1, len(valid)):
        gap = valid[i]["start"] - valid[i-1]["end"]
        if gap > 0:
            gaps.append(gap)
        elif gap < 0:
            overlaps.append(abs(gap))
    return gaps, overlaps


def main():
    device = "cuda"
    print("=" * 78)
    print("  ALIGNMENT BENCHMARK: WhisperX vs ctc-forced-aligner")
    print("=" * 78)
    print(f"  Audio: {AUDIO_PATH}")
    print(f"  Device: {device}")
    print(f"  Known text: {KNOWN_TEXT[:60]}...")
    print()

    results = {}  # name -> {words, cold_time, warm_times, error}

    # ------------------------------------------------------------------- #
    # 1. WhisperX (cold run)
    # ------------------------------------------------------------------- #
    print("\n[1/3] Running WhisperX (cold start - includes model loading)...")
    wx_error = None
    wx_model = wx_model_a = wx_metadata = None
    try:
        wx_words, wx_time_cold, wx_model, wx_model_a, wx_metadata = run_whisperx(
            AUDIO_PATH, device
        )
        print(f"  Cold run: {wx_time_cold:.2f}s, {len(wx_words)} words")
        print_words("WhisperX Results (cold)", wx_words)
        results["WhisperX"] = {"words": wx_words, "cold_time": wx_time_cold}
    except Exception as e:
        wx_error = str(e)
        import traceback
        print(f"  WhisperX FAILED: {e}")
        traceback.print_exc()
        results["WhisperX"] = {"words": [], "cold_time": float("inf"), "error": wx_error}

    # ------------------------------------------------------------------- #
    # 2. ctc-forced-aligner ONNX path (cold run)
    # ------------------------------------------------------------------- #
    print("\n[2/3] Running ctc-forced-aligner ONNX (cold start)...")
    ctc_onnx_error = None
    ctc_alignment = None
    try:
        ctc_onnx_words, ctc_onnx_cold, ctc_alignment = run_ctc_onnx(
            AUDIO_PATH, KNOWN_TEXT
        )
        print(f"  Cold run: {ctc_onnx_cold:.2f}s, {len(ctc_onnx_words)} words")
        print_words("ctc-forced-aligner ONNX Results (cold)", ctc_onnx_words)
        results["CTC-ONNX"] = {"words": ctc_onnx_words, "cold_time": ctc_onnx_cold}
    except Exception as e:
        ctc_onnx_error = str(e)
        import traceback
        print(f"  ctc-forced-aligner ONNX FAILED: {e}")
        traceback.print_exc()
        results["CTC-ONNX"] = {"words": [], "cold_time": float("inf"), "error": ctc_onnx_error}

    # ------------------------------------------------------------------- #
    # 3. ctc-forced-aligner torch path (cold run)
    # ------------------------------------------------------------------- #
    print("\n[3/3] Running ctc-forced-aligner Torch/MMS_FA (cold start)...")
    ctc_torch_error = None
    ctc_torch_model = None
    try:
        ctc_torch_words, ctc_torch_cold, ctc_torch_model = run_ctc_torch(
            AUDIO_PATH, KNOWN_TEXT
        )
        print(f"  Cold run: {ctc_torch_cold:.2f}s, {len(ctc_torch_words)} words")
        print_words("ctc-forced-aligner Torch Results (cold)", ctc_torch_words)
        results["CTC-Torch"] = {"words": ctc_torch_words, "cold_time": ctc_torch_cold}
    except Exception as e:
        ctc_torch_error = str(e)
        import traceback
        print(f"  ctc-forced-aligner Torch FAILED: {e}")
        traceback.print_exc()
        results["CTC-Torch"] = {"words": [], "cold_time": float("inf"), "error": ctc_torch_error}

    # ------------------------------------------------------------------- #
    # Side-by-side comparisons
    # ------------------------------------------------------------------- #
    tool_names = [k for k in results if results[k]["words"]]
    if len(tool_names) >= 2:
        for i in range(len(tool_names)):
            for j in range(i + 1, len(tool_names)):
                a, b = tool_names[i], tool_names[j]
                print_side_by_side(a, results[a]["words"], b, results[b]["words"])

    # ------------------------------------------------------------------- #
    # Statistics table
    # ------------------------------------------------------------------- #
    active = [k for k in results if results[k]["words"]]
    if active:
        print(f"\n{'='*90}")
        print("  TIMING STATISTICS")
        print(f"{'='*90}")
        header = f"  {'Metric':<30}"
        for name in active:
            header += f" {name:>18}"
        print(header)
        print(f"  {'-'*30}" + f" {'-'*18}" * len(active))

        all_stats = {name: compute_stats(results[name]["words"]) for name in active}

        for metric, key in [
            ("Total words detected", "count"),
            ("Words with timestamps", "valid"),
            ("Avg word duration (s)", "avg_dur"),
            ("Min word duration (s)", "min_dur"),
            ("Max word duration (s)", "max_dur"),
            ("Total span (s)", "total_span"),
        ]:
            row = f"  {metric:<30}"
            for name in active:
                val = all_stats[name][key]
                if isinstance(val, int):
                    row += f" {val:>18}"
                else:
                    row += f" {val:>18.4f}"
            print(row)

        row = f"  {'Cold-start time (s)':<30}"
        for name in active:
            row += f" {results[name]['cold_time']:>18.2f}"
        print(row)

        # Gap/overlap analysis
        print(f"\n  BOUNDARY QUALITY")
        print(f"  {'-'*70}")
        all_gaps = {}
        all_overlaps = {}
        for name in active:
            g, o = gap_analysis(results[name]["words"])
            all_gaps[name] = g
            all_overlaps[name] = o

        row = f"  {'Inter-word gaps':<30}"
        for name in active:
            row += f" {len(all_gaps[name]):>18}"
        print(row)

        row = f"  {'  Avg gap (s)':<30}"
        for name in active:
            g = all_gaps[name]
            if g:
                row += f" {sum(g)/len(g):>18.4f}"
            else:
                row += f" {'N/A':>18}"
        print(row)

        row = f"  {'  Max gap (s)':<30}"
        for name in active:
            g = all_gaps[name]
            if g:
                row += f" {max(g):>18.4f}"
            else:
                row += f" {'N/A':>18}"
        print(row)

        row = f"  {'Word overlaps':<30}"
        for name in active:
            row += f" {len(all_overlaps[name]):>18}"
        print(row)

        row = f"  {'  Avg overlap (s)':<30}"
        for name in active:
            o = all_overlaps[name]
            if o:
                row += f" {sum(o)/len(o):>18.4f}"
            else:
                row += f" {'N/A':>18}"
        print(row)

    # ------------------------------------------------------------------- #
    # Throughput (warm runs x3)
    # ------------------------------------------------------------------- #
    print(f"\n{'='*90}")
    print("  THROUGHPUT TEST (3 warm runs each, model already loaded)")
    print(f"{'='*90}")

    warm_results = {}

    if not wx_error:
        print("\n  WhisperX warm runs:")
        times = []
        for i in range(3):
            try:
                _, elapsed = run_whisperx_warm(
                    AUDIO_PATH, device, wx_model, wx_model_a, wx_metadata
                )
                times.append(elapsed)
                print(f"    Run {i+1}: {elapsed:.3f}s")
            except Exception as e:
                print(f"    Run {i+1}: FAILED - {e}")
        warm_results["WhisperX"] = times

    if not ctc_onnx_error:
        print("\n  ctc-forced-aligner ONNX warm runs:")
        times = []
        for i in range(3):
            try:
                _, elapsed = run_ctc_onnx_warm(
                    AUDIO_PATH, KNOWN_TEXT, ctc_alignment
                )
                times.append(elapsed)
                print(f"    Run {i+1}: {elapsed:.3f}s")
            except Exception as e:
                print(f"    Run {i+1}: FAILED - {e}")
        warm_results["CTC-ONNX"] = times

    if not ctc_torch_error:
        print("\n  ctc-forced-aligner Torch warm runs:")
        times = []
        for i in range(3):
            try:
                _, elapsed = run_ctc_torch_warm(
                    AUDIO_PATH, KNOWN_TEXT, ctc_torch_model
                )
                times.append(elapsed)
                print(f"    Run {i+1}: {elapsed:.3f}s")
            except Exception as e:
                print(f"    Run {i+1}: FAILED - {e}")
        warm_results["CTC-Torch"] = times

    print(f"\n{'='*90}")
    print("  THROUGHPUT SUMMARY")
    print(f"{'='*90}")
    avgs = {}
    for name, times in warm_results.items():
        if times:
            avg = sum(times) / len(times)
            avgs[name] = avg
            print(f"  {name:<30} avg warm time: {avg:.3f}s  (over {len(times)} runs)")
        else:
            print(f"  {name:<30} no successful warm runs")

    # Pairwise speed comparisons
    avg_names = list(avgs.keys())
    if len(avg_names) >= 2:
        print()
        fastest_name = min(avgs, key=avgs.get)
        fastest_time = avgs[fastest_name]
        for name in avg_names:
            if name != fastest_name:
                ratio = avgs[name] / fastest_time
                print(f"  {fastest_name} is {ratio:.1f}x faster than {name} (warm)")

    # ------------------------------------------------------------------- #
    # Errors
    # ------------------------------------------------------------------- #
    errors = {k: v.get("error") for k, v in results.items() if v.get("error")}
    if errors:
        print(f"\n{'='*90}")
        print("  ERRORS")
        print(f"{'='*90}")
        for name, err in errors.items():
            print(f"  {name}: {err}")

    # ------------------------------------------------------------------- #
    # Final verdict
    # ------------------------------------------------------------------- #
    print(f"\n{'='*90}")
    print("  VERDICT & RECOMMENDATIONS FOR yt-tts")
    print(f"{'='*90}")

    working_tools = [k for k in results if not results[k].get("error")]
    if len(working_tools) >= 2:
        print("""
  APPROACH COMPARISON:

  WhisperX (transcribe + align):
    - Does NOT need known text (full ASR transcription + forced alignment)
    - Uses faster-whisper for ASR, wav2vec2 for alignment
    - Better for discovery (when you don't know what's said)
    - Heavier: loads 2 models (Whisper + wav2vec2)
    - Pyannote VAD included (speaker-aware)
    - Transcription accuracy depends on Whisper model size

  ctc-forced-aligner ONNX (forced alignment only):
    - REQUIRES known text (forced alignment only, no ASR)
    - Uses wav2vec2 CTC emissions via ONNX Runtime (CPU or GPU)
    - Lightweight: single ONNX model, no torch dependency for inference
    - Very fast inference via ONNX optimizations

  ctc-forced-aligner Torch / MMS_FA:
    - REQUIRES known text
    - Uses torchaudio MMS_FA bundle for forced alignment
    - Higher quality alignment model (Meta's MMS)
    - Heavier torch dependency

  FOR yt-tts SPECIFICALLY:
    Since we already have transcript text from YouTube captions,
    a forced-alignment-only tool is the best fit:
    1. Skip the ASR transcription step entirely
    2. Alignment against known text is more accurate than ASR + align
    3. Faster throughput (no ASR inference needed)
    4. Tighter word boundaries = better clip stitching

  RECOMMENDED ARCHITECTURE:
    - Use ctc-forced-aligner (ONNX or Torch) as the primary alignment backend
    - Fall back to WhisperX / faster-whisper when transcript text is unavailable
    - The ONNX path is best for production (fast, no GPU required)
    - The Torch/MMS_FA path may give higher quality if GPU is available
""")
    elif len(working_tools) == 1:
        print(f"\n  Only {working_tools[0]} succeeded. Use it as primary backend.")
    else:
        print("\n  No tools worked successfully. Check installation.")

    print(f"\n{'='*90}")
    print("  BENCHMARK COMPLETE")
    print(f"{'='*90}")


if __name__ == "__main__":
    main()
