"""Tests for yt_vision_pro.manifest — manifest generation."""
from pathlib import Path

import pytest

from yt_vision_pro.manifest import generate_manifest


class TestGenerateManifest:
    def test_generates_markdown_file(self, tmp_path: Path):
        output_path = tmp_path / "manifest.md"

        result = generate_manifest(
            video_id="abc123",
            title="Test Video",
            duration=300.0,
            description="A test description.",
            frames=[
                {"frame_number": 0, "timestamp": 5.0, "path": "frames/frame_0000.jpg"},
                {"frame_number": 1, "timestamp": 15.0, "path": "frames/frame_0001.jpg"},
            ],
            captions=[
                {"start": 4.0, "end": 6.0, "text": "Hello world"},
                {"start": 14.0, "end": 16.0, "text": "Second caption"},
            ],
            output_path=output_path,
        )

        assert result == output_path
        assert output_path.exists()

    def test_manifest_contains_frontmatter(self, tmp_path: Path):
        output_path = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc123",
            title="Test Video",
            duration=300.0,
            description="desc",
            frames=[],
            captions=[],
            output_path=output_path,
        )
        content = output_path.read_text()
        assert content.startswith("---\n")
        assert "video_id: abc123" in content
        assert "video_title:" in content
        assert "density: normal" in content
        assert "slide_aware_dedup: true" in content

    def test_manifest_contains_running_summary_slot(self, tmp_path: Path):
        output_path = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc123",
            title="Test Video",
            duration=300.0,
            description="desc",
            frames=[],
            captions=[],
            output_path=output_path,
        )
        content = output_path.read_text()
        assert "## Running Summary" in content
        assert "Not yet processed" in content

    def test_manifest_renders_frame_references(self, tmp_path: Path):
        output_path = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc123",
            title="Test",
            duration=120.0,
            description="",
            frames=[
                {"frame_number": 0, "timestamp": 5.0, "path": "frames/frame_0000.jpg"},
                {"frame_number": 1, "timestamp": 25.0, "path": "frames/frame_0001.jpg"},
            ],
            captions=[
                {"start": 4.5, "end": 6.0, "text": "First caption"},
            ],
            output_path=output_path,
        )
        content = output_path.read_text()
        assert "frame_0000.jpg" in content
        assert "frame_0001.jpg" in content
        assert "5.0s" in content or "5.00s" in content or "@ 5.0" in content

    def test_manifest_includes_description_section(self, tmp_path: Path):
        output_path = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc123",
            title="Test",
            duration=60.0,
            description="This is the full YouTube description.",
            frames=[],
            captions=[],
            output_path=output_path,
        )
        content = output_path.read_text()
        assert "## Video Context" in content
        assert "This is the full YouTube description." in content

    def test_manifest_includes_caption_text_near_frames(self, tmp_path: Path):
        output_path = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc123",
            title="Test",
            duration=60.0,
            description="",
            frames=[
                {"frame_number": 0, "timestamp": 5.0, "path": "frames/frame_0000.jpg"},
            ],
            captions=[
                {"start": 4.0, "end": 6.5, "text": "Aligned caption text"},
            ],
            output_path=output_path,
        )
        content = output_path.read_text()
        assert "Aligned caption text" in content
