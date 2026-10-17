"""Small, controlled analytics workflow for the Swiggy Gold tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from time import perf_counter
from typing import Callable

import pandas as pd

from text_to_sql import AthenaQueryReport, execute_sql_report, generate_sql, validate_sql

MAX_AGENT_RESULT_ROWS = 100
MAX_CHART_ROWS = 20
MAX_QUESTION_LENGTH = 1000


def build_date_filter(start_date: date, end_date: date) -> str:
    if start_date > end_date:
        raise ValueError("Start date must be on or before end date.")
    return (
        f"order_date BETWEEN DATE '{start_date.isoformat()}' "
        f"AND DATE '{end_date.isoformat()}'"
    )


@dataclass
class AgentResult:
    question: str
    answer: str
    sql: str | None = None
    rows: list[dict] = field(default_factory=list)
    chart: dict | None = None
    source_tables: list[str] = field(default_factory=list)
    gemini_seconds: float | None = None
    query_report: AthenaQueryReport | None = None
    error: str | None = None
    limitations: list[str] = field(default_factory=list)


def _sources(sql: str) -> list[str]:
    import sqlglot
    from sqlglot import exp

    tree = sqlglot.parse_one(sql, read="trino")
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    return list(dict.fromkeys(
        f"{table.db}.{table.name}"
        for table in tree.find_all(exp.Table)
        if table.name.lower() not in cte_names
    ))


def prepare_chart(question: str, rows: list[dict]) -> dict | None:
    """Choose a predefined chart using only validated columns in returned rows."""
    frame = pd.DataFrame(rows)
    if frame.empty or len(frame) < 2:
        return None

    numeric = [
        col for col in frame.columns
        if pd.api.types.is_numeric_dtype(pd.to_numeric(frame[col], errors="coerce"))
        and pd.to_numeric(frame[col], errors="coerce").notna().any()
    ]
    if not numeric:
        return None
    normalized = {str(col).lower(): col for col in frame.columns}
    date_col = next(
        (normalized[name] for name in normalized
         if any(tag in name for tag in ("date", "week", "month", "day"))),
        None,
    )
    question_lc = question.lower()
    if date_col is not None and any(
        word in question_lc for word in ("trend", "over time", "daily", "weekly", "monthly")
    ):
        x = pd.to_datetime(frame[date_col], errors="coerce")
        y = numeric[0]
        chart_data = pd.DataFrame({"x": x, "y": pd.to_numeric(frame[y], errors="coerce")})
        chart_data = chart_data.dropna().sort_values("x").head(MAX_CHART_ROWS)
        if not chart_data.empty:
            return {
                "kind": "line", "x": "x", "y": "y",
                "x_label": str(date_col), "y_label": str(y),
                "data": chart_data.to_dict("records"),
            }

    dimension = next(
        (col for col in frame.columns if col not in numeric and frame[col].nunique(dropna=True) > 1),
        None,
    )
    if dimension is not None:
        chart_data = pd.DataFrame({
            "x": frame[dimension].astype("string"),
            "y": pd.to_numeric(frame[numeric[0]], errors="coerce"),
        }).dropna()
        chart_data = chart_data.sort_values("y", ascending=False).head(MAX_CHART_ROWS)
        if not chart_data.empty:
            return {
                "kind": "bar", "x": "x", "y": "y",
                "x_label": str(dimension), "y_label": str(numeric[0]),
                "data": chart_data.to_dict("records"),
            }
    return None


def summarize(question: str, rows: list[dict]) -> str:
    if not rows:
        return "Athena returned no rows for this question. Try a different date range or a more specific question."

    frame = pd.DataFrame(rows)
    numeric_columns = [
        col for col in frame.columns
        if pd.to_numeric(frame[col], errors="coerce").notna().any()
    ]
    if len(rows) == 1:
        facts = []
        for col, value in rows[0].items():
            if value is None or pd.isna(value):
                continue
            facts.append(f"{col.replace('_', ' ')}: {value}")
        if facts:
            return "Athena returned one result: " + "; ".join(facts[:6]) + "."
    if numeric_columns and len(frame) > 1:
        col = numeric_columns[0]
        values = pd.to_numeric(frame[col], errors="coerce").dropna()
        if not values.empty:
            return (
                f"Athena returned {len(frame)} rows. Across the returned results, "
                f"{col.replace('_', ' ')} ranges from {values.min():,.2f} "
                f"to {values.max():,.2f} (sum {values.sum():,.2f})."
            )
    return f"Athena returned {len(rows)} rows for this question. Review the result table for details."


def analyze_question(
    question: str,
    *,
    sql_generator: Callable[[str], str] = generate_sql,
    query_executor: Callable[..., AthenaQueryReport] = execute_sql_report,
    on_progress: Callable[[str], None] | None = None,
) -> AgentResult:
    """Generate once, validate, execute once, and summarize returned evidence."""
    clean_question = question.strip()
    if not clean_question:
        return AgentResult(question=question, answer="Enter a question to begin.", error="empty_question")
    if len(clean_question) > MAX_QUESTION_LENGTH:
        return AgentResult(
            question=question,
            answer=f"Keep the question under {MAX_QUESTION_LENGTH:,} characters.",
            error="question_too_long",
        )

    gemini_seconds = None
    try:
        if on_progress:
            on_progress("Identify approved Gold tables")
        started = perf_counter()
        if on_progress:
            on_progress("Draft one SQL query with Gemini")
        generated = sql_generator(clean_question)
        if isinstance(generated, tuple) and len(generated) == 2:
            draft, gemini_seconds = generated
        else:
            draft = generated
            gemini_seconds = perf_counter() - started
        if not isinstance(draft, str):
            raise ValueError("Gemini did not return a SQL string.")
        if draft.strip().upper().startswith("UNSUPPORTED:"):
            return AgentResult(
                question=clean_question,
                answer=(
                    "The approved Gold tables do not contain enough information "
                    "to answer that question. Ask about their available sales, "
                    "order, dish, restaurant, city, cuisine, rating, or delivery metrics."
                ),
                gemini_seconds=gemini_seconds,
                error="unsupported_question",
                limitations=["The request is outside the available Gold schema."],
            )
        if on_progress:
            on_progress("Parse and validate read-only SQL")
        sql = validate_sql(draft)
        if on_progress:
            on_progress("Execute the bounded query in Athena")
        report = query_executor(sql, max_rows=MAX_AGENT_RESULT_ROWS)
        if on_progress:
            on_progress("Summarize results and prepare a safe chart")
        answer = summarize(clean_question, report.rows)
        limitations = []
        if not report.rows:
            limitations.append("No matching rows were returned; no conclusion can be drawn.")
        if report.rows and len(report.rows) >= MAX_AGENT_RESULT_ROWS:
            limitations.append(f"Results are capped at {MAX_AGENT_RESULT_ROWS} rows.")
        return AgentResult(
            question=clean_question,
            answer=answer,
            sql=sql,
            rows=report.rows,
            chart=prepare_chart(clean_question, report.rows),
            source_tables=_sources(sql),
            gemini_seconds=gemini_seconds,
            query_report=report,
            limitations=limitations,
        )
    except Exception as exc:
        error_text = str(exc).lower()
        if "gld_food_performance" in error_text and any(
            marker in error_text
            for marker in ("table_not_found", "table not found", "does not exist")
        ):
            answer = (
                "Dish-level analysis is ready in the app, but the Gold table has "
                "not been built in Athena yet. Run dbt for gld_food_performance, "
                "then refresh the app."
            )
        elif isinstance(exc, ValueError):
            answer = (
                "That question could not be answered from the approved Gold "
                "tables and columns. Try asking about sales, orders, restaurants, "
                "dishes, cities, cuisine, ratings, or delivery metrics."
            )
        else:
            answer = "I could not answer this using the approved Gold data. Check the question or query setup."
        return AgentResult(
            question=clean_question,
            answer=answer,
            error=str(exc),
            gemini_seconds=gemini_seconds,
        )
