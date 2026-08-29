#!/usr/bin/env python3
"""eval_signal.py — decide whether a tick's collected metrics pass the gate.

Part of the personal-intel-agent skill. Sits between READ and SIGNAL. Reads
the previous state file, compares to the current collected values, and emits a
JSON verdict that the skill's DELIVER step consumes.

Two gate modes (set on the tracker's `eval:` block):

  mode: diff       — fire if ANY tracked item's value changed vs last run.
                      Non-numeric items (version/date/status/count-as-string)
                      compare by string equality; numeric items (price/count)
                      compare numerically. This is the monitor default.

  mode: threshold  — fire only when a numeric delta crosses the trigger:
                      trigger: pct  -> |new-old| / |old| >= value   (e.g. 0.10)
                      trigger: abs  -> |new-old| >= value            (e.g. 20)
                      Only numeric items (price/count) are eligible; non-numeric
                      items are ignored for the threshold but still diff-recorded.

EXIT CODES:
  0  signals PASSED the gate (something to report) -> verdict on stdout
  1  no signal (silent tick)                        -> "SILENT" on stdout
  2  usage / bad input

INPUT:  JSON on stdin, shape:
  {
    "eval": {                                   # mirrors tracker eval: block
      "mode": "diff" | "threshold",
      "trigger": "pct" | "abs",                 # threshold only
      "value": 0.10,                            # threshold only
      "items": ["lemonade_version", "price_usd"] # which metrics gate (default: all)
    },
    "current": { "metric": {"value": ..., "unit": ..., "url": ...}, ... },
    "previous": { "metric": {"value": ...}, ... }   # may be {} on first run
  }

OUTPUT (stdout, JSON):
  {
    "passed": true|false,
    "mode": ..., "trigger": ..., "value": ...,
    "changed": [ {"metric", "old", "new", "unit", "url", "delta_pct", "delta_abs"} ],
    "unchanged": [ "metric", ... ],
    "new_metrics": [ "metric", ... ],
    "first_run": true|false
  }

Run --self-test to validate against fixtures (no input needed).
"""
import sys, json, math


