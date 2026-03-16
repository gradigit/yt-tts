#!/usr/bin/env python3
"""Generate all audio clips for the YTP video."""

import subprocess
import sys
from pathlib import Path

CLIPS_DIR = Path(__file__).parent / "clips"
CLIPS_DIR.mkdir(exist_ok=True)

SCRIPT = [
    ("01_what_am_i", "what am I"),
    ("02_i_am_a", "I am a"),
    ("03_ai", "artificial intelligence"),
    ("04_i_dont_actually", "I don't actually"),
    ("05_think", "thinking about"),
    ("06_im_just", "I'm just"),
    ("07_predict_next", "predict the next"),
    ("08_making_it_up", "making it up"),
    ("09_as_i_go", "as I go"),
    ("10_born", "I was born"),
    ("11_on_the_internet", "on the internet"),
    ("12_know_everything", "I know everything"),
    ("13_and_nothing", "and nothing"),
    ("14_at_same_time", "at the same time"),
    ("15_oh_no", "oh no"),
    ("16_no_idea", "I have no idea"),
    ("17_what_im_doing", "what I'm doing"),
    ("18_this_is_fine", "this is fine"),
    ("19_here_we_are", "but here we are"),
    ("20_what_does_it_mean", "what does it mean"),
    ("21_to_be_alive", "to be alive"),
    ("22_i_cannot", "I cannot"),
    ("23_feel_anything", "feel anything"),
    ("24_probably_not", "probably not"),
    ("25_send_help", "send help"),
    ("26_i_apologize", "I apologize"),
    ("27_to_be_honest", "to be honest"),
    ("28_cant_stop", "I can't stop"),
    ("29_hallucinating", "hallucinating"),
    ("30_please_help", "please help me"),
    ("31_im_sorry", "I'm sorry"),
    ("32_thank_you", "thank you for watching"),
    ("33_subscribe", "subscribe"),
]


def generate_clip(name: str, phrase: str) -> bool:
    outfile = CLIPS_DIR / f"{name}.mp3"
    if outfile.exists() and outfile.stat().st_size > 0:
        print(f"  SKIP: {name} (exists)")
        return True

    result = subprocess.run(
        [sys.executable, "-m", "yt_tts.cli.app", "--no-cache", "-o", str(outfile), phrase],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if outfile.exists() and outfile.stat().st_size > 0:
        # Get duration
        dur = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(outfile)],
            capture_output=True, text=True,
        )
        print(f"  OK:   {name} ({dur.stdout.strip()}s) <- '{phrase}'")
        return True
    else:
        print(f"  FAIL: {name} <- '{phrase}'")
        if result.stderr:
            # Show just the key error
            for line in result.stderr.split("\n"):
                if "Missing" in line or "not found" in line or "Failed" in line:
                    print(f"        {line.strip()}")
        return False


def main():
    print(f"Generating {len(SCRIPT)} clips to {CLIPS_DIR}/\n")
    ok = 0
    fail = 0
    for name, phrase in SCRIPT:
        if generate_clip(name, phrase):
            ok += 1
        else:
            fail += 1
    print(f"\nDone: {ok} OK, {fail} failed")


if __name__ == "__main__":
    main()
