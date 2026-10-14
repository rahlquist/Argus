#!/usr/bin/env python3
"""fold.py — collapse duplicate news coverage into one card (the SIGNAL step).

Reads JSONL rows from stdin, one per collected item:
    {"title": str, "url": str, "source": str, "published": str,
     "snippet": str, "kind": str, "trust": "primary|secondary|tertiary"}

Clusters rows by cosine similarity over word-level TF-IDF vectors using
greedy single-linkage at --sim threshold (default 0.6).

Emits one card per cluster to stdout as JSONL:
    {"canonical": {...row...}, "members": [...rows...], "source_count": N}

Noise-filtered rejects (rows whose kind/title match --noise regexes) are
written to stderr as JSONL with a "reject_reason".

No third-party dependencies (stdlib only).

Usage:
    python fold.py [--sim 0.6] [--noise gossip] [--noise clickbait] [--self-test]
"""

import json
import math
import os
import re
import sys
from pathlib import Path


def tokenize(text):
    """Word-level tokens (lowercased). Word shingles beat char-trigrams for
    news near-duplicate detection, where shared headline words are the signal."""
    return re.findall(r"[a-z0-9]+", text.lower())


def tfidf_vectors(rows):
    """Return list of sparse tf-idf vectors (dict term->weight) + idf."""
    docs = [tokenize((r.get("title", "") + " " + r.get("snippet", ""))) for r in rows]
    df = {}
    for grams in docs:
        for term in set(grams):
            df[term] = df.get(term, 0) + 1
    n = len(docs)
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    vecs = []
    for grams in docs:
        tf = {}
        for g in grams:
            tf[g] = tf.get(g, 0) + 1
        total = len(grams)
        vec = {t: (c / total) * idf[t] for t, c in tf.items() if t in idf}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vecs.append({t: v / norm for t, v in vec.items()})
    return vecs


def cosine(a, b):
    if not a or not b:
        return 0.0
    # iterate the shorter vector
    if len(a) > len(b):
        a, b = b, a
    dot = sum(w * b.get(t, 0.0) for t, w in a.items())
    return dot  # both pre-normalized -> dot == cosine


def cluster_indices(rows, sim):
    """Greedy single-linkage cluster indices at ``sim`` (indices, not rows).

    Index-based so labeled fixtures can map labels back to members even when
    two rows are byte-identical.
    """
    return _cluster_indices(tfidf_vectors(rows), sim)


def _cluster_indices(vecs, sim):
    clusters = []  # list of member index lists
    for i, vec in enumerate(vecs):
        best = -1.0
        best_c = None
        for ci, cidx in enumerate(clusters):
            # single-linkage: max over members
            s = max(cosine(vec, vecs[j]) for j in cidx)
            if s > best:
                best = s
                best_c = ci
        if best_c is not None and best >= sim:
            clusters[best_c].append(i)
        else:
            clusters.append([i])
    return clusters


def fold(rows, sim, noise_re):
    clusters = cluster_indices(rows, sim)

    cards = []
    for cidx in clusters:
        members = [rows[i] for i in cidx]
        # canonical = highest trust tier, then longest snippet
        trust_rank = {"primary": 3, "secondary": 2, "tertiary": 1}
        canonical = sorted(
            members,
            key=lambda r: (trust_rank.get(r.get("trust", "tertiary"), 0),
                           len(r.get("snippet", ""))),
            reverse=True,
        )[0]
        cards.append({
            "canonical": canonical,
            "members": members,
            "source_count": len({m.get("source") for m in members}),
        })
    return cards


DEFAULT_SWEEP = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
LABELS = ("same", "different")


def default_fixtures_path():
    """Ship the starter fixture set next to the script."""
    return Path(__file__).resolve().parent.parent / "assets" / "fold-labels.jsonl"


