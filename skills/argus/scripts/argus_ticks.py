#!/usr/bin/env python3
"""argus_ticks.py — bounded tick ledger for Argus watches.

One append-only JSONL line per tick, plus a weekly rollup that answers the two
questions Argus otherwise cannot: *is a tracker still earning its schedule?* and
*is a source quietly starving?*

Ledger path: ``$ARGUS_TICK_LEDGER`` or ``~/.intel/state/ticks.jsonl``. The
default is deliberately shared across profiles and workdirs so one weekly
report covers every Argus job on the machine.

Record shape (all fields except ``job`` and ``outcome`` optional)::

    {"at": "...", "job": "...", "job_id": "...", "slug": "...",
     "outcome": "fired|silent|error|skipped", "reason": "...",
     "items_read": 34, "items_new": 0, "fired": 0, "errors": [],
     "sources": [{"source": "https://...", "status": 200, "items": 34, "ok": true}]}

Commands::

    argus_ticks.py record [--ledger P] [--at ISO] [JSON]
    argus_ticks.py rollup [--ledger P] [--days 14] [--silent-days 14]
                          [--cadence slug=monthly]... [--now ISO] [--prune]
    argus_ticks.py prune  [--ledger P] [--days 14] [--now ISO]
    argus_ticks.py --self-test

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUTCOMES = ("fired", "silent", "error", "skipped")
COMPLETED = ("fired", "silent", "skipped")

# A fetch error is more urgent than a source that merely has nothing new.
ERROR_STREAK_THRESHOLD = 2
ZERO_ITEM_STREAK_THRESHOLD = 3

CADENCE_DAYS = {"instant": 14, "daily": 14, "weekly": 21, "monthly": 45}


def default_ledger() -> Path:
    env = os.environ.get("ARGUS_TICK_LEDGER", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".intel" / "state" / "ticks.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_at(value) -> datetime:
    """Parse an ISO timestamp; naive values are treated as UTC."""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# ledger I/O
# ---------------------------------------------------------------------------


def append_record(ledger, record: dict) -> dict:
    """Append one validated record, stamping ``at`` when absent."""
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")
    outcome = str(record.get("outcome", "")).strip().lower()
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")
    if not str(record.get("job", "")).strip():
        raise ValueError("record must name a job")
    row = dict(record)
    row["outcome"] = outcome
    row["job"] = str(row["job"]).strip()
    row.setdefault("at", _iso(_now()))
    ledger = Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_records(ledger) -> list:
    """Read every valid record; corrupt lines are skipped, never fatal."""
    path = Path(ledger)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("at"):
            out.append(row)
    return out


def prune(ledger, now=None, days: int = 14) -> tuple:
    """Drop records older than ``days``. Returns ``(removed, kept)``."""
    now = now or _now()
    cutoff = now - timedelta(days=days)
    path = Path(ledger)
    if not path.exists():
        return (0, 0)
    kept_rows, removed = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict) or not row.get("at"):
                raise ValueError("malformed")
            if parse_at(row["at"]) < cutoff:
                removed += 1
                continue
            kept_rows.append(line)
        except Exception:
            removed += 1
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(ln + "\n" for ln in kept_rows), encoding="utf-8")
    tmp.replace(path)
    return (removed, len(kept_rows))


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def _in_window(records, now, days):
    cutoff = now - timedelta(days=days)
    out = []
    for row in records:
        try:
            if parse_at(row["at"]) >= cutoff:
                out.append(row)
        except Exception:
            continue
    return out


def _job_section(records) -> list:
    order, counts = [], {}
    for row in records:
        job = row.get("job") or "(unnamed)"
        if job not in counts:
            counts[job] = {"completed": 0, "failed": 0}
            order.append(job)
        if row.get("outcome") == "error":
            counts[job]["failed"] += 1
        else:
            counts[job]["completed"] += 1
    lines = []
    for job in sorted(order):
        c, f = counts[job]["completed"], counts[job]["failed"]
        lines.append(f"- {job} — {c} completed / {f} failed")
    return lines


def _source_attempts(records) -> dict:
    """Chronological attempt list per source URL."""
    seen = {}
    for row in sorted(records, key=lambda r: r.get("at", "")):
        for src in row.get("sources") or []:
            if not isinstance(src, dict):
                continue
            url = src.get("source")
            if not url:
                continue
            seen.setdefault(url, []).append(
                {
                    "job": row.get("job"),
                    "ok": bool(src.get("ok", True)),
                    "items": src.get("items", 0) or 0,
                    "status": src.get("status"),
                }
            )
    return seen


def _source_section(records) -> list:
    problems = []
    for url, attempts in sorted(_source_attempts(records).items()):
        error_streak = zero_streak = 0
        for att in reversed(attempts):
            if not att["ok"]:
                if zero_streak:
                    break
                error_streak += 1
            elif att["items"] == 0:
                if error_streak:
                    break
                zero_streak += 1
            else:
                break
        if error_streak >= ERROR_STREAK_THRESHOLD:
            problems.append(
                f"- {url} — {error_streak} consecutive error reads "
                f"(job: {attempts[-1]['job']}, last status: {attempts[-1]['status']})"
            )
        elif zero_streak >= ZERO_ITEM_STREAK_THRESHOLD:
            problems.append(
                f"- {url} — {zero_streak} consecutive zero-item reads (job: {attempts[-1]['job']})"
            )
    return problems


def _threshold_for(slug, silent_days, cadence):
    cadence_value = str((cadence or {}).get(slug, "")).strip().lower()
    if not cadence_value:
        return silent_days
    if cadence_value.isdigit():
        return max(silent_days, int(cadence_value))
    return max(silent_days, CADENCE_DAYS.get(cadence_value, silent_days))


def _retirement_section(records, now, silent_days, cadence) -> list:
    by_slug = {}
    for row in records:
        slug = row.get("slug")
        if not slug:
            continue
        entry = by_slug.setdefault(slug, {"last_fired": None, "first_seen": None, "job": row.get("job")})
        at = row.get("at")
        try:
            dt = parse_at(at)
        except Exception:
            continue
        if entry["first_seen"] is None or dt < entry["first_seen"]:
            entry["first_seen"] = dt
        if row.get("outcome") == "fired":
            if entry["last_fired"] is None or dt > entry["last_fired"]:
                entry["last_fired"] = dt
    lines = []
    for slug in sorted(by_slug):
        entry = by_slug[slug]
        reference = entry["last_fired"] or entry["first_seen"]
        if reference is None:
            continue
        silent = (now - reference).days
        if silent < _threshold_for(slug, silent_days, cadence):
            continue
        if entry["last_fired"] is None:
            lines.append(
                f"- `{slug}` — never fired in the window ({silent} days since first tick, "
                f"job: {entry['job']}) — suggest retirement or a gate review"
            )
        else:
            lines.append(
                f"- `{slug}` — silent {silent} days (job: {entry['job']}) — "
                "suggest retirement if the silence is not expected"
            )
    return lines


def build_report(records, now=None, days: int = 14, silent_days: int = 14,
                 cadence=None, pruned=None) -> str:
    now = now or _now()
    window = _in_window(records, now, days)
    out = [f"# Argus weekly rollup — {now.astimezone(timezone.utc).strftime('%Y-%m-%d')}", ""]

    out.append(f"## Jobs (last {days} days)")
    jobs = _job_section(window)
    out.extend(jobs if jobs else ["no ticks recorded"])
    out.append("")

    out.append("## Source health")
    sources = _source_section(window)
    out.extend(sources if sources else ["no source problems detected"])
    out.append("")

    out.append("## Silent trackers — retirement candidates")
    retired = _retirement_section(window, now, silent_days, cadence)
    out.extend(retired if retired else ["no retirement candidates"])
    out.append("")

    ledger_line = f"ledger: {len(window)} record(s) in window"
    if pruned is not None:
        ledger_line += f", pruned {pruned[0]} older record(s), {pruned[1]} kept"
    out.append(f"_{ledger_line}_")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_cadence(pairs) -> dict:
    out = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"--cadence expects slug=cadence, got {item!r}")
        key, value = item.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        run_self_test()
        return 0

    parser = argparse.ArgumentParser(description="Argus tick ledger")
    parser.add_argument("command", choices=["record", "rollup", "prune"])
    parser.add_argument("payload", nargs="?", help="JSON record (record only)")
    parser.add_argument("--ledger", default=str(default_ledger()))
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--silent-days", type=int, default=14)
    parser.add_argument("--cadence", action="append", default=[])
    parser.add_argument("--now")
    parser.add_argument("--prune", action="store_true", help="rollup: prune after reporting")
    args = parser.parse_args(argv)

    now = parse_at(args.now) if args.now else _now()

    if args.command == "record":
        raw = args.payload if args.payload is not None else sys.stdin.read()
        raw = (raw or "").strip()
        if not raw:
            print("record: no JSON supplied (pass an argument or pipe stdin)", file=sys.stderr)
            return 2
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"record: invalid JSON: {exc}", file=sys.stderr)
            return 2
        try:
            row = append_record(args.ledger, record)
        except ValueError as exc:
            print(f"record: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"recorded": row, "ledger": str(args.ledger)}, ensure_ascii=False))
        return 0

    if args.command == "prune":
        removed, kept = prune(args.ledger, now=now, days=args.days)
        print(json.dumps({"removed": removed, "kept": kept, "ledger": str(args.ledger)}))
        return 0

    pruned = prune(args.ledger, now=now, days=args.days) if args.prune else None
    records = load_records(args.ledger)
    report = build_report(
        records,
        now=now,
        days=args.days,
        silent_days=args.silent_days,
        cadence=_parse_cadence(args.cadence),
        pruned=pruned,
    )
    print(report)
    return 0


def run_self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "ticks.jsonl"
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        append_record(ledger, {"job": "j", "outcome": "silent", "slug": "s",
                               "sources": [{"source": "u", "status": 200, "items": 0, "ok": True}]})
        append_record(ledger, {"job": "j", "outcome": "error", "slug": "s"})
        records = load_records(ledger)
        assert len(records) == 2, records
        report = build_report(records, now=now, days=14, silent_days=14)
        assert "j — 1 completed / 1 failed" in report, report
        removed, kept = prune(ledger, now=now, days=14)
        assert (removed, kept) == (0, 2), (removed, kept)
    print("self-test OK: record/load/rollup/prune")


if __name__ == "__main__":
    raise SystemExit(main())
