# Troubleshooting

Common issues and their resolutions for Argus operations.

## Tracker Not Firing

| Symptom | Likely Cause | Fix |
|---|---|---|
| Tracker never fires | `eval.items` excludes the metric that changed | Check `eval.items` in tracker YAML |
| Tracker fires on every tick | `mode: diff` with no `items` gate | Add `eval.items` to limit gating metrics |
| Tracker fires when it shouldn't | Non-numeric metric in `eval.items` | Remove non-numeric metrics from `eval.items` |
| Tracker stops firing | State file corrupted or deleted | Check `state/<slug>.json`; restore from backup |
| Tracker fires once then stops | First-run baseline not persisted | Verify `state/<slug>.json` is written every tick |

## Briefing Is Empty

| Symptom | Likely Cause | Fix |
|---|---|---|
| No briefing on a tick with changes | All sources filtered as noise | Check noise rules in tracker YAML |
| No briefing on a tick with changes | All items folded into existing archive | Check `archive/<slug>.jsonl` for duplicate URLs |
| No briefing on a tick with changes | `continuity` is suppressing repeated cards | Verify continuity is working as expected |
| Briefing is always empty | All sources are tertiary | Add primary/secondary sources |
| Briefing is always empty | `monitor` gate is too strict | Check monitor script output |

## Source Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| Source URL returns 404 | Source moved or deleted | Update source URL in tracker YAML |
| Source returns unexpected data | API changed or is down | Check source API; mark metric as `value: <error>` |
| Source is rate-limited | Too many requests | Add rate limiting; increase interval between ticks |
| Source is paywalled | Authentication required | Remove source or use alternative |
| Source returns HTML instead of JSON | URL changed | Update source URL or extract logic |

## Cron Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| Job is paused | Manually paused or auto-paused on failure | `hermes cron resume <id>` |
| Job never runs | Job is disabled | `hermes cron resume <id>` or check `hermes cron list` |
| Job runs but doesn't deliver | Delivery target misconfigured | Check `--deliver` flag; verify bot/chat is active |
| Job runs late | System overload or other jobs blocking | Check system load; adjust schedule |
| Job fails repeatedly | Script error or missing dependency | Check `hermes cron runs <id>` for error output |

## Memory Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| Preferences not applied | Memory not loaded or outdated | Check `hermes memory status`; verify MEMORY.md |
| Memory is full | Too many entries | Consolidate stale entries; remove duplicates |
| Memory write fails | Memory provider issue | Check `hermes memory status`; retry |
| Tracker uses legacy `memory.md` | Pre-v0.21 installation | Migrate to Hermes memory (see `references/memory-schema.md`) |

## Watchdog Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| Watchdog alerts on every run | Grace period too tight | Increase grace period (default 1.5x interval) |
| Watchdog never alerts | Jobs are all paused | Verify at least one job is active |
| Watchdog itself fails | `hermes cron list` fails | Check Hermes installation; verify cron is running |
| Watchdog alerts on intentional pause | Job paused for vacation | Pause watchdog too, or add job to exclusion list |

## Performance Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| Tick takes too long | Too many sources or slow API | Reduce sources; increase interval; use `delegate_task` for parallel clusters |
| Context bloat | Reading full files instead of sections | Use `read_file` with `offset`/`limit`; use `search_files` with regex |
| High token usage | Large skill or too many references | Load only needed references; use `execute_code` for inline Python |
| Slow fold operation | Too many items to fold | Increase `sim` threshold; filter noise before folding |

## Error Codes

See `references/error-codes.md` for the full list of error codes and their meanings.
