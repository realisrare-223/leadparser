#!/usr/bin/env python3
"""
Scheduler -- runs LeadParser on a recurring schedule.

Uses the `schedule` library (free, pure Python, no daemon process needed).
Can also generate OS-level scheduling commands (Windows Task Scheduler /
Linux cron) if you prefer a system-level solution.

Usage
-----
  # Start the Python-based scheduler (keeps running in the foreground)
  python scheduler.py

  # Print Windows Task Scheduler setup commands and exit
  python scheduler.py --print-task-scheduler

  # Print Linux cron job entry and exit
  python scheduler.py --print-cron

The scheduler reads its settings from config.yaml -> scheduling:
  enabled:     true
  frequency:   "weekly"    # daily | weekly | monthly
  run_time:    "08:00"     # 24-hour HH:MM
  day_of_week: "monday"    # (for weekly runs)
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import schedule
import yaml
from dotenv import load_dotenv
from colorama import init as colorama_init, Fore, Style

logger = logging.getLogger("leadparser.scheduler")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run_leadparser(config_path: str = "config.yaml"):
    """
    Entry point called by the scheduler each time it fires.
    Imports and runs the main pipeline in-process.
    """
    import main as lp_main
    import argparse

    logger.info("Scheduled run starting...")
    config = load_config(config_path)

    # Build a minimal args namespace (no CLI flags for scheduled runs)
    args = argparse.Namespace(
        config=config_path,
        niche=None,
        export_only=False,
        no_sheets=False,
        dry_run=False,
    )

    try:
        stats, url = lp_main.run_pipeline(config, args, logger)
        logger.info(f"Scheduled run complete: {stats}")
        if url:
            logger.info(f"Google Sheets: {url}")
    except Exception as exc:
        logger.exception(f"Scheduled run failed: {exc}")


def start_scheduler(config: dict, config_path: str):
    """Set up and start the schedule loop based on config.yaml -> scheduling."""
    sched_cfg   = config.get("scheduling", {})
    frequency   = sched_cfg.get("frequency",   "weekly").lower()
    run_time    = sched_cfg.get("run_time",     "08:00")
    day_of_week = sched_cfg.get("day_of_week",  "monday").lower()

    print(f"{Fore.CYAN}Scheduler starting...{Style.RESET_ALL}")
    print(f"  Frequency : {frequency}")
    print(f"  Run time  : {run_time}")
    if frequency == "weekly":
        print(f"  Day       : {day_of_week}")
    print(f"  Press Ctrl+C to stop\n")

    if frequency == "daily":
        schedule.every().day.at(run_time).do(run_leadparser, config_path)
        logger.info(f"Scheduled: daily at {run_time}")

    elif frequency == "weekly":
        day_fn = getattr(schedule.every(), day_of_week, None)
        if day_fn is None:
            logger.error(f"Invalid day_of_week: '{day_of_week}'")
            sys.exit(1)
        day_fn.at(run_time).do(run_leadparser, config_path)
        logger.info(f"Scheduled: every {day_of_week} at {run_time}")

    elif frequency == "monthly":
        # schedule library doesn't support monthly natively;
        # run daily and check the day number ourselves
        def monthly_wrapper():
            import datetime
            if datetime.date.today().day == 1:
                run_leadparser(config_path)

        schedule.every().day.at(run_time).do(monthly_wrapper)
        logger.info(f"Scheduled: 1st of every month at {run_time}")

    else:
        logger.error(f"Unknown frequency: '{frequency}'. Use daily | weekly | monthly")
        sys.exit(1)

    # Main loop
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)    # check every 30 seconds
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


# ---------------------------------------------------------------------
# OS-level scheduling helpers
# ---------------------------------------------------------------------

def print_windows_task_scheduler(config: dict, config_path: str):
    """Print schtasks commands to set up Windows Task Scheduler (free, built-in)."""
    sched_cfg   = config.get("scheduling", {})
    frequency   = sched_cfg.get("frequency",   "weekly")
    run_time    = sched_cfg.get("run_time",     "08:00")
    day_of_week = sched_cfg.get("day_of_week",  "monday").capitalize()

    python_exe  = sys.executable
    script_path = Path(__file__).parent.absolute() / "scheduler.py"
    task_name   = "LeadParser"

    print(f"\n{Fore.CYAN}Windows Task Scheduler Setup{Style.RESET_ALL}")
    print("Run these commands in an elevated Command Prompt (Run as Administrator):\n")

    schedule_flag = "/SC WEEKLY /D MON" if frequency == "weekly" else "/SC DAILY"
    if frequency == "weekly":
        # Convert day name to Windows abbreviation
        day_abbr = day_of_week[:3].upper()
        schedule_flag = f"/SC WEEKLY /D {day_abbr}"

    cmd = (
        f'schtasks /CREATE /TN "{task_name}" '
        f'/TR "\\"{python_exe}\\" \\"{script_path}\\"" '
        f'{schedule_flag} /ST {run_time} /F'
    )
    print(cmd)
    print(f'\n# To delete: schtasks /DELETE /TN "{task_name}" /F')
    print(f'# To run now: schtasks /RUN /TN "{task_name}"')
    print(f'# To view:    schtasks /QUERY /TN "{task_name}"')


def print_cron_entry(config: dict):
    """Print a crontab entry for Linux/macOS (free, built-in)."""
    sched_cfg   = config.get("scheduling", {})
    frequency   = sched_cfg.get("frequency",   "weekly")
    run_time    = sched_cfg.get("run_time",     "08:00")
    day_of_week = sched_cfg.get("day_of_week",  "monday")

    hour, minute = run_time.split(":")
    python_exe   = sys.executable
    script_path  = Path(__file__).parent.absolute() / "scheduler.py"
    log_path     = Path(__file__).parent.absolute() / "logs" / "cron.log"

    # Cron weekday: 0=Sunday, 1=Monday, ..., 7=Sunday
    day_map = {
        "sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
        "thursday": 4, "friday": 5, "saturday": 6,
    }
    weekday = day_map.get(day_of_week.lower(), 1)

    if frequency == "daily":
        cron_expr = f"{minute} {hour} * * *"
    elif frequency == "weekly":
        cron_expr = f"{minute} {hour} * * {weekday}"
    elif frequency == "monthly":
        cron_expr = f"{minute} {hour} 1 * *"
    else:
        cron_expr = f"{minute} {hour} * * *"

    print(f"\n{Fore.CYAN}Linux / macOS Cron Setup{Style.RESET_ALL}")
    print("Run: crontab -e  and add this line:\n")
    print(f'{cron_expr} {python_exe} "{script_path}" >> "{log_path}" 2>&1')
    print("\n# Verify with: crontab -l")


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        prog="scheduler",
        description="LeadParser scheduler -- keeps the pipeline running on a schedule",
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument(
        "--print-task-scheduler", action="store_true",
        help="Print Windows Task Scheduler setup commands and exit",
    )
    parser.add_argument(
        "--print-cron", action="store_true",
        help="Print Linux/macOS crontab entry and exit",
    )
    return parser.parse_args()


def main():
    colorama_init(autoreset=True)
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    args   = parse_args()
    config = load_config(args.config)

    if args.print_task_scheduler:
        print_windows_task_scheduler(config, args.config)
        return

    if args.print_cron:
        print_cron_entry(config)
        return

    if not config.get("scheduling", {}).get("enabled", False):
        print(
            f"{Fore.YELLOW}Scheduling is disabled in config.yaml "
            f"(scheduling.enabled: false){Style.RESET_ALL}"
        )
        print("Set 'enabled: true' under the scheduling section to activate.")
        return

    start_scheduler(config, args.config)


if __name__ == "__main__":
    main()
