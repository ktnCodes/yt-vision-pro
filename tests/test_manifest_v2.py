"""Tests for v2 manifest spec — chunking, analysis slots, synthesis instructions."""
from pathlib import Path
import pytest
from yt_vision_pro.manifest import _chunk_frames, generate_manifest, generate_chapter_manifest

class TestChunkFrames:
    def test_chunks_frames_by_max(self):
        frames = [{"frame_number": i, "timestamp": float(i), "path": f"f{i}.jpg"} for i in range(25)]
        chunks = _chunk_frames(frames, max_per_chunk=12)
        assert len(chunks) == 3  # 12, 12, 1
        assert len(chunks[0]) == 12
        assert len(chunks[1]) == 12
        assert len(chunks[2]) == 1

    def test_single_chunk_when_fewer_than_max(self):
        frames = [{"frame_number": i, "timestamp": float(i), "path": f"f{i}.jpg"} for i in range(5)]
        chunks = _chunk_frames(frames, max_per_chunk=12)
        assert len(chunks) == 1
        assert len(chunks[0]) == 5

    def test_empty_frames_returns_empty(self):
        chunks = _chunk_frames([], max_per_chunk=12)
        assert chunks == []

    def test_exact_multiple(self):
        frames = [{"frame_number": i, "timestamp": float(i), "path": f"f{i}.jpg"} for i in range(24)]
        chunks = _chunk_frames(frames, max_per_chunk=12)
        assert len(chunks) == 2
        assert all(len(c) == 12 for c in chunks)

class TestV2ManifestFrontmatter:
    def test_includes_detector_field(self, tmp_path: Path):
        p = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc", title="T", duration=60.0, description="",
            frames=[], captions=[], output_path=p,
            detector="content", ocr_applied=True, caption_source="youtube"
        )
        content = p.read_text()
        assert "detector: content" in content

    def test_includes_ocr_applied_field(self, tmp_path: Path):
        p = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc", title="T", duration=60.0, description="",
            frames=[], captions=[], output_path=p,
            detector="content", ocr_applied=True, caption_source="youtube"
        )
        content = p.read_text()
        assert "ocr_applied: true" in content

    def test_includes_caption_source(self, tmp_path: Path):
        p = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc", title="T", duration=60.0, description="",
            frames=[], captions=[], output_path=p,
            detector="content", ocr_applied=False, caption_source="whisper"
        )
        content = p.read_text()
        assert "caption_source: whisper" in content

    def test_includes_density_metadata(self, tmp_path: Path):
        p = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc", title="T", duration=60.0, description="",
            frames=[], captions=[], output_path=p,
            detector="content", density="high", sensitivity=18.0, scene_sample_interval=3.0
        )
        content = p.read_text()
        assert "density: high" in content
        assert "sensitivity: 18.0" in content
        assert "scene_sample_interval: 3.0" in content
        assert "manifest_version: 3" in content

class TestV2ManifestChunking:
    def test_manifest_has_chunk_headers(self, tmp_path: Path):
        frames = [{"frame_number": i, "timestamp": float(i*10), "path": f"f{i}.jpg"} for i in range(15)]
        p = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc", title="T", duration=300.0, description="",
            frames=frames, captions=[], output_path=p
        )
        content = p.read_text()
        assert "## Chunk 1 of 2" in content
        assert "## Chunk 2 of 2" in content

    def test_manifest_has_analysis_slots(self, tmp_path: Path):
        frames = [{"frame_number": i, "timestamp": float(i*10), "path": f"f{i}.jpg"} for i in range(5)]
        p = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc", title="T", duration=60.0, description="",
            frames=frames, captions=[], output_path=p
        )
        content = p.read_text()
        assert "### Analysis" in content

class TestV2SynthesisInstructions:
    def test_has_final_synthesis_section(self, tmp_path: Path):
        p = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc", title="T", duration=60.0, description="",
            frames=[], captions=[], output_path=p
        )
        content = p.read_text()
        assert "## Final Synthesis" in content

    def test_mentions_code_preservation(self, tmp_path: Path):
        p = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc", title="T", duration=60.0, description="",
            frames=[], captions=[], output_path=p
        )
        content = p.read_text()
        assert "code" in content.lower() or "verbatim" in content.lower()

    def test_mentions_mermaid_preservation(self, tmp_path: Path):
        p = tmp_path / "manifest.md"
        generate_manifest(
            video_id="abc", title="T", duration=60.0, description="",
            frames=[], captions=[], output_path=p
        )
        content = p.read_text()
        # The synthesis instructions should mention preserving diagrams
        assert "diagram" in content.lower() or "mermaid" in content.lower()

class TestV2ChapterManifest:
    def test_chapter_manifest_has_v2_frontmatter(self, tmp_path: Path):
        manifests_dir = tmp_path / "manifests"
        result = generate_chapter_manifest(
            video_id="abc", video_title="T", video_duration=600.0,
            description="", chapter_number=0, chapter_title="Intro",
            chapter_timerange="0.0-60.0",
            frames=[], captions=[], output_dir=manifests_dir,
            detector="content", ocr_applied=True, caption_source="youtube"
        )
        content = result.read_text()
        assert "detector: content" in content
        assert "ocr_applied: true" in content
        assert "caption_source: youtube" in content
        assert "slide_aware_dedup: true" in content
