from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import current_user

router = APIRouter(prefix="/ai", tags=["ai"])


class AnswerPayload(BaseModel):
    content: str = Field(min_length=1)
    source: str = "AI"
    provider: str | None = None


class GeneratePayload(BaseModel):
    query: str = ""
    history: list[dict[str, str]] | None = None


class VerifyPayload(BaseModel):
    query: str = ""


@router.post("/questions/{question_id}/answers", status_code=201)
def save_answer(question_id: str, payload: AnswerPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.save_candidate(user["id"], question_id, payload.content, payload.source, payload.provider)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/questions/{question_id}/generate", status_code=201)
def generate_answer(question_id: str, payload: GeneratePayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.generate_answer(user["id"], question_id, payload.query, payload.history)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/questions/{question_id}/verify-web", status_code=201)
def verify_web(question_id: str, payload: VerifyPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.request_web_verification(user["id"], question_id, payload.query)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/questions/{question_id}/answers")
def list_answers(question_id: str, request: Request, user=Depends(current_user)):
    return request.app.state.services.ai.answers.list_for_question(question_id, user["id"])


@router.post("/answers/{answer_id}/adopt")
def adopt_answer(answer_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.adopt_personal_answer(user["id"], answer_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ChatMessagePayload(BaseModel):
    content: str = Field(min_length=1)
    conversation_id: str | None = None
    parent_message_id: str | None = None


@router.post("/questions/{question_id}/messages", status_code=201)
def send_chat_message(question_id: str, payload: ChatMessagePayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.send_chat_message(
            user_id=user["id"],
            question_id=question_id,
            content=payload.content,
            conversation_id=payload.conversation_id,
            parent_message_id=payload.parent_message_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/questions/{question_id}/conversations")
def list_question_conversations(question_id: str, request: Request, user=Depends(current_user)):
    return request.app.state.services.ai.list_conversations(user["id"], question_id)


@router.get("/conversations/{conversation_id}/messages")
def list_conversation_messages(conversation_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.list_messages(user["id"], conversation_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/messages/{message_id}/thread")
def get_message_thread(message_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.get_message_thread(user["id"], message_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
