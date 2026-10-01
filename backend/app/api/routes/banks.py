from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import current_user

router = APIRouter(prefix="/banks", tags=["banks"])


class BankPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    category: str = "默认分类"


class QuestionPayload(BaseModel):
    stem: str = Field(min_length=1)
    type: str = "SINGLE"
    options: List[Dict[str, Any]] = Field(default_factory=list)
    answer: str = ""
    explanation: str = ""
    difficulty: int | None = None
    tags: List[str] = Field(default_factory=list)
    chapter_id: str | None = None


class MemberPayload(BaseModel):
    username: str
    role: str = "MEMBER"


class ChapterPayload(BaseModel):
    name: str = Field(min_length=1)
    parent_id: str | None = None


class TagPayload(BaseModel):
    name: str = Field(min_length=1)


@router.get("")
def list_banks(request: Request, user=Depends(current_user)):
    return request.app.state.services.banks.list_for_user(user["id"])


@router.post("", status_code=201)
def create_bank(payload: BankPayload, request: Request, user=Depends(current_user)):
    return request.app.state.services.bank_service.create_bank(user["id"], payload.model_dump())


@router.post("/{bank_id}/questions", status_code=201)
def create_question(bank_id: str, payload: QuestionPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.bank_service.create_question(user["id"], bank_id, payload.model_dump())
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{bank_id}")
def get_bank(bank_id: str, request: Request, user=Depends(current_user)):
    bank = request.app.state.services.banks.get_for_user(bank_id, user["id"])
    if not bank:
        raise HTTPException(status_code=404, detail="bank not found")
    return bank


@router.get("/{bank_id}/questions")
def list_questions(bank_id: str, request: Request, user=Depends(current_user)):
    if not request.app.state.services.banks.get_for_user(bank_id, user["id"]):
        raise HTTPException(status_code=404, detail="bank not found")
    return request.app.state.services.questions.list_for_bank(bank_id, user["id"])


@router.post("/{bank_id}/questions/{question_id}/copy", status_code=201)
def copy_question(bank_id: str, question_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.bank_service.copy_question(user["id"], question_id, bank_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{bank_id}/members", status_code=201)
def add_member(bank_id: str, payload: MemberPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.banks.add_member(bank_id, user["id"], payload.username, payload.role)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{bank_id}/members")
def list_members(bank_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.banks.list_members(bank_id, user["id"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.delete("/{bank_id}/members/{member_user_id}", status_code=204)
def remove_member(bank_id: str, member_user_id: str, request: Request, user=Depends(current_user)):
    try:
        removed = request.app.state.services.banks.remove_member(bank_id, user["id"], member_user_id)
        if not removed:
            raise HTTPException(status_code=404, detail="member not found")
        return None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{bank_id}/chapters", status_code=201)
def create_chapter(bank_id: str, payload: ChapterPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.banks.create_chapter(bank_id, user["id"], payload.name, payload.parent_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{bank_id}/chapters")
def list_chapters(bank_id: str, request: Request, user=Depends(current_user)):
    return request.app.state.services.banks.list_chapters(bank_id, user["id"])


@router.put("/{bank_id}/chapters/{chapter_id}")
def update_chapter(bank_id: str, chapter_id: str, payload: ChapterPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.banks.update_chapter(bank_id, user["id"], chapter_id, payload.name, payload.parent_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{bank_id}/chapters/{chapter_id}", status_code=204)
def delete_chapter(bank_id: str, chapter_id: str, request: Request, user=Depends(current_user)):
    try:
        deleted = request.app.state.services.banks.delete_chapter(bank_id, user["id"], chapter_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="chapter not found")
        return None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{bank_id}/tags", status_code=201)
def create_tag(bank_id: str, payload: TagPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.banks.create_tag(bank_id, user["id"], payload.name)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{bank_id}/tags")
def list_tags(bank_id: str, request: Request, user=Depends(current_user)):
    return request.app.state.services.banks.list_tags(bank_id, user["id"])


@router.put("/{bank_id}/tags/{tag_id}")
def update_tag(bank_id: str, tag_id: str, payload: TagPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.banks.update_tag(bank_id, user["id"], tag_id, payload.name)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{bank_id}/tags/{tag_id}", status_code=204)
def delete_tag(bank_id: str, tag_id: str, request: Request, user=Depends(current_user)):
    try:
        deleted = request.app.state.services.banks.delete_tag(bank_id, user["id"], tag_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="tag not found")
        return None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc



@router.get("/{bank_id}/export")
def export_bank(bank_id: str, format: str = "json", request: Request = None, user=Depends(current_user)):
    from fastapi.responses import Response
    from backend.legacy.services.exporter import export_to_json, export_to_csv, export_to_text, export_to_excel

    bank = request.app.state.services.banks.get_for_user(bank_id, user["id"])
    if not bank:
        raise HTTPException(status_code=404, detail="bank not found")
    questions = request.app.state.services.questions.list_for_bank(bank_id, user["id"])
    fmt = (format or "json").lower()

    if fmt == "csv":
        content = export_to_csv(questions)
        return Response(content=content.encode("utf-8-sig"), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=bank_{bank_id}.csv"})
    elif fmt in ("txt", "text", "md"):
        content = export_to_text(questions)
        return Response(content=content.encode("utf-8"), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=bank_{bank_id}.txt"})
    elif fmt in ("xlsx", "excel"):
        content = export_to_excel(questions)
        return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=bank_{bank_id}.xlsx"})
    else:
        content = export_to_json(questions)
        return Response(content=content.encode("utf-8"), media_type="application/json; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=bank_{bank_id}.json"})
