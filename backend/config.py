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


def get_data_dir() -> Path:
    """Return data directory, prioritizing DATA_DIR environment variable."""
    custom_dir = os.environ.get("DATA_DIR")
    if custom_dir:
        return Path(custom_dir)
    return BASE_DIR / "data"


DEFAULT_DATA_DIR = get_data_dir()


@dataclass
class Settings:
    """Application runtime settings."""
    db_path: str = ""
    host: str = "0.0.0.0"
    port: int = 3000
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen2.5:7b"

    def __post_init__(self):
        if not self.db_path:
            self.db_path = os.environ.get("DB_PATH") or str(get_data_dir() / "fnexam.db")
        if not os.environ.get("HOST") and self.host == "0.0.0.0":
            self.host = os.environ.get("HOST", "0.0.0.0")


def get_settings() -> Settings:
    """Return fresh settings loaded from current environment."""
    data_dir = get_data_dir()
    # Seamless upgrade: use existing fnexam.db if present and easyexam.db does not exist yet
    legacy_db = data_dir / "fnexam.db"
    new_db = data_dir / "easyexam.db"
    default_db = str(legacy_db if legacy_db.exists() and not new_db.exists() else new_db)
    return Settings(
        db_path=os.environ.get("DB_PATH") or default_db,
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
