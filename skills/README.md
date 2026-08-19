# Skills Catalog

Index of skills in this repo. Add a row here whenever you publish a new one
(see [CONTRIBUTING.md](../CONTRIBUTING.md)).

| Skill | Purpose | Tier | Status |
|---|---|---|---|
| [`personal-intel-agent`](personal-intel-agent/) | Pull-to-you watch: name a topic, get briefed only when it moves; folds duplicate coverage, surfaces beyond-radar signals, learns preferences. | monitoring / research | ✅ live |

## How to read this

- **Tier** is a hint for where the skill belongs: `monitoring`, `research`, `devops`, `creative`, `productivity`, etc. It's just a tag — folder layout stays flat (`skills/<name>`).
- **Status**: `✅ live` (installed and working), `🧪 experimental`, `📝 draft`.

## Conventions

- One skill per folder, named in lowercase-hyphen.
- `SKILL.md` carries the frontmatter (`name`, `description` ≤ 60 chars, `version`, `author`, `license`, `platforms`, `metadata`).
- Supporting files go in `references/` (docs) and `scripts/` (helpers). Point to them from `SKILL.md`; don't inline bulky logic.
- Runtime state lives off-repo (e.g. `~/.intel/`); never commit secrets or live state.
