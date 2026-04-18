"""Transcript-guided frame extraction cues for yt-vision-pro.

Scans transcript segments for visual reference phrases and returns
deduplicated timestamps where the speaker is pointing at something
on screen.  Used by the light (default) pipeline mode.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class VisualCue:
    """A moment in the transcript where the speaker references something visual."""
    timestamp: float
    tier: int          # 1 = explicit visual, 2 = demo/screen, 3 = data/structure
    phrase: str        # the cue phrase that matched
    context: str       # surrounding transcript text


# Tier 1: Explicit visual references — high confidence
_TIER1_PHRASES = [
    "as you can see",
    "look at this",
    "this slide",
    "this diagram",
    "this chart",
    "on screen",
    "let me show",
    "here's the",
    "here is the",
    "take a look",
    "this image",
    "this screenshot",
    "this example",
    "watch this",
    "right here",
    "this is what",
    "you'll see",
    "you can see",
    "shown here",
    "displayed here",
    "see this",
    "see here",
    "notice this",
    "notice how",
    "look here",
    "check this out",
    "here we have",
    "here you can see",
    "on the screen",
    "what you see",
    "what we see",
]

# Tier 2: Demo/screen-share cues — medium confidence
_TIER2_PHRASES = [
    "let me pull up",
    "if i open",
    "switching to",
    "let me share",
    "i'll demonstrate",
    "here's my",
    "in this file",
    "this folder",
    "this window",
    "the ui shows",
    "this interface",
    "this is my",
    "let me go to",
    "open this up",
    "let me navigate",
    "let me click",
    "the screen shows",
    "i'm going to show",
    "what it looks like",
    "looks like this",
]

# Tier 3: Data/structure references — lower confidence, still valuable
_TIER3_PHRASES = [
    "the numbers show",
    "these results",
    "this benchmark",
    "the data",
    "this framework",
    "this architecture",
    "this workflow",
    "this structure",
    "step one",
    "step two",
    "step three",
    "the process",
    "this table",
    "this graph",
    "this model",
    "these metrics",
    "the comparison",
    "this layout",
    "this design",
    "this pattern",
]


def _build_tier_pattern(phrases: list[str]) -> re.Pattern:
    """Build a compiled regex that matches any of the phrases."""
    escaped = [re.escape(p) for p in phrases]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")", re.IGNORECASE)


_TIER_PATTERNS: list[tuple[int, re.Pattern]] = [
    (1, _build_tier_pattern(_TIER1_PHRASES)),
    (2, _build_tier_pattern(_TIER2_PHRASES)),
    (3, _build_tier_pattern(_TIER3_PHRASES)),
]


def find_visual_cues(
    segments: list[dict],
    tiers: tuple[int, ...] = (1, 2, 3),
) -> list[VisualCue]:
    """Scan transcript segments for visual reference phrases.

    Args:
        segments: List of dicts with 'text', 'start', and optionally 'duration'.
        tiers: Which tiers to include (1=explicit, 2=demo, 3=data).

    Returns:
        Sorted list of VisualCue objects by timestamp.
    """
    cues: list[VisualCue] = []
    for seg in segments:
        text = seg.get("text", "")
        start = seg.get("start", 0.0)

        for tier, pattern in _TIER_PATTERNS:
            if tier not in tiers:
                continue
            match = pattern.search(text)
            if match:
                cues.append(VisualCue(
                    timestamp=start,
                    tier=tier,
                    phrase=match.group(0).lower(),
                    context=text.strip(),
                ))
                break  # one cue per segment, highest tier wins

    cues.sort(key=lambda c: c.timestamp)
    return cues


def deduplicate_cues(
    cues: list[VisualCue],
    window: float = 15.0,
) -> list[VisualCue]:
    """Merge cues within a time window, keeping the highest-tier (lowest number) cue.

    Args:
        cues: Sorted list of VisualCue objects.
        window: Seconds within which cues are considered duplicates.

    Returns:
        Deduplicated list of cues.
    """
    if not cues:
        return []

    result: list[VisualCue] = []
    group: list[VisualCue] = [cues[0]]

    for cue in cues[1:]:
        if cue.timestamp - group[0].timestamp <= window:
            group.append(cue)
        else:
            # Keep the highest-tier (lowest number) cue from the group
            best = min(group, key=lambda c: (c.tier, c.timestamp))
            result.append(best)
            group = [cue]

    # Flush final group
    best = min(group, key=lambda c: (c.tier, c.timestamp))
    result.append(best)

    return result


def compute_cue_timestamps(
    segments: list[dict],
    tiers: tuple[int, ...] = (1, 2, 3),
    dedup_window: float = 15.0,
) -> list[float]:
    """End-to-end: scan segments, find cues, deduplicate, return timestamps.

    Args:
        segments: Transcript segments with 'text' and 'start' keys.
        tiers: Which tiers to scan for.
        dedup_window: Seconds within which cues are merged.

    Returns:
        Sorted list of unique timestamps where visual content is referenced.
    """
    cues = find_visual_cues(segments, tiers=tiers)
    deduped = deduplicate_cues(cues, window=dedup_window)
    return [cue.timestamp for cue in deduped]


def chapter_fill_timestamps(
    chapters: list[dict],
    existing_timestamps: list[float],
    max_total: int = 200,
    samples_per_chapter: int = 3,
) -> list[float]:
    """Fill remaining frame budget with evenly spaced chapter samples.

    Distributes frames across chapters that don't already have enough
    coverage from transcript-guided cues.

    Args:
        chapters: List of dicts with 'start_time' and 'end_time'.
        existing_timestamps: Already-selected cue timestamps.
        max_total: Maximum total frames (cue + fill combined).
        samples_per_chapter: Default samples to place in each chapter.

    Returns:
        Combined sorted list of all timestamps (cue + fill).
    """
    budget = max_total - len(existing_timestamps)
    if budget <= 0:
        return sorted(existing_timestamps)

    existing_set = set(round(t, 1) for t in existing_timestamps)

    # Count existing coverage per chapter
    chapter_coverage: dict[int, int] = {}
    for i, chapter in enumerate(chapters):
        start = chapter["start_time"]
        end = chapter["end_time"]
        count = sum(1 for t in existing_timestamps if start <= t < end)
        chapter_coverage[i] = count

    # Chapters needing fill: those with fewer than samples_per_chapter
    fill_candidates: list[tuple[int, dict]] = []
    for i, chapter in enumerate(chapters):
        needed = max(0, samples_per_chapter - chapter_coverage[i])
        if needed > 0:
            fill_candidates.append((i, chapter))

    if not fill_candidates:
        return sorted(existing_timestamps)

    # Distribute budget evenly across candidates, respecting per-chapter max
    per_chapter_budget = max(1, budget // len(fill_candidates))

    fill_timestamps: list[float] = []
    for _, chapter in fill_candidates:
        start = chapter["start_time"]
        end = chapter["end_time"]
        duration = end - start
        if duration <= 0:
            continue

        already_have = sum(1 for t in existing_timestamps if start <= t < end)
        needed = min(samples_per_chapter - already_have, per_chapter_budget)
        if needed <= 0:
            continue

        # Evenly space within chapter, offset from edges
        interval = duration / (needed + 1)
        for j in range(1, needed + 1):
            ts = round(start + j * interval, 3)
            if round(ts, 1) not in existing_set and ts < end:
                fill_timestamps.append(ts)
                existing_set.add(round(ts, 1))

        if len(fill_timestamps) + len(existing_timestamps) >= max_total:
            break

    all_timestamps = sorted(existing_timestamps + fill_timestamps)
    return all_timestamps[:max_total]
