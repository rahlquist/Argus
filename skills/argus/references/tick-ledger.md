# Tick Ledger

Argus asserts that "a silent tick is success." The tick ledger is what makes
that claim checkable instead of aspirational: one append-only line per tick,
plus a weekly rollup that answers *is this tracker still earning its schedule?*
and *is this source quietly starving?*

## Ledger

`$ARGUS_TICK_LEDGER`, defaulting to `~/.intel/state/ticks.jsonl`.

The default is deliberately **shared across profiles and workdirs** so a single
weekly job can report on every Argus watch on the machine. Override only if you
want isolated ledgers.

## Recording a tick

Every tick records exactly one row, after READ completes and after EVAL/SIGNAL
decides the outcome:

```bash
python3 scripts/argus_ticks.py record --ledger "$ARGUS_TICK_LEDGER" '{
  "job": "motherboard sales watch",
  "job_id": "27c14f7319f3",
  "slug": "motherboard-sales",
  "outcome": "silent",
  "reason": "no_new_items",
  "items_read": 34,
  "items_new": 0,
  "fired": 0,
  "sources": [
    {"source": "https://slickdeals.net/deals/motherboard/", "status": 200, "items": 34, "ok": true},
    {"source": "https://slickdeals.net/newsearch.php?q=motherboard", "status": 200, "items": 0, "ok": true}
  ]
}'
```

JSON may also be piped on stdin. Fields:

| Field | Required | Meaning |
|---|---|---|
| `job` | yes | Job name, used for the per-job rollup line |
| `outcome` | yes | `fired`, `silent`, `error`, or `skipped` |
| `slug` | no | Tracker slug; required for silence/retirement tracking |
| `job_id` | no | Cron job id, for cross-referencing `cron runs` |
| `reason` | no | Short machine token, e.g. `no_new_items`, `gate_failed` |
| `items_read` / `items_new` / `fired` | no | Counts |
| `errors` | no | List of short error strings |
| `sources` | no | Per-source attempt outcomes — drives source health |

`outcome: error` is the only outcome counted as *failed*. `skipped` counts as
completed.

**Record a tick even on a silent run.** A missing row is indistinguishable from
a job that never ran, which is the failure mode this ledger exists to catch.

## Weekly rollup

```bash
python3 scripts/argus_ticks.py rollup --days 14 --silent-days 14 --prune
```

Produces one Markdown message:

1. **Jobs** — one line per job: `name — N completed / M failed`.
2. **Source health** — sources with a trailing error streak (≥2) or a trailing
   zero-item streak (≥3). A successful read resets the streak.
3. **Silent trackers — retirement candidates** — trackers whose last `fired`
   tick is older than the silence threshold, or that never fired at all.

`--prune` drops records older than `--days` **after** building the report, so
the ledger stays a two-week window.

### Cadence awareness

A monthly tracker is *supposed* to be quiet. Pass cadence hints so the rollup
does not propose retiring a healthy low-frequency watch:

```bash
--cadence slug-voice-service=monthly --cadence motherboard-sales=daily
```

Thresholds: `instant`/`daily` → 14 days, `weekly` → 21, `monthly` → 45, or a
plain number of days. The effective threshold is the larger of `--silent-days`
and the cadence value. Without a hint, `--silent-days` applies flat.

## Bounds

The ledger is one line per tick, not one line per item. A tracker that reads
2,000 items writes one row. Pruning to 14 days bounds it by *tick rate*, not by
source volume — the same discipline as the GitHub event model.

## CLI

```
argus_ticks.py record [--ledger P] [--at ISO] [JSON]
argus_ticks.py rollup [--ledger P] [--days 14] [--silent-days 14]
                      [--cadence slug=cadence]... [--now ISO] [--prune]
argus_ticks.py prune  [--ledger P] [--days 14] [--now ISO]
argus_ticks.py --self-test
```
