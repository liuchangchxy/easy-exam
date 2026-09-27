from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import current_user

router = APIRouter(prefix="/questions", tags=["questions"])


class QuestionUpdate(BaseModel):
    stem: str = Field(min_length=1)
    type: str = "SINGLE"
    options: List[Dict[str, Any]] = []
    answer: str = ""
    explanation: str = ""
    difficulty: int = 3
    tags: List[str] = []
    base_version_number: int | None = None
    chapter_id: str | None = None
    regrade_history: bool = False
    apply_fsrs: bool = True


class RegradePayload(BaseModel):
    apply_fsrs: bool = True


class ResolveConflictPayload(BaseModel):
    adopt_version_number: int


@router.put("/{question_id}")
def update_question(question_id: str, payload: QuestionUpdate, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.questions.create_next_version(user["id"], question_id, payload.model_dump())
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{question_id}/regrade")
def regrade_question(question_id: str, payload: RegradePayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.questions.regrade_question_history(user["id"], question_id, apply_fsrs=payload.apply_fsrs)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{question_id}/versions")
def list_versions(question_id: str, request: Request, user=Depends(current_user)):
    return request.app.state.services.questions.list_versions(question_id, user["id"])


@router.get("/{question_id}/conflict")
def get_conflict(question_id: str, request: Request, user=Depends(current_user)):
    conflict = request.app.state.services.questions.get_active_conflict(question_id, user["id"])
    return {"has_conflict": conflict is not None, "conflict": conflict}


@router.post("/{question_id}/resolve-conflict")
def resolve_conflict(question_id: str, payload: ResolveConflictPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.questions.resolve_conflict(user["id"], question_id, payload.adopt_version_number)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{question_id}")
def get_question(question_id: str, request: Request, user=Depends(current_user)):
    q = request.app.state.services.questions.get_for_user(question_id, user["id"])
    if not q:
        raise HTTPException(status_code=404, detail="question not found")
    return q
