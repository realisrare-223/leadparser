#!/usr/bin/env python3
"""
LeadParser Worker — Scraper Job Queue Processor
================================================
Run this on your 24/7 PC. It polls Supabase every 30 seconds for
pending scraper jobs queued from the admin dashboard, runs main.py
as a subprocess, and updates the job status + result count.

Setup
-----
  1. pip install -r requirements.txt
  2. cp .env.example .env   # add SUPABASE_URL + SUPABASE_KEY (service role)
  3. python worker.py

The worker runs forever until you Ctrl+C it.
To run in the background on Windows:
  pythonw worker.py          # silent background process
  # or use Task Scheduler to run at startup
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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

POLL_INTERVAL = 30   # seconds between polls
MAIN_PY       = Path(__file__).parent / 'main.py'


# ── Core logic ─────────────────────────────────────────────────────────────

def claim_job() -> dict | None:
    """Atomically grab one pending job and mark it running."""
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
    job_id = job['id']

    # Mark running
    supabase.table('scraper_jobs').update({
        'status':     'running',
        'started_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', job_id).execute()

    log.info(f'Claimed job {job_id[:8]} — {job["city"]}, {job["state"]} | niche={job["niche"]} limit={job["limit_count"]}')
    return job


def run_job(job: dict) -> tuple[int, str]:
    """
    Run main.py for the given job.
    Returns (leads_scraped, error_message).
    """
    cmd = [sys.executable, str(MAIN_PY)]

    if job.get('city'):
        cmd += ['--city', job['city']]
    if job.get('state'):
        cmd += ['--state', job['state']]
    if job.get('niche') and job['niche'] != 'all':
        cmd += ['--niche', job['niche']]
    if job.get('limit_count'):
        cmd += ['--limit', str(job['limit_count'])]

    log.info(f'Running: {" ".join(cmd)}')

    try:
        result = subprocess.run(
            cmd,
            cwd=str(MAIN_PY.parent),
            capture_output=True,
            text=True,
            timeout=3600,    # 1 hour max per job
        )
        output = result.stdout + result.stderr

        if result.returncode != 0:
            # Extract a short error from the last 500 chars of output
            error_snippet = output[-500:].strip().replace('\n', ' ')
            log.error(f'Job failed (exit {result.returncode}): {error_snippet[:200]}')
            return 0, error_snippet[:500]

        # Try to parse lead count from output
        # main.py logs "Saved X new leads" or similar
        leads_count = 0
        for line in output.splitlines():
            line_lower = line.lower()
            for keyword in ['new leads', 'leads saved', 'upserted', 'inserted']:
                if keyword in line_lower:
                    # Extract last number on the line
                    nums = [w for w in line.split() if w.isdigit()]
                    if nums:
                        leads_count = max(leads_count, int(nums[-1]))

        log.info(f'Job done — ~{leads_count} leads scraped')
        return leads_count, ''

    except subprocess.TimeoutExpired:
        err = 'Job timed out after 1 hour'
        log.error(err)
        return 0, err
    except Exception as exc:
        err = str(exc)
        log.error(f'Job exception: {err}')
        return 0, err


def finish_job(job_id: str, result_count: int, error_msg: str = '') -> None:
    """Mark job done or failed in Supabase."""
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
    log.info('LeadParser Worker started. Polling every %ds. Press Ctrl+C to stop.', POLL_INTERVAL)

    while True:
        try:
            job = claim_job()
            if job:
                count, err = run_job(job)
                finish_job(job['id'], count, err)
            else:
                log.debug('No pending jobs.')
        except KeyboardInterrupt:
            log.info('Worker stopped.')
            break
        except Exception as exc:
            log.exception(f'Unexpected error in main loop: {exc}')

        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
