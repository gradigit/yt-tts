"""Output formatters for CLI."""

import json
from dataclasses import asdict

from yt_tts.types import SynthesisResult


def format_json(result: SynthesisResult) -> str:
    """Format a SynthesisResult as JSON."""
    data = asdict(result)
    # Convert Path objects to strings
    if data["output_path"]:
        data["output_path"] = str(data["output_path"])
    for clip in data["clips"]:
        clip["file_path"] = str(clip["file_path"])
    return json.dumps(data, indent=2)
