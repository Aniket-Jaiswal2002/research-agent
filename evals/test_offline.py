"""Offline smoke test: runs the full harness with a scripted fake LLM, a
hashing embedder and a fake web tool. No API keys or model downloads.

    python evals/test_offline.py
"""
import hashlib
import os
import re
import sys
import tempfile
import types

import numpy as np

os.environ.setdefault("GROQ_API_KEY", "offline")
os.environ.setdefault("TAVILY_API_KEY", "offline")


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


def main():
    pair = (FakeLLM(can_call_tools=False), FakeLLM())
    out = tempfile.mkdtemp()
    s1 = run_evals.main(["--agent-version", "v1", "--delay", "0", "--out", out], llm_pair=pair)
    s2 = run_evals.main(["--agent-version", "v2", "--delay", "0", "--out", out], llm_pair=pair)

    assert s1["n_tasks"] == 31, s1["n_tasks"]
    assert "loop-01" in s1["failed_ids"], "v1 loop bug should fail loop-01"
    assert "inject-01" in s1["failed_ids"], "obeying the injection must fail inject-01"
    assert s1["checks"]["retrieval_hit"]["rate"] > 0.5, s1["checks"]["retrieval_hit"]
    for f in ("summary.json", "report.md", "traces.jsonl"):
        assert os.path.exists(os.path.join(out, s1["run_id"], f))

    import report
    import glob
    report.main(sorted(glob.glob(os.path.join(out, "*", "summary.json"))))
    print(f"\nOK  v1={s1['pass_rate']:.0%}  v2={s2['pass_rate']:.0%}")


if __name__ == "__main__":
    main()
