"""Tests for chapter parsing and chapter-aware pipeline."""
import json
from pathlib import Path

import pytest

from yt_vision_pro.fetch import parse_chapters, ChapterInfo
from yt_vision_pro.db import Database


class TestParseChapters:
    def test_parses_chapters_from_info_json(self, tmp_path: Path):
        info = {
            "id": "abc123",
            "title": "Test",
            "duration": 600.0,
            "webpage_url": "https://youtube.com/watch?v=abc123",
            "chapters": [
                {"title": "Intro", "start_time": 0.0, "end_time": 60.0},
                {"title": "Main Content", "start_time": 60.0, "end_time": 300.0},
                {"title": "Recap", "start_time": 300.0, "end_time": 600.0},
            ],
        }
        info_path = tmp_path / "info.json"
        info_path.write_text(json.dumps(info))

        chapters = parse_chapters(info_path)

        assert len(chapters) == 3
        assert chapters[0].title == "Intro"
        assert chapters[0].start_time == 0.0
        assert chapters[0].end_time == 60.0
        assert chapters[1].title == "Main Content"
        assert chapters[2].title == "Recap"

    def test_returns_empty_when_no_chapters(self, tmp_path: Path):
        info = {
            "id": "abc123",
            "title": "Test",
            "duration": 600.0,
            "webpage_url": "https://youtube.com/watch?v=abc123",
        }
        info_path = tmp_path / "info.json"
        info_path.write_text(json.dumps(info))

        chapters = parse_chapters(info_path)
        assert chapters == []

    def test_returns_empty_when_chapters_is_none(self, tmp_path: Path):
        info = {
            "id": "abc123",
            "title": "Test",
            "duration": 600.0,
            "webpage_url": "https://youtube.com/watch?v=abc123",
            "chapters": None,
        }
        info_path = tmp_path / "info.json"
        info_path.write_text(json.dumps(info))

        chapters = parse_chapters(info_path)
        assert chapters == []

    def test_chapter_info_has_slug(self):
        ch = ChapterInfo(number=1, title="Load Balancing & CDNs", start_time=60.0, end_time=120.0)
        assert ch.slug == "load-balancing-cdns"

    def test_chapter_info_slug_handles_special_chars(self):
        ch = ChapterInfo(number=0, title="Intro: What's New?", start_time=0.0, end_time=30.0)
        assert ch.slug == "intro-whats-new"


class TestChapterDatabase:
    def test_insert_and_get_chapters(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 600.0, "https://example.com")
            db.insert_chapter(
                video_id="abc123",
                chapter_number=0,
                title="Intro",
                start_time=0.0,
                end_time=60.0,
            )
            db.insert_chapter(
                video_id="abc123",
                chapter_number=1,
                title="Main",
                start_time=60.0,
                end_time=300.0,
            )
            chapters = db.get_chapters("abc123")
            assert len(chapters) == 2
            assert chapters[0]["title"] == "Intro"
            assert chapters[1]["start_time"] == 60.0

    def test_get_chapters_returns_empty_for_no_chapters(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 600.0, "https://example.com")
            assert db.get_chapters("abc123") == []

    def test_frame_linked_to_chapter(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 600.0, "https://example.com")
            db.insert_chapter("abc123", 0, "Intro", 0.0, 60.0)
            db.insert_frame(
                video_id="abc123",
                frame_number=0,
                timestamp=15.0,
                path="frames/frame_0000.jpg",
                chapter_id=1,
            )
            frames = db.get_frames("abc123")
            assert frames[0]["chapter_id"] == 1

    def test_get_frames_by_chapter(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 600.0, "https://example.com")
            db.insert_chapter("abc123", 0, "Intro", 0.0, 60.0)
            db.insert_chapter("abc123", 1, "Main", 60.0, 300.0)
            db.insert_frame("abc123", 0, 15.0, "frames/f0.jpg", chapter_id=1)
            db.insert_frame("abc123", 1, 80.0, "frames/f1.jpg", chapter_id=2)
            db.insert_frame("abc123", 2, 120.0, "frames/f2.jpg", chapter_id=2)

            ch1_frames = db.get_frames_by_chapter(chapter_id=1)
            ch2_frames = db.get_frames_by_chapter(chapter_id=2)
            assert len(ch1_frames) == 1
            assert len(ch2_frames) == 2
