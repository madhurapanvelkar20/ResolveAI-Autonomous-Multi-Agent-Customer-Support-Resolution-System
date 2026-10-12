"""Deterministic policy-document ingestion and retrieval."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PolicyChunk:
    text: str
    source: str
    chunk_id: str


@dataclass(frozen=True)
class PolicyMatch:
    text: str
    source: str
    chunk_id: str
    score: int


def load_policy_chunks(policy_dir: str | Path) -> list[PolicyChunk]:
    """Load Markdown/text policies and split them into paragraph chunks."""
    directory = Path(policy_dir)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Policy directory not found: {directory}")

    chunks = []
    files = sorted(
        p for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in {".md", ".txt"}
    )

    for path in files:
        content = path.read_text(encoding="utf-8-sig").strip()
        paragraphs = re.split(r"\n\s*\n", content)

        for index, paragraph in enumerate(paragraphs, start=1):
            text = paragraph.strip()
            if text:
                chunks.append(
                    PolicyChunk(
                        text=text,
                        source=path.relative_to(directory).as_posix(),
                        chunk_id=f"{path.stem}-{index}",
                    )
                )

    return chunks


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[a-zA-Z0-9]+", text)
        if len(token) > 1
    }


def retrieve_policies(
    query: str,
    policy_dir: str | Path = "docs/policies",
    top_k: int = 3,
) -> list[PolicyMatch]:
    """Rank policy chunks by deterministic lexical overlap."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must not be empty")
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    matches = []
    for chunk in load_policy_chunks(policy_dir):
        chunk_tokens = _tokens(chunk.text)
        score = len(query_tokens & chunk_tokens)
        if score:
            matches.append(
                PolicyMatch(
                    text=chunk.text,
                    source=chunk.source,
                    chunk_id=chunk.chunk_id,
                    score=score,
                )
            )

    matches.sort(key=lambda item: (-item.score, item.source, item.chunk_id))
    return matches[:top_k]
