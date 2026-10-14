# Argus

Argus is a Hermes Agent skill for standing personal-intelligence watches. It
tracks topics and typed metrics, folds duplicate coverage, and briefs only when
a material signal moves.

Hermes v0.21 now provides the scheduler infrastructure—persistent memory,
previous-run continuity, change-gated monitor mode, durable per-job notepad,
per-job reasoning effort, and Bot Chat delivery. Argus focuses on the domain
work those primitives do not provide: tracker design, source discovery, trust
ranking, URL-level history, semantic folding, metric thresholds, sourced
briefing cards, beyond-radar discovery, and bounded GitHub repository discovery.

## GitHub discovery

Argus can support GitHub discovery without turning every scan into permanent
archive growth. Repositories are canonicalized by case-insensitive
`owner/repository` identity and stored as one mutable state record. Repeated
observations update `last_seen`, `times_seen`, and source provenance silently.
Only meaningful events—such as a distinct `pushed_at` transition—become sparse
archive events.

The GitHub discovery foundation includes:

- daily new-repository discovery and weekly activity re-evaluation as separate
  modes;
- merged sightings across GitHub Search and daily/weekly Trending;
- bounded candidate, new-repository, and event counts per run;
- explicit retention guidance for inactive repository state;
- advisory classifications only—discovered code is never cloned, installed,
  imported, or executed automatically.

See [`skills/argus/references/github-discovery.md`](skills/argus/references/github-discovery.md)
for the storage contract and deduplication rules. GitHub collection, scoring,
and classification orchestration are intentionally separate from these pure
identity/event helpers.

## Tick ledger and weekly rollup

"A silent tick is success" is Argus's whole promise, and nothing used to be able
to check it. The tick ledger fixes that: one bounded JSONL line per tick, and a
single weekly message that reports on every Argus watch on the machine.

```bash
# after every tick
python3 skills/argus/scripts/argus_ticks.py record '{"job":"motherboard sales watch",
  "slug":"motherboard-sales","outcome":"silent","items_read":34,"items_new":0,
  "sources":[{"source":"https://slickdeals.net/deals/motherboard/","status":200,"items":34,"ok":true}]}'

# Saturdays, one message, then prune to a two-week window
python3 skills/argus/scripts/argus_ticks.py rollup --days 14 --silent-days 14 --prune
```

The rollup contains three sections and nothing else:

1. **Jobs** — one line per job: `name — N completed / M failed`.
2. **Source health** — sources with a trailing error streak (≥2) or zero-item
   streak (≥3); a successful read resets the streak.
3. **Silent trackers — retirement candidates** — trackers silent beyond the
   threshold, or that never fired.

`--cadence slug=monthly` raises the threshold for legitimately quiet watches so
the rollup does not propose retiring a healthy monthly tracker. See
[`references/tick-ledger.md`](skills/argus/references/tick-ledger.md) and
[`references/weekly-rollup.md`](skills/argus/references/weekly-rollup.md).

## Collectors

Prose `extract:` instructions ask the model to interpret data on every tick,
which makes correctness depend on model discipline. Collectors replace them with
named, testable functions:

```yaml
metrics:
  - name: lemonade_version
    unit: version
    collector: 'github.release_tag(repo="lemonade-sdk/lemonade")'
```

Built-ins cover GitHub releases, commits, and issue state; HTTP JSON and regex
reads; and local JSON paths, sets, and glob counts. A failed fetch becomes
`value: "<error>"` with the exception text — structurally an error, never a
fabricated or silently reused value.

`llm_extract` is the single non-deterministic escape hatch. It requires an
agent-supplied value and is always reported with `deterministic: false`, so
interpreted values stay distinguishable from measured ones.

See [`references/collectors.md`](skills/argus/references/collectors.md).

## Scratch and fold tuning

DISCOVER is directed — it is seeded from interests you already track, so it can
only return more of the same. **Scratch** is the opposite: undirected searches
that propose *new trackers* as reviewable drafts, capped at 3 per run, with
30-day expiry and accept-only creation. See
[`references/scratch.md`](skills/argus/references/scratch.md).

`fold.py --eval` measures the folding threshold against labeled fixtures instead
of guessing it. The shipped starter set (`assets/fold-labels.jsonl`, 8 cases /
24 labeled pairs from real archived rows) says the live `--sim 0.4` splits most
true duplicates and `fold.py`'s own default of 0.6 folds nothing at all. See
[`references/fold-tuning.md`](skills/argus/references/fold-tuning.md).

