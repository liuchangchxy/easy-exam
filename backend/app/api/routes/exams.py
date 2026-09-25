from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import current_user

router = APIRouter(prefix="/exams", tags=["exams"])


class ProfilePayload(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class BlueprintPayload(BaseModel):
    blueprint: Dict[str, Any] = Field(default_factory=dict)


class ExamSessionPayload(BaseModel):
    bank_id: str
    total_questions: int = 0
    time_limit: int = 0
    profile_id: str | None = None


@router.post("/profiles", status_code=201)
def create_profile(payload: ProfilePayload, request: Request, user=Depends(current_user)):
    return request.app.state.services.exams.create_profile(user["id"], payload.name, payload.description)


@router.post("/profiles/{profile_id}/blueprint", status_code=201)
def save_blueprint(profile_id: str, payload: BlueprintPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.exams.save_blueprint(user["id"], profile_id, payload.blueprint)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions", status_code=201)
def start_exam(payload: ExamSessionPayload, request: Request, user=Depends(current_user)):
    try:
        blueprint_id = None
        if payload.profile_id:
            blueprint = request.app.state.services.exams.latest_blueprint(user["id"], payload.profile_id)
            if not blueprint:
                raise LookupError("exam blueprint not found")
            blueprint_id = blueprint["id"]
        return request.app.state.services.practice.start_session(
            user["id"], payload.bank_id, "EXAM", payload.total_questions, payload.time_limit,
            payload.profile_id, blueprint_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/complete")
def complete_exam(session_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.complete_session(user["id"], session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
