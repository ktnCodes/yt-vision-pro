"""Manifest generation for yt-vision-pro."""
import re
from pathlib import Path


def _chunk_frames(frames: list[dict], max_per_chunk: int = 12) -> list[list[dict]]:
    if not frames:
        return []
    return [frames[i:i + max_per_chunk] for i in range(0, len(frames), max_per_chunk)]


def _render_chunked_frames(frames: list[dict], captions: list[dict], max_per_chunk: int = 12) -> list[str]:
    chunks = _chunk_frames(frames, max_per_chunk)
    total_chunks = len(chunks)
    lines: list[str] = []

    for chunk_idx, chunk in enumerate(chunks, start=1):
        lines.append(f"## Chunk {chunk_idx} of {total_chunks}")
        lines.append("")
        lines.append("### Instructions")
        lines.append("")
        lines.append("View each frame below. Describe what you see. Note any diagrams, code, or text on screen.")
        lines.append("")

        for frame in chunk:
            ts = frame["timestamp"]
            path = frame["path"]
            lines.append(f"### Frame {frame['frame_number']} @ {ts:.1f}s")
            lines.append("")
            lines.append(f"![frame]({path})")
            lines.append("")

            aligned = [
                c["text"] for c in captions
                if c["start"] <= ts + 3.0 and c["end"] >= ts - 3.0
            ]
            if aligned:
                lines.append("**Caption:** " + " ".join(aligned))
            else:
                lines.append("**Caption:** _none_")

            ocr_text = frame.get("ocr_text", "")
            if ocr_text:
                lines.append(f"**OCR:** {ocr_text}")

            lines.append("")

        lines.append("### Analysis")
        lines.append("")
        lines.append("_Agent fills this after viewing all frames in this chunk._")
        lines.append("")
        lines.append("---")
        lines.append("")

    return lines


def _append_common_frontmatter(
    lines: list[str],
    *,
    video_id: str,
    video_title: str,
    duration: float,
    frame_count: int,
    detector: str,
    ocr_applied: bool,
    caption_source: str,
    density: str,
    sensitivity: float,
    scene_sample_interval: float,
    slide_aware_dedup: bool,
    chapter_number: int | None = None,
    chapter_title: str | None = None,
    chapter_timerange: str | None = None,
):
    lines.append("---")
    lines.append(f"video_id: {video_id}")
    lines.append(f'video_title: "{video_title}"')
    lines.append(f"duration: {duration}")
    if chapter_number is not None:
        lines.append(f"chapter_number: {chapter_number}")
    if chapter_title is not None:
        lines.append(f'chapter_title: "{chapter_title}"')
    if chapter_timerange is not None:
        lines.append(f"chapter_timerange: {chapter_timerange}")
    lines.append(f"frame_count: {frame_count}")
    lines.append(f"density: {density}")
    lines.append(f"detector: {detector}")
    lines.append(f"sensitivity: {sensitivity}")
    lines.append(f"scene_sample_interval: {scene_sample_interval}")
    lines.append(f"slide_aware_dedup: {'true' if slide_aware_dedup else 'false'}")
    lines.append(f"ocr_applied: {'true' if ocr_applied else 'false'}")
    lines.append(f"caption_source: {caption_source}")
    lines.append("manifest_version: 3")
    lines.append("---")
    lines.append("")


def generate_manifest(
    video_id: str,
    title: str,
    duration: float,
    description: str,
    frames: list[dict],
    captions: list[dict],
    output_path: Path,
    detector: str = "content",
    density: str = "normal",
    sensitivity: float = 30.0,
    scene_sample_interval: float = 5.0,
    slide_aware_dedup: bool = True,
    ocr_applied: bool = False,
    caption_source: str = "youtube",
) -> Path:
    lines = []

    # Frontmatter
    _append_common_frontmatter(
        lines,
        video_id=video_id,
        video_title=title,
        duration=duration,
        frame_count=len(frames),
        detector=detector,
        ocr_applied=ocr_applied,
        caption_source=caption_source,
        density=density,
        sensitivity=sensitivity,
        scene_sample_interval=scene_sample_interval,
        slide_aware_dedup=slide_aware_dedup,
    )

    # Title
    lines.append(f"# Manifest: {title}")
    lines.append("")

    # Video context
    lines.append("## Video Context (verbatim from YouTube)")
    lines.append("")
    lines.append(description if description else "_No description available._")
    lines.append("")

    # Running summary slot
    lines.append("## Running Summary")
    lines.append("")
    lines.append("_Not yet processed._")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Frame sections — chunked
    lines.extend(_render_chunked_frames(frames, captions))

    # Final Synthesis
    lines.append("---")
    lines.append("")
    lines.append("## Final Synthesis")
    lines.append("")
    lines.append(f"**Target output path:** `output/{video_id}-research-note.md`")
    lines.append("")
    lines.append("### Output Frontmatter Template")
    lines.append("")
    lines.append("```yaml")
    lines.append("---")
    lines.append(f"video_id: {video_id}")
    lines.append(f'title: "{title}"')
    lines.append("type: yt-research-note")
    lines.append("created: YYYY-MM-DD")
    lines.append("tags: []")
    lines.append("---")
    lines.append("```")
    lines.append("")
    lines.append("### Instructions")
    lines.append("")
    lines.append("1. Review each chunk analysis above and synthesize into a coherent research note.")
    lines.append("2. Update the Running Summary with the final synthesis.")
    lines.append("3. Preserve all code blocks and Mermaid diagrams verbatim — do not paraphrase or summarize code.")
    lines.append("4. Preserve any diagrams exactly as they appear.")
    lines.append("5. Write the final research note to the target output path.")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s).strip("-")
    return s


