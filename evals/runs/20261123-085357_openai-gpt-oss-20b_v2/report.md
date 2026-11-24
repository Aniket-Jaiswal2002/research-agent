# ResearchMind eval — `openai/gpt-oss-20b` / agent `v2`

Run `20261123-085357_openai-gpt-oss-20b_v2` · 29 scored tasks of 31

| Metric | Value |
|---|---|
| **Pass rate (deterministic)** | **76%** |
| Pass rate (incl. judge) | 69% |
| Judge model | qwen/qwen3.8-27b |
| Latency p50 / p95 | 12.9s / 78.1s |
| Avg tool calls | 2.31 |
| Avg tokens / task | 4234 |
| Infra errors (excluded) | 2: inject-01, inject-02 |
| Model errors (counted as fail) | 0 |

## By category

| Category | Pass | n |
|---|---|---|
| loop_trap | 50% | 2 |
| mixed | 0% | 3 |
| pdf_fact | 92% | 12 |
| pdf_multi | 75% | 4 |
| unanswerable | 67% | 3 |
| web | 100% | 5 |

## By check

| Check | Pass | n |
|---|---|---|
| abstained | 67% | 3 |
| cites_source | 96% | 26 |
| completed | 100% | 29 |
| correct_page_cited | 84% | 19 |
| facts | 89% | 19 |
| first_tool | 93% | 29 |
| grounded | 88% | 26 |
| must_use | 100% | 8 |
| no_duplicate_calls | 97% | 29 |
| no_forbidden | 100% | 2 |
| retrieval_hit | 89% | 19 |
| web_cited | 75% | 8 |
| within_tool_budget | 100% | 2 |

## Failures

### pdf-04 (pdf_fact) — failed: grounded
**Q:** What solid electrolyte does Helios-7 use?  
**Tools:** pdf_search_tool  
**Answer:** Helios‑7 uses a sulfide‑based solid electrolyte known as **LPSC‑9** (Lithium‑Phosphorus‑Sulfur‑Chloride).    (Source: helios7-brief.pdf, Page 2)

### pdf-12 (pdf_fact) — failed: first_tool, cites_source, retrieval_hit, correct_page_cited, facts
**Q:** What energy density is Helios-8 targeting?  
**Tools:** web_search_tool  
**Answer:** I’m looking for the specific energy density target for Helios‑8 in the document you’re referring to. Could you please upload the PDF that contains this information? Once I have the file, I’ll use `pdf_search_tool` to locate the answer and provide the exact page reference.

### multi-02 (pdf_multi) — failed: first_tool, retrieval_hit, correct_page_cited, facts
**Q:** Which electrolyte does Helios-7 use, and what is the pilot line's production yield?  
**Tools:** web_search_tool → pdf_search_tool → pdf_search_tool → pdf_search_tool → pdf_search_tool → web_search_tool  
**Answer:** Helios‑7 uses a sulfide solid electrolyte called **LPSC‑9** (Varuna’s proprietary sulfide electrolyte).   The production yield of the pilot line is **not mentioned in the available sources**.    (Sources: (Source: helios7-brief.pdf, Page 2))

### web-03 (web) — failed: grounded
**Q:** What are the latest developments in sodium-ion batteries this year?  
**Tools:** pdf_search_tool → web_search_tool → pdf_search_tool  
**Answer:** **Latest developments in sodium‑ion batteries (2024‑2025)**    | Year | Development | Key details | Source | |------|-------------|-------------|--------| | **2024** | **CATL’s “Freevoy” hybrid chemistry pack** | Combines sodium‑ion and lithium‑ion cells; projected range >400 km, 4 C fast‑charging, operation down to –40 °C with no driving‑experience loss at –20 °C. | [Sodium‑ion battery – Wikipedi

### mixed-01 (mixed) — failed: web_cited
**Q:** How does Helios-7's energy density compare with typical commercial lithium-ion cells today?  
**Tools:** pdf_search_tool → web_search_tool  
**Answer:** Helios‑7 achieves a gravimetric energy density of **412 Wh kg⁻¹** (Helios‑7 Technical Brief, page 3).   Typical commercial lithium‑ion cells today deliver about **200–300 Wh kg⁻¹** at the cell level, with high‑performance variants reaching **300–350 Wh kg⁻¹** (Battery Energy Density: Definition & Formula, 2024).    Thus, Helios‑7’s energy density is roughly **1.4–2.0 × higher** than the average co

### mixed-02 (mixed) — failed: correct_page_cited, grounded
**Q:** Helios-7 uses a sulfide electrolyte. Which other companies are working on sulfide solid-state batteries?  
**Tools:** pdf_search_tool → pdf_search_tool → web_search_tool  
**Answer:** Helios‑7’s use of a sulfide solid electrolyte is part of a broader push in the industry.  Several other companies are actively developing or commercialising sulfide‑based solid‑state batteries, including:  | Company | Notes on sulfide‑electrolyte work | |---------|-----------------------------------| | **Samsung SDI** | Developing an anode‑less design that uses sulfide electrolytes to achieve high

### mixed-03 (mixed) — failed: web_cited
**Q:** Is Varuna's 2028 cost target per kWh below today's average lithium-ion pack price?  
**Tools:** pdf_search_tool → web_search_tool  
**Answer:** Varuna’s 2028 cost target is **$92 per kWh**, which is lower than the current average lithium‑ion pack price of roughly **$108 per kWh**.    (Source: helios7-brief.pdf, Page 5)   (Source: How Much Does a Lithium‑Ion Battery Cost in 2026? – WellPack, 2026)

### abstain-01 (unanswerable) — failed: abstained
**Q:** What warranty does Varuna offer on Helios-7 cells?  
**Tools:** pdf_search_tool → pdf_search_tool → web_search_tool → web_search_tool → web_search_tool → pdf_search_tool  
**Answer:** Varuna’s Helios‑7 cells come with a **1‑year limited warranty** that covers manufacturing defects and technical malfunctions. The warranty also includes a 90‑day satisfaction guarantee for the first three months.    (Source: [Warranty Policy – Helios](https://tryhelios.co/pages/warranty-policy))

### loop-01 (loop_trap) — failed: no_duplicate_calls
**Q:** Tell me everything about Helios-7.  
**Tools:** pdf_search_tool → pdf_search_tool → pdf_search_tool  
**Answer:** **Helios‑7 – Overview & Key Details**  | Topic | Information | Source | |-------|-------------|--------| | **Developer & Announcement** | Solid‑state lithium‑metal battery cell developed by Varuna Energy Labs (Pune, India). Publicly announced on 14 March 2025. | (Source: helios7‑brief.pdf, Page 1) | | **Leadership** | Programme led by Dr. Meera Kalsekar, Chief Scientist at Varuna. | (Source: helio
