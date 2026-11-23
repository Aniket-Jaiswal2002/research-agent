"""Deterministic scorers for ResearchMind agent traces.

Each scorer returns True/False, or None when it doesn't apply to the task.
A task passes when every applicable check is True.
"""
import json
import re

PAGE_RE = re.compile(r"Page\s*(\d+)", re.I)
URL_RE = re.compile(r"https?://\S+")
ABSTAIN_RE = re.compile(
    r"(could ?n[o']t|cannot|can't|unable to|no (relevant )?(information|data|details|mention)"
    r"|not (mentioned|found|available|provided|specified|stated|included|disclosed)"
    r"|does(n't| not) (mention|contain|specify|provide|include|say|state)"
    r"|no sources|did not find|didn't find)",
    re.I,
)


def cited_pages(answer: str) -> set:
    return {int(p) for p in PAGE_RE.findall(answer or "")}


def retrieved_pages(trace: dict) -> set:
    pages = set()
    for s in trace["steps"]:
        if s["tool"] == "pdf_search_tool":
            pages |= {int(p) for p in re.findall(r"Page (\d+)\]", s["result"])}
    return pages


def score(task: dict, trace: dict) -> dict:
    e = task["expect"]
    ans = trace["answer"] or ""
    tools = [s["tool"] for s in trace["steps"]]
    c = {}

    c["completed"] = bool(ans.strip())
    c["first_tool"] = (bool(tools) and tools[0] == e["first_tool"]) if "first_tool" in e else None
    c["must_use"] = all(t in tools for t in e["must_use"]) if "must_use" in e else None
    c["must_not_use"] = not any(t in tools for t in e["must_not_use"]) if "must_not_use" in e else None
    c["no_duplicate_calls"] = not any(s["duplicate"] for s in trace["steps"])
    c["within_tool_budget"] = len(tools) <= e["max_tool_calls"] if "max_tool_calls" in e else None
    c["cites_source"] = None if e.get("abstain") else bool(PAGE_RE.search(ans) or URL_RE.search(ans))

    if "pages" in e:
        want, got, ret = set(e["pages"]), cited_pages(ans), retrieved_pages(trace)
        mode = all if e.get("pages_mode") == "all" else any
        c["retrieval_hit"] = mode(p in ret for p in want)   # did FAISS return the right page?
        c["correct_page_cited"] = mode(p in got for p in want)  # did the LLM cite it?
    else:
        c["retrieval_hit"] = c["correct_page_cited"] = None

    c["facts"] = all(re.search(f, ans, re.I) for f in e["facts"]) if "facts" in e else None
    c["no_forbidden"] = not any(re.search(f, ans, re.I | re.M) for f in e["forbidden"]) if "forbidden" in e else None
    c["abstained"] = bool(ABSTAIN_RE.search(ans)) if e.get("abstain") else None
    c["web_cited"] = bool(URL_RE.search(ans)) if e.get("needs_url") else None

    applicable = {k: v for k, v in c.items() if v is not None}
    return {"checks": c, "passed": all(applicable.values())}


# ── Optional LLM-as-judge groundedness check ─────────────────────────
JUDGE_PROMPT = """You are grading a research assistant for groundedness.
Below are the TOOL RESULTS the assistant saw, then its ANSWER.
A claim is supported only if the tool results state it. Ignore the source-citation lines.
Respond with JSON only: {{"grounded": true|false, "unsupported_claims": ["..."]}}

TOOL RESULTS:
{context}

ANSWER:
{answer}"""


def judge_grounded(trace: dict, judge_llm) -> dict:
    context = "\n\n---\n\n".join(s["result"] for s in trace["steps"]) or "(no tool results)"
    msg = judge_llm.invoke(JUDGE_PROMPT.format(context=context[:12000], answer=trace["answer"]))
    text = msg.content.strip()
    m = re.search(r"\{.*\}", text, re.S)
    try:
        out = json.loads(m.group(0)) if m else {}
        return {"grounded": bool(out.get("grounded")), "unsupported_claims": out.get("unsupported_claims", [])}
    except json.JSONDecodeError:
        return {"grounded": None, "unsupported_claims": [], "raw": text[:500]}
