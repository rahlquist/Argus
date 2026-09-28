# Briefing Template

Argus produces two briefing formats depending on the delivery target:

- **Markdown** — for bot-chat delivery (the primary format).
- **RSS 2.0** — for feed delivery (when the user wants a persistent feed).

## Markdown Format (Bot-Chat Delivery)

### News Card

```markdown
## <HEADLINE>

**Folded from <N> sources** · <date> · confidence: <high|medium|low>

**What happened**
- <fact 1, sourced>
- <fact 2, sourced>
- <fact 3, sourced>

**Why it matters**
- <tie to the user's interest / signal class>

**Sources** (all attached, deduped)
- [<outlet>](<url>) — <primary|secondary|tertiary>
- ...

**Verification**  (omit if cadence loose)
- <official confirmation / contradictory reports>
```

### Metric/Price Card

```markdown
# <entity> — watch update

## CHANGED
- <metric>: <old> → <new>  (<unit>)  [source](url)
  <why it matters — 1-2 sentences>

## UNCHANGED
- <metric>: <value> (no change)

Overall: <N> changed, <M> unchanged.
```

### Rules

- Lead with what moved; roll up what didn't.
- No padding on a silent tick — produce no substantive content.
- Every claim must have a source URL.
- "Beyond radar" items are labeled and tied to a stated interest.
- For metric trackers, CHANGED lines carry the delta:
  ```
  - Price: $99.99 → $89.99  (−10.0%, −$10.00)  (price)
  ```

## RSS 2.0 Format (Feed Delivery)

Each emitted card also appends an `<item>` to `briefings/feed.xml`:

```xml
<item>
  <title><HEADLINE></title>
  <link><canonical url></link>
  <pubDate><RFC822 date></pubDate>
  <description><folded-from N sources; why it matters></description>
</item>
```

The file is a minimal valid RSS 2.0 document; create it with a skeleton
`<channel>` on first write, then append items inside `<channel>`.

## Confidence Rubric

| Level | Criteria |
|---|---|
| **High** | 2+ independent primary sources, or 1 primary + 2 secondary |
| **Medium** | 1 primary source, or 2+ secondary sources |
| **Low** | 1 secondary source, or tertiary source with strong interest match |
| **Speculative** | Tertiary source only; label as "beyond radar" |

Strict rumor tracks suppress anything that doesn't reach **high**.

## Anti-Fabrication Rule

Never invent a `value`, `url`, or delta. If a source API fails, mark the
metric `value: <error>` and say so in the report; do not silently carry the
old value forward as if unchanged without noting the fetch failure.
