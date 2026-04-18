"""Tests for yt_vision_pro.ocr — RapidOCR text extraction from frames."""
from pathlib import Path
from unittest.mock import patch

from yt_vision_pro.ocr import extract_ocr_result, extract_ocr_text


class TestExtractOcrText:
    def test_returns_text_and_length_payload(self, tmp_path: Path):
        img_path = tmp_path / "frame.jpg"
        img_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        with patch("yt_vision_pro.ocr.RapidOCR") as MockOCR:
            mock_engine = MockOCR.return_value
            mock_engine.return_value = (
                [["box", "Hello World", 0.95], ["box2", "More text", 0.88]],
                None,
            )

            result = extract_ocr_result(img_path)

        assert result == {"text": "Hello World More text", "text_length": 21}

    def test_returns_string_from_image(self, tmp_path: Path):
        # Create a minimal valid JPEG-like file
        img_path = tmp_path / "frame.jpg"
        img_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        with patch("yt_vision_pro.ocr.RapidOCR") as MockOCR:
            mock_engine = MockOCR.return_value
            mock_engine.return_value = (
                [["box", "Hello World", 0.95], ["box2", "More text", 0.88]],
                None,
            )

            result = extract_ocr_text(img_path)

        assert "Hello World" in result
        assert "More text" in result

    def test_returns_empty_string_when_no_text_found(self, tmp_path: Path):
        img_path = tmp_path / "frame.jpg"
        img_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        with patch("yt_vision_pro.ocr.RapidOCR") as MockOCR:
            mock_engine = MockOCR.return_value
            mock_engine.return_value = (None, None)

            result = extract_ocr_text(img_path)

        assert result == ""

    def test_handles_empty_results_list(self, tmp_path: Path):
        img_path = tmp_path / "frame.jpg"
        img_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        with patch("yt_vision_pro.ocr.RapidOCR") as MockOCR:
            mock_engine = MockOCR.return_value
            mock_engine.return_value = ([], None)

            result = extract_ocr_text(img_path)

        assert result == ""


class TestOcrInManifest:
    def test_manifest_renders_ocr_text(self):
        from yt_vision_pro.manifest import _render_frames_section

        frames = [
            {"frame_number": 0, "timestamp": 5.0, "path": "f.jpg", "ocr_text": "Detected text here"},
        ]
        lines = _render_frames_section(frames, [])
        content = "\n".join(lines)
        assert "**OCR:** Detected text here" in content

    def test_manifest_skips_ocr_when_empty(self):
        from yt_vision_pro.manifest import _render_frames_section

        frames = [
            {"frame_number": 0, "timestamp": 5.0, "path": "f.jpg", "ocr_text": ""},
        ]
        lines = _render_frames_section(frames, [])
        content = "\n".join(lines)
        assert "**OCR:**" not in content

    def test_manifest_handles_no_ocr_key(self):
        from yt_vision_pro.manifest import _render_frames_section

        frames = [
            {"frame_number": 0, "timestamp": 5.0, "path": "f.jpg"},
        ]
        lines = _render_frames_section(frames, [])
        content = "\n".join(lines)
        assert "**OCR:**" not in content
