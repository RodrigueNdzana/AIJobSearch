"""
Extracts raw text from uploaded CV files so it can be embedded and searched.
Supports PDF (pypdf) and DOCX (python-docx). Add more formats here as needed.
"""

import io

from docx import Document
from pypdf import PdfReader


def extract_text(file_bytes: bytes, file_type: str) -> str:
    file_type = file_type.lower().lstrip(".")

    if file_type == "pdf":
        return _extract_pdf(file_bytes)
    if file_type in ("docx", "doc"):
        return _extract_docx(file_bytes)

    raise ValueError(f"Unsupported CV file type: {file_type}")


def _extract_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _extract_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n".join(paragraphs).strip()
