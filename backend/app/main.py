"""Versioned modular-monolith FastAPI entrypoint."""
from pathlib import Path
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import ai, assets, auth, banks, exams, imports, kills, learning, mistakes, practice, questions, sync, system
from backend.app.application.auth_service import AuthService
from backend.app.application.bank_service import BankService
from backend.app.infrastructure.db.connection import migrate
from backend.app.infrastructure.db.repositories.bank_repository import BankRepository
from backend.app.infrastructure.db.repositories.question_repository import QuestionRepository
from backend.app.infrastructure.db.repositories.practice_repository import PracticeRepository
from backend.app.infrastructure.db.repositories.ai_answer_repository import AiAnswerRepository
from backend.app.infrastructure.db.repositories.ai_conversation_repository import AiConversationRepository
from backend.app.infrastructure.db.repositories.exam_repository import ExamRepository
from backend.app.infrastructure.db.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.db.repositories.import_job_repository import ImportJobRepository
from backend.app.infrastructure.db.repositories.user_repository import UserRepository, UserSessionRepository
from backend.app.infrastructure.security.sessions import token_hash


def create_app(db_path: str | None = None, dist_dir: str | Path | None = None) -> FastAPI:
    resolved = db_path or os.environ.get("DB_PATH") or str(Path(os.environ.get("DATA_DIR", "data")) / "easyexam-v1.db")
    migrate(resolved)
    users = UserRepository(resolved)
    user_sessions = UserSessionRepository(resolved)
    bank_repo = BankRepository(resolved)
    question_repo = QuestionRepository(resolved)
    practices = PracticeRepository(resolved)
    ai_answers = AiAnswerRepository(resolved)
    ai_conversations = AiConversationRepository(resolved)
    exams_repo = ExamRepository(resolved)
    assets_repo = AssetRepository(resolved)
    import_jobs = ImportJobRepository(resolved)
    from backend.app.infrastructure.db.repositories.ai_draft_repository import AiDraftRepository
    ai_drafts = AiDraftRepository(resolved)
    from backend.app.infrastructure.db.repositories.ai_config_repository import AiConfigRepository
    ai_configs = AiConfigRepository(resolved)
    from backend.app.infrastructure.ai.web_search import OpenWebSearchAdapter
    web_search = OpenWebSearchAdapter(os.environ.get("OPEN_WEBSEARCH_URL"))
    services = type("Services", (), {})()
    services.users = users
    services.user_sessions = user_sessions
    services.banks = bank_repo
    services.questions = question_repo
    services.auth = AuthService(users, user_sessions)
    services.bank_service = BankService(bank_repo, question_repo)
    from backend.app.application.practice_service import PracticeService
    services.practice = PracticeService(practices, question_repo, bank_repo, exams_repo)
    from backend.app.application.ai_tutor_service import AiTutorService
    services.ai = AiTutorService(
        ai_answers,
        question_repo,
        conversations=ai_conversations,
        web_search=web_search,
        assets=assets_repo,
        drafts=ai_drafts,
        ai_configs=ai_configs,
    )
    services.ai_conversations = ai_conversations
    services.ai_drafts = ai_drafts
    services.ai_configs = ai_configs
    from backend.app.application.import_service import ImportService
    services.importer = ImportService(bank_repo, question_repo, import_jobs)
    from backend.app.application.learning_service import LearningService
    services.learning = LearningService(practices)
    services.exams = exams_repo
    from backend.app.application.asset_service import AssetService
    services.assets = AssetService(assets_repo)
    services.token_hash = token_hash

    app = FastAPI(title="EasyExam API", version="1.0.0")
    app.state.services = services

    @app.middleware("http")
    async def add_no_cache_for_html(request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path == "/index.html" or path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.include_router(system.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(banks.router, prefix="/api/v1")
    app.include_router(practice.router, prefix="/api/v1")
    app.include_router(ai.router, prefix="/api/v1")
    app.include_router(questions.router, prefix="/api/v1")
    app.include_router(imports.router, prefix="/api/v1")
    app.include_router(mistakes.router, prefix="/api/v1")
    app.include_router(learning.router, prefix="/api/v1")
    app.include_router(exams.router, prefix="/api/v1")
    app.include_router(sync.router, prefix="/api/v1")
    app.include_router(kills.router, prefix="/api/v1")
    app.include_router(assets.router, prefix="/api/v1")
    target_dist = Path(dist_dir) if dist_dir is not None else Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if target_dist.exists() and target_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(target_dist), html=True), name="static")
    return app


app = create_app()
