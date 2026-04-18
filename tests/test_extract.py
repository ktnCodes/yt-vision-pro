"""Tests for yt_vision_pro.extract — scene detection + frame extraction."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from yt_vision_pro.extract import ExtractionPoint, compute_extraction_points, compute_light_extraction_points, detect_scenes, extract_frames
from yt_vision_pro.fetch import ChapterInfo
from yt_vision_pro.stages import build_density_profiles


class TestDetectScenes:
    @patch("yt_vision_pro.extract.ContentDetector")
    @patch("yt_vision_pro.extract.open_video")
    @patch("yt_vision_pro.extract.SceneManager")
    def test_returns_scene_windows_for_content_detector(self, MockSceneManager, mock_open_video, MockContentDetector):
        mock_video = MagicMock()
        mock_open_video.return_value = mock_video

        mock_manager = MockSceneManager.return_value
        mock_manager.get_scene_list.return_value = [
            (MagicMock(get_seconds=lambda: 0.0), MagicMock(get_seconds=lambda: 5.0)),
            (MagicMock(get_seconds=lambda: 5.0), MagicMock(get_seconds=lambda: 15.0)),
        ]

        scenes = detect_scenes(Path("fake_video.mp4"), detector="content", sensitivity=18.0)

        MockContentDetector.assert_called_once_with(threshold=18.0)
        assert scenes == [(0.0, 5.0), (5.0, 15.0)]

    @patch("yt_vision_pro.extract.AdaptiveDetector")
    @patch("yt_vision_pro.extract.open_video")
    @patch("yt_vision_pro.extract.SceneManager")
    def test_uses_adaptive_detector_when_requested(self, MockSceneManager, mock_open_video, MockAdaptiveDetector):
        mock_open_video.return_value = MagicMock()
        mock_manager = MockSceneManager.return_value
        mock_manager.get_scene_list.return_value = []

        scenes = detect_scenes(Path("fake_video.mp4"), detector="adaptive")

        MockAdaptiveDetector.assert_called_once_with()
        assert scenes == []


class TestComputeExtractionPoints:
    def test_samples_within_scene_using_chapter_density(self):
        chapters = [
            ChapterInfo(number=0, title="Lecture", start_time=0.0, end_time=10.0, density="high"),
        ]
        profiles = build_density_profiles("normal", 5.0)

        points = compute_extraction_points([(0.0, 10.0)], chapters, profiles)

        assert [point.timestamp for point in points] == [0.0, 3.0, 6.0, 9.0]
        assert all(point.density == "high" for point in points)

    def test_fallback_sampling_when_no_scenes(self):
        chapters = [
            ChapterInfo(number=0, title="Lecture", start_time=0.0, end_time=65.0, density="normal"),
        ]
        profiles = build_density_profiles("normal", 5.0)

        points = compute_extraction_points([], chapters, profiles, fallback_interval=30.0)

        assert [point.timestamp for point in points] == [0.0, 30.0, 60.0]
        assert all(isinstance(point, ExtractionPoint) for point in points)


class TestExtractFrames:
    @patch("yt_vision_pro.extract.subprocess.run")
    def test_extracts_frames_at_timestamps(self, mock_run, tmp_path: Path):
        output_dir = tmp_path / "frames"
        output_dir.mkdir()

        timestamps = [5.0, 15.0, 30.0]

        def fake_ffmpeg(cmd, **kwargs):
            # Parse output path from ffmpeg command and create a fake image
            output_path = cmd[-1]
            Path(output_path).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_ffmpeg

        paths = extract_frames(Path("fake.mp4"), timestamps, output_dir)

        assert len(paths) == 3
        assert all(p.exists() for p in paths)
        assert paths[0].name == "frame_00005.00.jpg"
        assert mock_run.call_count == 3

    @patch("yt_vision_pro.extract.subprocess.run")
    def test_returns_empty_for_no_timestamps(self, mock_run, tmp_path: Path):
        output_dir = tmp_path / "frames"
        output_dir.mkdir()

        paths = extract_frames(Path("fake.mp4"), [], output_dir)

        assert paths == []
        assert mock_run.call_count == 0


class TestComputeLightExtractionPoints:
    def test_maps_timestamps_to_chapters(self):
        chapters = [
            ChapterInfo(number=0, title="Intro", start_time=0.0, end_time=60.0, density="normal"),
            ChapterInfo(number=1, title="Main", start_time=60.0, end_time=120.0, density="normal"),
        ]
        timestamps = [10.0, 30.0, 75.0, 100.0]
        points = compute_light_extraction_points(timestamps, chapters)

        assert len(points) == 4
        assert points[0].chapter_number == 0
        assert points[1].chapter_number == 0
        assert points[2].chapter_number == 1
        assert points[3].chapter_number == 1

    def test_deduplicates_timestamps(self):
        chapters = [
            ChapterInfo(number=0, title="Intro", start_time=0.0, end_time=60.0, density="normal"),
        ]
        timestamps = [10.0, 10.0, 10.0]
        points = compute_light_extraction_points(timestamps, chapters)
        assert len(points) == 1

    def test_skips_timestamps_outside_chapters(self):
        chapters = [
            ChapterInfo(number=0, title="Intro", start_time=10.0, end_time=20.0, density="normal"),
        ]
        timestamps = [5.0, 15.0, 25.0]
        # 5.0 and 25.0 are outside chapter bounds, but _chapter_for_timestamp
        # falls back to last chapter for timestamps past end
        points = compute_light_extraction_points(timestamps, chapters)
        assert any(p.timestamp == 15.0 for p in points)

    def test_empty_input(self):
        chapters = [
            ChapterInfo(number=0, title="Intro", start_time=0.0, end_time=60.0, density="normal"),
        ]
        points = compute_light_extraction_points([], chapters)
        assert points == []

    def test_no_chapters(self):
        points = compute_light_extraction_points([10.0, 20.0], [])
        assert points == []

    def test_preserves_chapter_density(self):
        chapters = [
            ChapterInfo(number=0, title="Dense", start_time=0.0, end_time=60.0, density="high"),
            ChapterInfo(number=1, title="Normal", start_time=60.0, end_time=120.0, density="normal"),
        ]
        timestamps = [10.0, 80.0]
        points = compute_light_extraction_points(timestamps, chapters)
        assert points[0].density == "high"
        assert points[1].density == "normal"
