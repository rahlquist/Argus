# Hermes Persistent Memory for Argus

Argus uses Hermes's normal persistent memory—MEMORY.md/USER.md loaded by cron
and the `memory` tool—not a private state-directory `memory.md` file. This
keeps preferences shared across CLI, Desktop, messaging, Bot Mode, and cron
runs, with one visible/editable source of truth.

## What belongs in Hermes memory

Store compact declarative facts:

- Preferences: `User prefers primary sources over commentary.`
- Noise policy: `User does not want celebrity gossip or hot takes.`
- Interests used by DISCOVER: `User follows open-source AI and solid-state batteries.`
- Source trust overrides: `User considers Example Wire reliable for launch reporting.`
- Delivery defaults: `User prefers morning Argus briefings in the research bot chat.`

Do not store raw article archives, tracker progress, execution logs, or temporary
TODO state in persistent memory. Those belong in `archive/`, `state/`, cron's
execution ledger, or session history.

## Update rules

- User-stated preferences outrank inferred preferences.
- Update memory immediately when the user corrects source weighting, topic
  scope, cadence, or noise policy.
- Use declarative facts, not instructions that could override a future request.
- Consolidate stale/duplicate entries when the memory budget is tight.
- Tracker-specific cursors and watermarks may use cron's bounded per-job
  notepad; they are not user-profile facts.

## Migration from pre-v0.21 Argus

Legacy Personal Intelligence Agent installations may have
`${INTEL_DIR}/memory.md` with sections for Preferences, Interests, Source trust
overrides, Delivery defaults, and Feedback log.

Migrate once:

1. Read the legacy file without altering it.
2. Convert durable preferences/interests/trust overrides into compact Hermes
   memory entries using one batched `memory` tool call.
3. Do not migrate transient feedback logs or historical run details.
4. Rename the legacy file to `memory.md.migrated` only after reading back the
   resulting memory entries and confirming the durable facts are present.

The archived file is provenance only. Future Argus runs must read and update
Hermes memory, not the migrated file.
