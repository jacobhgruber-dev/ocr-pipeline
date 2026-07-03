"""VLM-based metadata extraction — works on any document type."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models import MetadataResult

logger = logging.getLogger("ocr_pipeline.metadata_vlm")

_METADATA_SYSTEM_PROMPT = """\
You are a metadata extraction specialist. Given the first pages of a document,
extract structured metadata. Analyze the visual layout, typography, and content
to determine the document type and extract all available metadata fields.

Return a JSON object with these fields (use null for unavailable fields):
{
  "document_type": "academic_article | legal_opinion | legal_statute | legal_contract | book | book_chapter | technical_spec | technical_manual | datasheet | report | thesis | conference_paper | newspaper | magazine | other",
  "title": "full document title",
  "authors": ["Author 1", "Author 2"],
  "date": "YYYY or YYYY-MM-DD",
  "language": "en",
  "publisher": "publisher or issuing organization",
  "abstract": "abstract or summary text (first 500 chars)",
  "keywords": ["keyword1", "keyword2"],
  "identifiers": {"DOI": "...", "ISBN": "...", "arXiv": "...", "docket": "..."},
  "pages": "page range or count",
  "journal": "journal name (academic)",
  "volume": "volume (academic)",
  "issue": "issue (academic)",
  "court": "court name (legal)",
  "docket_number": "case/docket number (legal)",
  "edition": "edition string (books)",
  "series": "series name (books)",
  "part_number": "part or document number (technical)",
  "revision": "revision or version (technical)"
}

Rules:
- Extract ONLY what is visible on the page images. Do not invent or guess.
- For authors: if the document is a legal opinion, the "author" is the court or judge.
- For the title: prefer the largest/most prominent text on the first page.
- For language: detect from the text content. If multilingual, use the primary language.
- For document_type: classify based on visual layout and content patterns.
- If a field is not present, use null — do NOT write empty strings or empty arrays.
"""


def _call_gemini_with_images(
    model: str,
    images: list[bytes],
    system_prompt: str,
    user_text: str,
    api_key: str,
    max_tokens: int = 1024,
) -> str:
    """Send multiple page images to Gemini and return the text response.

    Uses the google-genai SDK.  Each image is sent as a ``Part.from_bytes``
    with ``image/png`` MIME type, followed by the text prompt.
    """
    from google import genai

    client = genai.Client(api_key=api_key)

    parts: list[Any] = []
    for img_bytes in images:
        parts.append(genai.types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
    parts.append(genai.types.Part.from_text(text=user_text))

    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
            max_output_tokens=max_tokens,
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini returned no text content")

    return response.text


class VlmMetadataEngine:
    """Extract structured metadata from any document using a VLM.

    Sends rendered page images of the first *page_count* pages to a VLM
    (default: gemini-2.5-flash) and parses the JSON response into a
    :class:`MetadataResult`.

    Does NOT implement :class:`OcrEngine` — metadata extraction has a
    different interface (multiple pages → structured JSON).
    """

    def __init__(
        self,
        vlm_model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        page_count: int = 3,
        timeout_sec: float = 30.0,
    ) -> None:
        self.vlm_model = vlm_model
        self.api_key = api_key
        self.page_count = page_count
        self.timeout_sec = timeout_sec

    def health_check(self) -> bool:
        """Check whether the configured API key is available."""
        return bool(self.api_key)

    def extract(
        self,
        pdf_path: Path,
        *,
        page_count: int | None = None,
    ) -> MetadataResult:
        """Extract metadata from the first *page_count* pages of *pdf_path*.

        Args:
            pdf_path: Path to the PDF.
            page_count: Override the default page count (min 1, max 5).

        Returns:
            ``MetadataResult`` with ``extraction_method="vlm"`` on success,
            or ``extraction_method="vlm_failed"`` on failure.
        """
        import fitz  # pymupdf

        if not self.api_key:
            logger.warning("No API key configured for VLM metadata extraction")
            return MetadataResult(extraction_method="vlm_failed")

        if not pdf_path.is_file():
            logger.warning("PDF not found: %s", pdf_path)
            return MetadataResult(extraction_method="vlm_failed")

        n = page_count if page_count is not None else self.page_count
        n = max(1, min(n, 5))

        # Render first N pages as images
        images: list[bytes] = []
        try:
            doc = fitz.open(str(pdf_path))
            total = doc.page_count
            for i in range(min(n, total)):
                page = doc[i]
                pix = page.get_pixmap(dpi=150)  # 150 DPI is enough for text
                images.append(pix.tobytes("png"))
            doc.close()
        except Exception as exc:
            logger.warning("Failed to render PDF %s: %s", pdf_path, exc)
            return MetadataResult(extraction_method="vlm_failed")

        if not images:
            return MetadataResult(extraction_method="vlm_failed")

        # Send to VLM
        try:
            json_text = self._call_vlm(images)
            data = json.loads(json_text)
            return self._parse_response(data)
        except Exception as exc:
            logger.warning("VLM metadata extraction failed for %s: %s", pdf_path, exc)
            return MetadataResult(extraction_method="vlm_failed")

    def _call_vlm(self, images: list[bytes]) -> str:
        """Send images to the VLM and return cleaned JSON text."""
        user_text = (
            "Extract structured metadata from these document pages. "
            "Return ONLY a JSON object — no preamble, no markdown fences, no explanation."
        )

        response = _call_gemini_with_images(
            model=self.vlm_model,
            images=images,
            system_prompt=_METADATA_SYSTEM_PROMPT,
            user_text=user_text,
            api_key=self.api_key,  # type: ignore[arg-type]
            max_tokens=4096,
        )

        # Strip markdown fences if present
        text = response.strip()
        if text.startswith("```"):
            # Remove opening fence (with optional language tag)
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            else:
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> MetadataResult:
        """Parse VLM JSON response into a MetadataResult."""
        ids = data.get("identifiers") or {}
        return MetadataResult(
            title=str(data.get("title") or ""),
            authors=[str(a) for a in (data.get("authors") or [])],
            abstract=str(data.get("abstract") or ""),
            keywords=[str(k) for k in (data.get("keywords") or [])],
            doi=str(ids.get("DOI") or ""),
            journal=str(data.get("journal") or ""),
            volume=str(data.get("volume") or ""),
            issue=str(data.get("issue") or ""),
            year="",
            pages=str(data.get("pages") or ""),
            document_type=str(data.get("document_type") or ""),
            language=str(data.get("language") or ""),
            publisher=str(data.get("publisher") or ""),
            isbn=str(ids.get("ISBN") or ""),
            docket_number=str(data.get("docket_number") or ""),
            court=str(data.get("court") or ""),
            edition=str(data.get("edition") or ""),
            series=str(data.get("series") or ""),
            part_number=str(data.get("part_number") or ""),
            revision=str(data.get("revision") or ""),
            date=str(data.get("date") or ""),
            identifiers=ids if isinstance(ids, dict) else {},
            extraction_method="vlm",
        )
