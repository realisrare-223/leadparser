"""
Phone Validator — normalises and validates US phone numbers.

Uses the `phonenumbers` library (free, no API required) which
implements the same logic as Google's libphonenumber.
"""

import re
import logging
import phonenumbers
from phonenumbers import NumberParseException

logger = logging.getLogger(__name__)

# Regex to extract a candidate phone number from arbitrary text
_PHONE_RE = re.compile(
    r"""
    (?:
        \+?1[\s.\-]?          # optional country code
    )?
    \(?(\d{3})\)?             # area code
    [\s.\-]?
    (\d{3})                   # exchange
    [\s.\-]?
    (\d{4})                   # subscriber
    """,
    re.VERBOSE,
)


class PhoneValidator:
    """
    Provides phone number extraction, validation, and formatting.

    All methods are stateless — create one instance and reuse it.
    """

    def __init__(self, default_region: str = "US"):
        self.default_region = default_region

    # ── Public API ───────────────────────────────────────────────────

    def format(self, raw: str) -> str:
        """
        Parse *raw* and return a consistently formatted US phone number
        in (XXX) XXX-XXXX format, or an empty string if parsing fails.
        """
        if not raw:
            return ""

        raw = raw.strip()

        # Try phonenumbers library first (most accurate)
        try:
            pn = phonenumbers.parse(raw, self.default_region)
            if phonenumbers.is_valid_number(pn):
                return phonenumbers.format_number(
                    pn, phonenumbers.PhoneNumberFormat.NATIONAL
                )
        except NumberParseException:
            pass

        # Fall back to regex extraction
        match = _PHONE_RE.search(raw)
        if match:
            area, exch, subs = match.groups()
            candidate = f"+1{area}{exch}{subs}"
            try:
                pn = phonenumbers.parse(candidate, self.default_region)
                if phonenumbers.is_valid_number(pn):
                    return phonenumbers.format_number(
                        pn, phonenumbers.PhoneNumberFormat.NATIONAL
                    )
            except NumberParseException:
                pass

        logger.debug(f"Could not parse phone number: {raw!r}")
        return ""

    def extract_from_text(self, text: str) -> list[str]:
        """
        Find all phone-number-like patterns in *text* and return a
        deduplicated list of formatted phone numbers.
        """
        results = []
        seen = set()
        for match in _PHONE_RE.finditer(text):
            area, exch, subs = match.groups()
            candidate = f"+1{area}{exch}{subs}"
            try:
                pn = phonenumbers.parse(candidate, self.default_region)
                if phonenumbers.is_valid_number(pn):
                    formatted = phonenumbers.format_number(
                        pn, phonenumbers.PhoneNumberFormat.NATIONAL
                    )
                    if formatted not in seen:
                        seen.add(formatted)
                        results.append(formatted)
            except NumberParseException:
                continue
        return results

    def is_valid(self, raw: str) -> bool:
        """Return True if *raw* is a valid US phone number."""
        return bool(self.format(raw))

    def to_e164(self, raw: str) -> str:
        """
        Return the E.164 format (+12025551234) or empty string.
        Useful if you ever integrate with a dialling/SMS API.
        """
        try:
            pn = phonenumbers.parse(raw, self.default_region)
            if phonenumbers.is_valid_number(pn):
                return phonenumbers.format_number(
                    pn, phonenumbers.PhoneNumberFormat.E164
                )
        except NumberParseException:
            pass
        return ""
