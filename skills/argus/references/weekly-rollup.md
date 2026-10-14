# Weekly Rollup Job

One message per week covering every Argus watch on the machine: per-job tick
counts, source health, and retirement candidates — then a two-week ledger prune.

## Setup

```yaml
name: argus weekly rollup
schedule: "0 9 * * 6"          # Saturday 09:00
skills: [argus]
deliver: bot-chat:<profile>    # same delivery as the watches themselves
workdir: /absolute/path/to/.intel
continuity: false              # the report is self-contained; no prior-run context needed
```

CLI equivalent:

```bash
hermes cron create \
  --name "argus weekly rollup" \
  --skill argus \
  --deliver "bot-chat:<profile>" \
  --workdir "$INTEL_DIR" \
  "0 9 * * 6" \
  "<the prompt below>"
```

Do **not** enable continuity here: the rollup is deterministic output from the
ledger, not an incremental digest, and prior-run injection would only add
tokens.

## Prompt

You are producing the Argus weekly rollup. Do not run any trackers and do not
fetch sources — this job reports on the ledger only.

1. Run:

   ```bash
   python3 <skill>/scripts/argus_ticks.py rollup --days 14 --silent-days 14 --prune \
     --cadence <slug>=<cadence> ...
   ```

   Pass one `--cadence` hint per tracker whose cadence is slower than daily
   (for example `--cadence slug-voice-service=monthly`) so a legitimately quiet
   watch is not proposed for retirement.

2. Return the script's output verbatim as your final response. It is already
   the complete message: job tick counts, source health, and retirement
   candidates.

3. Add at most one short line if a retirement candidate needs context the
   ledger cannot know (for example: "this tracker is intentionally seasonal").
   Otherwise add nothing.

Constraints:

- One message, every Saturday. Do not pad, do not repeat individual briefings,
  and do not summarize what each tracker watches.
- Do not run `--prune` separately; the rollup command already prunes after
  building the report.
- If the ledger is empty, say so in one line. An empty ledger means no Argus
  job recorded a tick — that is itself the finding.
