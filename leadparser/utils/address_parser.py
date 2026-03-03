"""
Address Parser — splits a full US address string into components.

Uses pure regex (no paid geocoding API).  Handles the most common
Google Maps address format:
    "123 Main St, Austin, TX 78701, USA"
"""

import re
import logging

logger = logging.getLogger(__name__)

# Pattern covers the most common US address formats returned by Google Maps
_ADDRESS_RE = re.compile(
    r"""
    ^
    (?P<street>[^,]+)               # Street address (everything before first comma)
    ,\s*
    (?P<city>[^,]+)                 # City
    ,\s*
    (?P<state>[A-Za-z]{2})         # 2-letter state abbreviation
    (?:\s+(?P<zip>\d{5}(?:-\d{4})?))?  # Optional ZIP code
    (?:,\s*USA)?                    # Optional ", USA" suffix from Google
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# US state name → abbreviation map (for addresses that spell out the state)
_STATE_ABBR = {
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
}


class AddressParser:
    """
    Splits a single-line US address into its component parts.
    Returns a dict with keys: street, city, state, zip.
    """

    def parse(self, address: str) -> dict:
        """
        Parse *address* and return a dict:
            {"street": "...", "city": "...", "state": "TX", "zip": "78701"}

        Missing fields are returned as empty strings.
        """
        result = {"street": "", "city": "", "state": "", "zip": ""}

        if not address or not address.strip():
            return result

        address = address.strip()

        # Try the main regex
        m = _ADDRESS_RE.match(address)
        if m:
            result["street"] = m.group("street").strip()
            result["city"]   = m.group("city").strip()
            result["state"]  = (m.group("state") or "").upper().strip()
            result["zip"]    = (m.group("zip")   or "").strip()
            return result

        # Fallback: split on commas and do best-effort parsing
        parts = [p.strip() for p in address.split(",") if p.strip()]
        if len(parts) >= 3:
            result["street"] = parts[0]
            result["city"]   = parts[1]
            # Last component might be "TX 78701" or just "TX"
            state_zip = parts[-1].strip()
            # Remove "USA" if present
            state_zip = re.sub(r"\bUSA\b", "", state_zip, flags=re.IGNORECASE).strip()
            tokens = state_zip.split()
            if tokens:
                state_token = tokens[0].upper()
                # Convert full state name to abbreviation if needed
                result["state"] = _STATE_ABBR.get(state_token.lower(), state_token)
            if len(tokens) >= 2:
                zip_token = tokens[1]
                if re.match(r"^\d{5}(-\d{4})?$", zip_token):
                    result["zip"] = zip_token
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
        """
        parsed = self.parse(address)
        if not parsed["city"]:
            parsed["city"]  = config_location.get("city", "")
        if not parsed["state"]:
            parsed["state"] = config_location.get("state", "")
        return parsed
