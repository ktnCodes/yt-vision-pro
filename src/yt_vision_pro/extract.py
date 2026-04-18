"""Scene detection + frame extraction for yt-vision-pro."""
from dataclasses import dataclass
import subprocess
from pathlib import Path

from scenedetect import AdaptiveDetector, ContentDetector, SceneManager, open_video

from yt_vision_pro.fetch import ChapterInfo
from yt_vision_pro.stages import DensityConfig


@dataclass(frozen=True)
class ExtractionPoint:
    timestamp: float
    chapter_number: int
    density: str
    scene_id: int


def detect_scenes(
    video_path: Path,
    detector: str = "content",
    sensitivity: float = 30.0,
) -> list[tuple[float, float]]:
    video = open_video(str(video_path))
    scene_manager = SceneManager()

    detector_name = detector.strip().lower()
    if detector_name == "adaptive":
        scene_manager.add_detector(AdaptiveDetector())
    elif detector_name == "content":
        scene_manager.add_detector(ContentDetector(threshold=sensitivity))
    else:
        raise ValueError(f"Unsupported detector '{detector}'.")

    scene_manager.detect_scenes(video)
    scenes = scene_manager.get_scene_list()
    return [
        (start.get_seconds(), end.get_seconds())
        for start, end in scenes
    ]


def _chapter_for_timestamp(chapters: list[ChapterInfo], timestamp: float) -> ChapterInfo | None:
    if not chapters:
        return None

    for chapter in chapters:
        if chapter.start_time <= timestamp < chapter.end_time:
            return chapter

    return chapters[-1]


def compute_light_extraction_points(
    timestamps: list[float],
    chapters: list[ChapterInfo],
) -> list[ExtractionPoint]:
    """Map pre-selected timestamps into ExtractionPoint objects.

    Used by the light (transcript-guided + chapter-fill) pipeline.
    No scene detection needed — timestamps come from transcript cues
    and chapter sampling.
    """
    points: list[ExtractionPoint] = []
    seen: set[float] = set()

    for ts in sorted(timestamps):
        rounded = round(ts, 3)
        if rounded in seen:
            continue
        chapter = _chapter_for_timestamp(chapters, ts)
        if chapter is None:
            continue
        points.append(ExtractionPoint(
            timestamp=ts,
            chapter_number=chapter.number,
            density=chapter.density,
            scene_id=0,
        ))
        seen.add(rounded)

    return points


def compute_extraction_points(
    scenes: list[tuple[float, float]],
    chapters: list[ChapterInfo],
    density_profiles: dict[str, DensityConfig],
    fallback_interval: float = 30.0,
) -> list[ExtractionPoint]:
    if not chapters:
        return []

    points: list[ExtractionPoint] = []
    seen_timestamps: set[float] = set()

    def append_point(timestamp: float, scene_id: int):
        rounded_timestamp = round(timestamp, 3)
        if rounded_timestamp in seen_timestamps:
            return

        chapter = _chapter_for_timestamp(chapters, timestamp)
        if chapter is None:
            return

        points.append(
            ExtractionPoint(
                timestamp=timestamp,
                chapter_number=chapter.number,
                density=chapter.density,
                scene_id=scene_id,
            )
        )
        seen_timestamps.add(rounded_timestamp)

    if not scenes:
        duration = chapters[-1].end_time
        scene_id = 0
        current_time = 0.0
        while current_time < duration:
            append_point(current_time, scene_id)
            current_time += fallback_interval
            scene_id += 1
        return points

    for scene_id, (start, end) in enumerate(scenes):
        append_point(start, scene_id)

        sample_time = start
        while True:
            chapter = _chapter_for_timestamp(chapters, sample_time)
            if chapter is None:
                break

            interval = density_profiles[chapter.density].scene_sample_interval
            if interval <= 0:
                break

            sample_time += interval
            if sample_time >= end:
                break

            append_point(sample_time, scene_id)

    points.sort(key=lambda point: point.timestamp)
    return points


def extract_frames(
    video_path: Path, timestamps: list[float], output_dir: Path
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for ts in timestamps:
        frame_path = output_dir / f"frame_{ts:08.2f}.jpg"
        if not frame_path.exists():
            subprocess.run(
                [
                    "ffmpeg",
                    "-ss", str(ts),
                    "-i", str(video_path),
                    "-frames:v", "1",
                    "-q:v", "2",
                    "-y",
                    str(frame_path),
                ],
                check=True,
                capture_output=True,
            )
        paths.append(frame_path)

    return paths
