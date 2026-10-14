#!/usr/bin/env python3
"""Behavior-contract tests for the Argus collector engine (scripts/argus_collect.py)."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
MODULE_PATH = ROOT / "skills" / "argus" / "scripts" / "argus_collect.py"
spec = importlib.util.spec_from_file_location("argus_collect", MODULE_PATH)
assert spec is not None and spec.loader is not None
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)


class FakeCtx:
    """Injected I/O so collectors are testable without network or disk."""

    def __init__(self, files=None, http=None):
        self.files = files or {}
        self.http = http or {}
        self.fetched = []

    def read_file(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def fetch(self, url):
        self.fetched.append(url)
        if url not in self.http:
            raise RuntimeError(f"no fixture for {url}")
        return self.http[url]


# ---------------------------------------------------------------------------
# spec parsing
# ---------------------------------------------------------------------------


def test_parses_inline_call_syntax():
    name, kwargs = collect.parse_collector_spec('github.release_tag(repo="owner/repo")')
    assert name == "github.release_tag"
    assert kwargs == {"repo": "owner/repo"}


def test_parses_multiple_kwargs_and_numeric_coercion():
    name, kwargs = collect.parse_collector_spec(
        'http.regex(url="https://x/y", pattern="v(\\\\d+)", group=1)'
    )
    assert name == "http.regex"
    assert kwargs["group"] == 1
    assert kwargs["url"] == "https://x/y"


def test_bare_name_without_parens_parses():
    name, kwargs = collect.parse_collector_spec("github.release_tag")
    assert name == "github.release_tag"
    assert kwargs == {}


def test_name_plus_args_mapping_merges():
    metric = {
        "collector": "github.release_tag",
        "args": {"repo": "owner/repo"},
    }
    name, kwargs = collect.resolve_collector(metric)
    assert name == "github.release_tag"
    assert kwargs["repo"] == "owner/repo"


def test_malformed_spec_raises():
    with pytest.raises(ValueError):
        collect.parse_collector_spec("github.release_tag(repo=")


# ---------------------------------------------------------------------------
# collectors
# ---------------------------------------------------------------------------


def test_file_json_path_reads_nested_value():
    ctx = FakeCtx(files={"/scan.json": json.dumps({"github_repos": [{"name": "a"}, {"name": "b"}]})})
    metric = {"name": "provider_count", "unit": "count", "collector": "file.json_path",
              "args": {"path": "/scan.json", "json_path": "github_repos"}}
    out = collect.collect_metric(metric, ctx)
    assert out["value"] == [{"name": "a"}, {"name": "b"}]
    assert out["deterministic"] is True
    assert out["error"] is None


def test_file_json_set_returns_sorted_unique_list():
    ctx = FakeCtx(files={"/scan.json": json.dumps({"github_repos": [{"name": "b"}, {"name": "a"}, {"name": "a"}]})})
    metric = {"name": "provider_set", "unit": "status", "collector": "file.json_set",
              "args": {"path": "/scan.json", "json_path": "github_repos", "key": "name"}}
    out = collect.collect_metric(metric, ctx)
    assert out["value"] == ["a", "b"]


def test_file_count_glob_counts_matches():
    ctx = FakeCtx(files={"/dir": "x"})
    metric = {"name": "n", "unit": "count", "collector": "file.count_glob",
              "args": {"path": "/dir", "pattern": "*.md"}}
    ctx.count_glob = lambda path, pattern: 4
    out = collect.collect_metric(metric, ctx)
    assert out["value"] == 4


def test_http_json_path_uses_fetcher():
    ctx = FakeCtx(http={"https://api.example/releases": json.dumps([{"tag_name": "v1.2.3"}])})
    metric = {"name": "ver", "unit": "version", "collector": "http.json_path",
              "args": {"url": "https://api.example/releases", "json_path": "0.tag_name"}}
    out = collect.collect_metric(metric, ctx)
    assert out["value"] == "v1.2.3"
    assert out["url"] == "https://api.example/releases"


def test_http_regex_extracts_group():
    ctx = FakeCtx(http={"https://x/y": "release v11.8.1 shipped"})
    metric = {"name": "ver", "unit": "version", "collector": "http.regex",
              "args": {"url": "https://x/y", "pattern": r"v(\d+\.\d+\.\d+)"}}
    out = collect.collect_metric(metric, ctx)
    assert out["value"] == "11.8.1"


def test_github_release_tag_uses_github_api():
    ctx = FakeCtx(http={"https://api.github.com/repos/o/r/releases?per_page=1": json.dumps([{"tag_name": "v2"}])})
    metric = {"name": "v", "unit": "version", "collector": "github.release_tag",
              "args": {"repo": "o/r"}}
    out = collect.collect_metric(metric, ctx)
    assert out["value"] == "v2"


def test_github_issue_state_maps_to_open_closed():
    ctx = FakeCtx(http={"https://api.github.com/repos/o/r/issues/341": json.dumps({"state": "closed"})})
    metric = {"name": "issue", "unit": "status", "collector": "github.issue_state",
              "args": {"repo": "o/r", "number": 341}}
    out = collect.collect_metric(metric, ctx)
    assert out["value"] == "closed"


def test_unknown_collector_is_an_error_not_a_crash():
    metric = {"name": "x", "unit": "status", "collector": "nope.missing", "args": {}}
    out = collect.collect_metric(metric, FakeCtx())
    assert out["error"]
    assert out["value"] == "<error>"
    assert out["deterministic"] is True


def test_fetch_failure_marks_error_and_never_invents_a_value():
    metric = {"name": "v", "unit": "version", "collector": "http.json_path",
              "args": {"url": "https://down.example/x", "json_path": "0"}}
    out = collect.collect_metric(metric, FakeCtx())
    assert out["error"]
    assert out["value"] == "<error>"


def test_llm_extract_requires_supplied_value_and_is_marked_nondeterministic():
    metric = {"name": "kernel_note", "unit": "status", "collector": "llm_extract",
              "args": {"prompt": "one-line amdxdna kernel status"}}
    missing = collect.collect_metric(metric, FakeCtx())
    assert missing["deterministic"] is False
    assert missing["error"]

    supplied = collect.collect_metric(metric, FakeCtx(), provided={"kernel_note": "amdxdna in mainline"})
    assert supplied["value"] == "amdxdna in mainline"
    assert supplied["deterministic"] is False


# ---------------------------------------------------------------------------
# whole-spec collection + output shape
# ---------------------------------------------------------------------------


def test_collect_all_produces_eval_signal_compatible_shape():
    spec_obj = {
        "slug": "demo",
        "metrics": [
            {"name": "a", "unit": "version", "collector": "http.regex",
             "args": {"url": "https://x/y", "pattern": r"v(\d+)"}},
        ],
    }
    ctx = FakeCtx(http={"https://x/y": "v9"})
    out = collect.collect_all(spec_obj, ctx)
    assert out["slug"] == "demo"
    assert set(out["metrics"]["a"]) >= {"value", "unit", "url", "error"}
    assert out["metrics"]["a"]["value"] == "9"
    # drop-in compatible with state/<slug>.current.json
    assert "last_run" in out


def test_collect_all_keeps_going_after_one_metric_fails():
    spec_obj = {
        "slug": "demo",
        "metrics": [
            {"name": "bad", "unit": "version", "collector": "http.json_path",
             "args": {"url": "https://down/x", "json_path": "0"}},
            {"name": "good", "unit": "version", "collector": "http.regex",
             "args": {"url": "https://x/y", "pattern": r"v(\d+)"}},
        ],
    }
    ctx = FakeCtx(http={"https://x/y": "v9"})
    out = collect.collect_all(spec_obj, ctx)
    assert out["metrics"]["bad"]["error"]
    assert out["metrics"]["good"]["value"] == "9"
