#!/usr/bin/env python3
"""
LeadParser Worker - Scraper Job Queue Processor
================================================
Run this whenever you want to generate leads. The site shows a live
"Engine Online" indicator while this is running, and lets you queue
jobs from the Scraper tab.

Setup
-----
  1. pip install -r requirements.txt
  2. cp .env.example .env   # add SUPABASE_URL + SUPABASE_KEY (service role)
  3. python worker.py

Ctrl+C to stop. The site will show "Engine Offline" within 30 seconds.
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

from dotenv import load_dotenv
from supabase import create_client, Client

# ── Setup ──────────────────────────────────────────────────────────────────
load_dotenv()

LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f'worker_{datetime.now().strftime("%Y%m%d")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger('worker')

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')   # service role key

if not SUPABASE_URL or not SUPABASE_KEY:
    log.error('SUPABASE_URL and SUPABASE_KEY must be set in .env')
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

POLL_INTERVAL      = 15   # seconds between job polls
HEARTBEAT_INTERVAL = 10   # seconds between heartbeat updates
MAIN_PY            = Path(__file__).parent / 'main.py'

_stop = False  # shared flag for clean shutdown


# ── Heartbeat (runs in background thread) ──────────────────────────────────

def heartbeat_loop() -> None:
    """Update worker_status.last_seen every HEARTBEAT_INTERVAL seconds."""
    while not _stop:
        try:
            supabase.table('worker_status').upsert({
                'id':        1,
                'last_seen': datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as exc:
            log.warning(f'Heartbeat failed: {exc}')
        time.sleep(HEARTBEAT_INTERVAL)


# ── Core job logic ─────────────────────────────────────────────────────────

def claim_job() -> dict | None:
    """Grab one pending job and mark it running."""
    res = (
        supabase.table('scraper_jobs')
        .select('*')
        .eq('status', 'pending')
        .order('created_at')
        .limit(1)
        .execute()
    )
    if not res.data:
        return None

    job = res.data[0]
    supabase.table('scraper_jobs').update({
        'status':     'running',
        'started_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', job['id']).execute()

    log.info(f'Claimed job {job["id"][:8]} — {job["city"]}, {job["state"]} | niche={job["niche"]} limit={job["limit_count"]}')
    return job


def run_job(job: dict) -> tuple[int, str]:
    """Run main.py for the given job. Returns (leads_count, error_msg)."""
    cmd = [sys.executable, str(MAIN_PY)]
    if job.get('city'):                            cmd += ['--city',  job['city']]
    if job.get('state'):                           cmd += ['--state', job['state']]
    if job.get('niche') and job['niche'] != 'all': cmd += ['--niche', job['niche']]
    if job.get('limit_count'):                     cmd += ['--limit', str(job['limit_count'])]

    log.info(f'Running: {" ".join(cmd)}')
    try:
        result = subprocess.run(
            cmd, cwd=str(MAIN_PY.parent),
            capture_output=True, text=True, timeout=3600,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            snippet = output[-500:].strip().replace('\n', ' ')
            log.error(f'Job failed (exit {result.returncode}): {snippet[:200]}')
            return 0, snippet[:500]

        # Parse lead count from output lines
        leads_count = 0
        for line in output.splitlines():
            ll = line.lower()
            if any(k in ll for k in ['new leads', 'leads saved', 'upserted', 'inserted']):
                nums = [w for w in line.split() if w.isdigit()]
                if nums:
                    leads_count = max(leads_count, int(nums[-1]))

        log.info(f'Job done — ~{leads_count} leads scraped')
        return leads_count, ''

    except subprocess.TimeoutExpired:
        return 0, 'Job timed out after 1 hour'
    except Exception as exc:
        return 0, str(exc)


def finish_job(job_id: str, result_count: int, error_msg: str = '') -> None:
    status = 'failed' if error_msg else 'done'
    supabase.table('scraper_jobs').update({
        'status':       status,
        'result_count': result_count,
        'error_msg':    error_msg,
        'finished_at':  datetime.now(timezone.utc).isoformat(),
    }).eq('id', job_id).execute()
    log.info(f'Job {job_id[:8]} → {status}')


# ── Main loop ──────────────────────────────────────────────────────────────

def main() -> None:
    global _stop

    # Start heartbeat thread
    hb = Thread(target=heartbeat_loop, daemon=True)
    hb.start()
    log.info('LeadParser Worker online. Site will show "Engine Online". Press Ctrl+C to stop.')

    try:
        while True:
            try:
                job = claim_job()
                if job:
                    count, err = run_job(job)
                    finish_job(job['id'], count, err)
                else:
                    log.debug('No pending jobs — waiting.')
            except Exception as exc:
                log.exception(f'Unexpected error: {exc}')
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        _stop = True
        log.info('Worker stopped. Site will show "Engine Offline" shortly.')


if __name__ == '__main__':
    main()
