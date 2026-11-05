"""pairwise-annotator — side-by-side preference annotation for AI responses.

A small, dependency-light tool for the human half of model evaluation:

* show two model responses to the same prompt side by side (order randomised to
  counter position bias),
* capture a preference, per-criterion rubric scores and a written rationale,
* store everything as append-only JSONL,
* measure inter-annotator agreement (percent agreement, Cohen's κ, Fleiss' κ),
* export majority-vote preference pairs in the ``{prompt, chosen, rejected}``
  format used for preference fine-tuning (DPO / RLHF reward modelling).
"""

__version__ = "0.1.0"
