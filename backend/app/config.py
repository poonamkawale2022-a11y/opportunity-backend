"""Central configuration. All secrets come from environment only."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # local .env (never committed)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_MODEL = "openai/gpt-4o-mini"
MODEL_FALLBACKS = [
    "openai/gpt-4o-mini",
    "meta-llama/llama-3.3-70b-instruct",
    "google/gemini-flash-1.5",
    "mistralai/mistral-small-3.1-24b-instruct",
]


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    SERPAPI_MONTHLY_BUDGET: int = _int("SERPAPI_MONTHLY_BUDGET", 250)
    SERPAPI_BASE_URL: str = os.getenv("SERPAPI_BASE_URL", "https://serpapi.com/search")
    SERPAPI_TIMEOUT_S: int = _int("SERPAPI_TIMEOUT_S", 25)

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "") or DEFAULT_MODEL
    OPENROUTER_SITE_URL: str = os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173")
    OPENROUTER_SITE_NAME: str = os.getenv("OPENROUTER_SITE_NAME", "Opportunity Intelligence Agent")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_TIMEOUT_S: int = _int("OPENROUTER_TIMEOUT_S", 60)

    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "opportunity_intel")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-only-change-me")

    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/integrations/gmail/callback")

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    DEMO_MODE: bool = _bool("DEMO_MODE", False)
    DATA_DIR: str = os.getenv("DATA_DIR", str(Path(__file__).resolve().parents[2] / "data"))
    MAX_TOOL_CALLS_PER_RUN: int = _int("MAX_TOOL_CALLS_PER_RUN", 12)
    MAX_AGENT_ITERATIONS: int = _int("MAX_AGENT_ITERATIONS", 6)
    OUTREACH_DAILY_LIMIT: int = _int("OUTREACH_DAILY_LIMIT", 20)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def model_candidates() -> list[str]:
    s = get_settings()
    cands = [s.OPENROUTER_MODEL] if s.OPENROUTER_MODEL else []
    for m in MODEL_FALLBACKS:
        if m not in cands:
            cands.append(m)
    return cands
