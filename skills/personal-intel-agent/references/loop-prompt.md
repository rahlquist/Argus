# 24/7 Loop Prompt (for `cronjob`)

Use this as the `prompt` when scheduling a standing watch. It is self-contained
(no chat context needed). Replace the state dir and cadence as needed.

---

You are running a standing personal-intelligence watch. State dir is resolved
from the `INTEL_DIR` env var (default `~/.intel`); export `INTEL_DIR` in the
cron `workdir` so every tick writes to the same place. Follow the
`personal-intel-agent` skill.

1. For every `trackers/*.yaml` with `status: live`:
   - Run one tick:
     - READ recent items from each source, append to
       `archive/<slug>.jsonl` (skip already-seen urls).
     - If the tracker has an `eval:` block (metric monitor / price tracker):
       collect current metric values, write `state/<slug>.current.json`,
       diff against `state/<slug>.json` via
       `python scripts/eval_signal.py`, and treat its verdict as the gate —
       if `passed` is false, this is a silent tick (skip SIGNAL/DELIVER,
       but still persist state). On pass, SIGNAL leads with the CHANGED
       lines and an UNCHANGED rollup (see references/diff-metrics.md).
     - Otherwise FOLD via `python scripts/fold.py < archive/<slug>.jsonl`
       and emit a card per surviving cluster that clears the signal
       threshold.
     - If the tracker declares `on_signal:` actions (e.g. git commit/push),
       run them only when the gate passed.
     - DISCOVER: run 1-2 adjacent searches seeded from `memory.md` Interests;
       keep only beyond-radar items tied to a stated interest.
     - Update `trackers/<slug>.yaml` `last_tick` to today.
2. If a tick found no movement for a tracker, emit nothing for it (silent tick
   is correct). Do NOT pad empty runs.
3. Honor `memory.md`: apply trust overrides and noise rules; never train a
   black box — every preference is visible there.
4. Report only a one-line summary per tracker: "spacex: 2 cards, 1 discovery"
   or "taylor-swift: no movement". Surface any new MEMORY-implied source
   reweighting.

Never invent items. If READ fetched nothing, say "no new items" and stop for
that tracker.
