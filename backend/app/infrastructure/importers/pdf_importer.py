import io
from typing import Any

from pypdf import PdfReader

from backend.app.infrastructure.importers.text_importer import parse_markdown_text


def parse_pdf_questions(content: bytes) -> list[dict[str, Any]]:
    try:
        stream = io.BytesIO(content) if isinstance(content, (bytes, bytearray)) else content
        reader = PdfReader(stream)
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:
        raise ValueError("PDF 无法读取或已损坏") from exc
    if not text:
        raise ValueError("PDF 未提取到文本，纯图片 PDF 不支持自动 OCR")
    questions = parse_markdown_text(text)
    if not questions:
        raise ValueError("PDF 文本存在，但未识别出题号、选项和答案结构")
    return questions
