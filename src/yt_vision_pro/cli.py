"""CLI entry point for yt-vision-pro."""
from collections import defaultdict
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from yt_vision_pro.align import detect_caption_source, parse_captions
from yt_vision_pro.db import Database
from yt_vision_pro.extract import compute_extraction_points, compute_light_extraction_points, detect_scenes, extract_frames
from yt_vision_pro.fetch import ChapterInfo, fetch_video, generate_synthetic_chapters, parse_video_info
from yt_vision_pro.filters import deduplicate_frames, is_black_frame, is_blurry, is_slide_like
from yt_vision_pro.manifest import generate_chapter_manifest, generate_manifest
from yt_vision_pro.ocr import extract_ocr_result
from yt_vision_pro.stages import (
    STAGES,
    clear_all_stages,
    clear_from_stage,
    is_stage_done,
    mark_stage_done,
    resolve_chapter_densities,
)
from yt_vision_pro.transcript_cues import chapter_fill_timestamps, compute_cue_timestamps
from yt_vision_pro.whisper import is_whisper_available, transcribe_audio

app = typer.Typer(name="yt-vision-pro", help="YouTube visual analysis pipeline.")
console = Console()
def _clear_matching_files(directory: Path, pattern: str):
    if not directory.exists():
        return
    for path in directory.glob(pattern):
        if path.is_file():
            path.unlink()




def _load_video_info_from_cache(cache_dir: Path):
    info_json = next(cache_dir.glob("source.info.json"))
    video_info = parse_video_info(info_json)
    video_files = [f for f in cache_dir.glob("source.*") if f.suffix in (".mp4", ".webm", ".mkv")]
    video_info.video_path = video_files[0] if video_files else None
    vtt_files = list(cache_dir.glob("*.vtt"))
    video_info.captions_path = vtt_files[0] if vtt_files else None
    return video_info


def _validate_detector(detector: str) -> str:
    detector_name = detector.strip().lower()
    if detector_name not in {"adaptive", "content"}:
        raise typer.BadParameter("--detector must be 'adaptive' or 'content'.")
    return detector_name


def _chapter_map(chapters: list[ChapterInfo]) -> dict[int, ChapterInfo]:
    return {chapter.number: chapter for chapter in chapters}


def _load_frame_records(
    db: Database,
    chapter_rows: list[dict],
    chapters_by_number: dict[int, ChapterInfo],
    kept_only: bool | None,
) -> dict[int, list[dict]]:
    records: dict[int, list[dict]] = defaultdict(list)
    for chapter_row in chapter_rows:
        chapter_number = chapter_row["chapter_number"]
        chapter = chapters_by_number.get(chapter_number)
        density = chapter.density if chapter else "normal"
        frames = db.get_frames_by_chapter(chapter_row["id"], kept_only=kept_only)
        for frame in frames:
            records[chapter_number].append(
                {
                    "id": frame["id"],
                    "frame_number": frame["frame_number"],
                    "timestamp": frame["timestamp"],
                    "path": frame["path"],
                    "ocr_text": frame.get("ocr_text", "") or "",
                    "density": density,
                    "is_kept": bool(frame.get("is_kept", 1)),
                }
            )

    for chapter_number in chapters_by_number:
        records.setdefault(chapter_number, [])

    return dict(records)


