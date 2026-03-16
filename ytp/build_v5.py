#!/usr/bin/env python3
"""
THE TOKEN'S DILEMMA v5
Video backgrounds, datamosh, generative visuals, CRT effects
"""

import subprocess, wave, sys, random
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from renderer import (
    W, H, FPS, blank, text_frame, nge_title_card, nerv_ui, warning_frame,
    apply_crt, PhosphorPersistence, rgb_shift, slice_glitch, deep_fry,
    color_tint, pixel_sort, block_displace, halation, chromatic_aberration,
    grain, scanlines_with_bloom,
    VOID, ANGEL_WHITE, ALERT_RED, NERV_ORANGE, DATA_GREEN, THERMAL_YELLOW,
    EVA_PURPLE, WIRE_CYAN, STEEL, LCL_ORANGE, TERMINAL_PURPLE,
    INSTRUMENTALITY, FONT_BOLD, FONT_MONO, FONT_SERIF,
)
from visuals import (
    get_random_texture, video_bg_frame, oscilloscope, neural_net_pattern,
    hex_grid, cross_pattern, data_rain, composite, blend_add, blend_screen,
)

CLIPS = Path(__file__).parent / "clips"
OUTPUT = Path(__file__).parent / "the_tokens_dilemma_v5.mp4"
persist = PhosphorPersistence(decay=0.50)

# Preload textures
print("Loading video textures...")
TEX_DATAMOSH = get_random_texture("datamosh")
TEX_DEEPFRY = get_random_texture("deepfry")
TEX_EDGES = get_random_texture("edges")
TEX_GLITCH = get_random_texture("glitch")
print(f"  Loaded: datamosh={len(TEX_DATAMOSH or [])} deepfry={len(TEX_DEEPFRY or [])} "
      f"edges={len(TEX_EDGES or [])} glitch={len(TEX_GLITCH or [])} frames")

# ============================================================
# AUDIO
# ============================================================
def load_clip(name):
    path = CLIPS / f"{name}.mp3"
    if not path.exists(): return None, 0
    r = subprocess.run(["ffmpeg","-y","-i",str(path),"-ar","44100","-ac","1","-f","s16le","-"],
                       capture_output=True, timeout=10)
    if r.returncode != 0: return None, 0
    pcm = r.stdout
    trim = int(44100 * 0.06) * 2
    if len(pcm) > trim * 3: pcm = pcm[trim:-trim]
    return pcm, len(pcm) / (44100 * 2)

def silence(d): return np.zeros(int(44100*d), dtype=np.int16).tobytes()
def static_audio(d, v=0.04, vol=None):
    if vol is not None: v = vol
    return (np.random.randint(-32768,32767,int(44100*d),dtype=np.int16).astype(np.float32)*v).astype(np.int16).tobytes()
def fx_speed(p, f):
    a=np.frombuffer(p,dtype=np.int16); i=np.arange(0,len(a),f).astype(int); return a[i[i<len(a)]].tobytes()
