# Hermes Platform Conventions

Argus runs inside Hermes. These conventions prevent tool failures and reduce
context bloat. Read this before your first tick.

## Background Processes

For long-running fetches (source scans, GitHub discovery, bulk diffs):

```
# WRONG — Hermes cannot track detached processes:
terminal(command="nohup python3 script.py &")
terminal(command="python3 script.py &")

# RIGHT — Hermes tracks and notifies:
terminal(command="python3 script.py", background=true, notify_on_complete=true)
```

- `background=true` — Hermes manages the process lifecycle.
- `notify_on_complete=true` — you get a notification when it finishes; no polling.
- `notify` parameter is **boolean** `true`/`false` or a **list of strings**
  (patterns to match in output). Never a string `"True"`.
- For bounded tasks, pair with `notify=true` and react to mid-run output.

## Stale-Write Protection

Hermes refuses to overwrite an existing file unless the current task has read
its full content. This prevents clobbering concurrent updates.

```
# WRONG — fails if file exists and wasn't read this session:
write_file(path="/home/rahlquist/.intel/diff_tick.py", content="...")

# RIGHT — read first, then write:
read_file(path="/home/rahlquist/.intel/diff_tick.py")
write_file(path="/home/rahlquist/.intel/diff_tick.py", content="...")

# PREFERRED — for small changes, use patch:
patch(path="/home/rahlquist/.intel/diff_tick.py", old_string="...", new_string="...")
```

- Always `read_file` before `write_file` to an existing file.
- Use `patch` for targeted edits — it's safer and shows the diff.
- If `write_file` refuses, read the file, merge, and retry.

## Parameter Typing

Hermes tool parameters are strictly typed:

| Parameter | Type | Wrong | Right |
|---|---|---|---|
| `background` | boolean | `"true"` | `true` |
| `notify` | boolean or list[string] | `"True"` | `true` or `["pattern"]` |
| `notify_on_complete` | boolean | `"true"` | `true` |
| `timeout` | integer (seconds) | `"30"` | `30` |
| `limit` | integer | `"50"` | `50` |

When in doubt, check the tool schema with `tool_describe`.

## Context Compression

Argus skills + references + tracker state can bloat context fast. Guidelines:

- **Read only what you need.** If you only need `open_obligations` from a
  16k-char tracker YAML, use `search_files` with a regex or `read_file` with
  `offset`/`limit` — don't read the whole file.
- **Use `execute_code` for inline Python.** Instead of writing an intermediate
  `.py` file, run Python directly:
  ```
  execute_code(code="from hermes_tools import terminal; print(terminal('python3 -c ...')['output'])")
  ```
- **Prefer `patch` over `write_file`** for small changes — it shows the diff
  and avoids stale-write issues.
- **Avoid `head -100` of scripts** when `execute_code` can run them inline.
- **Set `notify_on_complete=true`** on background tasks — don't poll with
  `sleep 45; tail ...`.
- **When context grows large**, summarize prior tool results in your own words
  before continuing, so the next turn starts from a compact summary.

## Error Handling

| Failure | What to do |
|---|---|
| `terminal` exit -1 (background wrapper) | Re-send with `background=true, notify_on_complete=true` |
| `write_file` refuses (stale write) | `read_file` first, merge, retry; or use `patch` |
| `notify="True"` rejected | Use boolean `true` or list `["pattern"]` |
| Fetch times out | Mark metric `value: <error>` in state; note in report |
| Diff is ambiguous | Escalate to user; don't guess |
| Tracker YAML corrupted | Restore from git or backup; don't silently overwrite |
| Source API returns unexpected data | Log the raw response; mark as `value: <error>` |
| Background task never completes | Check `process_manage` for status; kill and retry |

## Silent Tick Output

When there is nothing to report, produce **no substantive content**. The
correct output is:

- A single line confirming the tick ran (for the watchdog), OR
- Nothing at all (if the cron job has a monitor/no-agent gate).

Do not pad with "no changes detected" or "all quiet" — that's notification
overload. The watchdog (see below) handles liveness separately.

## Watchdog Pattern

A separate cron job should watch for ticks appearing on schedule. If a tick
doesn't fire within the expected window, alert the user.

- The watchdog is a **separate** cron job, not part of Argus.
- It checks for the existence of a heartbeat file or a timestamp in the
  notepad.
- If the heartbeat is stale, it sends an alert.
- This decouples "did the job run?" from "did the job find anything?"

See `references/watchdog.md` for the full watchdog specification.
