"""
SQLite Handler -- local database for lead storage and deduplication.

Uses Python's built-in sqlite3 module (no extra install needed).

Responsibilities
----------------
* Persist every scraped lead to a local SQLite file.
* Deduplicate leads before they reach Google Sheets.
* Track scraping sessions and provide run-history statistics.
* Allow "re-export all" without re-scraping.

Database schema
---------------
leads       -- one row per unique business
sessions    -- one row per scraping run with summary stats
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# -- Schema DDL -------------------------------------------------------

_CREATE_LEADS = """
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key       TEXT    UNIQUE NOT NULL,
    niche           TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    phone           TEXT    DEFAULT '',
    secondary_phone TEXT    DEFAULT '',
    address         TEXT    DEFAULT '',
    city            TEXT    DEFAULT '',
    state           TEXT    DEFAULT '',
    zip_code        TEXT    DEFAULT '',
    hours           TEXT    DEFAULT '',
    review_count    INTEGER DEFAULT 0,
    rating          TEXT    DEFAULT '',
    gmb_link        TEXT    DEFAULT '',
    website         TEXT    DEFAULT '',
    facebook        TEXT    DEFAULT '',
    instagram       TEXT    DEFAULT '',
    data_source     TEXT    DEFAULT 'Google Maps',
    date_added      TEXT    NOT NULL,
    lead_score      INTEGER DEFAULT 0,
    pitch_notes     TEXT    DEFAULT '',
    additional_notes TEXT   DEFAULT '',
    call_status     TEXT    DEFAULT '',
    follow_up_date  TEXT    DEFAULT '',
    exported        INTEGER DEFAULT 0,   -- 1 = already in Google Sheets
    raw_json        TEXT    DEFAULT ''   -- backup of the original dict
);
"""

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    niches_searched TEXT,
    total_scraped   INTEGER DEFAULT 0,
    new_leads       INTEGER DEFAULT 0,
    duplicates      INTEGER DEFAULT 0,
    errors          INTEGER DEFAULT 0,
    config_snapshot TEXT
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_leads_niche   ON leads (niche);",
    "CREATE INDEX IF NOT EXISTS idx_leads_city    ON leads (city);",
    "CREATE INDEX IF NOT EXISTS idx_leads_score   ON leads (lead_score DESC);",
    "CREATE INDEX IF NOT EXISTS idx_leads_exported ON leads (exported);",
]


class SQLiteHandler:
    """
    Thread-safe SQLite wrapper for LeadParser.
    Use as a context manager or call open()/close() manually.
    """

    def __init__(self, config: dict):
        db_path = Path(config["database"]["path"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path    = str(db_path)
        self.dedup_key  = config["database"].get("dedup_key", "name_city")
        self._conn: Optional[sqlite3.Connection] = None
        self._session_id: Optional[int] = None

    # -- Context manager -----------------------------------------------

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    def open(self):
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._create_schema()
        logger.info(f"Database opened: {self.db_path}")

    def close(self):
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    # -- Schema setup --------------------------------------------------

    def _create_schema(self):
        cur = self._conn.cursor()
        cur.execute(_CREATE_LEADS)
        cur.execute(_CREATE_SESSIONS)
        for idx_sql in _CREATE_INDEXES:
            cur.execute(idx_sql)
        self._conn.commit()

    # -- Session tracking ----------------------------------------------

    def start_session(self, niches: list[str], config: dict) -> int:
        """Record the start of a scraping run; return the session ID."""
        cur = self._conn.cursor()
        cur.execute(
            """INSERT INTO sessions (started_at, niches_searched, config_snapshot)
               VALUES (?, ?, ?)""",
            (
                datetime.now().isoformat(),
                json.dumps(niches),
                json.dumps({k: v for k, v in config.items()
                            if k not in ("pitch_templates",)})  # keep snapshot small
            ),
        )
        self._conn.commit()
        self._session_id = cur.lastrowid
        return self._session_id

    def end_session(self, stats: dict):
        """Record end-of-run statistics for the current session."""
        if not self._session_id:
            return
        self._conn.execute(
            """UPDATE sessions
               SET finished_at    = ?,
                   total_scraped  = ?,
                   new_leads      = ?,
                   duplicates     = ?,
                   errors         = ?
               WHERE id = ?""",
            (
                datetime.now().isoformat(),
                stats.get("total",      0),
                stats.get("new",        0),
                stats.get("duplicates", 0),
                stats.get("errors",     0),
                self._session_id,
            ),
        )
        self._conn.commit()

    # -- Lead persistence ----------------------------------------------

    def insert_lead(self, lead: dict) -> tuple[bool, str]:
        """
        Insert *lead* if it is not a duplicate.

        Returns (True, dedup_key) if inserted, (False, dedup_key) if duplicate.
        """
        key = self._make_dedup_key(lead)

        try:
            self._conn.execute(
                """INSERT INTO leads (
                       dedup_key, niche, name, phone, secondary_phone,
                       address, city, state, zip_code, hours,
                       review_count, rating, gmb_link, website,
                       facebook, instagram, data_source, date_added,
                       lead_score, pitch_notes, additional_notes,
                       call_status, follow_up_date, raw_json
                   ) VALUES (
                       :dedup_key, :niche, :name, :phone, :secondary_phone,
                       :address, :city, :state, :zip_code, :hours,
                       :review_count, :rating, :gmb_link, :website,
                       :facebook, :instagram, :data_source, :date_added,
                       :lead_score, :pitch_notes, :additional_notes,
                       :call_status, :follow_up_date, :raw_json
                   )""",
                {
                    "dedup_key":       key,
                    "niche":           lead.get("niche",            ""),
                    "name":            lead.get("name",             ""),
                    "phone":           lead.get("phone",            ""),
                    "secondary_phone": lead.get("secondary_phone",  ""),
                    "address":         lead.get("address",          ""),
                    "city":            lead.get("city",             ""),
                    "state":           lead.get("state",            ""),
                    "zip_code":        lead.get("zip_code",         ""),
                    "hours":           lead.get("hours",            ""),
                    "review_count":    lead.get("review_count",     0),
                    "rating":          str(lead.get("rating",       "")),
                    "gmb_link":        lead.get("gmb_link",         ""),
                    "website":         lead.get("website",          ""),
                    "facebook":        lead.get("facebook",         ""),
                    "instagram":       lead.get("instagram",        ""),
                    "data_source":     lead.get("data_source",      "Google Maps"),
                    "date_added":      lead.get("date_added",       datetime.now().strftime("%Y-%m-%d")),
                    "lead_score":      lead.get("lead_score",       0),
                    "pitch_notes":     lead.get("pitch_notes",      ""),
                    "additional_notes":lead.get("additional_notes", ""),
                    "call_status":     "",
                    "follow_up_date":  "",
                    "raw_json":        json.dumps(lead),
                },
            )
            self._conn.commit()
            return (True, key)

        except sqlite3.IntegrityError:
            # Duplicate -- unique constraint on dedup_key
            return (False, key)

    def bulk_insert(self, leads: list[dict]) -> dict:
        """
        Insert multiple leads.  Returns stats dict with counts.
        """
        stats = {"new": 0, "duplicates": 0, "errors": 0}
        for lead in leads:
            try:
                inserted, _ = self.insert_lead(lead)
                if inserted:
                    stats["new"] += 1
                else:
                    stats["duplicates"] += 1
            except Exception as exc:
                logger.error(f"DB insert error for '{lead.get('name', '?')}': {exc}")
                stats["errors"] += 1
        return stats

    # -- Queries -------------------------------------------------------

    def get_all_leads(self, min_score: int = 0) -> list[dict]:
        """Return all leads with score >= *min_score*, sorted by niche then score."""
        rows = self._conn.execute(
            """SELECT * FROM leads
               WHERE lead_score >= ?
               ORDER BY niche ASC, lead_score DESC""",
            (min_score,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_unexported_leads(self, min_score: int = 0) -> list[dict]:
        """Return leads that haven't been exported to Google Sheets yet."""
        rows = self._conn.execute(
            """SELECT * FROM leads
               WHERE exported = 0 AND lead_score >= ?
               ORDER BY niche ASC, lead_score DESC""",
            (min_score,),
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_exported(self, lead_ids: list[int]):
        """Mark a list of lead IDs as exported."""
        if not lead_ids:
            return
        placeholders = ",".join("?" * len(lead_ids))
        self._conn.execute(
            f"UPDATE leads SET exported = 1 WHERE id IN ({placeholders})",
            lead_ids,
        )
        self._conn.commit()

    def count_by_niche(self) -> dict[str, int]:
        """Return {niche: count} mapping for the summary sheet."""
        rows = self._conn.execute(
            "SELECT niche, COUNT(*) as cnt FROM leads GROUP BY niche"
        ).fetchall()
        return {row["niche"]: row["cnt"] for row in rows}

    def avg_score_by_niche(self) -> dict[str, float]:
        """Return {niche: avg_score} for the summary sheet."""
        rows = self._conn.execute(
            "SELECT niche, AVG(lead_score) as avg FROM leads GROUP BY niche"
        ).fetchall()
        return {row["niche"]: round(row["avg"], 1) for row in rows}

    def is_duplicate(self, lead: dict) -> bool:
        """Check without inserting whether this lead already exists."""
        key = self._make_dedup_key(lead)
        row = self._conn.execute(
            "SELECT 1 FROM leads WHERE dedup_key = ?", (key,)
        ).fetchone()
        return row is not None

    # -- Deduplication key ---------------------------------------------

    def _make_dedup_key(self, lead: dict) -> str:
        """
        Generate a stable deduplication hash from business name + city.
        Case-insensitive and strips extra whitespace.
        """
        name = (lead.get("name", "") or "").lower().strip()
        city = (lead.get("city", "") or "").lower().strip()
        raw  = f"{name}|{city}"
        return hashlib.md5(raw.encode()).hexdigest()
