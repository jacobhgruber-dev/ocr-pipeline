"""Audio/video media source — metadata extraction stub.

Detects audio and video file formats and extracts technical metadata
via FFprobe (if available).  Full transcription requires a separate
speech-to-text pipeline (whisper, etc.) and is out of scope.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".aiff", ".opus"}
_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".ts", ".3gp"}


class MediaSource(DocumentSource):
    """Document source for audio and video files.

    Extracts FFprobe metadata (duration, codec, bitrate, streams).
    Transcription is not supported — use a dedicated STT pipeline.
    """

    _probe_cache: dict[str, object] | None = None

    @property
    def source_format(self) -> str:
        ext = self.path.suffix.lower()
        if ext in _VIDEO_EXTS:
            return "video"
        return "audio"

    @property
    def source_mimetype(self) -> str:
        ext = self.path.suffix.lower()
        _mimes: dict[str, str] = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".flac": "audio/flac",
            ".ogg": "audio/ogg",
            ".mp4": "video/mp4",
            ".mkv": "video/x-matroska",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".webm": "video/webm",
        }
        return _mimes.get(ext, "application/octet-stream")

    @property
    def page_count(self) -> int:
        return 1

    def _probe(self) -> dict[str, object]:
        if self._probe_cache is not None:
            return self._probe_cache

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(self.path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                self._probe_cache = json.loads(result.stdout)
            else:
                self._probe_cache = {"error": "ffprobe failed"}
        except FileNotFoundError:
            self._probe_cache = {"error": "ffprobe not installed"}
            logger.debug("ffprobe not available")
        except Exception as exc:
            self._probe_cache = {"error": str(exc)}

        return self._probe_cache

    def extract_metadata(self) -> MetadataResult:
        probe = self._probe()
        st = self.path.stat()
        fmt_info = probe.get("format", {})
        streams = probe.get("streams", [])

        duration = fmt_info.get("duration", "")
        stream_types = [s.get("codec_type", "") for s in streams if isinstance(s, dict)]

        return MetadataResult(
            title=self.path.stem,
            document_type=self.source_format,
            extraction_method="ffprobe",
            source_info=SourceInfo(
                format=self.source_format,
                page_count=1,
                mimetype=self.source_mimetype,
                extra={
                    "duration_sec": str(duration),
                    "format_name": str(fmt_info.get("format_name", "")),
                    "bit_rate": str(fmt_info.get("bit_rate", "")),
                    "streams": stream_types,
                    "file_size_bytes": st.st_size,
                    "transcription_available": "false",
                },
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError(
            "MediaSource.render_page not supported — use ffmpeg for frame extraction."
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        probe = self._probe()

        fmt_info = probe.get("format", {})
        lines = [
            f"# {self.source_format.title()}: {self.path.name}",
            "",
            f"**Format**: {fmt_info.get('format_name', 'unknown')}",
            f"**Duration**: {fmt_info.get('duration', 'unknown')}s",
            f"**Bitrate**: {fmt_info.get('bit_rate', 'unknown')}",
            f"**Size**: {fmt_info.get('size', 'unknown')} bytes",
            "",
            "## Streams",
            "",
        ]

        for i, stream in enumerate(probe.get("streams", [])):
            if isinstance(stream, dict):
                lines.append(
                    f"- Stream {i}: {stream.get('codec_type', '?')} "
                    f"({stream.get('codec_name', '?')}), "
                    f"{stream.get('channels', '')} ch"
                    if stream.get("codec_type") == "audio"
                    else f"{stream.get('width', '')}x{stream.get('height', '')}"
                )

        lines.append("")
        lines.append("*Transcription not available — use whisper or cloud STT service.*")

        text = "\n".join(lines)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")
        return text, out_path
