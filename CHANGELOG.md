# Changelog

## 0.6.0 — Scratch proposals and measured fold thresholds

- **Scratch** (`scripts/argus_scratch.py`): undirected tracker proposals.
  DISCOVER is seeded from interests you already track, so it can only return
  more of the same. Scratch runs deliberately undirected searches and proposes
  *new* trackers as reviewable drafts — capped at 3 per run, deduped against
  live trackers, idempotent by stable id, expiring after 30 days, and created
  only on explicit human acceptance. `accept` emits a tracker spec skeleton.
- **Measured fold thresholds** (`fold.py --eval`): the folding threshold was a
  guess. `--eval` scores it against labeled fixtures and prints a
  precision/recall/F1 table per threshold, with `n/a` for undefined metrics
  instead of a misleading zero. `--fixtures` and `--sweep` are configurable.
- **Labeled fixture set** (`assets/fold-labels.jsonl`): 8 cases / 24 labeled
  pairs built from real archived rows, including the over-merge trap (two
  near-identical motherboard titles that are different SKUs). Marked as an
  agent-labeled starter set — review before trusting the table.
- **Finding**: on that fixture set the live cron prompts' `--sim 0.4` splits
  most true duplicates (recall 0.29) and `fold.py`'s own default of 0.6 folds
  nothing at all (recall 0.00). Best F1 at 0.20. Directional evidence, not a
  verdict — labels need human review before changing production thresholds.
- **Index-based clustering**: `cluster_indices()` returns index lists so labeled
  fixtures map labels back to members even when two rows are byte-identical.
- Docs: `references/scratch.md`, `references/fold-tuning.md`.
- Tests: `tests/skills/test_argus_scratch.py` (12 tests) plus fold-eval cases.

## 0.5.0 — Tick ledger, weekly rollup, and deterministic collectors

- **Tick ledger** (`scripts/argus_ticks.py`): one bounded JSONL line per tick
  recording job, slug, outcome, counts, and per-source outcomes. Shared ledger
  path (`$ARGUS_TICK_LEDGER`, default `~/.intel/state/ticks.jsonl`) so a single
  weekly job can report on every Argus watch on the machine.
- **Weekly rollup**: one Saturday message with a one-line
  `completed / failed` count per job, a source-health section (trailing error
  and zero-item streaks, reset by a successful read), and a retirement-candidate
  section for trackers silent beyond the threshold. `--prune` drops records
  older than the window after reporting, keeping the ledger at two weeks.
- **Cadence-aware retirement**: `--cadence slug=monthly` (or `weekly`, `daily`,
  `instant`, or a day count) raises the silence threshold so a legitimately
  quiet tracker is not proposed for retirement.
- **Collectors** (`scripts/argus_collect.py`): named, testable metric
  functions replacing prose `extract:` instructions. Built-ins cover GitHub
  releases/commits/issue state, HTTP JSON and regex reads, and local JSON sets,
  paths, and glob counts. Output drops straight into
  `state/<slug>.current.json`.
- **Explicit escape hatch**: `llm_extract` is the only non-deterministic
  collector. It requires an agent-supplied value and is always reported with
  `deterministic: false`, so interpreted values are distinguishable from
  measured ones.
- **Structural anti-fabrication**: a failed collector produces
  `value: "<error>"` with the exception text instead of relying on model
  discipline to avoid inventing a value.
- Docs: `references/tick-ledger.md`, `references/collectors.md`,
  `references/weekly-rollup.md`; `tracker-schema.md` now leads with
  `collector:`.
- Tests: `tests/skills/test_argus_ticks.py`, `tests/skills/test_argus_collect.py`
  (33 cases, no network, no disk).

## 0.4.3 — Troubleshooting, case studies, watchdog config, tests

- Added `references/troubleshooting.md` — common issues and resolutions
- Added `references/case-studies.md` — real-world signal detection examples
- Updated `skills/argus-watch/scripts/watchdog.py` — configurable grace periods, exclusions, config file
- Added `tests/skills/test_argus_watch.py` — comprehensive watchdog tests
- Updated `skills/argus-watch/SKILL.md` — documented configuration options
- Version: 0.4.2 → 0.4.3

## 0.4.2 — Argus Watch skill, error codes, GitHub discovery clarity

- Added `skills/argus-watch/` — zero-token watchdog skill for cron job health
- Added `references/error-codes.md` — centralized error code reference
- Updated `references/github-discovery.md` — added "What GitHub Discovery Does" section
- Updated `references/memory-schema.md` — added Memory Tool API and multi-user support
- Removed `references/watchdog.md` — replaced by `skills/argus-watch/`
- Version: 0.4.1 → 0.4.2

## 0.4.1 — Hermes conventions, watchdog, and briefing format

- Added `references/hermes-conventions.md` — background process pattern,
  stale-write protection, parameter typing, context compression, error
  handling, and silent tick output.
- Added `references/watchdog.md` — heartbeat pattern and watchdog cron job
  specification for liveness monitoring.
- Updated `references/briefing-template.md` — supports both markdown
  (bot-chat) and RSS 2.0 (feed) formats.
