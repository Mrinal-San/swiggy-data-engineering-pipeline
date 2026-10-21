
import os
import re
import time
from functools import lru_cache
from dataclasses import dataclass

import boto3
from dotenv import load_dotenv
from google import genai
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

load_dotenv()

# Gemini configuration
@lru_cache(maxsize=1)
def get_genai_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)

# AWS Athena configuration
REGION = "ap-southeast-2"
DATABASE = "swiggy_gold"
WORKGROUP = "primary"
RESULTS_S3 = "s3://swiggy-pipeline-mrinal/athena-results/"
QUERY_TIMEOUT_SECONDS = 180
MAX_SQL_LENGTH = 20_000
MAX_QUERY_RESULT_ROWS = 5000

athena = boto3.client("athena", region_name=REGION)

# The AI analyst is restricted to Gold. The direct dashboard also reads these
# explicitly approved Silver views through the same validated Athena boundary.
GOLD_TABLES = {
    "gld_daily_sales": [
        "order_date", "restaurant_city", "cuisine", "currency",
        "total_orders", "total_items", "total_quantity", "total_sales", "average_order_value",
        "avg_delivery_time_min", "avg_customer_rating",
    ],
    "gld_restaurant_performance": [
        "restaurant_id", "restaurant_name", "restaurant_city",
        "cuisine", "restaurant_rating", "restaurant_rating_count",
        "restaurant_cost", "total_orders", "total_sales",
        "avg_order_customer_rating", "avg_delivery_time_min",
    ],
    "gld_city_performance": [
        "restaurant_city", "total_orders", "completed_orders",
        "non_completed_orders", "completion_rate_pct", "completed_sales",
        "completed_items", "completed_quantity", "completed_subtotal",
        "completed_discount", "completed_delivery_fee", "completed_gst",
        "average_order_value", "avg_customer_rating", "avg_delivery_time_min",
    ],
    "gld_cuisine_performance": [
        "cuisine", "total_orders", "completed_orders", "non_completed_orders",
        "completion_rate_pct", "completed_sales", "completed_items",
        "completed_quantity", "completed_subtotal", "completed_discount",
        "completed_delivery_fee", "completed_gst", "average_order_value",
        "avg_customer_rating", "avg_delivery_time_min",
    ],
    "gld_customer_analytics": [
        "user_id", "total_orders", "completed_orders", "cancelled_orders",
        "first_order_date", "last_order_date", "total_completed_spend",
        "avg_completed_order_value", "avg_customer_rating", "avg_delivery_time_min",
    ],
    "gld_customer_rating_analysis": [
        "restaurant_id", "restaurant_name", "restaurant_city", "cuisine",
        "total_orders", "completed_orders", "rated_orders", "unrated_orders",
        "avg_customer_rating", "rating_1_count", "rating_2_count",
        "rating_3_count", "rating_4_count", "rating_5_count",
        "avg_delivery_time_min", "first_order_date", "last_order_date",
    ],
    "gld_delivery_performance": [
        "restaurant_id", "restaurant_city", "cuisine", "currency",
        "total_orders", "completed_orders", "orders_with_delivery_time",
        "avg_delivery_time_min", "min_delivery_time_min", "max_delivery_time_min",
        "avg_customer_rating", "orders_with_customer_rating", "completion_rate_pct",
    ],
    "gld_order_status_analysis": [
        "order_status", "restaurant_city", "currency", "total_orders",
        "completed_orders", "cancelled_orders", "pending_orders",
        "total_recorded_sales", "completed_sales", "total_discount",
        "total_delivery_fee", "total_gst", "avg_customer_rating",
        "avg_delivery_time_min",
    ],
    "gld_top_restaurants": [
        "restaurant_id", "restaurant_name", "restaurant_city", "cuisine",
        "restaurant_rating", "restaurant_rating_count", "restaurant_cost",
        "total_orders", "completed_orders", "completed_order_sales",
        "avg_order_customer_rating", "avg_delivery_time_min", "sales_rank",
    ],
}
SILVER_TABLES = {
    "slv_orders": [
        "order_id", "order_date", "restaurant_id", "restaurant_city",
        "cuisine", "items_count", "sales_qty", "currency", "order_status",
        "customer_rating", "delivery_time_min",
    ],
    "slv_order_items": [
        "order_item_id", "order_id", "restaurant_id", "food_id",
        "price", "quantity", "line_amount",
    ],
    "slv_food": ["food_id", "food_name", "food_type"],
    "slv_restaurants": [
        "restaurant_id", "restaurant_name", "city", "rating",
        "rating_count", "cost", "cuisine",
    ],
}
ALLOWED_TABLES = {**GOLD_TABLES, **SILVER_TABLES}
TABLE_SCHEMAS = {
    **{table: "swiggy_gold" for table in GOLD_TABLES},
    **{table: "swiggy_silver" for table in SILVER_TABLES},
}


