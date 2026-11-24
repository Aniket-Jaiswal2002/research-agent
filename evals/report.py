"""Compare eval runs side by side.

    python evals/report.py evals/runs/*/summary.json > evals/RESULTS.md
"""
import json
import sys


def main(paths):
    runs = [json.load(open(p)) for p in paths]
    if not runs:
        print("usage: python evals/report.py <summary.json> ...")
        return
    head = ["Metric"] + [f"{r['model']} · {r['agent_version']}" for r in runs]
    T = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]

    def row(name, fn):
        T.append("| " + " | ".join([name] + [fn(r) for r in runs]) + " |")

    # Compare v1 vs v2 on the deterministic rate only; groundedness (judge) is reported separately.
    row("**Pass rate (deterministic)**", lambda r: f"**{r['pass_rate_deterministic']:.0%}**")
    row("Passed / scored", lambda r: f"{round(r['pass_rate_deterministic'] * r['n_tasks'])} / {r['n_tasks']}")
    row("Pass rate excl. citation checks", lambda r: f"{r['pass_rate_excl_citations']:.0%}" if "pass_rate_excl_citations" in r else "–")
    row("Pass rate (incl. judge)", lambda r: f"{r['pass_rate']:.0%}" if r.get("judged") else "–")
    row("Judge model", lambda r: r.get("judge") or "–")
    cats = sorted({c for r in runs for c in r["by_category"]})
    for c in cats:
        row(f"{c}", lambda r, c=c: f"{r['by_category'][c]['rate']:.0%}" if c in r["by_category"] else "–")
    checks = sorted({c for r in runs for c in r["checks"]})
    for c in checks:
        label = "groundedness (judge, separate)" if c == "grounded" else f"check: {c}"
        row(label, lambda r, c=c: f"{r['checks'][c]['rate']:.0%}" if c in r["checks"] else "–")
    row("Latency p50 / p95", lambda r: f"{r['latency_p50_s']:.1f}s / {r['latency_p95_s']:.1f}s")
    row("Avg tool calls", lambda r: f"{r['avg_tool_calls']:.2f}")
    row("Avg tokens / task", lambda r: f"{r['avg_tokens']:.0f}")
    row("Tasks scored", lambda r: f"{r['n_tasks']} of {r.get('n_total', r['n_tasks'])}")
    row("Infra errors (excluded)", lambda r: (f"{r['errors']}: " + ", ".join(r.get("errored_ids", []))) if r.get("errors") else "0")
    row("Model errors (counted as fail)", lambda r: (f"{r['model_errors']}: " + ", ".join(r.get("model_error_ids", []))) if r.get("model_errors") else "0")

    out = ["# ResearchMind eval results", ""]
    incomplete = [r for r in runs if r.get("n_expected", r["n_total"]) > r["n_total"]]
    for r in incomplete:
        out += [f"> **Incomplete run:** `{r['run_id']}` has {r['n_total']} of {r['n_expected']} tasks.", ""]
    out += T
    versions = sorted({str(r.get("scorer_version", 1)) for r in runs})
    judges = sorted({r["judge"] for r in runs if r.get("judge")})
    out += ["", "## How to read this", "",
            "- **Pass rate (deterministic)** is the fraction of tasks where every applicable check passed, "
            "except the LLM judge's groundedness. Compare v1 vs v2 on this row only.",
            "- **Groundedness** is the judge's verdict on whether the answer is supported by the tool results; "
            "it is reported separately and only exists for judged runs. "
            + (f"Judge model(s): {', '.join(f'`{j}`' for j in judges)}; each differs from the model under test."
               if judges else "No run here used a judge."),
            "- **Pass rate excl. citation checks** drops `cites_source`, `web_cited` and `correct_page_cited`."
            + (" **Agent v3 appends citations in code, so those three checks rise without the answers improving: "
               "compare v3 with v1/v2 on this row and on the accuracy checks (`facts`, `retrieval_hit`, `abstained`), "
               "not on the citation checks.**" if any(r.get("agent_version") == "v3" for r in runs) else ""),
            "- **Infra errors** (429, 5xx, timeouts, ...) are excluded from every rate; **model errors** "
            "(HTTP 400 such as `output_parse_failed`) count as failures. See `evals/README.md`.",
            "- 31 tasks; each task ≈ 3 points. Differences under ~10 points are within run-to-run variance.",
            f"- Scorer version(s): {', '.join(versions)} (see `evals/SCORER_CHANGELOG.md`)."
            + (" **Mixed scorer versions: do not compare these runs.**" if len(versions) > 1 else "")]
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1:])
