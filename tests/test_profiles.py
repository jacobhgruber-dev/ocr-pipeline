"""Tests for DocumentProfile system."""

from __future__ import annotations

import pytest

from ocr_pipeline.profiles import (
    DocumentProfile,
    PROFILES,
    get_profile,
    list_profiles,
)
from ocr_pipeline.merger import _build_system_prompt


# ---------------------------------------------------------------------------
# DocumentProfile system
# ---------------------------------------------------------------------------


class TestGetProfileKnown:
    def test_get_academic(self):
        profile = get_profile("academic")
        assert profile.name == "academic"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5
        assert len(profile.suggested_engines) > 0
        assert len(profile.suggested_languages) > 0

    def test_get_mathematical(self):
        profile = get_profile("mathematical")
        assert profile.name == "mathematical"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5
        assert len(profile.suggested_engines) > 0

    def test_get_legal(self):
        profile = get_profile("legal")
        assert profile.name == "legal"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5
        assert len(profile.suggested_engines) > 0

    def test_get_general(self):
        profile = get_profile("general")
        assert profile.name == "general"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5
        assert len(profile.suggested_engines) > 0

    def test_get_technical(self):
        profile = get_profile("technical")
        assert profile.name == "technical"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5
        assert len(profile.suggested_engines) > 0
        # Technical profile should mention callout labels
        assert "WARNING" in profile.system_prompt or "callout" in profile.system_prompt.lower()

    def test_get_books(self):
        profile = get_profile("books")
        assert profile.name == "books"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5
        assert len(profile.suggested_engines) > 0
        # Books profile should mention front matter or chapter titles
        assert "chapter" in profile.system_prompt.lower() or "front matter" in profile.system_prompt.lower()

    def test_all_profiles_have_required_fields(self):
        for name in PROFILES:
            profile = get_profile(name)
            assert isinstance(profile.name, str)
            assert isinstance(profile.system_prompt, str)
            assert isinstance(profile.description, str)
            assert isinstance(profile.suggested_engines, list)
            assert isinstance(profile.suggested_languages, list)
            assert isinstance(profile.suggested_model, str)
            assert isinstance(profile.best_model, str)
            assert profile.name  # non-empty
            assert len(profile.system_prompt) > 10
            assert len(profile.description) > 0
            assert len(profile.suggested_engines) > 0

    def test_all_profiles_have_inline_suggestions(self):
        for name in PROFILES:
            profile = get_profile(name)
            assert len(profile.suggested_engines) > 0, f"{name}: no suggested engines"
            assert len(profile.suggested_languages) > 0, f"{name}: no suggested languages"
            assert profile.suggested_model in ("gemini-2.5-flash", "claude-sonnet-5"), (
                f"{name}: unexpected suggested_model {profile.suggested_model}"
            )
            assert profile.best_model in ("gemini-2.5-flash", "claude-sonnet-5"), (
                f"{name}: unexpected best_model {profile.best_model}"
            )


class TestGetProfileUnknown:
    def test_nonexistent_profile_falls_back_to_general(self):
        profile = get_profile("nonexistent")
        assert profile.name == "general"

    def test_empty_string_falls_back_to_general(self):
        profile = get_profile("")
        assert profile.name == "general"

    def test_returns_same_general_instance(self):
        p1 = get_profile("nonexistent")
        p2 = get_profile("also_nonexistent")
        assert p1 is p2  # same object in memory


class TestListProfiles:
    def test_has_at_least_six_items(self):
        names = list_profiles()
        assert len(names) >= 6

    def test_includes_all_major_profiles(self):
        names = list_profiles()
        assert "general" in names
        assert "academic" in names
        assert "mathematical" in names
        assert "legal" in names
        assert "technical" in names
        assert "books" in names

    def test_returns_sorted_list(self):
        names = list_profiles()
        assert names == sorted(names)

    def test_matches_profiles_dict_keys(self):
        names = list_profiles()
        assert set(names) == set(PROFILES.keys()) or set(names) >= set(PROFILES.keys())


class TestHeadersFootersAndImageText:
    """Verify all profiles include the header/footer bracketed format and image text OCR."""

    def test_general_has_header_footer_format(self):
        profile = get_profile("general")
        assert "[Header:" in profile.system_prompt or "Header:" in profile.system_prompt
        assert "[Footer:" in profile.system_prompt or "Footer:" in profile.system_prompt

    def test_general_has_image_text_ocr(self):
        profile = get_profile("general")
        assert "readable text" in profile.system_prompt.lower()

    def test_academic_has_header_footer_format(self):
        profile = get_profile("academic")
        assert "[Header:" in profile.system_prompt or "Header:" in profile.system_prompt

    def test_technical_has_image_text_ocr(self):
        profile = get_profile("technical")
        assert "readable text" in profile.system_prompt.lower() or "visible text" in profile.system_prompt.lower()


class TestDocumentProfileIsFrozen:
    def test_cannot_set_attribute(self):
        profile = get_profile("general")
        with pytest.raises(Exception):
            profile.name = "hacked"  # type: ignore[misc]

    def test_cannot_delete_attribute(self):
        profile = get_profile("general")
        with pytest.raises(Exception):
            del profile.name  # type: ignore[misc]

    def test_is_dataclass_instance(self):
        assert hasattr(DocumentProfile, "__dataclass_fields__")


# ---------------------------------------------------------------------------
# _build_system_prompt integration with profiles
# ---------------------------------------------------------------------------


class TestBuildSystemPromptWithProfile:
    def test_academic_prompt_mentions_citations(self):
        prompt = _build_system_prompt(profile_name="academic")
        assert "citation" in prompt.lower()

    def test_academic_prompt_is_longer_than_base(self):
        prompt = _build_system_prompt(profile_name="academic")
        base = _build_system_prompt(profile_name="general")
        assert len(prompt) > len(base)

    def test_legal_profile_mentions_statute(self):
        prompt = _build_system_prompt(profile_name="legal")
        assert "\u00a7" in prompt or "statute" in prompt.lower()

    def test_technical_profile_mentions_callouts(self):
        prompt = _build_system_prompt(profile_name="technical")
        assert "WARNING" in prompt or "callout" in prompt.lower()

    def test_books_profile_mentions_chapter(self):
        prompt = _build_system_prompt(profile_name="books")
        assert "chapter" in prompt.lower() or "front matter" in prompt.lower()

    def test_unknown_profile_falls_back_to_general(self):
        prompt = _build_system_prompt(profile_name="nonexistent_profile_key")
        assert "You are an OCR auditor" in prompt
        assert "[illegible]" in prompt


class TestBuildSystemPromptFallsBack:
    def test_mathematical_profile_mentions_latex(self):
        prompt = _build_system_prompt(profile_name="mathematical")
        assert "LaTeX" in prompt or "latex" in prompt.lower() or "math" in prompt.lower()

    def test_empty_profile_uses_general(self):
        prompt = _build_system_prompt(profile_name="")
        assert "You are an OCR auditor" in prompt
