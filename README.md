# Hermes Skills

A personal collection of [Hermes Agent](https://hermes-agent.nousresearch.com/) skills, maintained for reuse across machines and profiles.

## What's here

```
personal-intel-agent/
├── README.md              # this file
├── CONTRIBUTING.md        # how to add a new skill (the repeatable path)
├── LICENSE                # MIT
├── .gitignore
├── scripts/
│   └── install-skill.sh   # copy a skill into your local ~/.hermes/skills
├── skills/
│   ├── README.md          # the catalog (index of published skills)
│   ├── _template/         # copy-paste scaffold for a new skill
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── README.md
│   └── personal-intel-agent/
│       ├── SKILL.md
│       ├── references/
│       │   ├── tracker-schema.md   # spec fields + eval: + on_signal: block shape
│       │   ├── diff-metrics.md     # diff/threshold monitor + price tracker contract
│       │   ├── memory-schema.md     # open user-model format
│       │   ├── briefing-template.md # the signal card + RSS addendum
│       │   ├── loop-prompt.md       # self-contained 24/7 cron prompt
│       │   └── converting-monitors-to-trackers.md # port a cron/monitor into a tracker
│       └── scripts/
│           ├── fold.py              # dedup/fold news coverage (TF-IDF)
│           ├── eval_signal.py       # diff/threshold gate for metric + price monitors
│           └── notify_bot.sh        # deliver a card into a local Hermes Bot profile
└── ...future skills...
```

Each skill is a self-contained folder under `skills/<skill-name>/`. Drop a folder in, register it in the catalog, done.

## Install a skill

```bash
# from this repo root
./scripts/install-skill.sh personal-intel-agent
# → copies skills/personal-intel-agent into ~/.hermes/skills/personal-intel-agent
```

Or copy manually:
```bash
cp -r skills/personal-intel-agent ~/.hermes/skills/
```

After install, the skill is available to Hermes on next session load. Edit `references/` and `scripts/` as needed — they live beside `SKILL.md`.

## Add a new skill

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version: copy `skills/_template`, fill the frontmatter, write the body, add an entry to `skills/README.md`, commit.

## Notes
- Skills here are personal/reusable workflows, not necessarily upstream-hermes-conformant. The `personal-intel-agent` skill was built to mimic a commercial product's behavior; others will vary.
- Stateful skills (like `personal-intel-agent`) keep their runtime state under `~/.intel/` on the host, never in this repo. See each skill's docs.
- `personal-intel-agent` is two engines in one: a **news watch** (READ → FOLD → SIGNAL, silent when nothing moves) and a **metric/price monitor** (READ → `eval_signal.py` diff/threshold gate → SIGNAL only on real movement). Trackers declare which via the `eval:` block in `references/tracker-schema.md`; see `references/diff-metrics.md`.
