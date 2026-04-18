# yt-vision-pro

YouTube visual analysis pipeline — chapter-aware frame extraction, OCR-first slide preservation, quality filtering, and LLM-ready manifest synthesis.

The engine still lives in the `yt_vision_v2` package during migration, but the primary tool name is now `yt-vision-pro`. The legacy `ytv2` console alias is still available.

## What it does

1. Downloads a YouTube video + captions via yt-dlp
2. Parses chapters (or generates synthetic 15-min chunks for unchaptered videos)
3. Detects scene boundaries with `ContentDetector` or `AdaptiveDetector`
4. Extracts scene-start frames plus optional within-scene samples
5. Runs OCR on each frame before deduplication
6. Filters black/blurry frames and deduplicates with slide-aware pHash thresholds
7. Aligns captions to frames (YouTube VTT or whisper fallback)
8. Generates chunked Markdown manifests with density metadata for LLM synthesis

## Example Images:

<img width="1204" height="1307" alt="image" src="https://github.com/user-attachments/assets/1f0167a6-4ca0-40dd-80df-32ad8fc7105e" />

<img width="1117" height="1219" alt="image" src="https://github.com/user-attachments/assets/c31f5e59-b120-49af-b56a-2d9b9030608f" />

## Prerequisites

- Python 3.10+
- ffmpeg on PATH (`winget install ffmpeg` on Windows)

## Install

```bash
pip install -e ".[dev]"

# Optional: whisper fallback for videos without captions
pip install -e ".[whisper]"
```

## Usage

```bash
# Basic — process a YouTube video
yt-vision-pro <youtube-url>

# Custom cache directory
yt-vision-pro <youtube-url> --cache-dir ./my-cache

# Skip OCR (faster)
yt-vision-pro <youtube-url> --no-ocr

# Skip quality filters
yt-vision-pro <youtube-url> --no-filter

# Use the adaptive detector instead of content-based detection
yt-vision-pro <youtube-url> --detector adaptive

# Sample the first hour densely for lecture-heavy videos
yt-vision-pro <youtube-url> --dense-until 01:00:00

# Force specific chapters to high density
yt-vision-pro <youtube-url> --dense-chapters 0,1,2

# Re-run from scratch
yt-vision-pro <youtube-url> --force

# Resume from a specific stage (fetch, extract, ocr, dedup-with-ocr-context, align, manifest)
yt-vision-pro <youtube-url> --from-stage dedup-with-ocr-context

# Legacy alias still works
ytv2 <youtube-url>
```

## Density model

- `high`: 3s within-scene sampling, loose near-duplicate removal, strongest slide preservation
- `normal`: 5s within-scene sampling, balanced deduplication
- `low`: 15s within-scene sampling, aggressive deduplication for conversational videos

Use `--density` to set the default tier, `--dense-chapters` to promote specific chapter indices, and `--dense-until` to promote everything before a time cutoff.

## Pipeline stages

| Stage    | Description                                          | Sentinel |
|----------|------------------------------------------------------|----------|
| fetch    | Download video, captions, info.json via yt-dlp       | `.stages/fetch.done` |
| extract  | Scene detection + raw frame extraction               | `.stages/extract.done` |
| ocr      | RapidOCR on each frame                               | `.stages/ocr.done` |
| dedup-with-ocr-context | Quality filtering + slide-aware dedup      | `.stages/dedup-with-ocr-context.done` |
| align    | Parse captions (YouTube VTT or whisper fallback)     | `.stages/align.done` |
| manifest | Generate chunked Markdown manifests                  | `.stages/manifest.done` |

Each stage writes a sentinel file. On re-run, completed stages are skipped. Use `--force` to clear all sentinels or `--from-stage <name>` to re-run from a specific point.

## Output

- **Single-chapter videos:** `cache/manifest.md`
- **Multi-chapter videos:** `cache/manifests/manifest-00-intro.md`, etc.

Feed the manifest(s) to an LLM (Copilot Chat, Claude Code) for synthesis into research notes.

## Tests

```bash
pytest tests/ -v
```
