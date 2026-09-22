"""FastAPI application entrypoint for FnExam.

Assembles all domain services and repositories:
- System health
- Question bank & question management & multi-format ingestion
- Practice & exam session lifecycles & client localStorage draft syncing
- Mistake elimination (2 consecutive correct answers) & FSRS reviews
- Contextual AI tutor SSE streaming with offline fallback
"""
from contextlib import asynccontextmanager
import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.config import BASE_DIR, get_settings
from backend.database import init_db
from backend.repositories import (
    BankRepository,
    MistakeRepository,
    QuestionRepository,
    SessionRepository,
)
from backend.services import (
    AIService,
    FSRS5,
    MistakeService,
    Scorer,
    SessionService,
    build_tutor_prompt,
    parse_csv_content,
    parse_excel_content,
    parse_json_content,
    parse_markdown_text,
)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class BankCreateRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "默认分类"


class QuestionCreateRequest(BaseModel):
    stem: str
    type: str = "SINGLE"
    options: List[Dict[str, Any]] = Field(default_factory=list)
    answer: str
    explanation: str = ""
    difficulty: int = 3
    tags: List[str] = Field(default_factory=list)


class ImportRequest(BaseModel):
    format: str = "text"  # "text" | "csv" | "json"
    content: str


class SessionCreateRequest(BaseModel):
    bank_id: str
    mode: str = "PRACTICE"  # PRACTICE, EXAM, ELIMINATION, FSRS
    total_questions: int = 0
    time_limit: int = 0
    mistake_cause: Optional[str] = None
    shuffle_questions: bool = False
    shuffle_options: bool = False


class AnswerSubmitRequest(BaseModel):
    question_id: str
    user_answer: Any
    time_spent_delta: int = 0
    mistake_cause: Optional[str] = None


class DraftSyncRequest(BaseModel):
    current_index: Optional[int] = None
    answers: Optional[Dict[str, Any]] = None
    flags: Optional[List[str]] = None
    time_spent: Optional[int] = None


class ToggleFlagRequest(BaseModel):
    question_id: str


class MistakePracticeRequest(BaseModel):
    user_answer: Any
    mistake_cause: Optional[str] = None


class TutorChatRequest(BaseModel):
    question_context: Dict[str, Any] = Field(default_factory=dict)
    user_query: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None


# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------


