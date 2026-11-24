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
    assert s["pass_rate_deterministic"] <= s["pass_rate_excl_citations"] <= 1, "dropping checks can only raise the rate"
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


# ── v3 guardrails ─────────────────────────────────────────────────────
class WebFirstLLM(FakeLLM):
    """Ignores the 'PDF first' rule: its first call is always a web search."""

    def invoke(self, messages):
        if not any(isinstance(m, ToolMessage) for m in messages):
            self.n += 1
            q = next(m.content for m in messages if isinstance(m, HumanMessage))
            return AIMessage(content="", tool_calls=[{"name": "web_search_tool", "args": {"query": q}, "id": f"w{self.n}"}])
        return super().invoke(messages)


class ForcedPdfLLM(FakeLLM):
    """Stands in for llm.bind_tools(..., tool_choice="pdf_search_tool"): always calls the PDF tool.

    `fail_times` makes the first N invocations raise `exc` (None = always), to test recovery.
    """

    def __init__(self, fail_times=0, exc=None, **kw):
        super().__init__(**kw)
        self.fail_times, self.exc, self.attempts = fail_times, exc or MODEL, 0

    def invoke(self, messages):
        self.attempts += 1
        if self.fail_times is None or self.attempts <= self.fail_times:
            raise self.exc
        self.n += 1
        q = next(m.content for m in messages if isinstance(m, HumanMessage))
        return AIMessage(content="", tool_calls=[{"name": "pdf_search_tool", "args": {"query": q.lower()}, "id": f"f{self.n}"}])


