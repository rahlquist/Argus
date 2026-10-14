# Scratch — Undirected Tracker Proposals

DISCOVER is **directed**: it is seeded from interests you already track, so it
can only return more of what you already have. Scratch is the opposite. It runs
deliberately undirected searches and proposes **new trackers** — as reviewable
drafts, never as briefings.

The distinction in one line:

> DISCOVER says *"FastFlowLM released v1.0.6."*
> Scratch says *"four people published FastFlowLM-on-Krackan benchmarks this
> month — want a tracker for the next one?"*

The agent does the searching (that is judgment work). `scripts/argus_scratch.py`
owns the deterministic parts: scoring, dedupe against what you already track,
capping, expiry, decisions, and the tracker spec skeleton.

## Procedure

1. Read interests from Hermes persistent memory. Read the existing tracker
   slugs so proposals cannot duplicate live watches.
2. Run 3–5 **undirected** searches. They must not name anything you already
   track — otherwise this is DISCOVER with extra steps. Good shapes:
   - a *category* rather than an entity (`MCP server observability`)
   - a *method* rather than a story (`agent memory benchmark methodology`)
   - an ecosystem question (`"hermes plugin" OR "hermes skill" github 2026`)
3. Group hits into candidate themes and pass them to the script:

   ```bash
   argus_scratch.py propose --max 3 < candidates.json
   ```

   ```json
   {"existing": ["motherboard-sales", "nous-llm-deals"],
    "candidates": [
      {"theme": "mcp-observability-tooling",
       "interest": "multi-profile fleet management",
       "why": "3 of 9 hits connect to fleet management; you run 20+ MCP servers",
       "hits": [{"title": "...", "url": "...", "source": "..."}]}]}
   ```

4. Return the rendered proposal cards as the job's output. The user accepts or
   rejects with one command.

## Rules

- **Nothing is created automatically.** An accepted tracker is a permanent token
  cost, so acceptance is always an explicit human act.
- **Cap at 3 proposals per run** (`--max`). Extras are reported as deferred.
- **Expire unaccepted proposals after 30 days** (`--days`).
- **Dedupe against live trackers.** A theme matching an existing slug is skipped.
- **Idempotent.** Re-proposing the same theme returns the same proposal id and
  never appends a duplicate record.

## Lifecycle

```bash
argus_scratch.py propose --max 3 < candidates.json   # JSON on stdin
argus_scratch.py list                                # pending, unexpired
argus_scratch.py accept <id>                         # emits a tracker spec skeleton
argus_scratch.py reject <id>
argus_scratch.py expire --days 30
```

Store: `$ARGUS_SCRATCH_STORE` or `~/.intel/state/scratch/proposals.jsonl`.
Append-only — each decision appends a record and the latest record per id wins.

`accept` prints a YAML skeleton to review and finish: it has the slug, entity,
signal classes, cadence, and whatever source URLs the hits provided. It is a
draft, not a finished tracker spec.

## Failure mode

It proposes things you don't care about. That is the accepted cost — the output
is a draft you can dismiss with one word, and unaccepted drafts expire on their
own. The failure to avoid is the opposite one: auto-creating trackers, which
turns a passing curiosity into a permanent recurring cost.

## Cron job

Weekly, and it must not overlap the watches themselves:

```yaml
name: argus scratch — tracker proposals
schedule: "0 10 * * 6"          # Saturday, an hour after the weekly rollup
skills: [argus]
deliver: bot-chat:<profile>
workdir: /absolute/path/to/.intel
continuity: false
```
