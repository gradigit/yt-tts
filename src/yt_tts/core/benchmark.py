"""End-to-end quality benchmark for yt-tts synthesis.

Synthesizes text, transcribes the output with ASR, and computes
quality metrics including Word Error Rate (WER), precision, and recall.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class ClipScore:
    """Quality score for a single synthesized clip."""
    line_num: int
    intended: str
    heard: str
    recall: float  # fraction of intended words that appear in heard
    precision: float  # fraction of heard words that are intended
    extra_words: list[str] = field(default_factory=list)
    missing_words: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    expected_duration_s: float = 0.0
    grade: str = ""  # A/B/C/F

    def __post_init__(self):
        if self.recall >= 0.9 and self.precision >= 0.7:
            self.grade = "A"
        elif self.recall >= 0.7 and self.precision >= 0.5:
            self.grade = "B"
        elif self.recall >= 0.5:
            self.grade = "C"
        else:
            self.grade = "F"


@dataclass
class BenchmarkResult:
    """Full benchmark result for a multi-line synthesis."""
    clips: list[ClipScore]
    total_wer: float
    avg_recall: float
    avg_precision: float
    grade_counts: dict[str, int] = field(default_factory=dict)
    total_duration_s: float = 0.0

    @property
    def summary(self) -> str:
        total = len(self.clips)
        lines = [
            f"=== BENCHMARK RESULTS ===",
            f"Clips: {total}",
            f"WER: {self.total_wer:.1%}",
            f"Avg recall: {self.avg_recall:.1%}",
            f"Avg precision: {self.avg_precision:.1%}",
            f"Duration: {self.total_duration_s:.1f}s",
            f"Grades: {self.grade_counts}",
        ]
        return "\n".join(lines)


def _clean(text: str) -> list[str]:
    """Normalize text for comparison."""
    return re.sub(r"[^\w\s']", "", text.lower()).split()


def score_clip(intended: str, audio_path: str, line_num: int = 0,
               model_size: str = "small") -> ClipScore:
    """Score a single clip by transcribing and comparing to intended text."""
    from faster_whisper import WhisperModel

    # Transcribe
    model = WhisperModel(model_size, device="cuda" if _has_cuda() else "cpu",
                         compute_type="float16" if _has_cuda() else "int8")
    segments, _ = model.transcribe(audio_path)
    heard = " ".join(s.text.strip() for s in segments)

    intended_words = _clean(intended)
    heard_words = _clean(heard)

    if not intended_words:
        return ClipScore(line_num=line_num, intended=intended, heard=heard,
                        recall=1.0, precision=1.0)

    # Compute recall (what fraction of intended words appear in heard)
    intended_set = set(intended_words)
    heard_set = set(heard_words)
    overlap = intended_set & heard_set
    recall = len(overlap) / len(intended_set) if intended_set else 1.0
    precision = len(overlap) / len(heard_set) if heard_set else 1.0

    extra = sorted(heard_set - intended_set)
    missing = sorted(intended_set - heard_set)

    # Duration
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_path],
        capture_output=True, text=True,
    )
    duration_s = float(result.stdout.strip()) if result.stdout.strip() else 0.0
    expected_s = len(intended_words) * 0.4

    return ClipScore(
        line_num=line_num,
        intended=intended,
        heard=heard,
        recall=recall,
        precision=precision,
        extra_words=extra,
        missing_words=missing,
        duration_s=duration_s,
        expected_duration_s=expected_s,
    )


def benchmark_speech(text_path: str, clips_dir: str,
                     model_size: str = "small") -> BenchmarkResult:
    """Benchmark a full speech synthesis by scoring each clip."""
    lines = open(text_path).read().strip().split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    clips = []
    for i, line in enumerate(lines, 1):
        f = f"{i:02d}.mp3"
        path = os.path.join(clips_dir, f)
        if not os.path.exists(path) or os.path.getsize(path) < 500:
            clips.append(ClipScore(
                line_num=i, intended=line, heard="", recall=0.0,
                precision=0.0, missing_words=line.split(), grade="F",
            ))
            continue
        clips.append(score_clip(line, path, line_num=i, model_size=model_size))

    # Compute aggregate metrics
    recalls = [c.recall for c in clips]
    precisions = [c.precision for c in clips]
    avg_recall = sum(recalls) / len(recalls) if recalls else 0
    avg_precision = sum(precisions) / len(precisions) if precisions else 0

    # WER from full text comparison
    all_intended = " ".join(c.intended for c in clips)
    all_heard = " ".join(c.heard for c in clips)
    intended_words = _clean(all_intended)
    heard_words = _clean(all_heard)
    matcher = SequenceMatcher(None, intended_words, heard_words)
    matches = sum(b.size for b in matcher.get_matching_blocks())
    wer = 1 - (matches / max(len(intended_words), 1))

    grade_counts = {}
    for c in clips:
        grade_counts[c.grade] = grade_counts.get(c.grade, 0) + 1

    total_dur = sum(c.duration_s for c in clips)

    return BenchmarkResult(
        clips=clips,
        total_wer=wer,
        avg_recall=avg_recall,
        avg_precision=avg_precision,
        grade_counts=grade_counts,
        total_duration_s=total_dur,
    )


def _has_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False
