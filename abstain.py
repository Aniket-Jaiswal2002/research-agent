"""Shared abstention detector: does an answer say it could not find the information?

One regex, two users, so they can never disagree:
  * agent.py (v3) does not append a "Sources:" block to an abstention;
  * evals/scorers.py uses it for the `abstained` check.

No dependencies on purpose: both sides must be able to import it.
"""
import re
import unicodedata

ABSTAIN_RE = re.compile(
    r"(could ?n[o']t|cannot|can't|unable to|no (relevant )?(information|data|details|mention)"
    r"|not (mentioned|found|available|provided|specified|stated|included|disclosed)"
    r"|does(n't| not) (mention|contain|specify|provide|include|say|state)"
    r"|no sources|did not find|didn't find)",
    re.I,
)


def is_abstention(text) -> bool:
    """True if the answer matches ABSTAIN_RE. NFKC first, so "could not" (narrow no-break space) matches."""
    return bool(ABSTAIN_RE.search(unicodedata.normalize("NFKC", text or "")))
