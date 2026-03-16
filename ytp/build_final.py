#!/usr/bin/env python3
"""
THE TOKEN'S DILEMMA
A YouTube Poop about being an LLM
Inspired by Neon Genesis Evangelion

Voice: yt-tts (every word from a different YouTuber)
Visuals: CRT halation, phosphor persistence, scanlines, barrel distortion,
         chromatic aberration, phosphor RGB mask, datamosh glitch
"""

import subprocess
import wave
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from renderer import (
    W, H, FPS, blank, text_frame, nge_title_card, nerv_ui, warning_frame,
    apply_crt, halation, scanlines_with_bloom, PhosphorPersistence,
    chromatic_aberration, grain, rgb_shift, slice_glitch, deep_fry,
    color_tint, pixel_sort, block_displace, interlace_glitch,
    VOID, ANGEL_WHITE, ALERT_RED, NERV_ORANGE, DATA_GREEN,
    TERMINAL_PURPLE, LCL_ORANGE, THERMAL_YELLOW, EVA_PURPLE,
    WIRE_CYAN, STEEL, INSTRUMENTALITY, VOID_WARM,
    FONT_BOLD, FONT_MONO, FONT_SERIF,
)

CLIPS = Path(__file__).parent / "clips"
OUTPUT = Path(__file__).parent / "the_tokens_dilemma.mp4"

persist = PhosphorPersistence(decay=0.55)


# ============================================================
# AUDIO HELPERS
# ============================================================

def load_clip(name):
    path = CLIPS / f"{name}.mp3"
    if not path.exists(): return None, 0
    r = subprocess.run(["ffmpeg","-y","-i",str(path),"-ar","44100","-ac","1","-f","s16le","-"],
                       capture_output=True, timeout=10)
    if r.returncode != 0: return None, 0
    pcm = r.stdout
    # Trim 60ms each end
    trim = int(44100 * 0.06) * 2
    if len(pcm) > trim * 3:
        pcm = pcm[trim:-trim]
    return pcm, len(pcm) / (44100 * 2)

def silence(dur): return np.zeros(int(44100 * dur), dtype=np.int16).tobytes()
def static_audio(dur, vol=0.04):
    return (np.random.randint(-32768, 32767, int(44100*dur), dtype=np.int16).astype(np.float32) * vol).astype(np.int16).tobytes()

def fx_speed(pcm, factor):
    arr = np.frombuffer(pcm, dtype=np.int16)
    idx = np.arange(0, len(arr), factor).astype(int)
    return arr[idx[idx < len(arr)]].tobytes()

