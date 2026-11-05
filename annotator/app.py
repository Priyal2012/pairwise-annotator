"""Flask application: a small JSON API plus a single-page annotation UI."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from annotator.export import build_preference_pairs
from annotator.stats import compute_stats
from annotator.store import PREFERENCES, SCORE_RANGE, Store, ValidationError


def create_app(data_dir: Path | str | None = None, *, store: Store | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    data_dir = Path(data_dir or os.environ.get("ANNOTATOR_DATA", "data"))
    app.config["STORE"] = store or Store(data_dir)
    app.config["JSON_SORT_KEYS"] = False

    def get_store() -> Store:
        return app.config["STORE"]

    # ---- UI ----------------------------------------------------------------------
    @app.get("/")
    def index():
        store = get_store()
        return render_template(
            "index.html", criteria=store.criteria, score_min=SCORE_RANGE[0], score_max=SCORE_RANGE[1]
        )

    # ---- items -----------------------------------------------------------------------
    @app.get("/api/items")
    def list_items():
        store = get_store()
        annotator = request.args.get("annotator")
        done = store.done_item_ids(annotator) if annotator else set()
        rows = [{"id": i["id"], "prompt": i["prompt"][:120], "done": i["id"] in done} for i in store.items()]
        return jsonify({"items": rows, "total": len(rows), "done": len(done)})

    @app.get("/api/items/<item_id>")
    def get_item(item_id: str):
        item = get_store().item(item_id)
        if item is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(_present(item))

    @app.get("/api/next")
    def next_item():
        store = get_store()
        annotator = (request.args.get("annotator") or "").strip()
        if not annotator:
            return jsonify({"error": "annotator is required"}), 400
        item = store.next_item(annotator)
        done = len(store.done_item_ids(annotator))
        if item is None:
            return jsonify({"item": None, "done": done, "total": len(store.items())})
        return jsonify({"item": _present(item), "done": done, "total": len(store.items())})

    # ---- annotations ------------------------------------------------------------------
    @app.post("/api/annotations")
    def post_annotation():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"error": "body must be JSON"}), 400
        try:
            record = get_store().add_annotation(payload)
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 422
        return jsonify(record), 201

    @app.get("/api/annotations")
    def list_annotations():
        store = get_store()
        rows = store.annotations(item_id=request.args.get("item_id"), annotator=request.args.get("annotator"))
        return jsonify({"annotations": rows, "count": len(rows)})

    # ---- stats / export ---------------------------------------------------------------------
    @app.get("/api/stats")
    def stats():
        return jsonify(compute_stats(get_store()))

    @app.get("/api/export")
    def export():
        min_votes = int(request.args.get("min_votes", 1))
        min_agreement = float(request.args.get("min_agreement", 0.5))
        result = build_preference_pairs(get_store(), min_votes=min_votes, min_agreement=min_agreement)
        if request.args.get("format") == "json":
            return jsonify(result)
        body = "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in result["pairs"])
        return Response(
            body,
            mimetype="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=preference_pairs.jsonl"},
        )

    @app.get("/api/meta")
    def meta():
        store = get_store()
        return jsonify(
            {"criteria": list(store.criteria), "preferences": list(PREFERENCES), "score_range": list(SCORE_RANGE)}
        )

    return app


def _present(item: dict) -> dict:
    """Randomise which response is shown on the left to counter position bias.

    ``swapped`` is returned so the client can map its left/right choice back to
    the canonical A/B before submitting.
    """
    swapped = random.random() < 0.5
    left, right = (item["response_b"], item["response_a"]) if swapped else (item["response_a"], item["response_b"])
    return {
        "id": item["id"],
        "prompt": item["prompt"],
        "left": left,
        "right": right,
        "swapped": swapped,
        "meta": item.get("meta", {}),
    }
