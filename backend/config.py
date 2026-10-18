from __future__ import annotations

import os


class Config:
    API_PREFIX = "/api"
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").rstrip("/")
    DASHBOARD_CACHE_SECONDS = int(os.getenv("DASHBOARD_CACHE_SECONDS", "300"))
    MAX_ASSISTANT_QUESTION_LENGTH = 1000
    MAX_API_ROWS = 500
    CURRENCY = "INR"
