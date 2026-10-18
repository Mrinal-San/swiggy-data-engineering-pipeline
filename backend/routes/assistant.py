from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.routes.common import APIError
from backend.services.assistant_service import ask_question

assistant_bp = Blueprint("assistant", __name__)


@assistant_bp.post("/assistant/ask")
def ask():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise APIError(400, "INVALID_JSON", "Send a JSON object with a question field.")
    question = body.get("question")
    if not isinstance(question, str) or not question.strip():
        raise APIError(400, "INVALID_QUESTION", "Enter a question to analyze.")
    if len(question) > current_app.config["MAX_ASSISTANT_QUESTION_LENGTH"]:
        raise APIError(400, "QUESTION_TOO_LONG", "The question is longer than the allowed limit.")
    try:
        result = ask_question(question.strip())
    except ValueError as exc:
        current_app.logger.info("Assistant request rejected (%s)", getattr(request, "request_id", "unknown"))
        raise APIError(422, "SQL_VALIDATION_FAILED", "The generated query did not pass the read-only data checks.") from exc
    except Exception as exc:
        current_app.logger.exception("Assistant query failed")
        raise APIError(502, "ASSISTANT_QUERY_FAILED", "The analysis could not be completed. Please try again.") from exc
    return jsonify(result)
