"""Tests for yt_vision_pro.cli — Typer CLI."""
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from yt_vision_pro.cli import app
from yt_vision_pro.extract import ExtractionPoint
from yt_vision_pro.fetch import ChapterInfo, VideoInfo


runner = CliRunner()


class TestProcessCommand:
    @patch("yt_vision_pro.cli.transcribe_audio")
    @patch("yt_vision_pro.cli.is_whisper_available", return_value=False)
    @patch("yt_vision_pro.cli.extract_ocr_result", return_value={"text": "", "text_length": 0})
    @patch("yt_vision_pro.cli.is_slide_like", return_value=False)
    @patch("yt_vision_pro.cli.deduplicate_frames")
    @patch("yt_vision_pro.cli.is_blurry", return_value=False)
    @patch("yt_vision_pro.cli.is_black_frame", return_value=False)
    @patch("yt_vision_pro.cli.generate_manifest")
    @patch("yt_vision_pro.cli.extract_frames")
    @patch("yt_vision_pro.cli.compute_extraction_points")
    @patch("yt_vision_pro.cli.detect_scenes")
    @patch("yt_vision_pro.cli.parse_captions")
    @patch("yt_vision_pro.cli.fetch_video")
    def test_process_runs_end_to_end(
        self,
        mock_fetch,
        mock_parse_captions,
        mock_detect,
        mock_compute,
        mock_extract,
        mock_manifest,
        mock_is_black,
        mock_is_blurry,
        mock_dedup,
        mock_is_slide_like,
        mock_ocr,
        mock_whisper_avail,
        mock_transcribe,
        tmp_path: Path,
    ):
        frame_paths = [
            tmp_path / "frames" / "frame_00005.00.jpg",
            tmp_path / "frames" / "frame_00015.00.jpg",
            tmp_path / "frames" / "frame_00030.00.jpg",
        ]
        (tmp_path / "frames").mkdir(parents=True, exist_ok=True)
        for frame_path in frame_paths:
            frame_path.write_bytes(b"\x00" * 100)

        mock_fetch.return_value = VideoInfo(
            video_id="abc123",
            title="Test Video",
            duration=120.0,
            url="https://youtube.com/watch?v=abc123",
            description="Test desc",
            video_path=tmp_path / "source.mp4",
            captions_path=tmp_path / "source.en.vtt",
            chapters=[ChapterInfo(0, "Lecture", 0.0, 120.0)],
        )
        mock_detect.return_value = [(0.0, 10.0)]
        mock_compute.return_value = [
            ExtractionPoint(timestamp=5.0, chapter_number=0, density="high", scene_id=0),
            ExtractionPoint(timestamp=15.0, chapter_number=0, density="high", scene_id=1),
            ExtractionPoint(timestamp=30.0, chapter_number=0, density="high", scene_id=2),
        ]
        mock_extract.return_value = frame_paths
        mock_dedup.return_value = (frame_paths, [])
        mock_parse_captions.return_value = [{"start": 4.0, "end": 6.0, "text": "Hello"}]
        mock_manifest.return_value = tmp_path / "manifest.md"

        result = runner.invoke(
            app,
            [
                "https://youtube.com/watch?v=abc123",
                "--cache-dir", str(tmp_path),
                "--dense-until", "00:10:00",
                "--thorough",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_fetch.assert_called_once()
        mock_detect.assert_called_once()
        mock_compute.assert_called_once()
        assert mock_compute.call_args.args[1][0].density == "high"
        mock_manifest.assert_called_once()

    def test_process_requires_url_argument(self):
        result = runner.invoke(app, [])
        assert result.exit_code != 0

    @patch("yt_vision_pro.cli.transcribe_audio")
    @patch("yt_vision_pro.cli.is_whisper_available", return_value=False)
    @patch("yt_vision_pro.cli.extract_ocr_result", return_value={"text": "", "text_length": 0})
    @patch("yt_vision_pro.cli.is_slide_like", return_value=False)
    @patch("yt_vision_pro.cli.deduplicate_frames")
    @patch("yt_vision_pro.cli.is_blurry", return_value=False)
    @patch("yt_vision_pro.cli.is_black_frame", return_value=False)
    @patch("yt_vision_pro.cli.generate_manifest")
    @patch("yt_vision_pro.cli.extract_frames")
    @patch("yt_vision_pro.cli.compute_extraction_points")
    @patch("yt_vision_pro.cli.detect_scenes")
    @patch("yt_vision_pro.cli.parse_captions")
    @patch("yt_vision_pro.cli.fetch_video")
    def test_process_clears_stale_frames_before_extract(
        self,
        mock_fetch,
        mock_parse_captions,
        mock_detect,
        mock_compute,
        mock_extract,
        mock_manifest,
        mock_is_black,
        mock_is_blurry,
        mock_dedup,
        mock_is_slide_like,
        mock_ocr,
        mock_whisper_avail,
        mock_transcribe,
        tmp_path: Path,
    ):
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        stale_path = frames_dir / "stale.jpg"
        stale_path.write_bytes(b"stale")

        fresh_path = frames_dir / "frame_00005.00.jpg"
        fresh_path.write_bytes(b"fresh")

        mock_fetch.return_value = VideoInfo(
            video_id="abc123",
            title="Test Video",
            duration=120.0,
            url="https://youtube.com/watch?v=abc123",
            description="Test desc",
            video_path=tmp_path / "source.mp4",
            captions_path=tmp_path / "source.en.vtt",
            chapters=[ChapterInfo(0, "Lecture", 0.0, 120.0)],
        )
        mock_detect.return_value = [(0.0, 10.0)]
        mock_compute.return_value = [
            ExtractionPoint(timestamp=5.0, chapter_number=0, density="normal", scene_id=0),
        ]
        mock_extract.return_value = [fresh_path]
        mock_dedup.return_value = ([fresh_path], [])
        mock_parse_captions.return_value = []
        mock_manifest.return_value = tmp_path / "manifest.md"

        result = runner.invoke(
            app,
            ["https://youtube.com/watch?v=abc123", "--cache-dir", str(tmp_path), "--thorough"],
        )

        assert result.exit_code == 0, result.output
        assert stale_path.exists() is False

    @patch("yt_vision_pro.cli.transcribe_audio")
    @patch("yt_vision_pro.cli.is_whisper_available", return_value=False)
    @patch("yt_vision_pro.cli.extract_ocr_result", return_value={"text": "", "text_length": 0})
    @patch("yt_vision_pro.cli.is_slide_like", return_value=False)
    @patch("yt_vision_pro.cli.deduplicate_frames")
    @patch("yt_vision_pro.cli.is_blurry", return_value=False)
    @patch("yt_vision_pro.cli.is_black_frame", return_value=False)
    @patch("yt_vision_pro.cli.generate_chapter_manifest")
    @patch("yt_vision_pro.cli.extract_frames")
    @patch("yt_vision_pro.cli.compute_extraction_points")
    @patch("yt_vision_pro.cli.detect_scenes")
    @patch("yt_vision_pro.cli.parse_captions")
    @patch("yt_vision_pro.cli.fetch_video")
    def test_process_generates_chapter_manifests(
        self,
        mock_fetch,
        mock_parse_captions,
        mock_detect,
        mock_compute,
        mock_extract,
        mock_chapter_manifest,
        mock_is_black,
        mock_is_blurry,
        mock_dedup,
        mock_is_slide_like,
        mock_ocr,
        mock_whisper_avail,
        mock_transcribe,
        tmp_path: Path,
    ):
        frame_paths = [tmp_path / "frames" / f"frame_0000{i}.jpg" for i in range(3)]
        (tmp_path / "frames").mkdir(parents=True, exist_ok=True)
        for frame_path in frame_paths:
            frame_path.write_bytes(b"\x00" * 100)

        mock_fetch.return_value = VideoInfo(
            video_id="abc123",
            title="Test Video",
            duration=600.0,
            url="https://youtube.com/watch?v=abc123",
            description="",
            video_path=tmp_path / "source.mp4",
            captions_path=tmp_path / "source.en.vtt",
            chapters=[
                ChapterInfo(0, "Intro", 0.0, 60.0),
                ChapterInfo(1, "Main", 60.0, 600.0),
            ],
        )
        mock_detect.return_value = [(0.0, 10.0), (60.0, 90.0)]
        mock_compute.return_value = [
            ExtractionPoint(timestamp=5.0, chapter_number=0, density="normal", scene_id=0),
            ExtractionPoint(timestamp=70.0, chapter_number=1, density="high", scene_id=1),
            ExtractionPoint(timestamp=200.0, chapter_number=1, density="high", scene_id=2),
        ]
        mock_extract.return_value = frame_paths
        mock_dedup.return_value = (frame_paths, [])
        mock_parse_captions.return_value = []
        mock_chapter_manifest.return_value = tmp_path / "manifests" / "manifest.md"

        result = runner.invoke(
            app,
            [
                "https://youtube.com/watch?v=abc123",
                "--cache-dir", str(tmp_path),
                "--detector", "adaptive",
                "--dense-chapters", "1",
                "--thorough",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_detect.assert_called_once_with(mock_fetch.return_value.video_path, detector="adaptive", sensitivity=30.0)
        assert mock_chapter_manifest.call_count == 2

    @patch("yt_vision_pro.cli.transcribe_audio")
    @patch("yt_vision_pro.cli.is_whisper_available", return_value=False)
    @patch("yt_vision_pro.cli.extract_ocr_result", return_value={"text": "", "text_length": 0})
    @patch("yt_vision_pro.cli.is_slide_like", return_value=False)
    @patch("yt_vision_pro.cli.deduplicate_frames")
    @patch("yt_vision_pro.cli.is_blurry", return_value=False)
    @patch("yt_vision_pro.cli.is_black_frame", return_value=False)
    @patch("yt_vision_pro.cli.generate_manifest")
    @patch("yt_vision_pro.cli.extract_frames")
    @patch("yt_vision_pro.cli.compute_extraction_points")
    @patch("yt_vision_pro.cli.detect_scenes")
    @patch("yt_vision_pro.cli.parse_captions")
    @patch("yt_vision_pro.cli.fetch_video")
    def test_force_flag_clears_sentinels(
        self,
        mock_fetch,
        mock_parse_captions,
        mock_detect,
        mock_compute,
        mock_extract,
        mock_manifest,
        mock_is_black,
        mock_is_blurry,
        mock_dedup,
        mock_is_slide_like,
        mock_ocr,
        mock_whisper_avail,
        mock_transcribe,
        tmp_path: Path,
    ):
        (tmp_path / "frames").mkdir(parents=True, exist_ok=True)
        frame_paths = [tmp_path / "frames" / "f.jpg"]
        frame_paths[0].write_bytes(b"\x00" * 100)

        mock_fetch.return_value = VideoInfo(
            video_id="abc123",
            title="T",
            duration=60.0,
            url="https://youtube.com/watch?v=abc123",
            video_path=tmp_path / "source.mp4",
            chapters=[ChapterInfo(0, "Intro", 0.0, 60.0)],
        )
        mock_detect.return_value = [(0.0, 10.0)]
        mock_compute.return_value = [ExtractionPoint(timestamp=5.0, chapter_number=0, density="normal", scene_id=0)]
        mock_extract.return_value = frame_paths
        mock_dedup.return_value = (frame_paths, [])
        mock_manifest.return_value = tmp_path / "manifest.md"

        from yt_vision_pro.stages import is_stage_done, mark_stage_done
        mark_stage_done(tmp_path, "fetch")
        mark_stage_done(tmp_path, "extract")
        assert is_stage_done(tmp_path, "fetch")

        result = runner.invoke(
            app,
            ["https://youtube.com/watch?v=abc123", "--cache-dir", str(tmp_path), "--force", "--thorough"],
        )

        assert result.exit_code == 0, result.output
        mock_fetch.assert_called_once()
