# Skills Catalog

Index of skills in this repo. Add a row here whenever you publish a new one
(see [CONTRIBUTING.md](../CONTRIBUTING.md)).

| Skill | Purpose | Tier | Status |
|---|---|---|---|
| [`argus`](argus/) | Standing intelligence watch: folds duplicate coverage, discovers bounded GitHub repository signals, surfaces beyond-radar findings, and gates metric/price briefings on real movement. Uses Hermes v0.21 native memory, continuity, monitor mode, notepad state, reasoning effort, and Bot Chat delivery. | monitoring / research | ✅ live |
| [`argus-watch`](argus-watch/) | Zero-token watchdog for Hermes cron jobs. Monitors job health, alerts on failures, stays silent when all jobs are healthy. Runs as a `--no-agent` cron job. | monitoring / devops | ✅ live |

## How to read this

- **Tier** is a hint for where the skill belongs: `monitoring`, `research`, `devops`, `creative`, `productivity`, etc. It's just a tag — folder layout stays flat (`skills/<name>`).
- **Status**: `✅ live` (installed and working), `🧪 experimental`, `📝 draft`.

## Conventions

- One skill per folder, named in lowercase-hyphen.
- `SKILL.md` carries the frontmatter (`name`, `description` ≤ 60 chars, `version`, `author`, `license`, `platforms`, `metadata`).
- Supporting files go in `references/` (docs) and `scripts/` (helpers). Point to them from `SKILL.md`; don't inline bulky logic.
- Runtime state lives off-repo (e.g. `~/.intel/`); never commit secrets or live state.
