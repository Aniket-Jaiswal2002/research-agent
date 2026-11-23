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
    L = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]

    def row(name, fn):
        L.append("| " + " | ".join([name] + [fn(r) for r in runs]) + " |")

    # Compare v1 vs v2 on the deterministic rate only; groundedness (judge) is reported separately.
    row("**Pass rate (deterministic)**", lambda r: f"**{r['pass_rate_deterministic']:.0%}**")
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
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1:])
