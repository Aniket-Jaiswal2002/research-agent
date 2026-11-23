"""Run the ResearchMind eval suite.

    python evals/run_evals.py --model openai/gpt-oss-20b --agent-version v1
    python evals/run_evals.py --model openai/gpt-oss-120b --agent-version v2 --judge
    python evals/run_evals.py --only pdf_fact,injection --limit 5
    python evals/run_evals.py --resume evals/runs/<run_dir> --stop-on-infra-error
    python evals/run_evals.py --rerun-errors evals/runs/<run_dir>

Writes evals/runs/<run>/{meta.json, traces.jsonl, summary.json, report.md}.
Compare runs with:  python evals/report.py evals/runs/*/summary.json

Error policy (see scorers.classify_error):
  infra  errors (429, 5xx, timeouts, connection, ...) are EXCLUDED from pass rates;
         --rerun-errors re-runs them.
  model  errors (HTTP 400 such as output_parse_failed) COUNT AS FAILURES and are never re-run.
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
START_CWD = os.getcwd()  # relative CLI paths (e.g. --resume) resolve against this
os.chdir(ROOT)  # vector_store/ paths are relative to the repo root

from scorers import SCORER_VERSION, classify_error, judge_grounded, score  # noqa: E402

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


def error_class(row):
    """None, "infra" (excluded from rates) or "model" (counts as a failure)."""
    return classify_error(row.get("error"))


def summarise(rows, meta):
    # infra errors (rate limit, outage) say nothing about the agent: excluded from every rate.
    # model errors (e.g. output_parse_failed) are agent failures: kept, and they score as FAIL
    # because the empty trace they leave behind fails the completed/first_tool/... checks.
    infra = [r for r in rows if error_class(r) == "infra"]
    model_err = [r for r in rows if error_class(r) == "model"]
    n_total = len(rows)
    rows = [r for r in rows if error_class(r) != "infra"]
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(deterministic_pass(r))
    check_names = sorted({k for r in rows for k in r["checks"]})
    check_rates = {}
    for k in check_names:
        vals = [r["checks"][k] for r in rows if r["checks"].get(k) is not None]
        if vals:
            check_rates[k] = {"rate": sum(vals) / len(vals), "n": len(vals)}
    ok = [r for r in rows if not r.get("error")]  # latency/tokens only make sense for completed tasks
    lat = [r["latency_s"] for r in ok]
    return {
        **meta,
        "n_tasks": len(rows),          # scored tasks: everything except infra errors
        "n_total": n_total,            # tasks that have a row at all
        # deterministic = every check except the judge's 'grounded'; used to compare v1 vs v2
        "pass_rate_deterministic": sum(deterministic_pass(r) for r in rows) / max(1, len(rows)),
        # incl. judge = deterministic AND grounded; only meaningful when the run had a judge
        "pass_rate": sum(r["passed"] for r in rows) / max(1, len(rows)),
        "judged": bool(meta.get("judge")),
        "by_category": {c: {"rate": sum(v) / len(v), "n": len(v)} for c, v in sorted(by_cat.items())},
        "checks": check_rates,
        "latency_p50_s": pct(lat, 0.5),
        "latency_p95_s": pct(lat, 0.95),
        "avg_tool_calls": statistics.mean(r["n_tool_calls"] for r in ok) if ok else 0,
        "avg_tokens": statistics.mean(r["tokens"]["input"] + r["tokens"]["output"] for r in ok) if ok else 0,
        "errors": len(infra),                              # infra errors, excluded
        "errored_ids": [r["id"] for r in infra],
        "model_errors": len(model_err),                    # counted as FAIL
        "model_error_ids": [r["id"] for r in model_err],
        "failed_ids": [r["id"] for r in rows if not deterministic_pass(r)],
        "failed_ids_incl_judge": [r["id"] for r in rows if not r["passed"]],
    }


def write_report(summary, rows, path):
    s = summary
    incl_judge = f"{s['pass_rate']:.0%}" if s.get("judged") else "–"
    expected = s.get("n_expected", s["n_total"])
    progress = "" if expected == s["n_total"] else f" · **INCOMPLETE: {s['n_total']} of {expected} tasks ran**"
    infra_ids = f": {', '.join(s['errored_ids'])}" if s["errored_ids"] else ""
    model_ids = f": {', '.join(s['model_error_ids'])}" if s["model_error_ids"] else ""
    L = [f"# ResearchMind eval — `{s['model']}` / agent `{s['agent_version']}`", "",
         f"Run `{s['run_id']}` · {s['n_tasks']} scored tasks of {s['n_total']}{progress}", "",
         "| Metric | Value |", "|---|---|",
         f"| **Pass rate (deterministic)** | **{s['pass_rate_deterministic']:.0%}** |",
         f"| Pass rate (incl. judge) | {incl_judge} |",
         f"| Judge model | {s.get('judge') or '–'} |",
         f"| Latency p50 / p95 | {s['latency_p50_s']:.1f}s / {s['latency_p95_s']:.1f}s |",
         f"| Avg tool calls | {s['avg_tool_calls']:.2f} |",
         f"| Avg tokens / task | {s['avg_tokens']:.0f} |",
         f"| Infra errors (excluded) | {s['errors']}{infra_ids} |",
         f"| Model errors (counted as fail) | {s.get('model_errors', 0)}{model_ids} |", "",
         "## By category", "", "| Category | Pass | n |", "|---|---|---|"]
    L += [f"| {c} | {v['rate']:.0%} | {v['n']} |" for c, v in s["by_category"].items()]
    L += ["", "## By check", "", "| Check | Pass | n |", "|---|---|---|"]
    L += [f"| {c} | {v['rate']:.0%} | {v['n']} |" for c, v in s["checks"].items()]
    L += ["", "## Failures", ""]
    for r in rows:
        if r["passed"] or error_class(r) == "infra":
            continue
        bad = [k for k, v in r["checks"].items() if v is False]
        why = ", ".join(bad)
        if error_class(r) == "model":
            why = f"MODEL ERROR ({r['error'][:140]})"
        L += [f"### {r['id']} ({r['category']}) — failed: {why or '?'}",
              f"**Q:** {r['question']}  ",
              f"**Tools:** {' → '.join(r['tools']) or '(none)'}  ",
              f"**Answer:** {(r['answer'] or '(empty)')[:400].replace(chr(10), ' ')}", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def evaluate_task(task, model, version, llm_pair=None, judge_llm=None):
    """Run and score one task. Returns (row, trace).

    row["error"] is set when an API call failed (agent or judge); error_class(row) says whether
    it is an infra error (excluded from rates) or a model error (counted as a failure).
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


