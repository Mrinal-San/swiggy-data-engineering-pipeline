import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import text_to_sql
from analytics_agent import (
    analyze_question,
    build_date_filter,
    prepare_chart,
    summarize,
)
from text_to_sql import AthenaQueryReport, validate_sql


DAILY = '"swiggy_gold"."gld_daily_sales"'


class SQLValidationTests(unittest.TestCase):
    def test_accepts_approved_gold_table_and_cte(self):
        query = (
            f"WITH totals AS (SELECT SUM(total_sales) AS sales FROM {DAILY}) "
            "SELECT sales FROM totals"
        )
        self.assertIn("gld_daily_sales", validate_sql(query))

    def test_rejects_unapproved_table_in_nested_query(self):
        query = f"SELECT x FROM (SELECT name AS x FROM {DAILY}) q JOIN private.users u ON true"
        with self.assertRaises(ValueError):
            validate_sql(query)

    def test_rejects_wrong_schema_and_multiple_statements(self):
        with self.assertRaises(ValueError):
            validate_sql('SELECT total_sales FROM "other"."gld_daily_sales"')
        with self.assertRaises(ValueError):
            validate_sql(f"SELECT total_sales FROM {DAILY}; SELECT 1")

    def test_rejects_unknown_columns_and_star_projection(self):
        with self.assertRaises(ValueError):
            validate_sql(f"SELECT payroll FROM {DAILY}")
        with self.assertRaises(ValueError):
            validate_sql(f"SELECT * FROM {DAILY}")

    def test_applies_a_bounded_result_limit(self):
        self.assertIn("LIMIT 5000", validate_sql(f"SELECT total_sales FROM {DAILY}"))

    def test_approves_food_performance_table_and_schema(self):
        query = (
            'SELECT food_name, SUM(total_quantity) AS units_sold '
            'FROM "swiggy_gold"."gld_food_performance" '
            'GROUP BY food_name ORDER BY units_sold DESC LIMIT 1'
        )
        self.assertIn("gld_food_performance", validate_sql(query))

    def test_athena_boundary_validates_before_starting_query(self):
        original = text_to_sql.athena
        mock_athena = Mock()
        text_to_sql.athena = mock_athena
        try:
            with self.assertRaises(ValueError):
                text_to_sql.execute_sql("SELECT secret FROM private.users")
            mock_athena.start_query_execution.assert_not_called()
        finally:
            text_to_sql.athena = original


class AgentTests(unittest.TestCase):
    def report(self, rows):
        return AthenaQueryReport(
            rows=rows,
            execution_seconds=0.25,
            retrieval_seconds=0.04,
            engine_execution_ms=200,
            data_scanned_bytes=1024,
            query_execution_id="test-query",
        )

    def test_empty_question_and_empty_results(self):
        self.assertEqual(analyze_question(" ").error, "empty_question")
        self.assertIn("no rows", summarize("show sales", []).lower())

    def test_null_values_are_omitted_and_chart_uses_valid_columns(self):
        rows = [
            {"order_date": "2026-01-01", "total_sales": "10", "note": None},
            {"order_date": "2026-01-08", "total_sales": "20", "note": None},
        ]
        chart = prepare_chart("show weekly sales trend", rows)
        self.assertEqual(chart["kind"], "line")
        self.assertEqual(len(chart["data"]), 2)
        self.assertIn("ranges from", summarize("sales", rows))

    def test_chart_row_limit_and_no_numeric_chart(self):
        rows = [{"city": f"city-{i}", "sales": str(i)} for i in range(30)]
        self.assertLessEqual(len(prepare_chart("compare sales by city", rows)["data"]), 20)
        self.assertIsNone(prepare_chart("list cities", [{"city": "A"}, {"city": "B"}]))

    def test_date_filter_and_invalid_range(self):
        self.assertEqual(
            build_date_filter(date(2026, 1, 1), date(2026, 1, 7)),
            "order_date BETWEEN DATE '2026-01-01' AND DATE '2026-01-07'",
        )
        with self.assertRaises(ValueError):
            build_date_filter(date(2026, 1, 7), date(2026, 1, 1))

    def test_query_failure_is_returned_without_another_gemini_call(self):
        generator = Mock(return_value=f"SELECT total_sales FROM {DAILY}")
        executor = Mock(side_effect=RuntimeError("Athena unavailable"))
        result = analyze_question(
            "show sales", sql_generator=generator, query_executor=executor
        )
        self.assertIsNotNone(result.error)
        self.assertEqual(generator.call_count, 1)
        self.assertEqual(executor.call_count, 1)

    def test_unsupported_sql_is_rejected_before_athena(self):
        executor = Mock()
        result = analyze_question(
            "show payroll", sql_generator=lambda _: "SELECT x FROM private.payroll",
            query_executor=executor,
        )
        self.assertIsNotNone(result.error)
        executor.assert_not_called()

    def test_unsupported_question_response_does_not_execute_athena(self):
        executor = Mock()
        result = analyze_question(
            "show payroll", sql_generator=lambda _: "UNSUPPORTED: no payroll field",
            query_executor=executor,
        )
        self.assertEqual(result.error, "unsupported_question")
        self.assertIn("do not contain enough information", result.answer)
        executor.assert_not_called()

    def test_most_selling_dish_uses_units_sold_evidence(self):
        query = (
            'SELECT food_name, SUM(total_quantity) AS units_sold '
            'FROM "swiggy_gold"."gld_food_performance" '
            'GROUP BY food_name ORDER BY units_sold DESC LIMIT 1'
        )
        report = self.report([{"food_name": "Paneer Wrap", "units_sold": "42"}])
        result = analyze_question(
            "most selling dish",
            sql_generator=lambda _: query,
            query_executor=Mock(return_value=report),
        )
        self.assertIn("Paneer Wrap", result.answer)
        self.assertIn("gld_food_performance", result.source_tables[0])

    def test_missing_food_gold_table_gives_dbt_next_step(self):
        query = (
            'SELECT food_name, SUM(total_quantity) AS units_sold '
            'FROM "swiggy_gold"."gld_food_performance" '
            'GROUP BY food_name ORDER BY units_sold DESC LIMIT 1'
        )
        result = analyze_question(
            "most selling dish",
            sql_generator=lambda _: query,
            query_executor=Mock(
                side_effect=RuntimeError(
                    "TABLE_NOT_FOUND: swiggy_gold.gld_food_performance"
                )
            ),
        )
        self.assertIn("Run dbt", result.answer)


if __name__ == "__main__":
    unittest.main()
