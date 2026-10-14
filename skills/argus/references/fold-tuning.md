# Fold Threshold Tuning

`fold.py` decides whether two collected items become **one card or two** based
on a single number: the cosine-similarity threshold `--sim`. That number is
load-bearing, and until now it was a guess.

Too low → unrelated items merge, and a merge **hides a signal**.
Too high → the same story from ten outlets produces ten cards, which is the
flood Argus exists to prevent.

## Measuring it

```bash
python3 scripts/fold.py --eval                          # shipped starter fixtures
python3 scripts/fold.py --eval --fixtures my.jsonl
python3 scripts/fold.py --eval --sweep 0.15,0.2,0.25,0.3
```

Output is a precision/recall table per threshold:

```
fold threshold sweep — 8 labeled case(s)

| --sim | TP | FP | FN | TN | precision | recall | F1 |
|---|---|---|---|---|---|---|---|
| 0.20 * | 6 | 1 | 1 | 16 | 0.86 | 0.86 | 0.86 |
| 0.40 | 2 | 1 | 5 | 16 | 0.67 | 0.29 | 0.40 |
| 0.60 | 0 | 0 | 7 | 17 | n/a | 0.00 | n/a |
```

`n/a` means the labeled pairs at that threshold could not define the metric —
it is *undefined*, not zero. A threshold that folds nothing has no positive
predictions to be precise about.

## Fixture format

One JSON object per line. A `_meta` line is allowed and skipped.

```json
{"_meta": {"purpose": "..."}}
{"id": "docker-snap-compat",
 "rows": [{"title": "...", "snippet": "...", "source": "...", "trust": "secondary"}],
 "labels": [[0, 1, "same"], [0, 2, "different"], [1, 2, "different"]]}
```

`labels` are pairwise judgments over indices in `rows`. Pairs you do not label
are ignored entirely — you do not have to label every pair, and unlabeled merges
are neither rewarded nor penalised.

Labeling conventions that make the table meaningful:

- A fix and its test are the **same** change.
- Two unrelated subsystems are **different**.
- Distinct releases of one project are **different** cards.
- Near-identical product titles for **different** SKUs are **different** — this
  is the over-merge trap, and it is the most valuable case to include.

## Choosing a threshold

False merges hide signals; false splits only add noise. If you must trade, trade
recall for precision — a duplicate card is annoying, a swallowed signal is the
failure the whole system exists to prevent.

## Current measurement

The shipped starter set (`assets/fold-labels.jsonl`, 8 cases / 24 labeled pairs,
built from real archived rows) says:

| `--sim` | precision | recall | F1 |
|---|---|---|---|
| 0.20 | 0.86 | 0.86 | **0.86** |
| 0.30 | 0.80 | 0.57 | 0.67 |
| 0.40 | 0.67 | 0.29 | 0.40 |
| 0.60 | n/a | 0.00 | n/a |

**The live cron prompts pass `--sim 0.4`, and `fold.py`'s own default is 0.6.**
On this fixture set those split most true duplicates — 0.6 folds nothing at all.

Caveat, stated plainly: the starter labels are an **agent-labeled, unreviewed**
set, and several "same" pairs are commit/fix pairs that are harder than typical
news near-duplicates. Treat the table as directional evidence, not a verdict.
Review the labels before changing production thresholds — then change them.

## Adding fixtures

The fixture set is the artifact; grow it from your own archives when a briefing
looks wrong:

1. When a card merges two things that were actually different, or splits one
   story into several, copy those rows into a new case.
2. Label the pairs.
3. Re-run `--eval` and see whether the threshold that would have avoided it is
   also good elsewhere.

The set doubles as a regression test: change the tokenizer or the similarity
function and the table immediately shows whether folding improved.