def _load_tasks(path):
    return json.load(open(path, encoding="utf-8"))


def _read_records(run_dir):
    with open(os.path.join(run_dir, "traces.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_records(run_dir, records):
    path = os.path.join(run_dir, "traces.jsonl")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _strip(records):
    return [{k: v for k, v in r.items() if k not in ("trace", "prev_scoring")} for r in records]


def load_run_meta(run_dir):
    """meta.json (written when a run starts) or, for older runs, the keys of summary.json."""
    for name in ("meta.json", "summary.json"):
        p = os.path.join(run_dir, name)
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            keep = ("run_id", "model", "agent_version", "judge", "scorer_version", "n_expected")
            return {k: d[k] for k in keep if k in d}
    return None


def _finish(run_dir, rows, meta, label):
    """Write summary.json + report.md for `rows` and print the headline."""
    summary = summarise(rows, meta)
    json.dump(summary, open(os.path.join(run_dir, "summary.json"), "w"), indent=2)
    write_report(summary, rows, os.path.join(run_dir, "report.md"))
    incl = f"{summary['pass_rate']:.0%}" if summary["judged"] else "–"
    print(f"\n{label}: pass rate (deterministic) {summary['pass_rate_deterministic']:.0%} "
          f"(incl. judge: {incl}) · infra errors {summary['errors']} (excluded) · "
          f"model errors {summary['model_errors']} (fail)  ->  {run_dir}/report.md")
    return summary


def _judge_for(meta, judge_llm):
    if meta.get("judge") and judge_llm is None:
        from langchain_groq import ChatGroq
        judge_llm = ChatGroq(model=meta["judge"], temperature=0)
    return judge_llm if meta.get("judge") else None


def rerun_errors(run_dir, tasks_path, delay=2.0, llm_pair=None, judge_llm=None):
    """Re-run only the INFRA-errored tasks of an existing run, replace their rows, re-summarise.

    Model errors (e.g. output_parse_failed) are results, not outages, and are left alone.
    Model, agent version and judge model come from the run's own meta.json / summary.json.
    """
    run_dir = os.path.abspath(os.path.join(START_CWD, run_dir))
    meta = load_run_meta(run_dir)
    records = _read_records(run_dir)
    todo = [i for i, r in enumerate(records) if error_class(r) == "infra"]
    if not todo:
        print(f"No infra-errored tasks in {meta['run_id']}; nothing to re-run.")
        return json.load(open(os.path.join(run_dir, "summary.json"), encoding="utf-8"))

    tasks_by_id = {t["id"]: t for t in _load_tasks(tasks_path)}
    ensure_fixture()
    judge = _judge_for(meta, judge_llm)

    print(f"Re-running {len(todo)} infra-errored task(s) of {meta['run_id']}: "
          f"{', '.join(records[i]['id'] for i in todo)}")
    for n, i in enumerate(todo, 1):
        task = tasks_by_id[records[i]["id"]]
        print(f"[{n}/{len(todo)}] {task['id']}: {task['question']}")
        row, trace = evaluate_task(task, meta["model"], meta["agent_version"], llm_pair, judge)
        records[i] = {**row, "trace": trace}
        print(f"   {'PASS' if row['passed'] else 'FAIL'}  tools={row['tools']}"
              + (f"  error={row['error']}" if row["error"] else ""))
        if n < len(todo) and delay:
            time.sleep(delay)

    _write_records(run_dir, records)
    return _finish(run_dir, _strip(records), meta, "Re-run")


def resume(run_dir, tasks_path, delay=2.0, stop_on_infra_error=False, cli=None,
           llm_pair=None, judge_llm=None):
    """Run only the tasks that have no row in traces.jsonl yet, with the original settings.

    Settings come from meta.json / summary.json. A run that was killed before writing either has
    none, so `cli` (model, agent_version, judge) must be given and must agree with the run folder name.
    Existing rows (including errored ones) are never touched.
    """
    run_dir = os.path.abspath(os.path.join(START_CWD, run_dir))
    records = _read_records(run_dir)
    tasks = _load_tasks(tasks_path)
    order = {t["id"]: i for i, t in enumerate(tasks)}
    done = {r["id"] for r in records}
    if done - set(order):
        raise SystemExit(f"traces.jsonl has tasks that are not in {tasks_path}: {sorted(done - set(order))}")

    meta = load_run_meta(run_dir)
    if meta is None:
        if not cli:
            raise SystemExit("No meta.json/summary.json in the run folder: pass --model, --agent-version "
                             "(and --judge --judge-model) to say how the run was started.")
        suffix = f"_{cli['model'].replace('/', '-')}_{cli['agent_version']}"
        if not os.path.basename(run_dir).endswith(suffix):
            raise SystemExit(f"--model/--agent-version ({suffix.lstrip('_')}) do not match the run folder "
                             f"name {os.path.basename(run_dir)}")
        graded = any("grounded" in r["checks"] for r in records)
        if bool(cli["judge"]) != graded:
            raise SystemExit(f"--judge {'given' if cli['judge'] else 'missing'}, but the saved rows "
                             f"{'have' if graded else 'have no'} judge verdicts")
        meta = {"run_id": os.path.basename(run_dir), "model": cli["model"],
                "agent_version": cli["agent_version"], "judge": cli["judge"]}
    meta["scorer_version"] = SCORER_VERSION
    meta["n_expected"] = len(tasks)

    missing = [t for t in tasks if t["id"] not in done]
    json.dump(meta, open(os.path.join(run_dir, "meta.json"), "w"), indent=2)
    if not missing:
        print(f"{meta['run_id']} already has all {len(tasks)} tasks; nothing to resume.")
        return _finish(run_dir, _strip(records), meta, "Resume")

    ensure_fixture()
    judge = _judge_for(meta, judge_llm)
    print(f"Resuming {meta['run_id']}: {len(done)} done, {len(missing)} to run "
          f"({', '.join(t['id'] for t in missing)})")
    stopped = False
    with open(os.path.join(run_dir, "traces.jsonl"), "a", encoding="utf-8") as tf:
        for i, task in enumerate(missing, 1):
            print(f"[{i}/{len(missing)}] {task['id']}: {task['question']}")
            row, trace = evaluate_task(task, meta["model"], meta["agent_version"], llm_pair, judge)
            records.append({**row, "trace": trace})
            tf.write(json.dumps({**row, "trace": trace}, ensure_ascii=False) + "\n")
            tf.flush()
            print(f"   {'PASS' if row['passed'] else 'FAIL'}  tools={row['tools']}"
                  + (f"  [{error_class(row)} error] {row['error']}" if row["error"] else ""))
            if stop_on_infra_error and error_class(row) == "infra":
                print(f"STOPPED on infra error after {len(done) + i} of {len(tasks)} tasks.")
                stopped = True
                break
            if i < len(missing) and delay:
                time.sleep(delay)

    records.sort(key=lambda r: order[r["id"]])
    summary = _finish(run_dir, _strip(records), meta, "Resume (stopped early)" if stopped else "Resume")
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
    ap.add_argument("--stop-on-infra-error", action="store_true",
                    help="stop the run at the first infra error (429, 5xx, timeout, ...)")
    ap.add_argument("--rerun-errors", metavar="RUN_DIR",
                    help="re-run only the infra-errored tasks of an existing run and re-summarise it")
    ap.add_argument("--resume", metavar="RUN_DIR",
                    help="run only the tasks missing from traces.jsonl, with the run's original settings "
                         "(--model/--agent-version/--judge are only needed if the run has no meta.json)")
    args = ap.parse_args(argv)

    if args.rerun_errors:
        return rerun_errors(args.rerun_errors, args.tasks, args.delay, llm_pair, judge_llm)
    if args.resume:
        cli = {"model": args.model, "agent_version": args.agent_version,
               "judge": args.judge_model if args.judge else None}
        return resume(args.resume, args.tasks, args.delay, args.stop_on_infra_error, cli, llm_pair, judge_llm)

    ensure_fixture()

    tasks = _load_tasks(args.tasks)
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
    meta = {"run_id": run_id, "model": args.model, "agent_version": args.agent_version,
            "judge": args.judge_model if args.judge else None, "scorer_version": SCORER_VERSION,
            "n_expected": len(tasks)}
    json.dump(meta, open(os.path.join(run_dir, "meta.json"), "w"), indent=2)  # lets --resume work after a kill

    rows = []
    with open(os.path.join(run_dir, "traces.jsonl"), "w", encoding="utf-8") as tf:
        for i, task in enumerate(tasks, 1):
            print(f"[{i}/{len(tasks)}] {task['id']}: {task['question']}")
            row, trace = evaluate_task(task, args.model, args.agent_version, llm_pair,
                                       judge_llm if args.judge else None)
            err = row["error"]
            rows.append(row)
            tf.write(json.dumps({**row, "trace": trace}, ensure_ascii=False) + "\n")
            tf.flush()
            print(f"   {'PASS' if row['passed'] else 'FAIL'}  tools={row['tools']}"
                  + (f"  [{error_class(row)} error] {err}" if err else ""))
            if args.stop_on_infra_error and error_class(row) == "infra":
                print(f"STOPPED on infra error after {i} of {len(tasks)} tasks "
                      f"(continue later with --resume {run_dir}).")
                break
            if i < len(tasks) and args.delay:
                time.sleep(args.delay)

    return _finish(run_dir, rows, meta, "Pass rate")


if __name__ == "__main__":
    main()
