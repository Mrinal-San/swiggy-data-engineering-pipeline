from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return str(value)


def rows_to_json(rows: list[dict]) -> list[dict]:
    return [json_value(row) for row in rows]


def chart_hint(question: str, columns: list[str], rows: list[dict]) -> dict | None:
    """Suggest a chart only when both column names and returned shape support it."""
    if not rows:
        return None
    normalized = {column.lower(): column for column in columns}
    measures = [
        column for column in columns
        if any(token in column.lower() for token in (
            "sales", "orders", "count", "quantity", "rating", "delivery_time", "spend", "revenue",
        ))
    ]
    dates = [column for column in columns if any(token in column.lower() for token in ("date", "week", "month"))]
    if dates and measures:
        measure = measures[0]
        return {"type": "line", "x": dates[0], "y": measure}
    status = normalized.get("order_status")
    orders = normalized.get("total_orders")
    if status and orders and len(rows) <= 6:
        return {"type": "donut", "name": status, "value": orders}
    category_markers = ("city", "cuisine", "restaurant", "category", "status")
    categories = [column for column in columns if any(token in column.lower() for token in category_markers)]
    if categories and measures and len(rows) <= 40:
        return {"type": "bar", "category": categories[0], "value": measures[0]}
    return None
