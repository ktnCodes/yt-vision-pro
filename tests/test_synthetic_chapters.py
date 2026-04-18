"""Tests for synthetic chapter generation for unchaptered videos."""
import json
import math
from pathlib import Path
import pytest
from yt_vision_pro.fetch import generate_synthetic_chapters, ChapterInfo
from yt_vision_pro.db import Database


class TestGenerateSyntheticChapters:
    def test_45min_video_produces_3_chapters(self):
        chapters = generate_synthetic_chapters(duration=2700.0, max_chapter_length=900.0)
        assert len(chapters) == 3

    def test_chapter_times_cover_full_duration(self):
        chapters = generate_synthetic_chapters(duration=2700.0, max_chapter_length=900.0)
        assert chapters[0].start_time == 0.0
        assert chapters[-1].end_time == 2700.0

    def test_chapter_titles_auto_numbered(self):
        chapters = generate_synthetic_chapters(duration=2700.0, max_chapter_length=900.0)
        assert chapters[0].title == "Part 1"
        assert chapters[1].title == "Part 2"
        assert chapters[2].title == "Part 3"

    def test_chapters_marked_synthetic(self):
        chapters = generate_synthetic_chapters(duration=2700.0, max_chapter_length=900.0)
        assert all(ch.is_synthetic for ch in chapters)

    def test_short_video_produces_one_chapter(self):
        chapters = generate_synthetic_chapters(duration=300.0, max_chapter_length=900.0)
        assert len(chapters) == 1
        assert chapters[0].start_time == 0.0
        assert chapters[0].end_time == 300.0

    def test_custom_chapter_length(self):
        chapters = generate_synthetic_chapters(duration=3600.0, max_chapter_length=600.0)
        assert len(chapters) == 6

    def test_partial_last_chapter(self):
        # 25 min = 1500s, at 900s max -> int(1500/900)=1 chapter covering full duration
        chapters = generate_synthetic_chapters(duration=1500.0, max_chapter_length=900.0)
        assert len(chapters) == 1
        assert chapters[0].end_time == 1500.0


class TestSyntheticChapterDatabase:
    def test_insert_synthetic_chapter(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 2700.0, "https://example.com")
            db.insert_chapter("abc123", 0, "auto-chapter-00", 0.0, 900.0, is_synthetic=True)
            chapters = db.get_chapters("abc123")
            assert chapters[0]["is_synthetic"] == 1

    def test_real_chapter_not_synthetic(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 600.0, "https://example.com")
            db.insert_chapter("abc123", 0, "Intro", 0.0, 60.0)
            chapters = db.get_chapters("abc123")
            assert chapters[0]["is_synthetic"] == 0
