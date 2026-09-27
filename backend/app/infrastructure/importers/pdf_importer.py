import io
from typing import Any

from pypdf import PdfReader

from backend.app.infrastructure.importers.text_importer import parse_markdown_text


def parse_pdf_questions(content: bytes) -> list[dict[str, Any]]:
    result = extract_pdf_candidates(content)
    if result["confidence"] == "UNCERTAIN" and not result["questions"]:
        raise ValueError("PDF 文本存在，但未识别出题号、选项和答案结构")
    return result["questions"]


def extract_pdf_candidates(content: bytes) -> dict[str, Any]:
    try:
        stream = io.BytesIO(content) if isinstance(content, (bytes, bytearray)) else content
        reader = PdfReader(stream)
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:
        raise ValueError("PDF 无法读取或已损坏") from exc
    if not text:
        raise ValueError("PDF 未提取到文本，纯图片 PDF 不支持自动 OCR")

    # 1. Try standard parser first
    raw_questions = parse_markdown_text(text)
    if raw_questions:
        candidates = []
        has_uncertain = False
        for idx, q in enumerate(raw_questions):
            item = dict(q)
            item["candidate_id"] = idx + 1
            is_unc = False
            reasons = []
            if not item.get("answer"):
                is_unc = True
                reasons.append("缺少标准答案")
            if item.get("type") in {"SINGLE", "MULTI"} and len(item.get("options", [])) < 2:
                is_unc = True
                reasons.append("选择题选项不足 2 项")
            item["is_uncertain"] = is_unc
            item["uncertain_reason"] = "；".join(reasons) if reasons else ""
            if is_unc:
                has_uncertain = True
            candidates.append(item)
        return {
            "confidence": "UNCERTAIN" if has_uncertain else "HIGH",
            "text_snippet": text[:500],
            "questions": candidates,
        }

    # 2. Lenient chunking fallback for ambiguous layouts (EE-021)
    # Split paragraphs by double newline or numbered items
    import re
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    candidates = []
    cand_id = 1

    for para in paragraphs:
        lines = [line.strip() for line in para.split("\n") if line.strip()]
        if not lines:
            continue
        stem = lines[0]
        # Remove leading numbers like "1.", "1、"
        stem = re.sub(r"^(\d+[\.、\s]+|[一二三四五六七八九十]+[\.、\s]+)", "", stem).strip()
        options = []
        answer = ""
        explanation = ""

        for line in lines[1:]:
            opt_match = re.match(r"^([A-Ha-h])[\.、\s]+(.*)$", line)
            ans_match = re.search(r"(?:答案|参考答案|Answer)[:：\s]*([A-Ha-hTF正确错误]+)", line, re.IGNORECASE)
            exp_match = re.search(r"(?:解析|说明|Explanation)[:：\s]*(.*)$", line, re.IGNORECASE)

            if ans_match:
                answer = ans_match.group(1).strip().upper()
            elif exp_match:
                explanation = exp_match.group(1).strip()
            elif opt_match:
                options.append({"key": opt_match.group(1).upper(), "content": opt_match.group(2).strip()})
        if not options and not answer:
            continue

        q_type = "SINGLE"
        if len(answer) > 1 and all(c in "ABCDEFGH" for c in answer):
            q_type = "MULTI"
        elif answer in {"T", "F", "正确", "错误", "TRUE", "FALSE"}:
            q_type = "JUDGE"

        candidates.append({
            "candidate_id": cand_id,
            "type": q_type,
            "stem": stem or "未命名题目",
            "options": options,
            "answer": answer,
            "explanation": explanation,
            "difficulty": 3,
            "tags": [],
            "is_uncertain": True,
            "uncertain_reason": "未能完全自动匹配标准格式，已提取候选草稿供人工校正",
        })
        cand_id += 1

    return {
        "confidence": "UNCERTAIN",
        "text_snippet": text[:500],
        "questions": candidates,
    }
