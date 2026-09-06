#!/usr/bin/env python3
"""Tests for Argus GitHub repository identity/event deduplication."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[2]
MODULE_PATH = ROOT / "skills" / "argus" / "scripts" / "github_discovery.py"
spec = importlib.util.spec_from_file_location("github_discovery", MODULE_PATH)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def repo(pushed="2026-09-01T00:00:00Z", stars=100):
    return {
        "full_name": "Owner/Repo",
        "html_url": "https://github.com/Owner/Repo",
        "description": "A useful MCP tool",
        "stars": stars,
        "pushed_at": pushed,
        "source": "api",
    }


def test_canonical_repo_id_is_case_insensitive():
    assert mod.canonical_repo_id("Owner/Repo") == "owner/repo"
    assert mod.canonical_repo_id_from_record(repo()) == "owner/repo"


def test_unchanged_observation_does_not_create_event():
    state, _ = mod.observe_repo({}, repo())
    state2, event = mod.observe_repo(state, repo())
    assert event is None
    assert state2["times_seen"] == 2


def test_new_pushed_at_creates_one_activity_event():
    state = mod.observe_repo({}, repo("2026-09-01T00:00:00Z"))[0]
    updated, event = mod.observe_repo(state, repo("2026-09-02T00:00:00Z"))
    assert event["event"] == "new_activity"
    assert event["old_pushed_at"] == "2026-09-01T00:00:00Z"
    assert event["new_pushed_at"] == "2026-09-02T00:00:00Z"
    assert updated["last_reported_pushed_at"] == "2026-09-02T00:00:00Z"


def test_duplicate_sources_merge_without_event_or_duplicate_state():
    first = repo()
    first["source"] = "api:topic:mcp"
    state = mod.observe_repo({}, first)[0]
    second = repo()
    second["source"] = "trending-weekly"
    updated, event = mod.observe_repo(state, second)
    assert event is None
    assert updated["sources_seen"] == ["api:topic:mcp", "trending-weekly"]


def test_event_archive_dedup_key_prevents_repeated_activity_event():
    state = mod.observe_repo({}, repo("2026-09-01T00:00:00Z"))[0]
    state, event = mod.observe_repo(state, repo("2026-09-02T00:00:00Z"))
    assert event is not None
    state["last_pushed_at"] = "2026-09-01T00:00:00Z"
    state, event2 = mod.observe_repo(state, repo("2026-09-02T00:00:00Z"))
    assert event2 is None


def test_bound_candidates_limits_volume():
    rows = [dict(repo(), full_name=f"o/r{i}") for i in range(10)]
    assert len(mod.bound_candidates(rows, 3)) == 3
