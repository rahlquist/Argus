---
name: argus
description: "Standing intelligence watch: tracks topics and typed metrics, folds duplicate coverage, and briefs only when material signals move. Silent tick = success."
version: 0.4.3
author: rahlquist (rahlquist), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, monitoring, briefing, rss, agent]
    related_skills: [research, competitor-news-monitor]
---

# Argus

Argus is a standing personal-intelligence watch: name what matters, and it reads ranked sources, folds duplicate reporting, detects material movement, and sends a sourced briefing instead of a feed to scroll. A silent tick with no movement is the correct result.

Hermes v0.21 supplies the scheduler plumbing. Argus supplies the domain logic: tracker design, source discovery, trust ranking, URL-level deduplication, multi-source folding, threshold evaluation, briefing cards, adjacent-signal discovery, and bounded GitHub repository discovery. GitHub repositories use canonical identity plus sparse events; repeated observations never become archive growth. See `references/github-discovery.md`.

## When to Use
- User says "track/watch/monitor <X> and tell me when it moves", "keep me posted on…", or "brief me on <topic> daily/weekly".
- User wants duplicate coverage collapsed into one sourced card.
- User wants metric, version, status, count, or price changes gated by diff/threshold rules.
- User wants adjacent discoveries shaped by durable preferences.
- Don't use for one-off Q&A, a single-URL summary, or a local maintenance job with no intelligence-tracking component.

## Prerequisites
- Web tools active: `web_search`, `web_extract`; use `browser_exec` for JS/login-walled sources.
- A durable tracker state directory. Default: `${INTEL_DIR:-$HOME/.intel}`. Set the cron job's `workdir` to the state directory.
- Hermes v0.21+ for cron memory, `continuity`, monitor gating, per-job notepad, and `bot-chat:<profile>` delivery.
- Optional audio briefings: `text_to_speech`. Optional parallel source clusters: `delegate_task`.

## Native Hermes v0.21 Integration

Use native cron capabilities rather than duplicating scheduler infrastructure:

| Need | Native primitive | Argus responsibility |
|---|---|---|
| User preferences and interests | Cron loads Hermes MEMORY.md/USER.md and exposes the `memory` tool | Apply preferences to source weighting, noise rules, and DISCOVER |
| Previous-run context | `continuity=true` / CLI `--continuity` | Compare with prior brief and avoid repeated reporting |
| Small per-job cursor/watermark state | Durable cron notepad | Maintain bounded cursors or watermarks when useful |
| Cheap source-change gate | `monitor` / CLI `--monitor-script` or `--monitor-url` | Interpret changed content and emit the sourced brief |
| Bot delivery | `deliver: bot-chat:<profile>` | Produce the final briefing payload |
| Per-job reasoning budget | `reasoning_effort` | Use higher effort only where synthesis warrants it |

These primitives replace Argus's old private `memory.md` user model and `notify_bot.sh` delivery shim. They do **not** replace `archive/<slug>.jsonl`: continuity carries only the previous output (capped by Hermes), while the archive provides durable item-level URL deduplication and provenance across all runs.

## State Files

All under `${INTEL_DIR:-$HOME/.intel}`:
- `trackers/<slug>.yaml` — tracker spec (`references/tracker-schema.md`).
- `briefings/<date>-<slug>.md` — emitted cards (`references/briefing-template.md`).
- `archive/<slug>.jsonl` — every accepted item; URL-level dedup history.
- `state/<slug>.json` — last metric snapshot for `diff`/`threshold` trackers.

The user model lives in Hermes persistent memory, not in Argus state. See `references/memory-schema.md` for migration from the pre-v0.21 `memory.md` file.

## Procedure

### A. Establish a tracker (TRACK)
1. Parse the request into entity, type, signal classes, cadence, verification policy, and noise rules; write `trackers/<slug>.yaml` per `references/tracker-schema.md`.
   - *Complete when:* the spec has entity, type, at least one signal, cadence, one noise rule, and delivery intent.
2. Discover sources with 3–5 searches spanning official, newsroom, filings/papers, specialist, community, and long-form sources. Assign `primary|secondary|tertiary` trust tiers.
   - *Complete when:* at least 10 deduplicated sources are recorded, unless the subject genuinely has fewer authoritative sources and the limitation is explicit.
3. Create the cron job with a self-contained prompt, the `argus` skill, `continuity=true`, a stable `workdir`, and the intended delivery target. Use monitor mode only when a deterministic cheap source can gate the entire run.
   - *Complete when:* `cronjob list` shows the job with the intended schedule, continuity, workdir, and delivery.

