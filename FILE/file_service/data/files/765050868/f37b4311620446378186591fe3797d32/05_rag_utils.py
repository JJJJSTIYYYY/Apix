"""Synthetic RAG utility for chunking and scoring retrieval overlap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class Chunk:
    """Represents a text chunk used in retrieval experiments."""

    chunk_id: str
    text: str


def split_into_chunks(text: str, max_words: int = 40) -> List[Chunk]:
    """Split text into fixed-size word chunks."""
    words = text.split()
    chunks: List[Chunk] = []
    for index in range(0, len(words), max_words):
        part = words[index:index + max_words]
        chunk_text = " ".join(part)
        chunk_id = f"chunk-{index // max_words + 1}"
        chunks.append(Chunk(chunk_id=chunk_id, text=chunk_text))
    return chunks


def keyword_overlap(query: str, passages: Iterable[str]) -> float:
    """Compute a simple overlap score between a query and passages."""
    query_terms = set(query.lower().split())
    if not query_terms:
        return 0.0

    matched = set()
    for passage in passages:
        matched.update(query_terms.intersection(passage.lower().split()))

    return len(matched) / len(query_terms)


if __name__ == "__main__":
    sample_text = (
        "RAG systems often benefit from chunk boundaries that preserve topic coherence "
        "instead of splitting blindly across section headings and lists."
    )
    chunks = split_into_chunks(sample_text, max_words=8)
    score = keyword_overlap("topic coherence chunk boundaries", [c.text for c in chunks])

    for chunk in chunks:
        print(f"{chunk.chunk_id}: {chunk.text}")
    print(f"overlap_score={score:.2f}")
