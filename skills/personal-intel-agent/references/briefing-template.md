# Briefing Card Template (SIGNAL output)

One card per folded cluster. This is the folded "card" unit: what
happened, why it matters, every source attached.

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

## RSS addendum (`briefings/feed.xml`)
Each emitted card also appends an `<item>`:
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

## Confidence rubric
- **high** — primary/official source + ≥3 independent confirmations.
- **medium** — secondary newsrooms, no contradiction.
- **low** — single tertiary source, or rumor-track (strict tracks suppress
  anything that doesn't reach *high*).
