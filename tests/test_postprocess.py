"""Tests for PostProcessor — text cleanup steps."""

from __future__ import annotations

from ocr_pipeline.postprocess import PostProcessor


# ---------------------------------------------------------------------------
# Individual step tests
# ---------------------------------------------------------------------------


class TestSoftHyphens:
    def test_fix_soft_hyphens(self):
        post = PostProcessor(steps=["soft_hyphens"])
        result = post.process("word\u00ac\nnext")
        assert result == "wordnext"

    def test_removes_standalone_soft_hyphen(self):
        post = PostProcessor(steps=["soft_hyphens"])
        result = post.process("text\u00acwith\u00achyphens")
        assert result == "textwithhyphens"

    def test_soft_hyphen_with_space_before_newline(self):
        post = PostProcessor(steps=["soft_hyphens"])
        result = post.process("word\u00ac  \n  next")
        assert result == "wordnext"


class TestEmDashBreaks:
    def test_fix_em_dash_breaks(self):
        post = PostProcessor(steps=["em_dash_breaks"])
        result = post.process("word\u2014\nnext")
        assert result == "word\u2014next"


class TestWhitespaceNormalize:
    def test_collapses_triple_newlines(self):
        post = PostProcessor(steps=["whitespace_normalize"])
        result = post.process("line1\n\n\n\nline2")
        assert result == "line1\n\nline2"

    def test_strips_trailing_whitespace(self):
        post = PostProcessor(steps=["whitespace_normalize"])
        result = post.process("line1   \nline2\t")
        assert result == "line1\nline2"

    def test_preserves_single_newline(self):
        post = PostProcessor(steps=["whitespace_normalize"])
        result = post.process("a\nb")
        assert result == "a\nb"


class TestLigatureExpand:
    def test_expands_fi(self):
        post = PostProcessor(steps=["ligature_expand"])
        result = post.process("financial \ufb01le")
        assert "fi" in result
        assert "\ufb01" not in result

    def test_expands_fl(self):
        post = PostProcessor(steps=["ligature_expand"])
        result = post.process("\ufb02ower")
        assert result == "flower"

    def test_expands_ff(self):
        post = PostProcessor(steps=["ligature_expand"])
        result = post.process("\ufb00")
        assert result == "ff"

    def test_expands_ae(self):
        post = PostProcessor(steps=["ligature_expand"])
        result = post.process("encyclop\u00e6dia")
        assert result == "encyclopaedia"

    def test_expands_oe(self):
        post = PostProcessor(steps=["ligature_expand"])
        result = post.process("\u0153uvre")
        assert result == "oeuvre"

    def test_expands_uppercase_ae(self):
        post = PostProcessor(steps=["ligature_expand"])
        result = post.process("\u00c6sop")
        assert result == "AEsop"

    def test_expands_uppercase_oe(self):
        post = PostProcessor(steps=["ligature_expand"])
        result = post.process("\u0152il")
        assert result == "OEil"


class TestStrayControlChars:
    def test_removes_null(self):
        post = PostProcessor(steps=["stray_control_chars"])
        result = post.process("text\x00with\x00nulls")
        assert result == "textwithnulls"

    def test_removes_other_controls(self):
        post = PostProcessor(steps=["stray_control_chars"])
        result = post.process("abc\x01def\x02ghi")
        assert result == "abcdefghi"

    def test_removes_del(self):
        post = PostProcessor(steps=["stray_control_chars"])
        result = post.process("text\x7fdel")
        assert result == "textdel"

    def test_keeps_newline_and_tab(self):
        post = PostProcessor(steps=["stray_control_chars"])
        original = "line1\n\tline2"
        result = post.process(original)
        assert result == original

    def test_removes_vertical_tab(self):
        post = PostProcessor(steps=["stray_control_chars"])
        result = post.process("a\x0bb")
        assert result == "ab"


# ---------------------------------------------------------------------------
# Unicode preservation
# ---------------------------------------------------------------------------


class TestUnicodePreservation:
    def test_greek_survives_all_steps(self):
        post = PostProcessor()
        text = "\u0391\u03b3\u03b1\u03c0\u03b7"  # Ἀγαπη
        result = post.process(text)
        assert result == text

    def test_accented_latin_survives(self):
        post = PostProcessor()
        text = "caf\u00e9 r\u00e9sum\u00e9 fa\u00e7ade"
        result = post.process(text)
        assert result == text

    def test_cjk_survives(self):
        post = PostProcessor()
        text = "\u65e5\u672c\u8a9e"  # 日本語
        result = post.process(text)
        assert result == text

    def test_ligature_step_does_not_harm_greek(self):
        post = PostProcessor(steps=["ligature_expand"])
        text = "\u0391\u03b3\u03b1\u03c0\u03b7"
        result = post.process(text)
        assert result == text


# ---------------------------------------------------------------------------
# General PostProcessor behavior
# ---------------------------------------------------------------------------


class TestPostProcessorGeneral:
    def test_empty_text_returns_empty(self):
        post = PostProcessor()
        result = post.process("")
        assert result == ""

    def test_step_subset(self):
        post = PostProcessor()
        # Only soft hyphens — should not normalize whitespace or expand ligatures
        text = "word\u00ac\nnext\n\n\n\n\n\n"
        result = post.process(text, steps=["soft_hyphens"])
        assert "wordnext" in result
        # Triple+ newlines remain because whitespace_normalize wasn't run
        assert "\n\n\n\n" in result

    def test_all_steps_together(self):
        post = PostProcessor()
        text = "\x00Hello\u00e6 word\u00ac\n\n\x01next\u2014\n\n\n\n\nfinal\x7f"
        result = post.process(text)
        # After all steps: no control chars, ae expanded, soft hyphen removed,
        # em-dash line joined, whitespace normalized (3+ newlines → 2)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x7f" not in result
        assert "\u00ac" not in result  # soft hyphen removed
        assert "ae" in result  # ligature expanded
        assert "next\u2014final" in result  # em-dash joined
        # No triple+ newlines
        assert "\n\n\n" not in result

    def test_unknown_step_name_silently_ignored(self):
        post = PostProcessor(steps=["soft_hyphens"])
        result = post.process("text\u00ac\nmore", steps=["soft_hyphens", "nonexistent"])
        assert result == "textmore"

    def test_default_uses_all_registered_steps(self):
        post = PostProcessor()  # no explicit steps → all registered
        assert len(post._enabled_steps) == 6  # 6 cleanup steps (dehyphenate added)
