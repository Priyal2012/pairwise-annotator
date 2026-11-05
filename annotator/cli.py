"""Command-line entry points.

python -m annotator seed  [--data data]            # write the bundled seed items
python -m annotator serve [--data data] [--port 8000]
python -m annotator stats [--data data]
python -m annotator export [--data data] [--out preference_pairs.jsonl] [--min-votes 2]
python -m annotator simulate [--data data] [--annotators 3] [--noise 0.15]   # demo annotations
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from annotator.agreement import interpret_kappa
from annotator.export import build_preference_pairs
from annotator.seed import SEED_ITEMS
from annotator.stats import compute_stats
from annotator.store import Store


def cmd_seed(args) -> int:
    store = Store(args.data)
    added = store.add_items([dict(item) for item in SEED_ITEMS])
    print(f"added {added} item(s) to {store.items_path} ({len(store.items())} total)")
    return 0


def cmd_serve(args) -> int:
    from annotator.app import create_app

    store = Store(args.data)
    if not store.items():
        print("no items yet — run `python -m annotator seed` first", file=sys.stderr)
        return 2
    app = create_app(store=store)
    print(f"serving {len(store.items())} item(s) on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def cmd_stats(args) -> int:
    stats = compute_stats(Store(args.data))
    if args.json:
        print(json.dumps(stats, indent=2))
        return 0
    print(f"{stats['annotations']} annotation(s) on {stats['items']} item(s)")
    for name, a in stats["annotators"].items():
        prefs = ", ".join(f"{k}={v}" for k, v in sorted(a["preferences"].items()))
        median = f", median {a['median_seconds']}s/item" if a["median_seconds"] is not None else ""
        print(f"  {name:<12} {a['annotated']}/{a['of']}  ({prefs}{median})")
    if stats["left_side_preferred_rate"] is not None:
        print(f"left-hand response preferred {stats['left_side_preferred_rate']:.0%} of the time (position-bias check)")
    for p in stats["pairwise"]:
        print(
            f"  {p['raters'][0]} vs {p['raters'][1]}: agreement {p['percent_agreement']:.0%}, "
            f"Cohen's κ {p['cohen_kappa']:.2f} ({p['interpretation']}) on {p['shared_items']} items"
        )
    if stats["fleiss"]:
        f = stats["fleiss"]
        scope = f"across {f['raters']} raters on {f['items']} items"
        print(f"Fleiss' κ {scope}: {f['fleiss_kappa']:.2f} ({f['interpretation']})")
    return 0


def cmd_export(args) -> int:
    result = build_preference_pairs(Store(args.data), min_votes=args.min_votes, min_agreement=args.min_agreement)
    out = Path(args.out)
    with out.open("w", encoding="utf-8") as fh:
        for pair in result["pairs"]:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
    skipped = ", ".join(f"{k}={v}" for k, v in result["skipped"].items()) or "none"
    print(f"wrote {len(result['pairs'])} preference pair(s) to {out}; skipped: {skipped}")
    return 0


def cmd_simulate(args) -> int:
    """Generate demo annotations from the seed metadata, with some deliberate noise.

    Each simulated annotator picks the response the seed marks as better with
    probability ``1 - noise``; otherwise they pick the other one or a tie. This is
    only for demonstrating the stats/export commands — never mix it with real data.
    """
    store = Store(args.data)
    rng = random.Random(args.seed)
    names = [f"sim_{i + 1}" for i in range(args.annotators)]
    written = 0
    for item in store.items():
        defect_in = item.get("meta", {}).get("defect_in")
        if defect_in not in ("A", "B"):
            continue
        better = "B" if defect_in == "A" else "A"
        for name in names:
            roll = rng.random()
            if roll < 1 - args.noise:
                pref = better
            elif roll < 1 - args.noise / 2:
                pref = defect_in
            else:
                pref = "tie"
            scores = {}
            for side in ("A", "B"):
                base = 4 if side == better else 2
                scores[side] = {c: max(1, min(5, base + rng.choice((-1, 0, 0, 1)))) for c in store.criteria}
            store.add_annotation(
                {
                    "annotator": name,
                    "item_id": item["id"],
                    "preference": pref,
                    "scores": scores,
                    "rationale": f"[simulated] {item['meta'].get('defect', 'one answer has a defect')}",
                    "seconds_spent": round(rng.uniform(25, 90), 1),
                    "swapped": rng.random() < 0.5,
                }
            )
            written += 1
    print(f"wrote {written} simulated annotation(s) from {len(names)} annotator(s) to {store.annotations_path}")
    print(f"interpretation scale: {', '.join(interpret_kappa(k) for k in (-0.1, 0.1, 0.3, 0.5, 0.7, 0.9))}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="annotator", description="Pairwise preference annotation for AI responses.")
    p.add_argument("--data", default="data", help="data directory (default: data/)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="write the bundled seed items").set_defaults(fn=cmd_seed)

    s = sub.add_parser("serve", help="run the web UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--debug", action="store_true")
    s.set_defaults(fn=cmd_serve)

    st = sub.add_parser("stats", help="progress and agreement statistics")
    st.add_argument("--json", action="store_true")
    st.set_defaults(fn=cmd_stats)

    ex = sub.add_parser("export", help="write majority-vote preference pairs as JSONL")
    ex.add_argument("--out", default="preference_pairs.jsonl")
    ex.add_argument("--min-votes", type=int, default=1)
    ex.add_argument("--min-agreement", type=float, default=0.5)
    ex.set_defaults(fn=cmd_export)

    sim = sub.add_parser("simulate", help="generate demo annotations (for trying stats/export)")
    sim.add_argument("--annotators", type=int, default=3)
    sim.add_argument("--noise", type=float, default=0.15)
    sim.add_argument("--seed", type=int, default=0)
    sim.set_defaults(fn=cmd_simulate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)