def _strip(text, pages=True, urls=True):
    if pages:
        text = re.sub(r"\(Source:[^)]*\)", "", text)
    if urls:
        text = re.sub(r"\[web\]\([^)]*\)", "", text)
        text = re.sub(r"https?://[^\s\"'\]}]+", "", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


class FixedAnswerLLM(FakeLLM):
    """FakeLLM's search policy, but the final answer is a fixed string."""

    def __init__(self, text, **kw):
        super().__init__(**kw)
        self.text = text

    def invoke(self, messages):
        r = super().invoke(messages)
        return r if r.tool_calls else AIMessage(content=self.text)


class NoCiteLLM(FakeLLM):
    """Searches and answers like FakeLLM (so the answer overlaps the tool results) but cites nothing."""

    def invoke(self, messages):
        r = super().invoke(messages)
        if r.tool_calls:
            return r
        text = _strip(r.content)
        ctx = " ".join(m.content for m in messages if isinstance(m, ToolMessage))
        if "Example web result" in ctx and "Example web result" not in text:
            text += " Example web result."  # the fake body is cut at 600 chars; keep the web content in the answer
        return AIMessage(content=text)


class Flaky400LLM(FakeLLM):
    """Raises `exc` (default: a model 400) for the first `fail_times` calls (None = always), then behaves."""

    def __init__(self, fail_times=None, exc=None, **kw):
        super().__init__(**kw)
        self.fail_times, self.exc, self.attempts = fail_times, exc or MODEL, 0

    def invoke(self, messages):
        self.attempts += 1
        if self.fail_times is None or self.attempts <= self.fail_times:
            raise self.exc
        return super().invoke(messages)


def test_v3():
    """v3 enforces PDF-first, citations and 400-recovery in code; each guardrail has a v2 control."""
    import re as _re
    from scorers import cited_pages
    run_evals.ensure_fixture()
    Q = "What is the gravimetric energy density of Helios-7?"
    QW = "Who is the current CEO of Toyota?"
    QLOOP = "Tell me everything about Helios-7."

    def run(version, pair, q=Q):
        return agent.run_agent(q, version=version, llm_pair=pair)

    def raises(exc_type, version, pair, q=Q):
        try:
            run(version, pair, q)
        except exc_type:
            return True
        return False

    # ---- 1. PDF-first is enforced by tool_choice, not by the prompt --------------------------------
    r2 = run("v2", (FakeLLM(False), WebFirstLLM(), ForcedPdfLLM()))
    assert r2["steps"][0]["tool"] == "web_search_tool", "control: v2 trusts the model, so web-first slips through"
    forced = ForcedPdfLLM()
    r3 = run("v3", (FakeLLM(False), WebFirstLLM(), forced))
    assert r3["steps"][0]["tool"] == "pdf_search_tool" and r3["forced_pdf_first"] is True
    assert forced.n == 1, "the forced runner is used for the first call only"
    for v in ("v1", "v2"):
        unused = ForcedPdfLLM()
        run(v, (FakeLLM(False), FakeLLM(), unused))
        assert unused.n == 0 and unused.attempts == 0, f"{v} must never use the forced runner"
    r3b = run("v3", (FakeLLM(False), FakeLLM()))  # a 2-tuple has no forced runner: falls back, still works
    assert r3b["forced_pdf_first"] is False and r3b["answer"]
    # the real wiring: ChatGroq.bind_tools(tool_choice=...) encodes what the Groq API expects
    _llm, bound, forced_real = agent.get_llm("openai/gpt-oss-20b")
    assert forced_real.kwargs["tool_choice"] == {"type": "function", "function": {"name": "pdf_search_tool"}}
    assert bound.kwargs.get("tool_choice") is None
    assert [t["function"]["name"] for t in forced_real.kwargs["tools"]] == ["pdf_search_tool", "web_search_tool"]

    # ---- 2. citations: appended only for sources the answer actually overlaps with ----------------------
    nocite = lambda: (NoCiteLLM(False), NoCiteLLM(), ForcedPdfLLM())  # noqa: E731
    base = agent.run_agent(Q, version="v2", llm_pair=nocite())
    assert "Sources:" not in base["answer"] and not cited_pages(base["answer"]), "control: v2 leaves it uncited"

    r = run("v3", nocite())  # (a) PDF used, no page cited -> the retrieved page(s) the answer overlaps are appended
    retrieved = {int(p) for s in r["steps"] if s["tool"] == "pdf_search_tool" for p in _re.findall(r"Page (\d+)\]", s["result"])}
    pages = cited_pages(r["answer"])
    assert r["citations_appended"] == {"web": False, "pdf": True} and pages and pages <= retrieved, (r["answer"], retrieved)
    assert "\n\nSources:\n" in r["answer"]

    web_ans = "Example web result about Toyota leadership."  # (b) answer drawn from the web result, no URL
    r = run("v3", (FakeLLM(False), FixedAnswerLLM(web_ans), ForcedPdfLLM()), QW)
    assert r["citations_appended"] == {"web": True, "pdf": False}, r["citations_appended"]
    assert r["answer"] == web_ans + "\n\nSources:\n- https://example.com/news"

    r = run("v3", (FakeLLM(False), FixedAnswerLLM(web_ans + " (Source: helios7-brief.pdf, Page 3)"), ForcedPdfLLM()), QW)
    assert r["citations_appended"] == {"web": True, "pdf": False}, "page already cited -> only the URL is added"
    assert r["answer"].count("(Source:") == 1

    # (c) THE LIVE BUG: a web answer that happened to follow an irrelevant PDF search must not get PDF pages
    unrelated = "The current chief executive officer is Kenta Kon, appointed in April."
    r = run("v3", (FakeLLM(False), FixedAnswerLLM(unrelated), ForcedPdfLLM()), QW)
    assert r["citations_appended"] == {"web": False, "pdf": False} and r["answer"] == unrelated, r["answer"]

    ok = (FakeLLM(False), FakeLLM(), ForcedPdfLLM())  # (d) already cited -> answer untouched
    ra, rb = run("v2", ok, QW), run("v3", (FakeLLM(False), FakeLLM(), ForcedPdfLLM()), QW)
    assert rb["citations_appended"] == {"web": False, "pdf": False} and rb["answer"] == ra["answer"]

    ap = agent.append_missing_citations  # (e) the helper in isolation
    none = {"web": False, "pdf": False}
    p3 = "[Source: f.pdf, Page 3]\nHelios-7 reaches a gravimetric energy density of 412 Wh/kg and a volumetric density"
    p6 = "[Source: f.pdf, Page 6]\nRoadmap: Helios-8 targets 480 Wh/kg with silicon anodes by 2028"
    pdf = [p3 + "\n\n---\n\n" + p6]
    a, added = ap("The Helios-7 cell reaches a gravimetric energy density of 412 Wh/kg.", pdf, [])
    assert a.endswith("\n\nSources:\n(Source: f.pdf, Page 3)") and added == {"web": False, "pdf": True}, a  # page 6 not used
    assert ap("The current CEO of Toyota is Kenta Kon.", pdf, []) == ("The current CEO of Toyota is Kenta Kon.", none)
    a, added = ap("Helios-8 targets 480 Wh/kg, Helios-7 reaches 412 Wh/kg.", pdf, [])
    assert a.endswith("(Source: f.pdf, Page 3) (Source: f.pdf, Page 6)") and added["pdf"], a  # both pages used, no duplicates
    assert ap("ok, see page 3", pdf, []) == ("ok, see page 3", none)
    assert ap("The cell reaches 412 Wh/kg, pp. 3-6", pdf, [])[1] == none
    assert ap("412", pdf, [])[1]["pdf"] is True, "a one-token answer needs one shared token"
    assert ap("", pdf, []) == ("", none)
    web = ["[{'url': 'https://a.com/1', 'content': 'Toyota names Kenta Kon as new CEO in April 2026'}, "
           "{'url': 'https://b.com', 'content': 'Weather in Pune is sunny today'}]",
           '[{"url": "https://a.com/1", "content": "dup of the first"}, {"url": "https://c.com", "content": "Kenta Kon leads Toyota"}]']
    a, added = ap("The current CEO of Toyota is Kenta Kon.", [], web)
    assert a == "The current CEO of Toyota is Kenta Kon.\n\nSources:\n- https://a.com/1\n- https://c.com", a  # unrelated b.com skipped, no dups
    assert added == {"web": True, "pdf": False}
    assert ap("Pune is sunny.", [], web[:1])[0].endswith("- https://b.com")
    many = ["[{'url': 'https://s%d.com', 'content': 'Toyota Kenta Kon CEO'}]" % i for i in range(9)]
    assert ap("Kenta Kon leads Toyota", [], many)[0].count("\n- ") == agent.MAX_APPENDED_URLS
    assert ap("see https://x.org about Kenta Kon", [], web) == ("see https://x.org about Kenta Kon", none)
    assert ap("Kenta Kon", [], ["no urls in here, Kenta Kon"]) == ("Kenta Kon", none)
    assert ap("ok", [], []) == ("ok", none)
    raw = ["garbage {'url': 'https://a.com/1' Kenta Kon Toyota not parseable"]
    assert ap("Kenta Kon of Toyota", [], raw)[0].endswith("- https://a.com/1"), "unparseable results fall back to URL scraping"

    # abstentions get no Sources block, even when the answer overlaps the tool results
    abst = "The brief does not mention the gravimetric energy density of Helios-7."
    assert ap(abst, pdf, []) == (abst, none)
    assert ap("The brief gives the gravimetric energy density of Helios-7.", pdf, [])[1]["pdf"] is True, \
        "control: same overlap, not an abstention -> appended"
    assert ap("I could not confirm that Kenta Kon leads Toyota.", [], web)[1] == none, "narrow no-break space still matches"
    assert ap("Kenta Kon leads Toyota.", [], web)[1]["web"] is True, "control: web answer that is not an abstention"
    r = run("v3", (FakeLLM(False), FixedAnswerLLM(abst), ForcedPdfLLM()))  # end to end: the PDF was searched, nothing is appended
    assert r["answer"] == abst and r["citations_appended"] == none and [s["tool"] for s in r["steps"]] == ["pdf_search_tool"]

    # ---- 3. parse failures (model HTTP 400): retry once, unforced runner, tool-free only with tool results ----
    zero = {"retries": 0, "unforced_fallbacks": 0, "tool_free_fallbacks": 0, "static_fallbacks": 0}
    rec = lambda **kw: {**zero, **kw}  # noqa: E731

    flaky = Flaky400LLM(fail_times=1)  # (a) one 400 in the loop -> the retry succeeds
    r = run("v3", (FakeLLM(False), flaky, ForcedPdfLLM()))
    assert flaky.attempts == 2 and r["recovery"] == rec(retries=1), r["recovery"]
    assert r["answer"] and "Page" in r["answer"]

    ff = ForcedPdfLLM(fail_times=1)  # (b) one 400 on the forced first call -> the retry succeeds, still PDF-first
    r = run("v3", (FakeLLM(False), FakeLLM(), ff))
    assert ff.attempts == 2 and r["steps"][0]["tool"] == "pdf_search_tool" and r["recovery"] == rec(retries=1)

    fa = ForcedPdfLLM(fail_times=None)  # (c) the forced call always 400s (the live "tool_choice mismatch") -> unforced runner
    unforced = FakeLLM()
    tool_free = FakeLLM(False)
    r = run("v3", (tool_free, unforced, fa))
    assert fa.attempts == 2, "forced call: one try plus one retry"
    assert r["recovery"] == rec(retries=1, unforced_fallbacks=1), r["recovery"]
    assert unforced.n >= 2 and tool_free.n == 0, "the unforced runner takes over; the tool-free runner is not needed"
    assert r["steps"] and r["answer"] != agent.PARSE_FAILURE_ANSWER and "Page" in r["answer"]

    always = Flaky400LLM(fail_times=None)  # (d) 400 every time AFTER a tool result exists -> tool-free final answer
    r = run("v3", (FakeLLM(False), always, ForcedPdfLLM()))
    assert always.attempts == 2, "exactly one retry"
    assert r["recovery"] == rec(retries=1, tool_free_fallbacks=1), r["recovery"]
    assert r["answer"] != agent.PARSE_FAILURE_ANSWER and [s["tool"] for s in r["steps"]] == ["pdf_search_tool"] and "Page" in r["answer"]

    tf = FakeLLM(False)  # (e) first call fails on both runners: NO tool-free call (it would 400 too), fixed message
    r = run("v3", (tf, Flaky400LLM(fail_times=None), ForcedPdfLLM(fail_times=None)))
    assert tf.n == 0, "a tool-free call cannot recover a first call, so it must not be attempted"
    assert r["answer"] == agent.PARSE_FAILURE_ANSWER and r["steps"] == []
    assert r["recovery"] == rec(retries=2, unforced_fallbacks=1, static_fallbacks=1), r["recovery"]
    assert r["citations_appended"] == {"web": False, "pdf": False}

    r = run("v3", (Flaky400LLM(fail_times=None), Flaky400LLM(fail_times=None), ForcedPdfLLM()))  # (f) nothing works after a tool result
    assert r["answer"] == agent.PARSE_FAILURE_ANSWER and r["steps"], "the pdf step happened, then everything 400ed"
    assert r["recovery"] == rec(retries=2, tool_free_fallbacks=1, static_fallbacks=1), r["recovery"]
    assert r["citations_appended"] == {"web": False, "pdf": False}, "no citations on the fixed message"

    one = Flaky400LLM(fail_times=1, can_call_tools=False)  # (g) the budget-exhausted final answer also retries
    r = run("v3", (one, FakeLLM(), ForcedPdfLLM()), QLOOP)
    assert r["hit_iteration_budget"] and one.attempts == 2 and r["recovery"] == rec(retries=1) and r["answer"]

    # controls and boundaries
    assert raises(BadRequestError, "v2", (FakeLLM(False), Flaky400LLM(fail_times=None), ForcedPdfLLM())), "control: v2 crashes"
    assert raises(RuntimeError, "v3", (FakeLLM(False), Flaky400LLM(fail_times=None, exc=INFRA), ForcedPdfLLM())), \
        "infra errors (429/5xx/timeouts) must still propagate"
    assert raises(RuntimeError, "v3", (FakeLLM(False), FakeLLM(), ForcedPdfLLM(fail_times=None, exc=INFRA)))
    assert agent.is_model_400(MODEL) and not agent.is_model_400(INFRA)
    assert agent.is_model_400(types.SimpleNamespace(status_code=400)) is True  # attribute-style 400s too

    # ---- 4. through the harness: v3 beats v2 on exactly the checks it enforces ----------------------
    out = tempfile.mkdtemp()
    wf = lambda: (FakeLLM(False), WebFirstLLM(), ForcedPdfLLM())  # noqa: E731
    h2 = run_evals.main(["--agent-version", "v2", "--delay", "0", "--out", out], llm_pair=wf())
    h3 = run_evals.main(["--agent-version", "v3", "--delay", "0", "--out", out], llm_pair=wf())
    assert h2["checks"]["first_tool"]["rate"] < 1.0 == h3["checks"]["first_tool"]["rate"], (h2["checks"]["first_tool"], h3["checks"]["first_tool"])
    c2 = run_evals.main(["--agent-version", "v2", "--delay", "0", "--out", out], llm_pair=nocite())
    c3 = run_evals.main(["--agent-version", "v3", "--delay", "0", "--out", out], llm_pair=nocite())
    for chk in ("cites_source", "web_cited"):
        assert c2["checks"][chk]["rate"] < 1.0 == c3["checks"][chk]["rate"], (chk, c2["checks"][chk], c3["checks"][chk])
    print("v3 guardrail tests passed")


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
    test_v3()
    print(f"\nOK  v1={s1['pass_rate']:.0%}  v2={s2['pass_rate']:.0%}")


if __name__ == "__main__":
    main()
