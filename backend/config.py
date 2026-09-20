"""Central configuration loaded from environment variables."""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    # Database-only tools and their tests remain usable before dependencies are
    # installed. Normal setup installs python-dotenv from requirements.txt.
    def load_dotenv() -> bool:
        return False


# Loading here makes CLI, FastAPI, and Streamlit runs behave consistently.
load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", OLLAMA_MODEL)
TAVILY_MAX_RESULTS = int(os.getenv("TAVILY_MAX_RESULTS", "5"))