@app.command()
def process(
    url: str = typer.Argument(..., help="YouTube video URL to process."),
    cache_dir: Path = typer.Option(
        Path("cache"), help="Directory for cached downloads and frames."
    ),
    force: bool = typer.Option(False, "--force", help="Clear all sentinels and re-run from scratch."),
    from_stage: Optional[str] = typer.Option(
        None,
        "--from-stage",
        help="Re-run from this stage onward (fetch, extract, ocr, dedup-with-ocr-context, align, manifest).",
    ),
    thorough: bool = typer.Option(
        False, "--thorough", help="Use heavy pipeline: full scene detection, dense extraction, and pHash dedup."
    ),
    max_frames: int = typer.Option(200, "--max-frames", help="Maximum frames to extract in light mode."),
    no_ocr: bool = typer.Option(False, "--no-ocr", help="Skip OCR on extracted frames."),
    no_filter: bool = typer.Option(False, "--no-filter", help="Skip quality filters and dedup."),
    max_frames_per_chunk: int = typer.Option(12, "--max-frames-per-chunk", help="Max frames per manifest chunk."),
    detector: str = typer.Option("content", "--detector", help="Scene detector to use: content or adaptive."),
    sensitivity: float = typer.Option(30.0, "--sensitivity", help="Content detector threshold."),
    scene_sample_interval: float = typer.Option(5.0, "--scene-sample-interval", help="Default within-scene sampling interval in seconds. Set 0 to disable within-scene sampling for the default density tier."),
    density: str = typer.Option("normal", "--density", help="Default chapter density: high, normal, or low."),
    dense_chapters: str = typer.Option("", "--dense-chapters", help="Comma-separated chapter indices to upgrade to high density."),
    dense_until: str = typer.Option("", "--dense-until", help="Upgrade chapters starting before this timestamp to high density."),
):
    """Download a video, extract frames, and generate chapter-aware manifests."""
    detector_name = _validate_detector(detector)
    if scene_sample_interval < 0:
        raise typer.BadParameter("--scene-sample-interval must be zero or greater.")
    if from_stage and from_stage not in STAGES:
        raise typer.BadParameter(f"--from-stage must be one of: {', '.join(STAGES)}")

    if force:
        clear_all_stages(cache_dir)
    elif from_stage:
        clear_from_stage(cache_dir, from_stage)

    if not is_stage_done(cache_dir, "fetch"):
        console.print(f"[bold]Fetching video:[/bold] {url}")
        video_info = fetch_video(url, cache_dir)
        console.print(f"[green]Downloaded:[/green] {video_info.title} ({video_info.duration:.0f}s)")
        mark_stage_done(cache_dir, "fetch")
    else:
        console.print("[dim]fetch: skipped (already done)[/dim]")
        video_info = _load_video_info_from_cache(cache_dir)

    if video_info.video_path is None:
        raise typer.BadParameter(f"No downloaded video file found in {cache_dir}.")

    chapters = video_info.chapters
    if not chapters:
        console.print("[yellow]No chapters found — generating synthetic chapters.[/yellow]")
        chapters = generate_synthetic_chapters(video_info.duration)

    try:
        chapters, density_profiles = resolve_chapter_densities(
            chapters,
            default_density=density,
            dense_chapters=dense_chapters,
            dense_until=dense_until,
            default_scene_sample_interval=scene_sample_interval,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    chapters_by_number = _chapter_map(chapters)

    db_path = cache_dir / "pipeline.db"
    with Database(db_path) as db:
        db.create_tables()
        db.insert_video(
            video_id=video_info.video_id,
            title=video_info.title,
            duration=video_info.duration,
            url=video_info.url,
        )

        if not is_stage_done(cache_dir, "extract"):
            db.delete_frames(video_info.video_id)
            db.delete_chapters(video_info.video_id)

        db_chapters = db.get_chapters(video_info.video_id)
        if not db_chapters:
            for chapter in chapters:
                db.insert_chapter(
                    video_id=video_info.video_id,
                    chapter_number=chapter.number,
                    title=chapter.title,
                    start_time=chapter.start_time,
                    end_time=chapter.end_time,
                    is_synthetic=chapter.is_synthetic,
                )
            db_chapters = db.get_chapters(video_info.video_id)

        chapter_rows_by_number = {chapter_row["chapter_number"]: chapter_row for chapter_row in db_chapters}
        frames_dir = cache_dir / "frames"
        all_frame_records: dict[int, list[dict]] = {chapter.number: [] for chapter in chapters}
        pipeline_mode = "thorough" if thorough else "light"

        if not is_stage_done(cache_dir, "extract"):
            console.print(f"[bold]Pipeline mode: {pipeline_mode}[/bold]")
            _clear_matching_files(frames_dir, "*.jpg")

            if thorough:
                # --- Thorough mode: full scene detection + dense extraction ---
                console.print(f"[bold]Detecting scenes with {detector_name} detector...[/bold]")
                scenes = detect_scenes(video_info.video_path, detector=detector_name, sensitivity=sensitivity)
                if scenes:
                    console.print(f"[green]Found {len(scenes)} scene windows[/green]")
                else:
                    console.print("[yellow]No scenes detected — falling back to regular interval sampling.[/yellow]")

                extraction_points = compute_extraction_points(scenes, chapters, density_profiles)
                if not extraction_points:
                    extraction_points = compute_extraction_points([], chapters, density_profiles)
            else:
                # --- Light mode: transcript-guided + chapter fill ---
                transcript_segments = []
                if video_info.captions_path and video_info.captions_path.exists():
                    transcript_segments = parse_captions(video_info.captions_path)

                if transcript_segments:
                    cue_timestamps = compute_cue_timestamps(
                        transcript_segments,
                        tiers=(1, 2, 3),
                        dedup_window=15.0,
                    )
                    console.print(f"[green]Found {len(cue_timestamps)} transcript-guided cue points[/green]")
                else:
                    cue_timestamps = []
                    console.print("[yellow]No captions available — using chapter sampling only.[/yellow]")

                chapter_dicts = [
                    {"start_time": ch.start_time, "end_time": ch.end_time}
                    for ch in chapters
                ]
                all_timestamps = chapter_fill_timestamps(
                    chapter_dicts,
                    cue_timestamps,
                    max_total=max_frames,
                )
                console.print(
                    f"[green]Planned {len(all_timestamps)} extraction points "
                    f"({len(cue_timestamps)} cue + {len(all_timestamps) - len(cue_timestamps)} chapter fill)[/green]"
                )

                extraction_points = compute_light_extraction_points(all_timestamps, chapters)

            timestamps = [point.timestamp for point in extraction_points]
            console.print(f"[green]Total: {len(extraction_points)} extraction points[/green]")

            console.print("[bold]Extracting frames...[/bold]")
            frame_paths = extract_frames(video_info.video_path, timestamps, frames_dir)
            console.print(f"[green]Extracted {len(frame_paths)} raw frames[/green]")

            for frame_number, (point, frame_path) in enumerate(zip(extraction_points, frame_paths)):
                chapter_row = chapter_rows_by_number.get(point.chapter_number)
                frame_id = db.insert_frame(
                    video_id=video_info.video_id,
                    frame_number=frame_number,
                    timestamp=point.timestamp,
                    path=str(frame_path.relative_to(cache_dir)),
                    chapter_id=chapter_row["id"] if chapter_row else None,
                )
                all_frame_records.setdefault(point.chapter_number, []).append(
                    {
                        "id": frame_id,
                        "frame_number": frame_number,
                        "timestamp": point.timestamp,
                        "path": str(frame_path.relative_to(cache_dir)),
                        "ocr_text": "",
                        "density": point.density,
                    }
                )

            mark_stage_done(cache_dir, "extract")
        else:
            console.print("[dim]extract: skipped (already done)[/dim]")
            all_frame_records = _load_frame_records(db, db_chapters, chapters_by_number, kept_only=None)

        if not no_ocr and not is_stage_done(cache_dir, "ocr"):
            console.print("[bold]Running OCR on frames...[/bold]")
            ocr_count = 0
            for frames in all_frame_records.values():
                for frame in frames:
                    frame_path = cache_dir / frame["path"]
                    if not frame_path.exists():
                        continue
                    ocr_result = extract_ocr_result(frame_path)
                    frame["ocr_text"] = str(ocr_result["text"])
                    db.update_frame_ocr(frame["id"], frame["ocr_text"])
                    ocr_count += 1
            console.print(f"[green]OCR completed on {ocr_count} frames[/green]")
            mark_stage_done(cache_dir, "ocr")
        elif no_ocr:
            console.print("[dim]ocr: skipped (--no-ocr)[/dim]")
        else:
            console.print("[dim]ocr: skipped (already done)[/dim]")
            all_frame_records = _load_frame_records(db, db_chapters, chapters_by_number, kept_only=None)

        if no_filter or not thorough:
            if not thorough:
                console.print("[dim]dedup-with-ocr-context: skipped (light mode — sparse sampling)[/dim]")
            else:
                console.print("[dim]dedup-with-ocr-context: skipped (--no-filter)[/dim]")
            db.reset_frame_keep_status(video_info.video_id, True)
            if not is_stage_done(cache_dir, "dedup-with-ocr-context"):
                mark_stage_done(cache_dir, "dedup-with-ocr-context")
            all_frame_records = _load_frame_records(db, db_chapters, chapters_by_number, kept_only=None)
        elif not is_stage_done(cache_dir, "dedup-with-ocr-context"):
            console.print("[bold]Filtering and deduplicating frames with OCR context...[/bold]")
            db.reset_frame_keep_status(video_info.video_id, False)
            kept_total = 0
            removed_for_quality = 0
            removed_for_dedup = 0

            for chapter in chapters:
                chapter_frames = sorted(
                    all_frame_records.get(chapter.number, []),
                    key=lambda frame: frame["timestamp"],
                )
                if not chapter_frames:
                    continue

                quality_frames: list[dict] = []
                for frame in chapter_frames:
                    frame_path = cache_dir / frame["path"]
                    if is_black_frame(frame_path) or is_blurry(frame_path):
                        removed_for_quality += 1
                        continue
                    quality_frames.append(frame)

                if not quality_frames:
                    continue

                profile = density_profiles[chapter.density]
                frame_paths = [cache_dir / frame["path"] for frame in quality_frames]
                ocr_lookup = {str(cache_dir / frame["path"]): frame.get("ocr_text", "") for frame in quality_frames}
                slide_like_paths = {
                    str(cache_dir / frame["path"])
                    for frame in quality_frames
                    if is_slide_like(cache_dir / frame["path"], frame.get("ocr_text", ""))
                }

                kept_paths, removed_paths = deduplicate_frames(
                    frame_paths,
                    hamming_threshold=profile.dedup_hamming_threshold,
                    slide_hamming_threshold=profile.slide_dedup_hamming_threshold,
                    ocr_results=ocr_lookup,
                    slide_like_paths=slide_like_paths,
                )

                kept_path_strings = {str(path) for path in kept_paths}
                kept_ids = [
                    frame["id"]
                    for frame in quality_frames
                    if str(cache_dir / frame["path"]) in kept_path_strings
                ]
                db.set_frame_keep_status(kept_ids, True)
                kept_total += len(kept_ids)
                removed_for_dedup += len(removed_paths)

            console.print(
                f"[green]Kept {kept_total} frames after quality filtering and slide-aware dedup "
                f"({removed_for_quality} removed for quality, {removed_for_dedup} removed as near-duplicates)[/green]"
            )
            mark_stage_done(cache_dir, "dedup-with-ocr-context")
            all_frame_records = _load_frame_records(db, db_chapters, chapters_by_number, kept_only=True)
        else:
            console.print("[dim]dedup-with-ocr-context: skipped (already done)[/dim]")
            all_frame_records = _load_frame_records(db, db_chapters, chapters_by_number, kept_only=True)

        caption_source = "none"
        captions = []
        if not is_stage_done(cache_dir, "align"):
            if video_info.captions_path and video_info.captions_path.exists():
                console.print("[bold]Parsing captions...[/bold]")
                captions = parse_captions(video_info.captions_path)
                caption_source = detect_caption_source(video_info.captions_path)
                console.print(f"[green]Parsed {len(captions)} caption segments ({caption_source})[/green]")
            elif is_whisper_available():
                console.print("[bold]No captions found — running whisper transcription...[/bold]")
                whisper_vtt = cache_dir / "whisper.vtt"
                transcribe_audio(video_info.video_path, whisper_vtt)
                captions = parse_captions(whisper_vtt)
                caption_source = "whisper"
                console.print(f"[green]Whisper transcribed {len(captions)} segments[/green]")
            else:
                console.print("[yellow]No captions and whisper not available — frames-only manifest.[/yellow]")
            mark_stage_done(cache_dir, "align")
        else:
            console.print("[dim]align: skipped (already done)[/dim]")
            if video_info.captions_path and video_info.captions_path.exists():
                captions = parse_captions(video_info.captions_path)
                caption_source = detect_caption_source(video_info.captions_path)
            whisper_vtt = cache_dir / "whisper.vtt"
            if whisper_vtt.exists():
                captions = parse_captions(whisper_vtt)
                caption_source = "whisper"

        if not is_stage_done(cache_dir, "manifest"):
            ocr_applied = not no_ocr
            manifests_dir = cache_dir / "manifests"

            if len(chapters) > 1:
                console.print(f"[bold]Generating {len(chapters)} chapter manifests...[/bold]")
                for chapter in chapters:
                    chapter_frames = all_frame_records.get(chapter.number, [])
                    generate_chapter_manifest(
                        video_id=video_info.video_id,
                        video_title=video_info.title,
                        video_duration=video_info.duration,
                        description=video_info.description,
                        chapter_number=chapter.number,
                        chapter_title=chapter.title,
                        chapter_timerange=f"{chapter.start_time}-{chapter.end_time}",
                        frames=chapter_frames,
                        captions=captions,
                        output_dir=manifests_dir,
                        detector=detector_name,
                        ocr_applied=ocr_applied,
                        caption_source=caption_source,
                        density=chapter.density,
                        sensitivity=sensitivity,
                        scene_sample_interval=density_profiles[chapter.density].scene_sample_interval,
                        slide_aware_dedup=not no_filter,
                    )
                console.print(f"[green]Chapter manifests written to: {manifests_dir}[/green]")
            else:
                all_frames = []
                for frames in all_frame_records.values():
                    all_frames.extend(frames)
                all_frames.sort(key=lambda frame: frame["timestamp"])
                manifest_density = chapters[0].density if chapters else density
                manifest_path = cache_dir / "manifest.md"
                generate_manifest(
                    video_id=video_info.video_id,
                    title=video_info.title,
                    duration=video_info.duration,
                    description=video_info.description,
                    frames=all_frames,
                    captions=captions,
                    output_path=manifest_path,
                    detector=detector_name,
                    ocr_applied=ocr_applied,
                    caption_source=caption_source,
                    density=manifest_density,
                    sensitivity=sensitivity,
                    scene_sample_interval=density_profiles[manifest_density].scene_sample_interval,
                    slide_aware_dedup=not no_filter,
                )
                console.print(f"[green]Manifest written to: {manifest_path}[/green]")

            mark_stage_done(cache_dir, "manifest")
        else:
            console.print("[dim]manifest: skipped (already done)[/dim]")

    console.print("\n[bold green]Done![/bold green]")
    console.print("[dim]Feed the manifest(s) to Copilot Chat or Claude Code for synthesis.[/dim]")
