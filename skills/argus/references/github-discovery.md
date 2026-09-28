# GitHub Discovery Extension

## What GitHub Discovery Does

- **Discovers new repositories** matching your interests (daily/weekly scans)
- **Tracks repository activity** — detects meaningful `pushed_at` transitions
- **Deduplicates by canonical identity** — `owner/repo` is the unique key
- **Generates sparse events** — only first discovery and meaningful activity
- **Briefs on new activity** — only when something material changes
- **Respects hard bounds** — candidate, new-repo, and event limits per run
- **Never clones or executes** — discovered repos are candidates for review only

## What It Does Not Do

- Does not track stars, forks, or other metrics as news events
- Does not create archive rows for every API observation
- Does not clone, install, import, or run discovered code
- Does not replace the archive — it feeds into it with sparse events

## Storage Contract

Use three layers:

- `state/github/repos/<owner>__<repo>.json` — one mutable record per canonical
  case-insensitive `owner/repo` identity.
- `archive/github/events.jsonl` — sparse events only: first discovery,
  meaningful `pushed_at` transitions, or explicit user-relevant classification
  changes.
- `briefings/github/` — rendered cards.

Merge sightings from API queries and daily/weekly Trending into the same state
record. Store query/source provenance in `sources_seen` rather than duplicating
repository records.

## Deduplication rules

1. Canonical identity is lowercase `owner/repository`, never the search URL.
2. First sighting creates state and may create a discovery event.
3. Same repository with unchanged `pushed_at` updates `last_seen` and
   `times_seen` only; it creates no event and no briefing.
4. A changed `pushed_at` creates one `new_activity` event per distinct timestamp.
5. Star-count changes update state silently by default.
6. A repository found by multiple trackers is still one state record; attach
   `matched_trackers` rather than duplicating it.
7. Filtered candidates never enter durable state unless needed for tuning
   statistics; raw API payloads are not retained.

## Hard bounds

Apply limits before LLM processing and persistence:

```yaml
github:
  max_candidates_per_query: 100
  max_total_candidates_per_run: 500
  max_new_repos_per_run: 50
  max_events_per_run: 25
  inactive_state_retention_days: 365
```

These bounds protect the archive when self-tuning lowers star thresholds.

## Discovery modes

- **Daily:** search for new repositories and recent candidates. Deduplicate by
  repository identity; brief only new high-relevance discoveries.
- **Weekly:** recheck tracked repository state and compare `pushed_at`. Brief
  only meaningful new activity; do not write a snapshot event for every
  unchanged repository.

Hermes cron owns daily/weekly scheduling, continuity, delivery, and retries.
Argus owns collection, rate limiting, filtering, scoring, classification, and
sparse event generation.

## Safety boundary

A discovered repository is untrusted input. `PLUGIN/SKILL` means "candidate for
review", not "install or execute". Never clone, install, import, or run a
repository automatically based only on stars, score, license, or classification.