def load_cases(path):
    """Load labeled fold fixtures; ``_meta`` lines are skipped.

    Each case: ``{"id": str, "rows": [...], "labels": [[i, j, "same"|"different"]]}``
    """
    cases = []
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if "_meta" in case:
            continue
        rows = case.get("rows")
        labels = case.get("labels")
        if not isinstance(rows, list) or len(rows) < 2:
            raise ValueError(f"{path}:{lineno}: case needs at least 2 rows")
        if not isinstance(labels, list):
            raise ValueError(f"{path}:{lineno}: case needs a labels list")
        for label in labels:
            if not isinstance(label, list) or len(label) != 3:
                raise ValueError(f"{path}:{lineno}: label must be [i, j, 'same'|'different']")
            i, j, kind = label
            if not isinstance(i, int) or not isinstance(j, int):
                raise ValueError(f"{path}:{lineno}: label indices must be integers")
            if not (0 <= i < len(rows)) or not (0 <= j < len(rows)):
                raise ValueError(f"{path}:{lineno}: label index out of range for {len(rows)} rows")
            if kind not in LABELS:
                raise ValueError(f"{path}:{lineno}: label must be 'same' or 'different', got {kind!r}")
        cases.append({"id": case.get("id") or f"case-{lineno}", "rows": rows, "labels": labels})
    return cases


def score_threshold(cases, sim):
    """Precision/recall of the clustering at one threshold, over labeled pairs."""
    tp = fp = fn = tn = 0
    for case in cases:
        rows = case["rows"]
        clusters = cluster_indices(rows, sim)
        where = {}
        for ci, members in enumerate(clusters):
            for idx in members:
                where[idx] = ci
        for i, j, kind in case["labels"]:
            merged = where.get(i) == where.get(j)
            if kind == "same":
                tp += 1 if merged else 0
                fn += 0 if merged else 1
            else:
                fp += 1 if merged else 0
                tn += 0 if merged else 1
    pairs = tp + fp + fn + tn
    precision = (tp / (tp + fp)) if (tp + fp) else None
    recall = (tp / (tp + fn)) if (tp + fn) else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall):
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "sim": round(float(sim), 4),
        "pairs": pairs,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
    }


def eval_table(cases, sims=None):
    sims = list(sims) if sims else list(DEFAULT_SWEEP)
    rows = [score_threshold(cases, s) for s in sims]
    best = max(rows, key=lambda r: (r["f1"] or 0.0, r["precision"] or 0.0)) if rows else None
    return {"rows": rows, "best": best, "cases": len(cases)}


def _fmt(value):
    return "n/a" if value is None else f"{value:.2f}"


