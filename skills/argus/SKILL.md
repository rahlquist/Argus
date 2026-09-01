---
name: argus
description: "Watch topics and brief only when material signals move."
version: 0.3.0
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

Hermes v0.21 supplies the scheduler plumbing. Argus supplies the domain logic: tracker design, source discovery, trust ranking, URL-level deduplication, multi-source folding, threshold evaluation, briefing cards, and adjacent-signal discovery.

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

## References
- `references/tracker-schema.md` — tracker fields, delivery, `eval:`, and `on_signal:`.
- `references/memory-schema.md` — Hermes memory model and migration from legacy `memory.md`.
- `references/briefing-template.md` — signal card and RSS addendum.
- `references/diff-metrics.md` — diff/threshold semantics and report format.
- `references/loop-prompt.md` — self-contained Hermes v0.21 cron prompt and setup.
- `references/converting-monitors-to-trackers.md` — migration and gate-selection guide.
- `scripts/fold.py` — dependency-free news folding; includes `--self-test`.
- `scripts/eval_signal.py` — diff/threshold gate; includes `--self-test`.
