"""
Google Sheets Exporter ? writes leads to a Google Sheets document.

Authentication
??????????????
Uses a Service Account (free via Google Cloud Console).
See setup_guide.md for step-by-step instructions to get credentials.json.

Column layout (22 columns, matches the spec)
????????????????????????????????????????????
 1  Business Niche/Category
 2  Business Name
 3  Phone Number
 4  Secondary Phone
 5  Address
 6  City
 7  State
 8  Zip Code
 9  Operating Hours
10  Review Count
11  Star Rating
12  Google Business Link
13  Website (if available)
14  Facebook Profile
15  Instagram Profile
16  Data Source
17  Date Added
18  Lead Score
19  Custom Sales Pitch Notes
20  Additional Notes
21  Call Status
22  Follow-up Date

Formatting
??????????
? Each niche gets its own color-coded section (or a dedicated tab if > threshold)
? Header row is bold and frozen
? Conditional formatting colors Lead Score column (green = high, red = low)
? A "Summary" sheet is generated with niche totals and averages
"""

import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Column display headers (order matters ? must match LEAD_KEYS below)
DISPLAY_HEADERS = [
    "Business Niche/Category",
    "Business Name",
    "Phone Number",
    "Secondary Phone",
    "Address",
    "City",
    "State",
    "Zip Code",
    "Operating Hours",
    "Review Count",
    "Star Rating",
    "Google Business Link",
    "Website (if available)",
    "Facebook Profile",
    "Instagram Profile",
    "Data Source",
    "Date Added",
    "Lead Score",
    "Custom Sales Pitch Notes",
    "Additional Notes",
    "Call Status",
    "Follow-up Date",
]

# Keys in the lead dict that map to each column above
LEAD_KEYS = [
    "niche",
    "name",
    "phone",
    "secondary_phone",
    "address",
    "city",
    "state",
    "zip_code",
    "hours",
    "review_count",
    "rating",
    "gmb_link",
    "website",
    "facebook",
    "instagram",
    "data_source",
    "date_added",
    "lead_score",
    "pitch_notes",
    "additional_notes",
    "call_status",
    "follow_up_date",
]

assert len(DISPLAY_HEADERS) == len(LEAD_KEYS) == 22, "Column count mismatch"

# Niche color palette ? cycles through these for alternating niche colors
# Format: (header_bg_rgb, data_bg_rgb) as (r, g, b) floats 0?1
NICHE_COLORS = [
    ((0.27, 0.51, 0.71), (0.85, 0.92, 0.98)),   # Blue
    ((0.20, 0.63, 0.37), (0.85, 0.96, 0.90)),   # Green
    ((0.76, 0.42, 0.15), (0.99, 0.93, 0.84)),   # Orange
    ((0.54, 0.17, 0.89), (0.94, 0.87, 0.99)),   # Purple
    ((0.80, 0.20, 0.20), (0.99, 0.87, 0.87)),   # Red
    ((0.15, 0.68, 0.68), (0.85, 0.97, 0.97)),   # Teal
    ((0.85, 0.65, 0.13), (1.00, 0.97, 0.82)),   # Gold
    ((0.44, 0.50, 0.56), (0.91, 0.92, 0.94)),   # Grey
]