def generate_sql(question: str) -> str:
    """Generate SQL from the current approved Gold and sales-detail schemas."""
    schema_description = "\n".join(
        f"Table {table}: {', '.join(columns)}"
        for table, columns in ALLOWED_TABLES.items()
    )

    prompt = f"""
You generate Amazon Athena SQL for a Swiggy analytics project. Interpret common
paraphrases and typos by their intended business meaning, and prefer returning
a useful, bounded result over rejecting unfamiliar wording.

Available schema:
{schema_description}

Rules:
- Generate exactly one read-only SELECT query.
- Use only the listed tables and their listed columns.
- Fully qualify each table using its listed schema: Gold tables use
  "swiggy_gold"."table_name"; approved Silver detail tables use
  "swiggy_silver"."table_name".
- Never use INSERT, UPDATE, DELETE, MERGE, DROP, CREATE, ALTER,
  UNLOAD, or multiple statements.
- Never use SELECT *.
- Include LIMIT 100 unless the query already has a stricter limit.
- All sales and revenue questions must use order-item values, not the legacy
  sales_amount, subtotal, or completed-sales/order fields. The item value is
  COALESCE(line_amount, price * quantity, price, 0) from slv_order_items.
- For item/dish/food sales, join slv_order_items to slv_food on food_id (cast
  both IDs to varchar) and group by food_name. Sum the item value above.
- For cuisine sales, join slv_order_items to slv_orders on order_id (cast both
  IDs to varchar), group by cuisine, and sum the item value above. A request
  for dish sales and a request for cuisine sales are both answerable, but they
  are different groupings; do not substitute one for the other.
- For daily sales, use total_sales from gld_daily_sales. For restaurant sales,
  use total_sales from gld_restaurant_performance. Both now use order items.
- For total orders, use total_orders; do not filter on completed_orders.
- Treat item, dish, food, menu item, cuisine/category, restaurant, outlet,
  location/city, spend/sales/revenue, and time-period wording as synonyms only
  where the approved columns support that interpretation.
- Customer-level metrics in gld_customer_analytics are all-time aggregates.
- gld_delivery_performance is an all-time restaurant-level aggregate; weight
  average delivery time by orders_with_delivery_time when combining rows.
- gld_order_status_analysis contains one aggregate row per status, city, and currency.
- If the exact requested measure is unavailable, answer with the closest
  relevant database overview using available Gold data (for example, total
  item-based sales by date, city, or cuisine). Do not invent columns or facts.
- Return UNSUPPORTED only for requests with no meaningful relationship to the
  Swiggy database or for causal questions that these aggregate tables cannot
  establish.
- Questions asking for causes or causal relationships must be marked unsupported.
- Never infer causes, correlations, or financial profit from these tables.
- Otherwise return SQL only, with no Markdown fences or explanation.

User question: {question}
"""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from your .env file.")

    
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    response = get_genai_client(api_key).models.generate_content(
        model=model_name,
        contents=prompt,
    )


    sql = (response.text or "").strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql).strip()
    return sql


def validate_sql(sql: str) -> str:
    """Parse and allow only one SELECT over approved Gold tables."""
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL query is empty.")
    if len(sql) > MAX_SQL_LENGTH:
        raise ValueError(f"SQL exceeds the {MAX_SQL_LENGTH:,}-character limit.")
    try:
        statements = sqlglot.parse(sql, read="trino")
    except sqlglot.errors.ParseError as exc:
        raise ValueError("SQL could not be parsed as Athena-compatible SQL.") from exc
    if len(statements) != 1 or statements[0] is None:
        raise ValueError("Exactly one SQL statement is allowed.")

    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union)):
        raise ValueError("Only read-only SELECT queries are allowed.")
    if any(
        next(tree.find_all(kind), None) is not None
        for kind in (exp.Into, exp.Command, exp.Copy)
    ):
        raise ValueError("The query contains a prohibited SQL operation.")
    if next(tree.find_all(exp.Unnest), None) is not None:
        raise ValueError("Table-valued functions are not allowed.")
    for select in tree.find_all(exp.Select):
        if any(
            isinstance(item, exp.Star)
            or (isinstance(item, exp.Column) and item.is_star)
            for item in select.expressions
        ):
            raise ValueError("SELECT * is not allowed; name the required columns.")

    cte_names = {
        cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)
    }
    tables = list(tree.find_all(exp.Table))
    base_tables = [table for table in tables if table.name.lower() not in cte_names]
    if not base_tables:
        raise ValueError("The query must reference an approved Gold table.")
    for table in base_tables:
        if table.name.lower() not in ALLOWED_TABLES:
            raise ValueError(f"Table not allowed: {table.name}")
        if table.db.lower() != TABLE_SCHEMAS[table.name.lower()]:
            raise ValueError(f"Schema not allowed: {table.db or '(missing)'}")
        if table.catalog and table.catalog.lower() not in {"awsdatacatalog", "default"}:
            raise ValueError(f"Catalog not allowed: {table.catalog}")

    for scope in traverse_scope(tree):
        projection_aliases = {
            item.alias_or_name.lower()
            for item in scope.expression.expressions
            if isinstance(item, exp.Alias) and item.alias_or_name
        }
        for column in scope.columns:
            if column.is_star or column.name.lower() in projection_aliases:
                continue
            sources = list(scope.sources.items())
            if column.table:
                sources = [
                    (alias, source) for alias, source in sources
                    if alias.lower() == column.table.lower()
                ]
            available = set()
            for _, source in sources:
                if isinstance(source, exp.Table):
                    available.update(ALLOWED_TABLES.get(source.name.lower(), []))
                elif hasattr(source, "expression"):
                    available.update(
                        item.alias_or_name.lower()
                        for item in source.expression.expressions
                        if item.alias_or_name
                    )
            if available and column.name.lower() not in available:
                raise ValueError(f"Column not allowed or not found: {column.name}")

    limit = tree.args.get("limit")
    if limit is None:
        tree.limit(MAX_QUERY_RESULT_ROWS, copy=False)
    else:
        limit_expression = limit.expression
        if not isinstance(limit_expression, exp.Literal) or not limit_expression.is_int:
            raise ValueError("Query LIMIT must be an integer literal.")
        if int(limit_expression.this) > MAX_QUERY_RESULT_ROWS:
            tree.set(
                "limit",
                exp.Limit(expression=exp.Literal.number(MAX_QUERY_RESULT_ROWS)),
            )

    return tree.sql(dialect="trino")


