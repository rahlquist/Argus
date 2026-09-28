#!/usr/bin/env python3
"""Tests for the Argus Watch watchdog script.

Stdlib + pytest only. No network. Mocks hermes cron list output.

Run: pytest tests/skills/test_argus_watch.py -q
"""

import importlib.util
import os
import sys
import json
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

SKILL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "skills", "argus-watch", "scripts"
)


def _load(modname):
    path = os.path.join(SKILL_DIR, f"{modname}.py")
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


watchdog = _load("watchdog")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CRON_LIST = """
  62a0b4af34f3 [active]
    Name:      slug voice service — monthly update check
    Schedule:  0 9 * * *
    Repeat:    ∞
    Next run:  2026-09-29T09:00:00-04:00
    Deliver:   origin
    Skills:    argus
    Workdir:   /home/rahlquist/.intel
    Last run:  2026-09-28T09:02:25.476762-04:00  ok
    Dispatch:  on time (scheduled 2026-09-28T09:00:00-04:00)
    Execution: completed  a13d4eb199754d7e904467dddd07c1b9

  3364efef863e [paused]
    Name:      nous-llm-deals-watch
    Schedule:  every 60m
    Repeat:    ∞
    Next run:  2026-09-28T08:34:02.232910-04:00
    Deliver:   local
    Skills:    argus
    Workdir:   /home/rahlquist/.intel
    Last run:  2026-09-28T07:34:02.232910-04:00  ok
    Dispatch:  on time (scheduled 2026-09-28T07:16:56.652918-04:00)
    Execution: completed  39e763724a1741a1bd1a6af93961aef3

  104762a11415 [paused]
    Name:      pr-check-110506-30day
    Schedule:  once at 2026-10-13 09:00
    Repeat:    0/1
    Next run:  2026-10-13T09:00:00-04:00
    Deliver:   origin

  dfcd17dc0214 [active]
    Name:      Check PR 110946 acceptance (30d)
    Schedule:  once in 30d
    Repeat:    0/1
    Next run:  2026-10-14T11:01:56.260766-04:00
    Deliver:   bot-chat:loco-bot

  ef5c7044f68f [active]
    Name:      pr-115709-30day-check
    Schedule:  0 9 19 10 *
    Repeat:    ∞
    Next run:  2026-10-19T09:00:00-04:00
    Deliver:   local
"""


# ---------------------------------------------------------------------------
# parse_cron_list
# ---------------------------------------------------------------------------

def test_parse_cron_list_returns_all_jobs():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=SAMPLE_CRON_LIST, stderr=""
        )
        jobs = watchdog.parse_cron_list()
    
    assert len(jobs) == 5
    assert jobs[0]["id"] == "62a0b4af34f3"
    assert jobs[0]["status"] == "active"
    assert jobs[0]["name"] == "slug voice service — monthly update check"
    assert jobs[0]["schedule"] == "0 9 * * *"
    assert jobs[0]["last_run"] == "2026-09-28T09:02:25.476762-04:00"
    assert jobs[0]["last_run_status"] == "ok"


def test_parse_cron_list_handles_empty_output():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )
        jobs = watchdog.parse_cron_list()
    
    assert jobs == []


def test_parse_cron_list_handles_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error"
        )
        with pytest.raises(SystemExit):
            watchdog.parse_cron_list()


# ---------------------------------------------------------------------------
# parse_schedule_interval
# ---------------------------------------------------------------------------

def test_parse_schedule_interval_every_minutes():
    assert watchdog.parse_schedule_interval("every 30m") == 30
    assert watchdog.parse_schedule_interval("every 5m") == 5


def test_parse_schedule_interval_every_hours():
    assert watchdog.parse_schedule_interval("every 2h") == 120
    assert watchdog.parse_schedule_interval("every 1h") == 60


def test_parse_schedule_interval_every_days():
    assert watchdog.parse_schedule_interval("every 1d") == 1440


def test_parse_schedule_interval_cron_daily():
    assert watchdog.parse_schedule_interval("0 9 * * *") == 1440


def test_parse_schedule_interval_cron_weekly():
    assert watchdog.parse_schedule_interval("0 9 * * 1") == 10080


def test_parse_schedule_interval_cron_monthly():
    assert watchdog.parse_schedule_interval("0 9 1 * *") == 43200


def test_parse_schedule_interval_default():
    assert watchdog.parse_schedule_interval("unknown") == 60


# ---------------------------------------------------------------------------
# parse_timestamp
# ---------------------------------------------------------------------------

def test_parse_timestamp_valid():
    ts = watchdog.parse_timestamp("2026-09-28T09:02:25.476762-04:00")
    assert ts is not None
    assert ts.year == 2026
    assert ts.month == 9
    assert ts.day == 28


def test_parse_timestamp_empty():
    assert watchdog.parse_timestamp("") is None


def test_parse_timestamp_invalid():
    assert watchdog.parse_timestamp("not a date") is None


# ---------------------------------------------------------------------------
# check_job
# ---------------------------------------------------------------------------

