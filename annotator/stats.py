"""Progress and agreement statistics for a :class:`~annotator.store.Store`."""

from __future__ import annotations

from collections import Counter, defaultdict

from annotator.agreement import fleiss_from_labels, labels_by_rater, pairwise_kappas
from annotator.store import PREFERENCES, Store


def compute_stats(store: Store) -> dict:
    latest = store.latest_annotations()
    records = list(latest.values())
    items = store.items()

    per_annotator: dict[str, dict] = defaultdict(lambda: {"annotated": 0, "preferences": Counter(), "seconds": []})
    for r in records:
        bucket = per_annotator[r["annotator"]]
        bucket["annotated"] += 1
        bucket["preferences"][r["preference"]] += 1
        if r.get("seconds_spent") is not None:
            bucket["seconds"].append(r["seconds_spent"])

    annotators = {}
    for name, bucket in sorted(per_annotator.items()):
        secs = bucket["seconds"]
        annotators[name] = {
            "annotated": bucket["annotated"],
            "of": len(items),
            "preferences": dict(bucket["preferences"]),
            "median_seconds": _median(secs) if secs else None,
        }

    coverage = Counter(r["item_id"] for r in records)
    by_rater = labels_by_rater(
        {"annotator": r["annotator"], "item_id": r["item_id"], "label": r["preference"]} for r in records
    )

    # Position bias check: how often was the *left-hand* response preferred?
    left_pref = sum(
        1 for r in records if r["preference"] != "tie" and (r["preference"] == "A") != r.get("swapped", False)
    )
    decided = sum(1 for r in records if r["preference"] != "tie")

    return {
        "items": len(items),
        "annotations": len(records),
        "annotators": annotators,
        "items_with_n_annotations": dict(sorted(Counter(coverage.values()).items())),
        "overall_preferences": dict(Counter(r["preference"] for r in records)),
        "left_side_preferred_rate": round(left_pref / decided, 3) if decided else None,
        "pairwise": pairwise_kappas(by_rater),
        "fleiss": fleiss_from_labels(by_rater, PREFERENCES),
        "mean_scores": _mean_scores(records, store.criteria),
    }


def _median(values: list[float]) -> float:
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else round((s[mid - 1] + s[mid]) / 2, 1)


def _mean_scores(records: list[dict], criteria: tuple[str, ...]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {"A": {}, "B": {}}
    for side in ("A", "B"):
        for criterion in criteria:
            vals = [r["scores"][side][criterion] for r in records if criterion in r["scores"].get(side, {})]
            if vals:
                out[side][criterion] = round(sum(vals) / len(vals), 2)
    return out
