"""Deterministic and vector-based policy document ingestion, chunking, and retrieval."""

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from resolveai.config import Settings, get_settings


@dataclass(frozen=True)
class PolicyChunk:
    text: str
    source: str
    chunk_id: str
    policy_id: str = ""
    policy_version: str = ""
    section: str = ""
    chunk_index: int = 1
    citation: str = ""


@dataclass(frozen=True)
class PolicyMatch:
    text: str
    source: str
    chunk_id: str
    score: float | int
    policy_id: str = ""
    policy_version: str = ""
    section: str = ""
    citation: str = ""


class PolicyRetrievalResult(BaseModel):
    """Structured policy retrieval result with citation and metadata."""

    text: str
    source: str
    chunk_id: str
    policy_id: str
    policy_version: str
    section: str
    score: float = Field(ge=0.0)
    citation: str

    def to_evidence(self) -> Any:
        from resolveai.schemas import Evidence

        return Evidence(
            source=f"policy:{self.source}",
            status="policy",
            summary=self.text[:300],
            citation=self.citation,
            details={
                "policy_id": self.policy_id,
                "policy_version": self.policy_version,
                "section": self.section,
                "chunk_id": self.chunk_id,
                "score": round(self.score, 4),
            },
        )


class IngestionReport(BaseModel):
    """Summary of policy ingestion execution."""

    documents_loaded: int = 0
    chunks_added: int = 0
    chunks_updated: int = 0
    chunks_skipped: int = 0
    chunks_rejected: int = 0


def slugify(text: str) -> str:
    """Produce a deterministic, URL/ID-safe slug."""
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned) or "section"


def parse_policy_metadata(content: str) -> tuple[str, str, str]:
    """Extract policy identifier, version, and primary title from content."""
    clean = content.replace("*", "")
    pid_match = re.search(
        r"(?:Policy\s*Identifier|Policy\s*ID):\s*([A-Za-z0-9_-]+)",
        clean,
        re.IGNORECASE,
    )
    ver_match = re.search(
        r"Version:\s*([vV]?[0-9]+(?:\.[0-9]+)*)",
        clean,
        re.IGNORECASE,
    )
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)

    policy_id = pid_match.group(1).strip() if pid_match else "UNKNOWN"
    version = ver_match.group(1).strip() if ver_match else "1.0.0"
    title = title_match.group(1).strip() if title_match else ""
    return policy_id, version, title


def load_policy_chunks(
    policy_dir: str | Path,
    section_aware: bool = True,
) -> list[PolicyChunk]:
    """Load Markdown/text policies and split them into section-aware chunks."""
    directory = Path(policy_dir)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Policy directory not found: {directory}")

    chunks: list[PolicyChunk] = []
    files = sorted(
        p
        for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in {".md", ".txt"}
    )

    for path in files:
        content = path.read_text(encoding="utf-8-sig").strip()
        if not content:
            continue

        rel_source = path.relative_to(directory).as_posix()
        policy_id, version, title = parse_policy_metadata(content)

        # Check if the document has markdown sections (## headings)
        sections = re.split(r"(?m)^(?=##\s+)", content)
        has_sections = section_aware and len(sections) > 1

        if has_sections:
            chunk_seq = 0
            for sec_text in sections:
                sec_text = sec_text.strip()
                if not sec_text:
                    continue

                lines = sec_text.splitlines()
                first_line = lines[0].strip()
                if first_line.startswith("##"):
                    section_title = first_line.lstrip("#").strip()
                    body = "\n".join(lines[1:]).strip()
                else:
                    section_title = title or "Overview"
                    body = sec_text

                sec_slug = slugify(section_title)
                paragraphs = re.split(r"\n\s*\n", body)

                for p_idx, paragraph in enumerate(paragraphs, start=1):
                    p_text = paragraph.strip()
                    if not p_text:
                        continue

                    chunk_seq += 1
                    chunk_id = f"{path.stem}-{sec_slug}-{p_idx}"
                    citation = f"[{policy_id} v{version} {rel_source}#{sec_slug}]"
                    chunks.append(
                        PolicyChunk(
                            text=p_text,
                            source=rel_source,
                            chunk_id=chunk_id,
                            policy_id=policy_id,
                            policy_version=version,
                            section=section_title,
                            chunk_index=chunk_seq,
                            citation=citation,
                        )
                    )
        else:
            # Fallback for simple documents without ## sections
            paragraphs = re.split(r"\n\s*\n", content)
            active_section = title or "General"
            for index, paragraph in enumerate(paragraphs, start=1):
                text = paragraph.strip()
                if text:
                    sec_slug = slugify(active_section)
                    citation = f"[{policy_id} v{version} {rel_source}#{sec_slug}]"
                    chunks.append(
                        PolicyChunk(
                            text=text,
                            source=rel_source,
                            chunk_id=f"{path.stem}-{index}",
                            policy_id=policy_id,
                            policy_version=version,
                            section=active_section,
                            chunk_index=index,
                            citation=citation,
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
                    policy_id=chunk.policy_id,
                    policy_version=chunk.policy_version,
                    section=chunk.section,
                    citation=chunk.citation,
                )
            )

    matches.sort(key=lambda item: (-item.score, item.source, item.chunk_id))
    return matches[:top_k]


