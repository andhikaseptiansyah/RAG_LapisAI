from functools import lru_cache
from typing import TYPE_CHECKING, Any


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
    import chromadb

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
    import chromadb

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


def delete_document_chunks(
    filename: str,
    *,
    case_insensitive: bool = False,
) -> int:
    """Delete vector chunks for a filename.

    Normal ingestion uses Chroma's indexed equality filter. Administrative
    deletion can opt into a metadata scan to also clean up legacy case variants.
    """
    collection = get_collection()
    normalized_filename = str(filename or "").strip().casefold()
    if not normalized_filename:
        return 0

    if not case_insensitive:
        try:
            before_count = int(collection.count())
        except Exception:
            before_count = -1

        collection.delete(where={"filename": filename})

        if before_count < 0:
            return 0
        try:
            return max(before_count - int(collection.count()), 0)
        except Exception:
            return 0

    try:
        stored = collection.get(include=["metadatas"])
        stored_ids = stored.get("ids") or []
        stored_metadatas = stored.get("metadatas") or []
        matching_ids = [
            str(chunk_id)
            for chunk_id, metadata in zip(stored_ids, stored_metadatas)
            if isinstance(metadata, dict)
            and str(metadata.get("filename") or "").strip().casefold()
            == normalized_filename
        ]
        if matching_ids:
            collection.delete(ids=matching_ids)
        return len(matching_ids)
    except Exception:
        # Compatibility fallback for older Chroma clients that cannot list
        # metadata with the current include contract.
        collection.delete(where={"filename": filename})
        return 0


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
