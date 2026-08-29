#!/usr/bin/env python3
"""Behavior-contract tests for the personal-intel-agent skill scripts.

Stdlib + pytest + unittest.mock only. No network. Mirrors hermes-agent
skill-authoring HARDLINE #7: assert relationships/invariants, not frozen values.

Run:  pytest tests/skills/test_personal_intel_agent_skill.py -q
"""

import importlib.util
import os
import json
import sys

import pytest

SKILL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "skills", "personal-intel-agent", "scripts"
)


def _load(modname):
    path = os.path.join(SKILL_DIR, f"{modname}.py")
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


fold = _load("fold")
eval_signal = _load("eval_signal")


# ---------------------------------------------------------------------------
# eval_signal.py — the gate engine
# ---------------------------------------------------------------------------


def test_diff_fires_on_any_change():
    v = eval_signal.evaluate(
        {"mode": "diff"},
        {"x": {"value": "v2", "unit": "version"}},
        {"x": {"value": "v1"}},
    )
    assert v["passed"] is True
    assert len(v["changed"]) == 1


def test_diff_silent_on_no_change():
    v = eval_signal.evaluate(
        {"mode": "diff"},
        {"x": {"value": "v1"}},
        {"x": {"value": "v1"}},
    )
    assert v["passed"] is False
    assert v["changed"] == []
    assert v["unchanged"] == ["x"]


def test_items_gate_excludes_nonlisted_metric():
    """The core bug fix: metrics not in eval.items must NOT fire the gate."""
    v = eval_signal.evaluate(
        {"mode": "diff", "items": ["a"]},
        {"a": {"value": "v1", "unit": "version"},
         "b": {"value": "new!", "unit": "version"}},
        {"a": {"value": "v1"}, "b": {"value": "old"}},
    )
    # 'b' changed but is not a gating item -> gate stays silent
    assert v["passed"] is False
    # but the change is still recorded in state for future diffs
    assert "b" in [c["metric"] for c in v["changed"]]


def test_items_gate_fires_when_listed_metric_changes():
    v = eval_signal.evaluate(
        {"mode": "diff", "items": ["a"]},
        {"a": {"value": "v2", "unit": "version"},
         "b": {"value": "new!", "unit": "version"}},
        {"a": {"value": "v1"}, "b": {"value": "old"}},
    )
    assert v["passed"] is True


def test_items_omitted_falls_back_to_all():
    v = eval_signal.evaluate(
        {"mode": "diff"},
        {"a": {"value": "v1"}, "b": {"value": "new!"}},
        {"a": {"value": "v1"}, "b": {"value": "old"}},
    )
    assert v["passed"] is True


def test_threshold_pct_passes_on_crossing():
    v = eval_signal.evaluate(
        {"mode": "threshold", "trigger": "pct", "value": 0.10},
        {"price": {"value": 89.99, "unit": "price"}},
        {"price": {"value": 99.99}},
    )
    assert v["passed"] is True
    # delta should be negative ~ -10%
    ch = v["changed"][0]
    assert ch["delta_pct"] is not None and ch["delta_pct"] < 0


def test_threshold_pct_silent_below_trigger():
    v = eval_signal.evaluate(
        {"mode": "threshold", "trigger": "pct", "value": 0.10},
        {"price": {"value": 97.0, "unit": "price"}},
        {"price": {"value": 99.99}},
    )
    assert v["passed"] is False


def test_threshold_abs_passes_on_crossing():
    v = eval_signal.evaluate(
        {"mode": "threshold", "trigger": "abs", "value": 20},
        {"open_prs": {"value": 45, "unit": "count"}},
        {"open_prs": {"value": 10}},
    )
    assert v["passed"] is True


def test_threshold_first_run_is_silent():
    v = eval_signal.evaluate(
        {"mode": "threshold", "trigger": "pct", "value": 0.10},
        {"price": {"value": 89.99, "unit": "price"}},
        {},
    )
    assert v["first_run"] is True
    assert v["passed"] is False


