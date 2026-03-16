# Research Findings Summary

## 1. ASR Backend Strategy (MLX + Parakeet + Whisper)

### Recommended Architecture: Three-Tier Backend

| Platform | Backend | Speed (10s clip) | Word Timestamps |
|----------|---------|-------------------|-----------------|
| NVIDIA GPU | faster-whisper tiny (CUDA) | ~1-2s | Yes (cross-attention) |
| Apple Silicon | parakeet-mlx (TDT 0.6b) | ~0.5s | Yes (native TDT duration) |
| Apple Silicon | mlx-whisper tiny | ~0.4s | Yes (cross-attention) |
| CPU fallback | faster-whisper tiny (int8) | ~3-5s | Yes |
| Lightweight NVIDIA | onnx-asr + parakeet (int8) | ~1s | Token-level (≈word for English) |

### Key Decisions
- **Don't add nemo_toolkit as a dependency** — 7GB env, PyTorch required. Use onnx-asr instead (122KB wheel + 652MB int8 model)
- **MLX on Mac**: `pip install mlx-whisper` OR `pip install parakeet-mlx` — both give word timestamps
- **parakeet-mlx is 2x faster than mlx-whisper** on M4 Pro (0.5s vs 1.0s per clip)
- **Detection**: `try: import mlx.core; mlx.core.metal.is_available()` for MLX, ctranslate2 for CUDA

### Models
- `mlx-community/whisper-tiny.en-mlx` — fastest Whisper on Mac
- `mlx-community/parakeet-tdt-0.6b-v3` — fastest overall on Mac, English word timestamps native
- `faster-whisper` tiny/base — CUDA + CPU, word timestamps via cross-attention

## 2. Alternative Data Sources (Beyond YouTube)

### Tier 1: Ready to Use (have word timestamps + permissive license)
| Source | Size | License | Timestamps |
|--------|------|---------|------------|
| People's Speech | 30K hours | CC-BY / CC-BY-SA | Word-level (forced alignment) |
| LibriSpeech + MFA | 960 hours | CC-BY-4.0 | Word-level (Zenodo alignments) |
| VoxPopuli | 1,800h transcribed | CC0 | Word-level (human annotated) |

### Tier 2: Large Scale, Needs Processing
| Source | Size | License | Notes |
|--------|------|---------|-------|
| YODAS | 500K hours | CC (YouTube) | Segment-level only, needs WhisperX for word alignment |
| YouTube-Commons | 22.7M transcripts | CC-BY-4.0 | Text only, no audio, no timestamps |
| Common Voice | 20K+ hours | CC0 | No word timestamps (third-party alignment exists) |

### Tier 3: Social Media (ToS concerns)
- TikTok: Research API (academic only), rich captions
- Twitch: yt-dlp + Whisper on VODs
- Podcasts: RSS feeds + Whisper, no bulk dataset available anymore

### Tier 4: Movie/TV (inspiration only, can't use as data)
- PlayPhrase.me: 10M+ phrases, no API, fair use defense
- Yarn.co/GetYarn: Quote search, no API, ToS prohibits redistribution
- OpenSubtitles: API exists (10 downloads/day free), line-level SRT only

## 3. Parakeet vs Whisper (Benchmark Summary)

### For our use case (10-30s clips, known text, need word timestamps):

| Factor | Whisper tiny | Parakeet TDT 0.6b |
|--------|-------------|-------------------|
| WER | ~8% | ~1.7% |
| Params | 39M | 600M |
| Word timestamps | Cross-attention (okay) | Native TDT duration (better) |
| Single-clip GPU latency | ~1s | ~2s (more params) |
| Batch GPU throughput | Lower | Much higher (RTFx 3380 at batch=128) |
| Install weight | 200MB (faster-whisper) | 7GB (NeMo) or 652MB (onnx-asr int8) |
| CPU speed | Fast (39M params) | Slow (600M params) |

**Verdict**: For single-clip alignment on GPU, **Whisper tiny is faster** due to fewer params. Parakeet's accuracy edge matters less since we already know the text. For batch processing at scale, Parakeet wins on throughput. For Mac, parakeet-mlx is fastest.

## 4. Pipeline Optimization Ideas

### Timestamp Accuracy
- **Forced alignment** (wav2vec2, MFA) gives tightest word boundaries — better than Whisper cross-attention
- **WhisperX** = Whisper + wav2vec2 forced alignment (best of both, but needs PyTorch)
- **CTC forced alignment via torchaudio** — can align known text to audio without full ASR
- **Programmatic refinement**: snap-to-silence, snap-to-zero-crossing at word boundaries

### Tightness Control
- tight=30ms, normal=100ms, loose=250ms padding around word boundaries
- snap-to-silence: extend cut point to nearest silence (VAD-based)
- snap-to-zero-crossing: avoid audio clicks at cut points

### Scale Processing
- Batch inference: process multiple clips simultaneously (faster-whisper supports this)
- Whisper model loading: ~1s overhead per process — keep warm via daemon/batch mode
- Parallel chunk resolution: already using ThreadPoolExecutor(3 workers)
