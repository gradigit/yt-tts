"""Generative visuals and video texture loading for YTP.

Provides: video background loading, oscilloscope waveforms,
neural net visualizations, geometric patterns, and compositing.
"""

import numpy as np
import cv2
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import glob
import random

W, H = 1080, 1080
PROC_DIR = Path(__file__).parent / "processed"


# ============================================================
# VIDEO TEXTURE CACHE
# ============================================================

_texture_cache = {}


def load_texture(name_pattern, target_frames=150):
    """Load a processed video as a list of numpy frames.
    Caches results. name_pattern matches against processed/*.mp4"""
    if name_pattern in _texture_cache:
        return _texture_cache[name_pattern]

    matches = sorted(glob.glob(str(PROC_DIR / name_pattern)))
    if not matches:
        return None

    path = random.choice(matches)
    cap = cv2.VideoCapture(path)
    frames = []
    while len(frames) < target_frames:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret:
                break
        # Convert BGR to RGB and resize to 1080x1080
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if frame.shape[:2] != (H, W):
            frame = cv2.resize(frame, (W, H))
        frames.append(frame)
    cap.release()

    if frames:
        _texture_cache[name_pattern] = frames
    return frames if frames else None


def get_random_texture(style="datamosh"):
    """Get frames from a random processed video matching the style."""
    patterns = {
        "datamosh": "*_datamosh.mp4",
        "deepfry": "*_deepfry.mp4",
        "edges": "*_edges.mp4",
        "glitch": "*_glitch.mp4",
    }
    return load_texture(patterns.get(style, "*_datamosh.mp4"))


def video_bg_frame(frames, index, opacity=0.4, tint=None):
    """Get a darkened video frame for use as background."""
    if frames is None or not frames:
        return np.zeros((H, W, 3), dtype=np.uint8)

    f = frames[index % len(frames)].copy()
    # Darken for background use
    f = (f.astype(np.float32) * opacity).astype(np.uint8)

    if tint:
        t = np.array(tint, dtype=np.float32)
        f = (f.astype(np.float32) * 0.7 + t * 0.3 * opacity).clip(0, 255).astype(np.uint8)

    return f


# ============================================================
# GENERATIVE VISUALS
# ============================================================

