#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to python path to avoid import errors
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pickle
import re
from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from utils.vector_store import ResilientEmbeddings


def extract_cpt_codes(text: str) -> list[str]:
    """Find all 5-digit numbers that could be CPT codes in the text."""
    return sorted(list(set(re.findall(r"\b\d{5}\b", text))))


def ingest_all_policies(
    guidelines_dir: Path | str = "data/guidelines",
    faiss_out_path: Path | str = "data/indices/policies_faiss",
    bm25_out_path: Path | str = "data/indices/policies_bm25.pkl",
) -> None:
    """Ingest policy PDFs and serialize their FAISS and BM25 search indices."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    guidelines_path = Path(guidelines_dir)
    faiss_out = Path(faiss_out_path)
    bm25_out = Path(bm25_out_path)

    # Ensure output directories exist
    faiss_out.parent.mkdir(parents=True, exist_ok=True)
    bm25_out.parent.mkdir(parents=True, exist_ok=True)

    pdf_files = list(guidelines_path.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {guidelines_path}")
        return

    all_chunks: list[Document] = []

    for pdf_file in pdf_files:
        print(f"Parsing PDF guidelines from: {pdf_file.name}...")
        try:
            reader = PdfReader(str(pdf_file))
        except Exception as e:
            print(f"Error reading {pdf_file.name}: {e}. Skipping.")
            continue

        pages_docs: list[Document] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                cpt_codes = extract_cpt_codes(text)
                metadata = {
                    "source": pdf_file.name,
                    "page": i + 1,
                    "cpt_codes": cpt_codes,
                }
                pages_docs.append(Document(page_content=text, metadata=metadata))

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, length_function=len)
        chunks = text_splitter.split_documents(pages_docs)
        print(f"Generated {len(chunks)} chunks for {pdf_file.name}.")
        all_chunks.extend(chunks)

    if not all_chunks:
        print("No readable text chunks generated from guidelines. Ingestion aborted.")
        return

    print(f"Embedding {len(all_chunks)} chunks via OpenAI...")
    embeddings = ResilientEmbeddings(openai_api_key=api_key)
    faiss_db = FAISS.from_documents(all_chunks, embeddings)

    print(f"Saving persistent FAISS index to {faiss_out}...")
    faiss_db.save_local(str(faiss_out))

    print(f"Saving BM25 documents corpus to {bm25_out}...")
    with open(bm25_out, "wb") as f:
        pickle.dump(all_chunks, f)

    print("Policy document ingestion and persistent indexing successfully completed!")


if __name__ == "__main__":
    ingest_all_policies()
