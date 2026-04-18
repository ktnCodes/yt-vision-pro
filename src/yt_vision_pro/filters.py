"""Quality filters and slide-aware pHash dedup for yt-vision-pro."""
from pathlib import Path

import cv2
import imagehash
from PIL import Image


def is_black_frame(image_path: Path, threshold: int = 15) -> bool:
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return True
    return float(img.mean()) < threshold


def is_blurry(image_path: Path, threshold: float = 100.0) -> bool:
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return True
    laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
    return laplacian_var < threshold


def edge_density(
    image_path: Path,
    low_threshold: int = 100,
    high_threshold: int = 200,
) -> float:
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None or img.size == 0:
        return 0.0

    edges = cv2.Canny(img, low_threshold, high_threshold)
    return float((edges > 0).sum()) / float(edges.size)


def is_slide_like(
    image_path: Path,
    ocr_text: str = "",
    text_length_threshold: int = 80,
    edge_density_threshold: float = 0.08,
) -> bool:
    if len(ocr_text.strip()) >= text_length_threshold:
        return True
    return edge_density(image_path) >= edge_density_threshold


def _compute_phash(image_path: Path):
    with Image.open(image_path) as image:
        return imagehash.phash(image)


def _path_key(image_path: Path | str) -> str:
    return str(image_path)


def deduplicate_frames(
    frame_paths: list[Path],
    hamming_threshold: int = 5,
    slide_hamming_threshold: int | None = None,
    ocr_results: dict[str, str] | None = None,
    slide_like_paths: set[str] | None = None,
) -> tuple[list[Path], list[Path]]:
    if not frame_paths:
        return [], []

    ocr_lookup = {str(key): value for key, value in (ocr_results or {}).items()}
    explicit_slide_like = {str(path) for path in (slide_like_paths or set())}
    slide_flags: dict[str, bool] = {}
    slide_threshold = slide_hamming_threshold if slide_hamming_threshold is not None else max(1, hamming_threshold - 2)

    def is_slide(path: Path) -> bool:
        key = _path_key(path)
        if key not in slide_flags:
            slide_flags[key] = key in explicit_slide_like or is_slide_like(path, ocr_lookup.get(key, ""))
        return slide_flags[key]

    kept = [frame_paths[0]]
    removed = []
    kept_hashes = [_compute_phash(frame_paths[0])]

    is_slide(frame_paths[0])

    for path in frame_paths[1:]:
        candidate_hash = _compute_phash(path)
        candidate_is_slide = is_slide(path)
        is_dupe = False
        for kept_path, kept_hash in zip(kept, kept_hashes):
            threshold = slide_threshold if candidate_is_slide or is_slide(kept_path) else hamming_threshold
            if abs(candidate_hash - kept_hash) < threshold:
                is_dupe = True
                break
        if is_dupe:
            removed.append(path)
        else:
            kept.append(path)
            kept_hashes.append(candidate_hash)

    return kept, removed
