"""Bank Export Service for EasyExam (易考宝).

Exports question bank collections to JSON, CSV, plain text/Markdown, and Excel (.xlsx) formats.
Output is 100% compatible with EasyExam's ingestion pipeline (importer.py).
"""
import csv
import io
import json
import re
from typing import Any, Dict, List, Tuple, Union


def export_to_json(questions: List[Dict[str, Any]]) -> str:
    """Export questions list to pretty JSON string."""
    clean_questions = []
    for q in questions:
        item = {
            "stem": q.get("stem", ""),
            "type": q.get("type", "SINGLE"),
            "options": q.get("options", []),
            "answer": q.get("answer", ""),
            "explanation": q.get("explanation", ""),
            "difficulty": q.get("difficulty", 3),
            "tags": q.get("tags", []),
        }
        clean_questions.append(item)
    return json.dumps(clean_questions, ensure_ascii=False, indent=2)


def export_to_text(questions: List[Dict[str, Any]]) -> str:
    """Export questions to human-readable Markdown/plain text format."""
    lines = []
    type_map = {
        "SINGLE": "单选题",
        "MULTI": "多选题",
        "JUDGE": "判断题",
        "ESSAY": "简答题",
    }

    for idx, q in enumerate(questions, 1):
        q_type_str = type_map.get(q.get("type", "SINGLE"), "单选题")
        lines.append(f"{idx}. 【{q_type_str}】{q.get('stem', '')}")

        opts = q.get("options") or []
        for opt in opts:
            if isinstance(opt, dict):
                k = opt.get("key", "")
                c = opt.get("content", opt.get("text", ""))
                lines.append(f"{k}. {c}")
            elif isinstance(opt, str):
                lines.append(opt)

        lines.append(f"【答案】{q.get('answer', '')}")
        if q.get("explanation"):
            lines.append(f"【解析】{q.get('explanation', '')}")
        if q.get("difficulty"):
            lines.append(f"【难度】{q.get('difficulty', 3)}")
        if q.get("tags"):
            tags = q.get("tags")
            tag_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
            lines.append(f"【标签】{tag_str}")
        lines.append("")  # Blank line separator

    return "\n".join(lines).strip() + "\n"


def export_to_csv(questions: List[Dict[str, Any]]) -> str:
    """Export questions to CSV format with UTF-8 BOM."""
    output = io.StringIO()
    # Write BOM for Excel UTF-8 compatibility
    output.write("\ufeff")

    fieldnames = [
        "题干", "题型", "选项A", "选项B", "选项C", "选项D", "选项E", "选项F",
        "正确答案", "解析", "难度", "标签"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()

    type_map = {
        "SINGLE": "单选",
        "MULTI": "多选",
        "JUDGE": "判断",
        "ESSAY": "简答",
    }

    for q in questions:
        row = {
            "题干": q.get("stem", ""),
            "题型": type_map.get(q.get("type", "SINGLE"), "单选"),
            "选项A": "",
            "选项B": "",
            "选项C": "",
            "选项D": "",
            "选项E": "",
            "选项F": "",
            "正确答案": q.get("answer", ""),
            "解析": q.get("explanation", ""),
            "难度": q.get("difficulty", 3),
            "标签": ", ".join(q.get("tags", [])) if isinstance(q.get("tags"), list) else str(q.get("tags") or ""),
        }
        opts = q.get("options") or []
        for opt in opts:
            if isinstance(opt, dict):
                k = str(opt.get("key", "")).upper()
                c = opt.get("content", opt.get("text", ""))
                col_name = f"选项{k}"
                if col_name in row:
                    row[col_name] = c

        writer.writerow(row)

    return output.getvalue()


def export_to_excel(questions: List[Dict[str, Any]]) -> bytes:
    """Export questions to standard Excel (.xlsx) workbook bytes."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "题库备份"

    headers = [
        "题干", "题型", "选项A", "选项B", "选项C", "选项D", "选项E", "选项F",
        "正确答案", "解析", "难度", "标签"
    ]
    ws.append(headers)

    type_map = {
        "SINGLE": "单选",
        "MULTI": "多选",
        "JUDGE": "判断",
        "ESSAY": "简答",
    }

    for q in questions:
        stem = q.get("stem", "")
        q_type = type_map.get(q.get("type", "SINGLE"), "单选")
        opt_dict = {"A": "", "B": "", "C": "", "D": "", "E": "", "F": ""}

        opts = q.get("options") or []
        for opt in opts:
            if isinstance(opt, dict):
                k = str(opt.get("key", "")).upper()
                c = opt.get("content", opt.get("text", ""))
                if k in opt_dict:
                    opt_dict[k] = c

        answer = q.get("answer", "")
        explanation = q.get("explanation", "")
        diff = q.get("difficulty", 3)
        tags = ", ".join(q.get("tags", [])) if isinstance(q.get("tags"), list) else str(q.get("tags") or "")

        ws.append([
            stem, q_type,
            opt_dict["A"], opt_dict["B"], opt_dict["C"], opt_dict["D"], opt_dict["E"], opt_dict["F"],
            answer, explanation, diff, tags
        ])

    bio = io.BytesIO()
    wb.save(bio)
    wb.close()
    return bio.getvalue()


def export_bank_content(
    questions: List[Dict[str, Any]],
    format_str: str = "json"
) -> Tuple[Union[str, bytes], str, str]:
    """Dispatch export by format string.

    Returns:
        (content, media_type, file_extension)
    """
    fmt = format_str.strip().lower()
    if fmt in ("csv",):
        return export_to_csv(questions), "text/csv; charset=utf-8", "csv"
    elif fmt in ("text", "markdown", "md", "txt"):
        return export_to_text(questions), "text/plain; charset=utf-8", "txt"
    elif fmt in ("excel", "xlsx", "xls"):
        return export_to_excel(questions), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        # Default to JSON
        return export_to_json(questions), "application/json; charset=utf-8", "json"
