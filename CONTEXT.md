# yt-vision-pro — Context

Workspace for the yt-vision-pro tool. The engine is in the `yt_vision_pro` package, exposed as the `yt-vision-pro` CLI and `python -m yt_vision_pro` module.

## Structure

```
yt-vision-pro/
├── pyproject.toml          # Build config, deps, entry points
├── README.md               # Usage and pipeline docs
├── CONTEXT.md              # You are here
├── skills/                 # Claude skill files for deep-research and cache-cleanup
├── src/yt_vision_pro/
│   ├── cli.py              # Typer CLI — yt-vision-pro pipeline entry
│   ├── fetch.py            # yt-dlp download, chapter parsing, synthetic chapters
│   ├── extract.py          # Detector-selectable scene planning + ffmpeg frame extraction
│   ├── align.py            # VTT caption parsing + alignment window
│   ├── ocr.py              # RapidOCR text extraction + text-length metadata
│   ├── filters.py          # Black frame / blur detection + slide-aware pHash dedup
│   ├── manifest.py         # Chunked Markdown manifest generation with density metadata
│   ├── whisper.py          # Optional faster-whisper fallback (guarded import)
│   ├── stages.py           # Pipeline stage sentinels + density resolution helpers
│   ├── transcript_cues.py  # Transcript-guided visual cue detection for light mode
│   └── db.py               # SQLite metadata store (videos, chapters, frames)
└── tests/                  # pytest suite (135 tests)
```

## Key Design

- **Chapter-first**: Videos with chapters get per-chapter manifests. Unchaptered videos get synthetic 15-min chapters.
- **Density-aware extraction**: Per-chapter density controls let lecture-heavy sections sample more aggressively than low-information sections.
- **OCR before dedup**: OCR runs ahead of dedup so slide-like frames can survive when the on-screen content changes subtly.
- **Stage sentinels**: Each pipeline stage writes a `.stages/<name>.done` file. Re-runs skip completed stages. `--force` clears all.
- **Chunked manifests**: Frames are grouped into chunks of 12 with per-chunk analysis slots for LLM processing.
- **Whisper fallback**: When no YouTube captions exist, optionally transcribes with faster-whisper.

## Sibling

The legacy v1 tool now lives at `../_archived/yt-vision-v1/`. The active tool is yt-vision-pro in this folder.
