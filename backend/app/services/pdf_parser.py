"""PDF parsing utilities for multi-page resume text extraction and cleanup."""

from __future__ import annotations

import io
import re

from pypdf import PdfReader

from app.schemas import ParseResult
from app.utils.text import normalize_text, split_sections


class PDFParseError(ValueError):
    """Raised when PDF cannot be parsed into text."""


def parse_pdf_bytes(pdf_bytes: bytes) -> ParseResult:
    """Parse PDF bytes into raw/cleaned text and detected sections."""

    if not pdf_bytes:
        raise PDFParseError("Empty file content")

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        raise PDFParseError("Invalid PDF file") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise PDFParseError("Encrypted PDF is not supported") from exc

    page_lines: list[list[str]] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        lines = _to_lines(text)
        if lines:
            page_lines.append(lines)

    if not page_lines:
        raise PDFParseError(
            "No text extracted from PDF. If this is a scanned file, OCR is required."
        )

    page_lines = _strip_repeated_headers_and_footers(page_lines)
    page_texts = ["\n".join(lines) for lines in page_lines if lines]

    raw_text = "\n\n".join(page_texts).strip()
    if not raw_text:
        raise PDFParseError("No valid text remains after cleaning PDF content")

    cleaned_text = normalize_text(raw_text)
    sections = split_sections(cleaned_text)

    return ParseResult(
        page_count=max(len(reader.pages), 1),
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        sections=sections,
    )


def _to_lines(text: str) -> list[str]:
    """Normalize one page text into non-empty compact lines."""

    text = text.replace("\r", "\n")
    lines: list[str] = []
    for line in text.split("\n"):
        normalized = re.sub(r"[ \t]+", " ", line).strip()
        if normalized:
            lines.append(normalized)
    return lines


def _strip_repeated_headers_and_footers(page_lines: list[list[str]]) -> list[list[str]]:
    """Remove repeated first/last lines across pages as header/footer noise."""

    if len(page_lines) < 2:
        return page_lines

    top_counts: dict[str, int] = {}
    bottom_counts: dict[str, int] = {}

    for lines in page_lines:
        if not lines:
            continue
        top = lines[0]
        bottom = lines[-1]

        if len(top) <= 80:
            top_counts[top] = top_counts.get(top, 0) + 1
        if len(bottom) <= 80:
            bottom_counts[bottom] = bottom_counts.get(bottom, 0) + 1

    repeated_tops = {line for line, count in top_counts.items() if count >= 2}
    repeated_bottoms = {line for line, count in bottom_counts.items() if count >= 2}

    stripped_pages: list[list[str]] = []
    for lines in page_lines:
        mutable = list(lines)
        if mutable and mutable[0] in repeated_tops:
            mutable = mutable[1:]
        if mutable and mutable[-1] in repeated_bottoms:
            mutable = mutable[:-1]
        stripped_pages.append(mutable)

    return stripped_pages
