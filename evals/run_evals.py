"""Run the ResearchMind eval suite.

    python evals/run_evals.py --model openai/gpt-oss-20b --agent-version v1
    python evals/run_evals.py --model openai/gpt-oss-120b --agent-version v2 --judge
    python evals/run_evals.py --only pdf_fact,injection --limit 5

Writes evals/runs/<run>/{traces.jsonl, summary.json, report.md}.
Compare runs with:  python evals/report.py evals/runs/*/summary.json
"""
import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.join(ROOT, "evals")
sys.path.insert(0, ROOT)
sys.path.insert(0, EVALS)
START_CWD = os.getcwd()  # relative CLI paths (e.g. --rerun-errors) resolve against this
os.chdir(ROOT)  # vector_store/ paths are relative to the repo root

from scorers import score, judge_grounded, SCORER_VERSION  # noqa: E402

FIXTURE_PDF = os.path.join(EVALS, "fixtures", "helios7-brief.pdf")
FIXTURE_NAME = "helios7-brief"


def ensure_fixture():
    from tools import set_active_pdf
    if not os.path.exists(f"vector_store/{FIXTURE_NAME}/index.faiss"):
        if not os.path.exists(FIXTURE_PDF):
            from make_fixture import build
            build(FIXTURE_PDF)
        from ingest import ingest_pdf
        ingest_pdf(FIXTURE_PDF)
    set_active_pdf(FIXTURE_NAME)


def with_retry(fn, tries=5):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # Groq 429s / transient network errors
            msg = str(e).lower()
            if i == tries - 1 or not any(k in msg for k in ("rate", "429", "timeout", "connection", "503")):
                raise
            wait = 10 * (i + 1)
            print(f"   rate-limited/transient error, retrying in {wait}s ...")
            time.sleep(wait)


def pct(xs, q):
    if not xs:
        return 0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def deterministic_pass(row):
    """Pass computed from every applicable check EXCEPT the LLM judge's 'grounded'."""
    return all(v for k, v in row["checks"].items() if v is not None and k != "grounded")


def summarise(rows, meta):
    # Tasks that ended in an API error (rate limit, outage) say nothing about the agent,
    # so they are excluded from every rate and listed separately.
    errored = [r for r in rows if r.get("error")]
    n_total = len(rows)
    rows = [r for r in rows if not r.get("error")]
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(deterministic_pass(r))
    check_names = sorted({k for r in rows for k in r["checks"]})
    check_rates = {}
    for k in check_names:
        vals = [r["checks"][k] for r in rows if r["checks"].get(k) is not None]
        if vals:
            check_rates[k] = {"rate": sum(vals) / len(vals), "n": len(vals)}
    lat = [r["latency_s"] for r in rows]
    return {
        **meta,
        "n_tasks": len(rows),          # scored tasks only (errored ones excluded)
        "n_total": n_total,
        # deterministic = every check except the judge's 'grounded'; used to compare v1 vs v2
        "pass_rate_deterministic": sum(deterministic_pass(r) for r in rows) / max(1, len(rows)),
        # incl. judge = deterministic AND grounded; only meaningful when the run had a judge
        "pass_rate": sum(r["passed"] for r in rows) / max(1, len(rows)),
        "judged": bool(meta.get("judge")),
        "by_category": {c: {"rate": sum(v) / len(v), "n": len(v)} for c, v in sorted(by_cat.items())},
        "checks": check_rates,
        "latency_p50_s": pct(lat, 0.5),
        "latency_p95_s": pct(lat, 0.95),
        "avg_tool_calls": statistics.mean(r["n_tool_calls"] for r in rows) if rows else 0,
        "avg_tokens": statistics.mean(r["tokens"]["input"] + r["tokens"]["output"] for r in rows) if rows else 0,
        "errors": len(errored),
        "errored_ids": [r["id"] for r in errored],
        "failed_ids": [r["id"] for r in rows if not deterministic_pass(r)],
        "failed_ids_incl_judge": [r["id"] for r in rows if not r["passed"]],
    }


