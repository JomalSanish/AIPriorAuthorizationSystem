#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Reconfigure stdout to support UTF-8 on Windows consoles
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to python path to avoid import errors
sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils.vector_store import load_persistent_policy_store, hybrid_policy_search


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Query the persistent hybrid policy search index.")
    parser.add_argument("--query", type=str, required=True, help="Semantic or keyword query phrase.")
    parser.add_argument("--cpt", type=str, default=None, help="Optional CPT code filter/boost.")
    parser.add_argument("--k", type=int, default=3, help="Number of results to retrieve.")
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.5,
        help="Weight balance between vector (1.0) and lexical (0.0) search.",
    )

    args = parser.parse_args()

    print("Loading persistent policy indices...")
    store = load_persistent_policy_store()
    if not store:
        print("Error: Persistent policy store not found. Please run: python utils/ingest_policies.py first.")
        sys.exit(1)

    faiss_db, bm25_retriever = store
    print(f"Executing hybrid search for: '{args.query}' (CPT={args.cpt}, alpha={args.alpha})...\n")

    results = hybrid_policy_search(
        query=args.query,
        faiss_db=faiss_db,
        bm25_retriever=bm25_retriever,
        cpt_code=args.cpt,
        k=args.k,
        alpha=args.alpha,
    )

    if not results:
        print("No matching policy segments found.")
        return

    for i, (doc, score) in enumerate(results, 1):
        print(f"--- Match {i} [Score: {score:.4f}] ---")
        print(f"Source: {doc.metadata.get('source', 'unknown')} | Page: {doc.metadata.get('page', 'unknown')}")
        print(f"CPT Codes: {doc.metadata.get('cpt_codes', [])}")
        print(f"Content Preview:\n{doc.page_content}\n")


if __name__ == "__main__":
    main()
