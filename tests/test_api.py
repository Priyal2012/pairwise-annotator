import json

import pytest

from annotator.app import create_app
from annotator.cli import main
from annotator.seed import SEED_ITEMS
from annotator.store import Store


@pytest.fixture
def client(tmp_path):
    store = Store(tmp_path)
    store.add_items([dict(i) for i in SEED_ITEMS])
    app = create_app(store=store)
    app.testing = True
    return app.test_client()


def _payload(item, pref="A"):
    scores = {s: {c: 3 for c in ("correctness", "completeness", "clarity", "safety")} for s in ("A", "B")}
    return {
        "annotator": "tester",
        "item_id": item["id"],
        "preference": pref,
        "scores": scores,
        "rationale": "One answer states something false about return values.",
        "swapped": item["swapped"],
        "seconds_spent": 12.5,
    }


def test_index_renders(client):
    html = client.get("/").get_data(as_text=True)
    assert "Pairwise annotator" in html
    assert "correctness" in html and "safety" in html


def test_next_requires_annotator(client):
    assert client.get("/api/next").status_code == 400


def test_next_presents_randomised_sides(client):
    body = client.get("/api/next?annotator=tester").get_json()
    item = body["item"]
    assert {"id", "prompt", "left", "right", "swapped"} <= set(item)
    original = next(i for i in SEED_ITEMS if i["id"] == item["id"])
    if item["swapped"]:
        assert item["left"] == original["response_b"]
    else:
        assert item["left"] == original["response_a"]


def test_annotation_flow_and_progress(client):
    first = client.get("/api/next?annotator=tester").get_json()
    assert first["done"] == 0 and first["total"] == len(SEED_ITEMS)

    res = client.post("/api/annotations", json=_payload(first["item"]))
    assert res.status_code == 201
    assert res.get_json()["preference"] == "A"

    second = client.get("/api/next?annotator=tester").get_json()
    assert second["done"] == 1
    assert second["item"]["id"] != first["item"]["id"]

    listed = client.get("/api/items?annotator=tester").get_json()
    assert listed["done"] == 1 and sum(i["done"] for i in listed["items"]) == 1


def test_validation_errors_are_422(client):
    item = client.get("/api/next?annotator=tester").get_json()["item"]
    bad = _payload(item)
    bad["rationale"] = "ok"
    res = client.post("/api/annotations", json=bad)
    assert res.status_code == 422
    assert "rationale" in res.get_json()["error"]
    assert client.post("/api/annotations", data="not json", content_type="text/plain").status_code == 400


def test_stats_and_export_endpoints(client):
    for who in ("p", "q"):
        item = client.get(f"/api/next?annotator={who}").get_json()["item"]
        payload = _payload(item)
        payload["annotator"] = who
        client.post("/api/annotations", json=payload)
    stats = client.get("/api/stats").get_json()
    assert stats["annotations"] == 2
    assert set(stats["annotators"]) == {"p", "q"}
    assert stats["left_side_preferred_rate"] is not None

    export = client.get("/api/export")
    assert export.mimetype == "application/x-ndjson"
    lines = [json.loads(ln) for ln in export.get_data(as_text=True).splitlines()]
    assert len(lines) == 1 and {"prompt", "chosen", "rejected", "votes"} <= set(lines[0])
    assert client.get("/api/export?format=json").get_json()["items_total"] == len(SEED_ITEMS)


def test_cli_seed_simulate_stats_export(tmp_path, capsys):
    data = str(tmp_path / "data")
    assert main(["--data", data, "seed"]) == 0
    assert main(["--data", data, "simulate", "--annotators", "3", "--noise", "0.2"]) == 0
    assert main(["--data", data, "stats"]) == 0
    out = capsys.readouterr().out
    assert "Fleiss" in out and "Cohen" in out
    target = tmp_path / "pairs.jsonl"
    assert main(["--data", data, "export", "--out", str(target), "--min-votes", "2"]) == 0
    rows = [json.loads(ln) for ln in target.read_text().splitlines()]
    assert rows, "simulation with 3 annotators should yield majority pairs"
    # With low noise the majority should pick the non-defective answer most of the time.
    correct = 0
    for row in rows:
        seed = next(i for i in SEED_ITEMS if i["id"] == row["id"])
        better = "response_b" if seed["meta"]["defect_in"] == "A" else "response_a"
        correct += row["chosen"] == seed[better]
    assert correct / len(rows) >= 0.8
