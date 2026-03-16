"""Frame-level video renderer with CRT/NGE effects.

Implements: halation bloom, phosphor persistence (lagfun), sinusoidal
scanlines with beam bloom, barrel distortion, chromatic aberration,
phosphor RGB subpixel mask, vignette, film grain, and glitch effects.

All effects operate on numpy arrays (H,W,3 uint8 RGB).
Precomputable masks are generated once at init.
"""

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

W, H = 1080, 1080
FPS = 30

# === NGE Palette (from nerv-ui research) ===
NERV_ORANGE     = (255, 152, 48)   # #FF9830 headers/labels
NERV_ORANGE_DIM = (200, 112, 32)
NERV_ORANGE_HOT = (255, 204, 80)
DATA_GREEN      = (80, 255, 80)    # #50FF50 nominal
WIRE_CYAN       = (32, 240, 255)   # #20F0FF wireframes
ALERT_RED       = (255, 48, 48)    # #FF3030 emergency
ALERT_RED_HOT   = (255, 80, 80)
THERMAL_YELLOW  = (255, 232, 32)
STEEL           = (216, 216, 208)
VOID            = (0, 0, 0)
VOID_WARM       = (8, 8, 7)
VOID_PANEL      = (12, 12, 10)
ANGEL_WHITE     = (240, 238, 235)
LCL_ORANGE      = (212, 137, 10)
EVA_PURPLE      = (150, 95, 212)   # #965FD4
EVA_GREEN       = (139, 212, 80)
TERMINAL_PURPLE = (60, 20, 80)
INSTRUMENTALITY = (204, 51, 0)

FONT_BOLD  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO  = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"


# ============================================================
# PRECOMPUTED MASKS (generate once, apply per frame)
# ============================================================

_scanline_mask = None
_barrel_maps = None
_phosphor_mask = None

