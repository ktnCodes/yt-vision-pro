"""SQLite metadata store for the yt-vision-pro pipeline."""
import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.conn: sqlite3.Connection | None = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id   TEXT PRIMARY KEY,
                title      TEXT NOT NULL,
                duration   REAL NOT NULL,
                url        TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chapters (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id       TEXT NOT NULL REFERENCES videos(video_id),
                chapter_number INTEGER NOT NULL,
                title          TEXT NOT NULL,
                start_time     REAL NOT NULL,
                end_time       REAL NOT NULL,
                is_synthetic   INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS frames (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id     TEXT NOT NULL REFERENCES videos(video_id),
                chapter_id   INTEGER REFERENCES chapters(id),
                frame_number INTEGER NOT NULL,
                timestamp    REAL NOT NULL,
                path         TEXT NOT NULL,
                ocr_text     TEXT DEFAULT '',
                is_kept      INTEGER DEFAULT 1
            );
        """)
        self._ensure_column("frames", "is_kept", "INTEGER DEFAULT 1")
        self.conn.commit()

    def _has_column(self, table: str, column: str) -> bool:
        rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(row[1] == column for row in rows)

    def _ensure_column(self, table: str, column: str, definition: str):
        if self._has_column(table, column):
            return
        self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def insert_video(self, video_id: str, title: str, duration: float, url: str):
        self.conn.execute(
            """INSERT INTO videos (video_id, title, duration, url)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(video_id) DO UPDATE SET title=excluded.title""",
            (video_id, title, duration, url),
        )
        self.conn.commit()

    def get_video(self, video_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def insert_frame(
        self,
        video_id: str,
        frame_number: int,
        timestamp: float,
        path: str,
        chapter_id: int | None = None,
        ocr_text: str = "",
        is_kept: bool = True,
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO frames (video_id, frame_number, timestamp, path, chapter_id, ocr_text, is_kept)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (video_id, frame_number, timestamp, path, chapter_id, ocr_text, int(is_kept)),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def get_frames(self, video_id: str, kept_only: bool | None = None) -> list[dict]:
        query = "SELECT * FROM frames WHERE video_id = ?"
        params: list[object] = [video_id]
        if kept_only is not None:
            query += " AND is_kept = ?"
            params.append(int(kept_only))
        query += " ORDER BY timestamp"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_frames_by_chapter(self, chapter_id: int, kept_only: bool | None = None) -> list[dict]:
        query = "SELECT * FROM frames WHERE chapter_id = ?"
        params: list[object] = [chapter_id]
        if kept_only is not None:
            query += " AND is_kept = ?"
            params.append(int(kept_only))
        query += " ORDER BY timestamp"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def update_frame_ocr(self, frame_id: int, ocr_text: str):
        self.conn.execute(
            "UPDATE frames SET ocr_text = ? WHERE id = ?",
            (ocr_text, frame_id),
        )
        self.conn.commit()

    def set_frame_keep_status(self, frame_ids: list[int], is_kept: bool):
        if not frame_ids:
            return
        placeholders = ", ".join("?" for _ in frame_ids)
        self.conn.execute(
            f"UPDATE frames SET is_kept = ? WHERE id IN ({placeholders})",
            (int(is_kept), *frame_ids),
        )
        self.conn.commit()

    def reset_frame_keep_status(self, video_id: str, is_kept: bool):
        self.conn.execute(
            "UPDATE frames SET is_kept = ? WHERE video_id = ?",
            (int(is_kept), video_id),
        )
        self.conn.commit()

    def delete_frames(self, video_id: str):
        self.conn.execute("DELETE FROM frames WHERE video_id = ?", (video_id,))
        self.conn.commit()

    def insert_chapter(self, video_id: str, chapter_number: int, title: str, start_time: float, end_time: float, is_synthetic: bool = False):
        self.conn.execute(
            """INSERT INTO chapters (video_id, chapter_number, title, start_time, end_time, is_synthetic)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (video_id, chapter_number, title, start_time, end_time, int(is_synthetic)),
        )
        self.conn.commit()

    def delete_chapters(self, video_id: str):
        self.conn.execute("DELETE FROM chapters WHERE video_id = ?", (video_id,))
        self.conn.commit()

    def get_chapters(self, video_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM chapters WHERE video_id = ? ORDER BY chapter_number",
            (video_id,),
        ).fetchall()
        return [dict(r) for r in rows]
