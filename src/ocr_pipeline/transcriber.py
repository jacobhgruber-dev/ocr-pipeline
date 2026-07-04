"""Audio transcription via OpenAI Whisper (faster-whisper).

Uses ``faster-whisper`` for CPU-friendly transcription with automatic
model download.  Models are cached in ``~/.cache/huggingface/``.

Model sizes (trade off speed vs accuracy):
- tiny  (39 MB)  — fastest, for keyword/metadata extraction
- base  (141 MB) — good balance for speech
- small (466 MB) — best accuracy on CPU
- medium+ — GPU recommended, not default
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MODEL_SIZES = ("tiny", "base", "small", "medium", "large-v3")


def transcribe_audio(
    audio_path: Path,
    model_size: str = "tiny",
    language: str | None = None,
    timeout: float = 300.0,
) -> str:
    """Transcribe an audio file using faster-whisper.

    Args:
        audio_path: Path to WAV, MP3, FLAC, OGG, or other audio file.
        model_size: Whisper model size (``"tiny"``, ``"base"``, ``"small"``).
        language: ISO 639-1 language code (e.g. ``"en"``) or ``None`` for auto-detect.
        timeout: Maximum seconds for transcription.

    Returns:
        Transcribed text, or empty string on failure.
    """
    if model_size not in _MODEL_SIZES:
        logger.warning("Unknown model size '%s' — falling back to 'tiny'", model_size)
        model_size = "tiny"

    try:
        from faster_whisper import WhisperModel

        # Use CPU by default (fast enough for tiny/base models)
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
        )
        logger.info(
            "Transcribing %s with whisper-%s (detected: %s, prob: %.2f)",
            audio_path.name,
            model_size,
            info.language,
            info.language_probability,
        )

        parts: list[str] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                parts.append(text)

        return "\n".join(parts)

    except ImportError:
        logger.debug("faster-whisper not installed — install with: pip install faster-whisper")
    except FileNotFoundError:
        logger.warning("Audio file not found: %s", audio_path)
    except Exception as exc:
        logger.warning("Transcription failed for %s: %s", audio_path.name, exc)

    return ""
