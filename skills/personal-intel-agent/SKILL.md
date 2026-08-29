---
name: personal-intel-agent
description: "Brief only when a watched topic moves; fold duplicate news."
version: 0.2.0
author: rahlquist (rahlquist), Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [research, monitoring, briefing, rss, agent]
    related_skills: [research, competitor-news-monitor]
---

# Personal Intelligence Agent

Mimics a pull-to-you news intelligence agent: you name what matters in one sentence; the agent reads the sources 24/7, folds twenty takes on one story into a single briefed card, surfaces adjacent signals beyond your radar, and remembers your preferences so the feed sharpens over time.

What it is NOT: a chatbot that answers on demand, a summarizer of a single article, or a social feed to scroll. It is a standing watch that comes to you only when something actually moves. A silent tick with no movement is the correct, expected outcome — not a failure to report.

## When to Use
- User says "track/watch/monitor <X> and tell me when it moves", "keep me posted on…", "set up a watch on…", "brief me on <topic> daily/weekly".
- User wants duplicate news coverage collapsed into one sourced card ("fold these into one").
- User wants serendipitous discovery tied to their interests ("what am I missing?").
- User wants the agent to learn preferences ("less celebrity coverage", "more primary sources").
- Don't use for: one-off Q&A, summarizing a single URL (use `web_extract`), or live on-demand research (use `research`).

## Prerequisites
- Web tools active: `web_search`, `web_extract`; for JS/login-walled sources use `browser_exec`.
- A state directory for trackers + memory. Default `./.intel/` (create with `write_file`); override via env `INTEL_DIR`.
- Optional 24/7 loop: `cronjob` (self-contained prompt in references/loop-prompt.md).
- Optional audio briefings: `text_to_speech`. Optional parallel entity runs: `delegate_task`.

## How it works (the loop)
Eight leading words drive every run. TRACK → READ → FOLD → SIGNAL → DISCOVER, all shaped by MEMORY, emitted via DELIVER, repeated in LOOP.

- **TRACK** — one sentence becomes a tracker spec + ranked source map.
- **READ** — pull recent items from every matched source.
- **FOLD** — collapse duplicate coverage; keep one card, attach all sources; filter noise.
- **SIGNAL** — the briefed card: what happened, why it matters, every source, confidence.
- **DISCOVER** — beyond-radar: adjacent stories scored against your interests.
- **MEMORY** — persistent, editable user model (preferences, feedback, source trust).
- **DELIVER** — feed (chat), file, RSS, audio, or local Bot profile (`bot:<name>`).
- **LOOP** — schedule the tick; each run updates memory and delivers only on movement.

## State files
All under `INTEL_DIR` (= `./.intel` unless overridden):
- `trackers/<slug>.yaml` — one spec per tracked entity (schema: references/tracker-schema.md).
- `memory.md` — the open user model (schema: references/memory-schema.md).
- `briefings/<date>-<slug>.md` — emitted cards (template: references/briefing-template.md).
- `archive/<slug>.jsonl` — every item ever seen (dedup history across ticks).
- `state/<slug>.json` — last-run metric snapshot for `diff`/`threshold` trackers (written every tick; first run = baseline).

## Procedure

### Branch A — Establish a tracker (TRACK)
1. Parse the sentence into a spec: entity, type (company|person|team|rumor|niche|field), the signal classes that count as "moves" (launches, deals, injuries, filings), cadence (instant|daily|weekly), and noise rules (gossip/clickbait/fakes to drop). Write `trackers/<slug>.yaml` per `references/tracker-schema.md`.
   - *Completion:* spec file exists with entity, type, ≥1 signal class, cadence, and ≥1 noise rule.
2. **Source discovery.** For the entity run `web_search` with 3–5 queries spanning official / newsroom / fan-forum / filings-or-papers / blog-or-podcast. Classify each hit into a source type and a trust tier (primary|secondary|tertiary). Aim for 15–85 matched sources.
   - *Completion:* spec's `sources:` has ≥10 entries each with type + trust tier; duplicates removed.
3. Arm the push: pick delivery channel(s) from MEMORY (default feed in chat). Record in spec.
   - *Completion:* spec has `delivery:` set; tracker is "live".

### Branch B — Run a tick (READ → EVAL → FOLD → SIGNAL → DISCOVER)
4. **READ.** For each source in the spec, fetch recent items via `web_extract` (or `browser_exec` for JS/login walls). Emit each as a JSONL row: `{title, url, source, published, snippet, kind, trust}`. Append to `archive/<slug>.jsonl`, skipping URLs already archived (dedup history).
   - *Completion:* every source attempted; rows written; already-seen URLs not re-added.
4b. **EVAL (optional, for diff/threshold trackers).** If the spec has an `eval:` block (metric monitors, price trackers), collect current metric values into `state/<slug>.current.json`, load `state/<slug>.json` (last run), and run `scripts/eval_signal.py` to get a verdict (`passed` / changed list / unchanged list). This is the gate: a monitor only emits when its chosen metrics actually move. See `references/diff-metrics.md`.
   - *Completion:* verdict computed; if `passed` is false → silent tick (skip SIGNAL/DELIVER for this tracker).
5. **FOLD.** Pipe the new rows through `scripts/fold.py` (word-level TF-IDF cosine, greedy single-linkage at `--sim 0.6`). It emits one card per cluster with canonical source + all attached sources + noise-filtered rejects written to stderr.
   - *Completion:* every new row is in exactly one card or in the explicit rejects list with a reason.
