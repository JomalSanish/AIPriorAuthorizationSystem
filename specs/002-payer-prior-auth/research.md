# Research and Technology Choices: Prior Authorization Evidence Assistant

This document outlines the evaluation of options and final decisions for the RAG and LLM components of the project.

## 1. LLM Service Integration

### Decision
Use `langchain-openai` to call OpenAI's `gpt-4o-mini` (or standard `gpt-4o`) model.

### Rationale
- High performance on structure extraction and checklist compliance tasks.
- LangChain has native, robust wrappers (`ChatOpenAI`) supporting prompt mapping and structured tool calling.
- Cost-effective and fast response times suitable for interactive dashboard applications.

### Alternatives Considered
- **Gemini API**: Highly capable, but OpenAI was explicitly preferred by the user.
- **Local LLM (e.g., Llama-3 via Ollama)**: Avoided due to setup complexity and high resource consumption on developer laptops.

---

## 2. Vector Store and RAG Architecture

### Decision
Use **FAISS** (via `faiss-cpu` and `langchain-community`) with `OpenAIEmbeddings` for the vector database.
A pure-Python/numpy cosine similarity vector index will serve as an automatic fallback if binary dependencies fail to install on Windows.

### Rationale
- FAISS is a lightweight, high-performance in-memory vector index that requires no external database servers or Docker containers.
- Perfect for prototype/local scope as outlined in Principle V.
- Handles chunk searches and ranking cleanly with LangChain integration.

### Alternatives Considered
- **Pinecone / Weaviate**: Rejected because they require cloud api keys, sign-ups, and network roundtrips, violating the offline/local-first prototype principle.
- **Chroma**: A good alternative, but sqlite/binary dependencies on Windows are prone to installation errors in some virtual environments.

---

## 3. PDF Parsing and Text Chunking

### Decision
Use `pypdf` for page extraction and LangChain's `RecursiveCharacterTextSplitter` with `chunk_size=1000` and `chunk_overlap=200` characters.

### Rationale
- `pypdf` is a pure-Python package without external system dependencies (such as Java or C++ binaries), ensuring a seamless installation.
- Overlapping chunks ensure that clinical context spanning across pages or sections is not lost.

### Alternatives Considered
- **pdfplumber**: Excellent for tables, but slower and heavier than `pypdf`.
- **PyMuPDF**: Fast, but requires building C++ binaries which can fail on certain configurations.

---

## 4. UI/UX Design System

### Decision
Develop a sleek, modern Streamlit UI with unified state management. Tabs will represent role workflows, with custom styling injected for glassmorphism, glowing queue badges, and a readable font (`Plus Jakarta Sans`).

### Rationale
- Streamlit's native layout widgets (`st.tabs`, `st.columns`, `st.expander`) map perfectly to role-based queues.
- CSS overrides will provide a premium aesthetic without adding complex JavaScript framework dependencies.
