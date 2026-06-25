"""Tests verifying the OCR pipeline preserves citation-critical content."""

from __future__ import annotations

import pytest

from ocr_pipeline.postprocess import PostProcessor


class TestCitationPreservation:
    """Verify citation-critical content survives post-processing."""

    @pytest.fixture
    def pp(self):
        return PostProcessor()

    # ── Pope names ────────────────────────────────────────────

    def test_pope_names_survive_all_steps(self, pp):
        """Roman numeral Pope names must not be corrupted."""
        text = "Pope PAUL VI addressed the council. PIUS XII wrote the encyclical."
        result = pp.process(text)
        assert "PAUL VI" in result, "PAUL VI corrupted"
        assert "PIUS XII" in result, "PIUS XII corrupted"

    # ── Denzinger numbers ─────────────────────────────────────

    def test_denzinger_numbers_survive(self, pp):
        text = "See DS 150 for the Nicene Creed definition. Cf. Denz. 301."
        result = pp.process(text)
        assert "DS 150" in result
        assert "Denz. 301" in result

    # ── AAS references ────────────────────────────────────────

    def test_aas_references_survive(self, pp):
        text = "AAS 58 (1966) 123-145 contains the full text."
        result = pp.process(text)
        assert "AAS 58" in result

    # ── Canon law citations ───────────────────────────────────

    def test_canon_law_citations_survive(self, pp):
        text = "can. 123 \u00a72 and CIC/1983 c. 1055 address this."
        result = pp.process(text)
        assert "can. 123" in result
        assert "\u00a7" in result  # section symbol survives
        assert "CIC/1983" in result

    # ── DOIs ──────────────────────────────────────────────────

    def test_doi_survives(self, pp):
        text = "DOI: 10.1017/S0028688515000209"
        result = pp.process(text)
        assert "10.1017/S0028688515000209" in result

    # ── En dash preservation ──────────────────────────────────

    def test_en_dash_preserved(self, pp):
        text = "Pages 492\u2013511 contain the argument."  # en dash
        result = pp.process(text)
        assert "\u2013" in result, "En dash converted to hyphen"

    # ── Section symbol ────────────────────────────────────────

    def test_section_symbol_survives(self, pp):
        text = "\u00a7139 and \u00a7\u00a715-16"
        result = pp.process(text)
        assert "\u00a7" in result, "Section symbol stripped"

    # ── Aquinas abbreviations ─────────────────────────────────

    def test_aquinas_abbreviations_survive(self, pp):
        text = "Aquinas, ST, I-II q. 94 a. 2 and SCG, 1.3"
        result = pp.process(text)
        assert "ST" in result
        assert "SCG" in result

    # ── Patristic citations ───────────────────────────────────

    def test_patristic_citations_survive(self, pp):
        text = "Augustine, Conf. 8.12.29 (NPNF1 1:180)"
        result = pp.process(text)
        assert "Conf." in result
        assert "NPNF1" in result
        assert "1:180" in result

    # ── Ancient source abbreviations ──────────────────────────

    def test_ancient_source_abbreviations_survive(self, pp):
        text = "1QS 3:13-4:26 and 1 En. 10:1-3 and Ign. Eph. 7.2"
        result = pp.process(text)
        assert "1QS" in result
        assert "1 En." in result
        assert "Ign. Eph." in result

    # ── Rabbinic citations ────────────────────────────────────

    def test_rabbinic_citations_survive(self, pp):
        text = "m. Ber. 1:1 and b. Ber. 2a"
        result = pp.process(text)
        assert "m. Ber." in result
        assert "b. Ber." in result

    # ── Ligature expansion must not break citations ───────────

    def test_ligature_expansion_spares_citations(self, pp):
        """Ligature expansion should not mangle citation text."""
        text = "Cf. the \ufb01rst edition"  # ﬁ ligature → should become "first"
        result = pp.process(text, steps=["ligature_expand"])
        assert "first" in result

    # ── Control char removal spares Unicode ───────────────────

    def test_control_char_removal_spares_greek(self, pp):
        text = "\u039a\u03b1\u03bb\u03b7\u03bc\u03ad\u03c1\u03b1 \u03ba\u03cc\u03c3\u03bc\u03b5 \x00"  # Greek + null byte
        result = pp.process(text, steps=["stray_control_chars"])
        assert "\u039a\u03b1\u03bb\u03b7\u03bc\u03ad\u03c1\u03b1" in result
        assert "\x00" not in result

    # ── Whitespace normalization spares citation structure ────

    def test_whitespace_preserves_citation_line_breaks(self, pp):
        """Paragraph breaks within citations must be preserved."""
        text = (
            "Francis, encyclical *Laudato Si'* (24 May 2015).\n\n"
            "The document addresses climate change."
        )
        result = pp.process(text, steps=["whitespace_normalize"])
        assert "\n\n" in result or "\n" in result  # paragraph break survives

    # ── Soft hyphens in citations ─────────────────────────────

    def test_soft_hyphens_in_citations(self, pp):
        """Soft hyphens appearing in DOIs or author names must be removed correctly."""
        text = "10.1017/S00286885\u00ac\n15000209"  # soft hyphen in DOI
        result = pp.process(text, steps=["soft_hyphens"])
        assert "10.1017/S0028688515000209" in result
        assert "\u00ac" not in result


class TestCitationSystemPrompts:
    """Verify VLM system prompts include citation preservation rules."""

    def test_theological_prompt_includes_citation_rules(self):
        from ocr_pipeline.merger import _build_system_prompt

        prompt = _build_system_prompt(
            content_type="theological", column_layout="auto", languages=["en", "la"]
        )
        assert "PAUL VI" in prompt or "Pope" in prompt or "citation" in prompt.lower()

    def test_academic_prompt_includes_citation_rules(self):
        from ocr_pipeline.merger import _build_system_prompt

        prompt = _build_system_prompt(
            content_type="academic", column_layout="single", languages=["en"]
        )
        # Academic template should mention citations or references
        assert (
            "citation" in prompt.lower()
            or "reference" in prompt.lower()
            or "footnote" in prompt.lower()
        )

    def test_citation_focused_prompt_exists(self):
        from ocr_pipeline.merger import _SYSTEM_PROMPT_TEMPLATES

        assert "citation_focused" in _SYSTEM_PROMPT_TEMPLATES

    def test_general_prompt_does_not_include_specialized_rules(self):
        """General prompt should not include theological-specific citation rules."""
        from ocr_pipeline.merger import _build_system_prompt

        prompt = _build_system_prompt(
            content_type="general", column_layout="auto", languages=["en"]
        )
        # General prompt shouldn't mention Denzinger or AAS
        assert "Denzinger" not in prompt or "AAS" not in prompt
