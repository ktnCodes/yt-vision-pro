"""yt-dlp download wrapper for yt-vision-pro."""
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


VIDEO_SUFFIXES = (".mp4", ".webm", ".mkv")
MIN_DURATION_TOLERANCE_SECONDS = 30.0
MIN_DURATION_TOLERANCE_RATIO = 0.05


@dataclass
class ChapterInfo:
    number: int
    title: str
    start_time: float
    end_time: float
    is_synthetic: bool = False
    density: str = "normal"

    @property
    def slug(self) -> str:
        s = self.title.lower()
        s = re.sub(r"[^a-z0-9\s-]", "", s)
        s = re.sub(r"[\s]+", "-", s).strip("-")
        return s



def generate_synthetic_chapters(duration: float, max_chapter_length: float = 600.0) -> list[ChapterInfo]:
    """Create evenly-spaced synthetic chapters when a video has none."""
    if duration <= 0:
        return [ChapterInfo(number=0, title="Full Video", start_time=0.0, end_time=0.0, is_synthetic=True)]

    n_chapters = max(1, int(duration / max_chapter_length))
    chapter_length = duration / n_chapters
    chapters: list[ChapterInfo] = []
    for i in range(n_chapters):
        start = i * chapter_length
        end = min((i + 1) * chapter_length, duration)
        chapters.append(
            ChapterInfo(
                number=i,
                title=f"Part {i + 1}",
                start_time=start,
                end_time=end,
                is_synthetic=True,
            )
        )
    return chapters

@dataclass
class VideoInfo:
    video_id: str
    title: str
    duration: float
    url: str
    description: str = ""
    video_path: Path | None = None
    captions_path: Path | None = None
    info_json_path: Path | None = None
    chapters: list[ChapterInfo] = field(default_factory=list)


def parse_video_info(info_json_path: Path) -> VideoInfo:
    data = json.loads(info_json_path.read_text(encoding="utf-8"))
    return VideoInfo(
        video_id=data["id"],
        title=data["title"],
        duration=data["duration"],
        url=data["webpage_url"],
        description=data.get("description", ""),
        info_json_path=info_json_path,
        chapters=parse_chapters(info_json_path),
    )


def parse_chapters(info_json_path: Path) -> list[ChapterInfo]:
    data = json.loads(info_json_path.read_text(encoding="utf-8"))
    raw_chapters = data.get("chapters") or []
    return [
        ChapterInfo(
            number=i,
            title=ch["title"],
            start_time=ch["start_time"],
            end_time=ch["end_time"],
        )
        for i, ch in enumerate(raw_chapters)
    ]


def fetch_video(url: str, cache_dir: Path) -> VideoInfo:
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(cache_dir / "source.%(ext)s")

    # If ffmpeg is available, merge video+audio. Otherwise download best single format.
    has_ffmpeg = shutil.which("ffmpeg") is not None
    if has_ffmpeg:
        fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
    else:
        fmt = "best[height<=720][ext=mp4]/best[ext=mp4]/best"

    subprocess.run(
        [
            "yt-dlp",
            "--format", fmt,
            "--write-info-json",
            "--write-subs",
            "--write-auto-subs",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--output", output_template,
            "--no-playlist",
            url,
        ],
        check=True,
    )

    info_json_path = next(cache_dir.glob("source.info.json"), None)
    if info_json_path is None:
        raise FileNotFoundError(f"yt-dlp did not write info.json to {cache_dir}")

    info = parse_video_info(info_json_path)

    # Find the video file — may be source.mp4, source.f398.mp4, source.webm, etc.
    video_files = [f for f in cache_dir.glob("source.*") if f.suffix in (".mp4", ".webm", ".mkv")]
    info.video_path = video_files[0] if video_files else None

    vtt_files = list(cache_dir.glob("*.vtt"))
    info.captions_path = vtt_files[0] if vtt_files else None

    return info
