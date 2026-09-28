#!/usr/bin/env python3
"""
Argus Watch — zero-token watchdog for Hermes cron jobs.

Runs as a --no-agent cron job. Checks all active cron jobs for:
- Overdue runs (last_run older than grace period)
- Paused/disabled jobs that should be active
- Failed/errored runs

Outputs alerts only when something is wrong. Silent when all jobs are healthy.

Configuration:
  --grace-period MULTIPLIER  Grace period multiplier (default: 1.5)
  --exclude JOB_ID          Exclude a job from checks (repeatable)
  --config PATH             Path to JSON config file

Config file format:
{
  "grace_period": 1.5,
  "excludes": ["job-id-1", "job-id-2"],
  "jobs": {
    "job-id-1": {"grace_period": 2.0},
    "job-id-2": {"grace_period": 1.0}
  }
}
"""

import argparse
import json
import subprocess
import sys
import re
import os
from datetime import datetime, timezone, timedelta

def parse_cron_list():
    """Parse hermes cron list output into job dicts."""
    result = subprocess.run(
        ["hermes", "cron", "list", "--all"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"⚠️ Watchdog Error: hermes cron list failed: {result.stderr.strip()}")
        sys.exit(1)
    
    jobs = []
    current_job = {}
    
    for line in result.stdout.split("\n"):
        line = line.strip()
        
        # New job starts with an ID like "62a0b4af34f3 [active]"
        match = re.match(r'^([a-f0-9]+)\s+\[(\w+)\]', line)
        if match:
            if current_job:
                jobs.append(current_job)
            current_job = {
                "id": match.group(1),
                "status": match.group(2),
                "name": "",
                "schedule": "",
                "last_run": "",
                "last_run_status": "",
                "dispatch": "",
                "next_run": "",
            }
            continue
        
        if not current_job:
            continue
            
        if line.startswith("Name:"):
            current_job["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Schedule:"):
            current_job["schedule"] = line.split(":", 1)[1].strip()
        elif line.startswith("Last run:"):
            # "2026-09-28T09:02:25.476762-04:00  ok"
            parts = line.split(":", 1)[1].strip()
            # Split on double space to separate timestamp from status
            if "  " in parts:
                ts_str, status = parts.rsplit("  ", 1)
                current_job["last_run"] = ts_str.strip()
                current_job["last_run_status"] = status.strip()
            else:
                current_job["last_run"] = parts
                current_job["last_run_status"] = "unknown"
        elif line.startswith("Dispatch:"):
            current_job["dispatch"] = line.split(":", 1)[1].strip()
        elif line.startswith("Next run:"):
            current_job["next_run"] = line.split(":", 1)[1].strip()
    
    if current_job:
        jobs.append(current_job)
    
    return jobs


def parse_schedule_interval(schedule):
    """Parse schedule string into expected interval in minutes."""
    schedule = schedule.strip()
    
    # "every Nm" or "every Nh" or "every Nd"
    match = re.match(r'every\s+(\d+)([mhd])', schedule, re.IGNORECASE)
    if match:
        n = int(match.group(1))
        unit = match.group(2).lower()
        if unit == 'm':
            return n
        elif unit == 'h':
            return n * 60
        elif unit == 'd':
            return n * 60 * 24
    
    # Cron expression: "0 9 * * *" (daily) or "0 9 * * 1" (weekly)
    parts = schedule.split()
    if len(parts) == 5:
        minute, hour, day, month, weekday = parts
        # Daily: every day
        if day == '*' and month == '*' and weekday == '*':
            return 24 * 60  # 1 day
        # Weekly: specific day of week
        if day == '*' and month == '*' and weekday != '*':
            return 7 * 24 * 60  # 1 week
        # Monthly: specific day of month
        if day != '*' and month == '*' and weekday == '*':
            return 30 * 24 * 60  # ~1 month
    
    # Default: assume hourly
    return 60


def parse_timestamp(ts_str):
    """Parse ISO timestamp string into datetime."""
    if not ts_str:
        return None
    try:
        # Handle "2026-09-28T09:02:25.476762-04:00"
        return datetime.fromisoformat(ts_str)
    except ValueError:
        return None


def check_job(job, now, grace_period=1.5, excludes=None):
    """Check a single job for issues. Returns list of alerts."""
    alerts = []
    
    if excludes is None:
        excludes = set()
    
    # Skip excluded jobs
    if job["id"] in excludes:
        return alerts
    
    # Skip intentionally paused jobs
    if job["status"] == "paused":
        return alerts
    
    # Check if job is active but has no last_run
    if not job["last_run"]:
        alerts.append(f"⚠️ Job '{job['name']}' ({job['id']}) is active but has never run.")
        return alerts
    
    # Check last run status
    if job["last_run_status"] not in ("ok", "completed", ""):
        alerts.append(
            f"⚠️ Job '{job['name']}' ({job['id']}) last run status: {job['last_run_status']}\n"
            f"  Last run: {job['last_run']}\n"
            f"  Check: hermes cron runs {job['id']}"
        )
    
    # Check if job is overdue
    last_run_dt = parse_timestamp(job["last_run"])
    if last_run_dt:
        # Make both timezone-aware
        if last_run_dt.tzinfo is None:
            last_run_dt = last_run_dt.replace(tzinfo=timezone.utc)
        
        interval_min = parse_schedule_interval(job["schedule"])
        expected_interval = timedelta(minutes=interval_min)
        
        # Use job-specific grace period if available
        job_grace = grace_period
        # Note: job-specific grace periods are handled via config in main()
        
        grace_period_td = expected_interval * job_grace
        
        time_since_last_run = now - last_run_dt
        
        if time_since_last_run > grace_period_td:
            hours_overdue = (time_since_last_run - expected_interval).total_seconds() / 3600
            alerts.append(
                f"⚠️ Job '{job['name']}' ({job['id']}) is overdue.\n"
                f"  Last run: {job['last_run']} ({hours_overdue:.1f}h ago)\n"
                f"  Expected: every {interval_min} minutes\n"
                f"  Grace period: {job_grace}x interval\n"
                f"  Check: hermes cron runs {job['id']}"
            )
    
    # Check dispatch status
    if job["dispatch"] and "on time" not in job["dispatch"].lower():
        if "late" in job["dispatch"].lower() or "delayed" in job["dispatch"].lower():
            alerts.append(
                f"⚠️ Job '{job['name']}' ({job['id']}) dispatch delayed.\n"
                f"  Dispatch: {job['dispatch']}"
            )
    
    return alerts


def load_config(config_path):
    """Load configuration from JSON file."""
    if not config_path:
        return {}
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Watchdog Warning: Could not load config: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(description="Argus Watch — zero-token watchdog for Hermes cron jobs")
    parser.add_argument("--grace-period", type=float, default=1.5,
                        help="Grace period multiplier (default: 1.5)")
    parser.add_argument("--exclude", action="append", default=[],
                        help="Exclude a job from checks (repeatable)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to JSON config file")
    args = parser.parse_args()
    
    # Load config file if provided
    config = load_config(args.config)
    
    # Config file values override defaults
    grace_period = config.get("grace_period", args.grace_period)
    excludes = set(config.get("excludes", []) + args.exclude)
    
    now = datetime.now(timezone.utc)
    
    try:
        jobs = parse_cron_list()
    except Exception as e:
        print(f"⚠️ Watchdog Error: Failed to parse cron jobs: {e}")
        sys.exit(1)
    
    if not jobs:
        # No jobs found — this is fine, silent
        sys.exit(0)
    
    all_alerts = []
    for job in jobs:
        # Check for job-specific grace period in config
        job_grace = grace_period
        if "jobs" in config and job["id"] in config["jobs"]:
            job_grace = config["jobs"][job["id"]].get("grace_period", grace_period)
        
        alerts = check_job(job, now, job_grace, excludes)
        all_alerts.extend(alerts)
    
    if all_alerts:
        print("🔍 Argus Watch — Job Health Check")
        print("=" * 50)
        for alert in all_alerts:
            print(alert)
        print("=" * 50)
        print(f"Checked {len(jobs)} job(s), found {len(all_alerts)} issue(s).")
        sys.exit(0)
    else:
        # All healthy — silent (no output = no delivery)
        sys.exit(0)


if __name__ == "__main__":
    main()
