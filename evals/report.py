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

    row("**Overall pass rate**", lambda r: f"**{r['pass_rate']:.0%}**")
    cats = sorted({c for r in runs for c in r["by_category"]})
    for c in cats:
        row(f"{c}", lambda r, c=c: f"{r['by_category'][c]['rate']:.0%}" if c in r["by_category"] else "–")
    checks = sorted({c for r in runs for c in r["checks"]})
    for c in checks:
        row(f"check: {c}", lambda r, c=c: f"{r['checks'][c]['rate']:.0%}" if c in r["checks"] else "–")
    row("Latency p50 / p95", lambda r: f"{r['latency_p50_s']:.1f}s / {r['latency_p95_s']:.1f}s")
    row("Avg tool calls", lambda r: f"{r['avg_tool_calls']:.2f}")
    row("Avg tokens / task", lambda r: f"{r['avg_tokens']:.0f}")
    row("Tasks", lambda r: str(r["n_tasks"]))
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1:])
