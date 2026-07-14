from functools import lru_cache
from typing import TYPE_CHECKING, Any

import chromadb

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from uploads.config import CHROMA_PATH, COLLECTION_NAME, EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_embedding_model() -> "SentenceTransformer":
    """Load the embedding model lazily on the first embedding request.

    Chroma collection access and BM25 retrieval do not need PyTorch or
    Transformers, so keeping this import lazy materially reduces API startup
    time and avoids model initialization during health checks.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection():
    """Delete and recreate the active collection.

    Required after changing the embedding model so old and new vectors are never
    mixed in one collection.
    """
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    embeddings = get_embedding_model().encode(
        texts,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Embed one query with the same model used for document chunks."""
    if not str(text or "").strip():
        return []
    return embed_texts([text])[0]


def embed_chunks(chunks: list[dict]) -> list[dict]:
    texts = [chunk["text"] for chunk in chunks]
    embeddings = embed_texts(texts)

    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[i]

    return chunks


def delete_document_chunks(filename: str) -> None:
    collection = get_collection()

    try:
        collection.delete(where={"filename": filename})
    except Exception:
        # Safe to ignore when the document has never been indexed before.
        pass


def index_chunks(chunks: list[dict]) -> dict:
    if not chunks:
        return {
            "status": "indexed",
            "chunks": 0,
            "collection": COLLECTION_NAME,
            "embedding_model": EMBEDDING_MODEL,
        }

    collection = get_collection()
    chunks = embed_chunks(chunks)

    ids = [chunk["chunk_id"] for chunk in chunks]
    documents = [chunk["text"] for chunk in chunks]
    embeddings = [chunk["embedding"] for chunk in chunks]
    metadatas = []
    for chunk in chunks:
        metadata = {
            "filename": chunk["filename"],
            "chunk_index": chunk["chunk_index"],
            "token_count": chunk["token_count"],
            "location_type": chunk.get("location_type", "page"),
            "document_type": chunk.get("document_type", ""),
            "page_is_reliable": bool(chunk.get("page_is_reliable", False)),
        }

        # Chroma metadata does not accept None. TXT documents therefore do not
        # store a page field, while PDF and rendered DOCX chunks keep the real
        # page number produced by the parser.
        if chunk.get("page") is not None:
            metadata["page"] = int(chunk["page"])

        for metadata_key in (
            "chapter",
            "section",
            "paragraph_start",
            "paragraph_end",
            "line_start",
            "line_end",
        ):
            if chunk.get(metadata_key) is not None:
                metadata[metadata_key] = chunk[metadata_key]

        metadatas.append(metadata)

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"Indexed {len(chunks)} chunks into collection '{COLLECTION_NAME}'.")

    return {
        "status": "indexed",
        "chunks": len(chunks),
        "collection": COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL,
    }
