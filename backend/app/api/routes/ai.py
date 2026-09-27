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


class AiConfigPayload(BaseModel):
    ai_provider: str = "openai"
    ai_api_base: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_api_key: str | None = None
    search_provider: str = "open-webSearch"
    search_api_key: str | None = None
    search_api_base: str = "http://localhost:8000/v1/search"


@router.get("/config")
def get_ai_config(request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.get_user_ai_config(user["id"])
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/config")
def update_ai_config(payload: AiConfigPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.save_user_ai_config(user["id"], payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


class VariantGeneratePayload(BaseModel):
    original_question_id: str
    target_bank_id: str
    prompt_hint: str = ""


class DraftAcceptPayload(BaseModel):
    modifications: dict | None = None


@router.post("/variants", status_code=201)
def generate_variant(payload: VariantGeneratePayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.generate_variant_draft(
            user_id=user["id"],
            original_question_id=payload.original_question_id,
            target_bank_id=payload.target_bank_id,
            prompt_hint=payload.prompt_hint,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/drafts")
def list_drafts(status: str = "DRAFT", request: Request = None, user=Depends(current_user)):
    return request.app.state.services.ai.list_variant_drafts(user["id"], status)


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.get_variant_draft(user["id"], draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/accept", status_code=200)
def accept_draft(draft_id: str, payload: DraftAcceptPayload, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.accept_variant_draft(
            user_id=user["id"],
            draft_id=draft_id,
            modifications=payload.modifications,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/drafts/{draft_id}", status_code=200)
@router.post("/drafts/{draft_id}/discard", status_code=200)
def discard_draft(draft_id: str, request: Request, user=Depends(current_user)):
    try:
        return request.app.state.services.ai.discard_variant_draft(user["id"], draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
