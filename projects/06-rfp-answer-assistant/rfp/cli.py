"""Answer a questionnaire CSV from a knowledge folder and an approved-answer library."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .answering import Answer, AnthropicAnswerer, ExtractiveAnswerer
from .guardrails import lint
from .retrieval import Retriever, load_chunks, similarity

LIBRARY_REUSE_THRESHOLD = 0.5


def library_match(question: str, library: list[dict]) -> tuple[dict | None, float]:
    best, best_score = None, 0.0
    for entry in library:
        score = similarity(question, entry["question"])
        if score > best_score:
            best, best_score = entry, score
    return best, best_score


def answer_questionnaire(rows: list[dict], retriever: Retriever, library: list[dict], answerer) -> list[dict]:
    results = []
    for row in rows:
        entry, score = library_match(row["question"], library)
        if entry and score >= LIBRARY_REUSE_THRESHOLD:
            answer = Answer(entry["short_answer"], entry["long_answer"], "high", [f"library:{entry['id']}"],
                            f"reused approved answer (similarity {score:.2f})", "library")
        else:
            answer = answerer.answer(row["question"], row.get("section", ""), retriever.search(row["question"]))
        answer.flags = answer.flags + lint(answer)
        results.append({
            "id": row["id"],
            "section": row.get("section", ""),
            "question": row["question"],
            "short_answer": answer.short_answer,
            "long_answer": answer.long_answer,
            "confidence": answer.confidence,
            "sources": "; ".join(answer.source_ids),
            "origin": answer.origin,
            "needs_review": "yes" if answer.flags else "no",
            "flags": "; ".join(answer.flags),
        })
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questionnaire", type=Path)
    parser.add_argument("--knowledge", type=Path, required=True)
    parser.add_argument("--library", type=Path)
    parser.add_argument("--out", type=Path, default=Path("answers.csv"))
    parser.add_argument("--provider", default="extractive", help="extractive (offline) or anthropic[:model]")
    args = parser.parse_args(argv)

    with args.questionnaire.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    library = json.loads(args.library.read_text()) if args.library else []
    if args.provider.startswith("anthropic"):
        _, _, model = args.provider.partition(":")
        answerer = AnthropicAnswerer(model or "claude-opus-5-5")
    else:
        answerer = ExtractiveAnswerer()

    results = answer_questionnaire(rows, Retriever(load_chunks(args.knowledge)), library, answerer)
    with args.out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    review = sum(r["needs_review"] == "yes" for r in results)
    reused = sum(r["origin"] == "library" for r in results)
    print(f"{len(results)} answered -> {args.out}  ({reused} reused from library, {review} flagged for review)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
