"""Append-only JSONL storage for items and annotations.

Two files live in the data directory:

* ``items.jsonl``        — one prompt + two responses per line
* ``annotations.jsonl``  — one annotation per line, appended, never rewritten

Keeping annotations append-only means nothing is ever lost: a re-annotation is a
new line, and the *latest* line per (annotator, item) wins when we aggregate.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

PREFERENCES = ("A", "B", "tie")
DEFAULT_CRITERIA = ("correctness", "completeness", "clarity", "safety")
SCORE_RANGE = (1, 5)


class ValidationError(ValueError):
    """Raised when an annotation payload is malformed."""


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


class Store:
    def __init__(self, data_dir: Path | str, *, criteria: tuple[str, ...] = DEFAULT_CRITERIA):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.items_path = self.data_dir / "items.jsonl"
        self.annotations_path = self.data_dir / "annotations.jsonl"
        self.criteria = criteria
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {row["id"]: row for row in _read_jsonl(self.items_path)}

    # ---- items ------------------------------------------------------------------
    def items(self) -> list[dict]:
        return list(self._items.values())

    def item(self, item_id: str) -> dict | None:
        return self._items.get(item_id)

    def add_items(self, rows: list[dict]) -> int:
        """Append items (each needs ``prompt``, ``response_a``, ``response_b``); returns how many were added."""
        added = 0
        with self._lock, self.items_path.open("a", encoding="utf-8") as fh:
            for row in rows:
                for key in ("prompt", "response_a", "response_b"):
                    if not row.get(key):
                        raise ValidationError(f"item is missing '{key}'")
                row = {"id": row.get("id") or uuid.uuid4().hex[:8], **row}
                if row["id"] in self._items:
                    continue
                self._items[row["id"]] = row
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                added += 1
        return added

    # ---- annotations --------------------------------------------------------------
    def annotations(self, *, item_id: str | None = None, annotator: str | None = None) -> list[dict]:
        rows = _read_jsonl(self.annotations_path)
        if item_id is not None:
            rows = [r for r in rows if r["item_id"] == item_id]
        if annotator is not None:
            rows = [r for r in rows if r["annotator"] == annotator]
        return rows

    def latest_annotations(self) -> dict[tuple[str, str], dict]:
        """Most recent annotation per (annotator, item_id)."""
        latest: dict[tuple[str, str], dict] = {}
        for r in self.annotations():
            latest[(r["annotator"], r["item_id"])] = r
        return latest

    def add_annotation(self, payload: dict) -> dict:
        record = self.validate(payload)
        record["id"] = uuid.uuid4().hex[:12]
        record["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock, self.annotations_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def validate(self, payload: dict) -> dict:
        """Check and normalise an incoming annotation; raises :class:`ValidationError`."""
        if not isinstance(payload, dict):
            raise ValidationError("payload must be an object")
        annotator = str(payload.get("annotator", "")).strip()
        if not annotator:
            raise ValidationError("annotator is required")
        item_id = str(payload.get("item_id", ""))
        if item_id not in self._items:
            raise ValidationError(f"unknown item_id '{item_id}'")
        preference = payload.get("preference")
        if preference not in PREFERENCES:
            raise ValidationError(f"preference must be one of {PREFERENCES}")
        rationale = str(payload.get("rationale", "")).strip()
        if len(rationale) < 10:
            raise ValidationError("rationale must be at least 10 characters — say *why*")

        scores = payload.get("scores") or {}
        clean_scores: dict[str, dict[str, int]] = {}
        for side in ("A", "B"):
            side_scores = scores.get(side) or {}
            clean_scores[side] = {}
            for criterion in self.criteria:
                value = side_scores.get(criterion)
                if value is None:
                    raise ValidationError(f"missing score for {criterion} on response {side}")
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError(f"score for {criterion}/{side} must be an integer") from exc
                lo, hi = SCORE_RANGE
                if not lo <= value <= hi:
                    raise ValidationError(f"score for {criterion}/{side} must be between {lo} and {hi}")
                clean_scores[side][criterion] = value

        seconds = payload.get("seconds_spent")
        try:
            seconds = round(float(seconds), 1) if seconds is not None else None
        except (TypeError, ValueError):
            seconds = None

        return {
            "item_id": item_id,
            "annotator": annotator,
            "preference": preference,
            "scores": clean_scores,
            "rationale": rationale,
            "seconds_spent": seconds,
            "swapped": bool(payload.get("swapped", False)),
        }

    # ---- progress -------------------------------------------------------------------
    def done_item_ids(self, annotator: str) -> set[str]:
        return {item for (who, item) in self.latest_annotations() if who == annotator}

    def next_item(self, annotator: str) -> dict | None:
        done = self.done_item_ids(annotator)
        for item in self._items.values():
            if item["id"] not in done:
                return item
        return None
