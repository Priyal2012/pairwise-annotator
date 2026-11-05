"""Inter-annotator agreement statistics for nominal labels.

All functions are pure and operate on plain Python containers so they can be
unit-tested against textbook examples and reused outside the web app.

* :func:`percent_agreement` — share of items where two raters gave the same label
* :func:`cohen_kappa`       — chance-corrected agreement for exactly two raters
* :func:`fleiss_kappa`      — chance-corrected agreement for any number of raters
* :func:`pairwise_kappas`   — Cohen's κ for every pair of raters on shared items

Interpretation (Landis & Koch, 1977): < 0 poor, 0–0.2 slight, 0.21–0.4 fair,
0.41–0.6 moderate, 0.61–0.8 substantial, 0.81–1 almost perfect.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Hashable, Iterable, Mapping, Sequence
from itertools import combinations

Label = Hashable


def percent_agreement(a: Sequence[Label], b: Sequence[Label]) -> float:
    """Fraction of positions where ``a`` and ``b`` hold the same label."""
    if len(a) != len(b):
        raise ValueError("label sequences must have the same length")
    if not a:
        raise ValueError("no items to compare")
    return sum(x == y for x, y in zip(a, b, strict=True)) / len(a)


def cohen_kappa(a: Sequence[Label], b: Sequence[Label]) -> float:
    """Cohen's κ between two raters who labelled the same items in the same order.

    Returns 1.0 when both raters agree on every item and only ever use one
    label (expected agreement is then also 1, which would otherwise divide by 0).
    """
    if len(a) != len(b):
        raise ValueError("label sequences must have the same length")
    n = len(a)
    if n == 0:
        raise ValueError("no items to compare")
    observed = percent_agreement(a, b)
    counts_a, counts_b = Counter(a), Counter(b)
    expected = sum(counts_a[label] * counts_b[label] for label in set(a) | set(b)) / (n * n)
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected)


def fleiss_kappa(matrix: Sequence[Sequence[int]]) -> float:
    """Fleiss' κ from an items × categories matrix of rating counts.

    Every row must sum to the same number of raters ``n`` (≥ 2).
    """
    if not matrix:
        raise ValueError("matrix is empty")
    n_per_row = {sum(row) for row in matrix}
    if len(n_per_row) != 1:
        raise ValueError(f"all items must have the same number of ratings, got {sorted(n_per_row)}")
    n = n_per_row.pop()
    if n < 2:
        raise ValueError("Fleiss' kappa needs at least two ratings per item")
    n_items = len(matrix)
    n_cats = len(matrix[0])

    p_j = [sum(row[j] for row in matrix) / (n_items * n) for j in range(n_cats)]
    p_i = [(sum(c * c for c in row) - n) / (n * (n - 1)) for row in matrix]
    p_bar = sum(p_i) / n_items
    p_e = sum(p * p for p in p_j)
    if p_e == 1.0:
        return 1.0
    return (p_bar - p_e) / (1.0 - p_e)


def interpret_kappa(kappa: float) -> str:
    """Landis & Koch verbal scale."""
    if kappa < 0:
        return "poor"
    bands = [(0.20, "slight"), (0.40, "fair"), (0.60, "moderate"), (0.80, "substantial")]
    for upper, name in bands:
        if kappa <= upper:
            return name
    return "almost perfect"


# ---------------------------------------------------------------------------
# helpers that work on annotation records
# ---------------------------------------------------------------------------


def labels_by_rater(records: Iterable[Mapping]) -> dict[str, dict[str, Label]]:
    """``{annotator: {item_id: label}}`` from records with those three keys.

    Later records for the same (annotator, item) overwrite earlier ones, so a
    re-annotation counts once.
    """
    out: dict[str, dict[str, Label]] = defaultdict(dict)
    for r in records:
        out[r["annotator"]][r["item_id"]] = r["label"]
    return dict(out)


def pairwise_kappas(by_rater: Mapping[str, Mapping[str, Label]], *, min_shared: int = 2) -> list[dict]:
    """Cohen's κ and agreement for every pair of raters on the items they both labelled."""
    results = []
    for r1, r2 in combinations(sorted(by_rater), 2):
        shared = sorted(set(by_rater[r1]) & set(by_rater[r2]))
        if len(shared) < min_shared:
            continue
        a = [by_rater[r1][i] for i in shared]
        b = [by_rater[r2][i] for i in shared]
        k = cohen_kappa(a, b)
        results.append(
            {
                "raters": [r1, r2],
                "shared_items": len(shared),
                "percent_agreement": round(percent_agreement(a, b), 4),
                "cohen_kappa": round(k, 4),
                "interpretation": interpret_kappa(k),
            }
        )
    return results


def fleiss_from_labels(by_rater: Mapping[str, Mapping[str, Label]], categories: Sequence[Label]) -> dict | None:
    """Fleiss' κ over the items that *every* rater labelled (None if fewer than 2 such items)."""
    raters = list(by_rater)
    if len(raters) < 2:
        return None
    common = set.intersection(*(set(by_rater[r]) for r in raters))
    if len(common) < 2:
        return None
    index = {c: i for i, c in enumerate(categories)}
    matrix = []
    for item in sorted(common):
        row = [0] * len(categories)
        for r in raters:
            row[index[by_rater[r][item]]] += 1
        matrix.append(row)
    k = fleiss_kappa(matrix)
    return {
        "raters": len(raters),
        "items": len(matrix),
        "fleiss_kappa": round(k, 4),
        "interpretation": interpret_kappa(k),
    }
