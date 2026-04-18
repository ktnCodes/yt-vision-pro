"""Whisper fallback transcription for yt-vision-pro.

All faster-whisper imports are guarded — the module works even when
faster-whisper is not installed.
"""
from pathlib import Path
import subprocess
import tempfile

try:
    from faster_whisper import WhisperModel
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False


def is_whisper_available() -> bool:
    """Return True if faster-whisper can be imported."""
    return _WHISPER_AVAILABLE


def transcribe_audio(video_path: Path, output_vtt: Path) -> Path:
    """Extract audio with ffmpeg, transcribe with faster-whisper, write VTT.

    Raises RuntimeError if faster-whisper is not installed.
    """
    if not is_whisper_available():
        raise RuntimeError(
            "faster-whisper is not installed. Install with: pip install yt-vision-pro[whisper]"
        )

    # Extract audio to a temp WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = Path(tmp.name)

    subprocess.run(
        ["ffmpeg", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le",
         "-ar", "16000", "-ac", "1", str(audio_path), "-y"],
        check=True,
        capture_output=True,
    )

    try:
        model = WhisperModel("base", compute_type="int8")
        segments, _ = model.transcribe(str(audio_path), word_timestamps=True)

        with open(output_vtt, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for segment in segments:
                start = _format_vtt_time(segment.start)
                end = _format_vtt_time(segment.end)
                text = segment.text.strip()
                if text:
                    f.write(f"{start} --> {end}\n{text}\n\n")
    finally:
        audio_path.unlink(missing_ok=True)

    return output_vtt


def _format_vtt_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm for VTT."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"
