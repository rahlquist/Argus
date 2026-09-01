# Converting Existing Monitors or Cron Jobs to Argus

Hermes v0.21 absorbs the generic scheduler plumbing that earlier versions of
this skill carried itself. The migration goal is not to force every cron job
through Argus; it is to keep Argus where semantic intelligence work remains
and delegate generic scheduling, memory, continuity, gating, and delivery to
Hermes.

## Classify the job first

| Job shape | Correct implementation |
|---|---|
| Stable script output needs direct delivery, no reasoning | Cron `no_agent=true` script job; not Argus |
| One deterministic script/URL should wake an agent only on change | Cron `monitor` / CLI `--monitor-script` or `--monitor-url` + Argus prompt |
| Several typed metrics need diff/threshold math and a structured report | Argus tracker with `eval:` + `eval_signal.py` |
| Many sources require semantic folding, trust weighting, and synthesis | Argus news tracker |
| Local repo maintenance with no intelligence tracking | Plain cron job; do not force it into Argus |

## What v0.21 replaces

- **Private `memory.md` user model → Hermes persistent memory.** Cron agents
  now load MEMORY.md/USER.md and can update memory through the normal tool.
- **`notify_bot.sh` → `deliver: bot-chat:<profile>`.** Native delivery injects
  the briefing as a real inbound turn in the target bot's canonical Bot Chat.
- **Hand-written previous-run handoff → `continuity=true`.** Hermes injects the
  prior final output so Argus can avoid repeating the same briefing.
- **Always-running LLM watchdog → native monitor mode.** Unchanged exact output
  suppresses the agent and delivery entirely.
- **Tiny cursor files → cron notepad where appropriate.** The notepad is
  bounded scratch state, not a tracker database.

## What remains Argus-owned

- Tracker specifications and signal/noise policy
- Source discovery and trust tiers
- Durable URL-level archive and provenance
- Multi-source semantic folding
- Typed metric comparison and threshold reports
- Briefing-card structure and confidence
- Beyond-radar discovery tied to user interests
- Optional `on_signal:` actions

`continuity` does not replace the archive: it carries only the latest final
output and Hermes caps injected output. The archive is the long-term item-level
deduplication record.

## Tracker shape for typed metrics

```yaml
slug: <slug>
entity: <subject>
type: field
user_sentence: "<one-sentence watch>"
sources:
  - name: github-release
    url: "https://api.github.com/repos/<owner>/<repo>/releases?per_page=3"
    type: api
    trust: primary
eval:
  mode: diff                         # or threshold
  items: [release_version, issue_status]
metrics:
  - name: release_version
    unit: version
    source: github-release
    extract: "first release tag_name"
  - name: price_usd
    unit: price
    source: <price-page>
    extract: <selector-or-json-path>
on_signal:
  - git_commit_push: "<repo-path> <commit-message>"
delivery:
  - feed                              # cron routes this final output
status: live
```

Every tick writes `state/<slug>.json`, including silent ticks. The first run of
`diff` establishes and reports a baseline; the first run of `threshold`
establishes a silent baseline.

## Native cron wiring

Using the `cronjob` tool:

```yaml
name: <watch name>
schedule: "0 4 * * *"
prompt: <self-contained Argus loop prompt>
skills: [argus]
workdir: /absolute/path/to/.intel
continuity: true
deliver: bot-chat:<profile>
reasoning_effort: medium
```

CLI equivalent:

```bash
hermes cron create \
  --name "<watch name>" \
  --skill argus \
  --deliver "bot-chat:<profile>" \
  --continuity \
  --workdir "/absolute/path/to/.intel" \
  --reasoning-effort medium \
  "0 4 * * *" \
  "<self-contained Argus loop prompt>"
```

Keep the original schedule unless the user changes it. Pause the old job only
after the replacement is listed and a manual run proves its changed and
unchanged paths.

## Native monitor-mode wiring

Use this when one cheap source represents the watched state:

```bash
hermes cron create \
  --name "<watch name>" \
  --skill argus \
  --monitor-script "stable-monitor.py" \
  --deliver "bot-chat:<profile>" \
  --continuity \
  "0 4 * * *" \
  "Interpret the detected change, verify it against authoritative sources, and emit an Argus briefing only if material."
```

The monitor script path resolves under `~/.hermes/scripts/`; it is a path, not
an inline shell pipeline. `--monitor-url` accepts an HTTP(S) URL instead.
Unchanged exact bytes skip the LLM. Sort output and omit timestamps, random
IDs, and unstable whitespace.

## Dry-run before cutover

Prove the typed-metric gate independently:

```bash
printf '%s\n' '{"eval":{"mode":"diff"},"current":{"x":{"value":"v2","unit":"version"}},"previous":{"x":{"value":"v1"}}}' \
  | python3 skills/argus/scripts/eval_signal.py

printf '%s\n' '{"eval":{"mode":"diff"},"current":{"x":{"value":"v1","unit":"version"}},"previous":{"x":{"value":"v1"}}}' \
  | python3 skills/argus/scripts/eval_signal.py
```

The first command must return a passed verdict; the second must print `SILENT`
and exit 1. Then fire the actual cron job once and verify its execution ledger
and destination before pausing the predecessor.

## Migration checklist

- [ ] Classify job: plain script, native monitor, Argus metric, or Argus news.
- [ ] Migrate durable user preferences from legacy `memory.md` to Hermes memory.
- [ ] Replace bot shell delivery with `bot-chat:<profile>`.
- [ ] Enable `continuity` for recurring scout/digest behavior.
- [ ] Preserve archive/state paths if they carry valid dedup history.
- [ ] Dry-run change and no-change paths.
- [ ] Create and verify replacement job, then pause the predecessor.
- [ ] Verify delivery and ensure no duplicate schedule remains active.
