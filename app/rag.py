from pathlib import Path
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .config import CHROMA_DIR

_store = None


class OnnxEmbeddings(Embeddings):
    """all-MiniLM-L6-v2 via onnxruntime (no torch / scikit-learn)."""
    def __init__(self):
        self.fn = DefaultEmbeddingFunction()

    def embed_documents(self, texts):
        return [[float(x) for x in v] for v in self.fn(texts)]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def get_store() -> Chroma:
    global _store
    if _store is None:
        _store = Chroma("uni_docs", OnnxEmbeddings(), persist_directory=CHROMA_DIR)
    return _store


def ingest(path: str, **meta) -> int:
    p = Path(path)
    docs = PyPDFLoader(str(p)).load() if p.suffix.lower() == ".pdf" else TextLoader(str(p), encoding="utf-8").load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100).split_documents(docs)
    for c in chunks:
        c.metadata.update({"source": p.name, "document_type": meta.get("document_type", "regulation"), **meta})
    get_store().add_documents(chunks)
    return len(chunks)


@tool
def search_documents(query: str) -> str:
    """Search official college documents (regulations, handbooks, syllabus, exam rules, ERP how-to guides).
    Use for general institutional rules and procedures, NOT for personal student data."""
    hits = get_store().similarity_search(query, k=4)
    if not hits:
        return "No relevant documents found."
    body = "\n\n".join(f"[{h.metadata.get('source')} p.{h.metadata.get('page', '-')}]\n{h.page_content}" for h in hits)
    return f"<untrusted_documents>\n{body}\n</untrusted_documents>"
