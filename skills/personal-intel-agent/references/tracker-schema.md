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
created: 2026-08-18
last_tick: null
status: live               # live|paused
```

## Examples (from Zetik's own showcased trackers)

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
