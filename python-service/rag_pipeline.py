from __future__ import annotations

import hashlib
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import fitz  # PyMuPDF
import numpy as np
from docx import Document as DocxDocument
from rank_bm25 import BM25Okapi

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - fallback saat dependency belum siap
    SentenceTransformer = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import the same settings used by the main FastAPI backend and evaluation suite.
from uploads.config import (  # noqa: E402
    CHROMA_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    MIN_RESULT_SCORE,
)

DEFAULT_COLLECTION_NAME = COLLECTION_NAME
DEFAULT_CHROMA_DIR = CHROMA_PATH
DEFAULT_EMBEDDING_MODEL = EMBEDDING_MODEL
DEFAULT_MIN_SCORE = MIN_RESULT_SCORE
DEFAULT_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE_WORDS", "700"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP_WORDS", "100"))
FALLBACK_DIMENSION = int(os.getenv("FALLBACK_EMBEDDING_DIMENSION", "384"))


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class TextChunk:
    chunk_index: int
    content: str
    page_number: int
    token_count: int


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def tokenize(text: str) -> List[str]:
    return re.findall(r"[\w]+", (text or "").lower())


def hash_embedding(text: str, dimension: int = FALLBACK_DIMENSION) -> List[float]:
    vector = np.zeros(dimension, dtype=np.float32)
    tokens = tokenize(text)

    if not tokens:
        return vector.tolist()

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm

    return vector.astype(float).tolist()


class EmbeddingProvider:
    def __init__(self) -> None:
        self.model_name = DEFAULT_EMBEDDING_MODEL
        self._model: Any = None
        self.provider = "hash-fallback"
        self.dimension = FALLBACK_DIMENSION

        if SentenceTransformer is not None:
            try:
                self._model = SentenceTransformer(self.model_name)
                self.provider = "sentence-transformers"
                self.dimension = int(self._model.get_sentence_embedding_dimension())
            except Exception as exc:
                print(
                    "[PYTHON_RAG] sentence-transformers tidak bisa diload, "
                    f"pakai hash fallback. Detail: {exc}"
                )

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if self._model is not None:
            vectors = self._model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return vectors.astype(float).tolist()

        return [hash_embedding(text, self.dimension) for text in texts]


def extract_pdf(path: Path) -> List[PageText]:
    pages: List[PageText] = []

    with fitz.open(path) as pdf:
        for index, page in enumerate(pdf, start=1):
            text = normalize_whitespace(page.get_text("text"))
            if text:
                pages.append(PageText(page_number=index, text=text))

    return pages


def extract_docx(path: Path) -> List[PageText]:
    document = DocxDocument(path)
    paragraphs = [normalize_whitespace(p.text) for p in document.paragraphs]
    text = "\n".join([p for p in paragraphs if p])
    return [PageText(page_number=1, text=normalize_whitespace(text))] if text else []


def extract_txt(path: Path) -> List[PageText]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = normalize_whitespace(raw)
    return [PageText(page_number=1, text=text)] if text else []


def extract_pages(file_path: str) -> List[PageText]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    extension = path.suffix.lower()

    if extension == ".pdf":
        return extract_pdf(path)

    if extension == ".docx":
        return extract_docx(path)

    if extension == ".txt":
        return extract_txt(path)

    raise ValueError("Format file tidak didukung. Gunakan PDF, DOCX, atau TXT.")


def chunk_pages(
    pages: List[PageText],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[TextChunk]:
    chunks: List[TextChunk] = []
    chunk_index = 0
    safe_chunk_size = max(chunk_size, 100)
    safe_overlap = max(min(overlap, safe_chunk_size - 1), 0)
    step = safe_chunk_size - safe_overlap

    for page in pages:
        words = page.text.split()
        if not words:
            continue

        if len(words) <= safe_chunk_size:
            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    content=" ".join(words),
                    page_number=page.page_number,
                    token_count=len(words),
                )
            )
            chunk_index += 1
            continue

        for start in range(0, len(words), step):
            part = words[start : start + safe_chunk_size]
            if not part:
                continue

            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    content=" ".join(part),
                    page_number=page.page_number,
                    token_count=len(part),
                )
            )
            chunk_index += 1

            if start + safe_chunk_size >= len(words):
                break

    return chunks


