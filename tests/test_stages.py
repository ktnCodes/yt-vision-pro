"""Tests for yt_vision_pro.stages — pipeline stage sentinels."""
from pathlib import Path

from yt_vision_pro.fetch import ChapterInfo
from yt_vision_pro.stages import (
    STAGES,
    clear_all_stages,
    clear_from_stage,
    is_stage_done,
    mark_stage_done,
    parse_dense_chapters,
    parse_timestamp,
    resolve_chapter_densities,
)


class TestStageSentinels:
    def test_stage_not_done_initially(self, tmp_path: Path):
        assert is_stage_done(tmp_path, "fetch") is False

    def test_mark_stage_done_creates_sentinel(self, tmp_path: Path):
        mark_stage_done(tmp_path, "fetch")
        assert is_stage_done(tmp_path, "fetch") is True

    def test_mark_stage_done_creates_stages_dir(self, tmp_path: Path):
        cache_dir = tmp_path / "cache" / "vid1"
        mark_stage_done(cache_dir, "fetch")
        assert (cache_dir / ".stages" / "fetch.done").exists()

    def test_mark_stage_done_is_idempotent(self, tmp_path: Path):
        mark_stage_done(tmp_path, "fetch")
        mark_stage_done(tmp_path, "fetch")
        assert is_stage_done(tmp_path, "fetch") is True

    def test_multiple_stages_independent(self, tmp_path: Path):
        mark_stage_done(tmp_path, "fetch")
        mark_stage_done(tmp_path, "extract")

        assert is_stage_done(tmp_path, "fetch") is True
        assert is_stage_done(tmp_path, "extract") is True
        assert is_stage_done(tmp_path, "ocr") is False


class TestClearStages:
    def test_clear_all_removes_all_sentinels(self, tmp_path: Path):
        for stage in STAGES:
            mark_stage_done(tmp_path, stage)

        clear_all_stages(tmp_path)

        for stage in STAGES:
            assert is_stage_done(tmp_path, stage) is False

    def test_clear_from_stage_removes_stage_and_later(self, tmp_path: Path):
        for stage in STAGES:
            mark_stage_done(tmp_path, stage)

        clear_from_stage(tmp_path, "ocr")

        assert is_stage_done(tmp_path, "fetch") is True
        assert is_stage_done(tmp_path, "extract") is True
        assert is_stage_done(tmp_path, "ocr") is False
        assert is_stage_done(tmp_path, "align") is False
        assert is_stage_done(tmp_path, "manifest") is False

    def test_clear_from_first_stage_clears_all(self, tmp_path: Path):
        for stage in STAGES:
            mark_stage_done(tmp_path, stage)

        clear_from_stage(tmp_path, "fetch")

        for stage in STAGES:
            assert is_stage_done(tmp_path, stage) is False

    def test_clear_all_is_noop_when_no_stages_dir(self, tmp_path: Path):
        clear_all_stages(tmp_path)  # Should not raise


class TestStagesConstant:
    def test_stages_ordered(self):
        assert STAGES == ["fetch", "extract", "ocr", "dedup-with-ocr-context", "align", "manifest"]


class TestDensityResolution:
    def test_parses_dense_chapter_indices(self):
        assert parse_dense_chapters("0, 2,4") == {0, 2, 4}

    def test_parses_timestamp(self):
        assert parse_timestamp("01:00:00") == 3600.0
        assert parse_timestamp("02:30") == 150.0

    def test_resolve_chapter_densities_upgrades_requested_chapters(self):
        chapters = [
            ChapterInfo(number=0, title="Intro", start_time=0.0, end_time=60.0),
            ChapterInfo(number=1, title="Main", start_time=60.0, end_time=120.0),
        ]

        resolved, profiles = resolve_chapter_densities(
            chapters,
            default_density="normal",
            dense_chapters="1",
            default_scene_sample_interval=6.0,
        )

        assert resolved[0].density == "normal"
        assert resolved[1].density == "high"
        assert profiles["normal"].scene_sample_interval == 6.0
