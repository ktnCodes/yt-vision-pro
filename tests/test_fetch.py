"""Tests for yt_vision_pro.fetch — yt-dlp download wrapper."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_vision_pro.fetch import fetch_video, parse_video_info, VideoInfo


class TestParseVideoInfo:
    def test_parses_basic_info_json(self, tmp_path: Path):
        info = {
            "id": "abc123",
            "title": "Test Video Title",
            "duration": 305.4,
            "webpage_url": "https://www.youtube.com/watch?v=abc123",
            "description": "A test video description.",
        }
        info_path = tmp_path / "info.json"
        info_path.write_text(json.dumps(info))

        result = parse_video_info(info_path)

        assert isinstance(result, VideoInfo)
        assert result.video_id == "abc123"
        assert result.title == "Test Video Title"
        assert result.duration == 305.4
        assert result.url == "https://www.youtube.com/watch?v=abc123"
        assert result.description == "A test video description."

    def test_handles_missing_description(self, tmp_path: Path):
        info = {
            "id": "abc123",
            "title": "No Desc",
            "duration": 60.0,
            "webpage_url": "https://youtube.com/watch?v=abc123",
        }
        info_path = tmp_path / "info.json"
        info_path.write_text(json.dumps(info))

        result = parse_video_info(info_path)
        assert result.description == ""


class TestFetchVideo:
    @patch("yt_vision_pro.fetch.subprocess.run")
    def test_fetch_video_calls_ytdlp_and_returns_video_info(
        self, mock_run: MagicMock, tmp_path: Path
    ):
        cache_dir = tmp_path / "cache" / "abc123"
        cache_dir.mkdir(parents=True)

        # Simulate yt-dlp writing files
        info_data = {
            "id": "abc123",
            "title": "Test",
            "duration": 120.0,
            "webpage_url": "https://youtube.com/watch?v=abc123",
            "description": "desc",
        }

        def fake_run(cmd, **kwargs):
            # yt-dlp writes info.json and source.mp4
            (cache_dir / "source.info.json").write_text(json.dumps(info_data))
            (cache_dir / "source.mp4").write_bytes(b"fake")
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run

        result = fetch_video("https://youtube.com/watch?v=abc123", cache_dir)

        assert result.video_id == "abc123"
        assert result.title == "Test"
        assert mock_run.called

    @patch("yt_vision_pro.fetch.subprocess.run")
    def test_fetch_video_sets_captions_path_when_vtt_exists(
        self, mock_run: MagicMock, tmp_path: Path
    ):
        cache_dir = tmp_path / "cache" / "abc123"
        cache_dir.mkdir(parents=True)

        info_data = {
            "id": "abc123",
            "title": "Test",
            "duration": 120.0,
            "webpage_url": "https://youtube.com/watch?v=abc123",
        }

        def fake_run(cmd, **kwargs):
            (cache_dir / "source.info.json").write_text(json.dumps(info_data))
            (cache_dir / "source.mp4").write_bytes(b"fake")
            (cache_dir / "source.en.vtt").write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello")
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run

        result = fetch_video("https://youtube.com/watch?v=abc123", cache_dir)

        assert result.captions_path is not None
        assert result.captions_path.suffix == ".vtt"

    @patch("yt_vision_pro.fetch.subprocess.run")
    def test_fetch_video_captions_path_none_when_no_vtt(
        self, mock_run: MagicMock, tmp_path: Path
    ):
        cache_dir = tmp_path / "cache" / "abc123"
        cache_dir.mkdir(parents=True)

        info_data = {
            "id": "abc123",
            "title": "Test",
            "duration": 120.0,
            "webpage_url": "https://youtube.com/watch?v=abc123",
        }

        def fake_run(cmd, **kwargs):
            (cache_dir / "source.info.json").write_text(json.dumps(info_data))
            (cache_dir / "source.mp4").write_bytes(b"fake")
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run

        result = fetch_video("https://youtube.com/watch?v=abc123", cache_dir)

        assert result.captions_path is None
