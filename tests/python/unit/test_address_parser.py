"""
Unit tests for utils/address_parser.py

Tests cover:
  - Standard US addresses: "123 Main St, Austin, TX 78701"
  - US addresses with country suffix: "..., USA"
  - Canadian addresses: "789 Macleod Trail SE, Calgary, AB T2G 2L7"
  - Full province names: "Toronto, Ontario M5V 1K4"
  - Minimal addresses (2 or 1 component)
  - Empty / whitespace input
  - infer_city_state() fallback to config values
"""

import pytest
from utils.address_parser import AddressParser


@pytest.fixture
def parser():
    return AddressParser()


# ── Standard US addresses ─────────────────────────────────────────────────────

class TestUSAddresses:
    def test_standard_us(self, parser):
        result = parser.parse("123 Main St, Austin, TX 78701")
        assert result["street"] == "123 Main St"
        assert result["city"]   == "Austin"
        assert result["state"]  == "TX"
        assert result["zip"]    == "78701"

    def test_us_with_country_suffix(self, parser):
        result = parser.parse("123 Main St, Austin, TX 78701, USA")
        assert result["city"]  == "Austin"
        assert result["state"] == "TX"
        assert result["zip"]   == "78701"

    def test_us_full_state_name(self, parser):
        result = parser.parse("456 Oak Ave, Dallas, Texas 75201")
        assert result["state"] == "TX"
        assert result["city"]  == "Dallas"

    def test_us_zip_with_extension(self, parser):
        result = parser.parse("789 Elm St, Houston, TX 77002-1234")
        assert result["zip"].startswith("77002")
        assert result["state"] == "TX"

    def test_us_no_zip(self, parser):
        result = parser.parse("100 First St, Nashville, TN")
        assert result["city"]  == "Nashville"
        assert result["state"] == "TN"
        assert result["zip"]   == ""

    def test_street_preserved(self, parser):
        result = parser.parse("1600 Pennsylvania Ave NW, Washington, DC 20500")
        assert "1600 Pennsylvania Ave NW" in result["street"]
        assert result["state"] == "DC"


# ── Canadian addresses ────────────────────────────────────────────────────────

class TestCanadianAddresses:
    def test_canadian_postal_code(self, parser):
        result = parser.parse("789 Macleod Trail SE, Calgary, AB T2G 2L7")
        assert result["city"]  == "Calgary"
        assert result["state"] == "AB"
        assert "T2G" in result["zip"]

    def test_canadian_with_country_suffix(self, parser):
        result = parser.parse("100 King St W, Toronto, ON M5X 1A9, Canada")
        assert result["city"]  == "Toronto"
        assert result["state"] == "ON"
        assert "M5X" in result["zip"]

    def test_canadian_full_province_name(self, parser):
        result = parser.parse("200 Granville St, Vancouver, British Columbia V6C 1S4")
        assert result["state"] == "BC"
        assert result["city"]  == "Vancouver"

    def test_canadian_ontario(self, parser):
        result = parser.parse("1 Yonge St, Toronto, Ontario M5E 1E6")
        assert result["state"] == "ON"

    def test_canadian_quebec(self, parser):
        result = parser.parse("100 Rue Notre-Dame, Montreal, Quebec H2Y 1C6")
        assert result["state"] == "QC"


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_string(self, parser):
        result = parser.parse("")
        assert result == {"street": "", "city": "", "state": "", "zip": ""}

    def test_none(self, parser):
        result = parser.parse(None)
        assert result == {"street": "", "city": "", "state": "", "zip": ""}

    def test_whitespace_only(self, parser):
        result = parser.parse("   ")
        assert result == {"street": "", "city": "", "state": "", "zip": ""}

    def test_single_component(self, parser):
        """Only a street — city and state should be empty."""
        result = parser.parse("123 Main St")
        assert result["street"] == "123 Main St"
        assert result["city"]   == ""
        assert result["state"]  == ""

    def test_two_components(self, parser):
        result = parser.parse("123 Main St, Dallas")
        assert result["street"] == "123 Main St"
        assert result["city"]   == "Dallas"

    def test_result_always_has_all_keys(self, parser):
        result = parser.parse("Some Address")
        assert set(result.keys()) == {"street", "city", "state", "zip"}


# ── infer_city_state() ────────────────────────────────────────────────────────

class TestInferCityState:
    def test_uses_parsed_values_when_present(self, parser):
        config_loc = {"city": "Fallback City", "state": "ZZ"}
        result = parser.infer_city_state("123 Main St, Austin, TX 78701", config_loc)
        assert result["city"]  == "Austin"
        assert result["state"] == "TX"

    def test_falls_back_to_config_city(self, parser):
        config_loc = {"city": "Dallas", "state": "TX"}
        result = parser.infer_city_state("123 Main St", config_loc)
        assert result["city"] == "Dallas"

    def test_falls_back_to_config_state(self, parser):
        config_loc = {"city": "Dallas", "state": "TX"}
        result = parser.infer_city_state("123 Main St", config_loc)
        assert result["state"] == "TX"

    def test_config_full_state_name_abbreviated(self, parser):
        config_loc = {"city": "Austin", "state": "Texas"}
        result = parser.infer_city_state("123 Main St", config_loc)
        assert result["state"] == "TX"

    def test_empty_address_uses_full_config(self, parser):
        config_loc = {"city": "Houston", "state": "TX"}
        result = parser.infer_city_state("", config_loc)
        assert result["city"]  == "Houston"
        assert result["state"] == "TX"