6. **SIGNAL.** For each surviving card, write a briefing card per `references/briefing-template.md`: headline, what happened, why it matters, folded-from N sources, attached source list, confidence/verification. Honor cadence — only emit when a card clears the signal threshold (new event, not a rehash). For a `diff`/`threshold` tracker, lead with the CHANGED lines (old → new, source URL, delta) and a one-line UNCHANGED rollup, per `references/diff-metrics.md`.
   - *Completion:* each emitted card passes the template; rehashes suppressed.
7. **DISCOVER.** Separately run 1–2 broad `web_search` queries on adjacent topics derived from MEMORY interests. Fold/score; keep only items that connect to a stated interest where "everyone saw" the base story but missed the angle relevant to the user.
   - *Completion:* 0+ discovery notes, each tied to a MEMORY interest and labeled "beyond radar".

### Branch C — Feedback & memory (MEMORY)
8. On any user correction ("less celebrity coverage", "more open-source AI", "no hot takes", "prefer primary sources"), update `memory.md` immediately: add a preference line with provenance (`said` vs `learned`) and timestamp. Reshape future queries/weights from it.
   - *Completion:* memory.md reflects the change; next tick's source weighting honors it.

### Branch D — Deliver (DELIVER)
9. Emit the briefing per the tracker's `delivery:`:
   - feed → return cards inline in chat.
   - file → `write_file` to `briefings/<date>-<slug>.md`.
   - rss → append an `<item>` to `briefings/feed.xml` (schema in references/briefing-template.md).
   - audio → `text_to_speech` per card, deliver MEDIA path.
   - **bot** → deliver into a local Hermes **Bot profile** (e.g. `loco-bot`). cron's `deliver:` resolver has no profile-aware path, so the watch job keeps `deliver: local` and this step shells out: `bash scripts/notify_bot.sh <bot-profile>` fed the briefing on stdin (or pass a `.md` path). Verified path: `hermes -p <bot-profile> chat -Q -q "..."` lands in that bot's canonical Bot Chat. Support multiple bots by listing `bot:loco-bot,bot:senna` and looping.
   - *Completion:* channel received the cards; no movement = no delivery (silent tick is correct).

## Pitfalls
- **Silent tick is success, not failure.** The agent only surfaces movement when something actually moves. Don't pad empty runs.
- **Folding needs real items.** `fold.py` clusters what you collected; if READ fetched nothing, there's nothing to fold — report "no new items", don't invent.
- **Trust tiers matter.** Tertiary/fan sources feed DISCOVER, not SIGNAL. Keep rumors in rumor-trackers verified-only.
- **Memory is a contract.** Never train a black box; every preference must be visible/editable in `memory.md`.
- **Don't doomscroll the agent.** Cap sources per tick (e.g. 40) and items per card; a large entity → use `delegate_task` per source-cluster.
- **"Updated" is not "verified."** When a change touches multiple doc layers (skill-internal SKILL.md/references AND repo-level README/catalog), don't report done after editing only one layer. Grep the repo for stale references, update every layer that mentions the changed surface, then confirm remotely. A user asking "did you update the docs thoroughly?" is the correction firing — fix all layers, don't assert.
- **`gh repo rename` can flip visibility.** Renaming a repo has, in practice, left the repo PUBLIC even when it started private. After any rename, re-verify `private: true` via the API and re-set `--visibility private --accept-visibility-change-consequences` if needed. Never assume rename preserves the privacy flag.
- **Dry-run the gate before trusting a monitor.** For a `diff`/`threshold` tracker, prove the eval path with a synthesized prior state BEFORE relying on the nightly cron: fire on a simulated change, confirm silent on no-change. A monitor that can't prove its gate is worse than no monitor.

## Verification
- Tracker spec is valid YAML in `references/tracker-schema.md` shape.
- `python scripts/fold.py --self-test` passes (ships a tiny fixture).
- `python scripts/eval_signal.py --self-test` passes (diff / pct / abs / first-run fixtures).
- A tick produces: archive rows appended, 0+ cards matching template, memory unchanged-or-updated, delivery confirmed.
- `memory.md` shows the edit after a feedback turn.
- A `diff`/`threshold` tracker writes `state/<slug>.json` every run; on a no-change tick it emits nothing (silent tick).
- For any change that touches repo docs: remote HEAD reflects the commit, no stale references remain, and (if the repo is private) the API still reports `private: true`.

## Converting existing monitors to trackers
See `references/converting-monitors-to-trackers.md` — the real pattern for porting a standing monitor/cron job into a `personal-intel-agent` tracker (diff/threshold eval, `on_signal:` side-effects, `cron deliver: bot-chat:<profile>`), plus the dry-run and rename-privacy gotchas from a live migration.

## References
- `references/tracker-schema.md` — spec fields + examples (SpaceX, Taylor Swift, GTA 6 rumor).
- `references/memory-schema.md` — open user-model format.
- `references/briefing-template.md` — the signal card + RSS addendum.
- `references/diff-metrics.md` — `eval:` block shape (diff / threshold), metric units, and the CHANGED/UNCHANGED report format.
- `references/loop-prompt.md` — self-contained cron prompt for 24/7 LOOP.
- `references/converting-monitors-to-trackers.md` — port a monitor/cron job into a tracker; rename-privacy + dry-run gotchas.
- `scripts/fold.py` — dependency-free dedup/fold. `--self-test` included.
- `scripts/eval_signal.py` — diff/threshold gate. `--self-test` included.
- `scripts/notify_bot.sh` — deliver a card into a local Hermes Bot profile's chat.
