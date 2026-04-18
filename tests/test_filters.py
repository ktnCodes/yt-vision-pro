"""Tests for yt_vision_pro.filters — quality filters and pHash dedup."""
from pathlib import Path
from unittest.mock import patch

import numpy as np

from yt_vision_pro.filters import is_black_frame, is_blurry, is_slide_like, deduplicate_frames


class FakeHash:
    def __init__(self, value: int):
        self.value = value

    def __sub__(self, other):
        return self.value - other.value


class TestBlackFrameFilter:
    def test_rejects_black_frame(self, tmp_path: Path):
        # Create a nearly-black image
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:] = 5  # mean luminance = 5 < 15
        img_path = tmp_path / "black.jpg"
        _save_image(img, img_path)

        assert is_black_frame(img_path, threshold=15) == True

    def test_accepts_normal_frame(self, tmp_path: Path):
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        img_path = tmp_path / "normal.jpg"
        _save_image(img, img_path)

        assert is_black_frame(img_path, threshold=15) == False

    def test_accepts_borderline_frame(self, tmp_path: Path):
        img = np.ones((100, 100, 3), dtype=np.uint8) * 20
        img_path = tmp_path / "borderline.jpg"
        _save_image(img, img_path)

        assert is_black_frame(img_path, threshold=15) == False


class TestBlurFilter:
    def test_rejects_blurry_frame(self, tmp_path: Path):
        # Uniform image = zero Laplacian variance = very blurry
        img = np.ones((200, 200, 3), dtype=np.uint8) * 128
        img_path = tmp_path / "blurry.png"
        _save_image(img, img_path)

        assert is_blurry(img_path, threshold=100) == True

    def test_accepts_sharp_frame(self, tmp_path: Path):
        # Strong edges = high Laplacian variance
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        # Draw thick alternating bars
        for y in range(0, 200, 10):
            img[y:y+5, :] = 255
        img_path = tmp_path / "sharp.png"
        _save_image(img, img_path)

        assert is_blurry(img_path, threshold=100) == False


class TestDeduplicateFrames:
    def test_removes_duplicate_frames(self, tmp_path: Path):
        # Create identical images
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        paths = []
        for i in range(3):
            p = tmp_path / f"frame_{i}.jpg"
            _save_image(img, p)
            paths.append(p)

        kept, removed = deduplicate_frames(paths, hamming_threshold=5)

        assert len(kept) == 1
        assert len(removed) == 2

    def test_keeps_distinct_frames(self, tmp_path: Path):
        paths = []
        # Create radically different images
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        for i in range(3):
            img = np.zeros((200, 200, 3), dtype=np.uint8)
            img[:] = colors[i]
            # Add unique geometric patterns
            if i == 0:
                img[50:150, 50:150] = (0, 0, 0)
            elif i == 1:
                img[:100, :] = (255, 255, 255)
            else:
                for y in range(0, 200, 20):
                    img[y:y+10, :] = (255, 255, 0)
            p = tmp_path / f"frame_{i}.png"
            _save_image(img, p)
            paths.append(p)

        kept, removed = deduplicate_frames(paths, hamming_threshold=3)

        assert len(kept) == 3
        assert len(removed) == 0

    def test_handles_empty_list(self):
        kept, removed = deduplicate_frames([], hamming_threshold=5)
        assert kept == []
        assert removed == []

    def test_handles_single_frame(self, tmp_path: Path):
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        p = tmp_path / "frame_0.jpg"
        _save_image(img, p)

        kept, removed = deduplicate_frames([p], hamming_threshold=5)
        assert len(kept) == 1
        assert len(removed) == 0

    @patch("yt_vision_pro.filters._compute_phash")
    def test_slide_like_frames_use_tighter_threshold(self, mock_phash, tmp_path: Path):
        paths = [tmp_path / "frame_0.jpg", tmp_path / "frame_1.jpg"]
        for path in paths:
            path.write_bytes(b"frame")

        mock_phash.side_effect = [FakeHash(0), FakeHash(2)]

        kept, removed = deduplicate_frames(
            paths,
            hamming_threshold=5,
            slide_hamming_threshold=1,
            slide_like_paths={str(paths[1])},
        )

        assert kept == paths
        assert removed == []


class TestSlideLikeDetection:
    @patch("yt_vision_pro.filters.edge_density", return_value=0.0)
    def test_marks_text_heavy_frames_as_slide_like(self, mock_edge_density, tmp_path: Path):
        path = tmp_path / "slide.jpg"
        path.write_bytes(b"frame")

        assert is_slide_like(path, "x" * 81) is True


def _save_image(img: np.ndarray, path: Path):
    import cv2
    cv2.imwrite(str(path), img)
