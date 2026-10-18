from __future__ import annotations

import re

from backend.services.athena_service import execute_sql, generate_sql, validate_sql
from backend.services.response_formatter import chart_hint, rows_to_json


def _tables(sql: str) -> list[str]:
    names = re.findall(
        r'(?i)"?swiggy_gold"?\s*\.\s*"?(gld_[A-Za-z0-9_]+)', sql
    )
    return list(dict.fromkeys(f"swiggy_gold.{name}" for name in names))


def ask_question(question: str) -> dict:
    draft = generate_sql(question)
    if draft.strip().upper().startswith("UNSUPPORTED:"):
        reason = draft.split(":", 1)[1].strip()
        return {
            "status": "unsupported",
            "answer": reason or "This question is not supported by the available Gold data.",
            "columns": [], "rows": [], "row_count": 0, "sql": None,
            "sources": [], "chart": None,
        }
    validated_sql = validate_sql(draft)
    rows = rows_to_json(execute_sql(validated_sql, max_rows=100))
    columns = list(rows[0].keys()) if rows else []
    return {
        "status": "success",
        "answer": f"The query returned {len(rows):,} row(s).",
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "sql": validated_sql,
        "sources": _tables(validated_sql),
        "chart": chart_hint(question, columns, rows),
    }
