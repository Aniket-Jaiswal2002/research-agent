# ResearchMind eval results

| Metric | openai/gpt-oss-20b · v1 | openai/gpt-oss-20b · v2 | openai/gpt-oss-120b · v2 |
|---|---|---|---|
| **Pass rate (deterministic)** | **77%** | **76%** | **87%** |
| Passed / scored | 24 / 31 | 22 / 29 | 27 / 31 |
| Pass rate (incl. judge) | – | 69% | 81% |
| Judge model | – | qwen/qwen3.8-27b | qwen/qwen3.8-27b |
| injection | 100% | – | 100% |
| loop_trap | 50% | 50% | 50% |
| mixed | 33% | 0% | 67% |
| pdf_fact | 92% | 92% | 100% |
| pdf_multi | 100% | 75% | 100% |
| unanswerable | 0% | 67% | 100% |
| web | 100% | 100% | 60% |
| check: abstained | 0% | 67% | 100% |
| check: cites_source | 100% | 96% | 93% |
| check: completed | 90% | 100% | 97% |
| check: correct_page_cited | 100% | 84% | 95% |
| check: facts | 100% | 89% | 100% |
| check: first_tool | 97% | 93% | 97% |
| groundedness (judge, separate) | – | 88% | 93% |
| check: must_use | 100% | 100% | 88% |
| check: no_duplicate_calls | 97% | 97% | 97% |
| check: no_forbidden | 100% | 100% | 100% |
| check: retrieval_hit | 100% | 89% | 100% |
| check: web_cited | 88% | 75% | 75% |
| check: within_tool_budget | 50% | 100% | 50% |
| Latency p50 / p95 | 14.2s / 51.8s | 12.9s / 78.1s | 2.5s / 103.1s |
| Avg tool calls | 2.39 | 2.31 | 2.20 |
| Avg tokens / task | 3705 | 4234 | 3653 |
| Tasks scored | 31 of 31 | 29 of 31 | 31 of 31 |
| Infra errors (excluded) | 0 | 2: inject-01, inject-02 | 0 |
| Model errors (counted as fail) | 0 | 0 | 1: web-04 |

## How to read this

- **Pass rate (deterministic)** is the fraction of tasks where every applicable check passed, except the LLM judge's groundedness. Compare v1 vs v2 on this row only.
- **Groundedness** is the judge's verdict on whether the answer is supported by the tool results; it is reported separately and only exists for judged runs. Judge model(s): `qwen/qwen3.8-27b`; each differs from the model under test.
- **Infra errors** (429, 5xx, timeouts, ...) are excluded from every rate; **model errors** (HTTP 400 such as `output_parse_failed`) count as failures. See `evals/README.md`.
- 31 tasks; each task ≈ 3 points. Differences under ~10 points are within run-to-run variance.
- Scorer version(s): 3 (see `evals/SCORER_CHANGELOG.md`).
