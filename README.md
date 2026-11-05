# pairwise-annotator

**Side-by-side preference annotation for AI responses — with agreement statistics and
a DPO-ready export.**

Evaluating language models needs humans to compare outputs carefully and consistently.
This tool is the smallest thing that does that properly: a web UI for comparing two
responses to the same prompt, a rubric, a required written rationale, and the
statistics you need to know whether your annotators actually agree with each other.

```
$ python -m annotator seed
$ python -m annotator serve          # http://127.0.0.1:8000

$ python -m annotator stats
36 annotation(s) on 12 item(s)
  sim_1        12/12  (A=10, B=2, median 63.3s/item)
  sim_2        12/12  (A=8, B=3, tie=1, median 67.2s/item)
  sim_3        12/12  (A=8, B=4, median 53.3s/item)
left-hand response preferred 60% of the time (position-bias check)
  sim_1 vs sim_2: agreement 75%, Cohen's κ 0.38 (fair) on 12 items
  sim_1 vs sim_3: agreement 83%, Cohen's κ 0.57 (moderate) on 12 items
  sim_2 vs sim_3: agreement 75%, Cohen's κ 0.47 (moderate) on 12 items
Fleiss' κ across 3 raters on 12 items: 0.46 (moderate)

$ python -m annotator export --min-votes 2 --out preference_pairs.jsonl
wrote 12 preference pair(s) to preference_pairs.jsonl; skipped: none
```

## What's in it

**Annotation UI** (`annotator/templates`, `annotator/static` — plain HTML/JS, no build step)

- Two responses side by side; the order is **randomised per view** and the swap is
  recorded, so left/right position bias can be measured instead of silently poisoning
  the data.
- A rubric (correctness, completeness, clarity, safety — configurable) scored 1–5 for
  each response, an overall preference (A / B / tie), and a rationale that must be at
  least 10 characters. Keyboard shortcuts: `1` / `2` / `3`, `Ctrl+Enter` to submit.
- Progress per annotator, resumable: the server hands each annotator the next item
  they have not done.

**Storage** (`store.py`) — append-only JSONL. A re-annotation is a new line; the latest
line per (annotator, item) wins at aggregation time. Nothing is ever rewritten.

**Agreement** (`agreement.py`) — percent agreement, **Cohen's κ** (two raters),
**Fleiss' κ** (any number of raters), Landis–Koch interpretation. Pure functions,
unit-tested against the published textbook examples (Cohen 0.40, Fleiss 0.21).

**Export** (`export.py`) — majority vote per item → `{"prompt", "chosen", "rejected",
"votes", "agreement", "mean_scores", "rationales"}` JSONL, the shape used for DPO and
reward-model training. Ties, split votes and low-agreement items are skipped and
counted, because an ambiguous pair is worse than no pair.

**API** (`app.py`, Flask)

| Route                              | Purpose                                           |
| ---------------------------------- | ------------------------------------------------- |
| `GET  /api/next?annotator=`        | next unannotated item (sides randomised)          |
| `POST /api/annotations`            | submit; `422` with a reason on invalid payloads   |
| `GET  /api/items?annotator=`       | progress list                                     |
| `GET  /api/stats`                  | counts, per-annotator progress, κ, position bias  |
| `GET  /api/export[?format=json]`   | preference pairs (JSONL download)                 |

## Seed data

`annotator/seed.py` holds 12 software-engineering prompts (Python semantics, SQL
injection, git, HTTP idempotency, N+1 queries, password hashing, async, testing…) with
two hand-written answers each. In every pair one answer contains a concrete defect —
a false claim, an unsafe recommendation, or a snippet that would not run — and the
metadata records which. `python -m annotator simulate` uses that metadata to generate
noisy demo annotations so the stats and export commands have something to chew on
(`data/annotations.demo.jsonl` is one such run; real data is git-ignored).

## Install & run

```bash
git clone https://github.com/Priyal2012/pairwise-annotator
cd pairwise-annotator
pip install -e ".[dev]"          # flask + pytest + ruff

pytest                            # 28 tests
python -m annotator seed          # writes data/items.jsonl
python -m annotator serve         # open http://127.0.0.1:8000, enter a name, start
python -m annotator stats
python -m annotator export --min-votes 2
```

To annotate your own data, write `data/items.jsonl` with one object per line:
`{"id": "...", "prompt": "...", "response_a": "...", "response_b": "..."}`.

## Design notes

- *Why a required rationale?* A preference without a reason is nearly useless for
  improving a model or for auditing the annotator. Forcing a sentence also measurably
  slows people down in the right way.
- *Why randomise sides?* Annotators favour the left/first option more often than they
  should. Recording `swapped` lets `stats` report the left-preferred rate; anything far
  from 50 % is a flag.
- *Why κ and not just percent agreement?* With three labels and a skewed distribution,
  two annotators can agree 75 % of the time by chance. κ corrects for that.

## Layout

```
annotator/
├── app.py          # Flask routes
├── store.py        # JSONL persistence + validation
├── agreement.py    # percent agreement, Cohen's κ, Fleiss' κ
├── stats.py        # progress, bias check, agreement summary
├── export.py       # majority vote → preference pairs
├── seed.py         # 12 hand-written prompt/response pairs
├── cli.py          # seed / serve / stats / export / simulate
├── templates/index.html
└── static/app.js, style.css
```

MIT licensed.
