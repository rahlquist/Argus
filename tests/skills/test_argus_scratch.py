#!/usr/bin/env python3
"""Tests for fold.py --eval (threshold measurement) and argus_scratch.py."""

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def _load(name, rel):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fold = _load("fold", "skills/argus/scripts/fold.py")
scratch = _load("argus_scratch", "skills/argus/scripts/argus_scratch.py")

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def row(title, snippet=""):
    return {"title": title, "snippet": snippet, "source": "test", "trust": "secondary"}


# ---------------------------------------------------------------------------
# fold.py --eval : labeled-fixture scoring
# ---------------------------------------------------------------------------


def _fixture(tmp_path, cases, name="fx.jsonl"):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(c) for c in cases) + "\n")
    return p


def test_load_cases_skips_meta_line(tmp_path):
    fx = _fixture(tmp_path, [
        {"_meta": {"purpose": "x"}},
        {"id": "a", "rows": [row("one"), row("two")], "labels": [[0, 1, "same"]]},
    ])
    cases = fold.load_cases(fx)
    assert len(cases) == 1
    assert cases[0]["id"] == "a"


def test_load_cases_rejects_label_index_out_of_range(tmp_path):
    fx = _fixture(tmp_path, [
        {"id": "bad", "rows": [row("one")], "labels": [[0, 5, "same"]]},
    ])
    with pytest.raises(ValueError):
        fold.load_cases(fx)


def test_load_cases_rejects_unknown_label(tmp_path):
    fx = _fixture(tmp_path, [
        {"id": "bad", "rows": [row("one"), row("two")], "labels": [[0, 1, "maybe"]]},
    ])
    with pytest.raises(ValueError):
        fold.load_cases(fx)


def test_score_threshold_counts_true_and_false_positives():
    # near-identical but DIFFERENT boards (must not merge) + one true duplicate
    case = {
        "id": "c1",
        "rows": [
            row("GIGABYTE X870E AORUS PRO X3D ICE AM5 LGA 1718 ATX Motherboard",
                "339.99 free shipping at Amazon"),
            row("GIGABYTE X870E AORUS MASTER X3D ICE AM5 AMD X870E ATX Motherboard",
                "549.99 with liquid cooler bundle"),
            row("X870E Aorus Pro X3D ICE motherboard drops to 339.99",
                "AM5 LGA 1718 ATX board on sale"),
            row("Council approves new parking meter contract downtown",
                "the city council voted on parking meter maintenance"),
        ],
        "labels": [[0, 2, "same"], [0, 1, "different"], [1, 2, "different"],
                   [0, 3, "different"], [1, 3, "different"]],
    }
    low = fold.score_threshold([case], 0.05)    # similar boards collapse together
    high = fold.score_threshold([case], 0.95)   # nothing merges

    assert low["tp"] == 1
    assert low["fp"] == 2                       # the two "different" boards got merged
    assert low["precision"] < 1.0
    assert low["recall"] == 1.0

    assert high["tp"] == 0
    assert high["fn"] == 1                      # the "same" pair got split
    assert high["recall"] == 0.0


def test_score_threshold_perfect_separation():
    case = {
        "id": "c2",
        "rows": [
            row("SpaceX Starship third flight lifts off from Boca Chica",
                "Starship launched for the third time on its test flight"),
            row("Starship test flight three launches successfully from Texas",
                "the Starship vehicle launched on its third test flight"),
            row("Council approves new parking meter contract downtown",
                "the city council voted on parking meter maintenance"),
        ],
        "labels": [[0, 1, "same"], [0, 2, "different"], [1, 2, "different"]],
    }
    mid = fold.score_threshold([case], 0.4)
    assert mid["precision"] == 1.0
    assert mid["recall"] == 1.0
    assert mid["f1"] == 1.0


def test_score_threshold_reports_undefined_metrics_as_none():
    """No positive predictions among labeled pairs -> precision is undefined, not 0."""
    case = {
        "id": "c3",
        "rows": [row("alpha beta gamma delta"), row("alpha beta gamma delta"),
                 row("epsilon zeta eta theta")],
        "labels": [[0, 2, "different"]],   # 0-1 deliberately unlabeled
    }
    out = fold.score_threshold([case], 0.05)
    assert out["pairs"] == 1
    assert out["fp"] == 0          # merging 0+1 is not penalised because it is unlabeled
    assert out["tn"] == 1
    assert out["precision"] is None
    assert out["recall"] is None
    assert out["f1"] is None


def test_eval_table_reports_every_threshold_and_marks_best(tmp_path):
    cases = [
        {"id": "c1", "rows": [row("a b c d e"), row("a b c d e"), row("v w x y z")],
         "labels": [[0, 1, "same"], [0, 2, "different"], [1, 2, "different"]]},
    ]
    fx = _fixture(tmp_path, cases)
    table = fold.eval_table(fold.load_cases(fx), [0.2, 0.5, 0.9])
    assert [r["sim"] for r in table["rows"]] == [0.2, 0.5, 0.9]
    assert table["best"]["sim"] in (0.2, 0.5, 0.9)
    text = fold.render_eval_table(table)
    assert "precision" in text
    assert "recall" in text
    for r in table["rows"]:
        assert f"{r['sim']:.2f}" in text