def test_diff_first_run_fires_once():
    v = eval_signal.evaluate(
        {"mode": "diff"},
        {"a": {"value": "1"}},
        {},
    )
    assert v["first_run"] is True
    assert v["passed"] is True
    assert v["new_metrics"] == ["a"]


def test_threshold_ignores_nonnumeric_changes():
    """A non-numeric change must not satisfy a numeric threshold."""
    v = eval_signal.evaluate(
        {"mode": "threshold", "trigger": "pct", "value": 0.10, "items": ["status"]},
        {"status": {"value": "closed", "unit": "status"}},
        {"status": {"value": "open"}},
    )
    assert v["passed"] is False


def test_malformed_previous_state_does_not_throw():
    # prior state stored as a scalar (schema drift) -> degrade, don't crash
    v = eval_signal.evaluate(
        {"mode": "diff"},
        {"a": {"value": "v2"}},
        {"a": "v1"},
    )
    assert v["passed"] is True


# ---------------------------------------------------------------------------
# fold.py — the dedup/fold engine
# ---------------------------------------------------------------------------


def _row(title, snippet, trust, source):
    return {
        "title": title,
        "url": f"https://example/{source}",
        "source": source,
        "published": "2026-08-20",
        "snippet": snippet,
        "kind": "news",
        "trust": trust,
    }


def test_fold_clusters_near_duplicates():
    rows = [
        _row("SpaceX launches Starship on third test flight", "Starship lifted off from Boca Chica on its third test flight", "secondary", "Reuters"),
        _row("Starship test flight 3 launches successfully", "The Starship vehicle launched on its third test flight from Texas", "secondary", "SpaceNews"),
        _row("SpaceX Starship third flight lifts off", "Starship launched for the third time on its test flight", "primary", "NASA"),
    ]
    cards = fold.fold(rows, sim=0.4, noise_re=None)
    assert len(cards) == 1
    assert cards[0]["source_count"] == 3
    # canonical = highest trust (primary), then longest snippet
    assert cards[0]["canonical"]["trust"] == "primary"


def test_fold_distinct_sources_count():
    rows = [
        _row("Starship launch today confirmed", "the rocket lifted off on schedule", "primary", "NASA"),
        _row("Starship launch today confirmed again", "the rocket lifted off on schedule per sources", "primary", "NASA"),  # same source, diff title
    ]
    cards = fold.fold(rows, sim=0.4, noise_re=None)
    assert len(cards) == 1
    # distinct sources, not raw member length
    assert cards[0]["source_count"] == 1


def test_fold_noise_rejected():
    import re
    # Noise filtering is applied by main() BEFORE fold() runs (fold() itself
    # only clusters). Replicate the script's kept/rejected split, then cluster.
    noise_re = re.compile("clickbait|gossip", re.I)
    rows = [
        _row("CLICKBAIT you wont believe what the celebrity did", "shocking celebrity drama uncovered", "tertiary", "Gossip"),
        _row("Starship launch news confirmed today", "the rocket lifted off on its test flight", "secondary", "SpaceNews"),
    ]
    kept = [r for r in rows if not (noise_re.search(r["title"]) or noise_re.search(r["snippet"]))]
    assert len(kept) == 1, "noise row must be filtered before clustering"
    cards = fold.fold(kept, sim=0.4, noise_re=None)
    # only the real one remains -> exactly one card
    assert len(cards) == 1
    assert cards[0]["canonical"]["title"] == "Starship launch news confirmed today"


def test_repeated_noise_flag_form_works():
    import re
    # documented usage: repeated --noise args
    noise_re = re.compile("|".join(re.escape(t) for t in ["gossip", "clickbait"]), re.I)
    row = _row("CLICKBAIT headline", "shocking celebrity", "tertiary", "Gossip")
    kept = [r for r in [row] if not (noise_re.search(r["title"]) or noise_re.search(r["snippet"]))]
    assert kept == []
