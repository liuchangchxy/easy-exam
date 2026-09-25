import json
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from backend.app.dependencies import current_user
from backend.app.application.import_service import DuplicateImportError

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
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"文件导入处理失败：{exc}") from exc
