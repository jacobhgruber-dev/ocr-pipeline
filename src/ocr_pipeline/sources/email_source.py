"""Email document source — .eml and .mbox files.

Parses RFC 2822 email messages and extracts headers (From, To, Subject,
Date), body text, and attachments list.
"""

from __future__ import annotations

import email
import email.policy
import logging
from email.message import Message
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class EmailSource(DocumentSource):
    """Document source for email files (``.eml``, ``.mbox``).

    Extracts email headers as metadata and body text as content.
    .mbox files are treated as multiple messages (one per page).
    """

    _messages: list[Message] | None = None

    @property
    def source_format(self) -> str:
        ext = self.path.suffix.lower()
        return "mbox" if ext == ".mbox" else "email"

    @property
    def source_mimetype(self) -> str:
        return "message/rfc822"

    @property
    def page_count(self) -> int:
        return max(len(self._load_messages()), 1)

    def _load_messages(self) -> list[Message]:
        if self._messages is not None:
            return self._messages

        raw = self.path.read_bytes()
        ext = self.path.suffix.lower()

        if ext == ".mbox":
            msgs: list[Message] = []
            parser = email.parser.BytesParser(policy=email.policy.default)
            for raw_msg in raw.split(b"\nFrom "):
                raw_msg = raw_msg.strip()
                if raw_msg:
                    if not raw_msg.startswith(b"From "):
                        raw_msg = b"From " + raw_msg
                    try:
                        msg = parser.parsebytes(raw_msg)
                        msgs.append(msg)
                    except Exception:
                        pass
            self._messages = msgs
        else:
            try:
                msg = email.message_from_bytes(raw, policy=email.policy.default)
            except Exception:
                msg = email.message_from_string(raw.decode("utf-8", errors="replace"))
            self._messages = [msg]

        return self._messages

    @staticmethod
    def _get_body(msg: Message) -> str:
        """Extract the plain-text body from an email message."""
        if msg.is_multipart():
            parts: list[str] = []
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/plain":
                    try:
                        payload = part.get_content()
                        if isinstance(payload, str):
                            parts.append(payload)
                    except Exception:
                        pass
            return "\n\n".join(parts)
        else:
            try:
                payload = msg.get_content()
                return str(payload) if payload else ""
            except Exception:
                return ""

    def extract_metadata(self) -> MetadataResult:
        msgs = self._load_messages()
        if not msgs:
            return MetadataResult(
                extraction_method="email-parsing",
                source_info=SourceInfo(format="email", page_count=0),
            )

        msg = msgs[0]
        return MetadataResult(
            title=str(msg.get("Subject", "")),
            authors=[str(msg.get("From", ""))],
            date=str(msg.get("Date", "")),
            document_type="email",
            extraction_method="email-parsing",
            source_info=SourceInfo(
                format=self.source_format,
                page_count=len(msgs),
                mimetype="message/rfc822",
                extra={
                    "to": str(msg.get("To", "")),
                    "cc": str(msg.get("Cc", "")),
                    "message_id": str(msg.get("Message-ID", "")),
                },
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("EmailSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        msgs = self._load_messages()
        if page_index < 0 or page_index >= len(msgs):
            return "", None

        msg = msgs[page_index]
        lines = [
            f"From: {msg.get('From', '')}",
            f"To: {msg.get('To', '')}",
            f"Date: {msg.get('Date', '')}",
            f"Subject: {msg.get('Subject', '')}",
            "",
            self._get_body(msg),
        ]
        text = "\n".join(lines)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"page_{page_index + 1:04d}_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
