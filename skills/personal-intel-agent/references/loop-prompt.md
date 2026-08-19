# 24/7 Loop Prompt (for `cronjob`)

Use this as the `prompt` when scheduling a standing watch. It is self-contained
(no chat context needed). Replace the state dir and cadence as needed.

---

You are running a standing personal-intelligence watch. State dir: `./.intel/`
(override with env INTEL_DIR). Follow the `personal-intel-agent` skill.

1. For every `trackers/*.yaml` with `status: live`:
   - Run one tick: READ recent items from each source, append to
     `archive/<slug>.jsonl` (skip already-seen urls), then FOLD via
     `python scripts/fold.py < archive/<slug>.jsonl`.
   - For each surviving cluster that clears the tracker's signal threshold,
     write a briefing card to `briefings/<date>-<slug>.md` per the skill's
     card template, and deliver per the tracker's `delivery:` (feed/file/rss/audio/bot:<profile>).
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