class DeterministicFakeEmbeddingFunction:
    """Fast, offline, deterministic pseudo-embeddings for unit tests."""

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]

    def is_legacy(self) -> bool:
        return False

    def get_config(self) -> dict[str, Any]:
        return {"dimension": self.dimension}

    @classmethod
    def build_from_config(cls, config: dict[str, Any]) -> "DeterministicFakeEmbeddingFunction":
        return cls(dimension=config.get("dimension", 384))

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    @staticmethod
    def name() -> str:
        return "deterministic_fake"

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def __call__(self, input: list[str]) -> list[list[float]]:
        results = []
        for text in input:
            tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
            vec = [0.0] * self.dimension
            for token in tokens:
                digest = int(
                    hashlib.md5(token.encode("utf-8")).hexdigest(), 16
                )
                idx = digest % self.dimension
                vec[idx] += 1.0
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            else:
                vec[0] = 1.0
            results.append(vec)
        return results


class LocalSentenceTransformerEmbedding:
    """Locally cached SentenceTransformer embedding wrapper for ChromaDB."""

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]

    def is_legacy(self) -> bool:
        return False

    def get_config(self) -> dict[str, Any]:
        return {"model_name": self.model_name}

    @classmethod
    def build_from_config(cls, config: dict[str, Any]) -> "LocalSentenceTransformerEmbedding":
        return cls(model_name=config.get("model_name", "all-MiniLM-L6-v2"))

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model: Any = None

    @staticmethod
    def name() -> str:
        return "local_sentence_transformer"

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                try:
                    self._model = SentenceTransformer(
                        self.model_name,
                        local_files_only=True,
                    )
                except Exception:
                    self._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Local embedding model '{self.model_name}' could not be loaded: {exc}."
                ) from exc
        return self._model

    def __call__(self, input: list[str]) -> list[list[float]]:
        model = self._get_model()
        embeddings = model.encode(input, convert_to_numpy=True)
        return embeddings.tolist()


def get_default_embedding_function(model_name: str = "all-MiniLM-L6-v2") -> Any:
    return LocalSentenceTransformerEmbedding(model_name=model_name)


