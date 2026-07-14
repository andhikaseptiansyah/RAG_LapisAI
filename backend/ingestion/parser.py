from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pymupdf  # PyMuPDF
from docx import Document
from docx.oxml.ns import qn


_WHITESPACE_RE = re.compile(r"\s+")
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_NAMED_HEADING_RE = re.compile(
    r"^(?:chapter|section|part|bab|bagian)\s+(?:\d+|[ivxlcdm]+)(?:\b|\s*[:.-])",
    re.IGNORECASE,
)
_UNDERLINE_HEADING_RE = re.compile(r"^[=\-]{3,}$")


def _clean_text(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _normalize_for_match(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _heading_text(text: str, style_name: str = "") -> str | None:
    cleaned = _clean_text(text)
    if not cleaned:
        return None

    markdown_match = _MARKDOWN_HEADING_RE.match(cleaned)
    if markdown_match:
        return _clean_text(markdown_match.group(1))

    if style_name.casefold().startswith("heading"):
        return cleaned

    if _NAMED_HEADING_RE.match(cleaned):
        return cleaned

    if (
        len(cleaned) <= 100
        and cleaned.upper() == cleaned
        and any(character.isalpha() for character in cleaned)
    ):
        return cleaned

    return None


def _pdf_page_paragraphs(page: pymupdf.Page) -> list[dict[str, Any]]:
    paragraphs: list[dict[str, Any]] = []
    current_section: str | None = None

    blocks = page.get_text("blocks", sort=True)
    for block in blocks:
        if len(block) >= 7 and block[6] != 0:
            continue

        block_text = str(block[4] if len(block) > 4 else "")
        pieces = re.split(r"\n\s*\n+", block_text)

        for piece in pieces:
            text = _clean_text(piece)
            if not text:
                continue

            detected_heading = _heading_text(text)
            if detected_heading:
                current_section = detected_heading

            record: dict[str, Any] = {
                "number": len(paragraphs) + 1,
                "text": text,
            }
            if current_section:
                record["section"] = current_section
                record["chapter"] = current_section
            paragraphs.append(record)

    if paragraphs:
        return paragraphs

    fallback_text = str(page.get_text("text", sort=True) or "")
    for piece in re.split(r"\n\s*\n+", fallback_text):
        text = _clean_text(piece)
        if text:
            paragraphs.append({"number": len(paragraphs) + 1, "text": text})

    return paragraphs


def parse_pdf(filepath: str, filename: str) -> list[dict]:
    pages: list[dict] = []
    doc = pymupdf.open(filepath)

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            paragraphs = _pdf_page_paragraphs(page)
            if not paragraphs:
                continue

            page_data: dict[str, Any] = {
                "text": "\n\n".join(item["text"] for item in paragraphs),
                "page": page_num + 1,
                "page_is_reliable": True,
                "filename": filename,
                "document_type": "pdf",
                "location_type": "page_paragraphs",
                "paragraphs": paragraphs,
                "paragraph_start": int(paragraphs[0]["number"]),
                "paragraph_end": int(paragraphs[-1]["number"]),
            }

            section = next(
                (
                    str(item.get("section"))
                    for item in reversed(paragraphs)
                    if item.get("section")
                ),
                None,
            )
            if section:
                page_data["section"] = section
                page_data["chapter"] = section

            pages.append(page_data)
    finally:
        doc.close()

    return pages


def _find_libreoffice() -> str | None:
    configured = os.getenv("LIBREOFFICE_PATH", "").strip()
    if configured and Path(configured).exists():
        return configured

    for executable in ("libreoffice", "soffice", "soffice.exe"):
        resolved = shutil.which(executable)
        if resolved:
            return resolved

    return None


def _render_docx_pages(filepath: str) -> list[str]:
    """Render DOCX to PDF so page citations come from an actual document layout.

    DOCX has no intrinsic page model. A page number is only reliable after the
    document is rendered. LibreOffice is used when available; callers fall back
    to paragraph and chapter citations when rendering is unavailable.
    """
    libreoffice = _find_libreoffice()
    if not libreoffice:
        return []

    with tempfile.TemporaryDirectory(prefix="lapisai_docx_") as temp_dir:
        env = os.environ.copy()
        env.setdefault("HOME", temp_dir)
        command = [
            libreoffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            temp_dir,
            str(Path(filepath).resolve()),
        ]

        run_kwargs: dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "timeout": 60,
            "check": False,
            "env": env,
        }
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            completed = subprocess.run(command, **run_kwargs)
        except (OSError, subprocess.SubprocessError):
            return []

        if completed.returncode != 0:
            return []

        expected_pdf = Path(temp_dir) / f"{Path(filepath).stem}.pdf"
        if not expected_pdf.exists():
            candidates = list(Path(temp_dir).glob("*.pdf"))
            if not candidates:
                return []
            expected_pdf = candidates[0]

        page_texts: list[str] = []
        pdf = pymupdf.open(expected_pdf)
        try:
            for page in pdf:
                page_texts.append(_clean_text(page.get_text("text", sort=True)))
        finally:
            pdf.close()

        return page_texts


def _match_paragraph_to_pages(
    paragraph_text: str,
    page_texts: list[str],
    start_index: int,
) -> tuple[int | None, int | None, bool]:
    normalized = _normalize_for_match(paragraph_text)
    if not normalized or not page_texts:
        return None, None, False

    normalized_pages = [_normalize_for_match(page) for page in page_texts]
    search_start = min(max(start_index, 0), len(normalized_pages) - 1)

    first_words = normalized.split()[:12]
    last_words = normalized.split()[-12:]
    first_snippet = " ".join(first_words)
    last_snippet = " ".join(last_words)

    start_page: int | None = None
    end_page: int | None = None

    for page_index in range(search_start, len(normalized_pages)):
        page_text = normalized_pages[page_index]
        if normalized in page_text or (first_snippet and first_snippet in page_text):
            start_page = page_index
            break

    if start_page is not None:
        for page_index in range(start_page, len(normalized_pages)):
            page_text = normalized_pages[page_index]
            if normalized in page_text or (last_snippet and last_snippet in page_text):
                end_page = page_index
                break
        if end_page is None:
            end_page = start_page
        return start_page + 1, end_page + 1, True

    paragraph_tokens = set(normalized.split())
    best_page: int | None = None
    best_score = 0.0

    for page_index in range(search_start, len(normalized_pages)):
        page_text = normalized_pages[page_index]
        page_tokens = set(page_text.split())
        coverage = len(paragraph_tokens.intersection(page_tokens)) / max(
            len(paragraph_tokens), 1
        )
        prefix_ratio = SequenceMatcher(
            None,
            normalized[:180],
            page_text[: max(180, min(len(page_text), 900))],
        ).ratio()
        score = (coverage * 0.85) + (prefix_ratio * 0.15)
        if score > best_score:
            best_score = score
            best_page = page_index

    if best_page is not None and best_score >= 0.55:
        return best_page + 1, best_page + 1, True

    return None, None, False


def _count_page_breaks(paragraph: Any) -> int:
    page_breaks = len(paragraph._p.xpath(".//w:lastRenderedPageBreak"))
    for break_element in paragraph._p.xpath(".//w:br"):
        if break_element.get(qn("w:type")) == "page":
            page_breaks += 1
    return page_breaks


def _collect_docx_paragraphs(doc: Document) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current_section: str | None = None
    current_page_from_breaks = 1

    for paragraph in doc.paragraphs:
        text = _clean_text(paragraph.text)
        style_name = str(getattr(paragraph.style, "name", "") or "")
        page_breaks = _count_page_breaks(paragraph)

        if text:
            detected_heading = _heading_text(text, style_name)
            if detected_heading:
                current_section = detected_heading

            record: dict[str, Any] = {
                "number": len(records) + 1,
                "text": text,
                "break_page_start": current_page_from_breaks,
                "break_page_end": current_page_from_breaks + page_breaks,
                "break_page_reliable": page_breaks > 0,
            }
            if current_section:
                record["section"] = current_section
                record["chapter"] = current_section
            records.append(record)

        current_page_from_breaks += page_breaks

    return records


def parse_docx(filepath: str, filename: str) -> list[dict]:
    doc = Document(filepath)
    paragraphs = _collect_docx_paragraphs(doc)
    if not paragraphs:
        return []

    rendered_pages = _render_docx_pages(filepath)
    page_cursor = 0

    for paragraph in paragraphs:
        page_start, page_end, reliable = _match_paragraph_to_pages(
            paragraph["text"], rendered_pages, page_cursor
        )
        if reliable and page_start is not None:
            paragraph["page"] = page_start
            paragraph["page_end"] = page_end or page_start
            paragraph["page_is_reliable"] = True
            page_cursor = max(page_start - 1, page_cursor)
        elif paragraph.get("break_page_reliable"):
            paragraph["page"] = int(paragraph["break_page_start"])
            paragraph["page_end"] = int(paragraph["break_page_end"])
            paragraph["page_is_reliable"] = True
        else:
            paragraph["page"] = None
            paragraph["page_end"] = None
            paragraph["page_is_reliable"] = False

    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    current_key: tuple[Any, ...] | None = None

    for paragraph in paragraphs:
        reliable_page = (
            paragraph.get("page")
            if paragraph.get("page_is_reliable")
            else None
        )
        key = (reliable_page, bool(paragraph.get("page_is_reliable")))

        if current_group and key != current_key:
            groups.append(current_group)
            current_group = []

        current_group.append(paragraph)
        current_key = key

    if current_group:
        groups.append(current_group)

    pages: list[dict[str, Any]] = []
    for group in groups:
        page = group[0].get("page")
        page_is_reliable = bool(page is not None) and all(
            item.get("page_is_reliable") and item.get("page") == page
            for item in group
        )

        page_data: dict[str, Any] = {
            "text": "\n\n".join(item["text"] for item in group),
            "page": int(page) if page_is_reliable else None,
            "page_is_reliable": page_is_reliable,
            "filename": filename,
            "document_type": "docx",
            "location_type": (
                "page_paragraphs" if page_is_reliable else "paragraphs"
            ),
            "paragraphs": group,
            "paragraph_start": int(group[0]["number"]),
            "paragraph_end": int(group[-1]["number"]),
        }

        section = next(
            (
                str(item.get("section"))
                for item in reversed(group)
                if item.get("section")
            ),
            None,
        )
        if section:
            page_data["section"] = section
            page_data["chapter"] = section

        pages.append(page_data)

    return pages


def _append_txt_paragraph(
    paragraphs: list[dict[str, Any]],
    text: str,
    chapter: str | None,
) -> None:
    cleaned = _clean_text(text)
    if not cleaned:
        return

    record: dict[str, Any] = {
        "number": len(paragraphs) + 1,
        "text": cleaned,
    }
    if chapter:
        record["section"] = chapter
        record["chapter"] = chapter
    paragraphs.append(record)


def _parse_txt_paragraphs(lines: list[str]) -> list[dict[str, Any]]:
    paragraphs: list[dict[str, Any]] = []
    buffer: list[str] = []
    current_chapter: str | None = None

    def flush_buffer() -> None:
        nonlocal buffer
        if buffer:
            _append_txt_paragraph(
                paragraphs,
                " ".join(buffer),
                current_chapter,
            )
            buffer = []

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()

        if not stripped:
            flush_buffer()
            continue

        markdown_match = _MARKDOWN_HEADING_RE.match(stripped)
        if markdown_match:
            flush_buffer()
            current_chapter = _clean_text(markdown_match.group(1))
            _append_txt_paragraph(paragraphs, current_chapter, current_chapter)
            continue

        if _UNDERLINE_HEADING_RE.match(stripped):
            if buffer:
                inferred_chapter = _clean_text(buffer[-1])
                flush_buffer()
                if inferred_chapter:
                    current_chapter = inferred_chapter
                    paragraphs[-1]["section"] = current_chapter
                    paragraphs[-1]["chapter"] = current_chapter
            continue

        detected_heading = _heading_text(stripped)
        if detected_heading and not buffer:
            flush_buffer()
            current_chapter = detected_heading
            _append_txt_paragraph(paragraphs, detected_heading, current_chapter)
            continue

        buffer.append(stripped)

    flush_buffer()
    return paragraphs


def parse_txt(filepath: str, filename: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8-sig") as file_handle:
        lines = file_handle.readlines()

    paragraphs = _parse_txt_paragraphs(lines)
    if not paragraphs:
        return []

    page_data: dict[str, Any] = {
        "text": "\n\n".join(item["text"] for item in paragraphs),
        "page": None,
        "page_is_reliable": False,
        "filename": filename,
        "document_type": "txt",
        "location_type": "paragraphs",
        "paragraphs": paragraphs,
        "paragraph_start": int(paragraphs[0]["number"]),
        "paragraph_end": int(paragraphs[-1]["number"]),
    }

    chapter = next(
        (
            str(item.get("chapter"))
            for item in reversed(paragraphs)
            if item.get("chapter")
        ),
        None,
    )
    if chapter:
        page_data["section"] = chapter
        page_data["chapter"] = chapter

    return [page_data]


def parse_file(filepath: str) -> list[dict]:
    filename = os.path.basename(filepath)
    extension = os.path.splitext(filename)[1].lower()

    if extension == ".pdf":
        return parse_pdf(filepath, filename)
    if extension == ".docx":
        return parse_docx(filepath, filename)
    if extension == ".txt":
        return parse_txt(filepath, filename)

    raise ValueError(f"Unsupported file type: {extension}")