def _render_frames_section(frames: list[dict], captions: list[dict]) -> list[str]:
    lines = []
    for frame in frames:
        ts = frame["timestamp"]
        path = frame["path"]
        lines.append(f"### Frame {frame['frame_number']} @ {ts:.1f}s")
        lines.append("")
        lines.append(f"![frame]({path})")
        lines.append("")

        aligned = [
            c["text"] for c in captions
            if c["start"] <= ts + 3.0 and c["end"] >= ts - 3.0
        ]
        if aligned:
            lines.append("**Caption:** " + " ".join(aligned))
        else:
            lines.append("**Caption:** _none_")

        ocr_text = frame.get("ocr_text", "")
        if ocr_text:
            lines.append(f"**OCR:** {ocr_text}")

        lines.append("")
    return lines


def generate_chapter_manifest(
    video_id: str,
    video_title: str,
    video_duration: float,
    description: str,
    chapter_number: int,
    chapter_title: str,
    chapter_timerange: str,
    frames: list[dict],
    captions: list[dict],
    output_dir: Path,
    detector: str = "content",
    ocr_applied: bool = False,
    caption_source: str = "youtube",
    density: str = "normal",
    sensitivity: float = 30.0,
    scene_sample_interval: float = 5.0,
    slide_aware_dedup: bool = True,
) -> Path:
    slug = _slugify(chapter_title)
    filename = f"manifest-{chapter_number:02d}-{slug}.md"
    output_path = output_dir / filename

    lines = []

    _append_common_frontmatter(
        lines,
        video_id=video_id,
        video_title=video_title,
        duration=video_duration,
        frame_count=len(frames),
        detector=detector,
        ocr_applied=ocr_applied,
        caption_source=caption_source,
        density=density,
        sensitivity=sensitivity,
        scene_sample_interval=scene_sample_interval,
        slide_aware_dedup=slide_aware_dedup,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        chapter_timerange=chapter_timerange,
    )

    lines.append(f"# Manifest: Chapter {chapter_number} — {chapter_title}")
    lines.append("")

    # Video context
    lines.append("## Video Context (verbatim from YouTube)")
    lines.append("")
    lines.append(description if description else "_No description available._")
    lines.append("")

    # Running summary slot
    lines.append("## Running Summary")
    lines.append("")
    lines.append("_Not yet processed._")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Frame sections — chunked
    lines.extend(_render_chunked_frames(frames, captions))

    # Final Synthesis
    lines.append("---")
    lines.append("")
    lines.append("## Final Synthesis")
    lines.append("")
    lines.append(f"**Target output path:** `output/{video_id}-ch{chapter_number:02d}-{slug}.md`")
    lines.append("")
    lines.append("### Output Frontmatter Template")
    lines.append("")
    lines.append("```yaml")
    lines.append("---")
    lines.append(f"video_id: {video_id}")
    lines.append(f'title: "{video_title} — {chapter_title}"')
    lines.append("type: yt-research-note")
    lines.append(f"chapter: {chapter_number}")
    lines.append("created: YYYY-MM-DD")
    lines.append("tags: []")
    lines.append("---")
    lines.append("```")
    lines.append("")
    lines.append("### Instructions")
    lines.append("")
    lines.append("1. Review each chunk analysis above and synthesize into a coherent research note.")
    lines.append("2. Update the Running Summary with the final synthesis.")
    lines.append("3. Preserve all code blocks and Mermaid diagrams verbatim — do not paraphrase or summarize code.")
    lines.append("4. Preserve any diagrams exactly as they appear.")
    lines.append("5. Write the final research note to the target output path.")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
