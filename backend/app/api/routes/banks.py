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


@router.post("/{bank_id}/chapters", status_code=201)
def create_chapter(bank_id: str, payload: ChapterPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.banks.create_chapter(bank_id, user["id"], payload.name, payload.parent_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{bank_id}/chapters")
def list_chapters(bank_id: str, request: Request, user=Depends(current_user)):
    return request.app.state.services.banks.list_chapters(bank_id, user["id"])


@router.post("/{bank_id}/tags", status_code=201)
def create_tag(bank_id: str, payload: TagPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.banks.create_tag(bank_id, user["id"], payload.name)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{bank_id}/tags")
def list_tags(bank_id: str, request: Request, user=Depends(current_user)):
    return request.app.state.services.banks.list_tags(bank_id, user["id"])
