"""Recompute summary.json and report.md for finished runs from their saved traces.jsonl.

    python evals/resummarise.py evals/runs/<run_dir> [<run_dir> ...]

No LLM calls are made: scores and judge verdicts already live in traces.jsonl.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_evals import summarise, write_report  # noqa: E402


def resummarise(run_dir):
    old = json.load(open(os.path.join(run_dir, "summary.json"), encoding="utf-8"))
    meta = {k: old[k] for k in ("run_id", "model", "agent_version", "judge")}
    rows = []
    with open(os.path.join(run_dir, "traces.jsonl"), encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            r.pop("trace", None)
            rows.append(r)
    summary = summarise(rows, meta)
    json.dump(summary, open(os.path.join(run_dir, "summary.json"), "w"), indent=2)
    write_report(summary, rows, os.path.join(run_dir, "report.md"))
    incl = f"{summary['pass_rate']:.0%}" if summary["judged"] else "–"
    print(f"{meta['run_id']}: deterministic {summary['pass_rate_deterministic']:.0%}, incl. judge {incl}")


if __name__ == "__main__":
    for d in sys.argv[1:]:
        resummarise(d)
