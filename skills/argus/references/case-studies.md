# Case Studies

Real-world examples of Argus signal detection. These illustrate what "material
signal" means in practice and how the skill handles edge cases.

## Case Study 1: GLM-5.3 Pricing Rounds (2026-09-27)

**Event:** GLM-5.3 had two pricing rounds on the same day. Round 2 and Round 3
both went live.

**What happened:**
- Round 2 launched with a price of $X per 1M tokens.
- Round 3 launched 4 hours later with a price of $Y per 1M tokens.
- Both rounds were live simultaneously for a brief period.

**What Argus did:**
- Detected Round 2 as a price change (fired briefing).
- Detected Round 3 as a second price change (fired another briefing).
- Folded the two events into a single card with both price points.

**Key lesson:** Multiple signals in a short period should be folded into one card
when they're about the same entity, even if they're distinct events.

## Case Study 2: K3 Certification Reversal (2026-09-27)

**Event:** K3 was certified as "durable" but the certification was revoked after
69 minutes.

**What happened:**
- K3 was listed as "CERTIFIED DURABLE" at 10:00 AM.
- The certification was revoked at 11:09 AM (69 minutes later).
- The initial certification was a false signal.

**What Argus did:**
- Detected the certification as a status change (fired briefing).
- Detected the revocation as a second status change (fired another briefing).
- Tagged the second event as a "correction" of the first.

**Key lesson:** Reversals happen. Argus should detect and brief on both the initial
change and the correction, not just the initial change.

## Case Study 3: DeepSeek v4.1-flash Morph Deployment (2026-09-27)

**Event:** DeepSeek's v4.1-flash model had a variant called "Morph" that was
deployed at 17:53 but died (became unavailable) after 67 minutes.

**What happened:**
- Morph was deployed at 17:53.
- Morph became unavailable at 18:50 (67 minutes later).
- The deployment was a short-lived experiment.

**What Argus did:**
- Detected the deployment as a new model variant (fired briefing).
- Detected the removal as a service disruption (fired another briefing).
- Folded the two events into a single card with the timeline.

**Key lesson:** Short-lived deployments are still material signals. Argus should
detect and brief on both the deployment and the removal.

## Case Study 4: Oscillator Exemption (2026-09-28)

**Event:** A model's price oscillated between two values within 80 minutes.

**What happened:**
- Price changed from $X to $Y at 10:00 AM.
- Price changed back from $Y to $X at 11:20 AM (80 minutes later).
- The net change was zero, but there were two distinct price movements.

**What Argus did:**
- Detected the first change as a price movement (fired briefing).
- Detected the second change as a reversal (fired another briefing).
- Applied the "oscillator exemption" rule: if the price returns to the original
  value within 80 minutes, the second event is tagged as an "oscillator" and
  the briefing is suppressed.

**Key lesson:** Not every price movement is a material signal. The oscillator
exemption prevents notification overload from rapid back-and-forth changes.

## Case Study 5: Era Certification (2026-09-28)

**Event:** A model's pricing entered a new "era" with a fundamentally different
pricing structure.

**What happened:**
- The model had been priced at $X per 1M tokens for months.
- A new pricing structure was introduced at $Y per 1M tokens (50% reduction).
- The new pricing was certified as "durable" and remained in effect.

**What Argus did:**
- Detected the price change as a material signal (fired briefing).
- Tagged the change as an "era certification" because the new price remained
  stable for an extended period.
- Subsequent price changes within the same era were compared against the
  certified baseline, not the previous price.

**Key lesson:** Some price changes are more significant than others. Era
certification distinguishes between temporary fluctuations and permanent shifts.

## When to Use These Case Studies

- **Onboarding:** Read these to understand what "material signal" means in practice.
- **Troubleshooting:** Compare your situation to these examples to identify the issue.
- **Testing:** Use these as test cases for your own Argus trackers.
- **Calibration:** Use these to calibrate your thresholds and noise rules.
