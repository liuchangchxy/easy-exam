from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import current_user

router = APIRouter(prefix="/mistakes", tags=["mistakes"])


class ReviewPayload(BaseModel):
    user_answer: Any
    rating: int = Field(ge=1, le=4)
    mistake_cause: str | None = None


@router.get("")
def list_mistakes(bank_id: str | None = None, request: Request = None, user=Depends(current_user)):
    return request.app.state.services.practice.practices.list_mistakes(user["id"], bank_id)


@router.get("/due")
def list_due(bank_id: str | None = None, request: Request = None, user=Depends(current_user)):
    return request.app.state.services.practice.practices.list_due_reviews(user["id"], bank_id)


class MistakeCausePayload(BaseModel):
    mistake_cause: str


@router.put("/{question_id}/cause")
def update_mistake_cause(question_id: str, payload: MistakeCausePayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.update_mistake_cause(user["id"], question_id, payload.mistake_cause)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{question_id}/review", status_code=201)
def review_question(question_id: str, payload: ReviewPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.practice.review_answer(
            user["id"], question_id, payload.user_answer, payload.rating, payload.mistake_cause
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
