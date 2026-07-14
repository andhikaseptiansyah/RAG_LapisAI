from __future__ import annotations

from typing import Any


def count_tokens(text: str) -> int:
    # Lightweight approximation: 1 word is approximately 1.3 tokens.
    return int(len(text.split()) * 1.3)


def chunk_text(text: str, chunk_size: int = 750, overlap: int = 100) -> list[str]:
    words = text.split()
    chunks: list[str] = []

    if not words:
        return chunks

    chunk_words = max(int(chunk_size / 1.3), 1)
    overlap_words = max(int(overlap / 1.3), 0)

    if overlap_words >= chunk_words:
        overlap_words = max(chunk_words - 1, 0)

    step = max(chunk_words - overlap_words, 1)
    start = 0

    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunk = " ".join(words[start:end]).strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(words):
            break

        start += step

    return chunks


def _split_paragraph_units(
    paragraphs: list[dict[str, Any]],
    max_words: int,
) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []

    for paragraph in paragraphs:
        words = str(paragraph.get("text") or "").split()
        if not words:
            continue

        for start in range(0, len(words), max_words):
            part = " ".join(words[start : start + max_words]).strip()
            if not part:
                continue
            unit = dict(paragraph)
            unit["text"] = part
            unit["word_count"] = len(part.split())
            units.append(unit)

    return units


def _chunk_paragraph_group(
    page: dict[str, Any],
    paragraphs: list[dict[str, Any]],
    chunk_size: int,
    overlap: int,
) -> list[dict[str, Any]]:
    max_words = max(int(chunk_size / 1.3), 1)
    overlap_words = max(int(overlap / 1.3), 0)
    units = _split_paragraph_units(paragraphs, max_words)
    if not units:
        return []

    chunks: list[dict[str, Any]] = []
    start = 0

    while start < len(units):
        end = start
        total_words = 0

        while end < len(units):
            unit_words = int(units[end].get("word_count") or 0)
            if end > start and total_words + unit_words > max_words:
                break
            total_words += unit_words
            end += 1

        selected = units[start:end]
        if not selected:
            break

        text = "\n\n".join(str(item["text"]) for item in selected).strip()
        paragraph_numbers = [
            int(item["number"])
            for item in selected
            if item.get("number") is not None
        ]
        paragraph_start = min(paragraph_numbers) if paragraph_numbers else None
        paragraph_end = max(paragraph_numbers) if paragraph_numbers else None

        chapter = next(
            (
                str(item.get("chapter") or item.get("section"))
                for item in selected
                if item.get("chapter") or item.get("section")
            ),
            None,
        )

        chunk_data: dict[str, Any] = {
            "text": text,
            "page": page.get("page"),
            "page_is_reliable": bool(page.get("page_is_reliable", False)),
            "filename": page["filename"],
            "document_type": page.get("document_type", ""),
            "location_type": page.get("location_type", "paragraphs"),
            "token_count": count_tokens(text),
        }
        if paragraph_start is not None:
            chunk_data["paragraph_start"] = paragraph_start
        if paragraph_end is not None:
            chunk_data["paragraph_end"] = paragraph_end
        if chapter:
            chunk_data["chapter"] = chapter
            chunk_data["section"] = chapter

        chunks.append(chunk_data)

        if end >= len(units):
            break

        next_start = end
        overlap_count = 0
        while next_start > start + 1 and overlap_count < overlap_words:
            next_start -= 1
            overlap_count += int(units[next_start].get("word_count") or 0)

        start = next_start if next_start > start else start + 1

    return chunks


def _paragraph_chunks(
    page: dict[str, Any],
    chunk_size: int = 750,
    overlap: int = 100,
) -> list[dict[str, Any]]:
    paragraphs = list(page.get("paragraphs") or [])
    if not paragraphs:
        return []

    # When reliable section metadata exists, prevent one chunk from spanning
    # two consecutive sections. TXT input intentionally has no chapter metadata.
    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    current_chapter: str | None = None

    for paragraph in paragraphs:
        paragraph_chapter = str(
            paragraph.get("chapter")
            or paragraph.get("section")
            or ""
        ).strip() or None

        if (
            current_group
            and paragraph_chapter != current_chapter
        ):
            groups.append(current_group)
            current_group = []

        current_group.append(paragraph)
        current_chapter = paragraph_chapter

    if current_group:
        groups.append(current_group)

    chunks: list[dict[str, Any]] = []
    for group in groups:
        chunks.extend(
            _chunk_paragraph_group(
                page,
                group,
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )

    return chunks

def chunk_pages(pages: list[dict]) -> list[dict]:
    chunks: list[dict] = []

    for page in pages:
        structured_chunks = _paragraph_chunks(page)

        if structured_chunks:
            page_chunks = structured_chunks
        else:
            page_chunks = []
            for text_chunk in chunk_text(str(page.get("text") or "")):
                fallback: dict[str, Any] = {
                    "text": text_chunk,
                    "page": page.get("page"),
                    "page_is_reliable": bool(page.get("page_is_reliable", False)),
                    "filename": page["filename"],
                    "document_type": page.get("document_type", ""),
                    "location_type": page.get("location_type", "page"),
                    "token_count": count_tokens(text_chunk),
                }
                for metadata_key in (
                    "chapter",
                    "section",
                    "paragraph_start",
                    "paragraph_end",
                    "line_start",
                    "line_end",
                ):
                    if page.get(metadata_key) is not None:
                        fallback[metadata_key] = page[metadata_key]
                page_chunks.append(fallback)

        for index, chunk in enumerate(page_chunks):
            location = (
                f"p{chunk.get('page')}"
                if chunk.get("page") is not None
                else f"para{chunk.get('paragraph_start', 'unknown')}"
            )
            chunk["chunk_id"] = f"{page['filename']}_{location}_c{index}"
            chunk["chunk_index"] = index
            chunks.append(chunk)

    return chunks