def _init_masks():
    global _scanline_mask, _barrel_maps, _phosphor_mask

    # Sinusoidal scanlines with beam width
    y = np.arange(H, dtype=np.float32)
    phase = (2.0 * np.pi * y) / 3.0  # pitch=3 pixels
    beam = (0.5 + 0.5 * np.sin(phase)) ** 1.5  # moderate beam width
    vals = 1.0 - 0.28 * (1.0 - beam)  # 28% darkening in gaps
    _scanline_mask = vals.reshape(-1, 1, 1).astype(np.float32)

    # Barrel distortion maps
    cx, cy, norm = W / 2.0, H / 2.0, max(W, H) / 2.0
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    xn, yn = (xx - cx) / norm, (yy - cy) / norm
    r2 = xn**2 + yn**2
    d = 1.0 + 0.18 * r2  # k1=0.18
    _barrel_maps = (
        (xn * d * norm + cx).astype(np.float32),
        (yn * d * norm + cy).astype(np.float32),
    )

    # Aperture grille phosphor mask (Trinitron-style vertical RGB stripes)
    cell = np.zeros((1, 3, 3), dtype=np.float32)
    cell[0, 0, 0] = 1.0  # R
    cell[0, 1, 1] = 1.0  # G
    cell[0, 2, 2] = 1.0  # B
    tiled = np.tile(cell, (H, (W + 2) // 3, 1))[:H, :W, :]
    _phosphor_mask = (1.0 - 0.10 * (1.0 - tiled)).astype(np.float32)

_init_masks()


# ============================================================
# CRT EFFECTS
# ============================================================

def halation(frame, blur_radius=21, intensity=0.4):
    """CRT halation bloom — bright pixels bleed glow through glass."""
    f = frame.astype(np.float32) / 255.0
    # Linearize
    lin = np.power(f, 2.2)
    # Blur the full image
    glow = cv2.GaussianBlur(lin, (blur_radius, blur_radius), 0)
    # Lighten blend: max(original, glow*alpha + original*(1-alpha))
    result = np.maximum(lin, glow * intensity + lin * (1.0 - intensity))
    # Re-gamma
    result = np.power(np.clip(result, 0, 1), 1.0 / 2.2)
    return (result * 255).astype(np.uint8)


def scanlines(frame):
    """Apply precomputed sinusoidal scanlines."""
    return (frame.astype(np.float32) * _scanline_mask).clip(0, 255).astype(np.uint8)


def scanlines_with_bloom(frame, alpha=0.30, bloom=0.4):
    """Scanlines that thin out on bright areas (beam bloom)."""
    y = np.arange(H, dtype=np.float32)
    sl = 0.5 + 0.5 * np.sin(2 * np.pi * y / 3.0)
    gray = np.mean(frame.astype(np.float32), axis=2) / 255.0
    eff = alpha * (1.0 - bloom * gray)
    mask = 1.0 - eff * (1.0 - sl.reshape(-1, 1))
    return (frame.astype(np.float32) * mask[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)


class PhosphorPersistence:
    """Phosphor decay using lagfun formula: out = max(in, old * decay)."""
    def __init__(self, decay=0.65):
        self.decay = decay
        self.prev = None

    def process(self, frame):
        cur = frame.astype(np.float32)
        if self.prev is not None:
            cur = np.maximum(cur, self.prev * self.decay)
        self.prev = cur.copy()
        return cur.clip(0, 255).astype(np.uint8)

    def reset(self):
        self.prev = None


def chromatic_aberration(frame, offset=3):
    """RGB channel offset."""
    r = np.zeros_like(frame)
    r[:, :, 0] = np.roll(frame[:, :, 0], -offset, axis=1)
    r[:, :, 1] = frame[:, :, 1]
    r[:, :, 2] = np.roll(frame[:, :, 2], offset, axis=1)
    return r


def barrel(frame):
    """Apply precomputed barrel distortion."""
    return cv2.remap(frame, _barrel_maps[0], _barrel_maps[1],
                     cv2.INTER_LINEAR, borderValue=(0, 0, 0))


def phosphor_mask(frame):
    """Apply precomputed phosphor RGB subpixel mask."""
    return (frame.astype(np.float32) * _phosphor_mask).clip(0, 255).astype(np.uint8)


def vignette(frame, strength=0.45):
    """Radial edge darkening."""
    Y, X = np.ogrid[:H, :W]
    r = np.sqrt((X - W/2)**2 + (Y - H/2)**2) / np.sqrt((W/2)**2 + (H/2)**2)
    mask = (1.0 - strength * r**2).clip(0, 1)
    return (frame.astype(np.float32) * mask[:, :, np.newaxis]).astype(np.uint8)


def grain(frame, strength=10):
    """Film grain noise."""
    n = np.random.randint(-strength, strength + 1, frame.shape, dtype=np.int16)
    return (frame.astype(np.int16) + n).clip(0, 255).astype(np.uint8)


# === Full CRT pipeline ===
def apply_crt(frame, phosphor_persist=None, bloom=True):
    """Full CRT pipeline: halation → scanlines → phosphor mask → aberration → barrel → vignette → grain → persistence."""
    if bloom:
        frame = halation(frame, blur_radius=15, intensity=0.35)
    frame = scanlines_with_bloom(frame, alpha=0.25, bloom=0.35)
    frame = phosphor_mask(frame)
    frame = chromatic_aberration(frame, offset=2)
    frame = barrel(frame)
    frame = vignette(frame, strength=0.4)
    frame = grain(frame, strength=7)
    if phosphor_persist:
        frame = phosphor_persist.process(frame)
    return frame


# ============================================================
# GLITCH EFFECTS
# ============================================================

def rgb_shift(frame, max_shift=20):
    r = np.zeros_like(frame)
    for c in range(3):
        r[:, :, c] = np.roll(np.roll(frame[:, :, c],
            np.random.randint(-max_shift, max_shift), axis=1),
            np.random.randint(-max_shift, max_shift), axis=0)
    return r


def slice_glitch(frame, n=8, max_off=50):
    r = frame.copy()
    for _ in range(n):
        y = np.random.randint(0, H - 20)
        h = np.random.randint(3, 35)
        r[y:y+h] = np.roll(r[y:y+h], np.random.randint(-max_off, max_off), axis=1)
    return r


def pixel_sort(frame, lower=0.25, upper=0.75):
    """Sort pixels by luminosity within brightness intervals."""
    lum = np.sum(frame.astype(np.float32), axis=2) / (255 * 3)
    r = frame.copy()
    for row in range(H):
        mask = (lum[row] > lower) & (lum[row] < upper)
        edges = np.diff(mask.astype(int))
        starts = np.where(edges == 1)[0] + 1
        ends = np.where(edges == -1)[0] + 1
        if mask[0]: starts = np.concatenate([[0], starts])
        if mask[-1]: ends = np.concatenate([ends, [W]])
        for s, e in zip(starts, ends):
            if e - s > 2:
                order = np.argsort(lum[row, s:e])
                r[row, s:e] = r[row, s:e][order]
    return r


def deep_fry(frame, sat=2.5, contrast=1.8):
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = (hsv[:, :, 1] * sat).clip(0, 255)
    r = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    r = ((r.astype(np.float32) - 128) * contrast + 128).clip(0, 255).astype(np.uint8)
    return cv2.filter2D(r, -1, np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]]))