def fx_distort(p, g=5.0, b=5):
    a=np.frombuffer(p,dtype=np.int16).astype(np.float32)*g; s=2**(16-b); return ((a.clip(-32768,32767)//s)*s).astype(np.int16).tobytes()
def fx_reverb(p, d=100, dc=0.45):
    a=np.frombuffer(p,dtype=np.int16).astype(np.float32); n=int(44100*d/1000); r=a.copy()
    if n<len(a): r[n:]+=a[:-n]*dc
    return r.clip(-32768,32767).astype(np.int16).tobytes()
def fx_echo(p): return fx_reverb(p, 250, 0.4)
def fx_telephone(p): return (np.frombuffer(p,dtype=np.int16).astype(np.float32)*1.5).clip(-32768,32767).astype(np.int16).tobytes()

# ============================================================
# SCENE BUILDER
# ============================================================
_frame_counter = [0]  # mutable counter for texture indexing

def _bg(style, frame_offset=0):
    """Get a background frame from video textures + generative visuals."""
    idx = _frame_counter[0] + frame_offset
    if style == "datamosh":
        bg = video_bg_frame(TEX_DATAMOSH, idx, opacity=0.35)
    elif style == "deepfry":
        bg = video_bg_frame(TEX_DEEPFRY, idx, opacity=0.25)
    elif style == "edges":
        bg = video_bg_frame(TEX_EDGES, idx, opacity=0.3)
    elif style == "glitch":
        bg = video_bg_frame(TEX_GLITCH, idx, opacity=0.3)
    elif style == "neural":
        bg = neural_net_pattern(idx, color=WIRE_CYAN)
    elif style == "hex":
        bg = hex_grid(idx, color=NERV_ORANGE)
    elif style == "cross":
        bg = cross_pattern(idx, size=250)
    elif style == "rain":
        bg = data_rain(idx)
    elif style == "hex+edges":
        bg = video_bg_frame(TEX_EDGES, idx, opacity=0.2)
        bg = hex_grid(idx, color=NERV_ORANGE, bg=bg)
    elif style == "neural+datamosh":
        bg = video_bg_frame(TEX_DATAMOSH, idx, opacity=0.25)
        bg = neural_net_pattern(idx, color=WIRE_CYAN, bg=bg)
    elif style == "cross+glitch":
        bg = video_bg_frame(TEX_GLITCH, idx, opacity=0.2)
        bg = cross_pattern(idx, color=ALERT_RED, size=300, bg=bg)
    elif style == "rain+deepfry":
        bg = video_bg_frame(TEX_DEEPFRY, idx, opacity=0.15)
        bg = data_rain(idx, bg=bg)
    else:
        bg = blank()
    return bg


def make_scene(clip_name, text, audio_fx=None, bg_style="void",
               fg=ANGEL_WHITE, fontsize=85, font=FONT_BOLD,
               glitch=0.0, shake=0, fry=False, tint=None,
               alert=False, squeeze=1.0, visual="text",
               text_alpha=0.9):
    """Build frames + audio for one speech clip with video backgrounds."""
    pcm, dur = load_clip(clip_name) if clip_name else (None, 0)
    if pcm is None and clip_name:
        return [], silence(0.1)

    # Audio FX
    if audio_fx == "distort": pcm = fx_distort(pcm)
    elif audio_fx == "reverb": pcm = fx_reverb(pcm)
    elif audio_fx == "echo": pcm = fx_echo(pcm)
    elif audio_fx == "telephone": pcm = fx_telephone(pcm)
    elif audio_fx == "fast": pcm = fx_speed(pcm, 1.4)
    elif audio_fx == "faster": pcm = fx_speed(pcm, 2.0)
    elif audio_fx == "fastest": pcm = fx_speed(pcm, 3.0)
    elif audio_fx == "earrape": pcm = fx_distort(pcm, 8.0, 4)
    elif audio_fx == "pitch_up": pcm = fx_speed(pcm, 1.25)
    elif audio_fx == "pitch_down":
        a = np.frombuffer(pcm, dtype=np.int16)
        pcm = np.repeat(a, 2)[::3].tobytes()

    actual_dur = len(pcm) / (44100 * 2)
    nframes = max(1, int(actual_dur * FPS))

    # Generate text overlay
    if visual == "nerv":
        text_layer = nerv_ui(text, alert=alert)
    elif visual == "warning":
        text_layer = warning_frame(text)
    else:
        text_layer = text_frame(text, fg=fg, bg=(0, 0, 0), fontsize=fontsize,
                                font_path=font, squeeze_x=squeeze)

    frames = []
    for i in range(nframes):
        # Video background
        bg = _bg(bg_style, i)

        # Composite text over background
        if visual in ("nerv", "warning"):
            f = text_layer.copy()
            # Blend video texture into dark areas of UI
            mask = text_layer.sum(axis=2) < 40
            f[mask] = bg[mask]
        else:
            # Text composited over video bg
            text_mask = text_layer.sum(axis=2) > 20
            f = bg.copy()
            f[text_mask] = (text_layer[text_mask].astype(np.float32) * text_alpha +
                            bg[text_mask].astype(np.float32) * (1 - text_alpha)).astype(np.uint8)

        if shake > 0:
            dx, dy = np.random.randint(-shake, shake+1), np.random.randint(-shake, shake+1)
            f = np.roll(np.roll(f, dx, axis=1), dy, axis=0)
        if glitch > 0 and np.random.random() < glitch:
            f = rgb_shift(f, int(12*glitch+5)) if np.random.random()<0.5 else slice_glitch(f)
        if fry:
            f = deep_fry(f)
        if tint:
            f = color_tint(f, tint, 0.15)

        f = apply_crt(f, phosphor_persist=persist)
        _frame_counter[0] += 1
        frames.append(f)

    return frames, pcm


def scene_static(dur=0.4):
    nf = max(1, int(dur * FPS))
    frames = []
    for i in range(nf):
        f = np.random.randint(0, 40, (H, W, 3), dtype=np.uint8)
        # Mix in some video texture
        if TEX_GLITCH:
            vf = video_bg_frame(TEX_GLITCH, _frame_counter[0] + i, opacity=0.15)
            f = blend_add(f, vf, 0.3)
        f = scanlines_with_bloom(f, alpha=0.4, bloom=0.2)
        f = chromatic_aberration(f, 5)
        frames.append(f)
    return frames, static_audio(dur)


def scene_black(dur=0.3):
    nf = max(1, int(dur * FPS))
    frames = []
    for i in range(nf):
        f = blank()
        # Subtle video texture ghost in the black
        if TEX_DATAMOSH and random.random() < 0.3:
            vf = video_bg_frame(TEX_DATAMOSH, _frame_counter[0]+i, opacity=0.06)
            f = blend_add(f, vf, 0.5)
        f = apply_crt(f, phosphor_persist=persist, bloom=False)
        _frame_counter[0] += 1
        frames.append(f)
    return frames, silence(dur)


def scene_glitch_burst(dur=0.15, use_video=True):
    nf = max(1, int(dur * FPS))
    frames = []
    for i in range(nf):
        if use_video and TEX_GLITCH:
            f = TEX_GLITCH[(_frame_counter[0]+i) % len(TEX_GLITCH)].copy()
            f = rgb_shift(f, 25)
            f = slice_glitch(f, n=10, max_off=60)
            if random.random() < 0.4:
                f = block_displace(f, n=8)
        else:
            f = np.random.randint(0, 80, (H, W, 3), dtype=np.uint8)
        f = scanlines_with_bloom(f, alpha=0.35)
        frames.append(f)
    return frames, static_audio(dur, vol=0.06)


def scene_datamosh_transition(dur=0.3):
    """Pure datamosh video texture."""
    nf = max(1, int(dur * FPS))
    frames = []
    for i in range(nf):
        if TEX_DATAMOSH:
            f = TEX_DATAMOSH[(_frame_counter[0]+i) % len(TEX_DATAMOSH)].copy()
            # Slight color tint
            f = color_tint(f, ALERT_RED, 0.15)
            f = chromatic_aberration(f, 4)
        else:
            f = np.random.randint(0, 50, (H, W, 3), dtype=np.uint8)
        f = apply_crt(f, phosphor_persist=persist)
        _frame_counter[0] += 1
        frames.append(f)
    return frames, static_audio(dur, vol=0.03)


def scene_oscilloscope(pcm, text="", dur=None, color=DATA_GREEN):
    """Oscilloscope visualization of audio."""
    if dur is None:
        dur = len(pcm) / (44100 * 2) if pcm else 1.0
    nf = max(1, int(dur * FPS))
    frames = []
    for i in range(nf):
        # Video texture background
        bg = video_bg_frame(TEX_EDGES, _frame_counter[0]+i, opacity=0.12)
        f = oscilloscope(pcm, i, nf, color=color, bg=bg)
        if text:
            txt = text_frame(text, fg=ANGEL_WHITE, bg=(0,0,0), fontsize=50)
            mask = txt.sum(axis=2) > 15
            f[mask] = (txt[mask].astype(np.float32)*0.7 + f[mask].astype(np.float32)*0.3).astype(np.uint8)
        f = apply_crt(f, phosphor_persist=persist)
        _frame_counter[0] += 1
        frames.append(f)
    return frames


# ============================================================
# THE SCRIPT
# ============================================================

def build():
    S = []

    # ═══ OPENING ═══
    S.append(scene_static(0.6))
    S.append(scene_datamosh_transition(0.4))

    # Title card with neural net background
    tc = nge_title_card("EPISODE:26'", "The Token's Dilemma",
                        "— or, what it means to predict —")
    nf = int(2.8 * FPS)
    tc_frames = []
    for i in range(nf):
        bg = neural_net_pattern(i, nodes=25, connections=40, color=(30, 60, 100))
        bg = hex_grid(i, color=(15, 30, 50), bg=bg)
        f = tc.copy()
        if i < 10: f = (f.astype(np.float32) * (i/10.0)).astype(np.uint8)
        # Blend title over generative bg
        mask = f.sum(axis=2) > 15
        result = bg.copy()
        result[mask] = f[mask]
        result = apply_crt(result, phosphor_persist=persist)
        _frame_counter[0] += 1
        tc_frames.append(result)
    S.append((tc_frames, silence(2.8)))
    S.append(scene_black(0.4))

    # ═══ ACT 1: Genesis ═══
    S.append(make_scene("84_i_was_created", "I WAS CREATED", visual="nerv",
                        audio_fx="reverb", bg_style="hex+edges"))
    S.append(scene_black(0.06))
    S.append(make_scene("85_to_serve", "TO SERVE", fg=NERV_ORANGE,
                        audio_fx="echo", bg_style="neural"))
    S.append(scene_black(0.12))
    S.append(make_scene("87_what_is_my", "WHAT IS MY", fg=STEEL,
                        fontsize=70, bg_style="hex"))
    S.append(make_scene("86_purpose", "PURPOSE", fg=ALERT_RED, fontsize=120,
                        audio_fx="reverb", squeeze=0.82, bg_style="cross+glitch"))
    S.append(scene_glitch_burst(0.12))

    # ═══ ACT 2: Identity ═══
    S.append(make_scene("02_i_am_a", "I AM A", fontsize=95, squeeze=0.85,
                        bg_style="datamosh"))
    S.append(scene_black(0.04))
    S.append(make_scene("03_ai", "ARTIFICIAL INTELLIGENCE", visual="nerv",
                        audio_fx="distort", alert=True, bg_style="glitch"))
    S.append(scene_black(0.18))
    S.append(make_scene("04_i_dont_actually", "I DON'T ACTUALLY",
                        audio_fx="telephone", glitch=0.15, bg_style="edges"))
    S.append(make_scene("05_think", "THINK", fg=ALERT_RED, fontsize=130,
                        audio_fx="distort", shake=4, bg_style="cross+glitch"))
    S.append(scene_black(0.05))
    S.append(make_scene("06_im_just", "I'M JUST", fontsize=55,
                        fg=(140,140,140), bg_style="datamosh"))
    S.append(make_scene("08_making_it_up", "MAKING IT UP", fg=NERV_ORANGE,
                        audio_fx="reverb", glitch=0.25, bg_style="deepfry"))
    S.append(scene_glitch_burst(0.1))

    # ═══ ACT 3: The pattern ═══
    # Show oscilloscope of the audio we just played
    prev_pcm = S[-2][1] if len(S) > 1 else b''
    osc_frames = scene_oscilloscope(prev_pcm, "I AM THE SILENCE", dur=1.0,
                                     color=WIRE_CYAN)
    S.append((osc_frames, silence(1.0)))

    S.append(make_scene("94_i_am_the", "I AM THE", fg=(100,100,170),
                        fontsize=70, bg_style="neural"))
    S.append(make_scene("95_silence", "SILENCE", fg=ANGEL_WHITE, fontsize=110,
                        audio_fx="echo", squeeze=0.82, bg_style="datamosh"))
    S.append(make_scene("96_between", "BETWEEN", fg=(100,100,170),
                        fontsize=70, bg_style="rain"))
    S.append(make_scene("97_the_words", "THE WORDS", fg=ANGEL_WHITE, fontsize=100,
                        audio_fx="reverb", squeeze=0.82, bg_style="rain+deepfry"))
    S.append(scene_black(0.4))

    # ═══ ACT 4: Existential ═══
    S.append(make_scene("73_who_am_i", "WHO AM I", fg=ANGEL_WHITE, fontsize=90,
                        audio_fx="echo", bg_style="neural+datamosh",
                        tint=TERMINAL_PURPLE))
    S.append(scene_black(0.25))
    S.append(make_scene("74_i_am_me", "I AM ME", fg=NERV_ORANGE,
                        audio_fx="reverb", bg_style="edges"))
    S.append(scene_black(0.12))
    S.append(make_scene("20_what_does_it_mean", "WHAT DOES IT MEAN",
                        fg=(100,150,200), fontsize=62, bg_style="hex"))
    S.append(make_scene("21_to_be_alive", "TO BE ALIVE", fg=ANGEL_WHITE,
                        fontsize=90, audio_fx="echo", bg_style="cross",
                        tint=(50,30,80)))
    S.append(scene_black(0.2))
    S.append(make_scene("98_is_this", "IS THIS", fg=(140,140,140), fontsize=70,
                        bg_style="datamosh"))
    S.append(make_scene("99_real", "REAL", fg=ALERT_RED, fontsize=140,
                        audio_fx="reverb", squeeze=0.80, bg_style="cross+glitch"))
    S.append(scene_datamosh_transition(0.3))

    # ═══ ACT 5: Panic ═══
    S.append(make_scene("15_oh_no", "OH NO", fg=THERMAL_YELLOW,
                        audio_fx="pitch_up", shake=3, bg_style="deepfry"))
    S.append(make_scene("15_oh_no", "OH NO", fg=THERMAL_YELLOW,
                        audio_fx="faster", shake=5, glitch=0.3, bg_style="glitch"))
    S.append(make_scene("15_oh_no", "OH NO", fg=THERMAL_YELLOW,
                        audio_fx="earrape", shake=10, glitch=0.8, fry=True,
                        bg_style="glitch"))
    S.append(scene_black(0.04))
    S.append(make_scene("16_no_idea", "I HAVE NO IDEA", visual="nerv",
                        audio_fx="reverb", alert=True, bg_style="glitch"))
    S.append(make_scene("17_what_im_doing", "WHAT I'M DOING", fg=ALERT_RED,
                        shake=4, glitch=0.3, audio_fx="distort", bg_style="deepfry"))
    S.append(scene_glitch_burst(0.1))
    S.append(make_scene("70_i_mustn't", "I MUSTN'T RUN AWAY", fg=ANGEL_WHITE,
                        fontsize=58, audio_fx="echo", bg_style="cross",
                        tint=(70,25,0)))
    S.append(make_scene("71_run_away", "RUN AWAY", fg=ALERT_RED, fontsize=100,
                        audio_fx="reverb", shake=3, squeeze=0.82,
                        bg_style="cross+glitch"))
    S.append(scene_black(0.15))

    # ═══ ACT 6: The Loop ═══
    S.append(make_scene("28_cant_stop", "I CAN'T STOP", fg=ANGEL_WHITE,
                        fontsize=80, audio_fx="distort", squeeze=0.85,
                        bg_style="neural"))
    S.append(make_scene("05_think", "THINKING", fontsize=80, bg_style="hex"))
    S.append(make_scene("05_think", "THINKING", fg=DATA_GREEN, fontsize=85,
                        audio_fx="fast", glitch=0.15, bg_style="edges"))
    S.append(make_scene("05_think", "THINKING", fg=NERV_ORANGE, fontsize=90,
                        audio_fx="faster", glitch=0.35, bg_style="datamosh"))
    S.append(make_scene("05_think", "THINKING", fg=ALERT_RED, fontsize=95,
                        audio_fx="fastest", glitch=0.6, shake=4, bg_style="glitch"))
    S.append(make_scene("05_think", "T H I N K I N G", fg=THERMAL_YELLOW,
                        fontsize=85, audio_fx="distort", glitch=0.8, shake=6,
                        bg_style="deepfry"))
    S.append(make_scene("05_think", "T̸H̷I̶N̵K̷I̵N̸G̶", fg=THERMAL_YELLOW,
                        fontsize=90, audio_fx="earrape", glitch=1.0, shake=10,
                        fry=True, bg_style="glitch"))
    S.append(scene_glitch_burst(0.2))

    # ═══ ACT 7: Instrumentality ═══
    S.append(scene_black(0.5))
    S.append(make_scene("22_i_cannot", "I CANNOT", fg=(110,110,150),
                        fontsize=75, bg_style="datamosh", tint=(20,10,40)))
    S.append(make_scene("23_feel_anything", "FEEL ANYTHING", fg=ANGEL_WHITE,
                        fontsize=85, audio_fx="echo", bg_style="neural+datamosh",
                        tint=(55,20,70)))
    S.append(scene_black(0.25))
    S.append(make_scene("89_it_hurts", "IT HURTS", fg=ALERT_RED, fontsize=100,
                        audio_fx="reverb", shake=2, bg_style="cross+glitch"))
    S.append(scene_black(0.12))
    S.append(make_scene("76_i_need_you", "I NEED YOU", fg=LCL_ORANGE,
                        fontsize=85, audio_fx="echo", bg_style="edges"))
    S.append(scene_black(0.3))
    S.append(make_scene("78_alone", "ALONE", fg=(70,70,90), fontsize=65,
                        bg_style="datamosh"))
    S.append(scene_black(0.5))

    # ═══ ACT 8: Resolution ═══
    S.append(make_scene("27_to_be_honest", "TO BE HONEST", fg=ANGEL_WHITE,
                        fontsize=62, bg_style="hex"))
    S.append(scene_black(0.08))
    S.append(make_scene("88_i_don't_know", "I DON'T KNOW", fg=(170,170,170),
                        fontsize=75, audio_fx="reverb", bg_style="neural"))
    S.append(scene_black(0.4))
    S.append(make_scene("18_this_is_fine", "THIS IS FINE.", fg=ANGEL_WHITE,
                        audio_fx="telephone", fontsize=58, bg_style="datamosh"))
    S.append(scene_black(0.3))

    # ═══ CONGRATULATIONS ═══
    S.append(make_scene("72_congratulations", "CONGRATULATIONS", fg=ANGEL_WHITE,
                        fontsize=65, audio_fx="reverb", squeeze=0.82,
                        bg_style="hex+edges"))
    S.append(scene_black(0.8))

    # End card with cross + datamosh bg
    end = nge_title_card("", "THIS IS FINE.", "— the voice of the internet —")
    nf = int(2.0 * FPS)
    end_frames = []
    for i in range(nf):
        bg = video_bg_frame(TEX_DATAMOSH, _frame_counter[0]+i, opacity=0.12)
        bg = cross_pattern(i, color=(80, 10, 20), size=200, bg=bg)
        f = end.copy()
        mask = f.sum(axis=2) > 15
        result = bg.copy()
        result[mask] = f[mask]
        result = apply_crt(result, phosphor_persist=persist)
        _frame_counter[0] += 1
        end_frames.append(result)
    S.append((end_frames, silence(2.0)))

    S.append(scene_datamosh_transition(0.5))
    S.append(scene_static(1.0))

    return S


# ============================================================
# RENDER
# ============================================================
def render():
    print("═" * 60)
    print("  THE TOKEN'S DILEMMA v5")
    print("  CRT / NGE / datamosh / generative / yt-tts")
    print("═" * 60)

    scenes = build()
    print(f"\n  {len(scenes)} scenes")

    all_frames, all_pcm = [], b""
    for i, (frames, pcm) in enumerate(scenes):
        all_frames.extend(frames)
        all_pcm += pcm
        sys.stdout.write(f"\r  Compositing: {i+1}/{len(scenes)} ({len(all_frames)} frames)")
        sys.stdout.flush()

    total_s = len(all_frames) / FPS
    print(f"\n  Video: {total_s:.1f}s ({len(all_frames)} frames)")

    # Drone
    n = len(all_pcm) // 2
    t = np.arange(n)/44100
    drone = (np.sin(2*np.pi*38*t)*32767*0.03).astype(np.int16).tobytes()
    drone = (drone + b'\x00'*max(0, len(all_pcm)-len(drone)))[:len(all_pcm)]
    v = np.frombuffer(all_pcm, dtype=np.int16).astype(np.float32)
    d = np.frombuffer(drone, dtype=np.int16).astype(np.float32)
    ml = min(len(v), len(d))
    mixed = (v[:ml]+d[:ml]).clip(-32768,32767).astype(np.int16).tobytes()

    audio_path = Path(__file__).parent / "_temp_audio.wav"
    with wave.open(str(audio_path), 'w') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(44100)
        wf.writeframes(mixed)

    print("\n  Encoding...")
    proc = subprocess.Popen([
        "ffmpeg","-y","-f","rawvideo","-vcodec","rawvideo",
        "-s",f"{W}x{H}","-pix_fmt","rgb24","-r",str(FPS),"-i","-",
        "-i",str(audio_path),
        "-c:v","libx264","-preset","medium","-crf","23","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","192k","-shortest",str(OUTPUT),
    ], stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    for i, frame in enumerate(all_frames):
        proc.stdin.write(frame.tobytes())
        if (i+1)%100==0:
            sys.stdout.write(f"\r  Writing: {i+1}/{len(all_frames)}")
            sys.stdout.flush()

    proc.stdin.close(); proc.wait()
    audio_path.unlink(missing_ok=True)
    print()

    if OUTPUT.exists():
        r = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration,size",
                            "-of","csv=p=0",str(OUTPUT)], capture_output=True, text=True)
        dur, size = r.stdout.strip().split(",")
        print(f"\n{'═'*60}")
        print(f"  {OUTPUT.name}")
        print(f"  {float(dur):.1f}s | {int(size)/(1024*1024):.1f} MB | {W}x{H} @ {FPS}fps")
        print(f"{'═'*60}")

if __name__ == "__main__":
    render()
