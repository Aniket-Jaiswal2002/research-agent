"""Re-score finished runs from the answers and traces saved in traces.jsonl, then rebuild
summary.json and report.md. No API calls.

    python evals/resummarise.py evals/runs/<run_dir> [<run_dir> ...]

For every task that did not end in an API error the checks are recomputed with the current
evals/scorers.py against tasks.json. Judge verdicts (trace["judge"]) are reused as saved.
The previous checks/passed of each row are kept once under "prev_scoring" for audit, and the
before/after deterministic pass rate is printed so it can go into SCORER_CHANGELOG.md.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_evals  # noqa: E402
from run_evals import START_CWD, deterministic_pass, summarise, write_report  # noqa: E402
from scorers import SCORER_VERSION, score  # noqa: E402

TASKS_PATH = os.path.join(run_evals.EVALS, "tasks.json")


def rescore_run(run_dir, tasks_path=TASKS_PATH):
    run_dir = os.path.abspath(os.path.join(START_CWD, run_dir))
    old = json.load(open(os.path.join(run_dir, "summary.json"), encoding="utf-8"))
    meta = {k: old[k] for k in ("run_id", "model", "agent_version", "judge")}
    meta["scorer_version"] = SCORER_VERSION
    tasks = {t["id"]: t for t in json.load(open(tasks_path, encoding="utf-8"))}

    trace_path = os.path.join(run_dir, "traces.jsonl")
    records = [json.loads(line) for line in open(trace_path, encoding="utf-8")]
    changed = []
    for rec in records:
        if rec.get("error"):
            continue  # nothing to score: the API call failed
        was = deterministic_pass(rec)
        result = score(tasks[rec["id"]], rec["trace"])
        judge = rec["trace"].get("judge")
        if judge is not None:  # reuse the saved judge verdict
            result["checks"]["grounded"] = judge["grounded"]
            if judge["grounded"] is False:
                result["passed"] = False
        rec.setdefault("prev_scoring", {"checks": rec["checks"], "passed": rec["passed"]})
        rec["checks"], rec["passed"] = result["checks"], result["passed"]
        if deterministic_pass(rec) != was:
            changed.append((rec["id"], "FAIL->PASS" if not was else "PASS->FAIL"))

    tmp = trace_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, trace_path)

    rows = [{k: v for k, v in r.items() if k not in ("trace", "prev_scoring")} for r in records]
    summary = summarise(rows, meta)
    json.dump(summary, open(os.path.join(run_dir, "summary.json"), "w"), indent=2)
    write_report(summary, rows, os.path.join(run_dir, "report.md"))

    before = old.get("pass_rate_deterministic", old["pass_rate"])  # 3-task smoke run predates the new key
    return {"run_id": meta["run_id"], "before": before, "after": summary["pass_rate_deterministic"],
            "n_scored": summary["n_tasks"], "n_total": summary["n_total"], "errors": summary["errors"],
            "changed": changed, "judged": summary["judged"],
            "pass_incl_judge": summary["pass_rate"] if summary["judged"] else None}


if __name__ == "__main__":
    for d in sys.argv[1:]:
        r = rescore_run(d)
        flips = ", ".join(f"{i} {c}" for i, c in r["changed"]) or "none"
        print(f"{r['run_id']}: deterministic {r['before']:.1%} -> {r['after']:.1%} "
              f"({r['n_scored']} scored of {r['n_total']}, {r['errors']} errored) | changed: {flips}")