@dataclass
class AthenaQueryReport:
    rows: list[dict]
    execution_seconds: float
    retrieval_seconds: float
    engine_execution_ms: int | None
    data_scanned_bytes: int | None
    query_execution_id: str


def execute_sql_report(sql: str, *, max_rows: int = 100) -> AthenaQueryReport:
    """Validate and execute one bounded query; return rows and Athena metrics."""
    if not isinstance(max_rows, int) or not 1 <= max_rows <= 5000:
        raise ValueError("max_rows must be an integer between 1 and 5000.")
    sql = validate_sql(sql)

    response = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": DATABASE},
        ResultConfiguration={"OutputLocation": RESULTS_S3},
        WorkGroup=WORKGROUP,
    )

    execution_id = response["QueryExecutionId"]
    submitted_at = time.monotonic()

    while True:
        status_response = athena.get_query_execution(
            QueryExecutionId=execution_id
        )
        status = status_response["QueryExecution"]["Status"]["State"]

        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        if time.monotonic() - submitted_at >= QUERY_TIMEOUT_SECONDS:
            athena.stop_query_execution(QueryExecutionId=execution_id)
            raise TimeoutError(
                f"Athena query exceeded {QUERY_TIMEOUT_SECONDS} seconds and was cancelled."
            )
        time.sleep(1)

    if status != "SUCCEEDED":
        reason = status_response["QueryExecution"]["Status"].get(
            "StateChangeReason", "Unknown Athena error"
        )
        raise RuntimeError(f"Athena query {status}: {reason}")

    completed_at = time.monotonic()
    paginator = athena.get_paginator("get_query_results")
    rows = []
    column_names = None

    for page in paginator.paginate(QueryExecutionId=execution_id):
        for row in page["ResultSet"]["Rows"]:
            values = [
                cell.get("VarCharValue")
                for cell in row.get("Data", [])
            ]

            if column_names is None:
                column_names = values
                continue

            values += [None] * (len(column_names) - len(values))
            rows.append(dict(zip(column_names, values)))

            if len(rows) >= max_rows:
                break
        if len(rows) >= max_rows:
            break

    retrieval_finished_at = time.monotonic()
    query_info = status_response["QueryExecution"]
    statistics = query_info.get("Statistics", {})
    return AthenaQueryReport(
        rows=rows,
        execution_seconds=completed_at - submitted_at,
        retrieval_seconds=retrieval_finished_at - completed_at,
        engine_execution_ms=statistics.get("EngineExecutionTimeInMillis"),
        data_scanned_bytes=statistics.get("DataScannedInBytes"),
        query_execution_id=execution_id,
    )


def execute_sql(sql: str, *, max_rows: int = 100) -> list[dict]:
    """Run a validated query and return rows as dictionaries."""
    return execute_sql_report(sql, max_rows=max_rows).rows


def ask(question: str) -> None:
    if not question.strip():
        print("Please enter a question.")
        return

    sql = generate_sql(question)
    sql = validate_sql(sql)

    print("\nGenerated SQL:\n")
    print(sql)

    results = execute_sql(sql)

    print("\nResults:\n")
    if not results:
        print("No rows returned.")
        return

    columns = list(results[0].keys())
    print(" | ".join(columns))
    print("-" * min(120, sum(len(c) for c in columns) + 3 * len(columns)))

    for row in results:
        print(" | ".join(str(row.get(column, "")) for column in columns))


if __name__ == "__main__":
    print("Swiggy Text-to-SQL Chatbot")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("Ask a question: ").strip()
        if question.lower() in {"exit", "quit"}:
            break

        try:
            ask(question)
        except Exception as exc:
            print(f"\nError: {exc}\n")
