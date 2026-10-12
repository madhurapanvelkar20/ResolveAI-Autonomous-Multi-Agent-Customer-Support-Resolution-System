from pathlib import Path

import pytest

from resolveai.policies import load_policy_chunks, retrieve_policies


def test_loads_policy_paragraphs(tmp_path: Path):
    (tmp_path / "refunds.md").write_text(
        "# Refunds\n\nVerify the captured payment.\n\n"
        "Human review is required for exceptional refunds.",
        encoding="utf-8",
    )

    chunks = load_policy_chunks(tmp_path)

    assert len(chunks) == 3
    assert chunks[1].source == "refunds.md"
    assert "captured payment" in chunks[1].text


def test_retrieves_relevant_policy_first(tmp_path: Path):
    (tmp_path / "refunds.md").write_text(
        "Verify captured payments before processing a refund.",
        encoding="utf-8",
    )
    (tmp_path / "shipping.md").write_text(
        "Check the shipping carrier for delivery updates.",
        encoding="utf-8",
    )

    results = retrieve_policies("refund captured payment", tmp_path)

    assert results
    assert results[0].source == "refunds.md"
    assert results[0].score > 0


def test_no_matching_policy_returns_empty_list(tmp_path: Path):
    (tmp_path / "refunds.md").write_text(
        "Verify captured payments before processing a refund.",
        encoding="utf-8",
    )

    assert retrieve_policies("volcano astronomy", tmp_path) == []


def test_empty_query_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="Query"):
        retrieve_policies("  ", tmp_path)


def test_invalid_top_k_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="top_k"):
        retrieve_policies("refund", tmp_path, top_k=0)


def test_missing_policy_directory_is_rejected(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_policy_chunks(tmp_path / "missing")


def test_empty_policy_directory_returns_no_chunks(tmp_path: Path):
    assert load_policy_chunks(tmp_path) == []
    assert retrieve_policies("refund payment", tmp_path) == []


def test_top_k_limits_results(tmp_path: Path):
    (tmp_path / "a.md").write_text("Refund payment verification.", encoding="utf-8")
    (tmp_path / "b.md").write_text("Refund payment approval.", encoding="utf-8")

    results = retrieve_policies("refund payment", tmp_path, top_k=1)

    assert len(results) == 1
