"""Caption parsing and alignment for yt-vision-pro."""
from pathlib import Path

import webvtt


def parse_captions(vtt_path: Path) -> list[dict]:
    captions = []
    for caption in webvtt.read(str(vtt_path)):
        start = _timestamp_to_seconds(caption.start)
        end = _timestamp_to_seconds(caption.end)
        text = caption.text.strip()
        if text:
            captions.append({"start": start, "end": end, "text": text})
    return captions


def align_captions(captions: list[dict], timestamp: float, window: float = 3.0) -> list[str]:
    """Return caption texts whose time range overlaps [timestamp-window, timestamp+window]."""
    t_start = timestamp - window
    t_end = timestamp + window
    return [
        c["text"] for c in captions
        if c["end"] >= t_start and c["start"] <= t_end
    ]


def detect_caption_source(vtt_path: Path | None) -> str:
    """Return 'youtube', 'whisper', or 'none' based on the VTT file path."""
    if vtt_path is None:
        return "none"
    name = vtt_path.name.lower()
    if "whisper" in name:
        return "whisper"
    return "youtube"


def _timestamp_to_seconds(ts: str) -> float:
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)
