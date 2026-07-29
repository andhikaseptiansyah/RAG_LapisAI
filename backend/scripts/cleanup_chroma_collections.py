from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import chromadb  # noqa: E402

from uploads.config import CHROMA_PATH, COLLECTION_NAME  # noqa: E402


def main() -> None:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collections = client.list_collections()
    removed: list[str] = []

    for collection in collections:
        name = collection.name if hasattr(collection, "name") else str(collection)
        if name == COLLECTION_NAME:
            continue
        client.delete_collection(name=name)
        removed.append(name)

    print(f"Active collection: {COLLECTION_NAME}")
    if removed:
        print("Removed inactive collections: " + ", ".join(removed))
    else:
        print("No inactive collections found.")


if __name__ == "__main__":
    main()
