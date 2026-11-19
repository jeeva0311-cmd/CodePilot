"""
RAG vector store — ChromaDB with local ONNX all-MiniLM-L6-v2 embeddings.

Collections:
  - workspace_{slug}  : chunked workspace file contents, indexed per project
  - conversations      : past conversation snippets for project memory

Retrieval is used by the agent loop to inject relevant context before the
LLM step, without replacing any existing tool calls.
"""
import hashlib
import logging
import os
import re
import threading
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings

logger = logging.getLogger("codepilot.rag")

# File extensions worth indexing
_INDEXABLE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
    ".md", ".txt", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".sh", ".bat", ".sql", ".graphql", ".go", ".rs", ".java",
    ".cs", ".rb", ".php", ".swift", ".kt", ".cpp", ".c", ".h",
}

_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".tox", "htmlcov", ".eggs", ".chroma",
}


def _slug(path: str) -> str:
    """Safe collection-name slug from a path."""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", path)
    return f"ws_{safe[-40:]}" if len(safe) > 40 else f"ws_{safe}" or "ws_default"


def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


class RAGStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._client: Optional[chromadb.PersistentClient] = None
        self._ef = None

    def _init(self):
        if self._client is not None:
            return
        db_dir = str(Path(settings.DATABASE_PATH).parent / "chroma")
        os.makedirs(db_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=db_dir)
        self._ef = embedding_functions.DefaultEmbeddingFunction()
        logger.info(f"ChromaDB initialised at {db_dir}")

    def _collection(self, name: str):
        self._init()
        return self._client.get_or_create_collection(
            name=name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Workspace indexing ────────────────────────────────────────────────────
    def index_workspace(self, workspace_path: str) -> dict:
        """
        Walk workspace_path, chunk all indexable files, upsert into ChromaDB.
        Returns stats dict.
        """
        if not settings.RAG_ENABLED:
            return {"indexed": 0, "skipped": 0, "error": "RAG disabled"}

        root = Path(workspace_path)
        if not root.exists():
            return {"error": f"Path not found: {workspace_path}"}

        col = self._collection(_slug(workspace_path))
        indexed = skipped = errors = 0
        chunk_size = settings.RAG_CHUNK_SIZE
        overlap = settings.RAG_CHUNK_OVERLAP

        documents, metadatas, ids = [], [], []

        for fpath in _iter_files(root):
            try:
                rel = str(fpath.relative_to(root)).replace("\\", "/")
                content = fpath.read_text(encoding="utf-8", errors="replace")
                if not content.strip():
                    skipped += 1
                    continue

                chunks = _chunk_text(content, chunk_size, overlap)
                for i, chunk in enumerate(chunks):
                    chunk_id = hashlib.md5(f"{rel}:{i}:{chunk[:40]}".encode()).hexdigest()
                    documents.append(chunk)
                    metadatas.append({
                        "file": rel,
                        "chunk": i,
                        "workspace": workspace_path,
                        "ext": fpath.suffix,
                    })
                    ids.append(chunk_id)

                    # Batch upsert every 100 chunks to keep memory low
                    if len(documents) >= 100:
                        col.upsert(documents=documents, metadatas=metadatas, ids=ids)
                        indexed += len(documents)
                        documents, metadatas, ids = [], [], []

            except Exception as exc:
                logger.debug(f"Skipping {fpath}: {exc}")
                errors += 1

        # Flush remaining
        if documents:
            col.upsert(documents=documents, metadatas=metadatas, ids=ids)
            indexed += len(documents)

        logger.info(f"RAG index: {indexed} chunks from {workspace_path}")
        return {"indexed": indexed, "skipped": skipped, "errors": errors, "workspace": workspace_path}

    # ── Semantic retrieval ────────────────────────────────────────────────────
    def query(self, workspace_path: str, query_text: str, top_k: int = None) -> list[dict]:
        """
        Retrieve top_k most semantically relevant chunks from the workspace index.
        Returns list of {text, file, score, chunk_index}.
        """
        if not settings.RAG_ENABLED:
            return []
        if not query_text.strip():
            return []

        top_k = top_k or settings.RAG_TOP_K
        col = self._collection(_slug(workspace_path))

        try:
            count = col.count()
        except Exception:
            return []

        if count == 0:
            return []

        try:
            results = col.query(
                query_texts=[query_text],
                n_results=min(top_k, count),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.error(f"RAG query failed: {exc}")
            return []

        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            output.append({
                "text": doc,
                "file": meta.get("file", "?"),
                "score": round(1 - dist, 4),  # cosine similarity
                "chunk_index": meta.get("chunk", 0),
                "workspace": meta.get("workspace", ""),
            })

        return output

    # ── Conversation memory ───────────────────────────────────────────────────
    def index_message(self, conv_id: str, role: str, content: str):
        """Store a conversation message for future semantic search."""
        if not settings.RAG_ENABLED or not content.strip():
            return
        col = self._collection("conversation_memory")
        msg_id = hashlib.md5(f"{conv_id}:{role}:{content[:60]}".encode()).hexdigest()
        try:
            col.upsert(
                documents=[content[:800]],
                metadatas=[{"conv_id": conv_id, "role": role}],
                ids=[msg_id],
            )
        except Exception as exc:
            logger.debug(f"Failed to index message: {exc}")

    def get_collection_stats(self, workspace_path: str) -> dict:
        col = self._collection(_slug(workspace_path))
        return {
            "workspace": workspace_path,
            "chunk_count": col.count(),
            "collection": _slug(workspace_path),
        }

    def clear_workspace_index(self, workspace_path: str) -> dict:
        self._init()
        name = _slug(workspace_path)
        try:
            self._client.delete_collection(name)
            return {"cleared": True, "collection": name}
        except Exception as exc:
            return {"error": str(exc)}


def _iter_files(directory: Path):
    try:
        for entry in sorted(directory.iterdir(), key=lambda e: e.name):
            if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                continue
            if entry.is_dir():
                yield from _iter_files(entry)
            elif entry.is_file() and entry.suffix.lower() in _INDEXABLE_EXTS:
                if entry.stat().st_size < 500_000:  # skip files > 500 KB
                    yield entry
    except PermissionError:
        pass


# Singleton
rag_store = RAGStore()