def test_check_job_skips_paused():
    job = {
        "id": "abc123",
        "status": "paused",
        "name": "test",
        "schedule": "every 60m",
        "last_run": "",
        "last_run_status": "",
        "dispatch": "",
    }
    alerts = watchdog.check_job(job, datetime.now(timezone.utc), 1.5, set())
    assert alerts == []


def test_check_job_skips_excluded():
    job = {
        "id": "abc123",
        "status": "active",
        "name": "test",
        "schedule": "every 60m",
        "last_run": "",
        "last_run_status": "",
        "dispatch": "",
    }
    alerts = watchdog.check_job(job, datetime.now(timezone.utc), 1.5, {"abc123"})
    assert alerts == []


def test_check_job_alerts_on_never_run():
    job = {
        "id": "abc123",
        "status": "active",
        "name": "test",
        "schedule": "every 60m",
        "last_run": "",
        "last_run_status": "",
        "dispatch": "",
    }
    alerts = watchdog.check_job(job, datetime.now(timezone.utc), 1.5, set())
    assert len(alerts) == 1
    assert "never run" in alerts[0]


def test_check_job_alerts_on_failed_status():
    # Use a recent timestamp so only the error status alert fires (not overdue)
    last_run = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    job = {
        "id": "abc123",
        "status": "active",
        "name": "test",
        "schedule": "every 60m",
        "last_run": last_run,
        "last_run_status": "error",
        "dispatch": "",
    }
    alerts = watchdog.check_job(job, datetime.now(timezone.utc), 1.5, set())
    assert len(alerts) == 1
    assert "error" in alerts[0]


def test_check_job_alerts_on_overdue():
    # Last run 3 hours ago, schedule is every 60m, grace period 1.5x = 90m
    last_run = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    job = {
        "id": "abc123",
        "status": "active",
        "name": "test",
        "schedule": "every 60m",
        "last_run": last_run,
        "last_run_status": "ok",
        "dispatch": "",
    }
    alerts = watchdog.check_job(job, datetime.now(timezone.utc), 1.5, set())
    assert len(alerts) == 1
    assert "overdue" in alerts[0]


def test_check_job_silent_when_healthy():
    # Last run 30 minutes ago, schedule is every 60m, grace period 1.5x = 90m
    last_run = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    job = {
        "id": "abc123",
        "status": "active",
        "name": "test",
        "schedule": "every 60m",
        "last_run": last_run,
        "last_run_status": "ok",
        "dispatch": "on time",
    }
    alerts = watchdog.check_job(job, datetime.now(timezone.utc), 1.5, set())
    assert alerts == []


def test_check_job_custom_grace_period():
    # Last run 2 hours ago, schedule is every 60m, grace period 3x = 180m
    last_run = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    job = {
        "id": "abc123",
        "status": "active",
        "name": "test",
        "schedule": "every 60m",
        "last_run": last_run,
        "last_run_status": "ok",
        "dispatch": "",
    }
    # With 3x grace period, 2 hours is within 3 hours -> no alert
    alerts = watchdog.check_job(job, datetime.now(timezone.utc), 3.0, set())
    assert alerts == []
    
    # With 1.5x grace period, 2 hours is over 90m -> alert
    alerts = watchdog.check_job(job, datetime.now(timezone.utc), 1.5, set())
    assert len(alerts) == 1


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

def test_load_config_valid():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"grace_period": 2.0, "excludes": ["abc123"]}, f)
        config_path = f.name
    
    try:
        config = watchdog.load_config(config_path)
        assert config["grace_period"] == 2.0
        assert config["excludes"] == ["abc123"]
    finally:
        os.unlink(config_path)


def test_load_config_missing_file():
    config = watchdog.load_config("/nonexistent/path.json")
    assert config == {}


def test_load_config_invalid_json():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("not valid json")
        config_path = f.name
    
    try:
        config = watchdog.load_config(config_path)
        assert config == {}
    finally:
        os.unlink(config_path)


# ---------------------------------------------------------------------------
# Integration: main()
# ---------------------------------------------------------------------------

def test_main_silent_when_all_healthy():
    """When all jobs are healthy, main() should produce no output."""
    healthy_jobs = """
  62a0b4af34f3 [active]
    Name:      test job
    Schedule:  every 60m
    Last run:  {last_run}  ok
    Dispatch:  on time
""".format(last_run=(datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat())
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=healthy_jobs, stderr=""
        )
        with patch("sys.stdout") as mock_stdout:
            with patch("sys.argv", ["watchdog.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    watchdog.main()
                assert exc_info.value.code == 0
                # Should not print anything
                mock_stdout.write.assert_not_called()


def test_main_alerts_when_overdue():
    """When a job is overdue, main() should print an alert."""
    overdue_jobs = """
  62a0b4af34f3 [active]
    Name:      test job
    Schedule:  every 60m
    Last run:  {last_run}  ok
    Dispatch:  on time
""".format(last_run=(datetime.now(timezone.utc) - timedelta(hours=3)).isoformat())
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=overdue_jobs, stderr=""
        )
        with patch("sys.stdout") as mock_stdout:
            with patch("sys.argv", ["watchdog.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    watchdog.main()
                assert exc_info.value.code == 0
                # Should print an alert
                assert mock_stdout.write.call_count > 0
