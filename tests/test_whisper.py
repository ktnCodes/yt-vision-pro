"""Tests for whisper fallback — all mocked, no GPU needed."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from yt_vision_pro.whisper import is_whisper_available


class TestWhisperAvailability:
    @patch.dict("sys.modules", {"faster_whisper": MagicMock()})
    def test_returns_true_when_installed(self):
        # Need to reload module to pick up mock
        import importlib
        import yt_vision_pro.whisper as w
        importlib.reload(w)
        assert w.is_whisper_available() is True

    def test_returns_false_when_not_installed(self):
        import sys
        # Ensure faster_whisper is not importable
        with patch.dict("sys.modules", {"faster_whisper": None}):
            import importlib
            import yt_vision_pro.whisper as w
            importlib.reload(w)
            assert w.is_whisper_available() is False
