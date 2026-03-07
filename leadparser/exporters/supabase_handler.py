"""
supabase_handler.py — Central database handler using Supabase (PostgreSQL)

Replaces sqlite_handler.py. Uses the service role key (bypasses RLS)
so the scraper can insert leads freely. The dashboard uses the anon key
which respects RLS (callers see only their own assigned leads).

Environment variables required (set in .env):
  SUPABASE_URL  = https://your-project.supabase.co
  SUPABASE_KEY  = your-service-role-key   (NOT the anon key)
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger("leadparser.supabase")


# ── Columns sent to Supabase (matches schema exactly) ─────────────────────
LEAD_COLUMNS = [
    "dedup_key",
    "niche", "name", "phone", "secondary_phone",
    "address", "city", "state", "zip_code",
    "hours", "review_count", "rating",
    "gmb_link", "website", "facebook", "instagram",
    "data_source", "lead_score", "pitch_notes", "additional_notes",
    "date_added",
    "email",
]


def _dedup_key(name: str, city: str) -> str:
    """MD5 hash of lowercased name + city — matches SQLite handler logic."""
    raw = f"{name.lower().strip()}|{city.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


class SupabaseHandler:
    """
    Drop-in replacement for SQLiteHandler.
    Use as a context manager or call open()/close() manually.

    Usage:
        with SupabaseHandler() as db:
            stats = db.bulk_insert(leads)
    """

    def __init__(self, config: Optional[dict] = None):
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_KEY", "").strip()

        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_KEY must be set in your .env file.\n"
                "Copy .env.example → .env and fill in your Supabase credentials."
            )

        self.client: Client = create_client(url, key)
        self.config = config or {}
        logger.info("Supabase client initialised")

    # ── Context manager ────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass  # No persistent connection to close with supabase-py

    # ── Session tracking (lightweight — just logs) ─────────────────────────

    def start_session(self, niches: list, config: dict) -> str:
        """Return a session ID string (timestamp-based, not persisted to DB)."""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(
            f"Session {session_id} | niches: {niches} | "
            f"city: {config.get('location', {}).get('city', '?')}"
        )
        return session_id

    def end_session(self, stats: dict):
        logger.info(f"Session complete | stats: {stats}")

    # ── Core insert ────────────────────────────────────────────────────────

    def bulk_insert(self, leads: list[dict]) -> dict:
        """
        Upsert leads into Supabase.
        On conflict with dedup_key: skip (do nothing) — never overwrite.
        Returns {new, duplicates, errors}.
        """
        stats = {"new": 0, "duplicates": 0, "errors": 0}

        if not leads:
            return stats

        rows = []
        for lead in leads:
            try:
                row = self._prepare_row(lead)
                rows.append(row)
            except Exception as exc:
                logger.warning(f"Row prep failed for '{lead.get('name')}': {exc}")
                stats["errors"] += 1

        if not rows:
            return stats

        # Batch upsert in chunks of 100
        CHUNK = 100
        for i in range(0, len(rows), CHUNK):
            chunk = rows[i : i + CHUNK]
            try:
                result = (
                    self.client.table("leads")
                    .upsert(chunk, on_conflict="dedup_key", ignore_duplicates=True)
                    .execute()
                )
                # supabase-py returns inserted rows only (duplicates are skipped)
                inserted = len(result.data) if result.data else 0
                skipped  = len(chunk) - inserted
                stats["new"]        += inserted
                stats["duplicates"] += skipped
                logger.info(
                    f"Chunk {i//CHUNK + 1}: {inserted} new, {skipped} dupes"
                )
            except Exception as exc:
                logger.error(f"Bulk insert chunk failed: {exc}")
                stats["errors"] += len(chunk)

        return stats

    # ── Compatibility shims (used in main.py export paths) ─────────────────

    def get_all_leads(self, min_score: int = 0) -> list[dict]:
        """Fetch all leads at or above min_score. Used for CSV export."""
        try:
            result = (
                self.client.table("leads")
                .select("*")
                .gte("lead_score", min_score)
                .order("lead_score", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error(f"get_all_leads failed: {exc}")
            return []

    def get_unexported_leads(self, min_score: int = 0) -> list[dict]:
        """
        Supabase replaces Google Sheets — this now returns unassigned leads.
        Called in main.py for the optional Sheets export path (now skipped).
        """
        try:
            result = (
                self.client.table("leads")
                .select("*")
                .gte("lead_score", min_score)
                .is_("assigned_to", "null")
                .order("lead_score", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error(f"get_unexported_leads failed: {exc}")
            return []

    def mark_exported(self, ids: list):
        """No-op — kept for compatibility. Supabase doesn't use 'exported' flag."""
        pass

    # ── Private helpers ────────────────────────────────────────────────────

    def _prepare_row(self, lead: dict) -> dict:
        """Map a canonical lead dict to a Supabase-ready row dict."""
        name = (lead.get("name") or "").strip()
        city = (lead.get("city") or "").strip()

        row = {
            "dedup_key":        _dedup_key(name, city),
            "niche":            (lead.get("niche")            or "").strip(),
            "name":             name,
            "phone":            (lead.get("phone")            or "").strip(),
            "secondary_phone":  (lead.get("secondary_phone")  or "").strip(),
            "address":          (lead.get("address")          or "").strip(),
            "city":             city,
            "state":            (lead.get("state")            or "").strip(),
            "zip_code":         (lead.get("zip_code")         or "").strip(),
            "hours":            (lead.get("hours")            or "").strip(),
            "review_count":     int(lead.get("review_count", 0) or 0),
            "rating":           str(lead.get("rating", "")    or ""),
            "gmb_link":         (lead.get("gmb_link")         or "").strip(),
            "website":          (lead.get("website")          or "").strip(),
            "facebook":         (lead.get("facebook")         or "").strip(),
            "instagram":        (lead.get("instagram")        or "").strip(),
            "data_source":      (lead.get("data_source")      or "Google Maps").strip(),
            "lead_score":       int(lead.get("lead_score", 0) or 0),
            "pitch_notes":      (lead.get("pitch_notes")      or "").strip(),
            "additional_notes": (lead.get("additional_notes") or "").strip(),
            "date_added":       lead.get("date_added") or datetime.now().strftime("%Y-%m-%d"),
            "email":            (lead.get("email") or "").strip(),
        }

        # Must have a name + niche to be valid
        if not row["name"] or not row["niche"]:
            raise ValueError(f"Lead missing name or niche: {lead}")

        return row
