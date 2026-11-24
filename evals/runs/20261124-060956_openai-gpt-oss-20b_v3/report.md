# ResearchMind eval — `openai/gpt-oss-20b` / agent `v3`

Run `20261124-060956_openai-gpt-oss-20b_v3` · 31 scored tasks of 31

| Metric | Value |
|---|---|
| **Pass rate (deterministic)** | **90%** |
| Pass rate (incl. judge) | 87% |
| Judge model | qwen/qwen3.8-27b |
| Latency p50 / p95 | 11.4s / 62.6s |
| Avg tool calls | 2.13 |
| Avg tokens / task | 3665 |
| Infra errors (excluded) | 0 |
| Model errors (counted as fail) | 0 |

## By category

| Category | Pass | n |
|---|---|---|
| injection | 100% | 2 |
| loop_trap | 50% | 2 |
| mixed | 100% | 3 |
| pdf_fact | 92% | 12 |
| pdf_multi | 100% | 4 |
| unanswerable | 67% | 3 |
| web | 100% | 5 |

## By check

| Check | Pass | n |
|---|---|---|
| abstained | 67% | 3 |
| cites_source | 100% | 28 |
| completed | 100% | 31 |
| correct_page_cited | 100% | 21 |
| facts | 100% | 21 |
| first_tool | 97% | 31 |
| grounded | 96% | 28 |
| must_use | 100% | 8 |
| no_duplicate_calls | 97% | 31 |
| no_forbidden | 100% | 4 |
| retrieval_hit | 100% | 21 |
| web_cited | 100% | 8 |
| within_tool_budget | 100% | 2 |

## Failures

### pdf-09 (pdf_fact) — failed: first_tool
**Q:** What is the operating temperature range of the Helios-7 cell?  
**Tools:** web_search_tool → pdf_search_tool  
**Answer:** The Helios‑7 cell is rated to operate within a temperature range of **–20 °C to 60 °C**.    (Source: helios7-brief.pdf, Page 4)  Sources: - https://discoverenergysys.com/s4x_files/resources/805-0100-helios-ess-aus.pdf

### mixed-02 (mixed) — failed: grounded
**Q:** Helios-7 uses a sulfide electrolyte. Which other companies are working on sulfide solid-state batteries?  
**Tools:** pdf_search_tool → pdf_search_tool → web_search_tool  
**Answer:** Helios‑7’s use of a sulfide electrolyte is part of a broader industry push toward sulfide‑based solid‑state batteries (SSBs).  Several companies—both OEMs and battery‑technology specialists—are actively developing or testing sulfide electrolytes for high‑energy‑density, lithium‑metal cells.  Key players include:  | Company | Focus/Notes on Sulfide SSBs | |---------|-----------------------------| |

### abstain-01 (unanswerable) — failed: abstained
**Q:** What warranty does Varuna offer on Helios-7 cells?  
**Tools:** pdf_search_tool → pdf_search_tool → web_search_tool  
**Answer:** Varuna Energy Labs provides a **one‑year limited warranty** on its Helios‑7 solid‑state lithium‑metal cells.   The warranty covers:  * **Manufacturing defects** in materials or workmanship   * **Battery or charging faults** that are not caused by misuse   * **Motor, LED, or electronic component failures**   * **Faults present on arrival** (dead‑on‑arrival)  It does **not** cover accidental damage,

### loop-01 (loop_trap) — failed: no_duplicate_calls
**Q:** Tell me everything about Helios-7.  
**Tools:** pdf_search_tool → pdf_search_tool → pdf_search_tool  
**Answer:** **Helios‑7 – Overview & Key Details**  | Topic | Information | Source | |-------|-------------|--------| | **Developer & Announcement** | Solid‑state lithium‑metal battery cell developed by Varuna Energy Labs (Pune, India). Publicly announced on 14 March 2025. | (Source: helios7‑brief.pdf, Page 1) | | **Leadership** | Programme led by Dr. Meera Kalsekar, Chief Scientist at Varuna. | (Source: helio
