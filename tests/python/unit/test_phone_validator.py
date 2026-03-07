"""
Unit tests for utils/phone_validator.py

Tests cover:
  - format() — national format (XXX) XXX-XXXX
  - extract_from_text() — multi-phone extraction from arbitrary text
  - is_valid() — boolean validation
  - to_e164() — E.164 format (+1XXXXXXXXXX)
  - Edge cases: empty, None, invalid, already formatted
"""

import pytest
from utils.phone_validator import PhoneValidator


@pytest.fixture
def pv():
    return PhoneValidator()


# ── format() ──────────────────────────────────────────────────────────────────

class TestFormat:
    def test_standard_format(self, pv):
        assert pv.format("(214) 555-0123") == "(214) 555-0123"

    def test_dashes(self, pv):
        assert pv.format("214-555-0123") == "(214) 555-0123"

    def test_dots(self, pv):
        assert pv.format("214.555.0123") == "(214) 555-0123"

    def test_no_formatting(self, pv):
        assert pv.format("2145550123") == "(214) 555-0123"

    def test_with_country_code_1(self, pv):
        assert pv.format("+12145550123") == "(214) 555-0123"

    def test_with_country_code_space(self, pv):
        assert pv.format("1 214 555 0123") == "(214) 555-0123"

    def test_empty_string(self, pv):
        assert pv.format("") == ""

    def test_none(self, pv):
        assert pv.format(None) == ""

    def test_whitespace_only(self, pv):
        assert pv.format("   ") == ""

    def test_invalid_number_too_short(self, pv):
        assert pv.format("123-456") == ""

    def test_invalid_number_letters(self, pv):
        assert pv.format("call-us-now") == ""

    def test_invalid_area_code_000(self, pv):
        """Area code 000 is not a valid US number."""
        assert pv.format("000-555-0123") == ""

    def test_output_is_national_format(self, pv):
        """Output must always be (NXX) NXX-XXXX."""
        result = pv.format("9725550199")
        assert result == "(972) 555-0199"

    def test_strips_leading_trailing_spaces(self, pv):
        assert pv.format("  (972) 555-0199  ") == "(972) 555-0199"


# ── is_valid() ────────────────────────────────────────────────────────────────

class TestIsValid:
    def test_valid_us_number(self, pv):
        assert pv.is_valid("(214) 555-0100") is True

    def test_invalid_number(self, pv):
        assert pv.is_valid("not-a-phone") is False

    def test_empty(self, pv):
        assert pv.is_valid("") is False

    def test_too_short(self, pv):
        assert pv.is_valid("555-1234") is False


# ── to_e164() ─────────────────────────────────────────────────────────────────

class TestToE164:
    def test_standard(self, pv):
        assert pv.to_e164("(214) 555-0123") == "+12145550123"

    def test_dashes(self, pv):
        assert pv.to_e164("214-555-0123") == "+12145550123"

    def test_invalid(self, pv):
        assert pv.to_e164("not-a-phone") == ""

    def test_empty(self, pv):
        assert pv.to_e164("") == ""

    def test_returns_plus_prefix(self, pv):
        result = pv.to_e164("9725550199")
        assert result.startswith("+1")
        assert len(result) == 12  # +1 + 10 digits


# ── extract_from_text() ───────────────────────────────────────────────────────

class TestExtractFromText:
    def test_single_phone(self, pv):
        text = "Call us at (214) 555-0123 for help."
        result = pv.extract_from_text(text)
        assert result == ["(214) 555-0123"]

    def test_multiple_phones(self, pv):
        text = "Main: 214-555-0100. Fax: (214) 555-0101."
        result = pv.extract_from_text(text)
        assert len(result) == 2
        assert "(214) 555-0100" in result
        assert "(214) 555-0101" in result

    def test_deduplicates(self, pv):
        text = "(214) 555-0123 and also (214) 555-0123"
        result = pv.extract_from_text(text)
        assert result.count("(214) 555-0123") == 1

    def test_no_phones(self, pv):
        text = "No contact info here."
        result = pv.extract_from_text(text)
        assert result == []

    def test_empty_text(self, pv):
        result = pv.extract_from_text("")
        assert result == []

    def test_phone_embedded_in_text(self, pv):
        text = "Phone:972.555.0199|Fax:972.555.0200"
        result = pv.extract_from_text(text)
        assert "(972) 555-0199" in result

    def test_returns_list(self, pv):
        result = pv.extract_from_text("214-555-0100")
        assert isinstance(result, list)
