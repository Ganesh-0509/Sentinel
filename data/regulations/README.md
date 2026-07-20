# Regulation Corpus — provenance and replacement

## ⚠️ Read this before trusting any answer from the compliance assistant

The documents in this folder are **development summaries**, written to exercise the
retrieval pipeline. They paraphrase the *substance* of publicly-described requirements
so the RAG assistant has realistic material to retrieve and cite.

**They are NOT official regulatory text.** They contain no verbatim quotations and no
clause numbers, because inventing either would be worse than useless — a plausible-looking
but wrong citation is exactly how a compliance tool gets someone hurt.

Every file declares `provenance: SUMMARY`. The retriever propagates that field into every
citation, so the UI can visibly mark an answer as *"grounded in a development summary, not
the official standard."*

## To make this production-real

Replace each file with the official source document, then set `provenance: OFFICIAL`:

| File | Official source |
|---|---|
| `oisd_std_105_work_permit.md` | OISD-STD-105 *Work Permit System* — Oil Industry Safety Directorate |
| `factories_act_1948_hazardous_process.md` | The Factories Act, 1948 (esp. Chapter IV-A, hazardous processes) — Govt. of India |
| `confined_space_entry_sop.md` | Your site's own confined-space SOP |
| `emergency_response_sop.md` | Your site's on-site emergency plan |

Drop the PDFs/text into this folder and re-run the index build. The chunker reads
`.md` and `.txt`; add a PDF extractor if you supply PDFs.

## Numeric thresholds

Gas/oxygen limits used by the rule engine (`sentinel/rules/engine.py`) are
**site-configurable engineering defaults**, not quoted legal limits. Each plant must set
them from its own permit conditions and the applicable standard. They are deliberately
conservative.
