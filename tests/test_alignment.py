"""Tests for caption alignment and whisper fallback."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from yt_vision_pro.align import align_captions, detect_caption_source


class TestAlignCaptions:
    def test_aligns_within_default_window(self):
        captions = [
            {"start": 4.0, "end": 6.0, "text": "Hello"},
            {"start": 10.0, "end": 12.0, "text": "World"},
            {"start": 20.0, "end": 22.0, "text": "Foo"},
        ]
        result = align_captions(captions, timestamp=5.0, window=3.0)
        assert "Hello" in result
        assert "World" not in result

    def test_aligns_with_tight_window(self):
        captions = [
            {"start": 4.0, "end": 6.0, "text": "Hello"},
            {"start": 5.5, "end": 7.0, "text": "Overlap"},
        ]
        result = align_captions(captions, timestamp=5.0, window=1.0)
        assert "Hello" in result
        assert "Overlap" in result

    def test_returns_empty_when_no_match(self):
        captions = [{"start": 100.0, "end": 102.0, "text": "Far away"}]
        result = align_captions(captions, timestamp=5.0, window=3.0)
        assert result == []

    def test_returns_empty_for_empty_captions(self):
        result = align_captions([], timestamp=5.0, window=3.0)
        assert result == []


class TestDetectCaptionSource:
    def test_youtube_vtt(self, tmp_path: Path):
        vtt = tmp_path / "source.en.vtt"
        vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello")
        assert detect_caption_source(vtt) == "youtube"

    def test_whisper_vtt(self, tmp_path: Path):
        vtt = tmp_path / "whisper.vtt"
        vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello")
        assert detect_caption_source(vtt) == "whisper"

    def test_no_captions(self):
        assert detect_caption_source(None) == "none"
