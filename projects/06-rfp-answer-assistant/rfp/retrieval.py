"""Small TF-IDF retriever over a folder of markdown, chunked by heading."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

STOPWORDS = set("a an and are as at be by can do does for from has have how in is it its of on or our that the this to we what when where which who why will with you your".split())


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokens(text: str) -> list[str]:
    return [stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and len(t) > 1]


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    heading: str
    text: str


def load_chunks(folder: str | Path) -> list[Chunk]:
    chunks = []
    for path in sorted(Path(folder).glob("*.md")):
        title, heading, buffer, index = path.stem, path.stem, [], [0]

        def flush():
            body = "\n".join(buffer).strip()
            if body:
                index[0] += 1
                chunks.append(Chunk(f"{path.stem}#{index[0]}", title, heading, body))

        for line in path.read_text().splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.startswith("## "):
                flush()
                heading, buffer = line[3:].strip(), []
            else:
                buffer.append(line)
        flush()
    return chunks


class Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.vectors = [Counter(tokens(f"{c.heading} {c.heading} {c.text}")) for c in chunks]
        df = Counter(term for vector in self.vectors for term in vector)
        self.idf = {term: math.log((1 + len(chunks)) / (1 + n)) + 1 for term, n in df.items()}
        self.norms = [self._norm(v) for v in self.vectors]

    def _weights(self, counts: Counter) -> dict[str, float]:
        return {t: n * self.idf.get(t, 0.0) for t, n in counts.items()}

    def _norm(self, counts: Counter) -> float:
        return math.sqrt(sum(w * w for w in self._weights(counts).values())) or 1.0

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        q = self._weights(Counter(tokens(query)))
        q_norm = math.sqrt(sum(w * w for w in q.values())) or 1.0
        scored = []
        for chunk, vector, norm in zip(self.chunks, self.vectors, self.norms):
            weights = self._weights(vector)
            score = sum(w * weights.get(t, 0.0) for t, w in q.items()) / (q_norm * norm)
            if score > 0:
                scored.append((chunk, score))
        return sorted(scored, key=lambda pair: pair[1], reverse=True)[:k]


def similarity(a: str, b: str) -> float:
    ta, tb = set(tokens(a)), set(tokens(b))
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0
