"""PaperSource adapter for MCP integration.

TODO: Implement the PaperSource adapter that wraps a completed OCR pipeline
output directory and exposes the MCP PaperSource interface (search, download,
read). See docs/OCR_PIPELINE_V2_DESIGN.md section 9 for the design.
"""

from __future__ import annotations


class OcrCorpusSearcher:
    """PaperSource adapter for an OCR-processed corpus (not yet implemented)."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "OcrCorpusSearcher is not yet implemented. "
            "See docs/OCR_PIPELINE_V2_DESIGN.md section 9 for the planned design."
        )
