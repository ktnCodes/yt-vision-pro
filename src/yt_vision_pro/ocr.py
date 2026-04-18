"""OCR text extraction from video frames using RapidOCR."""
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


def extract_ocr_result(image_path: Path) -> dict[str, str | int]:
    engine = RapidOCR()
    results, _ = engine(str(image_path))

    if not results:
        return {"text": "", "text_length": 0}

    texts = [item[1] for item in results if len(item) > 1 and item[1]]
    text = " ".join(texts).strip()
    return {"text": text, "text_length": len(text)}


def extract_ocr_text(image_path: Path) -> str:
    return str(extract_ocr_result(image_path)["text"])
