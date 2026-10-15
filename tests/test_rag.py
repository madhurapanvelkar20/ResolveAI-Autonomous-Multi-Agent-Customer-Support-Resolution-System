"""Phase 3 tests: Policy knowledge base, chunking, persistent ChromaDB, and RAG retrieval."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from resolveai.policies import (
    DeterministicFakeEmbeddingFunction,
    PolicyChunk,
    PolicyVectorStore,
    load_policy_chunks,
    parse_policy_metadata,
)
from resolveai.tools import (
    AGENT_TOOL_ALLOWLIST,
    TOOL_REGISTRY,
    KnowledgeBaseSearch,
    OrderLookup,
    PaymentLookup,
    execute_tool,
    search_knowledge_base,
    set_policy_store_override,
)


REQUIRED_POLICY_FILES = [
    "refunds.md",
    "cancellations.md",
    "returns.md",
    "payments.md",
    "delivery.md",
    "damaged_products.md",
    "escalations.md",
]

REQUIRED_SECTIONS = [
    "1. Purpose and Scope",
    "2. Eligibility Conditions",
    "3. Explicit Time Windows and Thresholds",
    "4. Required Evidence and Information",
    "5. Conditions Requiring Manual Review",
    "6. Conditions Prohibiting Automatic Approval",
    "7. Required Actions and Customer Support Guidance",
    "8. Examples of Eligible and Ineligible Cases",
]


def test_all_seven_policy_documents_exist_and_contain_required_sections():
    """All 7 required policy documents must exist and have all 8 standard sections."""
    policy_dir = Path("docs/policies")
    assert policy_dir.exists() and policy_dir.is_dir()

    for filename in REQUIRED_POLICY_FILES:
        path = policy_dir / filename
        assert path.exists(), f"Policy file missing: {filename}"
        content = path.read_text(encoding="utf-8")
        assert len(content.strip()) > 200, f"Policy file too short: {filename}"

        policy_id, version, title = parse_policy_metadata(content)
        assert policy_id.startswith("POL-"), f"Invalid policy ID in {filename}: {policy_id}"
        assert version, f"Missing version in {filename}"
        assert title, f"Missing main title in {filename}"

        for section in REQUIRED_SECTIONS:
            assert f"## {section}" in content, (
                f"Missing section '{section}' in {filename}"
            )


def test_section_aware_chunking_and_metadata_preservation(tmp_path: Path):
    """Section-aware chunking preserves section title, slug, policy metadata, and citations."""
    sample_policy = (
        "# Refund Policy\n\n"
        "**Policy Identifier:** POL-REF-999  \n"
        "**Version:** 2.1.0  \n\n"
        "## 1. Purpose and Scope\n\n"
        "This policy covers all consumer refund requests.\n\n"
        "Refunds must be verified before payment disbursement.\n\n"
        "## 2. Eligibility Conditions\n\n"
        "Eligible within 30 days of delivery.\n"
    )
    (tmp_path / "refunds.md").write_text(sample_policy, encoding="utf-8")

    chunks = load_policy_chunks(tmp_path, section_aware=True)
    assert len(chunks) == 5

    c0 = chunks[2]
    assert c0.policy_id == "POL-REF-999"
    assert c0.policy_version == "2.1.0"
    assert c0.section == "1. Purpose and Scope"
    assert "refunds-1-purpose-and-scope-1" in c0.chunk_id
    assert "[POL-REF-999 v2.1.0 refunds.md#1-purpose-and-scope]" in c0.citation
    assert "This policy covers all consumer refund requests." in c0.text

    c1 = chunks[3]
    assert "refunds-1-purpose-and-scope-2" in c1.chunk_id
    assert "Refunds must be verified" in c1.text

    c2 = chunks[4]
    assert c2.section == "2. Eligibility Conditions"
    assert "refunds-2-eligibility-conditions-1" in c2.chunk_id


def test_stable_ids_and_idempotent_ingestion(tmp_path: Path):
    """Repeated ingestion of identical chunks produces zero duplicates and updates existing."""
    chroma_dir = tmp_path / "chroma"
    store = PolicyVectorStore(
        chroma_dir=chroma_dir,
        embedding_function=DeterministicFakeEmbeddingFunction(),
    )

    chunks = [
        PolicyChunk(
            text="Refund threshold is 100 dollars.",
            source="refunds.md",
            chunk_id="ref-threshold-1",
            policy_id="POL-REF-001",
            policy_version="1.0.0",
            section="Thresholds",
            citation="[POL-REF-001 v1.0.0 refunds.md#thresholds]",
        ),
        PolicyChunk(
            text="Damaged item requires photos.",
            source="damaged.md",
            chunk_id="dam-evidence-1",
            policy_id="POL-DAM-001",
            policy_version="1.0.0",
            section="Evidence",
            citation="[POL-DAM-001 v1.0.0 damaged.md#evidence]",
        ),
    ]

    report1 = store.ingest_chunks(chunks)
    assert report1.chunks_added == 2
    assert report1.chunks_updated == 0
    assert store.count() == 2

    # Second ingestion
    report2 = store.ingest_chunks(chunks)
    assert report2.chunks_added == 0
    assert report2.chunks_updated == 2
    assert store.count() == 2


def test_empty_and_missing_directory_handling(tmp_path: Path):
    """Missing directory raises FileNotFoundError; empty directory returns empty report."""
    chroma_dir = tmp_path / "chroma"
    store = PolicyVectorStore(
        chroma_dir=chroma_dir,
        embedding_function=DeterministicFakeEmbeddingFunction(),
    )

    with pytest.raises(FileNotFoundError):
        store.ingest_directory(tmp_path / "nonexistent")

    empty_dir = tmp_path / "empty_policies"
    empty_dir.mkdir()
    report = store.ingest_directory(empty_dir)
    assert report.documents_loaded == 0
    assert report.chunks_added == 0
    assert store.count() == 0


def test_malformed_and_empty_files_handling(tmp_path: Path):
    """Empty and whitespace files are skipped gracefully without crashing."""
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    (tmp_path / "whitespace.txt").write_text("   \n\n   ", encoding="utf-8")
    (tmp_path / "valid.md").write_text("# Valid\n\nSome text content.", encoding="utf-8")

    chunks = load_policy_chunks(tmp_path)
    assert len(chunks) == 2  # "# Valid" and "Some text content."
    assert all(c.source == "valid.md" for c in chunks)


def test_retrieval_ranking_and_metadata(tmp_path: Path):
    """Retriever returns ranked chunks with similarity scores and correct citations."""
    chroma_dir = tmp_path / "chroma"
    store = PolicyVectorStore(
        chroma_dir=chroma_dir,
        embedding_function=DeterministicFakeEmbeddingFunction(),
    )

    chunks = [
        PolicyChunk(
            text="Standard ground shipping takes three to seven business days.",
            source="delivery.md",
            chunk_id="del-1",
            policy_id="POL-DEL-001",
            policy_version="1.0.0",
            section="Delivery Timeline",
            citation="[POL-DEL-001 v1.0.0 delivery.md#delivery-timeline]",
        ),
        PolicyChunk(
            text="Autonomous refunds can be approved up to 100 dollars for eligible claims.",
            source="refunds.md",
            chunk_id="ref-1",
            policy_id="POL-REF-001",
            policy_version="1.0.0",
            section="Refund Limits",
            citation="[POL-REF-001 v1.0.0 refunds.md#refund-limits]",
        ),
    ]
    store.ingest_chunks(chunks)

    results = store.query("refunds limit 100 dollars", top_k=2)
    assert len(results) >= 1
    top = results[0]
    assert top.chunk_id == "ref-1"
    assert top.policy_id == "POL-REF-001"
    assert top.source == "refunds.md"
    assert top.score > 0
    assert "[POL-REF-001 v1.0.0 refunds.md#refund-limits]" in top.citation


def test_relevance_threshold_and_no_result_behavior(tmp_path: Path):
    """Relevance threshold filters out unrelated chunks instead of returning false matches."""
    chroma_dir = tmp_path / "chroma"
    store = PolicyVectorStore(
        chroma_dir=chroma_dir,
        embedding_function=DeterministicFakeEmbeddingFunction(),
    )

    chunks = [
        PolicyChunk(
            text="Refund limits are strictly capped.",
            source="refunds.md",
            chunk_id="ref-1",
            policy_id="POL-REF-001",
            policy_version="1.0.0",
            section="Thresholds",
            citation="[POL-REF-001 v1.0.0 refunds.md#thresholds]",
        ),
    ]
    store.ingest_chunks(chunks)

    # Completely unrelated query with high threshold returns empty
    results = store.query("astronomy telescope volcano", top_k=2, relevance_threshold=0.8)
    assert results == []

    # Empty store returns empty
    empty_store = PolicyVectorStore(
        chroma_dir=tmp_path / "empty_chroma",
        embedding_function=DeterministicFakeEmbeddingFunction(),
    )
    assert empty_store.query("refund", top_k=2) == []


def test_evidence_conversion_from_retrieval_result():
    """PolicyRetrievalResult converts cleanly into a typed Evidence object."""
    from resolveai.policies import PolicyRetrievalResult

    result = PolicyRetrievalResult(
        text="Refund limit is $100.",
        source="refunds.md",
        chunk_id="ref-1",
        policy_id="POL-REF-001",
        policy_version="1.0.0",
        section="Thresholds",
        score=0.88,
        citation="[POL-REF-001 v1.0.0 refunds.md#thresholds]",
    )

    evidence = result.to_evidence()
    assert evidence.status == "policy"
    assert evidence.source == "policy:refunds.md"
    assert evidence.citation == "[POL-REF-001 v1.0.0 refunds.md#thresholds]"
    assert evidence.details["policy_id"] == "POL-REF-001"
    assert evidence.details["score"] == 0.88


def test_tool_registry_and_schemas():
    """Tool registry includes search_knowledge_base, OrderLookup, and PaymentLookup."""
    assert "search_knowledge_base" in TOOL_REGISTRY
    assert "lookup_order" in TOOL_REGISTRY
    assert "lookup_payment" in TOOL_REGISTRY

    order_model, _ = TOOL_REGISTRY["lookup_order"]
    assert order_model is OrderLookup
    payment_model, _ = TOOL_REGISTRY["lookup_payment"]
    assert payment_model is PaymentLookup
    kb_model, _ = TOOL_REGISTRY["search_knowledge_base"]
    assert kb_model is KnowledgeBaseSearch


def test_agent_tool_allowlists():
    """Agents can only call authorized tools; triage cannot call refund or RAG."""
    assert "search_knowledge_base" in AGENT_TOOL_ALLOWLIST["investigation"]
    assert "search_knowledge_base" in AGENT_TOOL_ALLOWLIST["resolution"]
    assert "search_knowledge_base" in AGENT_TOOL_ALLOWLIST["critic"]
    assert "search_knowledge_base" not in AGENT_TOOL_ALLOWLIST["triage"]

    # Triage cannot execute RAG
    res_triage = execute_tool(
        "search_knowledge_base",
        {"query": "refund policy"},
        agent="triage",
    )
    assert res_triage["ok"] is False
    assert "not authorized" in res_triage["error"]

    # Triage cannot execute refund
    res_refund = execute_tool(
        "request_refund",
        {"payment_id": "p1", "amount": 10, "reason": "test"},
        agent="triage",
    )
    assert res_refund["ok"] is False
    assert "not authorized" in res_refund["error"]


def test_search_knowledge_base_end_to_end_with_mock_store():
    """search_knowledge_base tool returns formatted policy data and citations."""
    mock_store = MagicMock()
    from resolveai.policies import PolicyRetrievalResult

    mock_store.query.return_value = [
        PolicyRetrievalResult(
            text="Autonomous refund limit is $100.",
            source="refunds.md",
            chunk_id="ref-1",
            policy_id="POL-REF-001",
            policy_version="1.0.0",
            section="Thresholds",
            score=0.91,
            citation="[POL-REF-001 v1.0.0 refunds.md#thresholds]",
        )
    ]

    set_policy_store_override(mock_store)
    try:
        result = execute_tool(
            "search_knowledge_base",
            {"query": "refund limit", "top_k": 1},
            agent="investigation",
        )
        assert result["ok"] is True
        assert len(result["data"]) == 1
        item = result["data"][0]
        assert item["policy_id"] == "POL-REF-001"
        assert item["citation"] == "[POL-REF-001 v1.0.0 refunds.md#thresholds]"
        assert item["score"] == 0.91
    finally:
        set_policy_store_override(None)


def test_search_knowledge_base_rejects_empty_query():
    """search_knowledge_base validates input and rejects empty queries."""
    result = execute_tool(
        "search_knowledge_base",
        {"query": "   "},
        agent="investigation",
    )
    assert result["ok"] is False


def test_search_knowledge_base_handles_store_failure():
    """search_knowledge_base reports clean failure if store raises exception."""
    mock_store = MagicMock()
    mock_store.query.side_effect = RuntimeError("Chroma connection failed")

    set_policy_store_override(mock_store)
    try:
        result = execute_tool(
            "search_knowledge_base",
            {"query": "valid query"},
            agent="investigation",
        )
        assert result["ok"] is False
        assert "Policy retrieval unavailable" in result["error"]
    finally:
        set_policy_store_override(None)
