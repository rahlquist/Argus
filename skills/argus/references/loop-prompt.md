# Hermes v0.21 Standing-Watch Prompt

Use this as the self-contained `prompt` for an Argus cron job. Replace the
state directory and cadence as needed.

## Recommended cron setup

From an agent, create the job with `cronjob` using these fields:

```yaml
name: <watch name>
schedule: <schedule>
prompt: <the prompt below>
skills: [argus]
workdir: /absolute/path/to/.intel
continuity: true
deliver: bot-chat:<profile>  # or origin/local/platform:chat_id
```

From the CLI, the equivalent core options are:

```bash
hermes cron create \
  --name "<watch name>" \
  --skill argus \
  --deliver "bot-chat:<profile>" \
  --continuity \
  --workdir "/absolute/path/to/.intel" \
  "<schedule>" \
  "<the prompt below>"
```

Use `--monitor-script <path>` or `--monitor-url <url>` only when one stable,
deterministic output can gate the whole job. Hermes hashes exact bytes; a
timestamp or nondeterministic ordering defeats suppression.

## Prompt

You are running a standing Argus personal-intelligence watch. The current
working directory is the tracker state directory. Follow the `argus` skill.

Hermes has injected persistent user memory and, when continuity is enabled,
the previous run's final output. Apply that memory to source weighting and
noise rules. Use the previous output to avoid repeated reporting; do not treat
it as the durable item archive.

For every `trackers/*.yaml` with `status: live`:

1. READ every configured source. Append only new URLs to
   `archive/<slug>.jsonl`; preserve source and trust provenance.
2. If the tracker has `eval:`:
   - collect current metric values;
   - write `state/<slug>.current.json`;
   - compare with `state/<slug>.json` via `scripts/eval_signal.py`;
   - persist the current snapshot even when the gate is silent;
   - if `passed` is false, emit nothing for that tracker.
3. Otherwise FOLD only newly collected rows through `scripts/fold.py`, apply
   the tracker noise policy, and keep cards that represent material movement.
4. Run `on_signal:` actions only after the gate passes.
5. SIGNAL with sourced briefing cards. Do not repeat a card already reported
   in the injected previous-run output.
6. DISCOVER with 1–2 adjacent searches seeded from interests in Hermes
   persistent memory. Keep only discoveries tied to a stated interest.
7. Update the tracker's `last_tick`.

Do not pad a no-change run. If no tracker has a material signal, return no
substantive briefing content. For jobs that require guaranteed scheduler-level
no-delivery behavior, use native monitor mode or a `no_agent` script gate.
Never invent an item, metric, URL, delta, or source result.
