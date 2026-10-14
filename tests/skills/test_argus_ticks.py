#!/usr/bin/env python3
"""Behavior-contract tests for the Argus tick ledger (scripts/argus_ticks.py)."""

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
MODULE_PATH = ROOT / "skills" / "argus" / "scripts" / "argus_ticks.py"
spec = importlib.util.spec_from_file_location("argus_ticks", MODULE_PATH)
assert spec is not None and spec.loader is not None
ticks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ticks)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def rec(**kw):
    base = {
        "at": NOW.isoformat().replace("+00:00", "Z"),
        "job": "motherboard sales watch",
        "outcome": "silent",
        "slug": "motherboard-sales",
    }
    base.update(kw)
    return base


def days_ago(n):
    return (NOW - timedelta(days=n)).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# record / prune
# ---------------------------------------------------------------------------


def test_record_appends_one_line_and_stamps_time(tmp_path):
    ledger = tmp_path / "ticks.jsonl"
    ticks.append_record(ledger, {"job": "j", "outcome": "silent"})
    ticks.append_record(ledger, {"job": "j", "outcome": "fired"})
    lines = [ln for ln in ledger.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["job"] == "j"
    assert first["at"]  # stamped when absent


def test_record_rejects_unknown_outcome(tmp_path):
    with pytest.raises(ValueError):
        ticks.append_record(tmp_path / "t.jsonl", {"job": "j", "outcome": "banana"})


def test_prune_keeps_window_and_drops_older(tmp_path):
    ledger = tmp_path / "ticks.jsonl"
    ticks.append_record(ledger, rec(at=days_ago(1)))
    ticks.append_record(ledger, rec(at=days_ago(20)))
    removed, kept = ticks.prune(ledger, now=NOW, days=14)
    assert (removed, kept) == (1, 1)
    remaining = ticks.load_records(ledger)
    assert len(remaining) == 1


def test_prune_tolerates_corrupt_lines(tmp_path):
    ledger = tmp_path / "ticks.jsonl"
    ledger.write_text("{not json}\n" + json.dumps(rec(at=days_ago(1))) + "\n")
    removed, kept = ticks.prune(ledger, now=NOW, days=14)
    assert kept == 1
    assert removed == 1


def test_load_records_skips_corrupt_lines(tmp_path):
    ledger = tmp_path / "ticks.jsonl"
    ledger.write_text("garbage\n" + json.dumps(rec()) + "\n\n")
    assert len(ticks.load_records(ledger)) == 1


# ---------------------------------------------------------------------------
# rollup — job summary
# ---------------------------------------------------------------------------


def test_rollup_counts_completed_and_failed_per_job():
    records = [
        rec(outcome="silent"),
        rec(outcome="fired"),
        rec(outcome="error"),
        rec(job="other watch", outcome="silent"),
    ]
    report = ticks.build_report(records, now=NOW, days=14, silent_days=14)
    assert "motherboard sales watch — 2 completed / 1 failed" in report
    assert "other watch — 1 completed / 0 failed" in report


def test_rollup_ignores_records_outside_window():
    records = [rec(at=days_ago(1)), rec(at=days_ago(40), outcome="error")]
    report = ticks.build_report(records, now=NOW, days=14, silent_days=14)
    assert "1 completed / 0 failed" in report


def test_rollup_reports_no_jobs_when_ledger_empty():
    report = ticks.build_report([], now=NOW, days=14, silent_days=14)
    assert "no ticks recorded" in report.lower()


# ---------------------------------------------------------------------------
# rollup — source health
# ---------------------------------------------------------------------------


def test_source_health_flags_consecutive_zero_item_reads():
    src = "https://slickdeals.net/newsearch.php?q=motherboard"
    records = [
        rec(at=days_ago(3), sources=[{"source": src, "status": 200, "items": 0, "ok": True}]),
        rec(at=days_ago(2), sources=[{"source": src, "status": 200, "items": 0, "ok": True}]),
        rec(at=days_ago(1), sources=[{"source": src, "status": 200, "items": 0, "ok": True}]),
    ]
    report = ticks.build_report(records, now=NOW, days=14, silent_days=14)
    assert "Source health" in report
    assert "zero-item" in report
    assert src in report


def test_source_health_flags_error_streak():
    src = "https://portal.nousresearch.com/info"
    records = [
        rec(at=days_ago(2), sources=[{"source": src, "status": 403, "items": 0, "ok": False}]),
        rec(at=days_ago(1), sources=[{"source": src, "status": 403, "items": 0, "ok": False}]),
    ]
    report = ticks.build_report(records, now=NOW, days=14, silent_days=14)
    assert src in report
    assert "error" in report.lower()


def test_healthy_sources_are_not_reported():
    src = "https://example.com/feed"
    records = [rec(at=days_ago(1), sources=[{"source": src, "status": 200, "items": 5, "ok": True}])]
    report = ticks.build_report(records, now=NOW, days=14, silent_days=14)
    assert "no source problems" in report.lower()


def test_source_recovery_clears_streak():
    src = "https://example.com/feed"
    records = [
        rec(at=days_ago(3), sources=[{"source": src, "status": 500, "items": 0, "ok": False}]),
        rec(at=days_ago(2), sources=[{"source": src, "status": 500, "items": 0, "ok": False}]),
        rec(at=days_ago(1), sources=[{"source": src, "status": 200, "items": 7, "ok": True}]),
    ]
    report = ticks.build_report(records, now=NOW, days=14, silent_days=14)
    assert "no source problems" in report.lower()


# ---------------------------------------------------------------------------
# rollup — retirement candidates
# ---------------------------------------------------------------------------


def test_silent_tracker_beyond_threshold_is_flagged():
    records = [
        rec(slug="quiet-tracker", outcome="fired", at=days_ago(30)),
        rec(slug="quiet-tracker", outcome="silent", at=days_ago(1)),
    ]
    report = ticks.build_report(records, now=NOW, days=90, silent_days=14)
    assert "quiet-tracker" in report
    assert "30 days" in report
    assert "retire" in report.lower()


def test_recently_fired_tracker_is_not_flagged():
    records = [
        rec(slug="busy-tracker", outcome="fired", at=days_ago(2)),
        rec(slug="busy-tracker", outcome="silent", at=days_ago(1)),
    ]
    report = ticks.build_report(records, now=NOW, days=90, silent_days=14)
    assert "no retirement candidates" in report.lower()


def test_cadence_awareness_suppresses_expected_silence():
    records = [rec(slug="monthly-thing", outcome="fired", at=days_ago(30))]
    report = ticks.build_report(
        records, now=NOW, days=90, silent_days=14, cadence={"monthly-thing": "monthly"}
    )
    assert "no retirement candidates" in report.lower()


def test_retirement_section_comes_after_source_health():
    records = [rec(slug="quiet", outcome="fired", at=days_ago(30))]
    report = ticks.build_report(records, now=NOW, days=90, silent_days=14)
    assert report.index("Source health") < report.index("retirement candidates")
