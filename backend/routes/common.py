from __future__ import annotations

from datetime import date

from flask import current_app, g, jsonify, request


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str):
    return jsonify({
        "error": {"code": code, "message": message},
        "request_id": getattr(g, "request_id", None),
    }), status


def parse_date_arg(name: str, required: bool = True) -> date | None:
    value = request.args.get(name)
    if not value and not required:
        return None
    try:
        parsed = date.fromisoformat(value or "")
    except ValueError as exc:
        raise APIError(400, "INVALID_DATE", f"{name} must use YYYY-MM-DD format.") from exc
    if parsed.isoformat() != value:
        raise APIError(400, "INVALID_DATE", f"{name} must use YYYY-MM-DD format.")
    return parsed


def date_range_args() -> tuple[date, date, str]:
    start = parse_date_arg("start_date")
    end = parse_date_arg("end_date")
    if start is None or end is None:
        raise APIError(400, "INVALID_DATE_RANGE", "Both start_date and end_date are required.")
    if start > end:
        raise APIError(400, "INVALID_DATE_RANGE", "start_date must be on or before end_date.")
    currency = request.args.get("currency", "INR").upper()
    supported = current_app.config["SUPPORTED_CURRENCIES"]
    if currency not in supported:
        raise APIError(400, "UNSUPPORTED_CURRENCY", f"Supported currencies: {', '.join(sorted(supported))}.")
    return start, end, currency


def parse_limit(default: int = 10, maximum: int = 50) -> int:
    raw = request.args.get("limit", str(default))
    try:
        limit = int(raw)
    except ValueError as exc:
        raise APIError(400, "INVALID_LIMIT", "limit must be an integer.") from exc
    if not 1 <= limit <= maximum:
        raise APIError(400, "INVALID_LIMIT", f"limit must be between 1 and {maximum}.")
    return limit
