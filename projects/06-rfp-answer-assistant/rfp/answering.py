from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .retrieval import Chunk, tokens

SHORT_ANSWERS = ["Yes", "No", "Partial", "Roadmap", "Not applicable"]

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "short_answer": {"type": "string", "enum": SHORT_ANSWERS},
        "long_answer": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "source_ids": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["short_answer", "long_answer", "confidence", "source_ids", "rationale"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You answer vendor security and product questionnaires for a software company.
Answer only from the numbered sources provided. If the sources do not cover the question, set confidence to "low",
choose the short answer that is safest without overclaiming, and say what is missing in the rationale.
Never promise guarantees, certifications, or timelines that the sources do not state.
long_answer: two to four plain sentences a buyer's security reviewer can read. Cite sources by id in source_ids."""


@dataclass
class Answer:
    short_answer: str
    long_answer: str
    confidence: str
    source_ids: list[str]
    rationale: str
    origin: str
    flags: list[str] = field(default_factory=list)


def format_sources(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{c.id}] {c.source} — {c.heading}\n{c.text}" for c in chunks)


class AnthropicAnswerer:
    def __init__(self, model: str = "claude-opus-5-5", client=None):
        self.model = model
        self.client = client
        self.name = f"anthropic:{model}"

    def answer(self, question: str, section: str, chunks: list[tuple[Chunk, float]]) -> Answer:
        if self.client is None:
            import anthropic

            self.client = anthropic.Anthropic()
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}},
            messages=[{"role": "user", "content": f"Sources:\n{format_sources([c for c, _ in chunks])}\n\nSection: {section}\nQuestion: {question}"}],
        )
        if response.stop_reason == "refusal":
            return Answer("Not applicable", "", "low", [], "model declined to answer", self.name, ["refused"])
        text = next(block.text for block in response.content if block.type == "text")
        return Answer(**json.loads(text), origin=self.name)


class ExtractiveAnswerer:
    """Offline baseline: quotes the best-matching passage and infers a short answer from its wording."""

    name = "extractive"

    def answer(self, question: str, section: str, chunks: list[tuple[Chunk, float]]) -> Answer:
        if not chunks:
            return Answer("Not applicable", "No supporting documentation found.", "low", [], "no retrieval hits", self.name)
        best, score = chunks[0]
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", best.text.strip()) if s]
        asked = set(tokens(question))
        focus = max(range(len(sentences)), key=lambda i: len(asked & set(tokens(sentences[i]))))
        lowered = sentences[focus].lower()
        if re.search(r"\b(planned|roadmap|later this year|next quarter)\b", lowered):
            short = "Roadmap"
        elif re.search(r"\b(not supported|not available|do not|does not|no support)\b", lowered):
            short = "No"
        elif re.search(r"\b(partially|limited|only for|on request)\b", lowered):
            short = "Partial"
        else:
            short = "Yes"
        confidence = "high" if score > 0.35 else "medium" if score > 0.18 else "low"
        excerpt = " ".join(sentences[max(0, focus - 1): focus + 2])
        return Answer(short, excerpt, confidence, [best.id], f"passage score {score:.2f}; answer keyed on: {sentences[focus]!r}", self.name)
