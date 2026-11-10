from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.dependencies import current_user

router = APIRouter(prefix="/assets", tags=["assets"])


class AssetPayload(BaseModel):
    asset_type: str = Field(pattern="^(NOTE|SUMMARY|MNEMONIC)$")
    content: str = Field(min_length=1)
    question_id: str | None = None
    knowledge_tag_id: str | None = None


class AssetUpdatePayload(BaseModel):
    asset_type: str | None = Field(default=None, pattern="^(NOTE|SUMMARY|MNEMONIC)$")
    content: str | None = Field(default=None, min_length=1)


@router.post("", status_code=201)
def create_asset(payload: AssetPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.assets.create(user["id"], payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/upload", status_code=201)
async def upload_asset(
    request: Request,
    file: UploadFile = File(...),
    asset_type: str = Form("NOTE"),
    question_id: str | None = Form(None),
    knowledge_tag_id: str | None = Form(None),
    user=Depends(current_user),
):
    content = await file.read()
    try:
        return request.app.state.services.assets.create_from_file(
            user_id=user["id"],
            filename=file.filename or "",
            content=content,
            asset_type=asset_type,
            question_id=question_id,
            knowledge_tag_id=knowledge_tag_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("")
def list_assets(request: Request, question_id: str | None = None, user=Depends(current_user)):
    return request.app.state.services.assets.list_for_user(user["id"], question_id)


@router.get("/{asset_id}")
def get_asset(asset_id: str, request: Request, user=Depends(current_user)):
    asset = request.app.state.services.assets.get_for_user(user["id"], asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资料不存在或无权访问")
    return asset


@router.get("/{asset_id}/file")
def get_asset_file(asset_id: str, request: Request, download: bool = False, user=Depends(current_user)):
    stored = request.app.state.services.assets.get_file(user["id"], asset_id)
    if not stored:
        raise HTTPException(status_code=404, detail="资料文件不存在或已被删除")
    return FileResponse(
        path=str(stored["path"]),
        media_type=stored["mime_type"],
        filename=stored["file_name"],
        content_disposition_type="attachment" if download else "inline",
    )


@router.put("/{asset_id}")
def update_asset(asset_id: str, payload: AssetUpdatePayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.assets.update(user["id"], asset_id, payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="资料不存在或无权访问") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{asset_id}", status_code=204)
def delete_asset(asset_id: str, request: Request, user=Depends(current_user)):
    deleted = request.app.state.services.assets.delete(user["id"], asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="资料不存在或无权删除")
    return None