### B. Run a tick (READ → EVAL → FOLD → SIGNAL → DISCOVER)
4. **READ.** Fetch recent items from every source. Append rows shaped as `{title, url, source, published, snippet, kind, trust}` to `archive/<slug>.jsonl`, skipping archived URLs.
   - *Complete when:* every source was attempted and every new accepted item was persisted once.
5. **EVAL.** For trackers with `eval:`, collect current values, compare with `state/<slug>.json` through `scripts/eval_signal.py`, and persist the new state even on a silent tick.
   - *Complete when:* the verdict is computed; `passed=false` skips SIGNAL and delivery.
6. **FOLD.** For news trackers, pass only newly collected rows through `scripts/fold.py` (word-level TF-IDF cosine, greedy single-linkage). Preserve rejected rows with explicit reasons.
   - *Complete when:* every new row belongs to exactly one card or an explicit reject set.
7. **SIGNAL.** Render surviving cards with headline, sourced facts, why it matters, source list, confidence, and verification. For metric trackers, lead with CHANGED lines and roll up UNCHANGED values.
   - *Complete when:* every emitted card satisfies `references/briefing-template.md` and is not a rehash of the previous run supplied by continuity.
8. **DISCOVER.** Run 1–2 adjacent searches seeded by interests in Hermes persistent memory. Keep only items tied to a stated interest and label them "beyond radar".
   - *Complete when:* each discovery has an explicit interest connection; zero discoveries is valid.

### C. Learn and deliver
9. On user feedback, update Hermes persistent memory immediately with a compact declarative preference or source-trust fact. Do not create a second Argus-specific memory store.
   - *Complete when:* the memory update is durable and the next source-ranking decision reflects it.
10. Return only the meaningful briefing. Let cron route the final output to `bot-chat:<profile>`, the origin, or another configured target. When there is nothing to report, produce no substantive content; monitor/no-agent gates are the only paths that guarantee scheduler-level suppression before delivery.
   - *Complete when:* the configured channel receives the briefing; a no-change tick produces no fabricated or padded report.

## Choosing the Right Gate

- **Native monitor mode:** one deterministic script or URL represents the watched state. Exact unchanged output skips the LLM entirely. Output must be stable—no timestamps or nondeterministic ordering.
- **Argus `eval:` mode:** several typed metrics, threshold math, per-metric source URLs, or CHANGED/UNCHANGED reporting are required.
- **Argus news mode:** movement is semantic across many sources; READ/FOLD/SIGNAL must run.
- **`no_agent` script job:** output needs no interpretation. This is not an Argus job.

## Pitfalls
- `continuity` is previous-output context, not a durable item database. Keep the archive for URL-level dedup and provenance.
- Native monitor mode hashes exact output bytes. Sort deterministic output and omit generated-at timestamps.
- The cron notepad is bounded scratch state, not a replacement for tracker specs, archives, or large metric histories.
- Bot Chat delivery costs a second agent turn because the target bot receives the briefing as a real message and responds.
- Tertiary sources feed DISCOVER, not verified SIGNAL cards. Strict rumor trackers suppress anything below high confidence.
- If READ finds nothing, do not manufacture a card. A silent tick is success.
- Dry-run every diff/threshold gate with both a simulated change and a no-change case before enabling its schedule.
- After any GitHub repository rename, verify visibility and metadata explicitly; redirects do not prove privacy was preserved.

## Verification
- `python3 skills/argus/scripts/fold.py --self-test` passes.
- `python3 skills/argus/scripts/eval_signal.py --self-test` passes.
- `python3 scripts/run_tests.sh` passes.
- Frontmatter `name` matches the `skills/argus/` folder and description is at most 60 characters.
- A real tracker dry-run proves changed and unchanged paths; unchanged produces no briefing.
- `cronjob list` confirms native continuity/delivery/monitor fields instead of a delivery shim.
- Remote repository HEAD, documentation, repository visibility, and CI/check state are verified after push.

## When to Use Which Reference

| Situation | Read this |
|---|---|
| Designing a new tracker | `references/tracker-schema.md` |
| Configuring a price/metric monitor | `references/diff-metrics.md` |
| Writing a briefing card | `references/briefing-template.md` |
| Setting up a cron job | `references/loop-prompt.md` |
| Migrating from pre-v0.21 | `references/converting-monitors-to-trackers.md` |
| Using GitHub as a source | `references/github-discovery.md` |
| First tick / tool failure | `references/hermes-conventions.md` |
| Troubleshooting | `references/troubleshooting.md` |
| Case studies | `references/case-studies.md` |
| Error codes | `references/error-codes.md` |
| Setting up a watchdog | `skills/argus-watch/SKILL.md` |

