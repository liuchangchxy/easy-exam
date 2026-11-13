import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from backend.app.dependencies import current_user
from backend.app.application.import_service import DuplicateImportError
from backend.app.infrastructure.db.repositories.import_draft_repository import DraftStateTooLargeError

router = APIRouter(prefix="/imports", tags=["imports"])


class ImportPayload(BaseModel):
    format: str = "text"
    content: str
    duplicate_strategy: str = "prompt"


@router.post("/banks/{bank_id}", status_code=201)
def import_bank(bank_id: str, payload: ImportPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.importer.import_content(user["id"], bank_id, payload.format, payload.content, payload.duplicate_strategy)
    except DuplicateImportError as exc:
        raise HTTPException(status_code=409, detail=exc.preview) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"导入处理失败：{exc}") from exc


@router.post("/banks/{bank_id}/preview")
def preview_import(bank_id: str, payload: ImportPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.importer.preview_content(user["id"], bank_id, payload.format, payload.content)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"预检失败：{exc}") from exc


@router.post("/banks/{bank_id}/preview-file")
async def preview_file(bank_id: str, request: Request, file: UploadFile = File(...), user=Depends(current_user)):
    if not file.filename:
        raise HTTPException(status_code=422, detail="缺少文件名")
    form = await request.form()
    mapping_raw = form.get("column_mapping") or form.get("mapping") or request.query_params.get("column_mapping") or request.query_params.get("mapping")
    mapping = None
    if mapping_raw:
        try:
            mapping = json.loads(mapping_raw) if isinstance(mapping_raw, str) else mapping_raw
        except Exception:
            mapping = None
    content = await file.read()
    try:
        return request.app.state.services.importer.preview_spreadsheet(user["id"], bank_id, file.filename, content, mapping)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"文件预检失败：{exc}") from exc


@router.post("/banks/{bank_id}/file", status_code=201)
async def import_file(bank_id: str, request: Request, duplicate_strategy: str = "prompt", file: UploadFile = File(...), user=Depends(current_user)):
    if not file.filename:
        raise HTTPException(status_code=422, detail="缺少文件名，无法判断导入格式")
    form = await request.form()
    dup = form.get("duplicate_strategy") or duplicate_strategy
    mapping_raw = form.get("column_mapping") or form.get("mapping") or request.query_params.get("column_mapping") or request.query_params.get("mapping")
    mapping = None
    if mapping_raw:
        try:
            mapping = json.loads(mapping_raw) if isinstance(mapping_raw, str) else mapping_raw
        except Exception:
            mapping = None
    try:
        return request.app.state.services.importer.import_file(
            user["id"], bank_id, file.filename, await file.read(), duplicate_strategy=dup, custom_mapping=mapping
        )
    except DuplicateImportError as exc:
        raise HTTPException(status_code=409, detail=exc.preview) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"文件导入处理失败：{exc}") from exc


class PdfConfirmPayload(BaseModel):
    draft_id: str
    questions: list[dict]
    duplicate_strategy: str = "skip"


@router.post("/banks/{bank_id}/pdf-preview")
async def preview_pdf_file(bank_id: str, request: Request, file: UploadFile = File(...), user=Depends(current_user)):
    if not file.filename:
        raise HTTPException(status_code=422, detail="缺少文件名")
    content = await file.read()
    try:
        return request.app.state.services.importer.preview_pdf(user["id"], bank_id, file.filename, content)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"PDF 解析失败：{exc}") from exc


@router.post("/banks/{bank_id}/pdf-confirm", status_code=201)
def confirm_pdf_import(bank_id: str, payload: PdfConfirmPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.importer.confirm_pdf_draft(
            user["id"], bank_id, payload.draft_id, payload.questions, payload.duplicate_strategy
        )
    except DuplicateImportError as exc:
        raise HTTPException(status_code=409, detail=exc.preview) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"PDF 确认入库失败：{exc}") from exc


# --------------------------------------------------------------- wizard drafts


class DraftCreatePayload(BaseModel):
    source_kind: str = "file"
    filename: str | None = None
    step: int = 1
    state: Any = None


class DraftUpdatePayload(BaseModel):
    state: Any = None
    step: int | None = None
    filename: str | None = None
    status: str | None = None


@router.post("/banks/{bank_id}/drafts", status_code=201)
def create_import_draft(bank_id: str, payload: DraftCreatePayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.import_drafts.create(
            user["id"],
            bank_id,
            source_kind=payload.source_kind,
            filename=payload.filename,
            step=payload.step,
            state=payload.state,
        )
    except DraftStateTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/banks/{bank_id}/drafts")
def list_import_drafts(bank_id: str, request: Request, status: str = "OPEN", user=Depends(current_user)):
    try:
        return request.app.state.services.import_drafts.list_for_bank(user["id"], bank_id, status=status)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/drafts/{draft_id}")
def get_import_draft(draft_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.import_drafts.get(user["id"], draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/drafts/{draft_id}")
def update_import_draft(draft_id: str, payload: DraftUpdatePayload, request: Request, user=Depends(current_user)):
    fields = payload.model_dump(exclude_unset=True)
    try:
        return request.app.state.services.import_drafts.update(user["id"], draft_id, fields)
    except DraftStateTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/drafts/{draft_id}", status_code=204)
def delete_import_draft(draft_id: str, request: Request, user=Depends(current_user)):
    try:
        request.app.state.services.import_drafts.delete(user["id"], draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None


# --------------------------------------------------------- asynchronous jobs

_ASYNC_FORMATS = {"pdf", "xlsx", "csv", "json", "txt", "md", "markdown", "text"}


def _normalized_format(value: str) -> str:
    fmt = (value or "").strip().lower()
    return "markdown" if fmt in {"txt", "md", "markdown"} else fmt


@router.post("/banks/{bank_id}/jobs", status_code=202)
async def start_import_job(bank_id: str, request: Request, user=Depends(current_user)):
    content_type = (request.headers.get("content-type") or "").lower()
    mapping = None
    filename = None
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not getattr(upload, "filename", None):
            raise HTTPException(status_code=422, detail="缺少文件名，无法判断导入格式")
        filename = upload.filename
        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if suffix not in _ASYNC_FORMATS:
            raise HTTPException(status_code=422, detail="仅支持 PDF、XLSX、CSV、JSON、TXT 和 Markdown 文件")
        fmt = _normalized_format(suffix)
        duplicate_strategy = form.get("duplicate_strategy") or request.query_params.get("duplicate_strategy") or "prompt"
        mapping_raw = (
            form.get("column_mapping")
            or form.get("mapping")
            or request.query_params.get("column_mapping")
            or request.query_params.get("mapping")
        )
        if mapping_raw:
            try:
                mapping = json.loads(mapping_raw) if isinstance(mapping_raw, str) else mapping_raw
            except Exception:
                mapping = None
        content = await upload.read()
    else:
        try:
            payload = ImportPayload.model_validate(await request.json())
        except Exception as exc:
            raise HTTPException(status_code=422, detail="请求必须是 multipart 文件或 {format, content} JSON") from exc
        fmt = _normalized_format(payload.format)
        if fmt not in _ASYNC_FORMATS:
            raise HTTPException(status_code=422, detail="仅支持 PDF、XLSX、CSV、JSON、TXT 和 Markdown 文件")
        content = payload.content
        duplicate_strategy = payload.duplicate_strategy

    try:
        return request.app.state.services.importer.start_job(
            user["id"], bank_id, filename, fmt, content, duplicate_strategy, mapping
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
def get_import_job(job_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.importer.get_job(user["id"], job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel")
def cancel_import_job(job_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.importer.cancel_job(user["id"], job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