def oscilloscope(audio_pcm, frame_idx, total_frames, color=(80, 255, 80),
                 bg=None):
    """Draw an oscilloscope waveform from audio data."""
    if bg is None:
        frame = np.zeros((H, W, 3), dtype=np.uint8)
    else:
        frame = bg.copy()

    if not audio_pcm or len(audio_pcm) < 4:
        return frame

    samples = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32)
    n_samples = len(samples)

    # Window of samples for this frame
    samples_per_frame = n_samples // max(total_frames, 1)
    start = frame_idx * samples_per_frame
    end = min(start + samples_per_frame * 2, n_samples)
    chunk = samples[start:end]

    if len(chunk) < 10:
        return frame

    # Normalize
    chunk = chunk / max(abs(chunk).max(), 1) * (H * 0.35)

    # Draw waveform
    points = []
    for i in range(0, len(chunk), max(1, len(chunk) // W)):
        x = int(i / len(chunk) * W)
        y = int(H // 2 + chunk[min(i, len(chunk)-1)])
        y = max(0, min(H - 1, y))
        points.append((x, y))

    if len(points) > 1:
        pts = np.array(points, dtype=np.int32)
        # Draw glow (thick, dim)
        cv2.polylines(frame, [pts], False, tuple(c // 3 for c in color), 6)
        # Draw main line
        cv2.polylines(frame, [pts], False, color, 2)

    return frame


def neural_net_pattern(frame_idx, nodes=30, connections=60,
                       color=(32, 240, 255), bg=None):
    """Animated neural network-like node graph."""
    if bg is None:
        frame = np.zeros((H, W, 3), dtype=np.uint8)
    else:
        frame = bg.copy()

    rng = np.random.RandomState(42)  # deterministic layout
    # Generate node positions (fixed layout, slight animation)
    positions = []
    for i in range(nodes):
        x = int(rng.uniform(50, W - 50))
        y = int(rng.uniform(50, H - 50))
        # Subtle breathing animation
        dx = int(8 * np.sin(frame_idx * 0.05 + i * 0.3))
        dy = int(6 * np.cos(frame_idx * 0.04 + i * 0.5))
        positions.append((x + dx, y + dy))

    # Draw connections (random pairs)
    rng2 = np.random.RandomState(123)
    for _ in range(connections):
        a, b = rng2.randint(0, nodes, 2)
        if a != b:
            p1, p2 = positions[a], positions[b]
            # Pulse alpha based on frame
            alpha = 0.3 + 0.2 * np.sin(frame_idx * 0.08 + a)
            c = tuple(int(v * alpha) for v in color)
            cv2.line(frame, p1, p2, c, 1, cv2.LINE_AA)

    # Draw nodes
    for i, (x, y) in enumerate(positions):
        # Pulse size
        r = int(4 + 2 * np.sin(frame_idx * 0.1 + i))
        cv2.circle(frame, (x, y), r + 2, tuple(c // 4 for c in color), -1)  # glow
        cv2.circle(frame, (x, y), r, color, -1)

    return frame


def hex_grid(frame_idx, color=(255, 152, 48), bg=None, rotate=0):
    """NERV-style hexagonal grid pattern."""
    if bg is None:
        frame = np.zeros((H, W, 3), dtype=np.uint8)
    else:
        frame = bg.copy()

    hex_size = 40
    dx = hex_size * 1.5
    dy = hex_size * np.sqrt(3)

    # Animation: slow drift
    ox = int(frame_idx * 0.3) % int(dx)
    oy = int(frame_idx * 0.2) % int(dy)

    alpha = 0.15 + 0.05 * np.sin(frame_idx * 0.05)
    c = tuple(int(v * alpha) for v in color)

    for row in range(-1, int(H / dy) + 2):
        for col in range(-1, int(W / dx) + 2):
            cx = int(col * dx + (row % 2) * dx / 2 - ox)
            cy = int(row * dy - oy)

            pts = []
            for angle_idx in range(6):
                a = np.radians(60 * angle_idx + 30 + rotate)
                px = int(cx + hex_size * np.cos(a))
                py = int(cy + hex_size * np.sin(a))
                pts.append((px, py))

            pts_arr = np.array(pts, dtype=np.int32)
            cv2.polylines(frame, [pts_arr], True, c, 1, cv2.LINE_AA)

    return frame


def cross_pattern(frame_idx, color=(200, 16, 46), size=200, bg=None):
    """Evangelion cross motif."""
    if bg is None:
        frame = np.zeros((H, W, 3), dtype=np.uint8)
    else:
        frame = bg.copy()

    # Pulsing glow
    pulse = 0.6 + 0.3 * np.sin(frame_idx * 0.08)
    c = tuple(int(v * pulse) for v in color)

    cx, cy = W // 2, H // 2
    thickness = max(3, size // 15)

    # Vertical bar
    cv2.rectangle(frame,
                  (cx - thickness, cy - size),
                  (cx + thickness, cy + size), c, -1)
    # Horizontal bar (shorter)
    hsize = int(size * 0.6)
    cv2.rectangle(frame,
                  (cx - hsize, cy - size // 4 - thickness),
                  (cx + hsize, cy - size // 4 + thickness), c, -1)

    # Bloom glow around the cross
    mask = np.zeros((H, W), dtype=np.float32)
    mask[max(0,cy-size):min(H,cy+size), max(0,cx-thickness*3):min(W,cx+thickness*3)] = pulse * 0.3
    mask[max(0,cy-size//4-thickness*3):min(H,cy-size//4+thickness*3), max(0,cx-hsize):min(W,cx+hsize)] = pulse * 0.3
    mask = cv2.GaussianBlur(mask, (0, 0), 20)
    for ch in range(3):
        frame[:, :, ch] = np.minimum(255,
            frame[:, :, ch].astype(np.float32) + mask * color[ch]).astype(np.uint8)

    return frame


def data_rain(frame_idx, color=(0, 200, 60), density=40, bg=None):
    """Matrix-style falling data streams."""
    if bg is None:
        frame = np.zeros((H, W, 3), dtype=np.uint8)
    else:
        frame = bg.copy()

    rng = np.random.RandomState(frame_idx // 3)  # update every 3 frames
    font = cv2.FONT_HERSHEY_SIMPLEX

    chars = "01アイウエオカキクケコ∞∑∂∫πφψωΔΩ"

    for i in range(density):
        x = (i * 27 + 13) % W
        speed = 3 + (i * 7) % 8
        y_base = (frame_idx * speed + i * 43) % (H + 200) - 100

        for j in range(8):
            y = y_base + j * 22
            if 0 <= y < H:
                ch = chars[rng.randint(len(chars))]
                alpha = max(0.1, 1.0 - j * 0.12)
                c = tuple(int(v * alpha) for v in color)
                cv2.putText(frame, ch, (x, y), font, 0.45, c, 1, cv2.LINE_AA)

    return frame


def composite(bg, fg, fg_alpha=1.0):
    """Composite fg over bg with alpha."""
    if fg_alpha >= 1.0:
        mask = fg.sum(axis=2) > 10
        result = bg.copy()
        result[mask] = fg[mask]
        return result
    return (bg.astype(np.float32) * (1 - fg_alpha) +
            fg.astype(np.float32) * fg_alpha).clip(0, 255).astype(np.uint8)


def blend_add(bg, fg, strength=0.5):
    """Additive blend of fg onto bg."""
    return (bg.astype(np.float32) + fg.astype(np.float32) * strength).clip(0, 255).astype(np.uint8)


def blend_screen(bg, fg, strength=0.5):
    """Screen blend mode."""
    a = bg.astype(np.float32) / 255
    b = fg.astype(np.float32) / 255
    result = 1 - (1 - a) * (1 - b * strength)
    return (result * 255).clip(0, 255).astype(np.uint8)
