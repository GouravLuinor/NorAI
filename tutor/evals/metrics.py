"""
metrics.py — Pure retrieval-eval metrics for the P3.1 golden-QA suite.

Deliberately free of Chroma / Gemini imports so tests can run fully offline.
All functions are pure: they take dicts shaped like Retriever.retrieve() output
    {"text", "heading", "heading_path", "chapter_id", "source", "distance"}
and the gold-section fragments from a golden set.
"""

from __future__ import annotations

GOLD_HIT_BOUNDARY = 1e9


def chunk_matches(chunk: dict, gold_fragments: list[str]) -> bool:
    """
    True if any gold fragment is a case-insensitive substring of the chunk's
    heading_path OR equals its leaf heading. Fragments are deliberately short
    ("AI as a Sounding Board") so they survive full heading paths.
    """
    heading_path = (chunk.get("heading_path") or "").lower()
    heading = (chunk.get("heading") or "").lower()
    haystack = f"{heading_path} || {heading}"
    for frag in gold_fragments:
        if frag.lower() in haystack:
            return True
    return False


def first_gold_rank(retrieved: list[dict], gold_fragments: list[str]) -> int:
    """1-based rank of the first gold hit in `retrieved`, or 0 if none."""
    for i, chunk in enumerate(retrieved, 1):
        if chunk_matches(chunk, gold_fragments):
            return i
    return 0


def mrr(ranks: list[int]) -> float:
    """Mean reciprocal rank. Pass one 1-based first-hit rank per question
    (0 for questions with no gold hit)."""
    if not ranks:
        return 0.0
    return round(sum(1.0 / r for r in ranks if r > 0) / len(ranks), 4)


def hit_rate(hits: list[bool]) -> float:
    if not hits:
        return 0.0
    return round(sum(1 if h else 0 for h in hits) / len(hits), 4)


def is_strong(chunk: dict, threshold: float) -> bool:
    """A chunk is a 'strong' match (reference-worthy) when its cosine distance
    is at or below the confidence threshold. Missing distance = weak."""
    d = chunk.get("distance")
    if d is None:
        return False
    return d <= threshold


def evaluate_questions(
    questions: list[dict],
    top_k: int,
    threshold: float,
) -> dict:
    """
    Aggregate MRR / hit-rate@k / distance stats / reference-gate stats for a
    list of question dicts:
        {"q": str, "retrieved": [chunk...], "gold": [fragment...]}

    Returns a flat dict of summary numbers:
        questions, top_k, mrr, hit_rate,
        mean_hit_distance, mean_miss_distance,
        mean_strong_count, zero_strong_fraction,
        strong_precision, gold_strong_recall
    """
    ranks = []
    hits = []
    hit_dists: list[float] = []
    miss_dists: list[float] = []
    strong_counts = []
    strong_total = 0
    strong_gold = 0
    gold_strong = 0

    for q in questions:
        retrieved = q.get("retrieved", [])[:top_k]
        gold = q.get("gold", [])

        rank = first_gold_rank(retrieved, gold)
        ranks.append(rank)
        hits.append(rank > 0)

        strong = [c for c in retrieved if is_strong(c, threshold)]
        strong_counts.append(len(strong))
        strong_total += len(strong)
        strong_gold += sum(1 for c in strong if chunk_matches(c, gold))

        any_gold = any(chunk_matches(c, gold) for c in retrieved)
        if any_gold:
            if any(is_strong(c, threshold) and chunk_matches(c, gold) for c in strong):
                gold_strong += 1

        for c in retrieved:
            d = c.get("distance")
            if d is None:
                continue
            if chunk_matches(c, gold):
                hit_dists.append(d)
            else:
                miss_dists.append(d)

    n = len(questions)
    return {
        "questions": n,
        "top_k": top_k,
        "threshold": threshold,
        "mrr": round(mrr(ranks), 4),
        "hit_rate": round(hit_rate(hits), 4),
        "mean_hit_distance": round(sum(hit_dists) / len(hit_dists), 4) if hit_dists else None,
        "mean_miss_distance": round(sum(miss_dists) / len(miss_dists), 4) if miss_dists else None,
        "mean_strong_count": round(sum(strong_counts) / n, 3) if n else 0.0,
        "zero_strong_fraction": round(sum(1 for c in strong_counts if c == 0) / n, 3) if n else 0.0,
        "strong_precision": round(strong_gold / strong_total, 4) if strong_total else None,
        "gold_strong_recall": round(gold_strong / n, 4) if n else None,
    }


def threshold_sweep(questions: list[dict], top_k: int, thresholds: list[float]) -> list[dict]:
    """
    Run evaluate_questions across a range of confidence thresholds and pick the
    threshold with the best F1 of (strong_precision, gold_strong_recall).
    Returns (rows, recommended_threshold).
    """
    rows = []
    best = None
    for t in thresholds:
        s = evaluate_questions(questions, top_k, t)
        p = s["strong_precision"]
        r = s["gold_strong_recall"]
        if p is not None and r is not None and (p + r) > 0:
            f1 = 2 * p * r / (p + r)
        else:
            f1 = 0.0
        s["f1"] = round(f1, 4)
        rows.append(s)
        if best is None or f1 > best[1]:
            best = (t, f1)
    return rows, best[0] if best else thresholds[len(thresholds) // 2]
