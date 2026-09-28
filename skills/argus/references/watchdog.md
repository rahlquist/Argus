# Watchdog Pattern

A separate cron job that watches for Argus ticks appearing on schedule. If a
tick doesn't fire within the expected window, alert the user.

## Why Separate

- Argus ticks are **silent on success** — no output means "nothing moved."
- The watchdog answers a different question: "did the job run at all?"
- Decoupling liveness from signal prevents notification overload.

## Design

### Heartbeat File

Each Argus tick writes a heartbeat file at the end of a successful run:

```
${INTEL_DIR:-$HOME/.intel}/heartbeats/<slug>.json
```

Contents:
```json
{
  "slug": "nous-llm-deals",
  "last_run": "2026-09-28T11:30:00Z",
  "status": "ok",
  "cards_emitted": 4,
  "sources_checked": 12
}
```

- Written on every tick, silent or not.
- `status` is `ok` or `error`.
- `cards_emitted` is the number of briefing cards produced (0 on silent tick).

### Watchdog Cron Job

A separate cron job runs every N minutes (e.g., every 30 min for an hourly
Argus job). Its prompt:

```
Read all files in ${INTEL_DIR:-$HOME/.intel}/heartbeats/.
For each heartbeat, check if last_run is within the expected window.
If any heartbeat is stale, alert the user with the slug and last_run time.
If all heartbeats are fresh, produce no output.
```

### Alert Format

```
⚠️ Watchdog Alert: Argus job "nous-llm-deals" is overdue.
  Last run: 2026-09-28T11:30:00Z (2h 15m ago)
  Expected: every 60 minutes
  Check: cronjob list, logs, and heartbeat file
```

## Setup

1. Create the heartbeat directory:
   ```
   mkdir -p ${INTEL_DIR:-$HOME/.intel}/heartbeats
   ```

2. Add a step to the Argus cron prompt: "At the end of every tick, write
   `heartbeats/<slug>.json` with the current timestamp and status."

3. Create the watchdog cron job:
   - Schedule: every 30 minutes (or appropriate for your Argus cadence)
   - Prompt: the watchdog prompt above
   - Delivery: `bot-chat:<profile>` (same as Argus)
   - No skill needed — this is a simple file check

## Pitfalls

- The watchdog itself can fail. Consider a meta-watchdog or a simpler
  "last run" check in your main cron dashboard.
- Don't alert on the first missed tick — allow a grace period (e.g., 1.5x
  the expected interval).
- If the Argus job is intentionally paused (e.g., vacation), the watchdog
  should be paused too.
