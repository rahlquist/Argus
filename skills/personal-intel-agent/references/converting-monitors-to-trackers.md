# Converting Existing Monitors / Cron Jobs to Trackers

Real pattern from a live migration: two standing loco-bot cron jobs (a local
`hmem` provider-catalog scanner + git-commit, and an AMD Ryzen AI NPU version
watcher) were ported into `personal-intel-agent` trackers — extending the skill
with a `diff`/`threshold` engine so the monitors kept their exact value (version
bumps, git side-effects) instead of being downgraded to plain text search.

## Decision: which jobs fit

- **Monitor/cron job that reports VALUE CHANGES** (versions, prices, counts,
  statuses, set membership) → trackers with an `eval:` block (`diff` or
  `threshold` mode). This preserves the original job's core output (e.g.
  "Lemonade v11.5.2 → v11.6.0") that a fold-the-news tracker would lose.
- **Local repo maintenance that is NOT web/entity tracking** (e.g. scanning one
  local dir, appending a README, committing) → does NOT fit the skill model;
  leave it as a plain cron job. Don't force it.

## Tracker shape for a monitor

```yaml
slug: <slug>
entity: <what>
type: field
user_sentence: "<one sentence>"
sources:
  - name: github-release
    url: "https://api.github.com/repos/<owner>/<repo>/releases?per_page=3"
    type: api
    trust: primary
eval:
  mode: diff                       # or threshold (trigger: pct|abs, value: N)
  items: [lemonade_version, xdna_commit_date]   # gating metrics
metrics:
  - name: lemonade_version
    unit: version
    source: github-release
    extract: "jq -r '.[0].tag_name'"   # how to pull the value from the source
  - name: price_usd
    unit: price
    source: <price-page>
    extract: "<selector or jq>"
on_signal:                         # run ONLY when the gate passes (optional)
  - git_commit_push: "<repo-path> <commit-msg>"   # e.g. the hmem README update
delivery:
  - feed
  - bot:loco-bot
```

- Non-numeric units (`version`, `date`, `status`) → string equality diff.
- Numeric units (`count`, `price`) → feed threshold math with `delta_abs`/`delta_pct`.
- Every tick writes `state/<slug>.json` regardless of fire, so the next run
  has a correct baseline (first run = baseline, fires once).

## Cron wiring (key gotcha)

The skill's `deliver: bot:<profile>` shell-out is for *in-skill* delivery.
For a **cron job** the clean path is the scheduler's own resolver:

```
hermes -p <profile> cron create \
  --name "<name>" --skill personal-intel-agent \
  --deliver bot-chat:<profile> \
  --workdir "$INTEL_DIR" \
  "0 4 * * *" "<loop-prompt from references/loop-prompt.md, with INTEL_DIR set>"
```

- `--deliver bot-chat:<profile>` lands in that bot's chat directly — no
  `notify_bot.sh` needed for cron-driven runs.
- Keep the original job's schedule (e.g. `0 3 * * *`, `0 4 * * *`); the skill's
  hourly watch model is not mandatory.
- **Pause the original** plain-prompt job after the tracker goes live, so you
  don't double-run.

## Dry-run the gate BEFORE trusting the nightly cron

`eval_signal.py` takes `{eval, current, previous}` on stdin and emits a verdict.
Prove both paths with a synthesized prior:

```bash
# simulate a change -> expect rc=0 (passed), changed list non-empty
echo '{"eval":{"mode":"diff"},"current":{"x":{"value":"v2","unit":"version"}},
       "previous":{"x":{"value":"v1"}}}' | python scripts/eval_signal.py
# simulate no change -> expect rc=1 (silent)
echo '{"eval":{"mode":"diff"},"current":{"x":{"value":"v1"}},
       "previous":{"x":{"value":"v1"}}}' | python scripts/eval_signal.py
```

A monitor that can't prove its gate fires on change and stays silent on no-change
is worse than the original cron job. Verify before flipping the schedule.

## Repo rename-privacy gotcha (GitHub)

During this migration the skill's home repo was renamed
(`hermes-skills` → `personal-intel-agent`). The rename left the repo **PUBLIC**
despite starting private. Fix:

```
gh repo edit <owner>/<repo> --visibility private --accept-visibility-change-consequences
# verify:
curl -s -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/repos/<owner>/<repo> \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['private'])"
```

**Always re-check `private: true` after a rename.** Old URLs 301-redirect, so
existing links/remotes keep working — but update any hardcoded repo-name
references in READMEs/catalog so they don't go stale.

## Principles that held

- A silent tick is correct. The point of porting is *fewer* noisy runs, not more.
- Preserve the original job's exact output contract (version deltas, git commits).
  If the skill can't carry it, extend the skill (as done here with `eval:` +
  `on_signal:`) rather than silently dropping it.