def test_shipped_fixture_set_loads_and_separates():
    fx = ROOT / "skills" / "argus" / "assets" / "fold-labels.jsonl"
    cases = fold.load_cases(fx)
    assert len(cases) >= 6, cases
    assert sum(len(c["labels"]) for c in cases) >= 18
    table = fold.eval_table(cases, [0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
    # every sweep row must be scoreable; at least one threshold should beat trivial
    assert all(r["pairs"] > 0 for r in table["rows"])
    assert max(r["f1"] or 0.0 for r in table["rows"]) > 0.5


# ---------------------------------------------------------------------------
# argus_scratch.py : tracker proposal channel
# ---------------------------------------------------------------------------


def cand(theme, interest="fleet management", hits=3):
    return {
        "theme": theme,
        "interest": interest,
        "why": f"{hits} hits connect to {interest}",
        "hits": [{"title": f"{theme} item {i}", "source": f"src{i}"} for i in range(hits)],
    }


def test_propose_assigns_stable_id_and_expiry(tmp_path):
    store = tmp_path / "proposals.jsonl"
    out = scratch.propose([cand("mcp-observability")], store=store, now=NOW, existing=[])
    assert len(out["accepted"]) == 1
    p = out["accepted"][0]
    assert p["id"]
    assert p["status"] == "pending"
    assert p["expires_at"] > NOW.isoformat()
    again = scratch.propose([cand("mcp-observability")], store=store, now=NOW, existing=[])
    assert again["accepted"][0]["id"] == p["id"]


def test_propose_skips_themes_already_tracked(tmp_path):
    store = tmp_path / "proposals.jsonl"
    out = scratch.propose(
        [cand("motherboard-sales"), cand("mcp-observability")],
        store=store, now=NOW, existing=["motherboard-sales"],
    )
    themes = [p["theme"] for p in out["accepted"]]
    assert themes == ["mcp-observability"]
    assert out["skipped"][0]["theme"] == "motherboard-sales"


def test_propose_caps_at_max_and_reports_deferred(tmp_path):
    store = tmp_path / "proposals.jsonl"
    out = scratch.propose(
        [cand(f"theme-{i}") for i in range(6)],
        store=store, now=NOW, existing=[], max_proposals=3,
    )
    assert len(out["accepted"]) == 3
    assert len(out["deferred"]) == 3


def test_propose_ranks_more_evidence_first(tmp_path):
    store = tmp_path / "proposals.jsonl"
    out = scratch.propose(
        [cand("thin", hits=1), cand("thick", hits=9)],
        store=store, now=NOW, existing=[], max_proposals=3,
    )
    assert [p["theme"] for p in out["accepted"]] == ["thick", "thin"]


def test_list_hides_decided_and_expired(tmp_path):
    store = tmp_path / "proposals.jsonl"
    a = scratch.propose([cand("keep")], store=store, now=NOW, existing=[])["accepted"][0]
    b = scratch.propose([cand("dropme")], store=store, now=NOW, existing=[])["accepted"][0]
    scratch.decide(b["id"], "reject", store=store, now=NOW)
    pending = scratch.list_pending(store=store, now=NOW)
    assert [p["id"] for p in pending] == [a["id"]]

    old = NOW - timedelta(days=40)
    c = scratch.propose([cand("stale")], store=store, now=old, existing=[])["accepted"][0]
    scratch.expire(store=store, now=NOW, days=30)
    assert c["id"] not in [p["id"] for p in scratch.list_pending(store=store, now=NOW)]


def test_accept_emits_tracker_spec_skeleton(tmp_path):
    store = tmp_path / "proposals.jsonl"
    p = scratch.propose([cand("mcp-observability")], store=store, now=NOW, existing=[])["accepted"][0]
    out = scratch.decide(p["id"], "accept", store=store, now=NOW)
    assert out["status"] == "accepted"
    spec = out["spec"]
    assert f"slug: {p['id']}" in spec
    assert "status: live" in spec
    assert "signals:" in spec
    assert "noise:" in spec
    assert scratch.list_pending(store=store, now=NOW) == []


def test_decide_unknown_id_is_an_error(tmp_path):
    store = tmp_path / "proposals.jsonl"
    with pytest.raises(KeyError):
        scratch.decide("nope", "accept", store=store, now=NOW)


def test_render_proposals_mentions_accept_command_and_expiry(tmp_path):
    store = tmp_path / "proposals.jsonl"
    p = scratch.propose([cand("mcp-observability")], store=store, now=NOW, existing=[])["accepted"][0]
    text = scratch.render([p], now=NOW)
    assert p["id"] in text
    assert f"accept {p['id']}" in text
    assert "mcp-observability" in text


def test_propose_rejects_candidate_without_theme(tmp_path):
    store = tmp_path / "proposals.jsonl"
    with pytest.raises(ValueError):
        scratch.propose([{"interest": "x", "hits": []}], store=store, now=NOW, existing=[])
