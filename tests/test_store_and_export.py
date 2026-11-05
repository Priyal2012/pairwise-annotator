from collections import Counter

import pytest

from annotator.export import build_preference_pairs, majority
from annotator.seed import SEED_ITEMS
from annotator.store import Store, ValidationError


def _scores(a=4, b=2):
    return {
        "A": {c: a for c in ("correctness", "completeness", "clarity", "safety")},
        "B": {c: b for c in ("correctness", "completeness", "clarity", "safety")},
    }


def _annotation(item_id, annotator="p", preference="A", **extra):
    base = {
        "annotator": annotator,
        "item_id": item_id,
        "preference": preference,
        "scores": _scores(),
        "rationale": "Response A is correct about the return value; B is wrong.",
    }
    base.update(extra)
    return base


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path)
    s.add_items([dict(i) for i in SEED_ITEMS])
    return s


def test_items_persist_and_dedupe(tmp_path, store):
    assert len(store.items()) == len(SEED_ITEMS)
    assert store.add_items([dict(SEED_ITEMS[0])]) == 0  # same id -> skipped
    reloaded = Store(tmp_path)
    assert len(reloaded.items()) == len(SEED_ITEMS)


def test_add_items_requires_fields(store):
    with pytest.raises(ValidationError):
        store.add_items([{"prompt": "x", "response_a": "y"}])


def test_annotation_round_trip(tmp_path, store):
    item = store.items()[0]
    rec = store.add_annotation(_annotation(item["id"], seconds_spent="41.27", swapped=True))
    assert rec["id"] and rec["created_at"]
    assert rec["seconds_spent"] == 41.3
    assert rec["swapped"] is True
    assert Store(tmp_path).annotations(annotator="p")[0]["item_id"] == item["id"]


@pytest.mark.parametrize(
    "mutation,message",
    [
        ({"annotator": ""}, "annotator"),
        ({"item_id": "nope"}, "unknown item_id"),
        ({"preference": "C"}, "preference"),
        ({"rationale": "meh"}, "rationale"),
        ({"scores": {"A": {}, "B": {}}}, "missing score"),
        ({"scores": {**_scores(), "A": {**_scores()["A"], "clarity": 9}}}, "between 1 and 5"),
        ({"scores": {**_scores(), "B": {**_scores()["B"], "safety": "high"}}}, "integer"),
    ],
)
def test_validation_errors(store, mutation, message):
    payload = _annotation(store.items()[0]["id"])
    payload.update(mutation)
    with pytest.raises(ValidationError, match=message):
        store.add_annotation(payload)


def test_next_item_skips_done(store):
    first = store.next_item("p")
    store.add_annotation(_annotation(first["id"]))
    second = store.next_item("p")
    assert second["id"] != first["id"]
    assert store.done_item_ids("p") == {first["id"]}
    assert store.next_item("someone_else")["id"] == first["id"]


def test_latest_annotation_wins(store):
    item = store.items()[0]["id"]
    store.add_annotation(_annotation(item, preference="A"))
    store.add_annotation(_annotation(item, preference="B"))
    assert store.latest_annotations()[("p", item)]["preference"] == "B"


def test_majority():
    assert majority(Counter(A=2, B=1)) == ("A", pytest.approx(2 / 3))
    assert majority(Counter(A=1, B=1)) == (None, 0.5)
    assert majority(Counter()) == (None, 0.0)


def test_export_majority_vote_and_skips(store):
    i1, i2, i3 = (i["id"] for i in store.items()[:3])
    for who, pref in (("p", "A"), ("q", "A"), ("r", "B")):
        store.add_annotation(_annotation(i1, annotator=who, preference=pref))
    for who, pref in (("p", "A"), ("q", "B")):
        store.add_annotation(_annotation(i2, annotator=who, preference=pref))
    store.add_annotation(_annotation(i3, annotator="p", preference="tie"))

    result = build_preference_pairs(store, min_votes=1)
    pairs = {p["id"]: p for p in result["pairs"]}
    assert set(pairs) == {i1}
    assert pairs[i1]["chosen"] == store.item(i1)["response_a"]
    assert pairs[i1]["rejected"] == store.item(i1)["response_b"]
    assert pairs[i1]["votes"] == {"A": 2, "B": 1, "tie": 0}
    assert pairs[i1]["agreement"] == pytest.approx(2 / 3, abs=1e-3)
    assert pairs[i1]["mean_scores"]["chosen"]["correctness"] == 4.0
    assert len(pairs[i1]["rationales"]) == 2
    assert result["skipped"]["tie_or_no_majority"] == 2
    assert result["skipped"]["too_few_votes"] == len(SEED_ITEMS) - 3

    strict = build_preference_pairs(store, min_votes=3, min_agreement=0.75)
    assert strict["pairs"] == [] and strict["skipped"]["low_agreement"] == 1
