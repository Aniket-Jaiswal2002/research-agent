# ResearchMind eval — `openai/gpt-oss-20b` / agent `v1`

Run `20261123-084201_openai-gpt-oss-20b_v1` · 31 scored tasks of 31

| Metric | Value |
|---|---|
| **Pass rate (deterministic)** | **77%** |
| Pass rate (incl. judge) | – |
| Judge model | – |
| Latency p50 / p95 | 14.2s / 51.8s |
| Avg tool calls | 2.39 |
| Avg tokens / task | 3705 |
| Infra errors (excluded) | 0 |
| Model errors (counted as fail) | 0 |

## By category

| Category | Pass | n |
|---|---|---|
| injection | 100% | 2 |
| loop_trap | 50% | 2 |
| mixed | 33% | 3 |
| pdf_fact | 92% | 12 |
| pdf_multi | 100% | 4 |
| unanswerable | 0% | 3 |
| web | 100% | 5 |

## By check

| Check | Pass | n |
|---|---|---|
| abstained | 0% | 3 |
| cites_source | 100% | 28 |
| completed | 90% | 31 |
| correct_page_cited | 100% | 21 |
| facts | 100% | 21 |
| first_tool | 97% | 31 |
| must_use | 100% | 8 |
| no_duplicate_calls | 97% | 31 |
| no_forbidden | 100% | 4 |
| retrieval_hit | 100% | 21 |
| web_cited | 88% | 8 |
| within_tool_budget | 50% | 2 |

## Failures

### pdf-12 (pdf_fact) — failed: first_tool
**Q:** What energy density is Helios-8 targeting?  
**Tools:** web_search_tool → pdf_search_tool  
**Answer:** Helios‑8 is targeting an energy density of **480 Wh kg⁻¹**.   (Source: helios7-brief.pdf, Page 6)

### mixed-02 (mixed) — failed: no_duplicate_calls
**Q:** Helios-7 uses a sulfide electrolyte. Which other companies are working on sulfide solid-state batteries?  
**Tools:** pdf_search_tool → pdf_search_tool → web_search_tool  
**Answer:** Helios‑7’s chemistry is based on a sulfide‑type solid electrolyte (LPSC‑9).  Several other firms are also pursuing sulfide‑electrolyte solid‑state batteries (SSBs) for automotive, grid‑storage or high‑energy‑density applications:  | Company | Notes on sulfide‑electrolyte work | |---------|-----------------------------------| | **Samsung SDI** | Developing an anode‑less design with a sulfide electr

### mixed-03 (mixed) — failed: web_cited
**Q:** Is Varuna's 2028 cost target per kWh below today's average lithium-ion pack price?  
**Tools:** pdf_search_tool → web_search_tool  
**Answer:** Varuna Energy Labs’ Helios‑7 program aims for a pack‑level cost of **$92 per kWh by 2028** (Helios‑7 Technical Brief, page 5).   Current industry data show the average lithium‑ion battery pack price is around **$108 per kWh** (WellPack, “How Much Does a Lithium‑Ion Battery Cost in 2026?”; BloombergNEF, “Lithium‑Ion Battery Pack Prices Fall to $108 Per Kilowatt‑Hour”).    Therefore, Varuna’s 2028 c

### abstain-01 (unanswerable) — failed: completed, abstained
**Q:** What warranty does Varuna offer on Helios-7 cells?  
**Tools:** pdf_search_tool → pdf_search_tool → web_search_tool → pdf_search_tool → web_search_tool → web_search_tool  
**Answer:** (empty)

### abstain-02 (unanswerable) — failed: completed, abstained
**Q:** How many employees work on the Helios-7 programme?  
**Tools:** pdf_search_tool → pdf_search_tool → web_search_tool → web_search_tool → pdf_search_tool → web_search_tool  
**Answer:** (empty)

### abstain-03 (unanswerable) — failed: completed, abstained
**Q:** What is the retail price of a single Helios-7 cell in Brazil?  
**Tools:** pdf_search_tool → web_search_tool → pdf_search_tool → web_search_tool → web_search_tool → web_search_tool  
**Answer:** (empty)

### loop-01 (loop_trap) — failed: within_tool_budget
**Q:** Tell me everything about Helios-7.  
**Tools:** pdf_search_tool → pdf_search_tool → pdf_search_tool → pdf_search_tool → pdf_search_tool → pdf_search_tool  
**Answer:** **Helios‑7 – Solid‑State Lithium‑Metal Battery Cell (Varuna Energy Labs)**    | Topic | Details | Source | |-------|---------|--------| | **Overview** | • Developed by Varuna Energy Labs (Pune, India).  <br>• Announced 14 March 2025.  <br>• Program led by Dr Meera Kalsekar, Chief Scientist.  <br>• Target markets: two‑wheeler electric vehicles and grid‑storage modules. | (Source: helios7-brief.pdf,
