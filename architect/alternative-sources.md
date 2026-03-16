# Alternative Data Sources — Reference for Future Expansion

Saved from research conducted 2026-03-16. To be revisited when expanding beyond YouTube-Commons.

## Datasets (verified, with word timestamps)

### People's Speech
- **Size**: 30K+ hours, needs verification on download size
- **License**: CC-BY (clean subset), CC-BY-SA (full)
- **Sources**: Internet Archive — includes Twitch, local news, documentaries
- **Timestamps**: Word-level (forced alignment)
- **HuggingFace**: `MLCommons/peoples_speech`
- **Status**: Awaiting size verification

### YODAS / YODAS2
- **Size**: 500K+ hours across 100+ languages
- **License**: CC (YouTube source)
- **Timestamps**: Segment-level only — needs WhisperX for word alignment
- **HuggingFace**: `espnet/yodas2`
- **Status**: Awaiting size verification. Massive processing needed.

### LibriSpeech + MFA Alignments
- **Size**: 960 hours (clean read audiobooks)
- **License**: CC-BY-4.0
- **Timestamps**: Word-level (MFA alignments on Zenodo)
- **Downside**: Read-aloud speech, not conversational/internet-native

### VoxPopuli
- **Size**: 1,800h transcribed, 400K hours unlabeled
- **License**: CC0
- **Timestamps**: Word-level (human annotated)
- **Downside**: Formal parliamentary speech, not internet-native

### Common Voice (Mozilla)
- **Size**: 20K+ hours
- **License**: CC0
- **Timestamps**: None (third-party alignment exists for English subset)

## Social Media (ToS concerns — not recommended for V1)

### TikTok
- Research API (academic only, US/EU university researchers)
- `voice_to_text` and `subtitles` fields available
- Third-party scraping violates ToS

### Twitch
- No native transcript API
- yt-dlp + Whisper on VODs
- TwitchTranscripts.com has VTT for top channels

### Twitter/X
- No native captions since late 2022
- Third-party ASR required

## Movie/TV (inspiration, not data source)

### PlayPhrase.me
- 10M+ phrases from movie/TV dialogue (6 languages)
- No public API, no redistribution
- Fair use defense (self-assessed)

### Yarn / GetYarn.io
- Movie/TV quote search
- No API, redistribution prohibited

### OpenSubtitles
- REST API (10 free downloads/day)
- SRT format (line-level, not word-level)

## YouTube Crawling

### Channel RSS Feeds
- `https://www.youtube.com/feeds/videos.xml?channel_id=X`
- 15 most recent videos per channel, no auth needed
- Requires browser User-Agent
- Intermittently returning 404/500 (known issue since Dec 2025)
- Fields: video_id, title, published date, views, description

### Discovery Methods
- yt-dlp `--flat-playlist` for channel backfill
- `feed/hashtag/TERM` for topic discovery
- `feed/trending?bp=...` for category trending (general trending may redirect)

### Cost Estimates (1M videos/month)
- Residential proxies needed (datacenter IPs are blocked)
- Bright Data: $240-600/month at 60-150 GB bandwidth
- SOAX: $90/month for 25 GB included
- youtube-transcript-api v1.1.0+ uses InnerTube (lower bandwidth)

### Manual vs Auto Captions
- yt-dlp `kind=asr` field distinguishes manual from auto-generated
- `info['subtitles']` = manual; `info['automatic_captions']` = auto
- `--write-subs --write-auto-subs` prefers manual, falls back to auto

## Podcast Pipeline
- RSS → MP3 download → Whisper ASR → forced alignment → FTS5 index
- ~2-7 min per hour on GPU, ~20-40 min on CPU
- PodcastIndex API: 3.2M episodes with creator transcripts (minority)
- Apple Podcasts: 125M+ auto-transcripts, locked behind account tokens
- Third-party: Taddy (200M+ episodes claimed), PodSqueeze (unverified)

## Prior Art Tools

### Filmot
- 1.53B YouTube transcripts indexed by solo developer
- $510/month server costs
- Search-only, no clip extraction API

### kelciour/playphrase (199 stars)
- Closest OSS equivalent to yt-tts concept
- SRT grep + ffmpeg clip extraction + mpv playback

### videogrep (3,453 stars)
- Canonical supercut tool (SRT regex → moviepy concatenation)

### sentence-mixing (8 stars) + CLI (14 stars)
- Phoneme-level YouTube Poop generation
- MFA v1 (incompatible with current v3.x), yt-dlp 2022 pinned
- 3-step scoring: phoneme quality, target match, spectral continuity

### ytpai (22 stars)
- WhisperX-based web app for word-level sentence mixing
