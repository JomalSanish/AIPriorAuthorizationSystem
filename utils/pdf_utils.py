from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader


from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extract text content from a PDF file."""
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_file}")

    reader = PdfReader(str(pdf_file))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages)


def chunk_pdf(pdf_path: str | Path, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[Document]:
    """Extract and split text from a PDF into LangChain Document chunks."""
    pdf_file = Path(pdf_path)
    reader = PdfReader(str(pdf_file))
    documents: list[Document] = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            # Keep track of page source and index in metadata
            documents.append(Document(
                page_content=text,
                metadata={"source": pdf_file.name, "page": i + 1}
            ))
            
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len
    )
    return text_splitter.split_documents(documents)


def build_excerpt(text: str, keyword: str, max_chars: int = 220) -> str:
    """Create a compact excerpt around a keyword match from text."""
    normalized = text.lower()
    keyword_lower = keyword.lower()
    index = normalized.find(keyword_lower)
    if index == -1:
        return text[:max_chars]

    start = max(0, index - 80)
    end = min(len(text), index + max_chars)
    return text[start:end].strip()

