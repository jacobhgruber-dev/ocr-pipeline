from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from ..models import EngineOutput, MetadataResult

logger = logging.getLogger(__name__)

# GROBID TEI namespace
_TEI_NS = "http://www.tei-c.org/ns/1.0"


class GrobidEngine:
    """GROBID metadata extraction engine.

    Extracts structured metadata from academic PDFs: title, authors,
    affiliations, abstract, references, citations, DOIs, etc.

    Requires a running GROBID server (default: ``http://localhost:8070``).
    Install::

        docker run -p 8070:8070 lfoppiano/grobid:0.8.1

    GROBID is NOT a page-level OCR engine — it processes the full PDF and
    returns structured TEI XML.  This engine wraps that functionality so
    the pipeline can enrich per-PDF metadata.
    """

    # -- Protocol requirements -------------------------------------------------

    @property
    def engine_name(self) -> str:
        return "grobid"

    def __init__(self, grobid_url: str = "http://localhost:8070") -> None:
        self.grobid_url = grobid_url.rstrip("/")

    # -- Core API ---------------------------------------------------------------

    def recognize(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float = 120.0,
        pdf_path: Path | None = None,
    ) -> EngineOutput:
        """Extract metadata from a PDF via GROBID.

        *image_path* and *page_index* are accepted for protocol compatibility
        but are ignored — GROBID processes the full PDF, not page images.

        Args:
            image_path: Ignored (protocol compatibility).
            page_index: Ignored (protocol compatibility).
            timeout_sec: Per-request timeout in seconds.
            pdf_path: Path to the source PDF.  Required for metadata extraction.

        Returns:
            ``EngineOutput`` with ``text`` set to a JSON-serialized metadata
            dict (or empty on error), and ``blocks`` set to ``None``.
        """
        t0 = time.monotonic()
        if pdf_path is None:
            return EngineOutput(
                engine=self.engine_name,
                text="",
                error="pdf_path is required for GROBID metadata extraction",
                duration_sec=time.monotonic() - t0,
                blocks=None,
            )

        import importlib.util

        if importlib.util.find_spec("requests") is None:
            return EngineOutput(
                engine=self.engine_name,
                text="",
                error="requests library is required for GROBID. Install with: uv add requests",
                duration_sec=time.monotonic() - t0,
                blocks=None,
            )

        if not pdf_path.is_file():
            return EngineOutput(
                engine=self.engine_name,
                text="",
                error=f"PDF not found: {pdf_path}",
                duration_sec=time.monotonic() - t0,
                blocks=None,
            )

        try:
            metadata = self.extract_metadata(pdf_path, timeout_sec=timeout_sec)
            duration = time.monotonic() - t0
            metadata_dict = metadata.to_dict()
            return EngineOutput(
                engine=self.engine_name,
                text=json.dumps(metadata_dict, ensure_ascii=False),
                duration_sec=duration,
                blocks=None,
            )
        except Exception as exc:
            duration = time.monotonic() - t0
            logger.warning("GROBID metadata extraction failed for %s: %s", pdf_path, exc)
            return EngineOutput(
                engine=self.engine_name,
                text="",
                error=str(exc),
                duration_sec=duration,
                blocks=None,
            )

    def extract_metadata(
        self,
        pdf_path: Path,
        *,
        timeout_sec: float = 120.0,
    ) -> MetadataResult:
        """Extract full structured metadata from a PDF via GROBID REST API.

        Calls ``POST /api/processHeaderDocument`` for header metadata and
        ``POST /api/processReferences`` for bibliographic references.

        Args:
            pdf_path: Path to the source PDF.
            timeout_sec: Per-request timeout in seconds.

        Returns:
            ``MetadataResult`` with extracted fields.

        Raises:
            RuntimeError: If the GROBID server is unreachable or returns
                          a non-200 status.
            ValueError: If the PDF cannot be read.
        """
        if not pdf_path.is_file():
            raise ValueError(f"PDF not found: {pdf_path}")

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # -- Header metadata ---------------------------------------------------
        header_tei = self._post_grobid(
            endpoint="/api/processHeaderDocument",
            pdf_bytes=pdf_bytes,
            filename=pdf_path.name,
            timeout_sec=timeout_sec,
        )

        result = self._parse_header_tei(header_tei)
        result.raw_tei = header_tei

        # -- References --------------------------------------------------------
        try:
            refs_tei = self._post_grobid(
                endpoint="/api/processReferences",
                pdf_bytes=pdf_bytes,
                filename=pdf_path.name,
                timeout_sec=timeout_sec,
            )
            result.references = self._parse_references_tei(refs_tei)
            result.raw_tei += "\n<!-- REFERENCES -->\n" + refs_tei
        except Exception:
            logger.debug("GROBID reference extraction failed for %s", pdf_path, exc_info=True)

        return result

    def health_check(self) -> bool:
        """Return ``True`` if the GROBID server is reachable."""
        try:
            import requests
        except ImportError:
            return False
        try:
            resp = requests.get(
                f"{self.grobid_url}/api/isalive",
                timeout=10.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # -- Internal helpers ------------------------------------------------------

    def _post_grobid(
        self,
        endpoint: str,
        pdf_bytes: bytes,
        filename: str,
        timeout_sec: float,
    ) -> str:
        """POST a PDF to a GROBID endpoint and return the TEI XML response.

        Raises:
            RuntimeError: On non-200 status or connection failure.
        """
        import requests

        url = f"{self.grobid_url}{endpoint}"
        try:
            resp = requests.post(
                url,
                files={"input": (filename, pdf_bytes, "application/pdf")},
                timeout=timeout_sec,
            )
        except requests.ConnectionError as exc:
            raise RuntimeError(
                f"GROBID server at {self.grobid_url} is not reachable. "
                f"Is it running?  Start with: docker run -p 8070:8070 lfoppiano/grobid:0.8.1"
            ) from exc
        except requests.Timeout as exc:
            raise RuntimeError(
                f"GROBID request to {endpoint} timed out after {timeout_sec}s"
            ) from exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"GROBID returned HTTP {resp.status_code} from {endpoint}: {resp.text[:500]}"
            )

        return resp.text

    # -- TEI XML parsing -------------------------------------------------------

    @staticmethod
    def _parse_header_tei(xml_text: str) -> MetadataResult:
        """Parse GROBID header TEI XML into a MetadataResult."""
        result = MetadataResult()

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            logger.warning("Failed to parse GROBID TEI XML: %s", exc)
            return result

        ns = _TEI_NS

        # -- Title --
        title_el = root.find(f".//{{{ns}}}titleStmt/{{{ns}}}title")
        if title_el is not None and title_el.text:
            # Some GROBID responses nest the title in a <title type="main">
            main_title = title_el.find(f"{{{ns}}}title")
            if main_title is not None and main_title.text:
                result.title = main_title.text.strip()
            elif title_el.text:
                result.title = title_el.text.strip()

        # -- Authors --
        for author_el in root.findall(f".//{{{ns}}}sourceDesc//{{{ns}}}author"):
            author_text = _tei_text_content(author_el, ns)
            if author_text:
                result.authors.append(author_text)

        # -- Abstract --
        abstract_el = root.find(f".//{{{ns}}}profileDesc/{{{ns}}}abstract/{{{ns}}}p")
        if abstract_el is not None and abstract_el.text:
            result.abstract = abstract_el.text.strip()

        # -- Keywords --
        for kw_el in root.findall(f".//{{{ns}}}textClass/{{{ns}}}keywords/{{{ns}}}term"):
            if kw_el.text:
                result.keywords.append(kw_el.text.strip())

        # -- DOI --
        doi_el = root.find(f".//{{{ns}}}idno[@type='DOI']")
        if doi_el is not None and doi_el.text:
            result.doi = doi_el.text.strip()

        # -- Journal / venue --
        monogr = root.find(f".//{{{ns}}}sourceDesc//{{{ns}}}monogr")
        if monogr is not None:
            journal_title = monogr.find(f"{{{ns}}}title")
            if journal_title is not None and journal_title.text:
                result.journal = journal_title.text.strip()

            # Imprint: volume, issue, pages, date
            imprint = monogr.find(f"{{{ns}}}imprint")
            if imprint is not None:
                vol_el = imprint.find(f"{{{ns}}}biblScope[@unit='volume']")
                if vol_el is not None and vol_el.text:
                    result.volume = vol_el.text.strip()

                issue_el = imprint.find(f"{{{ns}}}biblScope[@unit='issue']")
                if issue_el is not None and issue_el.text:
                    result.issue = issue_el.text.strip()

                pages_el = imprint.find(f"{{{ns}}}biblScope[@unit='page']")
                if pages_el is not None and pages_el.text:
                    result.pages = pages_el.text.strip()

                date_el = imprint.find(f"{{{ns}}}date[@type='published']")
                if date_el is None:
                    date_el = imprint.find(f"{{{ns}}}date")
                if date_el is not None:
                    when = date_el.get("when", "")
                    if when:
                        result.year = when[:4]
                    elif date_el.text:
                        result.year = date_el.text.strip()

        return result

    @staticmethod
    def _parse_references_tei(xml_text: str) -> list[dict[str, Any]]:
        """Parse GROBID references TEI XML into a list of reference dicts."""
        refs: list[dict[str, Any]] = []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            logger.warning("Failed to parse GROBID references TEI: %s", exc)
            return refs

        ns = _TEI_NS

        for bibl in root.findall(f".//{{{ns}}}listBibl/{{{ns}}}biblStruct"):
            ref: dict[str, Any] = {}

            # Title
            title_el = bibl.find(f".//{{{ns}}}analytic/{{{ns}}}title")
            if title_el is not None and title_el.text:
                ref["title"] = title_el.text.strip()

            # Authors
            authors: list[str] = []
            for author_el in bibl.findall(f".//{{{ns}}}author"):
                author_text = _tei_text_content(author_el, ns)
                if author_text:
                    authors.append(author_text)
            if authors:
                ref["authors"] = authors

            # DOI
            doi_el = bibl.find(f".//{{{ns}}}idno[@type='DOI']")
            if doi_el is not None and doi_el.text:
                ref["doi"] = doi_el.text.strip()

            # Journal / venue
            monogr = bibl.find(f"{{{ns}}}monogr")
            if monogr is not None:
                jtitle = monogr.find(f"{{{ns}}}title")
                if jtitle is not None and jtitle.text:
                    ref["journal"] = jtitle.text.strip()

                imprint = monogr.find(f"{{{ns}}}imprint")
                if imprint is not None:
                    date_el = imprint.find(f"{{{ns}}}date[@type='published']")
                    if date_el is None:
                        date_el = imprint.find(f"{{{ns}}}date")
                    if date_el is not None:
                        when = date_el.get("when", "")
                        ref["year"] = when[:4] if when else (date_el.text or "").strip()

                    vol_el = imprint.find(f"{{{ns}}}biblScope[@unit='volume']")
                    if vol_el is not None and vol_el.text:
                        ref["volume"] = vol_el.text.strip()

                    pages_el = imprint.find(f"{{{ns}}}biblScope[@unit='page']")
                    if pages_el is not None and pages_el.text:
                        ref["pages"] = pages_el.text.strip()

            # Raw citation string (from note)
            note_el = bibl.find(f".//{{{ns}}}note")
            if note_el is not None and note_el.text:
                ref["raw"] = note_el.text.strip()

            if ref:  # only add non-empty refs
                refs.append(ref)

        return refs


def _tei_text_content(el: ElementTree.Element, ns: str) -> str:
    """Extract a human-readable author string from a TEI author element.

    Concatenates forename(s) and surname with spaces.
    """
    parts: list[str] = []
    for forename_el in el.findall(f"{{{ns}}}persName/{{{ns}}}forename"):
        if forename_el.text:
            parts.append(forename_el.text.strip())
    surname_el = el.find(f"{{{ns}}}persName/{{{ns}}}surname")
    if surname_el is not None and surname_el.text:
        parts.append(surname_el.text.strip())
    if not parts:
        # Fallback: try direct text content
        text = "".join(el.itertext()).strip()
        return text
    return " ".join(parts)
