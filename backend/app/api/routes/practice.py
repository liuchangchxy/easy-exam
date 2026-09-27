from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app.dependencies import current_user

router = APIRouter(prefix="/practice", tags=["practice"])


class StartSessionPayload(BaseModel):
    bank_id: str
    mode: str = "PRACTICE"
    total_questions: int = 0
    time_limit: int = 0
    question_ids: list[str] | None = None
    config: dict | None = None
    record_mistakes: bool | None = None


class AttemptPayload(BaseModel):
    question_id: str
    user_answer: Any
    mistake_cause: str | None = None
    fsrs_rating: int | None = None


class DraftPayload(BaseModel):
    current_index: int | None = None
    answers: dict | None = None
    flags: list[str] | None = None
    time_spent: int | None = None


class FlagPayload(BaseModel):
    question_id: str


@router.get("/sessions/active")
def list_active_sessions(request: Request, mode: str | None = None, user=Depends(current_user)):
    return request.app.state.services.practice.list_active_sessions(user["id"], mode)


@router.post("/sessions", status_code=201)
def start_session(payload: StartSessionPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.start_session(
            user["id"], payload.bank_id, payload.mode, payload.total_questions, payload.time_limit,
            question_ids=payload.question_ids,
            config=payload.config,
            record_mistakes=payload.record_mistakes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/attempts", status_code=201)
def submit_attempt(session_id: str, payload: AttemptPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.submit_attempt(
            user["id"], session_id, payload.question_id, payload.user_answer,
            fsrs_rating=payload.fsrs_rating, mistake_cause=payload.mistake_cause,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.get_session(user["id"], session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/questions")
def get_session_questions(session_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.get_session(user["id"], session_id)["questions"]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/answer", status_code=201)
def submit_answer_alias(session_id: str, payload: AttemptPayload, request: Request, user=Depends(current_user)):
    return submit_attempt(session_id, payload, request, user)


@router.post("/sessions/{session_id}/sync")
def sync_draft(session_id: str, payload: DraftPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.sync_draft(user["id"], session_id, payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/toggle-flag")
def toggle_flag(session_id: str, payload: FlagPayload, request: Request, user=Depends(current_user)):
    try:
        return {"flags": request.app.state.services.practice.toggle_flag(user["id"], session_id, payload.question_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.complete_session(user["id"], session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/abandon")
def abandon_session(session_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.abandon_session(user["id"], session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/abandon-all")
def abandon_all_sessions(request: Request, user=Depends(current_user)):
    return request.app.state.services.practice.abandon_all_sessions(user["id"])
