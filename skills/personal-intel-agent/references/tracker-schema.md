# Tracker Spec Schema

One YAML file per tracked entity at `trackers/<slug>.yaml`. The slug is a
lowercase, hyphenated entity id (e.g. `spacex`, `taylor-swift`, `gta-6-rumor`).

## Fields

```yaml
slug: spacex                # unique id, matches filename
entity: SpaceX              # display name
type: company               # company|person|team|rumor|niche|field
user_sentence: "Track SpaceX launches and tests; alert me on launch days."
signals:                    # what counts as "it moved" -> push fires
  - launches
  - tests
  - slips                 # schedule slips / delays
  - major contracts
noise:                     # dropped before folding
  - gossip
  - employee drama
  - stock-price hot-takes
cadence: instant            # instant|daily|weekly
verification: loose        # loose|strict (rumor tracks -> strict/verified-only)
sources:                    # discovered in TRACK step; >=10 entries
  - url: https://x.com/SpaceX
    type: official
    trust: primary
  - url: https://www.spacex.com/
    type: official
    trust: primary
  - url: https://www.reuters.com/space/
    type: newsroom
    trust: secondary
  - url: https://forum.nasaspaceflight.com/
    type: fan-forum
    trust: tertiary
delivery:                  # from MEMORY; default = feed (chat)
  - feed
  # - bot:loco-bot          # deliver into a local Hermes Bot profile's chat
  # - bot:senna             # (cron deliver: stays 'local'; skill step calls notify_bot.sh)
eval:                       # OPTIONAL — metric monitor / price tracker gate
  mode: diff                # diff|threshold  (omit for a news/topic tracker)
  trigger: pct              # threshold only: pct|abs
  value: 0.10               # threshold only: fraction (pct) or amount (abs)
  items:                   # which metrics gate (default: all). For threshold,
                           # list only numeric metrics (price/count).
    - lemonade_version
    - bugzilla_2445615
on_signal:                 # OPTIONAL — side-effects run ONLY when the gate passes
  - git_commit_push: "<repo-path> <commit-msg>"   # e.g. an hmem README update
metrics:                   # the watched values; READ step fills `current`
  - name: lemonade_version
    unit: version           # version|date|status|count|price
    source: "https://api.github.com/repos/lemonade-sdk/lemonade/releases?per_page=1"
    extract: "first release tag_name"
  - name: bugzilla_2445615
    unit: status
    source: "https://bugzilla.kernel.org/show_bug.cgi?id=2445615"
    extract: "open|closed"
created: 2026-08-18
last_tick: null
status: live               # live|paused
```

### `eval:` block shape

| Field | Meaning |
|---|---|
| `mode: diff` | Fire if **any** tracked metric's value changed vs last run. |
| `mode: threshold` | Fire only when a numeric delta crosses `trigger`. |
| `trigger: pct` + `value: 0.10` | `\|new−old\| / \|old\| >= 0.10` (e.g. a ≥10% price move). |
| `trigger: abs` + `value: 20` | `\|new−old\| >= 20` (e.g. a stock-count delta of 20+). |
| `items:` | Subset of metrics that gate the fire. For `threshold`, list **numeric only** (price/count); non-numeric items are ignored for the gate but still recorded for diff. Omit → all metrics gate. |

`metrics:` declares each watched value, its `unit`, where to read it (`source`),
and how to `extract` the scalar. Non-numeric units (`version`, `date`,
`status`) diff by string equality; numeric (`price`, `count`) feed the
threshold math. Full detail + report format: `references/diff-metrics.md`.

### `on_signal:` block (optional)

Side-effects that run **only when the gate passes** (a real movement). The only
supported action today is `git_commit_push`, which runs against the given repo
path with the given commit message. Never use it to commit state files
(`trackers/`, `archive/`, `state/`, `briefings/` under `INTEL_DIR`) — those
live off-repo and are gitignored. Example in
`references/converting-monitors-to-trackers.md`.

For a plain topic/company tracker (SpaceX, Taylor Swift) there is **no**
`eval:` block — the news FOLD/SIGNAL path handles it and the "move" is a
surviving folded card.

## Examples (showcased trackers)

**Taylor Swift — Tours & Releases** (person · music)
```yaml
slug: taylor-swift
entity: Taylor Swift
type: person
signals: [tours, album-drops, announcements]
noise: [clickbait, fan speculation]
cadence: instant
verification: loose
```

**Lakers — Trades & Injuries** (team · nba)
```yaml
slug: lakers
entity: Los Angeles Lakers
type: team
signals: [trades, injury-reports, deals]
noise: [hot-takes, rumors-unconfirmed]
cadence: instant
verification: strict
```

**GTA 6 — Release Watch** (rumor · gaming)
```yaml
yaml
slug: gta-6-rumor
entity: GTA 6
type: rumor
signals: [release-date, official-signal]
noise: [leaks, fakes, speculation]
cadence: instant
verification: strict     # verified only
```

**LEGO — Retiring Sets Watch** (niche · collecting)
```yaml
slug: lego-retiring
entity: LEGO retiring sets
type: niche
signals: [confirmed-retirements, clearance]
noise: [speculation]
cadence: weekly          # weekly brief
verification: strict
```

## Source type vocabulary
`official` · `newsroom` · `newsletter` · `podcast` · `blog` · `fan-forum` ·
`filings` · `papers` · `git-repo` · `retail` · `social`

## Trust tiers
- `primary` — the entity itself, regulators, filings (highest weight in SIGNAL)
- `secondary` — established newsrooms, wires, beat writers
- `tertiary` — fan media, blogs, forums (feed DISCOVER, not SIGNAL)
