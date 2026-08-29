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


def fold(rows, sim, noise_re):
    vecs = tfidf_vectors(rows)
    clusters = []  # list of (member_indices)
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


def main():
    args = sys.argv[1:]
    sim = 0.6
    noise_terms = []
    self_test = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--sim":
            sim = float(args[i + 1]); i += 2; continue
        if a == "--noise":
            noise_terms.append(args[i + 1]); i += 2; continue
        if a == "--self-test":
            self_test = True; i += 1; continue
        i += 1

    if self_test:
        run_self_test()
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


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # downstream (e.g. `head`) closed early; exit quietly
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(0)