def write_report(summary, rows, path):
    s = summary
    incl_judge = f"{s['pass_rate']:.0%}" if s.get("judged") else "–"
    L = [f"# ResearchMind eval — `{s['model']}` / agent `{s['agent_version']}`", "",
         f"Run `{s['run_id']}` · {s['n_tasks']} scored tasks of {s['n_total']}", "",
         "| Metric | Value |", "|---|---|",
         f"| **Pass rate (deterministic)** | **{s['pass_rate_deterministic']:.0%}** |",
         f"| Pass rate (incl. judge) | {incl_judge} |",
         f"| Judge model | {s.get('judge') or '–'} |",
         f"| Latency p50 / p95 | {s['latency_p50_s']:.1f}s / {s['latency_p95_s']:.1f}s |",
         f"| Avg tool calls | {s['avg_tool_calls']:.2f} |",
         f"| Avg tokens / task | {s['avg_tokens']:.0f} |",
         f"| Errors | {s['errors']} (excluded){': ' + ', '.join(s['errored_ids']) if s['errored_ids'] else ''} |", "",
         "## By category", "", "| Category | Pass | n |", "|---|---|---|"]
    L += [f"| {c} | {v['rate']:.0%} | {v['n']} |" for c, v in s["by_category"].items()]
    L += ["", "## By check", "", "| Check | Pass | n |", "|---|---|---|"]
    L += [f"| {c} | {v['rate']:.0%} | {v['n']} |" for c, v in s["checks"].items()]
    L += ["", "## Failures", ""]
    for r in rows:
        if r["passed"] or r.get("error"):
            continue
        bad = [k for k, v in r["checks"].items() if v is False]
        L += [f"### {r['id']} ({r['category']}) — failed: {', '.join(bad) or r.get('error', '?')}",
              f"**Q:** {r['question']}  ",
              f"**Tools:** {' → '.join(r['tools']) or '(none)'}  ",
              f"**Answer:** {(r['answer'] or '(empty)')[:400].replace(chr(10), ' ')}", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def evaluate_task(task, model, version, llm_pair=None, judge_llm=None):
    """Run and score one task. Returns (row, trace).

    row["error"] is set when an API call failed (agent or judge); such rows are
    excluded from pass rates by summarise() and can be re-run with --rerun-errors.
    """
    from agent import run_agent
    err = None
    try:
        trace = with_retry(lambda: run_agent(task["question"], model=model,
                                             version=version, llm_pair=llm_pair))
    except Exception as e:
        trace = {"answer": "", "steps": [], "tokens": {"input": 0, "output": 0},
                 "latency_s": 0, "iterations": 0, "hit_iteration_budget": False}
        err = f"{type(e).__name__}: {e}"
    result = score(task, trace)
    if judge_llm is not None and not err and not task["expect"].get("abstain"):
        try:
            g = with_retry(lambda: judge_grounded(trace, judge_llm))
        except Exception as e:
            err = f"JudgeError: {type(e).__name__}: {e}"
        else:
            result["checks"]["grounded"] = g["grounded"]
            trace["judge"] = g
            if g["grounded"] is False:
                result["passed"] = False
    row = {"id": task["id"], "category": task["category"], "question": task["question"],
           "answer": trace["answer"], "tools": [s["tool"] for s in trace["steps"]],
           "n_tool_calls": len(trace["steps"]), "tokens": trace["tokens"],
           "latency_s": trace["latency_s"], "checks": result["checks"],
           "passed": result["passed"], "error": err}
    return row, trace


def rerun_errors(run_dir, tasks_path, delay=2.0, llm_pair=None, judge_llm=None):
    """Re-run only the errored tasks of an existing run, replace their rows, re-summarise.

    Model, agent version and judge model come from the run's own summary.json.
    """
    run_dir = os.path.abspath(os.path.join(START_CWD, run_dir))
    old = json.load(open(os.path.join(run_dir, "summary.json"), encoding="utf-8"))
    meta = {k: old[k] for k in ("run_id", "model", "agent_version", "judge")}
    trace_path = os.path.join(run_dir, "traces.jsonl")
    records = [json.loads(line) for line in open(trace_path, encoding="utf-8")]
    todo = [i for i, r in enumerate(records) if r.get("error")]
    if not todo:
        print(f"No errored tasks in {meta['run_id']}; nothing to re-run.")
        return old

    tasks_by_id = {t["id"]: t for t in json.load(open(tasks_path, encoding="utf-8"))}
    ensure_fixture()
    if meta["judge"] and judge_llm is None:
        from langchain_groq import ChatGroq
        judge_llm = ChatGroq(model=meta["judge"], temperature=0)

    print(f"Re-running {len(todo)} errored task(s) of {meta['run_id']}: "
          f"{', '.join(records[i]['id'] for i in todo)}")
    for n, i in enumerate(todo, 1):
        task = tasks_by_id[records[i]["id"]]
        print(f"[{n}/{len(todo)}] {task['id']}: {task['question']}")
        row, trace = evaluate_task(task, meta["model"], meta["agent_version"], llm_pair,
                                   judge_llm if meta["judge"] else None)
        records[i] = {**row, "trace": trace}
        print(f"   {'PASS' if row['passed'] else 'FAIL'}  tools={row['tools']}"
              + (f"  error={row['error']}" if row["error"] else ""))
        if n < len(todo) and delay:
            time.sleep(delay)

    tmp = trace_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, trace_path)

    rows = [{k: v for k, v in r.items() if k != "trace"} for r in records]
    summary = summarise(rows, meta)
    json.dump(summary, open(os.path.join(run_dir, "summary.json"), "w"), indent=2)
    write_report(summary, rows, os.path.join(run_dir, "report.md"))
    incl = f"{summary['pass_rate']:.0%}" if summary["judged"] else "–"
    print(f"\nPass rate (deterministic): {summary['pass_rate_deterministic']:.0%}  "
          f"(incl. judge: {incl}), errors remaining: {summary['errors']}  ->  {run_dir}/report.md")
    return summary


