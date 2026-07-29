from ingestion.parser import parse_file
from ingestion.chunker import chunk_pages
from ingestion.indexer import delete_document_chunks, index_chunks


def ingest(filepath: str) -> dict:
    pages = parse_file(filepath)
    print(f"Parsed {len(pages)} pages from {filepath}")

    chunks = chunk_pages(pages)
    print(f"Created {len(chunks)} chunks")

    if pages:
        delete_document_chunks(pages[0]["filename"])

    index_result = index_chunks(chunks)
    print("Ingestion complete.")

    return {
        "status": index_result["status"],
        "pages": len(pages),
        "chunks": index_result["chunks"],
        "collection": index_result["collection"],
        "embedding_model": index_result["embedding_model"],
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m uploads.ingest <filepath>")
        sys.exit(1)

    result = ingest(sys.argv[1])
    print(result)