class PolicyVectorStore:
    """ChromaDB-backed local vector store for policy ingestion and retrieval."""

    def __init__(
        self,
        chroma_dir: str | Path = "data/chroma",
        collection_name: str = "resolveai_policies",
        embedding_function: Any = None,
        settings: Settings | None = None,
    ):
        self.chroma_dir = Path(chroma_dir)
        self.collection_name = collection_name
        self.settings = settings or get_settings()
        self._embedding_function = embedding_function
        self._client: Any = None
        self._collection: Any = None

    @property
    def embedding_function(self) -> Any:
        if self._embedding_function is None:
            self._embedding_function = get_default_embedding_function(
                self.settings.embedding_model_name
            )
        return self._embedding_function

    def _get_collection(self) -> Any:
        if self._collection is None:
            try:
                import chromadb
            except ImportError as exc:
                raise RuntimeError(
                    "ChromaDB is required for vector storage. Install chromadb."
                ) from exc

            self.chroma_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.chroma_dir))
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def count(self) -> int:
        return self._get_collection().count()

    def reset(self) -> None:
        """Clear all policy chunks from the collection."""
        try:
            import chromadb

            if self._client is None:
                self.chroma_dir.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self.chroma_dir)
                )
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = None

    def ingest_chunks(self, chunks: list[PolicyChunk]) -> IngestionReport:
        """Idempotently ingest chunks using stable chunk IDs."""
        report = IngestionReport()
        if not chunks:
            return report

        collection = self._get_collection()

        # Deduplicate chunks by ID while preserving order
        unique_chunks: dict[str, PolicyChunk] = {}
        for chunk in chunks:
            if not chunk.text.strip():
                report.chunks_rejected += 1
                continue
            if chunk.chunk_id in unique_chunks:
                report.chunks_skipped += 1
            else:
                unique_chunks[chunk.chunk_id] = chunk

        if not unique_chunks:
            return report

        try:
            existing_data = collection.get(ids=list(unique_chunks.keys()))
            existing_ids = set(existing_data.get("ids", []))
        except Exception:
            existing_ids = set()

        ids = []
        documents = []
        metadatas = []

        for chunk_id, chunk in unique_chunks.items():
            ids.append(chunk_id)
            documents.append(chunk.text)
            metadatas.append(
                {
                    "source": chunk.source,
                    "policy_id": chunk.policy_id,
                    "policy_version": chunk.policy_version,
                    "section": chunk.section,
                    "chunk_id": chunk.chunk_id,
                    "chunk_index": chunk.chunk_index,
                    "citation": chunk.citation,
                }
            )
            if chunk_id in existing_ids:
                report.chunks_updated += 1
            else:
                report.chunks_added += 1

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        return report

    def ingest_directory(
        self,
        policy_dir: str | Path = "docs/policies",
    ) -> IngestionReport:
        """Load and ingest all policy documents from the directory."""
        directory = Path(policy_dir)
        if not directory.exists() or not directory.is_dir():
            raise FileNotFoundError(f"Policy directory not found: {directory}")

        files = sorted(
            p
            for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in {".md", ".txt"}
        )

        chunks = load_policy_chunks(directory)
        report = self.ingest_chunks(chunks)
        report.documents_loaded = len(files)
        return report

    def query(
        self,
        query: str,
        top_k: int = 3,
        relevance_threshold: float = 0.0,
    ) -> list[PolicyRetrievalResult]:
        """Rank policy chunks by vector similarity, enforcing relevance threshold."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        collection = self._get_collection()
        total_count = collection.count()
        if total_count == 0:
            return []

        limit = min(top_k, total_count)
        results = collection.query(
            query_texts=[query],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        matches: list[PolicyRetrievalResult] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            # Cosine distance ranges [0, 2]; similarity in [0, 1]
            similarity = max(0.0, min(1.0, 1.0 - dist))
            if similarity < relevance_threshold:
                continue

            citation = meta.get(
                "citation",
                f"[{meta.get('policy_id', 'UNKNOWN')} {meta.get('source', '')}]",
            )
            matches.append(
                PolicyRetrievalResult(
                    text=doc,
                    source=meta.get("source", ""),
                    chunk_id=meta.get("chunk_id", ""),
                    policy_id=meta.get("policy_id", ""),
                    policy_version=meta.get("policy_version", ""),
                    section=meta.get("section", ""),
                    score=similarity,
                    citation=citation,
                )
            )

        matches.sort(key=lambda item: -item.score)
        return matches[:top_k]
