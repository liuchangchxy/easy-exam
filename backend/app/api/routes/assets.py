from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from backend.app.dependencies import current_user

router = APIRouter(prefix="/assets", tags=["assets"])


class AssetPayload(BaseModel):
    asset_type: str = Field(pattern="^(NOTE|SUMMARY|MNEMONIC)$")
    content: str = Field(min_length=1)
    question_id: str | None = None
    knowledge_tag_id: str | None = None


@router.post("", status_code=201)
def create_asset(payload: AssetPayload, request: Request, user=Depends(current_user)):
    return request.app.state.services.assets.create(user["id"], payload.model_dump())


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
