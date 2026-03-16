"""Cross-platform ASR backend selector.

Priority: CUDA (faster-whisper) > MLX (mlx-whisper/parakeet-mlx) > CPU (faster-whisper)

All backends expose a unified interface returning word-level timestamps.
"""

import logging
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

Backend = Literal["cuda", "mlx", "cpu"]

# Module-level model cache
_backend: Backend | None = None
_model = None
_model_id: str | None = None


@dataclass
class WordInfo:
    """Unified word timestamp from any ASR backend."""

    word: str
    start: float  # seconds
    end: float  # seconds
    probability: float


@dataclass
class TranscribeResult:
    """Unified transcription result."""

    text: str
    words: list[WordInfo]
    language: str


def detect_backend(preferred: str = "auto") -> Backend:
    """Detect the best available ASR backend."""
    if preferred == "faster-whisper":
        return "cuda" if _has_cuda() else "cpu"
    if preferred == "mlx":
        if _has_mlx():
            return "mlx"
        logger.warning("MLX requested but not available, falling back to CPU")
        return "cpu"

    # Auto-detect
    if _has_cuda():
        return "cuda"
    if _has_mlx():
        return "mlx"
    return "cpu"


def _has_cuda() -> bool:
    """Check if CUDA is available for faster-whisper."""
    try:
        # Preload CUDA libs from common locations
        import ctypes
        import os

        for d in ["/usr/local/lib/ollama/cuda_v12", "/usr/local/cuda/lib64"]:
            for lib in ["libcublas.so.12", "libcublasLt.so.12"]:
                p = os.path.join(d, lib)
                if os.path.isfile(p):
                    try:
                        ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)
                    except OSError:
                        pass

        import ctranslate2

        return bool(ctranslate2.get_supported_compute_types("cuda"))
    except Exception:
        return False


def _has_mlx() -> bool:
    """Check if MLX (Apple Silicon) is available."""
    if sys.platform != "darwin" or platform.machine() != "arm64":
        return False
    try:
        import mlx.core as mx

        return mx.metal.is_available()
    except ImportError:
        return False


def forced_align(
    audio_path: str | Path,
    known_text: str,
) -> TranscribeResult:
    """Align known text to audio using CTC forced alignment.

    This is BETTER than ASR when you already know what words are in the audio.
    Uses torchaudio MMS_FA model — no recognition step, just alignment.
    ~30ms word boundary accuracy vs ~200ms for Whisper.
    """
    return _forced_align_ctc(str(audio_path), known_text)


def transcribe(
    audio_path: str | Path,
    model_size: str = "tiny",
    backend: str = "auto",
) -> TranscribeResult:
    """Transcribe audio and get word-level timestamps.

    Use forced_align() instead when you already know the transcript text.
    This is the fallback for --video mode where transcripts are unknown.
    """
    global _backend, _model, _model_id

    resolved_backend = detect_backend(backend)

    if resolved_backend == "mlx":
        return _transcribe_mlx(str(audio_path), model_size)
    elif resolved_backend == "cuda":
        return _transcribe_faster_whisper(str(audio_path), model_size, "cuda")
    else:
        return _transcribe_faster_whisper(str(audio_path), model_size, "cpu")


def _transcribe_faster_whisper(audio_path: str, model_size: str, device: str) -> TranscribeResult:
    """Transcribe using faster-whisper (CUDA or CPU)."""
    global _model, _model_id

    compute_type = "float16" if device == "cuda" else "int8"
    model_key = f"fw:{model_size}:{device}:{compute_type}"

    if _model_id != model_key:
        from faster_whisper import WhisperModel

        logger.info("Loading faster-whisper '%s' on %s (%s)", model_size, device, compute_type)
        try:
            _model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception:
            if device == "cuda":
                logger.warning("CUDA failed, falling back to CPU")
                device, compute_type = "cpu", "int8"
                _model = WhisperModel(model_size, device=device, compute_type=compute_type)
                model_key = f"fw:{model_size}:{device}:{compute_type}"
            else:
                raise
        _model_id = model_key

    segments, info = _model.transcribe(audio_path, word_timestamps=True)

    words = []
    text_parts = []
    for seg in segments:
        text_parts.append(seg.text)
        if seg.words:
            for w in seg.words:
                words.append(
                    WordInfo(
                        word=w.word.strip(),
                        start=w.start,
                        end=w.end,
                        probability=w.probability,
                    )
                )

    return TranscribeResult(
        text=" ".join(text_parts).strip(),
        words=words,
        language=info.language,
    )


