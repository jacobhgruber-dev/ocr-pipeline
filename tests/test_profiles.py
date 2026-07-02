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
    def test_get_theological_journal(self):
        profile = get_profile("theological_journal")
        assert profile.name == "theological_journal"
        assert profile.content_type == "theological"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5

    def test_get_academic(self):
        profile = get_profile("academic")
        assert profile.name == "academic"
        assert profile.content_type == "academic"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5

    def test_get_irish_hagiography(self):
        profile = get_profile("irish_hagiography")
        assert profile.name == "irish_hagiography"
        assert profile.content_type == "irish_hagiography"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5

    def test_get_mathematical(self):
        profile = get_profile("mathematical")
        assert profile.name == "mathematical"
        assert profile.content_type == "mathematical"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5

    def test_get_legal(self):
        profile = get_profile("legal")
        assert profile.name == "legal"
        assert profile.content_type == "legal"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5

    def test_get_citation_focused(self):
        profile = get_profile("citation_focused")
        assert profile.name == "citation_focused"
        assert profile.content_type == "citation_focused"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5

    def test_get_general(self):
        profile = get_profile("general")
        assert profile.name == "general"
        assert profile.content_type == "general"
        assert len(profile.system_prompt) > 100
        assert len(profile.description) > 5

    def test_all_profiles_have_required_fields(self):
        for name in PROFILES:
            profile = get_profile(name)
            assert isinstance(profile.name, str)
            assert isinstance(profile.content_type, str)
            assert isinstance(profile.system_prompt, str)
            assert isinstance(profile.description, str)
            assert profile.name  # non-empty
            assert profile.content_type  # non-empty
            assert len(profile.system_prompt) > 10
            assert len(profile.description) > 0


class TestGetProfileUnknown:
    def test_nonexistent_profile_falls_back_to_general(self):
        profile = get_profile("nonexistent")
        assert profile.name == "general"
        assert profile.content_type == "general"

    def test_empty_string_falls_back_to_general(self):
        profile = get_profile("")
        assert profile.name == "general"

    def test_returns_same_general_instance(self):
        p1 = get_profile("nonexistent")
        p2 = get_profile("also_nonexistent")
        assert p1 is p2  # same object in memory


class TestListProfiles:
    def test_has_at_least_seven_items(self):
        names = list_profiles()
        assert len(names) >= 7

    def test_includes_all_major_profiles(self):
        names = list_profiles()
        assert "general" in names
        assert "theological_journal" in names
        assert "irish_hagiography" in names
        assert "academic" in names
        assert "mathematical" in names
        assert "legal" in names
        assert "citation_focused" in names

    def test_returns_sorted_list(self):
        names = list_profiles()
        assert names == sorted(names)

    def test_matches_profiles_dict_keys(self):
        names = list_profiles()
        assert set(names) == set(PROFILES.keys())


class TestIrishHagiography:
    def test_system_prompt_mentions_fada(self):
        profile = get_profile("irish_hagiography")
        assert "fada" in profile.system_prompt.lower()

    def test_system_prompt_mentions_acute_accent(self):
        profile = get_profile("irish_hagiography")
        # Check for the actual fada character(s) in the prompt
        prompt_lower = profile.system_prompt.lower()
        assert "fada" in prompt_lower or "\u00e1" in profile.system_prompt

    def test_description_mentions_diacritics(self):
        profile = get_profile("irish_hagiography")
        assert "fada" in profile.description.lower()


class TestTheologicalJournal:
    def test_system_prompt_mentions_ecclesiastical_or_latin(self):
        profile = get_profile("theological_journal")
        prompt_lower = profile.system_prompt.lower()
        assert "ecclesiastical" in prompt_lower or "latin" in prompt_lower

    def test_description_mentions_journal(self):
        profile = get_profile("theological_journal")
        assert "journal" in profile.description.lower()


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
    def test_irish_hagiography_prompt_mentions_fada(self):
        prompt = _build_system_prompt(profile_name="irish_hagiography")
        assert "fada" in prompt.lower()

    def test_irish_hagiography_prompt_is_longer_than_base(self):
        prompt = _build_system_prompt(profile_name="irish_hagiography")
        base = _build_system_prompt(content_type="general")
        # The profile prompt includes context hints + formatting rules
        assert len(prompt) > len(base)

    def test_theological_profile_mentions_ecclesiastical(self):
        prompt = _build_system_prompt(profile_name="theological_journal")
        assert "ecclesiastical" in prompt.lower() or "latin" in prompt.lower()

    def test_unknown_profile_falls_back_to_general(self):
        prompt = _build_system_prompt(profile_name="nonexistent_profile_key")
        # Falls back to general profile prompt (no longer appends context hints)
        assert "You are an OCR auditor" in prompt
        assert "[illegible]" in prompt


class TestBuildSystemPromptFallsBack:
    def test_mathematical_content_type_mentions_latex(self):
        prompt = _build_system_prompt(content_type="mathematical")
        assert "LaTeX" in prompt or "latex" in prompt.lower() or "math" in prompt.lower()

    def test_theological_content_type_mentions_ecclesiastical(self):
        prompt = _build_system_prompt(content_type="theological")
        assert "ecclesiastical" in prompt.lower() or "theological" in prompt.lower()

    def test_unknown_content_type_falls_back_to_general(self):
        prompt = _build_system_prompt(content_type="nonexistent")
        assert "You are an OCR auditor" in prompt

    def test_empty_content_type_uses_general(self):
        prompt = _build_system_prompt(content_type="")
        assert "You are an OCR auditor" in prompt

    def test_profile_name_takes_precedence_over_content_type(self):
        prompt = _build_system_prompt(
            content_type="mathematical",
            profile_name="irish_hagiography",
        )
        # Should use the irish_hagiography profile, not mathematical
        assert "fada" in prompt.lower()
        # Irish hagiography prompt should NOT have LaTeX math content
        assert "latex math mode" not in prompt.lower()