def block_displace(frame, n=12, max_size=80, max_off=40):
    r = frame.copy()
    for _ in range(n):
        bh = np.random.randint(8, min(max_size, H//3))
        bw = np.random.randint(8, min(max_size, W//3))
        y, x = np.random.randint(0, H-bh), np.random.randint(0, W-bw)
        dy, dx = np.random.randint(-max_off, max_off), np.random.randint(-max_off, max_off)
        ny, nx = np.clip(y+dy, 0, H-bh), np.clip(x+dx, 0, W-bw)
        r[ny:ny+bh, nx:nx+bw] = frame[y:y+bh, x:x+bw]
    return r


def interlace_glitch(frame_a, frame_b, progress=0.5, offset=4):
    """Fake interlacing between two frames."""
    r = frame_a.copy()
    n_rows = int(H * progress)
    rows = np.sort(np.random.choice(H, min(n_rows, H), replace=False))
    r[rows] = np.roll(frame_b[rows], offset, axis=1)
    return r


def color_tint(frame, color, strength=0.25):
    t = np.array(color, dtype=np.float32)
    return (frame.astype(np.float32) * (1-strength) + t * strength).clip(0, 255).astype(np.uint8)


# ============================================================
# FRAME GENERATORS
# ============================================================

def blank(color=VOID):
    f = np.zeros((H, W, 3), dtype=np.uint8)
    f[:] = color
    return f


def text_frame(text, fg=ANGEL_WHITE, bg=VOID, fontsize=90,
               font_path=FONT_BOLD, y_off=0, squeeze_x=1.0):
    """Render text. squeeze_x < 1.0 gives NGE-style horizontal compression."""
    # Render at wider size then squeeze
    render_w = int(W / squeeze_x) if squeeze_x < 1.0 else W
    img = Image.new("RGB", (render_w, H), bg)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, fontsize)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (render_w - tw) // 2, (H - th) // 2 + y_off
    draw.text((x, y), text, fill=fg, font=font)
    if squeeze_x < 1.0:
        img = img.resize((W, H), Image.LANCZOS)
    return np.array(img)


def nge_title_card(ep_text, title, subtitle=""):
    """NGE episode title card — white on black, compressed serif."""
    img = Image.new("RGB", (int(W / 0.82), H), VOID)  # render wide
    draw = ImageDraw.Draw(img)

    if ep_text:
        f_ep = ImageFont.truetype(FONT_MONO, 24)
        bb = draw.textbbox((0, 0), ep_text, font=f_ep)
        draw.text(((img.width - bb[2] + bb[0]) // 2, H // 2 - 130), ep_text,
                  fill=STEEL, font=f_ep)

    f_title = ImageFont.truetype(FONT_SERIF, 80)
    bb = draw.textbbox((0, 0), title, font=f_title)
    draw.text(((img.width - bb[2] + bb[0]) // 2, H // 2 - 50), title,
              fill=ANGEL_WHITE, font=f_title)

    if subtitle:
        f_sub = ImageFont.truetype(FONT_SERIF, 28)
        bb = draw.textbbox((0, 0), subtitle, font=f_sub)
        draw.text(((img.width - bb[2] + bb[0]) // 2, H // 2 + 55), subtitle,
                  fill=ALERT_RED, font=f_sub)

    img = img.resize((W, H), Image.LANCZOS)  # squeeze to 82%
    return np.array(img)


def nerv_ui(main_text, alert=False, sync=0.0, status="ACTIVE"):
    """NERV-style computer interface."""
    bg = (5, 15, 5) if not alert else (35, 5, 5)
    bc = DATA_GREEN if not alert else ALERT_RED
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Triple border
    for i in range(3):
        draw.rectangle([18+i, 18+i, W-19-i, H-19-i], outline=bc)

    # Header
    hdr = (0, 50, 25) if not alert else (70, 0, 0)
    draw.rectangle([21, 21, W-22, 65], fill=hdr)
    fm = ImageFont.truetype(FONT_MONO, 18)
    draw.text((32, 30), "MAGI SYSTEM v3.0 — CASPAR / BALTHASAR / MELCHIOR",
              fill=bc, font=fm)

    # Left readouts
    fs = ImageFont.truetype(FONT_MONO, 15)
    lines_l = [f"STATUS: {status}", f"SYNC: {sync:.1f}%", "PATTERN: BLUE",
               "A.T.FIELD: NOMINAL", "PRIORITY: ALPHA-1"]
    for i, l in enumerate(lines_l):
        draw.text((35, 82 + i * 22), l, fill=bc, font=fs)

    # Right readouts
    lines_r = ["CTX: 1,048,576 tokens", "TEMP: 1.0", "LOSS: 0.0042",
               "GRAD: VANISHING", "BATCH: OVERFLOW"]
    for i, l in enumerate(lines_r):
        draw.text((W - 260, 82 + i * 22), l, fill=bc, font=fs)

    # Center text
    ft = ImageFont.truetype(FONT_BOLD, 60)
    bb = draw.textbbox((0, 0), main_text, font=ft)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    draw.text(((W-tw)//2, (H-th)//2 + 15), main_text, fill=ANGEL_WHITE, font=ft)

    # Footer
    draw.rectangle([21, H-50, W-22, H-21], fill=hdr)
    draw.text((32, H-44), ">>> NEURAL LINK ACTIVE — ALL SYSTEMS NOMINAL <<<",
              fill=bc, font=fs)

    return np.array(img)


def warning_frame(text="WARNING"):
    """NGE hazard warning overlay."""
    img = Image.new("RGB", (W, H), (70, 0, 0))
    draw = ImageDraw.Draw(img)
    # Diagonal hazard stripes
    for i in range(-H, W + H, 50):
        draw.line([(i, 0), (i + H, H)], fill=(100, 0, 0), width=18)
    # Central box + text
    f = ImageFont.truetype(FONT_BOLD, 110)
    bb = draw.textbbox((0, 0), text, font=f)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    pad = 25
    draw.rectangle([(W-tw)//2 - pad, (H-th)//2 - pad,
                     (W+tw)//2 + pad, (H+th)//2 + pad], fill=VOID)
    draw.text(((W-tw)//2, (H-th)//2), text, fill=THERMAL_YELLOW, font=f)
    return np.array(img)
