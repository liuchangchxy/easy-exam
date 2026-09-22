"""Configuration module for FnExam.

Loads settings from environment variables with sensible defaults for fnOS deployment:
- SQLite database location
- Server host & port
- Ollama / LLM endpoint configurations
"""
from dataclasses import dataclass
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"


@dataclass
class Settings:
    """Application runtime settings."""
    db_path: str = os.environ.get("DB_PATH", str(DEFAULT_DATA_DIR / "fnexam.db"))
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", "3000"))
    llm_base_url: str = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_api_key: str = os.environ.get("LLM_API_KEY", "")
    llm_model: str = os.environ.get("LLM_MODEL", "qwen2.5:7b")


def get_settings() -> Settings:
    """Return fresh settings loaded from current environment."""
    return Settings(
        db_path=os.environ.get("DB_PATH", str(DEFAULT_DATA_DIR / "fnexam.db")),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "3000")),
        llm_base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        llm_model=os.environ.get("LLM_MODEL", "qwen2.5:7b"),
    )


# Module-level defaults
settings = get_settings()
DB_PATH = settings.db_path
HOST = settings.host
PORT = settings.port
LLM_BASE_URL = settings.llm_base_url
LLM_API_KEY = settings.llm_api_key
LLM_MODEL = settings.llm_model