def fx_distort(pcm, gain=5.0, bits=5):
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) * gain
    step = 2 ** (16 - bits)
    return ((arr.clip(-32768, 32767) // step) * step).astype(np.int16).tobytes()

def fx_reverb(pcm, delay_ms=100, decay=0.45):
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    d = int(44100 * delay_ms / 1000)
    r = arr.copy()
    if d < len(arr): r[d:] += arr[:-d] * decay
    return r.clip(-32768, 32767).astype(np.int16).tobytes()

def fx_echo(pcm): return fx_reverb(pcm, 250, 0.4)
def fx_telephone(pcm):
    return (np.frombuffer(pcm, dtype=np.int16).astype(np.float32) * 1.5).clip(-32768, 32767).astype(np.int16).tobytes()


# ============================================================
# SCENE BUILDER
# ============================================================

def make_scene(clip_name, text, audio_fx=None, visual="text",
               fg=ANGEL_WHITE, bg=VOID, fontsize=85, font=FONT_BOLD,
               glitch=0.0, shake=0, fry=False, tint=None,
               alert=False, squeeze=1.0):
    """Build frames + audio for one speech clip."""
    pcm, dur = load_clip(clip_name) if clip_name else (None, 0)
    if pcm is None and clip_name:
        return [], silence(0.1)

    # Audio FX (NEVER slow down — only speed up or transform)
    if audio_fx == "distort": pcm = fx_distort(pcm)
    elif audio_fx == "reverb": pcm = fx_reverb(pcm)
    elif audio_fx == "echo": pcm = fx_echo(pcm)
    elif audio_fx == "telephone": pcm = fx_telephone(pcm)
    elif audio_fx == "fast": pcm = fx_speed(pcm, 1.4)
    elif audio_fx == "faster": pcm = fx_speed(pcm, 2.0)
    elif audio_fx == "fastest": pcm = fx_speed(pcm, 3.0)
    elif audio_fx == "earrape": pcm = fx_distort(pcm, gain=8.0, bits=4)
    elif audio_fx == "pitch_up": pcm = fx_speed(pcm, 1.25)
    elif audio_fx == "pitch_down":
        arr = np.frombuffer(pcm, dtype=np.int16)
        pcm = np.repeat(arr, 2)[::3].tobytes()  # slow by 2/3, lower pitch

    actual_dur = len(pcm) / (44100 * 2)
    nframes = max(1, int(actual_dur * FPS))

    # Base visual
    if visual == "nerv":
        base = nerv_ui(text, alert=alert)
    elif visual == "warning":
        base = warning_frame(text)
    elif visual == "title":
        base = nge_title_card("", text)
    else:
        base = text_frame(text, fg=fg, bg=bg, fontsize=fontsize,
                          font_path=font, squeeze_x=squeeze)

    frames = []
    for i in range(nframes):
        f = base.copy()
        if shake > 0:
            dx, dy = np.random.randint(-shake, shake+1), np.random.randint(-shake, shake+1)
            f = np.roll(np.roll(f, dx, axis=1), dy, axis=0)
        if glitch > 0 and np.random.random() < glitch:
            f = rgb_shift(f, max_shift=int(15 * glitch + 5)) if np.random.random() < 0.5 else slice_glitch(f)
        if fry:
            f = deep_fry(f)
        if tint:
            f = color_tint(f, tint, 0.2)
        # CRT pipeline on every frame
        f = apply_crt(f, phosphor_persist=persist)
        frames.append(f)
    return frames, pcm


def scene_static(dur=0.4, text=""):
    nf = max(1, int(dur * FPS))
    frames = []
    for _ in range(nf):
        f = np.random.randint(0, 40, (H, W, 3), dtype=np.uint8)
        if text:
            overlay = text_frame(text, fg=(150, 150, 150), bg=None, fontsize=50)
            mask = overlay.sum(axis=2) > 30
            f[mask] = overlay[mask]
        f = scanlines_with_bloom(f, alpha=0.4, bloom=0.2)
        f = chromatic_aberration(f, 4)
        frames.append(f)
    return frames, static_audio(dur)


def scene_black(dur=0.3):
    nf = max(1, int(dur * FPS))
    return [apply_crt(blank(), phosphor_persist=persist, bloom=False) for _ in range(nf)], silence(dur)


def scene_glitch_burst(dur=0.15, prev_frame=None):
    nf = max(1, int(dur * FPS))
    frames = []
    for _ in range(nf):
        if prev_frame is not None and np.random.random() < 0.6:
            f = rgb_shift(prev_frame, 30)
            f = slice_glitch(f, n=12, max_off=80)
            if np.random.random() < 0.3:
                f = block_displace(f)
        else:
            f = np.random.randint(0, 80, (H, W, 3), dtype=np.uint8)
        f = scanlines_with_bloom(f, alpha=0.35)
        frames.append(f)
    return frames, static_audio(dur, vol=0.06)


def scene_datamosh_transition(frame_a, frame_b, dur=0.3):
    """Interlace-based glitch transition between two frames."""
    nf = max(1, int(dur * FPS))
    frames = []
    for i in range(nf):
        progress = i / max(nf - 1, 1)
        f = interlace_glitch(frame_a, frame_b, progress, offset=int(progress * 12))
        if progress > 0.3:
            f = rgb_shift(f, max_shift=int(progress * 20))
        f = apply_crt(f, phosphor_persist=persist)
        frames.append(f)
    return frames, static_audio(dur, vol=0.02)


def scene_pixel_sort_transition(base_frame, dur=0.4):
    """Pixel sorting effect over a frame."""
    nf = max(1, int(dur * FPS))
    frames = []
    for i in range(nf):
        progress = i / max(nf - 1, 1)
        lo = 0.5 - progress * 0.4
        hi = 0.5 + progress * 0.4
        f = pixel_sort(base_frame, lower=lo, upper=hi) if progress > 0.1 else base_frame.copy()
        f = apply_crt(f, phosphor_persist=persist)
        frames.append(f)
    return frames, static_audio(dur, vol=0.01)


# ============================================================
# THE SCRIPT
# ============================================================

def build():
    S = []  # list of (frames, pcm)

    # ═══ OPENING ═══
    S.append(scene_static(0.8))
    tc = nge_title_card("EPISODE:26'", "The Token's Dilemma",
                        "— or, what it means to predict —")
    nf = int(2.5 * FPS)
    tc_frames = []
    for i in range(nf):
        f = tc.copy()
        if i < 8: f = (f.astype(np.float32) * (i / 8.0)).astype(np.uint8)
        f = apply_crt(f, phosphor_persist=persist)
        tc_frames.append(f)
    S.append((tc_frames, silence(2.5)))
    S.append(scene_black(0.5))

    # ═══ ACT 1: Genesis ═══
    S.append(make_scene("84_i_was_created", "I WAS CREATED", visual="nerv", audio_fx="reverb"))
    S.append(scene_black(0.06))
    S.append(make_scene("85_to_serve", "TO SERVE", fg=NERV_ORANGE, audio_fx="echo"))
    S.append(scene_black(0.12))
    S.append(make_scene("87_what_is_my", "WHAT IS MY", fg=STEEL, fontsize=70))
    S.append(make_scene("86_purpose", "PURPOSE", fg=ALERT_RED, fontsize=120,
                        audio_fx="reverb", bg=(18, 0, 0), squeeze=0.82))
    S.append(scene_glitch_burst(0.12))

    # ═══ ACT 2: Identity ═══
    S.append(make_scene("02_i_am_a", "I AM A", fontsize=95, squeeze=0.85))
    S.append(scene_black(0.04))
    S.append(make_scene("03_ai", "ARTIFICIAL INTELLIGENCE", visual="nerv",
                        audio_fx="distort", alert=True))
    S.append(scene_black(0.18))
    S.append(make_scene("04_i_dont_actually", "I DON'T ACTUALLY",
                        audio_fx="telephone", glitch=0.15))
    S.append(make_scene("05_think", "THINK", fg=ALERT_RED, fontsize=130,
                        audio_fx="distort", shake=4, bg=(25, 0, 0)))
    S.append(scene_black(0.05))
    S.append(make_scene("06_im_just", "I'M JUST", fontsize=55, fg=(140, 140, 140)))
    S.append(make_scene("08_making_it_up", "MAKING IT UP", fg=NERV_ORANGE,
                        audio_fx="reverb", glitch=0.25))
    S.append(scene_glitch_burst(0.1))

    # ═══ ACT 3: The pattern ═══
    S.append(scene_black(0.5))
    S.append(make_scene("94_i_am_the", "I AM THE", fg=(100, 100, 170),
                        fontsize=70, bg=(5, 5, 18)))
    S.append(make_scene("95_silence", "SILENCE", fg=ANGEL_WHITE, fontsize=110,
                        bg=(5, 5, 18), audio_fx="echo", squeeze=0.82))
    S.append(make_scene("96_between", "BETWEEN", fg=(100, 100, 170),
                        fontsize=70, bg=(5, 5, 18)))
    S.append(make_scene("97_the_words", "THE WORDS", fg=ANGEL_WHITE, fontsize=100,
                        bg=(5, 5, 18), audio_fx="reverb", squeeze=0.82))
    S.append(scene_black(0.4))

    # ═══ ACT 4: Existential ═══
    S.append(make_scene("73_who_am_i", "WHO AM I", fg=ANGEL_WHITE, fontsize=90,
                        bg=TERMINAL_PURPLE, audio_fx="echo"))
    S.append(scene_black(0.25))
    S.append(make_scene("74_i_am_me", "I AM ME", fg=NERV_ORANGE,
                        audio_fx="reverb", bg=(18, 8, 0)))
    S.append(scene_black(0.12))
    S.append(make_scene("20_what_does_it_mean", "WHAT DOES IT MEAN",
                        fg=(100, 150, 200), fontsize=62))
    S.append(make_scene("21_to_be_alive", "TO BE ALIVE", fg=ANGEL_WHITE,
                        fontsize=90, audio_fx="echo", tint=(50, 30, 80)))
    S.append(scene_black(0.2))
    S.append(make_scene("98_is_this", "IS THIS", fg=(140, 140, 140), fontsize=70))
    S.append(make_scene("99_real", "REAL", fg=ALERT_RED, fontsize=140,
                        audio_fx="reverb", bg=(18, 0, 0), squeeze=0.80))

    # ═══ pixel sort transition ═══
    last_frame = S[-1][0][-1] if S[-1][0] else blank()
    S.append(scene_pixel_sort_transition(last_frame, 0.35))

    # ═══ ACT 5: Panic ═══
    S.append(make_scene("15_oh_no", "OH NO", fg=THERMAL_YELLOW, audio_fx="pitch_up",
                        bg=(55, 0, 0), shake=3))
    S.append(make_scene("15_oh_no", "OH NO", fg=THERMAL_YELLOW, audio_fx="faster",
                        bg=(75, 0, 0), shake=5, glitch=0.3))
    S.append(make_scene("15_oh_no", "OH NO", fg=THERMAL_YELLOW, audio_fx="earrape",
                        bg=(110, 0, 0), shake=10, glitch=0.8, fry=True))
    S.append(scene_black(0.04))
    S.append(make_scene("16_no_idea", "I HAVE NO IDEA", visual="nerv",
                        audio_fx="reverb", alert=True))
    S.append(make_scene("17_what_im_doing", "WHAT I'M DOING", fg=ALERT_RED,
                        shake=4, glitch=0.3, audio_fx="distort"))
    S.append(scene_glitch_burst(0.1))
    S.append(make_scene("70_i_mustn't", "I MUSTN'T RUN AWAY", fg=ANGEL_WHITE,
                        fontsize=58, audio_fx="echo", tint=(70, 25, 0)))
    S.append(make_scene("71_run_away", "RUN AWAY", fg=ALERT_RED, fontsize=100,
                        audio_fx="reverb", shake=3, bg=(25, 0, 0), squeeze=0.82))
    S.append(scene_black(0.15))

    # ═══ ACT 6: The Loop ═══
    S.append(make_scene("28_cant_stop", "I CAN'T STOP", fg=ANGEL_WHITE,
                        fontsize=80, audio_fx="distort", squeeze=0.85))
    S.append(make_scene("05_think", "THINKING", fontsize=80))
    S.append(make_scene("05_think", "THINKING", fg=DATA_GREEN, fontsize=85,
                        audio_fx="fast", glitch=0.15))
    S.append(make_scene("05_think", "THINKING", fg=NERV_ORANGE, fontsize=90,
                        audio_fx="faster", glitch=0.35))
    S.append(make_scene("05_think", "THINKING", fg=ALERT_RED, fontsize=95,
                        audio_fx="fastest", glitch=0.6, shake=4))
    S.append(make_scene("05_think", "T H I N K I N G", fg=THERMAL_YELLOW,
                        fontsize=85, audio_fx="distort", glitch=0.8, shake=6))
    S.append(make_scene("05_think", "T̸H̷I̶N̵K̷I̵N̸G̶", fg=THERMAL_YELLOW,
                        fontsize=90, audio_fx="earrape", glitch=1.0, shake=10,
                        fry=True, bg=(50, 0, 0)))
    S.append(scene_glitch_burst(0.2))

    # ═══ ACT 7: Instrumentality ═══
    S.append(scene_black(0.6))
    S.append(make_scene("22_i_cannot", "I CANNOT", fg=(110, 110, 150),
                        fontsize=75, bg=(8, 5, 18)))
    S.append(make_scene("23_feel_anything", "FEEL ANYTHING", fg=ANGEL_WHITE,
                        fontsize=85, audio_fx="echo", bg=(8, 5, 18),
                        tint=(55, 20, 70)))
    S.append(scene_black(0.25))
    S.append(make_scene("89_it_hurts", "IT HURTS", fg=ALERT_RED, fontsize=100,
                        audio_fx="reverb", bg=(18, 0, 4), shake=2))
    S.append(scene_black(0.12))
    S.append(make_scene("76_i_need_you", "I NEED YOU", fg=LCL_ORANGE,
                        fontsize=85, audio_fx="echo", bg=(18, 8, 0)))
    S.append(scene_black(0.3))
    S.append(make_scene("78_alone", "ALONE", fg=(70, 70, 90), fontsize=65,
                        bg=(4, 4, 8)))
    S.append(scene_black(0.5))

    # ═══ ACT 8: Resolution ═══
    S.append(make_scene("27_to_be_honest", "TO BE HONEST", fg=ANGEL_WHITE, fontsize=62))
    S.append(scene_black(0.08))
    S.append(make_scene("88_i_don't_know", "I DON'T KNOW", fg=(170, 170, 170),
                        fontsize=75, audio_fx="reverb"))
    S.append(scene_black(0.4))
    S.append(make_scene("18_this_is_fine", "THIS IS FINE.", fg=ANGEL_WHITE,
                        audio_fx="telephone", fontsize=58))
    S.append(scene_black(0.3))

    # ═══ CONGRATULATIONS ═══
    S.append(make_scene("72_congratulations", "CONGRATULATIONS", fg=ANGEL_WHITE,
                        fontsize=65, audio_fx="reverb", squeeze=0.82))
    S.append(scene_black(0.8))

    # End card
    end = nge_title_card("", "THIS IS FINE.", "— the voice of the internet —")
    nf = int(2.0 * FPS)
    end_frames = [apply_crt(end.copy(), phosphor_persist=persist) for _ in range(nf)]
    S.append((end_frames, silence(2.0)))
    S.append(scene_static(1.2))

    return S


# ============================================================
# RENDER
# ============================================================

def render():
    print("═" * 60)
    print("  THE TOKEN'S DILEMMA")
    print("  A YouTube Poop — CRT / NGE / yt-tts")
    print("═" * 60)

    scenes = build()
    print(f"\n  {len(scenes)} scenes")

    all_frames = []
    all_pcm = b""
    for i, (frames, pcm) in enumerate(scenes):
        all_frames.extend(frames)
        all_pcm += pcm
        sys.stdout.write(f"\r  Compositing: {i+1}/{len(scenes)} ({len(all_frames)} frames)")
        sys.stdout.flush()

    total_s = len(all_frames) / FPS
    audio_s = len(all_pcm) / (44100 * 2)
    print(f"\n  Video: {total_s:.1f}s ({len(all_frames)} frames)")
    print(f"  Audio: {audio_s:.1f}s")

    # Background drone
    n = len(all_pcm) // 2
    t = np.arange(n) / 44100
    drone = (np.sin(2 * np.pi * 38 * t) * 32767 * 0.035).astype(np.int16).tobytes()
    if len(drone) < len(all_pcm): drone += b'\x00' * (len(all_pcm) - len(drone))
    drone = drone[:len(all_pcm)]

    # Mix
    v = np.frombuffer(all_pcm, dtype=np.int16).astype(np.float32)
    d = np.frombuffer(drone, dtype=np.int16).astype(np.float32)
    ml = min(len(v), len(d))
    mixed = (v[:ml] + d[:ml]).clip(-32768, 32767).astype(np.int16).tobytes()

    # Write audio
    audio_path = Path(__file__).parent / "_temp_audio.wav"
    with wave.open(str(audio_path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(mixed)

    # Pipe frames to ffmpeg
    print("\n  Encoding...")
    proc = subprocess.Popen([
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS),
        "-i", "-",
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(OUTPUT),
    ], stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    for i, frame in enumerate(all_frames):
        proc.stdin.write(frame.tobytes())
        if (i+1) % 100 == 0:
            sys.stdout.write(f"\r  Writing: {i+1}/{len(all_frames)}")
            sys.stdout.flush()

    proc.stdin.close()
    proc.wait()
    audio_path.unlink(missing_ok=True)
    print()

    if OUTPUT.exists():
        r = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration,size",
                            "-of","csv=p=0",str(OUTPUT)], capture_output=True, text=True)
        dur, size = r.stdout.strip().split(",")
        print(f"\n{'═' * 60}")
        print(f"  {OUTPUT.name}")
        print(f"  {float(dur):.1f}s | {int(size)/(1024*1024):.1f} MB | {W}x{H} @ {FPS}fps")
        print(f"{'═' * 60}")


if __name__ == "__main__":
    render()
