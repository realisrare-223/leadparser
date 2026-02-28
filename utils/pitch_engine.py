"""
Pitch Engine — generates personalised sales pitch notes for each lead.

Templates are defined in config.yaml → pitch_templates.
Placeholders supported: {name}, {city}, {niche}, {review_count}, {rating}.

The engine tries:
  1. Exact niche match (e.g. "plumbers")
  2. Partial niche match  (e.g. "HVAC" in "HVAC contractors")
  3. Default template
"""

import logging
from string import Formatter

logger = logging.getLogger(__name__)


class PitchEngine:
    """
    Generates niche-specific sales pitch notes for cold-calling.
    Instantiate once with the config dict; call generate() per lead.
    """

    def __init__(self, config: dict):
        self.templates: dict = config.get("pitch_templates", {})
        self.location:  dict = config.get("location", {})

    # ── Public API ───────────────────────────────────────────────────

    def generate(self, niche: str, raw: dict, config: dict) -> str:
        """
        Build and return the pitch text for a single lead.

        Parameters
        ----------
        niche : the search niche (e.g. "plumbers")
        raw   : scraped data dict
        config: full config (for fallback city/state if needed)
        """
        template = self._pick_template(niche)
        context  = self._build_context(niche, raw, config)

        try:
            return template.format(**context).strip()
        except KeyError as exc:
            logger.warning(f"Missing placeholder {exc} in pitch template for '{niche}'")
            # Return the template with unfilled placeholders rather than crashing
            return self._safe_format(template, context).strip()

    # ── Template selection ────────────────────────────────────────────

    def _pick_template(self, niche: str) -> str:
        """
        Find the best matching template for *niche*.
        Falls back to 'default' if nothing matches.
        """
        niche_lower = niche.lower()

        # 1. Exact match
        if niche in self.templates:
            return self.templates[niche]

        # 2. Case-insensitive exact match
        for key, tmpl in self.templates.items():
            if key.lower() == niche_lower:
                return tmpl

        # 3. Partial match (niche contains key, or key contains niche)
        for key, tmpl in self.templates.items():
            if key.lower() in niche_lower or niche_lower in key.lower():
                return tmpl

        # 4. Default fallback
        return self.templates.get("default", (
            "Hi {name}, I help local businesses in {city} grow their "
            "customer base through better online presence. Would you have "
            "10 minutes to chat?"
        ))

    # ── Context building ──────────────────────────────────────────────

    def _build_context(self, niche: str, raw: dict, config: dict) -> dict:
        """Assemble the substitution dict for the template."""
        name          = raw.get("name", "there")
        city          = raw.get("city") or config.get("location", {}).get("city", "your city")
        review_count  = raw.get("review_count", 0) or 0
        rating        = raw.get("rating", "") or ""

        return {
            "name":         name if name else "there",
            "city":         city,
            "niche":        niche,
            "review_count": str(review_count),
            "rating":       str(rating),
        }

    # ── Safe formatter (never raises) ────────────────────────────────

    @staticmethod
    def _safe_format(template: str, context: dict) -> str:
        """
        Format *template* replacing only keys that exist in *context*;
        leave unresolved {placeholders} as-is rather than raising.
        """
        result = template
        for key, value in context.items():
            result = result.replace("{" + key + "}", str(value))
        return result

    # ── Utility ───────────────────────────────────────────────────────

    def list_niches_with_templates(self) -> list[str]:
        """Return the list of niches that have explicit templates."""
        return [k for k in self.templates if k != "default"]
