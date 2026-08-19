# Hermes Skills

A personal collection of [Hermes Agent](https://hermes-agent.nousresearch.com/) skills, maintained for reuse across machines and profiles.

## What's here

```
hermes-skills/
├── README.md              # this file
├── CONTRIBUTING.md        # how to add a new skill (the repeatable path)
├── LICENSE                # MIT
├── .gitignore
├── scripts/
│   └── install-skill.sh   # copy a skill into your local ~/.hermes/skills
├── skills/
│   ├── README.md          # the catalog (index of published skills)
│   ├── _template/         # copy-paste scaffold for a new skill
│   │   └── SKILL.md
│   └── personal-intel-agent/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
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
