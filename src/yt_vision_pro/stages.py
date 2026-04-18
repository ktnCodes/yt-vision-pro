"""Pipeline stage sentinels and density helpers for yt-vision-pro."""
from dataclasses import dataclass, replace
from pathlib import Path

from yt_vision_pro.fetch import ChapterInfo

STAGES = ["fetch", "extract", "ocr", "dedup-with-ocr-context", "align", "manifest"]


@dataclass(frozen=True)
class DensityConfig:
    name: str
    scene_sample_interval: float
    dedup_hamming_threshold: int
    slide_dedup_hamming_threshold: int


DEFAULT_DENSITY_PROFILES = {
    "high": DensityConfig(
        name="high",
        scene_sample_interval=3.0,
        dedup_hamming_threshold=3,
        slide_dedup_hamming_threshold=1,
    ),
    "normal": DensityConfig(
        name="normal",
        scene_sample_interval=5.0,
        dedup_hamming_threshold=5,
        slide_dedup_hamming_threshold=3,
    ),
    "low": DensityConfig(
        name="low",
        scene_sample_interval=15.0,
        dedup_hamming_threshold=8,
        slide_dedup_hamming_threshold=6,
    ),
}


def normalize_density(value: str) -> str:
    density = value.strip().lower()
    if density not in DEFAULT_DENSITY_PROFILES:
        raise ValueError(f"Unsupported density '{value}'. Expected one of: high, normal, low.")
    return density


def parse_dense_chapters(spec: str) -> set[int]:
    if not spec.strip():
        return set()

    chapter_numbers: set[int] = set()
    for token in spec.split(","):
        value = token.strip()
        if not value:
            continue
        try:
            chapter_number = int(value)
        except ValueError as exc:
            raise ValueError(f"Invalid chapter index '{value}' in --dense-chapters.") from exc
        if chapter_number < 0:
            raise ValueError("Chapter indices in --dense-chapters must be zero or greater.")
        chapter_numbers.add(chapter_number)
    return chapter_numbers


def parse_timestamp(value: str | None) -> float | None:
    if value is None:
        return None

    token = value.strip()
    if not token:
        return None

    parts = token.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp '{value}'. Expected SS, MM:SS, or HH:MM:SS.") from exc

    raise ValueError(f"Invalid timestamp '{value}'. Expected SS, MM:SS, or HH:MM:SS.")


def build_density_profiles(
    default_density: str,
    default_scene_sample_interval: float,
) -> dict[str, DensityConfig]:
    density = normalize_density(default_density)
    profiles = {
        name: replace(config)
        for name, config in DEFAULT_DENSITY_PROFILES.items()
    }
    profiles[density] = replace(
        profiles[density],
        scene_sample_interval=max(0.0, default_scene_sample_interval),
    )
    return profiles


def resolve_chapter_densities(
    chapters: list[ChapterInfo],
    default_density: str,
    dense_chapters: str = "",
    dense_until: str | None = None,
    default_scene_sample_interval: float = 5.0,
) -> tuple[list[ChapterInfo], dict[str, DensityConfig]]:
    density = normalize_density(default_density)
    dense_chapter_numbers = parse_dense_chapters(dense_chapters)
    dense_until_seconds = parse_timestamp(dense_until)
    profiles = build_density_profiles(density, default_scene_sample_interval)

    resolved: list[ChapterInfo] = []
    for chapter in chapters:
        chapter_density = density
        if chapter.number in dense_chapter_numbers:
            chapter_density = "high"
        elif dense_until_seconds is not None and chapter.start_time < dense_until_seconds:
            chapter_density = "high"

        resolved.append(replace(chapter, density=chapter_density))

    return resolved, profiles


def _sentinel_path(cache_dir: Path, stage: str) -> Path:
    return cache_dir / ".stages" / f"{stage}.done"


def is_stage_done(cache_dir: Path, stage: str) -> bool:
    return _sentinel_path(cache_dir, stage).exists()


def mark_stage_done(cache_dir: Path, stage: str):
    sentinel = _sentinel_path(cache_dir, stage)
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.touch()


def clear_all_stages(cache_dir: Path):
    stages_dir = cache_dir / ".stages"
    if stages_dir.exists():
        for f in stages_dir.iterdir():
            f.unlink()


def clear_from_stage(cache_dir: Path, stage: str):
    idx = STAGES.index(stage)
    for s in STAGES[idx:]:
        sentinel = _sentinel_path(cache_dir, s)
        if sentinel.exists():
            sentinel.unlink()
