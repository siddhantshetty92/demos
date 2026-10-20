# RFP Answer Assistant

**Answers security and product questionnaires from your own documentation, reuses approved answers, and flags anything a human should check.**

## Problem

Enterprise deals come with 100–400 question RFPs and security questionnaires. Most questions have been answered before in slightly different words; the rest need a careful answer grounded in real documentation. Two failure modes cost the most: inconsistent answers to the same question across deals, and a confident "Yes" to something the product doesn't do.

## How it works

For each row of a questionnaire CSV:

1. **Answer library first.** If an approved answer to a near-identical question exists (token Jaccard ≥ 0.5), reuse it verbatim with its id as the source. Consistency comes before cleverness.
2. **Retrieve.** A small TF-IDF retriever over markdown docs, chunked by heading, returns the top passages with ids.
3. **Answer with citations.** The LLM gets only those passages and must return schema-constrained JSON: a short answer from a fixed vocabulary (`Yes / No / Partial / Roadmap / Not applicable`), a 2–4 sentence long answer, a confidence level, and the source ids it used. It is told to drop confidence instead of guessing when the sources don't cover the question.
4. **Guardrails.** Every answer is linted for overclaims ("guarantee", "100%", "never", "fully compliant"), length, and affirmative answers with no source. Anything flagged, or low confidence, is marked `needs_review`.
5. **Write back** a CSV with answer, sources, origin (library / model / extractive) and review flags, so a reviewer works only the flagged rows.

An **offline extractive mode** answers from the best-matching sentence without any API. It shows the pipeline end to end, and its mistakes show why the model step exists.

**Mock data:** a fictional product's docs in [`examples/knowledge/`](examples/knowledge), a 10-question [`questionnaire.csv`](examples/questionnaire.csv), an approved-answer [`library.json`](examples/library.json) → [`sample-output/answers.csv`](sample-output/answers.csv) (offline extractive mode).

## Run it

```bash
python3 -m rfp.cli examples/questionnaire.csv --knowledge examples/knowledge \
  --library examples/library.json --out answers.csv                       # offline
pip install -r requirements.txt
ANTHROPIC_API_KEY=… python3 -m rfp.cli … --provider anthropic              # Claude
python3 -m unittest discover -s tests                                      # 8 tests, model client faked
```

## Design choices

- **The model never sees the whole knowledge base**, only retrieved, numbered passages, so every claim is traceable to a source id.
- **Fixed short-answer vocabulary.** Buyers' scoring sheets want Yes/No/Partial, and an enum is easy to validate and diff across deals.
- **Library reuse before generation** keeps answers consistent and skips the model for questions that repeat across deals.
- **Flags, not silent fixes.** Guardrails never rewrite an answer; they route it to a person.

The knowledge base in `examples/` describes a fictional product.
