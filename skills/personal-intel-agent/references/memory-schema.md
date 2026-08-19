# Memory Schema — the open user model

`memory.md` is the persistent, editable record of what Zetik would call
"everything it learns about you, out in the open." Every preference carries
**provenance** (`said` = user told us directly; `learned` = inferred from
behavior) and a date. Nothing is hidden; the user can edit or delete any line.

## Format

```markdown
# Intel Memory

## Preferences
- less celebrity coverage            # said · 2026-08-18
- more open-source AI                # said · 2026-08-18
- no hot takes                       # said · 2026-08-18
- prefers primary sources            # learned · 2026-08-12
- skips celebrity news               # learned · 2026-08-12

## Interests (drive DISCOVER)
- solid-state batteries              # from tracker lego? no — tracked topic · 2026-08-12
- open-source AI models

## Source trust overrides
- bloomberg: promoted to primary     # said · 2026-08-18

## Delivery defaults
- feed: on
- morning_push: on
- newsletter: off
- rss: off
- audio: off

## Feedback log
- 2026-08-18 "less celebrity coverage" -> demoted tertiary celebrity sources
```

## Rules
- Plain-language lines only. The agent parses the `# said · DATE` / `# learned · DATE`
  suffix; anything without it defaults to `said`.
- On any user correction, append a line AND a feedback-log entry immediately.
- `Interests` is what powers Branch B step 7 (DISCOVER): run adjacent searches
  seeded from these, not from the tracked entities.
- Trust overrides reweight `fold.py` clustering and SIGNAL source ranking next tick.
