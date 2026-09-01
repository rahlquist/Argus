# Diff & Threshold Metrics (the EVAL step)

Used by metric monitors and price trackers — the trackers whose "move" is a
**value changing**, not a news story breaking. The `eval:` block in the
tracker spec declares the gate; `scripts/eval_signal.py` computes the verdict
each tick and the skill only emits when the gate passes.

## Metric units

| unit | compared by | numeric? | example |
|---|---|---|---|
| `version` | string equality | no | `v11.5.2` |
| `date` | string equality | no | `2026-08-20` (ISO) |
| `status` | string equality | no | `open` / `closed` / `present` / `missing` |
| `count` | numeric delta | yes | `45` open PRs |
| `price` | numeric delta | yes | `89.99` (USD) |

Non-numeric units diff by string; a change is "old → new". Numeric units feed
the threshold math and additionally report `delta_abs` and `delta_pct`.

## Gate modes

### `mode: diff`
Fire if **any** gating metric changed vs `state/<slug>.json`.
- First run (no prior state) → fire, record baseline, all metrics listed under
  CHANGED as initial values (no "old").
- Non-numeric change → always counts.
- Numeric change → counts regardless of magnitude (use `threshold` to gate on
  magnitude).

### `mode: threshold`
Fire only when a numeric delta crosses the trigger.
- `trigger: pct`, `value: 0.10` → `|new − old| / |old| >= 0.10`.
- `trigger: abs`, `value: 20` → `|new − old| >= 20`.
- Only metrics listed in `eval.items:` that are numeric participate. A price
  tracker lists just its price metric(s) there; version/status fields (if any)
  are ignored for the gate but still written to state for future diffs.

## State handling

Every tick (regardless of fire) writes `state/<slug>.json`:
```json
{
  "last_run": "2026-08-27",
  "metrics": { "lemonade_version": {"value": "v11.6.0", "unit": "version", "url": "…"}, "price_usd": {"value": 89.99, "unit": "price"} }
}
```
The READ step first writes `state/<slug>.current.json` (fresh values), then
`eval_signal.py` diffs `current` against the persisted `metrics` and the
verdict decides whether SIGNAL/DELIVER run. If silent (no pass), state is
still updated so the next run has a correct baseline.

## Report format (SIGNAL output for a diff/threshold tracker)

Lead with what moved; roll up what didn't. No padding on a silent tick.

```
# <entity> — watch update

## CHANGED
- Lemonade SDK: v11.5.2 → v11.6.0  (version)  [source](url)
- Bugzilla 2445615: open → closed  (status)  — NPU driver blocker resolved

## UNCHANGED
- RyzenAI-SW docs: 1.8.0 (no change)
- XDNA driver commit: 2026-08-20 (no change)

Overall: 2 changed, 3 unchanged.
```
For a `threshold` price tracker the CHANGED line carries the delta:
```
- Price: $99.99 → $89.99  (−10.0%, −$10.00)  (price)
```

## Anti-fabrication rule
Never invent a `value`, `url`, or delta. If a source API fails, mark the
metric `value: <error>` and say so in the report; do not silently carry the
old value forward as if unchanged without noting the fetch failure.
