#!/usr/bin/env python3
"""
LeadParser Dashboard — Localhost web viewer for scraped leads.
=============================================================
Shows ONLY businesses WITHOUT a website (highest-need prospects).
Reads data/leads_latest.csv on every page load — always up to date.

Usage:
  python dashboard.py                          # default http://localhost:5000
  python dashboard.py --port 8080              # custom port
  python dashboard.py --csv path/to/file.csv   # custom CSV path
  python dashboard.py --open                   # auto-open browser on start
"""

import argparse
import csv
import webbrowser
from pathlib import Path
from threading import Timer

try:
    from flask import Flask, render_template_string, jsonify
except ImportError:
    raise SystemExit(
        "[!] Flask is required: pip install flask\n"
        "    Or: pip install -r requirements.txt"
    )

app = Flask(__name__)

# Set by CLI args at startup
_csv_path: str = "data/leads_latest.csv"

# ── Score helpers ────────────────────────────────────────────────────────

def _score(lead: dict) -> int:
    try:
        return int(lead.get("Lead Score", 0) or 0)
    except (ValueError, TypeError):
        return 0


def _tier(score: int) -> tuple[str, str]:
    """Return (css-class, label) for a given score."""
    if score >= 18:
        return "hot",    "HOT"
    if score >= 12:
        return "warm",   "WARM"
    if score >= 7:
        return "medium", "MED"
    return "low", "LOW"


# ── Data loading ─────────────────────────────────────────────────────────

def load_leads() -> list[dict]:
    """
    Load the CSV and return only rows that have NO website.
    Sorted by Lead Score descending.
    """
    path = Path(_csv_path)
    if not path.exists():
        return []

    leads = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            website = (row.get("Website (if available)") or "").strip()
            if not website:
                leads.append(row)

    leads.sort(key=_score, reverse=True)
    return leads


def compute_stats(leads: list[dict]) -> dict:
    scores = [_score(l) for l in leads]
    niches = sorted({
        l.get("Business Niche/Category", "").strip()
        for l in leads
        if l.get("Business Niche/Category", "").strip()
    })
    return {
        "total":  len(leads),
        "hot":    sum(1 for s in scores if s >= 18),
        "warm":   sum(1 for s in scores if 12 <= s < 18),
        "medium": sum(1 for s in scores if 7  <= s < 12),
        "low":    sum(1 for s in scores if s  < 7),
        "niches": niches,
    }


