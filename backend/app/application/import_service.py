import json
from typing import Any, Dict, List, Optional
import uuid

from backend.app.infrastructure.db.connection import transaction
from backend.app.infrastructure.importers.text_importer import parse_csv_content, parse_json_content, parse_markdown_text
from backend.app.infrastructure.importers.pdf_importer import parse_pdf_questions
from backend.app.infrastructure.importers.spreadsheet_importer import (
    analyze_spreadsheet_structure,
    parse_rows_with_mapping,
    read_csv_rows,
    read_xlsx_rows,
)


class DuplicateImportError(ValueError):
    def __init__(self, preview: dict):
        super().__init__("重复题目需要明确选择 duplicate_strategy: skip、new 或 merge")
        self.preview = preview


class ImportService:
    def __init__(self, banks, questions, jobs=None):
        self.banks = banks
        self.questions = questions
        self.jobs = jobs

    def _begin(self, user_id: str, bank_id: str, fmt: str, filename: str | None = None):
        return self.jobs.create(user_id, bank_id, fmt, filename) if self.jobs else None

    def _finish(self, user_id: str, job: dict | None, status: str, imported_count: int = 0, reason: str | None = None):
        if self.jobs and job:
            return self.jobs.finish(job["id"], user_id, status, imported_count, reason)
        return None

    @staticmethod
    def _key(item: dict) -> tuple[str, str]:
        return (str(item.get("stem") or "").strip().casefold(), str(item.get("answer") or "").strip().upper())

    def _find_duplicates(self, user_id: str, bank_id: str, items: list[dict]) -> list[dict]:
        existing = self.questions.list_for_bank(bank_id, user_id)
        by_key = {self._key(item): item for item in existing}
        duplicates = []
        for index, item in enumerate(items):
            match = by_key.get(self._key(item))
            if match:
                duplicates.append({"index": index, "question_id": match["id"], "stem": item.get("stem", "")})
        return duplicates

    def _parse(self, fmt: str, content: str) -> list[dict]:
        if fmt in {"text", "markdown"}:
            items = parse_markdown_text(content)
        elif fmt == "csv":
            items = parse_csv_content(content)
        elif fmt == "json":
            items = parse_json_content(content)
        else:
            raise ValueError("unsupported import format")
        if not items:
            raise ValueError("no recognizable questions found")
        return items

    def _persist_items(
        self,
        user_id: str,
        bank_id: str,
        job: dict | None,
        items: list[dict],
        duplicates: list[dict],
        duplicate_strategy: str,
        conn=None,
    ) -> dict:
        if duplicates and duplicate_strategy not in {"skip", "new", "merge"}:
            preview = {
                "accepted": False,
                "reason": "发现重复题目，请选择处理策略",
                "question_count": len(items),
                "duplicates": duplicates,
            }
            if conn is None:
                self._finish(user_id, job, "PRECHECK_FAILED", reason=preview["reason"])
            elif job:
                conn.execute(
                    "UPDATE import_jobs SET status = 'PRECHECK_FAILED', reason = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (preview["reason"], job["id"]),
                )
            raise DuplicateImportError(preview)

        duplicate_by_index = {item["index"]: item for item in duplicates}
        operations = []
        for index, item in enumerate(items):
            duplicate = duplicate_by_index.get(index)
            if duplicate and duplicate_strategy == "skip":
                continue
            if duplicate and duplicate_strategy == "merge":
                operations.append({"op": "merge", "question_id": duplicate["question_id"], "payload": item})
            else:
                operations.append({"op": "create", "payload": item})

        try:
            created = self.questions.batch_create_or_update_questions(user_id, bank_id, operations, conn=conn) if operations else []
        except ValueError as exc:
            if conn is None:
                self._finish(user_id, job, "PRECHECK_FAILED", reason=str(exc))
            elif job:
                conn.execute(
                    "UPDATE import_jobs SET status = 'PRECHECK_FAILED', reason = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (str(exc), job["id"]),
                )
            raise
        except Exception as exc:
            if conn is None:
                self._finish(user_id, job, "FAILED", reason=str(exc))
            elif job:
                conn.execute(
                    "UPDATE import_jobs SET status = 'FAILED', reason = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (str(exc), job["id"]),
                )
            raise

        if conn is None:
            self._finish(user_id, job, "IMPORTED", len(created))
        elif job:
            conn.execute(
                "UPDATE import_jobs SET status = 'IMPORTED', imported_count = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (len(created), job["id"]),
            )
        return {
            "bank_id": bank_id,
            "job_id": job["id"] if job else None,
            "imported_count": len(created),
            "duplicate_count": len(duplicates),
            "questions": created,
        }

    def preview_content(self, user_id: str, bank_id: str, fmt: str, content: str) -> dict:
        if not self.banks.get_for_user(bank_id, user_id):
            raise LookupError("bank not found")
        items = self._parse(fmt, content)
        duplicates = self._find_duplicates(user_id, bank_id, items)
        return {
            "accepted": not duplicates,
            "reason": "发现重复题目，请选择处理策略" if duplicates else "预检通过",
            "question_count": len(items),
            "format": fmt,
            "duplicates": duplicates,
        }

    def preview_spreadsheet(
        self,
        user_id: str,
        bank_id: str,
        filename: str,
        content: bytes,
        custom_mapping: Optional[Dict[str, Any]] = None,
    ) -> dict:
        if not self.banks.get_for_user(bank_id, user_id):
            raise LookupError("bank not found")
        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if suffix == "xlsx":
            headers, rows = read_xlsx_rows(content)
        elif suffix == "csv":
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("文件必须使用 UTF-8 编码") from exc
            headers, rows = read_csv_rows(text)
        else:
            raise ValueError("仅支持预览 XLSX 和 CSV 表格")

        analysis = analyze_spreadsheet_structure(headers, rows)
        mapping = custom_mapping or analysis["mapping"]
        missing = []
        if mapping.get("stem") is None:
            missing.append("stem")
        if mapping.get("answer") is None:
            missing.append("answer")

        items = []
        duplicates = []
        if not missing:
            try:
                items = parse_rows_with_mapping(rows, mapping)
                duplicates = self._find_duplicates(user_id, bank_id, items)
            except Exception:
                items = []

        if missing:
            accepted = False
            reason = f"缺少必要列映射（{', '.join(missing)}）"
        elif not items:
            accepted = False
            reason = "表格中未识别到有效题目"
        elif duplicates:
            accepted = False
            reason = "发现重复题目，请选择处理策略"
        else:
            accepted = True
            reason = "预检通过"
        return {
            "accepted": accepted,
            "reason": reason,
            "headers": headers,
            "mapping": mapping,
            "missing": missing,
            "preview_rows": rows[:5],
            "question_count": len(items),
            "duplicates": duplicates,
        }

    def import_content(self, user_id: str, bank_id: str, fmt: str, content: str, duplicate_strategy: str = "prompt") -> dict:
        if not self.banks.get_for_user(bank_id, user_id):
            raise LookupError("bank not found")
        job = self._begin(user_id, bank_id, fmt)
        try:
            items = self._parse(fmt, content)
            duplicates = self._find_duplicates(user_id, bank_id, items)
        except ValueError as exc:
            self._finish(user_id, job, "PRECHECK_FAILED", reason=str(exc))
            raise
        except Exception as exc:
            self._finish(user_id, job, "FAILED", reason=str(exc))
            raise

        res = self._persist_items(user_id, bank_id, job, items, duplicates, duplicate_strategy)
        res["format"] = fmt
        return res

    def import_pdf(self, user_id: str, bank_id: str, content: bytes, duplicate_strategy: str = "prompt") -> dict:
        if not self.banks.get_for_user(bank_id, user_id):
            raise LookupError("bank not found")
        job = self._begin(user_id, bank_id, "pdf")
        try:
            items = parse_pdf_questions(content)
            duplicates = self._find_duplicates(user_id, bank_id, items)
        except ValueError as exc:
            self._finish(user_id, job, "PRECHECK_FAILED", reason=str(exc))
            raise
        except Exception as exc:
            self._finish(user_id, job, "FAILED", reason=str(exc))
            raise

        res = self._persist_items(user_id, bank_id, job, items, duplicates, duplicate_strategy)
        res["format"] = "pdf"
        return res

    def preview_pdf(self, user_id: str, bank_id: str, filename: str, content: bytes) -> dict:
        if not self.banks.get_for_user(bank_id, user_id):
            raise LookupError("bank not found")
        from backend.app.infrastructure.importers.pdf_importer import extract_pdf_candidates
        parsed = extract_pdf_candidates(content)
        candidates = parsed["questions"]
        if not candidates:
            raise ValueError("PDF 未能识别出任何题目内容")

        draft_id = str(uuid.uuid4())
        with transaction(self.questions.db_path) as conn:
            conn.execute(
                """INSERT INTO pdf_import_drafts(id, user_id, bank_id, filename, candidate_questions_json, status)
                   VALUES (?, ?, ?, ?, ?, 'PENDING')""",
                (draft_id, user_id, bank_id, filename, json.dumps(candidates, ensure_ascii=False)),
            )

        duplicates = self._find_duplicates(user_id, bank_id, candidates)
        return {
            "draft_id": draft_id,
            "filename": filename,
            "confidence": parsed["confidence"],
            "text_snippet": parsed["text_snippet"],
            "question_count": len(candidates),
            "candidates": candidates,
            "duplicates": duplicates,
        }

    def confirm_pdf_draft(self, user_id: str, bank_id: str, draft_id: str, questions: list[dict], duplicate_strategy: str = "skip") -> dict:
        if not self.banks.get_for_user(bank_id, user_id):
            raise LookupError("bank not found")
        if not questions:
            raise ValueError("提交的题目列表不能为空")

        with transaction(self.questions.db_path) as conn:
            # Atomic CAS transition: ensures only one worker/call can confirm this pending draft
            cursor = conn.execute(
                """UPDATE pdf_import_drafts
                   SET status = 'CONFIRMED', updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND user_id = ? AND bank_id = ? AND status = 'PENDING'""",
                (draft_id, user_id, bank_id),
            )
            if cursor.rowcount == 0:
                draft_row = conn.execute(
                    "SELECT status FROM pdf_import_drafts WHERE id = ? AND user_id = ? AND bank_id = ?",
                    (draft_id, user_id, bank_id),
                ).fetchone()
                if not draft_row:
                    raise LookupError("未找到对应的 PDF 校对草稿")
                raise ValueError("该校对草稿已完成导入或已作废")

            draft_filename = conn.execute(
                "SELECT filename FROM pdf_import_drafts WHERE id = ?", (draft_id,)
            ).fetchone()[0]

            job_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO import_jobs(id, user_id, bank_id, filename, format, status) VALUES (?, ?, ?, ?, 'pdf', 'PENDING')",
                (job_id, user_id, bank_id, draft_filename),
            )
            job = {"id": job_id}

            duplicates = self._find_duplicates(user_id, bank_id, questions)
            res = self._persist_items(user_id, bank_id, job, questions, duplicates, duplicate_strategy, conn=conn)
            res["format"] = "pdf"
            res["draft_id"] = draft_id
            res["status"] = "IMPORTED"
            return res

    def import_file(
        self,
        user_id: str,
        bank_id: str,
        filename: str,
        content: bytes,
        duplicate_strategy: str = "prompt",
        custom_mapping: Optional[Dict[str, Any]] = None,
    ) -> dict:
        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if suffix == "pdf":
            return self.import_pdf(user_id, bank_id, content, duplicate_strategy)

        if suffix == "xlsx":
            job = self._begin(user_id, bank_id, "xlsx", filename)
            try:
                headers, rows = read_xlsx_rows(content)
                analysis = analyze_spreadsheet_structure(headers, rows)
                mapping = custom_mapping or analysis["mapping"]
                if mapping.get("stem") is None or mapping.get("answer") is None:
                    raise ValueError("Excel 至少需要题干和答案列")
                items = parse_rows_with_mapping(rows, mapping)
                if not items:
                    raise ValueError("Excel 中未识别到有效题目")
                duplicates = self._find_duplicates(user_id, bank_id, items)
            except ValueError as exc:
                self._finish(user_id, job, "PRECHECK_FAILED", reason=str(exc))
                raise
            except Exception as exc:
                self._finish(user_id, job, "FAILED", reason=str(exc))
                raise
            return self._persist_items(user_id, bank_id, job, items, duplicates, duplicate_strategy)

        if suffix == "csv":
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("文件必须使用 UTF-8 编码") from exc

            # If custom mapping is provided or headers look like spreadsheet columns
            if custom_mapping is not None:
                job = self._begin(user_id, bank_id, "csv", filename)
                try:
                    headers, rows = read_csv_rows(text)
                    if custom_mapping.get("stem") is None or custom_mapping.get("answer") is None:
                        raise ValueError("CSV 至少需要题干和答案列")
                    items = parse_rows_with_mapping(rows, custom_mapping)
                    if not items:
                        raise ValueError("CSV 中未识别到有效题目")
                    duplicates = self._find_duplicates(user_id, bank_id, items)
                except ValueError as exc:
                    self._finish(user_id, job, "PRECHECK_FAILED", reason=str(exc))
                    raise
                except Exception as exc:
                    self._finish(user_id, job, "FAILED", reason=str(exc))
                    raise
                return self._persist_items(user_id, bank_id, job, items, duplicates, duplicate_strategy)
            else:
                # Try auto-detecting with spreadsheet mapping first, else fallback to standard csv
                try:
                    headers, rows = read_csv_rows(text)
                    analysis = analyze_spreadsheet_structure(headers, rows)
                    if analysis["mapping"].get("stem") is not None and analysis["mapping"].get("answer") is not None:
                        job = self._begin(user_id, bank_id, "csv", filename)
                        items = parse_rows_with_mapping(rows, analysis["mapping"])
                        if items:
                            duplicates = self._find_duplicates(user_id, bank_id, items)
                            return self._persist_items(user_id, bank_id, job, items, duplicates, duplicate_strategy)
                except Exception:
                    pass
                return self.import_content(user_id, bank_id, "csv", text, duplicate_strategy)

        if suffix in {"json", "txt", "md", "markdown"}:
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("文件必须使用 UTF-8 编码") from exc
            return self.import_content(user_id, bank_id, "markdown" if suffix in {"txt", "md", "markdown"} else suffix, text, duplicate_strategy)

        raise ValueError("仅支持 PDF、XLSX、CSV、JSON、TXT 和 Markdown 文件")