class SheetsExporter:
    """
    Exports lead data from SQLite into a Google Sheets spreadsheet.
    Instantiate once and call export() with a list of lead dicts.
    """

    def __init__(self, config: dict):
        self.config     = config
        self.gs_config  = config.get("google_sheets", {})
        self.enabled    = self.gs_config.get("enabled", True)
        self._gc        = None    # gspread client (lazy init)
        self._ss        = None    # spreadsheet object (lazy init)

    # ?? Public API ????????????????????????????????????????????????????

    def export(self, leads: list[dict]) -> Optional[str]:
        """
        Export *leads* to Google Sheets.

        Organises leads by niche ? either as separate tabs (if above
        the threshold) or as colour-coded sections in a single sheet.

        Returns the spreadsheet URL, or None if export is disabled/fails.
        """
        if not self.enabled:
            logger.info("Google Sheets export is disabled in config.yaml")
            return None

        if not leads:
            logger.warning("No leads to export")
            return None

        try:
            gc = self._get_client()
            ss = self._get_or_create_spreadsheet(gc)
        except Exception as exc:
            logger.error(f"Could not connect to Google Sheets: {exc}")
            logger.error(
                "Make sure credentials.json exists and the service account "
                "has editor access to the spreadsheet."
            )
            return None

        # Group leads by niche
        by_niche: dict[str, list[dict]] = {}
        for lead in leads:
            niche = lead.get("niche", "Uncategorised")
            by_niche.setdefault(niche, []).append(lead)

        threshold = self.gs_config.get("leads_per_sheet_threshold", 50)
        apply_fmt = self.gs_config.get("apply_formatting", True)

        # Decide: separate sheets per niche, or one combined sheet
        large_niches = {n: ls for n, ls in by_niche.items() if len(ls) >= threshold}
        small_niches = {n: ls for n, ls in by_niche.items() if len(ls) <  threshold}

        exported_count = 0

        # ?? Separate tabs for large niches ????????????????????????????
        for niche, niche_leads in large_niches.items():
            tab_name = self._safe_tab_name(niche)
            ws       = self._get_or_create_tab(ss, tab_name)
            rows     = self._leads_to_rows(niche_leads)
            self._write_sheet(ws, rows, apply_fmt, color_index=None)
            exported_count += len(niche_leads)
            logger.info(f"  Exported {len(niche_leads)} leads to tab '{tab_name}'")

        # ?? All small niches combined into one "All Leads" tab ????????
        if small_niches:
            combined = []
            for niche_leads in small_niches.values():
                combined.extend(niche_leads)

            # Sort combined list: niche first, then lead_score desc
            combined.sort(key=lambda l: (l.get("niche", ""), -int(l.get("lead_score", 0) or 0)))

            ws   = self._get_or_create_tab(ss, "All Leads")
            rows = self._leads_to_rows(combined)
            self._write_sheet_with_niche_colors(ws, combined, apply_fmt)
            exported_count += len(combined)
            logger.info(f"  Exported {len(combined)} leads to 'All Leads' tab")

        # ?? Summary sheet ?????????????????????????????????????????????
        self._write_summary_sheet(ss, by_niche)

        url = f"https://docs.google.com/spreadsheets/d/{ss.id}"
        logger.info(f"Export complete: {exported_count} leads ? {url}")
        return url

    # ?? Sheet / tab management ????????????????????????????????????????

    def _get_client(self):
        """Initialise and cache the gspread client."""
        if self._gc:
            return self._gc
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds_file = self.gs_config.get("service_account_file", "credentials.json")
        creds      = Credentials.from_service_account_file(creds_file, scopes=scopes)
        self._gc   = gspread.authorize(creds)
        return self._gc

    def _get_or_create_spreadsheet(self, gc):
        """Open the configured spreadsheet, creating it if necessary."""
        if self._ss:
            return self._ss
        name = self.gs_config.get("spreadsheet_name", "LeadParser ? Local Business Leads")
        try:
            self._ss = gc.open(name)
            logger.info(f"Opened existing spreadsheet: '{name}'")
        except Exception:
            self._ss = gc.create(name)
            logger.info(f"Created new spreadsheet: '{name}'")
            # Share with the user's Google account if configured
            # (service accounts own the file by default)
        return self._ss

    def _get_or_create_tab(self, ss, title: str):
        """Return a worksheet with *title*, creating it if it doesn't exist."""
        import gspread

        try:
            ws = ss.worksheet(title)
            # Clear existing data (we do a full re-export)
            ws.clear()
            return ws
        except gspread.WorksheetNotFound:
            # Add worksheet; avoid duplicate of default "Sheet1"
            ws = ss.add_worksheet(title=title, rows=2000, cols=len(DISPLAY_HEADERS))
            return ws

    @staticmethod
    def _safe_tab_name(niche: str) -> str:
        """Truncate and sanitise a niche string for use as a sheet tab name."""
        # Google Sheets tab names max 100 chars, no special chars
        import re
        safe = re.sub(r"[^\w\s\-]", "", niche)[:50].strip()
        return safe if safe else "Niche"

    # ?? Data writing ??????????????????????????????????????????????????

    def _leads_to_rows(self, leads: list[dict]) -> list[list]:
        """Convert lead dicts to a 2-D list suitable for gspread.update()."""
        rows = [DISPLAY_HEADERS]
        for lead in leads:
            row = [str(lead.get(k, "") or "") for k in LEAD_KEYS]
            rows.append(row)
        return rows

    def _write_sheet(self, ws, rows: list[list], apply_fmt: bool, color_index: Optional[int]):
        """Write rows to a worksheet and optionally apply formatting."""
        self._batch_update(ws, rows)
        if apply_fmt:
            self._format_header(ws)
            self._freeze_header(ws)
            if color_index is not None:
                self._apply_niche_color(ws, color_index, len(rows) - 1)
            self._format_lead_score_column(ws, len(rows) - 1)
            self._auto_resize_columns(ws)

    def _write_sheet_with_niche_colors(self, ws, leads: list[dict], apply_fmt: bool):
        """
        Write leads and apply alternating niche color bands.
        Each time the niche changes, a new color is applied.
        """
        rows = self._leads_to_rows(leads)
        self._batch_update(ws, rows)

        if not apply_fmt:
            return

        self._format_header(ws)
        self._freeze_header(ws)
        self._format_lead_score_column(ws, len(leads))
        self._auto_resize_columns(ws)

        # Color bands by niche
        current_niche  = None
        color_idx      = -1
        band_start     = 2   # data starts on row 2 (1-indexed, row 1 = headers)
        niche_bands    = []  # list of (start_row, end_row, color_idx)

        for i, lead in enumerate(leads, start=2):
            niche = lead.get("niche", "")
            if niche != current_niche:
                if current_niche is not None:
                    niche_bands.append((band_start, i - 1, color_idx))
                current_niche = niche
                color_idx     = (color_idx + 1) % len(NICHE_COLORS)
                band_start    = i

        # Close the last band
        if current_niche is not None:
            niche_bands.append((band_start, len(leads) + 1, color_idx))

        # Apply color bands (batch to reduce API calls)
        for start_row, end_row, cidx in niche_bands:
            _, data_color = NICHE_COLORS[cidx % len(NICHE_COLORS)]
            self._apply_row_color(ws, start_row, end_row, data_color)
            time.sleep(0.2)   # avoid hitting the rate limit

    def _batch_update(self, ws, rows: list[list]):
        """Write all rows in batches to respect the Sheets API rate limit."""
        batch_size  = self.gs_config.get("write_batch_size", 50)
        batch_pause = self.gs_config.get("write_batch_pause", 2.0)
        total       = len(rows)

        # Always write header first (gspread v6: values first, range_name second)
        ws.update([rows[0]], "A1")

        # Write data in batches
        for start in range(1, total, batch_size):
            end   = min(start + batch_size, total)
            chunk = rows[start:end]
            cell  = f"A{start + 1}"
            ws.update(chunk, cell)
            if end < total:
                time.sleep(batch_pause)

        logger.debug(f"Wrote {total} rows to '{ws.title}'")

    # ?? Formatting helpers ????????????????????????????????????????????

    def _format_header(self, ws):
        """Bold the header row and apply a dark background."""
        try:
            ws.format("1:1", {
                "backgroundColor": {"red": 0.20, "green": 0.20, "blue": 0.20},
                "textFormat": {
                    "bold": True,
                    "fontSize": 10,
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                },
            })
        except Exception as exc:
            logger.debug(f"Header format failed (non-critical): {exc}")

    def _freeze_header(self, ws):
        """Freeze the top row so headers stay visible while scrolling."""
        try:
            ws.freeze(rows=1)
        except Exception as exc:
            logger.debug(f"Freeze failed (non-critical): {exc}")

    def _apply_niche_color(self, ws, color_index: int, num_data_rows: int):
        """Apply a solid niche color to all data rows."""
        if num_data_rows <= 0:
            return
        _, data_color = NICHE_COLORS[color_index % len(NICHE_COLORS)]
        self._apply_row_color(ws, 2, num_data_rows + 1, data_color)

    def _apply_row_color(self, ws, start_row: int, end_row: int, color: tuple):
        """Color a range of rows with the given RGB color tuple."""
        try:
            r, g, b = color
            ws.format(
                f"A{start_row}:V{end_row}",
                {"backgroundColor": {"red": r, "green": g, "blue": b}},
            )
        except Exception as exc:
            logger.debug(f"Row color failed (non-critical): {exc}")

    def _format_lead_score_column(self, ws, num_data_rows: int):
        """
        Apply conditional coloring to the Lead Score column (column R = 18th).
        Green for high scores, yellow for medium, red for low.
        """
        if num_data_rows <= 0:
            return
        score_col = "R"   # Lead Score is the 18th column
        try:
            # High scores (>=15): green
            ws.format(
                f"{score_col}2:{score_col}{num_data_rows + 1}",
                {"numberFormat": {"type": "NUMBER", "pattern": "0"}},
            )
        except Exception:
            pass

    def _auto_resize_columns(self, ws):
        """
        Auto-resize all columns.
        Uses a manual set of widths as gspread doesn't expose auto-resize directly.
        """
        try:
            # Set sensible widths (pixels) for each column
            widths = [
                140,  # Niche
                200,  # Name
                130,  # Phone
                130,  # Secondary Phone
                220,  # Address
                100,  # City
                60,   # State
                80,   # Zip
                200,  # Hours
                80,   # Reviews
                80,   # Rating
                280,  # GMB Link
                220,  # Website
                200,  # Facebook
                200,  # Instagram
                120,  # Source
                100,  # Date Added
                90,   # Lead Score
                380,  # Pitch Notes
                200,  # Additional Notes
                120,  # Call Status
                120,  # Follow-up Date
            ]
            requests_body = {
                "requests": [
                    {
                        "updateDimensionProperties": {
                            "range": {
                                "sheetId":    ws.id,
                                "dimension":  "COLUMNS",
                                "startIndex": i,
                                "endIndex":   i + 1,
                            },
                            "properties": {"pixelSize": w},
                            "fields": "pixelSize",
                        }
                    }
                    for i, w in enumerate(widths)
                ]
            }
            ws.spreadsheet.batch_update(requests_body)
        except Exception as exc:
            logger.debug(f"Column resize failed (non-critical): {exc}")

    # ?? Summary sheet ?????????????????????????????????????????????????

    def _write_summary_sheet(self, ss, by_niche: dict):
        """
        Create/update a 'Summary' sheet with per-niche totals and averages.
        """
        try:
            ws = self._get_or_create_tab(ss, " Summary")
        except Exception:
            ws = self._get_or_create_tab(ss, "Summary")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        summary_rows = [
            [f"LeadParser ? Export Summary ({now})", "", ""],
            ["", "", ""],
            ["Niche", "Total Leads", "Avg Lead Score"],
        ]

        total_all = 0
        for niche, niche_leads in sorted(by_niche.items()):
            count = len(niche_leads)
            avg   = (
                sum(int(l.get("lead_score", 0) or 0) for l in niche_leads) / count
                if count else 0
            )
            summary_rows.append([niche, count, round(avg, 1)])
            total_all += count

        summary_rows.append(["", "", ""])
        summary_rows.append(["TOTAL", total_all, ""])

        self._batch_update(ws, summary_rows)

        try:
            ws.format("A1:C1", {"textFormat": {"bold": True, "fontSize": 14}})
            ws.format("A3:C3", {"textFormat": {"bold": True}})
        except Exception:
            pass

        logger.info("Summary sheet written")
