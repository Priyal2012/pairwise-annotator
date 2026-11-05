import pytest

from annotator.agreement import (
    cohen_kappa,
    fleiss_from_labels,
    fleiss_kappa,
    interpret_kappa,
    labels_by_rater,
    pairwise_kappas,
    percent_agreement,
)


def _from_table(yy, yn, ny, nn):
    """Build two label lists from a 2×2 agreement table."""
    a = ["y"] * (yy + yn) + ["n"] * (ny + nn)
    b = ["y"] * yy + ["n"] * yn + ["y"] * ny + ["n"] * nn
    return a, b


def test_cohen_kappa_textbook_example():
    # Classic example: observed agreement 0.70, expected 0.50 -> kappa 0.40
    a, b = _from_table(20, 5, 10, 15)
    assert percent_agreement(a, b) == pytest.approx(0.70)
    assert cohen_kappa(a, b) == pytest.approx(0.40)


def test_cohen_kappa_perfect_and_chance():
    assert cohen_kappa(["A", "B", "tie"], ["A", "B", "tie"]) == 1.0
    assert cohen_kappa(["A", "A"], ["A", "A"]) == 1.0  # degenerate: single label, full agreement
    a, b = _from_table(25, 25, 25, 25)  # independent raters
    assert cohen_kappa(a, b) == pytest.approx(0.0)


def test_cohen_kappa_rejects_bad_input():
    with pytest.raises(ValueError):
        cohen_kappa(["A"], ["A", "B"])
    with pytest.raises(ValueError):
        cohen_kappa([], [])


def test_fleiss_kappa_textbook_example():
    # 14 raters, 10 subjects, 5 categories; widely published result is 0.210.
    matrix = [
        [0, 0, 0, 0, 14],
        [0, 2, 6, 4, 2],
        [0, 0, 3, 5, 6],
        [0, 3, 9, 2, 0],
        [2, 2, 8, 1, 1],
        [7, 7, 0, 0, 0],
        [3, 2, 6, 3, 0],
        [2, 5, 3, 2, 2],
        [6, 5, 2, 1, 0],
        [0, 2, 2, 3, 7],
    ]
    assert fleiss_kappa(matrix) == pytest.approx(0.2099, abs=1e-3)


def test_fleiss_kappa_validation():
    with pytest.raises(ValueError):
        fleiss_kappa([[2, 1], [1, 1]])  # unequal rater counts
    with pytest.raises(ValueError):
        fleiss_kappa([[1, 0]])  # one rater


def test_interpretation_bands():
    assert interpret_kappa(-0.2) == "poor"
    assert interpret_kappa(0.1) == "slight"
    assert interpret_kappa(0.35) == "fair"
    assert interpret_kappa(0.5) == "moderate"
    assert interpret_kappa(0.7) == "substantial"
    assert interpret_kappa(0.95) == "almost perfect"


def test_pairwise_and_fleiss_from_records():
    records = [
        {"annotator": "ann", "item_id": "i1", "label": "A"},
        {"annotator": "ann", "item_id": "i2", "label": "B"},
        {"annotator": "ann", "item_id": "i3", "label": "A"},
        {"annotator": "bob", "item_id": "i1", "label": "A"},
        {"annotator": "bob", "item_id": "i2", "label": "B"},
        {"annotator": "bob", "item_id": "i3", "label": "tie"},
        {"annotator": "cat", "item_id": "i1", "label": "A"},
        {"annotator": "cat", "item_id": "i3", "label": "A"},
        # re-annotation: latest wins
        {"annotator": "cat", "item_id": "i1", "label": "B"},
    ]
    by_rater = labels_by_rater(records)
    assert by_rater["cat"]["i1"] == "B"

    pairs = pairwise_kappas(by_rater)
    ab = next(p for p in pairs if p["raters"] == ["ann", "bob"])
    assert ab["shared_items"] == 3
    assert ab["percent_agreement"] == pytest.approx(2 / 3, abs=1e-3)

    fleiss = fleiss_from_labels(by_rater, ("A", "B", "tie"))
    assert fleiss["items"] == 2  # only i1 and i3 were labelled by all three
    assert fleiss["raters"] == 3