def render_eval_table(table):
    lines = [
        f"fold threshold sweep — {table['cases']} labeled case(s)",
        "",
        "| --sim | TP | FP | FN | TN | precision | recall | F1 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in table["rows"]:
        marker = " *" if table["best"] and r["sim"] == table["best"]["sim"] else ""
        lines.append(
            f"| {r['sim']:.2f}{marker} | {r['tp']} | {r['fp']} | {r['fn']} | {r['tn']} "
            f"| {_fmt(r['precision'])} | {_fmt(r['recall'])} | {_fmt(r['f1'])} |"
        )
    if table["best"]:
        b = table["best"]
        lines += [
            "",
            f"best F1 at --sim {b['sim']:.2f} "
            f"(precision {_fmt(b['precision'])}, recall {_fmt(b['recall'])})",
            "",
            "n/a means the labeled pairs at that threshold could not define the metric. "
            "False merges hide signals; false splits only add noise — if you must trade, "
            "trade recall for precision.",
        ]
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    sim = 0.6
    noise_terms = []
    self_test = False
    eval_mode = False
    fixtures = None
    sweep = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--sim":
            sim = float(args[i + 1]); i += 2; continue
        if a == "--noise":
            noise_terms.append(args[i + 1]); i += 2; continue
        if a == "--eval":
            eval_mode = True; i += 1; continue
        if a == "--fixtures":
            fixtures = args[i + 1]; i += 2; continue
        if a == "--sweep":
            sweep = [float(x) for x in args[i + 1].split(",") if x.strip()]; i += 2; continue
        if a == "--self-test":
            self_test = True; i += 1; continue
        i += 1

    if self_test:
        run_self_test()
        return

    if eval_mode:
        path = Path(fixtures) if fixtures else default_fixtures_path()
        if not path.exists():
            print(f"fold --eval: no fixtures at {path}", file=sys.stderr)
            sys.exit(2)
        cases = load_cases(path)
        if not cases:
            print(f"fold --eval: {path} contains no labeled cases", file=sys.stderr)
            sys.exit(2)
        print(render_eval_table(eval_table(cases, sweep)))
        return

    noise_re = re.compile("|".join(re.escape(t) for t in noise_terms), re.I) if noise_terms else None

    rows = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    kept, rejected = [], []
    for r in rows:
        if noise_re and (noise_re.search(r.get("title", "")) or noise_re.search(r.get("snippet", ""))):
            rejected.append({"row": r, "reject_reason": "noise-match"})
        else:
            kept.append(r)

    cards = fold(kept, sim, noise_re)
    for c in cards:
        print(json.dumps(c, ensure_ascii=False))
    for rej in rejected:
        print(json.dumps(rej, ensure_ascii=False), file=sys.stderr)


def run_self_test():
    fixture = [
        {"title": "SpaceX launches Starship on third test flight",
         "url": "https://a.example/1", "source": "Reuters", "snippet": "Starship lifted off from Boca Chica", "trust": "secondary"},
        {"title": "Starship test flight 3 launches successfully from Texas",
         "url": "https://b.example/2", "source": "SpaceNews", "snippet": "The Starship vehicle launched on its third flight", "trust": "secondary"},
        {"title": "SpaceX Starship third flight lifts off",
         "url": "https://c.example/3", "source": "NASA", "snippet": "Starship launched for the third time", "trust": "primary"},
        {"title": "Taylor Swift announces new album drop",
         "url": "https://d.example/4", "source": "Billboard", "snippet": "Taylor Swift revealed a surprise album", "trust": "secondary"},
        {"title": "CLICKBAIT you won't BELIEVE what the celebrity did",
         "url": "https://e.example/5", "source": "Gossip", "snippet": "shocking celebrity drama", "trust": "tertiary"},
    ]
    noise_re = re.compile(r"clickbait|gossip", re.I)
    kept = [r for r in fixture if not (noise_re.search(r["title"]) or noise_re.search(r["snippet"]))]
    cards = fold(kept, 0.4, noise_re)
    spacex = [c for c in cards if any("Starship" in m["title"] or "SpaceX" in m["title"] for m in c["members"])]
    assert len(spacex) == 1, f"expected 1 SpaceX cluster, got {len(spacex)}"
    assert spacex[0]["source_count"] == 3, f"expected 3 SpaceX members, got {spacex[0]['source_count']}"
    assert spacex[0]["canonical"]["trust"] == "primary", "canonical should be the primary source"
    assert len(cards) == 2, f"expected 2 clusters total (SpaceX + Taylor), got {len(cards)}"
    print("self-test OK: 3 SpaceX items folded into 1 card, clickbait rejected, canonical=primary")

    # --eval scoring: similar-but-different items must show up as false merges
    case = {
        "id": "selftest",
        "rows": [
            {"title": "GIGABYTE X870E AORUS PRO X3D ICE AM5 LGA 1718 ATX Motherboard",
             "snippet": "339.99 free shipping at Amazon"},
            {"title": "GIGABYTE X870E AORUS MASTER X3D ICE AM5 AMD X870E ATX Motherboard",
             "snippet": "549.99 with liquid cooler bundle"},
            {"title": "X870E Aorus Pro X3D ICE motherboard drops to 339.99",
             "snippet": "AM5 LGA 1718 ATX board on sale"},
            {"title": "Council approves new parking meter contract downtown",
             "snippet": "the city council voted on parking meter maintenance"},
        ],
        "labels": [[0, 2, "same"], [0, 1, "different"], [1, 2, "different"],
                   [0, 3, "different"], [1, 3, "different"]],
    }
    loose = score_threshold([case], 0.05)
    tight = score_threshold([case], 0.95)
    assert loose["tp"] == 1, loose
    assert loose["fp"] == 2, loose          # the two near-identical boards merged
    assert loose["recall"] == 1.0, loose
    assert tight["tp"] == 0 and tight["fn"] == 1, tight
    table = eval_table([case], [0.05, 0.4, 0.95])
    assert len(table["rows"]) == 3
    assert table["best"] is not None
    assert "precision" in render_eval_table(table)
    print("self-test OK: --eval scoring (loose over-merges, tight splits, table renders)")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # downstream (e.g. `head`) closed early; exit quietly
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(0)
