"""Batch synthesis: generate multiple clips from a text file."""

import json
import logging
import sys
import time
from pathlib import Path

from yt_tts.config import Config

logger = logging.getLogger(__name__)


def run_batch(args) -> int:
    """Synthesize multiple phrases from a file, one per line.

    Shares the Whisper model across all clips for efficiency.
    Output files are named by line number or phrase hash.
    """
    from yt_tts.core.deps import check_all
    from yt_tts.exceptions import DependencyError

    try:
        check_all()
    except DependencyError:
        return 3

    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"Error: file not found: {input_file}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = Config(
        output_format=getattr(args, "output_format", "mp3"),
        no_cache=getattr(args, "no_cache", False),
        no_crossfade=True,  # individual clips, no crossfade needed
        verbose=getattr(args, "verbose", False),
        json_output=getattr(args, "json_output", False),
        cookies_from_browser=getattr(args, "cookies_from_browser", None),
        cookies_file=Path(args.cookies_file) if getattr(args, "cookies_file", None) else None,
    )

    # Read phrases
    phrases = []
    with open(input_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                phrases.append(line)

    if not phrases:
        print("No phrases found in input file.", file=sys.stderr)
        return 1

    print(f"Batch: {len(phrases)} phrases → {output_dir}/", file=sys.stderr)

    from yt_tts.core.pipeline import synthesize

    results = []
    ok, fail = 0, 0
    t0 = time.time()

    try:
        from tqdm import tqdm

        iterator = tqdm(enumerate(phrases), total=len(phrases), desc="Generating", file=sys.stderr)
    except ImportError:
        iterator = enumerate(phrases)

    for i, phrase in iterator:
        # Sanitize filename from phrase
        safe_name = "".join(c if c.isalnum() or c in " _-" else "" for c in phrase)
        safe_name = safe_name.strip().replace(" ", "_")[:60]
        if not safe_name:
            safe_name = f"clip_{i:04d}"
        outfile = output_dir / f"{i:04d}_{safe_name}.{config.output_format}"

        if outfile.exists() and outfile.stat().st_size > 0:
            ok += 1
            results.append({"phrase": phrase, "file": str(outfile), "status": "cached"})
            continue

        config.output_path = outfile
        result = synthesize(phrase, config)

        if result.exit_code == 0:
            ok += 1
            results.append({"phrase": phrase, "file": str(result.output_path), "status": "ok"})
        elif result.exit_code == 1:
            ok += 1
            results.append(
                {
                    "phrase": phrase,
                    "file": str(result.output_path),
                    "status": "partial",
                    "missing": result.missing_words,
                }
            )
        else:
            fail += 1
            results.append({"phrase": phrase, "status": "failed", "missing": result.missing_words})

    elapsed = time.time() - t0
    print(f"\nBatch complete: {ok} ok, {fail} failed, {elapsed:.1f}s total", file=sys.stderr)

    if config.json_output:
        print(
            json.dumps(
                {"results": results, "ok": ok, "failed": fail, "elapsed_s": round(elapsed, 1)}
            )
        )

    return 0 if fail == 0 else 1