def main(argv=None, llm_pair=None, judge_llm=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.getenv("RM_MODEL", "openai/gpt-oss-20b"))
    ap.add_argument("--agent-version", default="v1", choices=["v1", "v2"])
    ap.add_argument("--tasks", default=os.path.join(EVALS, "tasks.json"))
    ap.add_argument("--only", help="comma-separated categories")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between tasks (free-tier rate limits)")
    ap.add_argument("--judge", action="store_true", help="add LLM-as-judge groundedness check")
    ap.add_argument("--judge-model", default="qwen/qwen3.8-27b")
    ap.add_argument("--out", default=os.path.join(EVALS, "runs"))
    ap.add_argument("--rerun-errors", metavar="RUN_DIR",
                    help="re-run only the errored tasks of an existing run and re-summarise it")
    args = ap.parse_args(argv)

    if args.rerun_errors:
        return rerun_errors(args.rerun_errors, args.tasks, args.delay, llm_pair, judge_llm)

    ensure_fixture()

    tasks = json.load(open(args.tasks, encoding="utf-8"))
    if args.only:
        cats = set(args.only.split(","))
        tasks = [t for t in tasks if t["category"] in cats]
    if args.limit:
        tasks = tasks[: args.limit]

    if args.judge and judge_llm is None:
        from langchain_groq import ChatGroq
        judge_llm = ChatGroq(model=args.judge_model, temperature=0)

    run_id = f"{datetime.now():%Y%m%d-%H%M%S}_{args.model.replace('/', '-')}_{args.agent_version}"
    run_dir = os.path.join(args.out, run_id)
    os.makedirs(run_dir, exist_ok=True)

    rows = []
    with open(os.path.join(run_dir, "traces.jsonl"), "w", encoding="utf-8") as tf:
        for i, task in enumerate(tasks, 1):
            print(f"[{i}/{len(tasks)}] {task['id']}: {task['question']}")
            row, trace = evaluate_task(task, args.model, args.agent_version, llm_pair,
                                       judge_llm if args.judge else None)
            err = row["error"]
            rows.append(row)
            tf.write(json.dumps({**row, "trace": trace}, ensure_ascii=False) + "\n")
            print(f"   {'PASS' if row['passed'] else 'FAIL'}  tools={row['tools']}"
                  + (f"  error={err}" if err else ""))
            if i < len(tasks) and args.delay:
                time.sleep(args.delay)

    meta = {"run_id": run_id, "model": args.model, "agent_version": args.agent_version,
            "judge": args.judge_model if args.judge else None, "scorer_version": SCORER_VERSION}
    summary = summarise(rows, meta)
    json.dump(summary, open(os.path.join(run_dir, "summary.json"), "w"), indent=2)
    write_report(summary, rows, os.path.join(run_dir, "report.md"))
    incl = f"{summary['pass_rate']:.0%}" if summary["judged"] else "–"
    print(f"\nPass rate (deterministic): {summary['pass_rate_deterministic']:.0%}  "
          f"(incl. judge: {incl})  ->  {run_dir}/report.md")
    return summary


if __name__ == "__main__":
    main()
