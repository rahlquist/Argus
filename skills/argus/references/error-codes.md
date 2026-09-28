# Error Codes

Centralized list of error codes and their meanings for Argus operations.

## Terminal Errors

| Code | Meaning | Resolution |
|---|---|---|
| `exit -1` | Shell-level background wrapper detected (`nohup`/`disown`/`setsid`) | Re-send with `background=true, notify_on_complete=true` |
| `exit 127` | Command not found | Check command path; use absolute paths |
| `exit 126` | Command not executable | Check file permissions; use `python3 script.py` instead of `./script.py` |
| `exit 130` | Interrupted (SIGINT) | Re-run the command |
| `exit 137` | Killed (SIGKILL, often OOM) | Reduce memory usage; split the task |
| `exit 143` | Terminated (SIGTERM) | Re-run the command |

## File Errors

| Code | Meaning | Resolution |
|---|---|---|
| `stale_write_blocked` | `write_file` refused — file exists but wasn't read this session | `read_file` first, merge, retry; or use `patch` |
| `file_not_found` | File doesn't exist | Check path; create with `write_file` if needed |
| `permission_denied` | Insufficient permissions | Check file ownership; use `sudo` if needed |
| `disk_full` | No space left on device | Clean up old files; check `df -h` |

## API Errors

| Code | Meaning | Resolution |
|---|---|---|
| `rate_limited` | API rate limit hit | Wait and retry; check `Retry-After` header |
| `timeout` | API request timed out | Retry with longer timeout; check network |
| `auth_failed` | API authentication failed | Check API key; refresh token if needed |
| `not_found` | API resource not found | Check URL; resource may have been deleted |
| `server_error` | API server error (5xx) | Retry with backoff; check status page |

## Cron Errors

| Code | Meaning | Resolution |
|---|---|---|
| `job_paused` | Job is paused | `hermes cron resume <id>` |
| `job_missing` | Job not found | `hermes cron list` to verify job ID |
| `dispatch_failed` | Job failed to dispatch | Check `hermes cron runs <id>` for details |
| `execution_failed` | Job execution failed | Check `hermes cron runs <id>` for error output |
| `delivery_failed` | Delivery target failed | Check delivery target config; verify bot/chat is active |

## Memory Errors

| Code | Meaning | Resolution |
|---|---|---|
| `memory_full` | Memory budget exceeded | Consolidate stale entries; remove duplicates |
| `memory_not_found` | Memory entry not found | Check key; entry may have been removed |
| `memory_write_failed` | Memory write failed | Check memory provider; retry |

## Validation Errors

| Code | Meaning | Resolution |
|---|---|---|
| `invalid_tracker_yaml` | Tracker YAML is malformed | Validate against `references/tracker-schema.md` |
| `invalid_metric_value` | Metric value is not valid for its unit | Check unit type; verify source data |
| `invalid_source_url` | Source URL is malformed or unreachable | Check URL; verify source is active |
| `duplicate_slug` | Tracker slug already exists | Use a unique slug; check `trackers/` directory |

## Watchdog Errors

| Code | Meaning | Resolution |
|---|---|---|
| `heartbeat_stale` | Heartbeat file is older than expected | Check if Argus job is running; verify cron |
| `heartbeat_missing` | No heartbeat file found | Check if Argus job has run; verify heartbeat path |
| `job_disabled` | Argus job is disabled | `hermes cron resume <id>` |
| `job_error` | Argus job reported an error | Check `hermes cron runs <id>` for details |