- Updated skill description for better triggering.
- Added "When to Use Which Reference" mapping table to SKILL.md.
- Added "Quick Start" section to SKILL.md.
- Added "Known Limitations" section to SKILL.md.
- Added skill-level changelog to SKILL.md.
- Updated README.md with watchdog section.

## 0.4.0 — Bounded GitHub discovery foundation

- Added canonical, case-insensitive `owner/repository` identity handling.
- Added compact per-repository state merging with source provenance and
  `times_seen` tracking.
- Added sparse `new_activity` events for distinct `pushed_at` transitions;
  unchanged observations and star-only changes do not create archive events.
- Added hard candidate bounds and documentation for daily discovery and weekly
  re-evaluation, preventing GitHub scans from turning repeated observations
  into unbounded Argus archive growth.
- Added an explicit safety boundary: repository classifications are review
  candidates, never automatic clone/install/execute permissions.
- Deliberately did not import GitRadar's scheduler, duplicate cache layout, or
  blind self-tuning threshold loop; Hermes cron and Argus state remain the
  owners of those concerns.

## 0.3.0 — Argus / Hermes v0.21 native-cron rewrite

### Renamed
- Renamed the skill from `personal-intel-agent` to **Argus**.
- Moved the install path from `skills/personal-intel-agent/` to
  `skills/argus/` and renamed the behavior test accordingly.
- Updated repository docs, catalog entries, commands, examples, and script
  identity to use `argus` consistently.

### Re-architected around Hermes v0.21
- **Persistent user model:** replaced the Argus-private `memory.md` contract
  with Hermes persistent MEMORY.md/USER.md and the `memory` tool. Cron runs now
  share preferences and interests with Desktop, CLI, messaging, and Bot Mode
  instead of maintaining a divergent second memory store.
- **Run continuity:** recurring jobs now use `continuity=true` (CLI
  `--continuity`) so Hermes injects the previous final output. Argus uses that
  context to avoid repeat briefings and continue incremental digests.
- **Native change gating:** documented cron `monitor` / CLI
  `--monitor-script` and `--monitor-url` for deterministic watches. Exact
  unchanged output skips the LLM and delivery entirely.
- **Native Bot Chat delivery:** replaced the `notify_bot.sh` subprocess shim
  with `deliver: bot-chat:<profile>`. Delivery becomes a first-class scheduler
  route and a real inbound Bot Chat turn that the target bot can answer.
- **Durable bounded scratch state:** documented cron's per-job notepad for
  small cursors and watermarks rather than ad-hoc tiny state files.
- **Per-job reasoning:** documented `reasoning_effort` so expensive synthesis
  can be pinned without changing the global model configuration.

### Deliberately retained Argus state and logic
- Kept `archive/<slug>.jsonl` for long-term URL-level deduplication and source
  provenance. Hermes continuity contains only the latest bounded output and is
  not an item database.
- Kept tracker specifications, trust tiers, semantic multi-source folding,
  typed metric diff/threshold evaluation, briefing templates, adjacent-signal
  discovery, and optional `on_signal:` actions. These are intelligence-domain
  behavior, not scheduler plumbing.
- Kept `state/<slug>.json` for complete typed metric snapshots; the cron
  notepad is intentionally bounded and not a metric-history replacement.

### Migration
- Added a migration guide that classifies existing jobs as plain script,
  native monitor, Argus metric tracker, or Argus news tracker.
- Added one-time migration from legacy `${INTEL_DIR}/memory.md` to Hermes
  memory, preserving only durable user facts.
- Removed `scripts/notify_bot.sh`; cron jobs should use native Bot Chat
  delivery.
- Added a self-contained v0.21 loop prompt and both `cronjob` and CLI setup
  examples using `argus`, continuity, stable workdir, native delivery, monitor
  mode, and reasoning effort.

### Platform support
- Restored `[linux, macos, windows]`: Argus's remaining helper scripts are
  Python and the skill no longer depends on the POSIX-only delivery shim.

## 0.2.0
- **Fix: `eval.items:` metric gate was dead code.** The gate now restricts
  firing to only the metrics listed in `eval.items:` (or all metrics when
  omitted). Previously every metric gated regardless, defeating the documented
  contract and the "list only price metrics" guidance. (`eval_signal.py`)
- **Fix: `fold.py` source_count now counts distinct sources**, not raw cluster
  length (duplicate sources no longer inflate "folded from N sources").
- **Fix: `fold.py` no longer raises BrokenPipeError** when stdout is closed
  early.
- **Docs:** corrected `fold.py` description from char-trigram to word-level
  TF-IDF; fixed the repeated `--noise` usage form; clarified first-run baseline
  differences (`diff` reports once, `threshold` is silent).
- **Schema:** added `on_signal:` to `tracker-schema.md`.
- **Safety:** expanded runtime-state ignores and resolved state from
  `INTEL_DIR` rather than a hardcoded relative path.
- **Testing:** added behavior-contract tests and self-test runners.

## 0.1.0
- Initial release: news watch (READ → FOLD → SIGNAL → DISCOVER), metric/price
  monitor (`diff`/`threshold`), private `memory.md` user model, and
  feed/file/RSS/audio/bot delivery.
