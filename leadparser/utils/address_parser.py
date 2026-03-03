"""
Address Parser — splits a full address string into components.

Uses pure regex (no paid geocoding API).  Handles the most common
Google Maps address formats for both US and Canada:
    "123 Main St, Austin, TX 78701, USA"
    "1234 W 57th Ave, Vancouver, BC V6P 3V8, Canada"
    "456 King St W, Toronto, Ontario M5V 1K4, Canada"
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Patterns ────────────────────────────────────────────────────────────────

# Canadian postal code: A1A 1A1 (with optional space in middle)
_CA_POSTAL_RE = re.compile(r'\b[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d\b')
# US zip code: 12345 or 12345-6789
_US_ZIP_RE    = re.compile(r'\b\d{5}(?:-\d{4})?\b')

# Primary address regex — handles US and Canadian formats
# Street, City, State/Province [Postal], [Country]
_ADDRESS_RE = re.compile(
    r"""
    ^
    (?P<street>[^,]+?)              # Street address
    ,\s*
    (?P<city>[^,]+?)                # City
    ,\s*
    (?P<state_raw>[^,]+?)           # State/Province (may include postal code)
    (?:,\s*(?:USA|Canada|United\s+States))?   # Optional country suffix
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ── State / Province lookups ─────────────────────────────────────────────────

_STATE_ABBR: dict[str, str] = {
    # US states
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
    # Canadian provinces / territories
    "alberta": "AB", "british columbia": "BC", "manitoba": "MB",
    "new brunswick": "NB", "newfoundland and labrador": "NL",
    "northwest territories": "NT", "nova scotia": "NS", "nunavut": "NU",
    "ontario": "ON", "prince edward island": "PE", "quebec": "QC",
    "québec": "QC", "saskatchewan": "SK", "yukon": "YT",
}


def _abbr(raw: str) -> str:
    """Convert a full state/province name to its 2-letter abbreviation.
    If already 2 letters, return uppercase as-is."""
    raw = raw.strip()
    if len(raw) == 2:
        return raw.upper()
    return _STATE_ABBR.get(raw.lower(), raw.upper())


def _strip_postal(text: str) -> tuple[str, str]:
    """Strip a US zip or Canadian postal code from *text*.
    Returns (cleaned_text, postal_code)."""
    m = _CA_POSTAL_RE.search(text)
    if m:
        postal = m.group(0).strip()
        return text[:m.start()].strip().rstrip(',').strip(), postal
    m = _US_ZIP_RE.search(text)
    if m:
        postal = m.group(0).strip()
        return text[:m.start()].strip().rstrip(',').strip(), postal
    return text, ""


def _normalize(address: str) -> str:
    """Strip trailing country names and normalise whitespace."""
    for suffix in (', Canada', ', USA', ', United States', ',Canada', ',USA'):
        if address.lower().endswith(suffix.lower()):
            address = address[: -len(suffix)].rstrip(',').strip()
            break
    return address.strip()


def _looks_like_postal(text: str) -> bool:
    """Return True if *text* looks like a bare postal code (not a city name)."""
    t = text.strip()
    return bool(_CA_POSTAL_RE.fullmatch(t) or _US_ZIP_RE.fullmatch(t))


class AddressParser:
    """
    Splits a single-line address into its component parts.
    Returns a dict with keys: street, city, state, zip.
    Handles US and Canadian addresses as returned by Google Maps.
    """

    def parse(self, address: str) -> dict:
        result = {"street": "", "city": "", "state": "", "zip": ""}

        if not address or not address.strip():
            return result

        address = _normalize(address.strip())

        # ── Primary regex attempt ──────────────────────────────────────
        m = _ADDRESS_RE.match(address)
        if m:
            street   = m.group("street").strip()
            city     = m.group("city").strip()
            state_raw = m.group("state_raw").strip()

            # state_raw may look like "BC V6P 3V8" or "Texas 78701" or just "TX"
            state_clean, postal = _strip_postal(state_raw)

            result["street"] = street
            result["city"]   = city
            result["state"]  = _abbr(state_clean) if state_clean else ""
            result["zip"]    = postal
            return result

        # ── Comma-split fallback ───────────────────────────────────────
        parts = [p.strip() for p in address.split(",") if p.strip()]

        if len(parts) >= 3:
            result["street"] = parts[0]

            # parts[1] should be city — but skip it if it looks like a postal code
            if not _looks_like_postal(parts[1]):
                result["city"] = parts[1]
            else:
                # Unusual format: no separate city component; use config fallback
                pass

            # The state/province is typically parts[2]; strip any postal code from it
            state_raw, postal = _strip_postal(parts[2])
            if state_raw:
                result["state"] = _abbr(state_raw)
            result["zip"] = postal

            # If len(parts) >= 4 and parts[2] was actually a postal-only component,
            # the real state might be in parts[3] (rare Canadian format)
            if not result["state"] and len(parts) >= 4:
                state_raw2, _ = _strip_postal(parts[3])
                if state_raw2:
                    result["state"] = _abbr(state_raw2)

        elif len(parts) == 2:
            result["street"] = parts[0]
            result["city"]   = parts[1]
        else:
            result["street"] = address

        return result

    def infer_city_state(self, address: str, config_location: dict) -> dict:
        """
        Parse the address, and if city/state are missing, fall back to
        the configured location from config.yaml.
        The config state is normalised to its 2-letter abbreviation.
        """
        parsed = self.parse(address)
        if not parsed["city"]:
            parsed["city"]  = config_location.get("city", "")
        if not parsed["state"]:
            raw_state = config_location.get("state", "")
            parsed["state"] = _abbr(raw_state) if raw_state else ""
        else:
            # Always store abbreviation, even if config had full name
            parsed["state"] = _abbr(parsed["state"])
        return parsed
