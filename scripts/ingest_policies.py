"""Ingest and index policy documents into persistent ChromaDB vector storage."""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolveai.config import get_settings
from resolveai.policies import PolicyVectorStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Markdown support policy documents into ChromaDB."
    )
    parser.add_argument(
        "--policy-dir",
        type=str,
        default=None,
        help="Path to directory containing policy documents (default: settings.policy_dir).",
    )
    parser.add_argument(
        "--chroma-dir",
        type=str,
        default=None,
        help="Path to ChromaDB storage directory (default: settings.chroma_dir).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing collection before ingesting.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed output.",
    )
    args = parser.parse_args()

    settings = get_settings()
    policy_dir = Path(args.policy_dir or settings.policy_dir)
    chroma_dir = Path(args.chroma_dir or settings.chroma_dir)

    if not policy_dir.exists():
        print(f"Error: Policy directory not found: {policy_dir}", file=sys.stderr)
        return 1

    if not args.quiet:
        print("ResolveAI Policy Knowledge Base Ingestion")
        print(f"Policy directory: {policy_dir}")
        print(f"Chroma storage:   {chroma_dir}")
        print(f"Embedding model:  {settings.embedding_model_name}")

    start_time = time.perf_counter()
    try:
        store = PolicyVectorStore(
            chroma_dir=chroma_dir,
            settings=settings,
        )

        if args.reset:
            if not args.quiet:
                print("Resetting existing vector store collection...")
            store.reset()

        report = store.ingest_directory(policy_dir)
        total_chunks = store.count()
        elapsed = time.perf_counter() - start_time

        if not args.quiet:
            print("\nIngestion Summary:")
            print(f"  Documents loaded: {report.documents_loaded}")
            print(f"  Chunks added:     {report.chunks_added}")
            print(f"  Chunks updated:   {report.chunks_updated}")
            print(f"  Chunks skipped:   {report.chunks_skipped}")
            print(f"  Chunks rejected:  {report.chunks_rejected}")
            print(f"  Total chunks in index: {total_chunks}")
            print(f"  Execution time:   {elapsed:.2f}s")
            print("\nVector index is ready for autonomous agent queries.")

        return 0

    except Exception as exc:
        print(f"Error during policy ingestion: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