def _num(v):
    """Return float if v is numeric (int/float/str of number), else None."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace("$", "").replace(",", "").replace("%", "")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _changed(old, new, unit):
    """Return (changed_bool, delta_pct_or_None, delta_abs_or_None)."""
    ou, nu = _num(old), _num(new)
    numeric = ou is not None and nu is not None
    if numeric:
        delta_abs = nu - ou
        delta_pct = (delta_abs / abs(ou)) if ou != 0 else (0.0 if delta_abs == 0 else None)
        return delta_abs != 0.0, delta_pct, delta_abs
    # non-numeric: string compare
    return str(old) != str(new), None, None


def evaluate(eval_block, current, previous):
    mode = eval_block.get("mode", "diff")
    trigger = eval_block.get("trigger")
    value = eval_block.get("value")
    gate_items = set(eval_block.get("items", [])) or set(current.keys())
    first_run = not previous

    changed, unchanged, new_metrics = [], [], []
    for m, cur in current.items():
        unit = cur.get("unit", "version")
        newv = cur.get("value")
        prev = previous.get(m, {})
        oldv = prev.get("value") if isinstance(prev, dict) else None
        if m not in previous:
            new_metrics.append(m)
            changed.append(_rec(m, oldv, newv, unit, cur.get("url"), first_run))
            continue
        ch, dpct, dabs = _changed(oldv, newv, unit)
        if ch:
            changed.append(_rec(m, oldv, newv, unit, cur.get("url"), False, dpct, dabs))
        else:
            unchanged.append(m)

    # Gate decision — only metrics listed in `items:` (or all, if omitted) may fire.
    passed = False
    if mode == "diff":
        passed = any(c["metric"] in gate_items for c in changed)
    elif mode == "threshold":
        for c in changed:
            if c["metric"] not in gate_items:
                continue
            if c.get("delta_abs") is None:
                continue  # non-numeric change doesn't count for threshold
            if trigger == "pct":
                if c.get("delta_pct") is not None and abs(c["delta_pct"]) >= float(value or 0):
                    passed = True
                    break
            elif trigger == "abs":
                if abs(c["delta_abs"]) >= float(value or 0):
                    passed = True
                    break
    else:
        passed = any(c["metric"] in gate_items for c in changed)

    return {
        "passed": passed,
        "mode": mode,
        "trigger": trigger,
        "value": value,
        "changed": changed,
        "unchanged": unchanged,
        "new_metrics": new_metrics,
        "first_run": first_run,
    }


def _rec(metric, old, new, unit, url, first_run, dpct=None, dabs=None):
    r = {"metric": metric, "old": old, "new": new, "unit": unit, "url": url}
    if dpct is not None:
        r["delta_pct"] = round(dpct, 4)
    if dabs is not None:
        r["delta_abs"] = round(dabs, 4)
    return r


def _self_test():
    # 1) NPU-like diff: version + status change, one unchanged
    inp = {
        "eval": {"mode": "diff"},
        "current": {
            "lemonade_version": {"value": "v11.6.0", "unit": "version", "url": "https://github.com/lemonade-sdk/lemonade/releases"},
            "bugzilla_2445615": {"value": "closed", "unit": "status"},
            "xdna_commit_date": {"value": "2026-08-20", "unit": "date"},
        },
        "previous": {
            "lemonade_version": {"value": "v11.5.2"},
            "bugzilla_2445615": {"value": "open"},
            "xdna_commit_date": {"value": "2026-08-20"},
        },
    }
    v = evaluate(inp["eval"], inp["current"], inp["previous"])
    assert v["passed"] is True, "diff should pass on any change"
    assert len(v["changed"]) == 2, v["changed"]
    assert len(v["unchanged"]) == 1, v["unchanged"]
    # 2) Price threshold: 10% drop should pass; 5% should not
    price_in = {
        "eval": {"mode": "threshold", "trigger": "pct", "value": 0.10},
        "current": {"price_usd": {"value": 89.99, "unit": "price"}},
        "previous": {"price_usd": {"value": 99.99}},
    }
    vp = evaluate(price_in["eval"], price_in["current"], price_in["previous"])
    assert vp["passed"] is True, "10% drop should pass"
    price_small = {
        "eval": {"mode": "threshold", "trigger": "pct", "value": 0.10},
        "current": {"price_usd": {"value": 97.0, "unit": "price"}},
        "previous": {"price_usd": {"value": 99.99}},
    }
    vs = evaluate(price_small["eval"], price_small["current"], price_small["previous"])
    assert vs["passed"] is False, "3% drop should NOT pass at 10% gate"
    # 3) First run: diff passes (baseline established), records new_metrics
    fr = evaluate({"mode": "diff"}, {"a": {"value": "1"}}, {})
    assert fr["passed"] is True and fr["first_run"] is True and fr["new_metrics"] == ["a"]
    # 4) abs threshold on count
    cnt = {
        "eval": {"mode": "threshold", "trigger": "abs", "value": 20},
        "current": {"open_prs": {"value": 45, "unit": "count"}},
        "previous": {"open_prs": {"value": 10}},
    }
    vc = evaluate(cnt["eval"], cnt["current"], cnt["previous"])
    assert vc["passed"] is True, "35 delta >= 20 abs should pass"
    # 5) items: gate — a changed metric NOT in items must NOT fire
    gated = {
        "eval": {"mode": "diff", "items": ["a"]},
        "current": {"a": {"value": "v1"}, "b": {"value": "new!"}},
        "previous": {"a": {"value": "v1"}, "b": {"value": "old"}},
    }
    vg = evaluate(gated["eval"], gated["current"], gated["previous"])
    assert vg["passed"] is False, "non-gated metric change must NOT fire the gate"
    assert "b" in [c["metric"] for c in vg["changed"]], "non-gated change still recorded in state"
    print("self-test OK: diff(2 chg/1 unch), pct(10% pass/3% fail), first-run, abs(>=20 pass), items-gate")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
        sys.exit(0)
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        print(f"eval_signal.py: bad JSON stdin: {e}", file=sys.stderr)
        sys.exit(2)
    verdict = evaluate(
        payload.get("eval", {}),
        payload.get("current", {}),
        payload.get("previous", {}),
    )
    print(json.dumps(verdict, indent=2))
    sys.exit(0 if verdict["passed"] else 1)