## Repository layout

```
argus/
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── scripts/
│   ├── install-skill.sh
│   └── run_tests.sh
├── skills/
│   ├── README.md
│   ├── _template/
│   ├── argus/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   ├── tracker-schema.md
│   │   │   ├── diff-metrics.md
│   │   │   ├── memory-schema.md
│   │   │   ├── briefing-template.md
│   │   │   ├── loop-prompt.md
│   │   │   ├── converting-monitors-to-trackers.md
│   │   │   ├── github-discovery.md
│   │   │   ├── hermes-conventions.md
│   │   │   ├── troubleshooting.md
│   │   │   ├── case-studies.md
│   │   │   ├── error-codes.md
│   │   │   ├── tick-ledger.md
│   │   │   ├── collectors.md
│   │   │   ├── weekly-rollup.md
│   │   │   ├── scratch.md
│   │   │   └── fold-tuning.md
│   │   ├── scripts/
│   │   │   ├── fold.py
│   │   │   ├── eval_signal.py
│   │   │   ├── github_discovery.py
│   │   │   ├── argus_ticks.py
│   │   │   ├── argus_collect.py
│   │   │   └── argus_scratch.py
│   │   └── assets/
│   │       └── fold-labels.jsonl
│   └── argus-watch/
│       ├── SKILL.md
│       └── scripts/
│           └── watchdog.py
└── tests/skills/
    ├── test_argus_skill.py
    ├── test_argus_watch.py
    ├── test_github_discovery.py
    ├── test_argus_ticks.py
    ├── test_argus_collect.py
    └── test_argus_scratch.py
```

## Install

```bash
./scripts/install-skill.sh argus
# installs skills/argus into ~/.hermes/skills/argus
```

Or copy it manually:

```bash
cp -r skills/argus ~/.hermes/skills/
```

Start a new Hermes session after installation so the skill index reloads.

## Hermes v0.21 architecture

| Concern | Implementation |
|---|---|
| User preferences/interests | Hermes MEMORY.md/USER.md + `memory` tool |
| Previous-run dedup context | Cron `continuity=true` / CLI `--continuity` |
| Cheap change detection | Cron `monitor` / CLI `--monitor-script` or `--monitor-url` |
| Small cursor/watermark state | Cron's bounded per-job notepad |
| Bot delivery | Cron `deliver: bot-chat:<profile>` |
| Semantic news folding | Argus `fold.py` |
| Typed metric thresholds | Argus `eval_signal.py` |
| Long-term URL history | Argus `archive/<slug>.jsonl` |

The v0.21 rewrite removes the old `notify_bot.sh` shell shim and stops using an
Argus-private `memory.md` user model. Native delivery is safer and creates a
real Bot Chat turn; native memory prevents preferences from diverging between
cron, Desktop, CLI, and messaging sessions. Continuity reduces repeat briefs,
but the archive remains because prior-output injection is bounded and is not an
item-level provenance database.

See [`CHANGELOG.md`](CHANGELOG.md) and
[`skills/argus/references/converting-monitors-to-trackers.md`](skills/argus/references/converting-monitors-to-trackers.md)
for the full migration rationale.

## Two tracker engines

- **News watch:** READ → FOLD → SIGNAL → DISCOVER; duplicate reports become one
  sourced card and no material movement means silence.
- **Metric/price monitor:** READ → `eval_signal.py` → SIGNAL; `diff` and
  `threshold` gates report exact old/new values and stay silent below the gate.

## Watchdog

A separate cron job watches for ticks appearing on schedule. The `argus-watch`
skill provides a zero-token watchdog that monitors job health and alerts on
failures. See `skills/argus-watch/SKILL.md`.

Tracker mode is declared in `references/tracker-schema.md`. Runtime state stays
under `${INTEL_DIR:-$HOME/.intel}` and is ignored by Git.

## Validate

```bash
python3 skills/argus/scripts/fold.py --self-test
python3 skills/argus/scripts/eval_signal.py --self-test
python3 skills/argus/scripts/argus_ticks.py --self-test
python3 skills/argus/scripts/argus_collect.py --self-test
uv run --with pytest pytest tests/skills -q    # or: bash scripts/run_tests.sh
```

## Add another skill

See [CONTRIBUTING.md](CONTRIBUTING.md). Copy `skills/_template`, complete the
frontmatter and procedure, add a catalog row, test it, and commit.
