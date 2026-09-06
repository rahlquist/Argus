#!/usr/bin/env python3
"""Bounded GitHub repository identity and event deduplication helpers.

Collection/auth/ranking remain orchestration concerns. These pure helpers keep
persistent repository state compact: one state record per canonical owner/repo,
plus sparse events only for meaningful pushed_at transitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple


def canonical_repo_id(full_name: str) -> str:
    """Return a stable case-insensitive owner/repository identity."""
    return str(full_name).strip().lower()


def canonical_repo_id_from_record(repo: Dict[str, Any]) -> str:
    value = repo.get("full_name") or repo.get("html_url", "").rstrip("/").split("github.com/")[-1]
    return canonical_repo_id(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if str(x)]
    return [str(value)] if value else []


def observe_repo(existing: Optional[Dict[str, Any]], repo: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Merge one observation and return (state, sparse_event_or_none).

    A new activity event is emitted once per distinct pushed_at value. Star or
    source changes alone update state silently.
    """
    existing = dict(existing or {})
    repo_id = canonical_repo_id_from_record(repo)
    pushed = repo.get("pushed_at")
    source = repo.get("source")
    state = {
        **existing,
        "repo_id": repo_id,
        "full_name": repo.get("full_name") or existing.get("full_name") or repo_id,
        "html_url": repo.get("html_url") or existing.get("html_url"),
        "first_seen": existing.get("first_seen") or _now(),
        "last_seen": _now(),
        "times_seen": int(existing.get("times_seen", 0)) + 1,
        "last_pushed_at": pushed or existing.get("last_pushed_at"),
        "last_stars": repo.get("stars", existing.get("last_stars")),
    }
    sources = _source_list(existing.get("sources_seen"))
    if source and source not in sources:
        sources.append(str(source))
    state["sources_seen"] = sources

    previous_pushed = existing.get("last_pushed_at")
    reported = existing.get("last_reported_pushed_at")
    if pushed and previous_pushed and pushed != previous_pushed and pushed != reported:
        state["last_reported_pushed_at"] = pushed
        return state, {
            "event": "new_activity",
            "repo": repo_id,
            "url": state["html_url"],
            "old_pushed_at": previous_pushed,
            "new_pushed_at": pushed,
            "observed_at": state["last_seen"],
            "source": source,
        }
    if not existing and pushed:
        state["last_reported_pushed_at"] = pushed
    return state, None


def bound_candidates(rows: Iterable[Dict[str, Any]], limit: int) -> list[Dict[str, Any]]:
    """Cap per-run candidate volume before LLM processing or persistence."""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    return list(rows)[:limit]