def create_app(
    db_path: Optional[str] = None,
    dist_dir: Optional[Union[str, Path]] = None,
) -> FastAPI:
    """Create and configure the FnExam FastAPI application instance."""
    settings = get_settings()
    resolved_db_path = db_path if db_path is not None else settings.db_path

    # Ensure database schema is initialized
    init_db(resolved_db_path)

    app = FastAPI(
        title="EasyExam API (易考宝)",
        description="Self-hosted modern AI exam and practice system for private cloud NAS",
        version="1.0.0",
    )

    # Enable CORS for multi-device mobile, tablet, and local frontend dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Repositories and Services
    bank_repo = BankRepository(resolved_db_path)
    question_repo = QuestionRepository(resolved_db_path)
    session_repo = SessionRepository(resolved_db_path)
    mistake_repo = MistakeRepository(resolved_db_path)
    fsrs_engine = FSRS5()
    mistake_service = MistakeService(mistake_repo=mistake_repo, fsrs=fsrs_engine)
    session_service = SessionService(
        session_repo=session_repo,
        question_repo=question_repo,
        mistake_service=mistake_service,
    )

    def get_ai_service() -> AIService:
        """Create fresh AIService reading current environment variables."""
        return AIService()

    # -----------------------------------------------------------------------
    # 1. System Health
    # -----------------------------------------------------------------------

    @app.get("/api/health")
    def health_check() -> Dict[str, str]:
        """System health check endpoint."""
        return {"status": "ok", "app": "easy-exam"}

    # -----------------------------------------------------------------------
    # 2. Banks & Questions
    # -----------------------------------------------------------------------

    @app.get("/api/banks")
    def list_banks() -> List[Dict[str, Any]]:
        """List all question banks."""
        return bank_repo.list_banks()

    @app.post("/api/banks")
    def create_bank(payload: BankCreateRequest) -> Dict[str, Any]:
        """Create a new question bank."""
        bank_id = bank_repo.create_bank(
            name=payload.name,
            description=payload.description,
            category=payload.category,
        )
        bank = bank_repo.get_bank(bank_id)
        if not bank:
            raise HTTPException(status_code=500, detail="Failed to retrieve created bank.")
        return bank

    @app.get("/api/banks/{bank_id}")
    def get_bank(bank_id: str) -> Dict[str, Any]:
        """Get bank details by ID."""
        bank = bank_repo.get_bank(bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail=f"Bank '{bank_id}' not found.")
        return bank

    @app.post("/api/banks/{bank_id}/questions")
    def create_question(bank_id: str, payload: QuestionCreateRequest) -> Dict[str, Any]:
        """Create a question in the specified bank."""
        bank = bank_repo.get_bank(bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail=f"Bank '{bank_id}' not found.")

        q_id = question_repo.create_question(
            bank_id=bank_id,
            q_type=payload.type,
            stem=payload.stem,
            options=payload.options,
            answer=payload.answer,
            explanation=payload.explanation,
            difficulty=payload.difficulty,
            tags=payload.tags,
        )
        q = question_repo.get_question(q_id)
        if not q:
            raise HTTPException(status_code=500, detail="Failed to retrieve created question.")
        return q

    @app.get("/api/banks/{bank_id}/questions")
    def list_questions(bank_id: str) -> List[Dict[str, Any]]:
        """List all questions belonging to a bank."""
        bank = bank_repo.get_bank(bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail=f"Bank '{bank_id}' not found.")
        return question_repo.list_questions_by_bank(bank_id)

    @app.post("/api/banks/{bank_id}/import")
    def import_questions(bank_id: str, payload: ImportRequest) -> Dict[str, Any]:
        """Import questions into a bank from text, markdown, CSV, JSON, or Excel (base64)."""
        bank = bank_repo.get_bank(bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail=f"Bank '{bank_id}' not found.")

        fmt = payload.format.strip().lower()
        if fmt in ("text", "markdown", "md"):
            parsed = parse_markdown_text(payload.content)
        elif fmt == "csv":
            parsed = parse_csv_content(payload.content)
        elif fmt == "json":
            try:
                parsed = parse_json_content(payload.content)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        elif fmt in ("excel", "xlsx", "xls"):
            b64_str = payload.content
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            try:
                raw_bytes = base64.b64decode(b64_str)
                parsed = parse_excel_content(raw_bytes)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse Excel content: {str(e)}")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format '{payload.format}'. Supported: text, csv, json, excel.",
            )

        created_questions: List[Dict[str, Any]] = []
        for item in parsed:
            q_id = question_repo.create_question(
                bank_id=bank_id,
                q_type=item.get("type", "SINGLE"),
                stem=item.get("stem", ""),
                options=item.get("options", []),
                answer=item.get("answer", ""),
                explanation=item.get("explanation", ""),
                difficulty=item.get("difficulty", 3),
                tags=item.get("tags", []),
            )
            q = question_repo.get_question(q_id)
            if q:
                created_questions.append(q)

        return {
            "imported_count": len(created_questions),
            "questions": created_questions,
        }

    @app.post("/api/banks/{bank_id}/upload")
    async def upload_questions_file(bank_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
        """Upload and import question bank file (.xlsx, .xls, .csv, .json, .txt, .md)."""
        bank = bank_repo.get_bank(bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail=f"Bank '{bank_id}' not found.")

        file_bytes = await file.read()
        filename = (file.filename or "").lower()

        try:
            if filename.endswith(".xlsx") or filename.endswith(".xls"):
                parsed = parse_excel_content(file_bytes)
            elif filename.endswith(".csv"):
                parsed = parse_csv_content(file_bytes)
            elif filename.endswith(".json"):
                text_content = file_bytes.decode("utf-8", errors="replace")
                parsed = parse_json_content(text_content)
            else:
                text_content = file_bytes.decode("utf-8", errors="replace")
                parsed = parse_markdown_text(text_content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"File parse error: {str(e)}")

        created_questions: List[Dict[str, Any]] = []
        for item in parsed:
            q_id = question_repo.create_question(
                bank_id=bank_id,
                q_type=item.get("type", "SINGLE"),
                stem=item.get("stem", ""),
                options=item.get("options", []),
                answer=item.get("answer", ""),
                explanation=item.get("explanation", ""),
                difficulty=item.get("difficulty", 3),
                tags=item.get("tags", []),
            )
            q = question_repo.get_question(q_id)
            if q:
                created_questions.append(q)

        return {
            "imported_count": len(created_questions),
            "questions": created_questions,
        }

    # -----------------------------------------------------------------------
    # 3. Sessions & Draft Sync
    # -----------------------------------------------------------------------

    @app.post("/api/sessions")
    def start_session(payload: SessionCreateRequest) -> Dict[str, Any]:
        """Start a new practice or exam session."""
        bank = bank_repo.get_bank(payload.bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail=f"Bank '{payload.bank_id}' not found.")

        total = payload.total_questions
        if total <= 0:
            total = bank.get("question_count", 0)

        session = session_service.start_session(
            bank_id=payload.bank_id,
            mode=payload.mode,
            total_questions=total,
            time_limit=payload.time_limit,
            shuffle_questions=payload.shuffle_questions,
            shuffle_options=payload.shuffle_options,
            mistake_cause=payload.mistake_cause,
        )
        return session

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> Dict[str, Any]:
        """Get session state and answers."""
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
        return session

    @app.get("/api/sessions/{session_id}/questions")
    def get_session_questions(session_id: str) -> List[Dict[str, Any]]:
        """Get the ordered/shuffled questions list for an active session."""
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
        questions = session.get("questions")
        if not questions and session.get("bank_id"):
            questions = question_repo.list_questions_by_bank(session["bank_id"])
        return questions or []

    @app.post("/api/sessions/{session_id}/answer")
    def submit_answer(session_id: str, payload: AnswerSubmitRequest) -> Dict[str, Any]:
        """Submit an answer to a question in an active session."""
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

        res = session_service.submit_answer(
            session_id=session_id,
            question_id=payload.question_id,
            user_answer=payload.user_answer,
            time_spent_delta=payload.time_spent_delta,
            mistake_cause=payload.mistake_cause,
        )
        return res

    @app.post("/api/sessions/{session_id}/sync")
    def sync_draft(session_id: str, payload: DraftSyncRequest) -> Dict[str, Any]:
        """Sync client localStorage draft progress into the session."""
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

        updated = session_service.sync_draft(
            session_id=session_id,
            current_index=payload.current_index,
            answers=payload.answers,
            flags=payload.flags,
            time_spent=payload.time_spent,
        )
        return updated

    @app.post("/api/sessions/{session_id}/toggle-flag")
    def toggle_flag(session_id: str, payload: ToggleFlagRequest) -> Dict[str, Any]:
        """Toggle question doubtful flag in session."""
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

        updated_flags = session_service.toggle_flag(
            session_id=session_id,
            question_id=payload.question_id,
        )
        return {"flags": updated_flags, "question_id": payload.question_id}

    @app.post("/api/sessions/{session_id}/complete")
    def complete_session(session_id: str) -> Dict[str, Any]:
        """Complete an examination or practice session and return the score report."""
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

        report = session_service.complete_session(session_id)
        return report

    # -----------------------------------------------------------------------
    # 4. Mistakes & FSRS
    # -----------------------------------------------------------------------

    @app.get("/api/mistakes")
    def list_mistakes(
        bank_id: Optional[str] = Query(None),
        cause: Optional[str] = Query(None),
    ) -> List[Dict[str, Any]]:
        """List active uncleared mistakes, optionally filtered by bank or 6-level taxonomy cause."""
        return mistake_service.get_active_mistakes_by_cause(bank_id=bank_id, cause=cause)

    @app.post("/api/mistakes/{question_id}/practice")
    def practice_mistake(question_id: str, payload: MistakePracticeRequest) -> Dict[str, Any]:
        """Submit an answer in mistake elimination mode. 2 consecutive correct answers clear the mistake."""
        q = question_repo.get_question(question_id)
        if not q:
            raise HTTPException(status_code=404, detail=f"Question '{question_id}' not found.")

        is_correct, score_ratio = Scorer.evaluate(
            q.get("type", "SINGLE"),
            payload.user_answer,
            q.get("answer", ""),
        )

        rec = mistake_service.record_question_result(
            question_id=question_id,
            bank_id=q.get("bank_id", ""),
            is_correct=is_correct,
            cause=payload.mistake_cause,
        )

        return {
            "is_correct": is_correct,
            "score_ratio": score_ratio,
            "consecutive_correct": rec.get("consecutive_correct", 0),
            "is_cleared": bool(rec.get("is_cleared", False)),
            "record": rec,
        }

    @app.get("/api/mistakes/due")
    def list_due_mistakes(bank_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
        """List questions due for review calculated by FSRS-5."""
        return mistake_service.get_due_reviews(bank_id=bank_id)

    # -----------------------------------------------------------------------
    # 5. Contextual AI Tutor
    # -----------------------------------------------------------------------

    @app.post("/api/ai/tutor/chat")
    def tutor_chat(payload: TutorChatRequest) -> StreamingResponse:
        """Stream AI tutor explanation using Server-Sent Events (SSE) with offline fallback."""
        ai = get_ai_service()
        messages = build_tutor_prompt(
            question_context=payload.question_context,
            user_query=payload.user_query,
            history=payload.history,
        )

        def event_stream() -> Generator[str, None, None]:
            for chunk in ai.stream_chat(messages):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # -----------------------------------------------------------------------
    # Static Assets (Frontend mounting if built)
    # -----------------------------------------------------------------------
    target_dist = Path(dist_dir) if dist_dir is not None else (BASE_DIR / "frontend" / "dist")
    if target_dist.exists() and target_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(target_dist), html=True), name="static")

    return app


# Default application instance for Uvicorn
app = create_app()

if __name__ == "__main__":
    import uvicorn
    from backend.config import HOST, PORT

    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
