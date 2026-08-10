from __future__ import annotations

import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'system_knowledge_designer.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "project_data")).resolve()
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")
    CODEX_CONTROL_TOKEN = os.environ.get("CODEX_CONTROL_TOKEN", "")
    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    WTF_CSRF_TIME_LIMIT = None
