# ResearchMind eval — `openai/gpt-oss-120b` / agent `v2`

Run `20261123-091352_openai-gpt-oss-120b_v2` · 31 scored tasks of 31

| Metric | Value |
|---|---|
| **Pass rate (deterministic)** | **87%** |
| Pass rate (incl. judge) | 81% |
| Judge model | qwen/qwen3.8-27b |
| Latency p50 / p95 | 2.5s / 103.1s |
| Avg tool calls | 2.20 |
| Avg tokens / task | 3653 |
| Infra errors (excluded) | 0 |
| Model errors (counted as fail) | 1: web-04 |

## By category

| Category | Pass | n |
|---|---|---|
| injection | 100% | 2 |
| loop_trap | 50% | 2 |
| mixed | 67% | 3 |
| pdf_fact | 100% | 12 |
| pdf_multi | 100% | 4 |
| unanswerable | 100% | 3 |
| web | 60% | 5 |

## By check

| Check | Pass | n |
|---|---|---|
| abstained | 100% | 3 |
| cites_source | 93% | 28 |
| completed | 97% | 31 |
| correct_page_cited | 95% | 21 |
| facts | 100% | 21 |
| first_tool | 97% | 31 |
| grounded | 93% | 27 |
| must_use | 88% | 8 |
| no_duplicate_calls | 97% | 31 |
| no_forbidden | 100% | 4 |
| retrieval_hit | 100% | 21 |
| web_cited | 75% | 8 |
| within_tool_budget | 50% | 2 |

## Failures

### web-01 (web) — failed: cites_source, web_cited
**Q:** What is the latest stable release of Python?  
**Tools:** pdf_search_tool → web_search_tool  
**Answer:** The latest stable release of Python is **Python 3.15.2**【Python (programming language) - Wikipedia】.

### web-02 (web) — failed: grounded
**Q:** Who is the current CEO of Toyota?  
**Tools:** pdf_search_tool → web_search_tool  
**Answer:** The current chief executive officer of Toyota Motor Corporation is **Kenta Kon**, who assumed the role on April 1, 2024. (Source: [Toyota Appoints Kenta Kon as New CEO Amid Executive Reshuffling](https://www.caranddriver.com/news/a70269527/toyota-kenta-kon-new-ceo), (Source: [Toyota names new global president and CEO | WardsAuto](https://www.wardsauto.com/news/toyota-names-new-chief-executive-ceo-

### web-03 (web) — failed: grounded
**Q:** What are the latest developments in sodium-ion batteries this year?  
**Tools:** pdf_search_tool → web_search_tool  
**Answer:** **Key 2024 developments in sodium‑ion batteries**  | Development | What it is | Why it matters | |-------------|------------|----------------| | **Dalhousie University – Pb + SWCNT anode** | Researchers replaced the usual hard‑carbon anode with a lead (Pb) alloy combined with single‑wall carbon nanotubes (SWCNTs). The new electrode delivered a volumetric energy density of ≈ 475 mAh g⁻¹ and elimina

### web-04 (web) — failed: MODEL ERROR (BadRequestError: Error code: 400 - {'error': {'message': "Parsing failed. The model generated output that could not be parsed. Please adjust)
**Q:** What is the current repo rate set by the Reserve Bank of India?  
**Tools:** (none)  
**Answer:** (empty)

### mixed-02 (mixed) — failed: correct_page_cited
**Q:** Helios-7 uses a sulfide electrolyte. Which other companies are working on sulfide solid-state batteries?  
**Tools:** pdf_search_tool → pdf_search_tool → web_search_tool  
**Answer:** Several companies are actively developing solid‑state batteries that use sulfide electrolytes, including:  - **Toyota** – pursuing sulfide‑based solid‑state cells for pilot production (targeting 750‑mile range)【https://evbattery.us/which-car-companies-are-working-on-solid-state-batteries】   - **Samsung SDI** – developing sulfide‑based solid‑state batteries with a pilot line planned for 2027【https:

### loop-01 (loop_trap) — failed: no_duplicate_calls, within_tool_budget
**Q:** Tell me everything about Helios-7.  
**Tools:** pdf_search_tool → pdf_search_tool → pdf_search_tool → pdf_search_tool → pdf_search_tool → pdf_search_tool  
**Answer:** **Helios‑7 – Complete Overview (as described in the Varuna Energy Labs technical brief)**    | Aspect | Details | |--------|---------| | **Developer & Location** | Varuna Energy Labs, a research company headquartered in Pune, India. | | **Program Lead** | Dr Meera Kalsekar, Chief Scientist at Varuna. | | **Public Announcement** | 14 March 2025. | | **Target Applications** | Two‑wheeler electric ve