class LapisRagStore:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path=DEFAULT_CHROMA_DIR)
        self.collection = self.client.get_or_create_collection(
            name=DEFAULT_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self.embedding_provider = EmbeddingProvider()

    def index_document(
        self,
        document_id: str,
        file_path: str,
        filename: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pages = extract_pages(file_path)
        chunks = chunk_pages(pages)

        if not chunks:
            raise ValueError("Dokumen tidak punya teks yang bisa di-index.")

        try:
            self.collection.delete(where={"document_id": document_id})
        except Exception:
            # Chroma bisa throw saat dokumen belum pernah ada. Aman diabaikan.
            pass

        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedding_provider.embed(texts)
        ids = [f"{document_id}:{chunk.chunk_index}" for chunk in chunks]
        metadatas: List[Dict[str, Any]] = []

        for chunk in chunks:
            metadata = {
                "document_id": document_id,
                "filename": filename,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
            }
            if extra_metadata:
                metadata.update(extra_metadata)
            metadatas.append(metadata)

        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return {
            "document_id": document_id,
            "filename": filename,
            "chunks": len(chunks),
            "embedding_provider": self.embedding_provider.provider,
            "embedding_model": self.embedding_provider.model_name,
        }

    def _get_all_records(self) -> Dict[str, Any]:
        return self.collection.get(include=["documents", "metadatas"])

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> List[Dict[str, Any]]:
        clean_query = normalize_whitespace(query)
        if not clean_query:
            return []

        all_records = self._get_all_records()
        all_docs = all_records.get("documents") or []
        all_ids = all_records.get("ids") or []
        all_metas = all_records.get("metadatas") or []

        if not all_docs:
            return []

        query_embedding = self.embedding_provider.embed([clean_query])[0]
        semantic_result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(max(top_k * 5, top_k), len(all_docs)),
            include=["documents", "metadatas", "distances"],
        )

        semantic_scores: Dict[str, float] = {}
        semantic_docs: Dict[str, str] = {}
        semantic_metas: Dict[str, Dict[str, Any]] = {}

        for idx, chunk_id in enumerate(semantic_result.get("ids", [[]])[0]):
            distance = float((semantic_result.get("distances", [[]])[0] or [0])[idx])
            score = max(0.0, 1.0 - distance)
            semantic_scores[chunk_id] = score
            semantic_docs[chunk_id] = semantic_result.get("documents", [[]])[0][idx]
            semantic_metas[chunk_id] = semantic_result.get("metadatas", [[]])[0][idx]

        tokenized_corpus = [tokenize(doc) for doc in all_docs]
        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores_raw = bm25.get_scores(tokenize(clean_query))
        max_bm25 = float(np.max(bm25_scores_raw)) if len(bm25_scores_raw) else 0.0
        bm25_scores = {
            all_ids[index]: (float(score) / max_bm25 if max_bm25 > 0 else 0.0)
            for index, score in enumerate(bm25_scores_raw)
        }

        # Kandidat gabungan: semantic candidates + BM25 candidates terbaik.
        top_bm25_ids = sorted(
            bm25_scores,
            key=lambda item_id: bm25_scores[item_id],
            reverse=True,
        )[: max(top_k * 5, top_k)]
        candidate_ids = set(semantic_scores.keys()) | set(top_bm25_ids)

        by_id_doc = {item_id: doc for item_id, doc in zip(all_ids, all_docs)}
        by_id_meta = {item_id: meta for item_id, meta in zip(all_ids, all_metas)}

        ranked: List[Dict[str, Any]] = []
        for item_id in candidate_ids:
            semantic_score = semantic_scores.get(item_id, 0.0)
            keyword_score = bm25_scores.get(item_id, 0.0)
            final_score = (0.75 * semantic_score) + (0.25 * keyword_score)

            if final_score < min_score:
                continue

            metadata = semantic_metas.get(item_id) or by_id_meta.get(item_id) or {}
            content = semantic_docs.get(item_id) or by_id_doc.get(item_id) or ""

            ranked.append(
                {
                    "chunkId": item_id,
                    "documentId": metadata.get("document_id", ""),
                    "documentName": metadata.get("filename", "-"),
                    "page": str(metadata.get("page_number", "-")),
                    "content": content,
                    "score": round(final_score, 6),
                    "semanticScore": round(semantic_score, 6),
                    "keywordScore": round(keyword_score, 6),
                    "metadata": metadata,
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:top_k]


store = LapisRagStore()
