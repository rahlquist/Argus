#!/usr/bin/env python3
"""argus_scratch.py — undirected scratching: propose trackers, never stories.

DISCOVER is directed: it is seeded from interests you already track, so it can
only return more of the same. Scratch is the opposite — it proposes *new*
trackers, from deliberately undirected searches, as reviewable drafts.

The agent does the searching (that is judgment work). This script owns the
deterministic parts: scoring, dedupe against what you already track, capping,
expiry, decisions, and emitting a tracker spec skeleton on acceptance.

Nothing is ever created automatically. An accepted tracker is a permanent token
cost, so acceptance is always an explicit human act.

Input (JSON on stdin)::

    {"existing": ["motherboard-sales", ...],
     "candidates": [
       {"theme": "mcp-observability-tooling",
        "interest": "multi-profile fleet management",
        "why": "3 of 9 hits connect to fleet management; you run 20+ MCP servers",
        "hits": [{"title": "...", "url": "...", "source": "..."}]}]}

Commands::

    argus_scratch.py propose [--store P] [--max 3] [--now ISO]     # JSON on stdin
    argus_scratch.py list    [--store P] [--now ISO]
    argus_scratch.py accept  <id> [--store P] [--now ISO]
    argus_scratch.py reject  <id> [--store P] [--now ISO]
    argus_scratch.py expire  [--store P] [--days 30] [--now ISO]
    argus_scratch.py --self-test

Store: ``$ARGUS_SCRATCH_STORE`` or ``~/.intel/state/scratch/proposals.jsonl``.
Append-only: each decision appends a record; the latest record per id wins.

Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_TTL_DAYS = 30
DEFAULT_MAX_PROPOSALS = 3
PENDING = "pending"


def default_store() -> Path:
    env = os.environ.get("ARGUS_SCRATCH_STORE", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".intel" / "state" / "scratch" / "proposals.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def slugify(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(text).lower())).strip("-")


def proposal_id(theme: str) -> str:
    """Stable id so re-proposing the same theme never creates a duplicate."""
    slug = slugify(theme) or "proposal"
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


# ---------------------------------------------------------------------------
# store
# ---------------------------------------------------------------------------


def load_latest(store) -> dict:
    """Latest record per id (append-only store, later records win)."""
    path = Path(store)
    latest = {}
    if not path.exists():
        return latest
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("id"):
            latest[rec["id"]] = {**latest.get(rec["id"], {}), **rec}
    return latest


def _append(store, record: dict) -> dict:
    path = Path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------


def _score(candidate: dict) -> float:
    hits = candidate.get("hits") or []
    score = float(len(hits))
    if candidate.get("interest"):
        score += 1.0
    if candidate.get("why"):
        score += 0.5
    return score


def propose(candidates, store=None, now=None, existing=None,
            max_proposals=DEFAULT_MAX_PROPOSALS, ttl_days=DEFAULT_TTL_DAYS) -> dict:
    """Score, dedupe, cap, and persist candidate tracker proposals."""
    store = store or default_store()
    now = now or _now()
    existing_norm = {slugify(e) for e in (existing or []) if str(e).strip()}
    latest = load_latest(store)

    accepted, skipped, deferred = [], [], []
    ranked = []
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            raise ValueError("each candidate must be an object")
        theme = str(candidate.get("theme") or "").strip()
        if not theme:
            raise ValueError("each candidate needs a 'theme'")
        norm = slugify(theme)
        if norm in existing_norm:
            skipped.append({"theme": theme, "reason": "already tracked"})
            continue
        ranked.append(candidate)
    ranked.sort(key=_score, reverse=True)

    for candidate in ranked:
        theme = str(candidate["theme"]).strip()
        pid = proposal_id(theme)
        if len(accepted) >= max_proposals:
            deferred.append({"theme": theme, "reason": "over per-run cap"})
            continue
        if pid in latest and latest[pid].get("status") == PENDING:
            accepted.append(latest[pid])          # idempotent re-proposal
            continue
        record = {
            "id": pid,
            "theme": theme,
            "interest": candidate.get("interest"),
            "why": candidate.get("why"),
            "hits": candidate.get("hits") or [],
            "evidence": len(candidate.get("hits") or []),
            "score": round(_score(candidate), 2),
            "status": PENDING,
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(days=ttl_days)),
        }
        _append(store, record)
        latest[pid] = record
        accepted.append(record)
    return {"accepted": accepted, "skipped": skipped, "deferred": deferred}


# ---------------------------------------------------------------------------
# read / decide
# ---------------------------------------------------------------------------


def list_pending(store=None, now=None) -> list:
    store = store or default_store()
    now = now or _now()
    out = []
    for rec in load_latest(store).values():
        if rec.get("status") != PENDING:
            continue
        try:
            if _parse(rec["expires_at"]) <= now:
                continue
        except Exception:
            pass
        out.append(rec)
    return sorted(out, key=lambda r: (-float(r.get("score", 0)), r["id"]))


def tracker_spec(record: dict, now=None) -> str:
    """YAML skeleton for an accepted proposal. Review before use."""
    now = now or _now()
    sources = []
    for hit in record.get("hits") or []:
        url = hit.get("url")
        if url:
            sources.append(f'  - url: {url}\n    type: web\n    trust: secondary')
    if not sources:
        sources.append("  - url: <add at least one primary source>\n    type: web\n    trust: primary")
    why = record.get("why") or f"Proposed from scratch search: {record.get('theme')}"
    return "\n".join([
        f"slug: {record['id']}",
        f"entity: {record.get('theme')}",
        "type: field",
        f"user_sentence: \"{why}\"",
        "signals:",
        "  - new-release",
        "  - notable-change",
        "noise:",
        "  - off-topic",
        "  - social-media-speculation",
        "cadence: weekly",
        "verification: loose",
        "sources:",
        *sources,
        "delivery:",
        "  - feed",
        f"created: {now.astimezone(timezone.utc).strftime('%Y-%m-%d')}",
        "last_tick: null",
        "status: live",
    ]) + "\n"


def decide(pid: str, decision: str, store=None, now=None) -> dict:
    """Record accept/reject. Returns the updated record (accept adds a spec)."""
    if decision not in ("accept", "reject"):
        raise ValueError("decision must be 'accept' or 'reject'")
    store = store or default_store()
    now = now or _now()
    latest = load_latest(store)
    if pid not in latest:
        raise KeyError(f"unknown proposal id: {pid}")
    record = latest[pid]
    status = "accepted" if decision == "accept" else "rejected"
    updated = {**record, "status": status, "decided_at": _iso(now)}
    if decision == "accept":
        updated["spec"] = tracker_spec(updated, now=now)
    _append(store, updated)
    return updated


def expire(store=None, now=None, days=DEFAULT_TTL_DAYS) -> int:
    """Mark stale pending proposals expired. Returns how many were expired."""
    store = store or default_store()
    now = now or _now()
    cutoff = now - timedelta(days=days)
    count = 0
    for rec in load_latest(store).values():
        if rec.get("status") != PENDING:
            continue
        try:
            created = _parse(rec.get("created_at") or now)
        except Exception:
            continue
        if created <= cutoff:
            _append(store, {**rec, "status": "expired", "expired_at": _iso(now)})
            count += 1
    return count


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def render(proposals, now=None) -> str:
    now = now or _now()
    if not proposals:
        return "No tracker proposals pending. Scratch found nothing worth watching."
    lines = [f"# Argus scratch — {len(proposals)} tracker proposal(s)", ""]
    for p in proposals:
        expires = ""
        try:
            expires = _parse(p["expires_at"]).astimezone(timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            pass
        lines.append(f"## {p.get('theme')}  ·  id `{p['id']}`")
        if p.get("interest"):
            lines.append(f"**Interest:** {p['interest']}")
        if p.get("why"):
            lines.append(f"**Why:** {p['why']}")
        lines.append(f"**Evidence:** {p.get('evidence', len(p.get('hits') or []))} hit(s)")
        for hit in (p.get("hits") or [])[:5]:
            title = hit.get("title") or hit.get("url") or "(untitled)"
            source = hit.get("source") or ""
            lines.append(f"- {title}{f' — {source}' if source else ''}")
        lines.append("**Suggested cadence:** weekly   ·   **Cost:** ~1 tick/week")
        lines.append(f"**Accept:** `argus_scratch.py accept {p['id']}`   "
                     f"**Reject:** `argus_scratch.py reject {p['id']}`")
        if expires:
            lines.append(f"**Expires:** {expires}")
        lines.append("")
    lines.append("Nothing is created automatically — an accepted tracker is a permanent token cost.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        run_self_test()
        return 0

    parser = argparse.ArgumentParser(description="Argus scratch — tracker proposals")
    parser.add_argument("command", choices=["propose", "list", "accept", "reject", "expire"])
    parser.add_argument("proposal_id", nargs="?")
    parser.add_argument("--store", default=str(default_store()))
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_PROPOSALS)
    parser.add_argument("--days", type=int, default=DEFAULT_TTL_DAYS)
    parser.add_argument("--now")
    args = parser.parse_args(argv)
    now = _parse(args.now) if args.now else _now()

    if args.command == "propose":
        raw = sys.stdin.read().strip()
        if not raw:
            print("propose: no JSON on stdin", file=sys.stderr)
            return 2
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"propose: invalid JSON: {exc}", file=sys.stderr)
            return 2
        candidates = payload.get("candidates") if isinstance(payload, dict) else payload
        existing = payload.get("existing") if isinstance(payload, dict) else []
        try:
            out = propose(candidates, store=args.store, now=now,
                          existing=existing, max_proposals=args.max, ttl_days=args.days)
        except ValueError as exc:
            print(f"propose: {exc}", file=sys.stderr)
            return 2
        for item in out["skipped"]:
            print(f"skipped {item['theme']}: {item['reason']}", file=sys.stderr)
        for item in out["deferred"]:
            print(f"deferred {item['theme']}: {item['reason']}", file=sys.stderr)
        print(render(out["accepted"], now=now))
        return 0

    if args.command == "list":
        print(render(list_pending(store=args.store, now=now), now=now))
        return 0

    if args.command == "expire":
        count = expire(store=args.store, now=now, days=args.days)
        print(f"expired {count} stale proposal(s)")
        return 0

    if not args.proposal_id:
        print(f"{args.command}: needs a proposal id", file=sys.stderr)
        return 2
    try:
        updated = decide(args.proposal_id, args.command, store=args.store, now=now)
    except (KeyError, ValueError) as exc:
        print(f"{args.command}: {exc}", file=sys.stderr)
        return 2
    print(f"{args.command}ed {updated['id']} ({updated['theme']})")
    if args.command == "accept":
        print()
        print(updated["spec"])
    return 0


def run_self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "proposals.jsonl"
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        cands = [
            {"theme": "mcp-observability-tooling", "interest": "fleet management",
             "why": "20+ MCP servers, no visibility",
             "hits": [{"title": "a"}, {"title": "b"}, {"title": "c"}]},
            {"theme": "motherboard-sales", "interest": "deals", "hits": [{"title": "x"}]},
            {"theme": "thin", "hits": [{"title": "y"}]},
            {"theme": "thinner", "hits": [{"title": "z"}]},
        ]
        out = propose(cands, store=store, now=now, existing=["motherboard-sales"], max_proposals=2)
        assert len(out["accepted"]) == 2, out
        assert out["accepted"][0]["theme"] == "mcp-observability-tooling"
        assert out["skipped"][0]["theme"] == "motherboard-sales"
        assert len(out["deferred"]) == 1
        pid = out["accepted"][0]["id"]
        pending = list_pending(store=store, now=now)
        assert pid in [p["id"] for p in pending], pending
        assert render(pending, now=now).count("## ") == len(pending)
        acc = decide(pid, "accept", store=store, now=now)
        assert f"slug: {pid}" in acc["spec"] and "status: live" in acc["spec"]
        assert all(p["id"] != pid for p in list_pending(store=store, now=now))
        old = now - timedelta(days=45)
        stale = propose([{"theme": "stale-one", "hits": [{"title": "q"}]}],
                        store=store, now=old, existing=[])["accepted"][0]
        assert expire(store=store, now=now, days=30) >= 1
        assert stale["id"] not in [p["id"] for p in list_pending(store=store, now=now)]
    print("self-test OK: propose/dedupe/cap/accept/expire/render")


if __name__ == "__main__":
    raise SystemExit(main())
