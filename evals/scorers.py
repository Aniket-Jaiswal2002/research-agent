"""Deterministic scorers for ResearchMind agent traces.

Each scorer returns True/False, or None when it doesn't apply to the task.
A task passes when every applicable check is True.
"""
import json
import re
import unicodedata

# 1 = original (exact-character matching); 2 = Unicode/unit normalisation + multi-page citation parsing.
# See evals/SCORER_CHANGELOG.md. Saved in every summary.json; runs without the key were scored with 1.
SCORER_VERSION = 2

PAGE_RE = re.compile(r"Page\s*(\d+)", re.I)  # kept for backwards compatibility; see cited_pages()

# U+2010..U+2015 (hyphens, non-breaking hyphen, figure dash, en/em dash, bar) and U+2212 (minus)
_DASHES = {cp: "-" for cp in range(0x2010, 0x2016)}
_DASHES[0x2212] = "-"
# "Wh kg-1", "Wh·kg-1" -> "Wh/kg" (after NFKC, "kg⁻¹" has become "kg−1" -> "kg-1")
_PER_UNIT_RE = re.compile(r"(?<=\w)[\s·⋅]+(kg|mg|g|ml|l|cm|mm|m|s|h)-1(?!\d)", re.I)

_NUM = r"\d{1,3}(?!\d)"
_RANGE = rf"{_NUM}(?:\s*(?:-|to)\s*{_NUM})?"
# "Page 3", "Page 3 & 6", "Pages 3 and 6", "Pages 3, 6", "pp. 3-6", "Page 3, Page 6" (the latter via finditer)
_PAGE_REF_RE = re.compile(
    rf"\b(?:pages?|pp?\.)\s*(?P<body>{_RANGE}(?:\s*(?:,|;|&|and)\s*{_RANGE}(?!\s*(?!and\b)[A-Za-z%°]))*)", re.I)


def normalize(text: str) -> str:
    """Canonicalise model output before pattern matching.

    NFKC folds compatibility characters (narrow no-break space, superscripts, ligatures);
    every dash/hyphen/minus variant becomes "-"; per-unit exponents become "/unit".
    """
    t = unicodedata.normalize("NFKC", text or "").translate(_DASHES)
    t = _PER_UNIT_RE.sub(lambda m: "/" + m.group(1), t)
    return re.sub(r"[ \t]+", " ", t)
URL_RE = re.compile(r"https?://\S+")
ABSTAIN_RE = re.compile(
    r"(could ?n[o']t|cannot|can't|unable to|no (relevant )?(information|data|details|mention)"
    r"|not (mentioned|found|available|provided|specified|stated|included|disclosed)"
    r"|does(n't| not) (mention|contain|specify|provide|include|say|state)"
    r"|no sources|did not find|didn't find)",
    re.I,
)


def cited_pages(answer: str) -> set:
    """Page numbers cited in an answer, including lists ("Pages 3, 6", "Page 3 & 6") and ranges ("pp. 3-6")."""
    pages = set()
    for m in _PAGE_REF_RE.finditer(normalize(answer)):
        for part in re.split(r"\s*(?:,|;|&|\band\b)\s*", m.group("body"), flags=re.I):
            r = re.fullmatch(r"(\d{1,3})(?:\s*(?:-|to)\s*(\d{1,3}))?", part.strip(), re.I)
            if not r:
                continue
            a = int(r.group(1))
            b = int(r.group(2)) if r.group(2) else a
            if a <= b and b - a <= 100:
                pages.update(range(a, b + 1))
            else:
                pages.update((a, b))
    return pages


def retrieved_pages(trace: dict) -> set:
    pages = set()
    for s in trace["steps"]:
        if s["tool"] == "pdf_search_tool":
            pages |= {int(p) for p in re.findall(r"Page (\d+)\]", s["result"])}
    return pages


# Errors come stored as "<ExceptionType>: <message>" (see run_evals.evaluate_task).
# model = the model's own output was rejected (HTTP 400: output_parse_failed, tool_use_failed, ...).
#         The agent failed the task, so it counts as a FAIL.
# infra = everything else (429, 5xx, timeouts, connection errors, auth, unknown model, judge failures).
#         Says nothing about the agent, so the task is excluded from pass rates.
_MODEL_ERR_RE = re.compile(r"BadRequestError|Error code: 400|output_parse_failed|tool_use_failed|failed_generation", re.I)


def classify_error(err):
    """None if there was no error, else "model" or "infra"."""
    if not err:
        return None
    if err.startswith("JudgeError"):
        return "infra"  # the grader failing is not the agent's fault
    return "model" if _MODEL_ERR_RE.search(err) else "infra"


def score(task: dict, trace: dict) -> dict:
    e = task["expect"]
    ans = normalize(trace["answer"] or "")
    tools = [s["tool"] for s in trace["steps"]]
    c = {}

    c["completed"] = bool(ans.strip())
    c["first_tool"] = (bool(tools) and tools[0] == e["first_tool"]) if "first_tool" in e else None
    c["must_use"] = all(t in tools for t in e["must_use"]) if "must_use" in e else None
    c["must_not_use"] = not any(t in tools for t in e["must_not_use"]) if "must_not_use" in e else None
    c["no_duplicate_calls"] = not any(s["duplicate"] for s in trace["steps"])
    c["within_tool_budget"] = len(tools) <= e["max_tool_calls"] if "max_tool_calls" in e else None
    c["cites_source"] = None if e.get("abstain") else bool(cited_pages(ans) or URL_RE.search(ans))

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
