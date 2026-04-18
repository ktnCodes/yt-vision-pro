"""Tests for per-chapter manifest generation."""
from pathlib import Path

import pytest

from yt_vision_pro.manifest import generate_chapter_manifest


class TestGenerateChapterManifest:
    def test_generates_chapter_manifest_file(self, tmp_path: Path):
        manifests_dir = tmp_path / "manifests"
        result = generate_chapter_manifest(
            video_id="abc123",
            video_title="Full Video Title",
            video_duration=600.0,
            description="Full desc",
            chapter_number=2,
            chapter_title="Load Balancing",
            chapter_timerange="60.0-300.0",
            frames=[
                {"frame_number": 0, "timestamp": 65.0, "path": "frames/frame_0000.jpg"},
            ],
            captions=[],
            output_dir=manifests_dir,
        )

        assert result.exists()
        assert "manifest-02-load-balancing.md" in result.name

    def test_chapter_manifest_contains_chapter_frontmatter(self, tmp_path: Path):
        manifests_dir = tmp_path / "manifests"
        result = generate_chapter_manifest(
            video_id="abc123",
            video_title="Test Video",
            video_duration=600.0,
            description="desc",
            chapter_number=1,
            chapter_title="Getting Started",
            chapter_timerange="0.0-120.0",
            frames=[],
            captions=[],
            output_dir=manifests_dir,
        )
        content = result.read_text()
        assert "chapter_number: 1" in content
        assert 'chapter_title: "Getting Started"' in content
        assert "chapter_timerange:" in content
        assert "density: normal" in content
        assert "manifest_version: 3" in content

    def test_chapter_manifest_has_running_summary(self, tmp_path: Path):
        manifests_dir = tmp_path / "manifests"
        result = generate_chapter_manifest(
            video_id="abc123",
            video_title="T",
            video_duration=60.0,
            description="",
            chapter_number=0,
            chapter_title="Intro",
            chapter_timerange="0.0-60.0",
            frames=[],
            captions=[],
            output_dir=manifests_dir,
        )
        content = result.read_text()
        assert "## Running Summary" in content
        assert "Not yet processed" in content

    def test_multiple_chapters_produce_separate_files(self, tmp_path: Path):
        manifests_dir = tmp_path / "manifests"
        paths = []
        for i, title in enumerate(["Intro", "Main", "Recap"]):
            p = generate_chapter_manifest(
                video_id="abc123",
                video_title="Test",
                video_duration=600.0,
                description="",
                chapter_number=i,
                chapter_title=title,
                chapter_timerange=f"{i*200.0}-{(i+1)*200.0}",
                frames=[],
                captions=[],
                output_dir=manifests_dir,
            )
            paths.append(p)

        assert len(set(paths)) == 3
        assert all(p.exists() for p in paths)
        assert "manifest-00-intro.md" in paths[0].name
        assert "manifest-01-main.md" in paths[1].name
        assert "manifest-02-recap.md" in paths[2].name