## Quick Start

1. **Design a tracker** — write `trackers/<slug>.yaml` per `references/tracker-schema.md`.
2. **Discover sources** — 3–5 searches, assign trust tiers, record in tracker.
3. **Create the cron job** — self-contained prompt, `argus` skill, `continuity=true`, stable `workdir`, delivery target.
4. **Run a tick** — READ → EVAL → FOLD → SIGNAL → DISCOVER. Silent tick = success.
5. **Write a heartbeat** — at the end of every tick, write `heartbeats/<slug>.json` (see `skills/argus-watch/SKILL.md`).
6. **Set up a watchdog** — separate cron job that checks heartbeats and alerts on stale ticks.

## Known Limitations

- **No real-time data.** Argus ticks are scheduled; it cannot monitor streaming sources or push notifications.
- **No authenticated sources.** Argus cannot log into paywalled or account-gated sources.
- **No code execution.** Argus never clones, installs, imports, or runs discovered code.
- **Ambiguous diffs require human judgment.** When a source reports conflicting values, Argus escalates rather than guessing.
- **Context bloat.** Large tracker YAMLs, long histories, and many sources can strain context. Use `references/hermes-conventions.md` to manage this.
- **Single-user.** Argus is designed for one user's intelligence watch, not multi-tenant monitoring.

## Skill Changelog

### 0.4.3
- Added `references/troubleshooting.md` — common issues and resolutions.
- Added `references/case-studies.md` — real-world signal detection examples.
- Updated `skills/argus-watch/scripts/watchdog.py` — configurable grace periods, exclusions, config file.
- Added `tests/skills/test_argus_watch.py` — comprehensive watchdog tests.
- Updated `skills/argus-watch/SKILL.md` — documented configuration options.

### 0.4.2
- Added `skills/argus-watch/` — zero-token watchdog skill for cron job health.
- Added `references/error-codes.md` — centralized error code reference.
- Updated `references/github-discovery.md` — added "What GitHub Discovery Does" section.
- Updated `references/memory-schema.md` — added Memory Tool API and multi-user support.

### 0.4.1
- Added `references/hermes-conventions.md` — background processes, stale-write protection, parameter typing, context compression, error handling.
- Updated `references/briefing-template.md` — supports both markdown (bot-chat) and RSS 2.0 (feed) formats.
- Updated description for better skill triggering.
- Added "When to Use Which Reference" mapping table.
- Added "Quick Start" section.
- Added "Known Limitations" section.

### 0.4.0
- Added bounded GitHub discovery with canonical identity and sparse events.
- Added `references/github-discovery.md`.
- Updated `references/briefing-template.md` — supports both markdown (bot-chat) and RSS 2.0 (feed) formats.
- Updated description for better skill triggering.
- Added "When to Use Which Reference" mapping table.
- Added "Quick Start" section.
- Added "Known Limitations" section.

### 0.3.0
- Restructured into SKILL.md + references (was 34k chars single file).
- Removed historical jargon and one-off events from core skill.
- Added CHANGELOG.md for repo-level tracking.

## References
- `references/tracker-schema.md` — tracker fields, delivery, `eval:`, and `on_signal:`.
- `references/memory-schema.md` — Hermes memory model and migration from legacy `memory.md`.
- `references/briefing-template.md` — markdown and RSS briefing formats.
- `references/diff-metrics.md` — diff/threshold semantics and report format.
- `references/loop-prompt.md` — self-contained Hermes v0.21 cron prompt and setup.
- `references/converting-monitors-to-trackers.md` — migration and gate-selection guide.
- `references/github-discovery.md` — bounded GitHub discovery, repository identity, and sparse-event retention.
- `references/hermes-conventions.md` — Hermes platform conventions (background processes, stale-write, typing, context, errors).
- `references/troubleshooting.md` — common issues and resolutions.
- `references/case-studies.md` — real-world signal detection examples.
- `references/error-codes.md` — centralized error code reference.
- `skills/argus-watch/SKILL.md` — zero-token watchdog for cron job health.
- `scripts/fold.py` — dependency-free news folding; includes `--self-test`.
- `scripts/eval_signal.py` — diff/threshold gate; includes `--self-test`.