# ── HTML template ─────────────────────────────────────────────────────────

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LeadParser Dashboard</title>

  <!-- Bootstrap 5 -->
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <!-- DataTables -->
  <link rel="stylesheet"
        href="https://cdn.datatables.net/1.13.8/css/dataTables.bootstrap5.min.css">

  <style>
    :root {
      --bg:       #0d1117;
      --surface:  #161b27;
      --card:     #1c2236;
      --border:   #2a3050;
      --accent:   #00d4ff;
      --text:     #c9d1d9;
      --muted:    #6e7a96;
      --hot:      #ff4d4d;
      --warm:     #ff9f43;
      --medium:   #feca57;
      --low:      #4a5580;
    }

    * { box-sizing: border-box; }
    body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; }

    /* ── Navbar ── */
    .lp-nav {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 10px 24px;
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .lp-nav .brand   { font-weight: 700; font-size: 1.25rem; color: var(--accent); }
    .lp-nav .sub     { font-size: 0.8rem; color: var(--muted); flex: 1; }
    .lp-nav .refresh { font-size: 0.78rem; }

    /* ── Stat cards ── */
    .stats-row { display: flex; gap: 12px; flex-wrap: wrap; padding: 20px 24px 0; }
    .stat-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 22px;
      text-align: center;
      min-width: 100px;
    }
    .stat-number { font-size: 2rem; font-weight: 700; line-height: 1; }
    .stat-label  { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-top: 4px; }
    .c-accent  { color: var(--accent); }
    .c-hot     { color: var(--hot); }
    .c-warm    { color: var(--warm); }
    .c-medium  { color: var(--medium); }
    .c-low     { color: var(--low); }

    /* ── Table wrapper ── */
    .table-section {
      margin: 20px 24px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }
    .table-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      flex-wrap: wrap;
      gap: 8px;
    }
    .table-title { font-size: 0.85rem; color: var(--muted); }
    .csv-path    { font-size: 0.72rem; color: var(--muted); font-family: monospace; }

    /* ── DataTable overrides ── */
    table.dataTable { color: var(--text) !important; }
    table.dataTable thead th {
      background: var(--surface) !important;
      color: var(--accent) !important;
      border-color: var(--border) !important;
      white-space: nowrap;
      font-size: 0.78rem;
      font-weight: 600;
      letter-spacing: 0.5px;
    }
    table.dataTable tbody td { border-color: var(--border) !important; vertical-align: middle; }
    table.dataTable tbody tr:hover td { background: rgba(0, 212, 255, 0.04) !important; }

    /* Row tiers */
    tr.tier-hot    td { background: rgba(255,  77,  77, 0.07) !important; }
    tr.tier-warm   td { background: rgba(255, 159,  67, 0.07) !important; }
    tr.tier-medium td { background: rgba(254, 202,  87, 0.05) !important; }

    /* Score badge */
    .score-badge {
      display: inline-block;
      font-size: 0.7rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 20px;
      white-space: nowrap;
    }
    .badge-hot    { background: var(--hot);    color: #fff; }
    .badge-warm   { background: var(--warm);   color: #111; }
    .badge-medium { background: var(--medium); color: #111; }
    .badge-low    { background: var(--low);    color: #ccc; }

    /* Niche pill */
    .niche-pill {
      font-size: 0.68rem;
      padding: 2px 8px;
      border-radius: 20px;
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--muted);
      white-space: nowrap;
    }

    /* Truncated pitch notes */
    .pitch-cell {
      max-width: 220px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: 0.75rem;
      color: var(--muted);
      cursor: help;
    }

    .gmb-link { color: var(--accent); text-decoration: none; font-size: 0.8rem; }
    .gmb-link:hover { text-decoration: underline; }

    /* DataTables controls */
    .dataTables_filter input,
    .dataTables_length select {
      background: var(--surface) !important;
      color: var(--text) !important;
      border: 1px solid var(--border) !important;
      border-radius: 6px !important;
      padding: 4px 10px !important;
    }
    .dataTables_info, .dataTables_filter label,
    .dataTables_length label { color: var(--muted) !important; font-size: 0.78rem; }

    .page-link { background: var(--surface) !important; border-color: var(--border) !important; color: var(--text) !important; }
    .page-item.active .page-link { background: var(--accent) !important; border-color: var(--accent) !important; color: #111 !important; }

    /* Empty state */
    .empty-state { text-align: center; padding: 60px 20px; color: var(--muted); }
    .empty-state h3 { color: var(--text); margin-bottom: 8px; }
  </style>
</head>
<body>

<!-- Navbar -->
<div class="lp-nav">
  <span class="brand">&#9889; LeadParser Dashboard</span>
  <span class="sub">No-Website Leads &mdash; sorted by score</span>
  <button class="btn btn-outline-info btn-sm refresh" onclick="location.reload()">&#8635; Refresh</button>
</div>

<!-- Stats -->
<div class="stats-row">
  <div class="stat-card">
    <div class="stat-number c-accent">{{ stats.total }}</div>
    <div class="stat-label">Total Leads</div>
  </div>
  <div class="stat-card">
    <div class="stat-number c-hot">{{ stats.hot }}</div>
    <div class="stat-label">&#128293; HOT 18+</div>
  </div>
  <div class="stat-card">
    <div class="stat-number c-warm">{{ stats.warm }}</div>
    <div class="stat-label">&#127777; WARM 12-17</div>
  </div>
  <div class="stat-card">
    <div class="stat-number c-medium">{{ stats.medium }}</div>
    <div class="stat-label">&#11088; MEDIUM 7-11</div>
  </div>
  <div class="stat-card">
    <div class="stat-number c-low">{{ stats.low }}</div>
    <div class="stat-label">LOW &lt;7</div>
  </div>
  <div class="stat-card">
    <div class="stat-number" style="color:#a0aec0;">{{ stats.niches|length }}</div>
    <div class="stat-label">Niches</div>
  </div>
</div>

<!-- Table -->
<div class="table-section">
  <div class="table-header">
    <span class="table-title">
      Businesses without a website &mdash; highest-need prospects
    </span>
    <span class="csv-path">{{ csv_path }}</span>
  </div>

  {% if leads %}
  <div class="table-responsive">
    <table id="leadsTable" class="table table-dark table-sm w-100">
      <thead>
        <tr>
          <th>Score</th>
          <th>Business Name</th>
          <th>Niche</th>
          <th>Phone</th>
          <th>Address</th>
          <th>City</th>
          <th>St</th>
          <th>Reviews</th>
          <th>Rating</th>
          <th>Hours</th>
          <th>GMB</th>
          <th>Pitch Notes</th>
          <th>Notes</th>
          <th>Added</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {% for lead in leads %}
        {% set s = lead['Lead Score']|int %}
        {% if s >= 18 %}{% set tier='hot'    %}{% set lbl='HOT'  %}
        {% elif s >= 12 %}{% set tier='warm'  %}{% set lbl='WARM' %}
        {% elif s >= 7  %}{% set tier='medium'%}{% set lbl='MED'  %}
        {% else          %}{% set tier='low'  %}{% set lbl='LOW'  %}{% endif %}
        <tr class="tier-{{ tier }}">
          <td class="text-center">
            <span class="score-badge badge-{{ tier }}">{{ s }} {{ lbl }}</span>
          </td>
          <td><strong style="font-size:0.82rem;">{{ lead['Business Name'] }}</strong></td>
          <td><span class="niche-pill">{{ lead['Business Niche/Category'] }}</span></td>
          <td style="white-space:nowrap;font-size:0.82rem;">{{ lead['Phone Number'] }}</td>
          <td style="font-size:0.78rem;">{{ lead['Address'] }}</td>
          <td style="font-size:0.82rem;">{{ lead['City'] }}</td>
          <td style="font-size:0.82rem;">{{ lead['State'] }}</td>
          <td class="text-center">{{ lead['Review Count'] }}</td>
          <td class="text-center">{{ lead['Star Rating'] }}&#9733;</td>
          <td style="font-size:0.75rem;max-width:140px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
            {{ lead['Operating Hours'] }}
          </td>
          <td class="text-center">
            {% if lead['Google Business Link'] %}
            <a class="gmb-link"
               href="{{ lead['Google Business Link'] }}"
               target="_blank" rel="noopener noreferrer">View &#8599;</a>
            {% endif %}
          </td>
          <td>
            <span class="pitch-cell" title="{{ lead['Custom Sales Pitch Notes'] }}">
              {{ lead['Custom Sales Pitch Notes'] }}
            </span>
          </td>
          <td style="font-size:0.72rem;color:var(--muted);max-width:120px;">
            {{ lead['Additional Notes'] }}
          </td>
          <td style="font-size:0.78rem;white-space:nowrap;">{{ lead['Date Added'] }}</td>
          <td style="font-size:0.78rem;">{{ lead['Call Status'] or '—' }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% else %}
  <div class="empty-state">
    <h3>No leads found</h3>
    <p>
      Run the parser first:<br>
      <code style="color:var(--accent);">python main.py --city "Your City" --state XX</code>
    </p>
    <p style="font-size:0.8rem;">
      Looking for: <code style="color:var(--muted);">{{ csv_path }}</code>
    </p>
  </div>
  {% endif %}
</div>

<!-- JS -->
<script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>
<script src="https://cdn.datatables.net/1.13.8/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.8/js/dataTables.bootstrap5.min.js"></script>
<script>
$(document).ready(function () {
  $('#leadsTable').DataTable({
    pageLength: 25,
    order: [[0, 'desc']],
    columnDefs: [
      { orderable: false, targets: [10, 11] },  // GMB link, Pitch (non-sortable)
      { width: '90px',  targets: [0] },
      { width: '60px',  targets: [6, 7, 8] },
    ],
    language: {
      search:     'Search:',
      lengthMenu: 'Show _MENU_ leads',
      info:       'Showing _START_\u2013_END_ of _TOTAL_ leads',
      paginate: { previous: '&#8592;', next: '&#8594;' },
    },
  });
});
</script>
</body>
</html>"""


# ── Flask routes ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    leads = load_leads()
    stats = compute_stats(leads)
    return render_template_string(_HTML, leads=leads, stats=stats, csv_path=_csv_path)


@app.route("/api/leads")
def api_leads():
    """JSON endpoint — returns all no-website leads."""
    return jsonify(load_leads())


@app.route("/api/stats")
def api_stats():
    """JSON endpoint — returns summary stats."""
    return jsonify(compute_stats(load_leads()))


# ── CLI entry point ───────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="LeadParser Dashboard — localhost lead viewer",
    )
    p.add_argument("--port", type=int, default=5000,
                   help="Port to serve on (default: 5000)")
    p.add_argument("--csv", default="data/leads_latest.csv",
                   help="Path to leads CSV (default: data/leads_latest.csv)")
    p.add_argument("--open", action="store_true",
                   help="Auto-open browser when server starts")
    return p.parse_args()


def main():
    global _csv_path
    args      = _parse_args()
    _csv_path = args.csv
    url       = f"http://localhost:{args.port}"

    lead_count = len(load_leads())
    print(f"\n  LeadParser Dashboard")
    print(f"  URL  : {url}")
    print(f"  CSV  : {_csv_path}")
    print(f"  Leads: {lead_count} (no-website only)")
    print(f"  Press Ctrl+C to stop\n")

    if not Path(_csv_path).exists():
        print(f"  [!] CSV not found — run 'python main.py' first to generate leads.\n")

    if args.open:
        Timer(1.2, webbrowser.open, args=[url]).start()

    app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
