# Argus

Argus is a Hermes Agent skill for standing personal-intelligence watches. It
tracks topics and typed metrics, folds duplicate coverage, and briefs only when
a material signal moves.

Hermes v0.21 now provides the scheduler infrastructure—persistent memory,
previous-run continuity, change-gated monitor mode, durable per-job notepad,
per-job reasoning effort, and Bot Chat delivery. Argus focuses on the domain
work those primitives do not provide: tracker design, source discovery, trust
ranking, URL-level history, semantic folding, metric thresholds, sourced
briefing cards, and beyond-radar discovery.

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
│   └── argus/
│       ├── SKILL.md
│       ├── references/
│       │   ├── tracker-schema.md
│       │   ├── diff-metrics.md
│       │   ├── memory-schema.md
│       │   ├── briefing-template.md
│       │   ├── loop-prompt.md
│       │   └── converting-monitors-to-trackers.md
│       └── scripts/
│           ├── fold.py
│           └── eval_signal.py
└── tests/skills/test_argus_skill.py
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

Tracker mode is declared in `references/tracker-schema.md`. Runtime state stays
under `${INTEL_DIR:-$HOME/.intel}` and is ignored by Git.

## Validate

```bash
python3 skills/argus/scripts/fold.py --self-test
python3 skills/argus/scripts/eval_signal.py --self-test
python3 scripts/run_tests.sh
```

## Add another skill

See [CONTRIBUTING.md](CONTRIBUTING.md). Copy `skills/_template`, complete the
frontmatter and procedure, add a catalog row, test it, and commit.
