"""Aggregate annotations and export preference pairs.

The export format is the one used for preference fine-tuning (DPO) and reward
modelling::

    {"prompt": ..., "chosen": ..., "rejected": ..., "votes": {"A": 2, "B": 1, "tie": 0},
     "agreement": 0.67, "rationales": [...]}

Items are decided by **majority vote** over the latest annotation of each
annotator. Ties and items without a clear majority are skipped (and counted) —
an ambiguous pair is worse training data than no pair.
"""

from __future__ import annotations

from collections import Counter

from annotator.store import Store


def majority(votes: Counter) -> tuple[str | None, float]:
    """Winning label and its share of votes; None when there is no strict winner."""
    total = sum(votes.values())
    if total == 0:
        return None, 0.0
    (top, top_n), *rest = votes.most_common()
    if rest and rest[0][1] == top_n:
        return None, top_n / total
    return top, top_n / total


def build_preference_pairs(store: Store, *, min_votes: int = 1, min_agreement: float = 0.5) -> dict:
    latest = store.latest_annotations()
    by_item: dict[str, list[dict]] = {}
    for (_, item_id), record in latest.items():
        by_item.setdefault(item_id, []).append(record)

    pairs, skipped = [], Counter()
    for item in store.items():
        records = by_item.get(item["id"], [])
        if len(records) < min_votes:
            skipped["too_few_votes"] += 1
            continue
        votes = Counter(r["preference"] for r in records)
        winner, share = majority(votes)
        if winner is None or winner == "tie":
            skipped["tie_or_no_majority"] += 1
            continue
        if share < min_agreement:
            skipped["low_agreement"] += 1
            continue
        chosen_key, rejected_key = ("response_a", "response_b") if winner == "A" else ("response_b", "response_a")
        pairs.append(
            {
                "id": item["id"],
                "prompt": item["prompt"],
                "chosen": item[chosen_key],
                "rejected": item[rejected_key],
                "votes": {"A": votes["A"], "B": votes["B"], "tie": votes["tie"]},
                "agreement": round(share, 4),
                "mean_scores": _mean_scores(records, winner),
                "rationales": [r["rationale"] for r in records if r["preference"] == winner],
            }
        )
    return {"pairs": pairs, "skipped": dict(skipped), "items_total": len(store.items())}


def _mean_scores(records: list[dict], winner: str) -> dict[str, dict[str, float]]:
    """Average rubric score per criterion for chosen and rejected sides."""
    loser = "B" if winner == "A" else "A"
    out: dict[str, dict[str, float]] = {"chosen": {}, "rejected": {}}
    criteria = sorted({c for r in records for c in r["scores"].get("A", {})})
    for criterion in criteria:
        for key, side in (("chosen", winner), ("rejected", loser)):
            vals = [r["scores"][side][criterion] for r in records if criterion in r["scores"].get(side, {})]
            if vals:
                out[key][criterion] = round(sum(vals) / len(vals), 2)
    return out