def _transcribe_mlx(audio_path: str, model_size: str) -> TranscribeResult:
    """Transcribe using mlx-whisper or parakeet-mlx on Apple Silicon."""
    # Try parakeet-mlx first (faster, better timestamps for English)
    try:
        return _transcribe_parakeet_mlx(audio_path)
    except ImportError:
        pass

    # Fall back to mlx-whisper
    try:
        return _transcribe_mlx_whisper(audio_path, model_size)
    except ImportError:
        pass

    raise ImportError(
        "No MLX ASR backend found. Install one:\n"
        "  pip install parakeet-mlx    # fastest, English\n"
        "  pip install mlx-whisper     # multilingual"
    )


def _transcribe_parakeet_mlx(audio_path: str) -> TranscribeResult:
    """Transcribe using parakeet-mlx (fastest on Apple Silicon, English only)."""
    from parakeet_mlx import from_pretrained

    global _model, _model_id
    model_key = "parakeet-mlx"
    if _model_id != model_key:
        logger.info("Loading parakeet-mlx (TDT 0.6b)")
        _model = from_pretrained("mlx-community/parakeet-tdt-0.6b-v3")
        _model_id = model_key

    result = _model.transcribe(audio_path)

    words = []
    for sent in result.sentences:
        for tok in sent.tokens:
            words.append(
                WordInfo(
                    word=tok.text.strip(),
                    start=tok.start,
                    end=tok.end if hasattr(tok, "end") else tok.start + tok.duration,
                    probability=1.0,
                )
            )

    return TranscribeResult(text=result.text, words=words, language="en")


def _transcribe_mlx_whisper(audio_path: str, model_size: str) -> TranscribeResult:
    """Transcribe using mlx-whisper."""
    import mlx_whisper

    model_map = {
        "tiny": "mlx-community/whisper-tiny.en-mlx",
        "base": "mlx-community/whisper-base-mlx-q4",
        "small": "mlx-community/whisper-small-mlx-4bit",
        "medium": "mlx-community/whisper-medium-mlx-8bit",
        "large-v3": "mlx-community/whisper-large-v3-turbo",
    }
    repo = model_map.get(model_size, model_map["tiny"])

    logger.info("Loading mlx-whisper '%s'", model_size)
    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=repo,
        word_timestamps=True,
    )

    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            words.append(
                WordInfo(
                    word=w["word"].strip(),
                    start=w["start"],
                    end=w["end"],
                    probability=w.get("probability", 0.0),
                )
            )

    return TranscribeResult(
        text=result.get("text", "").strip(),
        words=words,
        language=result.get("language", "en"),
    )


# ============================================================
# CTC Forced Alignment (MahmoudAshraf97/ctc-forced-aligner)
# ============================================================

_fa_model = None


def _forced_align_ctc(audio_path: str, known_text: str) -> TranscribeResult:
    """Align known text to audio using ctc-forced-aligner with MMS_FA.

    This skips ASR recognition entirely — just maps known words to
    timestamps in the audio. ~30ms boundary accuracy.
    Uses the proven ctc_forced_aligner library (not hand-rolled torchaudio).
    """
    global _fa_model

    import tempfile

    from ctc_forced_aligner import get_word_stamps

    # Write known text to a temp file (library requires a file path)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(known_text)
        transcript_path = f.name

    try:
        word_timestamps, _, model = get_word_stamps(
            audio_path, transcript_path, model=_fa_model, model_type="MMS_FA"
        )
        _fa_model = model  # cache for reuse
    finally:
        import os

        os.unlink(transcript_path)

    # Parse results — the library returns nested lists of word dicts
    result_words = []
    for entry in word_timestamps:
        if isinstance(entry, dict):
            result_words.append(
                WordInfo(
                    word=entry.get("text", entry.get("word", "")),
                    start=float(entry.get("start", entry.get("start_time", 0))),
                    end=float(entry.get("end", entry.get("end_time", 0))),
                    probability=1.0,
                )
            )
        elif isinstance(entry, (list, tuple)):
            for w in entry:
                if isinstance(w, dict):
                    result_words.append(
                        WordInfo(
                            word=w.get("text", w.get("word", "")),
                            start=float(w.get("start", w.get("start_time", 0))),
                            end=float(w.get("end", w.get("end_time", 0))),
                            probability=1.0,
                        )
                    )

    return TranscribeResult(
        text=known_text,
        words=result_words,
        language="en",
    )
