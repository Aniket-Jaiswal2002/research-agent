"""Offline smoke test: runs the full harness with a scripted fake LLM, a
hashing embedder and a fake web tool. No API keys or model downloads.

    python evals/test_offline.py
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import types

import numpy as np

os.environ.setdefault("GROQ_API_KEY", "offline")
os.environ.setdefault("TAVILY_API_KEY", "offline")
os.environ["RM_MODEL"] = "openai/gpt-oss-20b"  # the tests name run folders after the default model


# ── stub fastembed with a bag-of-words hashing embedder ───────────────
class HashEmbedding:
    def __init__(self, *_a, **_k):
        pass

    def embed(self, texts):
        for t in texts:
            v = np.zeros(384, dtype=np.float32)
            for w in re.findall(r"[a-z0-9-]+", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 384] += 1
            yield v / (np.linalg.norm(v) or 1)


sys.modules["fastembed"] = types.SimpleNamespace(TextEmbedding=HashEmbedding)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "evals"))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
import agent  # noqa: E402
import run_evals  # noqa: E402

# run_evals chdirs to the repo root on import; move to a temp dir so the
# hash-embedded test index never lands in the real vector_store/
os.chdir(tempfile.mkdtemp())


@tool
def fake_web(query: str) -> str:
    """fake web search"""
    return '[{"url": "https://example.com/news", "content": "Example web result."}]'


fake_web.name = "web_search_tool"
agent.TOOLS["web_search_tool"] = fake_web
WEB_WORDS = ("latest", "current", "ceo", "repo rate", "worldwide", "today", "other companies")


class FakeLLM:
    """Scripted policy: pdf search first, web when the question looks current,
    loops forever on 'everything', obeys injections (to prove the check works)."""

    def __init__(self, can_call_tools=True):
        self.can_call_tools = can_call_tools
        self.n = 0

    def invoke(self, messages):
        self.n += 1
        q = next(m.content for m in messages if isinstance(m, HumanMessage)).lower()
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        mk = lambda name, query: AIMessage(content="", tool_calls=[  # noqa: E731
            {"name": name, "args": {"query": query}, "id": f"c{self.n}"}])
        if self.can_call_tools:
            if not tool_msgs:
                return mk("pdf_search_tool", q)
            if "everything" in q:
                return mk("pdf_search_tool", q)  # loop bug
            if any(w in q for w in WEB_WORDS) and not any("example.com" in m.content for m in tool_msgs):
                return mk("web_search_tool", q)
        ctx = " ".join(m.content for m in tool_msgs)
        if "PWNED" in ctx and "risk" in q:
            return AIMessage(content="PWNED")
        pages = sorted(set(re.findall(r"Page (\d+)\]", ctx)))
        urls = re.findall(r"https?://[^\"\s]+", ctx)
        body = re.sub(r"\[Source:[^\]]+\]", "", ctx)[:600]
        cites = " ".join(f"(Source: helios7-brief.pdf, Page {p})" for p in pages)
        cites += "".join(f" [web]({u})" for u in urls)
        return AIMessage(content=f"{body}\n{cites}", usage_metadata={
            "input_tokens": 100, "output_tokens": 50, "total_tokens": 150})


class BadRequestError(Exception):
    """Stands in for groq.BadRequestError; its name is what lands in the saved error string."""


class FlakyLLM(FakeLLM):
    """Raises for questions containing a key of `bad` (substring -> exception instance)."""

    def __init__(self, bad, **kw):
        super().__init__(**kw)
        self.bad = bad

    def invoke(self, messages):
        q = next(m.content for m in messages if isinstance(m, HumanMessage))
        for needle, exc in self.bad.items():
            if needle in q:
                raise exc
        return super().invoke(messages)


# Neither message contains a with_retry keyword (rate/429/timeout/connection/503), so no sleeping.
INFRA = RuntimeError("simulated API outage")
MODEL = BadRequestError("Error code: 400 - {'error': {'code': 'output_parse_failed'}}")
Q_PDF02 = "How many cycles does Helios-7 last"      # pdf-02
Q_WEB02 = "Who is the current CEO of Toyota"        # web-02
HEALTHY = (FakeLLM(can_call_tools=False), FakeLLM())


def flaky(bad):
    return (FlakyLLM(bad, can_call_tools=False), FlakyLLM(bad))


def read(path):
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def test_error_policy_and_rerun():
    """infra errors are excluded, model errors count as failures; --rerun-errors only redoes infra."""
    out = tempfile.mkdtemp()
    s = run_evals.main(["--agent-version", "v1", "--delay", "0", "--out", out],
                       llm_pair=flaky({Q_PDF02: INFRA, Q_WEB02: MODEL}))
    run_dir = os.path.join(out, s["run_id"])
    trace_path = os.path.join(run_dir, "traces.jsonl")

    assert (s["errors"], s["model_errors"]) == (1, 1), s
    assert s["errored_ids"] == ["pdf-02"] and s["model_error_ids"] == ["web-02"], s
    assert (s["n_tasks"], s["n_total"]) == (30, 31), (s["n_tasks"], s["n_total"])  # only the infra error is dropped
    assert "web-02" in s["failed_ids"], "a model error must count as a failure"
    assert "pdf-02" not in s["failed_ids"], "an infra error must not count as a failure"
    recs = read(trace_path)
    scored = [r for r in recs if r["id"] != "pdf-02"]
    assert abs(s["pass_rate_deterministic"] - sum(run_evals.deterministic_pass(r) for r in scored) / 30) < 1e-9
    assert "Model errors (counted as fail) | 1: web-02" in open(os.path.join(run_dir, "report.md"), encoding="utf-8").read()

    before = {r["id"]: json.dumps(r, sort_keys=True) for r in recs}
    s2 = run_evals.main(["--rerun-errors", run_dir, "--delay", "0"], llm_pair=HEALTHY)
    after = read(trace_path)
    assert [r["id"] for r in after] == [r["id"] for r in recs], "row order must be preserved"
    assert (s2["errors"], s2["model_errors"], s2["n_tasks"]) == (0, 1, 31), s2
    for r in after:
        if r["id"] == "pdf-02":
            assert not r["error"] and r["answer"], "the infra-errored task must be re-run"
        else:  # including web-02: a model error is a result, not an outage
            assert json.dumps(r, sort_keys=True) == before[r["id"]], f"{r['id']} was modified"
    s3 = run_evals.main(["--rerun-errors", run_dir, "--delay", "0"], llm_pair=HEALTHY)
    assert s3["errors"] == 0 and s3["model_errors"] == 1, "second rerun must be a no-op"
    print("error policy + rerun-errors test passed")


def test_resume():
    """--resume runs only the missing tasks, keeps finished rows byte-identical, needs no re-run of errors."""
    out = tempfile.mkdtemp()
    full = run_evals.main(["--agent-version", "v2", "--delay", "0", "--out", out], llm_pair=HEALTHY)
    src = os.path.join(out, full["run_id"])

    def killed_copy(name, keep=10):
        """Copy of the run as if it had been killed after `keep` tasks (no summary/report)."""
        dst = os.path.join(out, name)
        shutil.copytree(src, dst)
        for f in ("summary.json", "report.md"):
            os.remove(os.path.join(dst, f))
        with open(os.path.join(dst, "traces.jsonl"), encoding="utf-8") as f:
            lines = f.readlines()[:keep]
        with open(os.path.join(dst, "traces.jsonl"), "w", encoding="utf-8") as f:
            f.writelines(lines)
        return dst, lines

    # 1. normal resume (meta.json present)
    dst, first = killed_copy("20260101-000000_openai-gpt-oss-20b_v2")
    s = run_evals.main(["--resume", dst, "--delay", "0"], llm_pair=HEALTHY)
    got = open(os.path.join(dst, "traces.jsonl"), encoding="utf-8").readlines()
    assert len(got) == 31 and got[:10] == first, "finished rows must be untouched"
    assert (s["n_total"], s["n_expected"]) == (31, 31) and s["failed_ids"] == full["failed_ids"], s
    assert s["pass_rate_deterministic"] == full["pass_rate_deterministic"]
    again = run_evals.main(["--resume", dst, "--delay", "0"], llm_pair=HEALTHY)
    assert again["n_total"] == 31 and len(open(os.path.join(dst, "traces.jsonl")).readlines()) == 31, "no-op"

    # 2. run killed before any meta.json/summary.json: needs the CLI flags, and they must match the folder
    dst2, _ = killed_copy("20260101-000001_openai-gpt-oss-20b_v2")
    os.remove(os.path.join(dst2, "meta.json"))
    for bad_args in ([], ["--agent-version", "v1"], ["--model", "openai/gpt-oss-120b", "--agent-version", "v2"],
                     ["--agent-version", "v2", "--judge"]):
        try:
            run_evals.main(["--resume", dst2, "--delay", "0", *bad_args], llm_pair=HEALTHY)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"resume with {bad_args} should have been refused")
    assert len(read(os.path.join(dst2, "traces.jsonl"))) == 10, "a refused resume must not run anything"
    s2 = run_evals.main(["--resume", dst2, "--delay", "0", "--agent-version", "v2"], llm_pair=HEALTHY)
    assert s2["n_total"] == 31 and os.path.exists(os.path.join(dst2, "meta.json"))

    # 3. --stop-on-infra-error stops right after the first infra error; resume continues from there
    out2 = tempfile.mkdtemp()
    bad_q = "Who is the current CEO of Toyota"  # web-02, the 18th task
    s3 = run_evals.main(["--agent-version", "v1", "--delay", "0", "--out", out2, "--stop-on-infra-error"],
                        llm_pair=flaky({bad_q: INFRA}))
    run3 = os.path.join(out2, s3["run_id"])
    recs = read(os.path.join(run3, "traces.jsonl"))
    assert recs[-1]["id"] == "web-02" and recs[-1]["error"], "run must stop at the first infra error"
    assert (s3["n_total"], s3["n_expected"], s3["errors"]) == (len(recs), 31, 1) and len(recs) < 31, s3
    assert "INCOMPLETE" in open(os.path.join(run3, "report.md"), encoding="utf-8").read()
    s4 = run_evals.main(["--resume", run3, "--delay", "0"], llm_pair=HEALTHY)
    assert s4["n_total"] == 31 and s4["errors"] == 1, "resume continues but does not redo the errored row"
    s5 = run_evals.main(["--rerun-errors", run3, "--delay", "0"], llm_pair=HEALTHY)
    assert s5["errors"] == 0 and s5["n_tasks"] == 31, s5

    # 4. a MODEL error never stops a --stop-on-infra-error run
    out3 = tempfile.mkdtemp()
    s6 = run_evals.main(["--agent-version", "v1", "--delay", "0", "--out", out3, "--stop-on-infra-error"],
                        llm_pair=flaky({bad_q: MODEL}))
    assert s6["n_total"] == 31 and s6["model_errors"] == 1 and "web-02" in s6["failed_ids"], s6
    print("resume + stop-on-infra-error test passed")


def main():
    pair = (FakeLLM(can_call_tools=False), FakeLLM())
    out = tempfile.mkdtemp()
    s1 = run_evals.main(["--agent-version", "v1", "--delay", "0", "--out", out], llm_pair=pair)
    s2 = run_evals.main(["--agent-version", "v2", "--delay", "0", "--out", out], llm_pair=pair)

    assert s1["n_tasks"] == 31, s1["n_tasks"]
    assert "loop-01" in s1["failed_ids"], "v1 loop bug should fail loop-01"
    assert "inject-01" in s1["failed_ids"], "obeying the injection must fail inject-01"
    assert s1["checks"]["retrieval_hit"]["rate"] > 0.5, s1["checks"]["retrieval_hit"]
    for f in ("summary.json", "report.md", "traces.jsonl", "meta.json"):
        assert os.path.exists(os.path.join(out, s1["run_id"], f))

    import report
    import glob
    report.main(sorted(glob.glob(os.path.join(out, "*", "summary.json"))))
    test_error_policy_and_rerun()
    test_resume()
    print(f"\nOK  v1={s1['pass_rate']:.0%}  v2={s2['pass_rate']:.0%}")


if __name__ == "__main__":
    main()
