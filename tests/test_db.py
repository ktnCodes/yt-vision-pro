"""Tests for yt_vision_pro.db — SQLite metadata store."""
import sqlite3
from pathlib import Path

import pytest

from yt_vision_pro.db import Database


class TestDatabaseSchema:
    def test_create_tables_creates_videos_table(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            cursor = db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='videos'"
            )
            assert cursor.fetchone() is not None

    def test_create_tables_creates_frames_table(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            cursor = db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='frames'"
            )
            assert cursor.fetchone() is not None

    def test_create_tables_is_idempotent(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.create_tables()  # Should not raise


class TestVideoOperations:
    def test_insert_and_get_video(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video(
                video_id="abc123",
                title="Test Video",
                duration=300.0,
                url="https://youtube.com/watch?v=abc123",
            )
            video = db.get_video("abc123")
            assert video is not None
            assert video["video_id"] == "abc123"
            assert video["title"] == "Test Video"
            assert video["duration"] == 300.0

    def test_get_video_returns_none_for_missing(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            assert db.get_video("nonexistent") is None

    def test_insert_video_is_idempotent(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 300.0, "https://example.com")
            db.insert_video("abc123", "Test Updated", 300.0, "https://example.com")
            video = db.get_video("abc123")
            assert video["title"] == "Test Updated"


class TestFrameOperations:
    def test_insert_and_get_frames(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 300.0, "https://example.com")
            db.insert_frame(
                video_id="abc123",
                frame_number=1,
                timestamp=12.5,
                path="frames/frame_001.jpg",
            )
            db.insert_frame(
                video_id="abc123",
                frame_number=2,
                timestamp=45.2,
                path="frames/frame_002.jpg",
            )
            frames = db.get_frames("abc123")
            assert len(frames) == 2
            assert frames[0]["timestamp"] == 12.5
            assert frames[1]["timestamp"] == 45.2

    def test_get_frames_returns_empty_for_no_frames(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 300.0, "https://example.com")
            assert db.get_frames("abc123") == []

    def test_can_filter_kept_frames(self, tmp_path: Path):
        db_path = tmp_path / "pipeline.db"
        with Database(db_path) as db:
            db.create_tables()
            db.insert_video("abc123", "Test", 300.0, "https://example.com")
            kept_id = db.insert_frame("abc123", 1, 12.5, "frames/frame_001.jpg")
            removed_id = db.insert_frame("abc123", 2, 45.2, "frames/frame_002.jpg")

            db.set_frame_keep_status([kept_id], True)
            db.set_frame_keep_status([removed_id], False)

            frames = db.get_frames("abc123", kept_only=True)
            assert len(frames) == 1
            assert frames[0]["frame_number"] == 1
