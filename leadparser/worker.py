#!/usr/bin/env python3
"""
LeadParser Worker - Scraper Job Queue Processor
================================================
Run this whenever you want to generate leads. The site shows a live
"Engine Online" indicator while this is running, and lets you queue
jobs from the Scraper tab.

Supports running up to MAX_PARALLEL jobs simultaneously — each job
runs main.py in its own subprocess so scrapes don't block each other.

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
from concurrent.futures import ThreadPoolExecutor, Future
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

POLL_INTERVAL      = 10   # seconds between job polls
HEARTBEAT_INTERVAL = 10   # seconds between heartbeat updates
MAX_PARALLEL       = 4    # max concurrent scrape jobs (increase if your machine allows)
MAX_XHR_WORKERS    = 4    # max XHR workers per job when running solo
MAIN_PY            = Path(__file__).parent / 'main.py'


def calculate_resource_allocation(active_jobs: int, total_slots: int = MAX_PARALLEL) -> dict:
    """
    Calculate how to distribute XHR workers across active jobs.
    
    Returns dict with:
    - concurrent_xhr: XHR workers per job
    - max_parallel: total parallel jobs allowed
    - active_slots: currently active job count
    
    Strategy:
    - 1 job running: use all 4 XHR workers on it
    - 2 jobs running: split 2 XHR workers each
    - 3 jobs running: split 1-2-1 or round-robin
    - 4+ jobs: 1 XHR worker each (minimum)
    """
    if active_jobs <= 0:
        return {'concurrent_xhr': MAX_XHR_WORKERS, 'max_parallel': total_slots}
    
    # Calculate XHR workers per job (distribute evenly, minimum 1)
    xhr_per_job = max(1, MAX_XHR_WORKERS // active_jobs)
    
    # If we have more slots than jobs, we can increase per-job workers
    available_slots = total_slots - active_jobs
    if available_slots > 0 and xhr_per_job < MAX_XHR_WORKERS:
        # Bonus workers for jobs that can use them
        bonus = min(available_slots, MAX_XHR_WORKERS - xhr_per_job)
        xhr_per_job += bonus // active_jobs
    
    return {
        'concurrent_xhr': xhr_per_job,
        'max_parallel': total_slots,
        'active_slots': active_jobs,
    }

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
    """Atomically grab one pending job and mark it running.

    Uses an optimistic-lock pattern (update WHERE status='pending') so
    parallel workers never double-claim the same job.
    """
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
    now = datetime.now(timezone.utc).isoformat()

    # Only proceed if the row is still 'pending' (guards against parallel claims)
    update_res = (
        supabase.table('scraper_jobs')
        .update({'status': 'running', 'started_at': now, 'progress': 0})
        .eq('id', job['id'])
        .eq('status', 'pending')   # guard
        .execute()
    )
    if not update_res.data:
        return None   # another worker thread claimed it first

    log.info(
        f'Claimed job {job["id"][:8]} — {job["city"]}, {job["state"]}'
        f' | niche={job["niche"]} limit={job["limit_count"]}'
    )
    return job


CANCEL_POLL = 5  # seconds between cancellation checks while subprocess is running


def run_job(job: dict, resource_allocation: dict = None) -> tuple[int, str]:
    """Run main.py for the given job. Returns (leads_count, error_msg).

    Uses Popen instead of subprocess.run so we can check for cancellation
    every CANCEL_POLL seconds without blocking the thread indefinitely.
    Returns (0, '__cancelled__') when the job is cancelled via the UI.
    
    Args:
        job: The job dict from the database
        resource_allocation: Dict with 'concurrent_xhr' key for worker distribution
    """
    cmd = [sys.executable, str(MAIN_PY)]

    # Core params
    if job.get('city'):                             cmd += ['--city',   job['city']]
    if job.get('state'):                            cmd += ['--state',  job['state']]
    if job.get('niche') and job['niche'] != 'all':  cmd += ['--niche',  job['niche']]
    if job.get('limit_count'):                      cmd += ['--limit',  str(job['limit_count'])]
    if job.get('id'):                               cmd += ['--job-id', job['id']]

    # Per-job filter overrides
    if job.get('min_reviews', 0) > 0:
        cmd += ['--min-reviews', str(job['min_reviews'])]
    if job.get('max_reviews', 9999) < 9999:
        cmd += ['--max-reviews', str(job['max_reviews'])]
    if job.get('min_rating', 0) > 0:
        cmd += ['--min-rating', str(job['min_rating'])]
    if job.get('max_rating', 5.0) < 5.0:
        cmd += ['--max-rating', str(job['max_rating'])]
    # website_filter: 'any'=no flag | 'no'=exclude website | 'yes'=require website
    wf = job.get('website_filter', 'any')
    if wf == 'no':
        cmd += ['--exclude-website']
    elif wf == 'yes':
        cmd += ['--require-website']
    if job.get('require_phone', False):
        cmd += ['--require-phone']
    if job.get('min_score', 0) > 0:
        cmd += ['--min-score', str(job['min_score'])]
    
    # Parser override with automatic resource allocation
    parser = job.get('parser', 'playwright')
    if parser and parser not in ('', 'playwright'):
        cmd += ['--parser', parser]
        
        # Apply concurrent XHR based on resource allocation
        if parser == 'xhr' and resource_allocation:
            concurrent_xhr = resource_allocation.get('concurrent_xhr', 1)
            if concurrent_xhr > 1:
                cmd += ['--concurrent-xhr', str(concurrent_xhr)]
                log.info(f"Job {job['id'][:8]} using {concurrent_xhr} concurrent XHR workers")

    log.info(f'Running: {" ".join(cmd)}')
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(MAIN_PY.parent),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except Exception as exc:
        return 0, str(exc)

    # Poll: wait CANCEL_POLL seconds, then check DB for cancellation signal.
    # Repeat until the subprocess finishes naturally or is cancelled.
    stdout = stderr = ''
    elapsed = 0
    MAX_SECONDS = 3600
    while True:
        try:
            stdout, stderr = proc.communicate(timeout=CANCEL_POLL)
            break  # subprocess finished naturally
        except subprocess.TimeoutExpired:
            elapsed += CANCEL_POLL
            if elapsed >= MAX_SECONDS:
                proc.kill()
                proc.communicate()
                return 0, 'Job timed out after 1 hour'

            # Check whether the UI cancelled this job
            try:
                check = (
                    supabase.table('scraper_jobs')
                    .select('status')
                    .eq('id', job['id'])
                    .single()
                    .execute()
                )
                if check.data and check.data['status'] == 'cancelled':
                    log.info(f'Job {job["id"][:8]} cancelled — killing subprocess')
                    proc.kill()
                    proc.communicate()   # reap zombie
                    return 0, '__cancelled__'
            except Exception as exc:
                log.warning(f'Cancel-check DB call failed: {exc}')

    output = stdout + stderr
    if proc.returncode != 0:
        snippet = output[-500:].strip().replace('\n', ' ')
        log.error(f'Job {job["id"][:8]} failed (exit {proc.returncode}): {snippet[:200]}')
        return 0, snippet[:500]

    # Parse lead count from output lines
    leads_count = 0
    for line in output.splitlines():
        ll = line.lower()
        if any(k in ll for k in ['new leads', 'leads saved', 'upserted', 'inserted']):
            nums = [w for w in line.split() if w.isdigit()]
            if nums:
                leads_count = max(leads_count, int(nums[-1]))

    log.info(f'Job {job["id"][:8]} done — ~{leads_count} leads scraped')
    return leads_count, ''


def finish_job(job_id: str, result_count: int, error_msg: str = '') -> None:
    if error_msg == '__cancelled__':
        # Row was already set to 'cancelled' by the API; delete it so it's
        # completely gone from history (consistent with the frontend's optimistic removal).
        supabase.table('scraper_jobs').delete().eq('id', job_id).execute()
        log.info(f'Job {job_id[:8]} cancelled and removed from history')
        return

    status = 'failed' if error_msg else 'done'
    supabase.table('scraper_jobs').update({
        'status':       status,
        'progress':     100 if not error_msg else None,
        'result_count': result_count,
        'error_msg':    error_msg,
        'finished_at':  datetime.now(timezone.utc).isoformat(),
    }).eq('id', job_id).execute()
    log.info(f'Job {job_id[:8]} → {status}')


def process_job(job: dict, resource_allocation: dict = None) -> None:
    """Full job lifecycle: run then finalize. Designed for thread pool use."""
    count, err = run_job(job, resource_allocation)
    finish_job(job['id'], count, err)


# ── Main loop ──────────────────────────────────────────────────────────────

def main() -> None:
    global _stop

    # Start heartbeat thread
    hb = Thread(target=heartbeat_loop, daemon=True)
    hb.start()
    log.info(
        f'LeadParser Worker online — up to {MAX_PARALLEL} parallel jobs, '
        f'{MAX_XHR_WORKERS} max XHR workers per job. '
        f'Site will show "Engine Online". Press Ctrl+C to stop.'
    )

    futures: dict[str, Future] = {}
    executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL, thread_name_prefix='scraper')

    try:
        while True:
            try:
                # Prune completed futures
                done_ids = [jid for jid, f in futures.items() if f.done()]
                for jid in done_ids:
                    del futures[jid]

                # Calculate resource allocation based on current + pending jobs
                active_jobs = len(futures)
                slots = MAX_PARALLEL - active_jobs
                
                # Count pending jobs to estimate total load
                pending_res = supabase.table('scraper_jobs').select('id').eq('status', 'pending').execute()
                pending_count = len(pending_res.data) if pending_res.data else 0
                total_estimated = active_jobs + min(pending_count, slots)
                
                # Calculate how to distribute XHR workers
                resource_alloc = calculate_resource_allocation(total_estimated, MAX_PARALLEL)
                
                if pending_count > 0:
                    log.info(
                        f'Resource allocation: {active_jobs} active, {pending_count} pending, '
                        f'{resource_alloc["concurrent_xhr"]} XHR workers per job'
                    )

                # Claim new jobs up to available slots
                for _ in range(slots):
                    job = claim_job()
                    if job:
                        # Pass resource allocation so job knows how many XHR workers to use
                        futures[job['id']] = executor.submit(process_job, job, resource_alloc)
                    else:
                        break   # no more pending jobs right now

                if not futures:
                    log.debug('No pending jobs — waiting.')

            except Exception as exc:
                log.exception(f'Unexpected error in main loop: {exc}')

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        _stop = True
        log.info('Worker stopping — waiting for active jobs to finish…')
        executor.shutdown(wait=True)
        log.info('Worker stopped. Site will show "Engine Offline" shortly.')


if __name__ == '__main__':
    main()
