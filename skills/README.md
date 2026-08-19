# Skills Catalog

Index of skills in this repo. Add a row here whenever you publish a new one
(see [CONTRIBUTING.md](../CONTRIBUTING.md)).

| Skill | Purpose | Tier | Status |
|---|---|---|---|
| [`personal-intel-agent`](personal-intel-agent/) | Pull-to-you watch: name a topic, get briefed only when it moves; folds duplicate coverage, surfaces beyond-radar signals, learns preferences. | monitoring / research | ✅ live |

### `personal-intel-agent` — delivery channels

A tracker's `delivery:` field (in `~/.intel/trackers/<slug>.yaml`) selects one or more outputs; the skill fans out to all of them on a tick with movement. Silent tick (no movement) = nothing sent.

| Channel | Behavior | Mechanism |
|---|---|---|
| `feed` | Cards printed inline in the active chat | default |
| `file` | Write `briefings/<date>-<slug>.md` | `write_file` |
| `rss` | Append `<item>` to `briefings/feed.xml` | XML append |
| `audio` | Speak each card, return MEDIA path | `text_to_speech` |
| `bot:<profile>` | Push into a local Hermes Bot's chat (e.g. `bot:loco-bot`) | `scripts/notify_bot.sh <profile>` → `hermes -p <profile> chat` |

> Note: Hermes cron's own `deliver:` field has no profile-aware path, so the watch job stays `deliver: local` and the skill performs the bot routing itself. Runtime state (`~/.intel/`, cron jobs) is never committed here. Full detail in [`SKILL.md`](personal-intel-agent/SKILL.md) Branch D and [`tracker-schema.md`](personal-intel-agent/references/tracker-schema.md).

## How to read this

- **Tier** is a hint for where the skill belongs: `monitoring`, `research`, `devops`, `creative`, `productivity`, etc. It's just a tag — folder layout stays flat (`skills/<name>`).
- **Status**: `✅ live` (installed and working), `🧪 experimental`, `📝 draft`.

## Conventions

- One skill per folder, named in lowercase-hyphen.
- `SKILL.md` carries the frontmatter (`name`, `description` ≤ 60 chars, `version`, `author`, `license`, `platforms`, `metadata`).
- Supporting files go in `references/` (docs) and `scripts/` (helpers). Point to them from `SKILL.md`; don't inline bulky logic.
- Runtime state lives off-repo (e.g. `~/.intel/`); never commit secrets or live state.
