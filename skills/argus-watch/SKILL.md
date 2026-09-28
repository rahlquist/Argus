---
name: argus-watch
description: "Zero-token watchdog for Hermes cron jobs. Monitors job health, alerts on failures."
version: 0.1.0
author: rahlquist (rahlquist), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [monitoring, watchdog, cron, health, alerts]
    related_skills: [argus]
---

# Argus Watch

A zero-token watchdog for Hermes cron jobs. Monitors job health and alerts on failures.

## When to Use

- You want to ensure your cron jobs are running on schedule
- You want to be alerted when a job fails or is overdue
- You want a lightweight health check that doesn't consume tokens

## Quick Start

1. **Create the watchdog cron job:**
   ```bash
   hermes cron create \
     --name "argus-watch" \
     --schedule "every 30m" \
     --no-agent \
     --script "skills/argus-watch/scripts/watchdog.py" \
     --deliver "bot-chat:<profile>"
   ```

2. **The watchdog runs every 30 minutes** (or your chosen interval) and:
   - Checks all active cron jobs for overdue runs
   - Alerts if a job is paused/disabled but should be active
   - Alerts if a job's last run failed
   - Stays silent when all jobs are healthy

3. **For error analysis** (when the watchdog finds issues), attach the `argus` skill to the cron job so the agent can analyze failures in detail.

## How It Works

- **Zero-token mode:** `--no-agent` runs the script directly, no LLM involved
- **Silent on success:** No output = no delivery = no notification
- **Alerts on failure:** Output is delivered to the configured target
- **Grace period:** Jobs are only flagged after 1.5x their expected interval

## Configuration

### Command-line Options

| Option | Default | Description |
|---|---|---|
| `--grace-period` | `1.5` | Grace period multiplier |
| `--exclude` | — | Exclude a job from checks (repeatable) |
| `--config` | — | Path to JSON config file |

### Config File

```json
{
  "grace_period": 1.5,
  "excludes": ["job-id-1", "job-id-2"],
  "jobs": {
    "job-id-1": {"grace_period": 2.0},
    "job-id-2": {"grace_period": 1.0}
  }
}
```

- `grace_period` — default grace period multiplier (default: 1.5)
- `excludes` — job IDs to skip during checks
- `jobs.<id>.grace_period` — per-job override of the grace period

### Per-job Grace Periods

Different jobs may need different grace periods:

- **Fast jobs** (every 5m): grace period 1.0x = 5 minutes
- **Normal jobs** (every 60m): grace period 1.5x = 90 minutes
- **Slow jobs** (every 24h): grace period 2.0x = 48 hours

Set per-job grace periods in the config file:

```json
{
  "jobs-id-1": {"grace_period": 2.0}
}
```

## Scripts

- `scripts/watchdog.py` — zero-token health check script

## Pitfalls

- The watchdog itself can fail. Consider a meta-watchdog or a simpler "last run" check in your main cron dashboard.
- Don't alert on the first missed tick — allow a grace period (e.g., 1.5x the expected interval).
- If a cron job is intentionally paused (e.g., vacation), the watchdog should be paused too.
- The watchdog checks `hermes cron list --all` — if this command fails, the watchdog will alert.
