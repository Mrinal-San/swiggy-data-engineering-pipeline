
import os
import re
import time
from functools import lru_cache

import boto3
from dotenv import load_dotenv
from google import genai

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

athena = boto3.client("athena", region_name=REGION)

# Only these Gold tables may be queried.
ALLOWED_TABLES = {
    "gld_daily_sales": [
        "order_date", "restaurant_city", "cuisine", "currency",
        "total_orders", "total_items", "total_quantity",
        "total_subtotal", "total_discount", "total_delivery_fee",
        "total_gst", "total_sales", "average_order_value",
        "avg_delivery_time_min", "avg_customer_rating",
    ],
    "gld_restaurant_performance": [
        "restaurant_id", "restaurant_name", "restaurant_city",
        "cuisine", "restaurant_rating", "restaurant_rating_count",
        "restaurant_cost", "total_orders", "completed_orders",
        "total_recorded_sales", "completed_order_sales",
        "avg_order_customer_rating", "avg_delivery_time_min",
    ],
}


def generate_sql(question: str) -> str:
    """Generate SQL using the actual Gold table schemas."""
    schema_description = "\n".join(
        f"Table {table}: {', '.join(columns)}"
        for table, columns in ALLOWED_TABLES.items()
    )

    prompt = f"""
You generate Amazon Athena SQL for a Swiggy analytics project.

Available schema:
{schema_description}

Rules:
- Generate exactly one read-only SELECT query.
- Use only the two listed tables and their listed columns.
- Fully qualify tables as "swiggy_gold"."table_name".
- Never use INSERT, UPDATE, DELETE, MERGE, DROP, CREATE, ALTER,
  UNLOAD, or multiple statements.
- Never use SELECT *.
- Include LIMIT 100 unless the query already has a stricter limit.
- For highest completed restaurant sales, use completed_order_sales.
- For daily sales, use total_sales from gld_daily_sales.
- Return SQL only, with no Markdown fences or explanation.

User question: {question}
"""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from your .env file.")

    response = get_genai_client(api_key).models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
    )

    sql = (response.text or "").strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql).strip()
    return sql


def validate_sql(sql: str) -> str:
    """Apply basic read-only and table allowlist checks."""
    cleaned = sql.strip().rstrip(";")

    if not cleaned:
        raise ValueError("Gemini returned an empty SQL query.")

    # Permit one statement only.
    if ";" in cleaned:
        raise ValueError("Multiple SQL statements are not allowed.")

    # Only SELECT queries are permitted in this first version.
    if not re.match(r"(?is)^SELECT\b", cleaned):
        raise ValueError("Only SELECT queries are allowed in this version.")

    # Block comments and suspicious SQL tokens.
    if re.search(r"(?is)(--|/\*|\*/)", cleaned):
        raise ValueError("SQL comments are not allowed.")

    forbidden = (
        r"\b(insert|update|delete|merge|drop|create|alter|"
        r"unload|grant|revoke|call|execute|prepare|deallocate)\b"
    )
    if re.search(forbidden, cleaned, flags=re.IGNORECASE):
        raise ValueError("The query contains a prohibited SQL operation.")

    # Require at least one approved, fully-qualified Gold table.
    tables_used = re.findall(
        r'(?i)"swiggy_gold"\s*\.\s*'
        r'"(gld_daily_sales|gld_restaurant_performance)"',
        cleaned,
    )
    if not tables_used:
        raise ValueError("The query must reference an approved Gold table.")

    # Reject other table names in FROM or JOIN clauses.
    table_refs = re.findall(
        r'(?i)\b(?:from|join)\s+'
        r'(?:"?([a-zA-Z_][\w]*)"?\s*\.\s*)?'
        r'"?([a-zA-Z_][\w]*)"?',
        cleaned,
    )

    for schema, table in table_refs:
        if schema and schema.lower() != DATABASE.lower():
            raise ValueError(f"Schema not allowed: {schema}")
        if table.lower() not in ALLOWED_TABLES:
            raise ValueError(f"Table not allowed: {table}")

    return cleaned


def execute_sql(sql: str, *, max_rows: int = 100) -> list[dict]:
    """Run a validated query and return rows as dictionaries."""
    if not isinstance(max_rows, int) or not 1 <= max_rows <= 5000:
        raise ValueError("max_rows must be an integer between 1 and 5000.")

    response = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": DATABASE},
        ResultConfiguration={"OutputLocation": RESULTS_S3},
        WorkGroup=WORKGROUP,
    )

    execution_id = response["QueryExecutionId"]

    while True:
        status_response = athena.get_query_execution(
            QueryExecutionId=execution_id
        )
        status = status_response["QueryExecution"]["Status"]["State"]

        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break

        time.sleep(1)

    if status != "SUCCEEDED":
        reason = status_response["QueryExecution"]["Status"].get(
            "StateChangeReason", "Unknown Athena error"
        )
        raise RuntimeError(f"Athena query {status}: {reason}")

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
                return rows

    return rows


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
