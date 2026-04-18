"""Tests for transcript_cues.py — visual cue detection and chapter fill."""
import pytest

from yt_vision_pro.transcript_cues import (
    VisualCue,
    chapter_fill_timestamps,
    compute_cue_timestamps,
    deduplicate_cues,
    find_visual_cues,
)


class TestFindVisualCues:
    def test_tier1_explicit_visual(self):
        segments = [
            {"text": "as you can see here the diagram shows", "start": 10.0},
            {"text": "now let me talk about something else", "start": 20.0},
        ]
        cues = find_visual_cues(segments)
        assert len(cues) == 1
        assert cues[0].tier == 1
        assert cues[0].timestamp == 10.0
        assert "as you can see" in cues[0].phrase

    def test_tier2_demo_cue(self):
        segments = [
            {"text": "let me pull up the file manager", "start": 30.0},
        ]
        cues = find_visual_cues(segments, tiers=(2,))
        assert len(cues) == 1
        assert cues[0].tier == 2

    def test_tier3_data_reference(self):
        segments = [
            {"text": "these results are really interesting", "start": 60.0},
        ]
        cues = find_visual_cues(segments, tiers=(3,))
        assert len(cues) == 1
        assert cues[0].tier == 3

    def test_highest_tier_wins_per_segment(self):
        segments = [
            {"text": "as you can see this benchmark shows the data", "start": 10.0},
        ]
        cues = find_visual_cues(segments, tiers=(1, 2, 3))
        assert len(cues) == 1
        assert cues[0].tier == 1  # tier 1 beats tier 3

    def test_no_cues_in_plain_speech(self):
        segments = [
            {"text": "I think we should consider a few things", "start": 5.0},
            {"text": "the most important factor is collaboration", "start": 15.0},
        ]
        cues = find_visual_cues(segments)
        assert len(cues) == 0

    def test_case_insensitive(self):
        segments = [
            {"text": "AS YOU CAN SEE the numbers are clear", "start": 100.0},
        ]
        cues = find_visual_cues(segments)
        assert len(cues) == 1

    def test_filtered_tiers(self):
        segments = [
            {"text": "as you can see this chart", "start": 10.0},  # tier 1
            {"text": "let me pull up the code", "start": 30.0},   # tier 2
            {"text": "the data shows improvement", "start": 50.0},  # tier 3
        ]
        cues = find_visual_cues(segments, tiers=(1,))
        assert len(cues) == 1
        assert cues[0].timestamp == 10.0

    def test_empty_segments(self):
        assert find_visual_cues([]) == []

    def test_sorted_by_timestamp(self):
        segments = [
            {"text": "look at this diagram", "start": 50.0},
            {"text": "as you can see here", "start": 10.0},
            {"text": "take a look at the chart", "start": 30.0},
        ]
        cues = find_visual_cues(segments)
        timestamps = [c.timestamp for c in cues]
        assert timestamps == sorted(timestamps)


class TestDeduplicateCues:
    def test_merges_within_window(self):
        cues = [
            VisualCue(timestamp=10.0, tier=1, phrase="look at this", context="..."),
            VisualCue(timestamp=12.0, tier=2, phrase="let me show", context="..."),
            VisualCue(timestamp=14.0, tier=3, phrase="the data", context="..."),
        ]
        result = deduplicate_cues(cues, window=15.0)
        assert len(result) == 1
        assert result[0].tier == 1  # highest tier kept

    def test_separate_groups(self):
        cues = [
            VisualCue(timestamp=10.0, tier=1, phrase="look at this", context="..."),
            VisualCue(timestamp=50.0, tier=2, phrase="let me show", context="..."),
        ]
        result = deduplicate_cues(cues, window=15.0)
        assert len(result) == 2

    def test_empty_input(self):
        assert deduplicate_cues([]) == []

    def test_single_cue(self):
        cues = [VisualCue(timestamp=5.0, tier=1, phrase="here", context="...")]
        result = deduplicate_cues(cues, window=15.0)
        assert len(result) == 1

    def test_tight_window(self):
        cues = [
            VisualCue(timestamp=10.0, tier=1, phrase="a", context="..."),
            VisualCue(timestamp=12.0, tier=1, phrase="b", context="..."),
            VisualCue(timestamp=14.0, tier=1, phrase="c", context="..."),
            VisualCue(timestamp=30.0, tier=2, phrase="d", context="..."),
        ]
        result = deduplicate_cues(cues, window=5.0)
        assert len(result) == 2


class TestComputeCueTimestamps:
    def test_end_to_end(self):
        segments = [
            {"text": "as you can see here", "start": 10.0},
            {"text": "nothing visual here", "start": 20.0},
            {"text": "look at this chart", "start": 60.0},
        ]
        timestamps = compute_cue_timestamps(segments)
        assert 10.0 in timestamps
        assert 60.0 in timestamps
        assert len(timestamps) == 2

    def test_dedup_merges_nearby(self):
        segments = [
            {"text": "as you can see", "start": 10.0},
            {"text": "look at this", "start": 12.0},
            {"text": "right here", "start": 14.0},
        ]
        timestamps = compute_cue_timestamps(segments, dedup_window=15.0)
        assert len(timestamps) == 1


class TestChapterFillTimestamps:
    def test_fills_empty_chapters(self):
        chapters = [
            {"start_time": 0.0, "end_time": 60.0},
            {"start_time": 60.0, "end_time": 120.0},
        ]
        result = chapter_fill_timestamps(chapters, [], max_total=200, samples_per_chapter=3)
        assert len(result) > 0
        # Frames should be within chapter boundaries
        for ts in result:
            assert 0.0 <= ts < 120.0

    def test_respects_max_total(self):
        chapters = [
            {"start_time": 0.0, "end_time": 300.0},
            {"start_time": 300.0, "end_time": 600.0},
        ]
        existing = list(range(0, 200))  # already at budget
        result = chapter_fill_timestamps(chapters, [float(t) for t in existing], max_total=200)
        assert len(result) <= 200

    def test_preserves_existing_timestamps(self):
        chapters = [
            {"start_time": 0.0, "end_time": 60.0},
            {"start_time": 60.0, "end_time": 120.0},
        ]
        existing = [15.0, 75.0]
        result = chapter_fill_timestamps(chapters, existing, max_total=200, samples_per_chapter=3)
        assert 15.0 in result
        assert 75.0 in result
        assert len(result) > len(existing)

    def test_no_fill_when_budget_exhausted(self):
        chapters = [{"start_time": 0.0, "end_time": 60.0}]
        existing = [float(i) for i in range(200)]
        result = chapter_fill_timestamps(chapters, existing, max_total=200)
        assert len(result) == 200

    def test_empty_chapters(self):
        result = chapter_fill_timestamps([], [10.0], max_total=200)
        assert result == [10.0]

    def test_chapters_with_existing_coverage(self):
        chapters = [
            {"start_time": 0.0, "end_time": 60.0},
            {"start_time": 60.0, "end_time": 120.0},
        ]
        # Chapter 0 already has 3 frames, chapter 1 has none
        existing = [10.0, 20.0, 30.0]
        result = chapter_fill_timestamps(chapters, existing, max_total=200, samples_per_chapter=3)
        # Chapter 1 should get fills
        ch1_frames = [t for t in result if 60.0 <= t < 120.0]
        assert len(ch1_frames) >= 1
