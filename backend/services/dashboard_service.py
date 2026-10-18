from __future__ import annotations

from datetime import date, timedelta

from .athena_service import query_rows

DAILY = '"swiggy_gold"."gld_daily_sales"'
RESTAURANTS = '"swiggy_gold"."gld_restaurant_performance"'
CUSTOMERS = '"swiggy_gold"."gld_customer_analytics"'
RATINGS = '"swiggy_gold"."gld_customer_rating_analysis"'
DELIVERY = '"swiggy_gold"."gld_delivery_performance"'
ORDER_STATUS = '"swiggy_gold"."gld_order_status_analysis"'


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _date_filter(start: date, end: date) -> str:
    # Dates have already been parsed and bounded by the request validator.
    return f"order_date BETWEEN DATE '{start.isoformat()}' AND DATE '{end.isoformat()}'"


def available_date_range() -> dict:
    rows = query_rows(
        f"SELECT CAST(MIN(order_date) AS VARCHAR) AS first_date, "
        f"CAST(MAX(order_date) AS VARCHAR) AS last_date FROM {DAILY} WHERE currency = 'INR'",
        1,
    )
    return rows[0] if rows else {"first_date": None, "last_date": None}


def dashboard_summary(start: date, end: date, currency: str = "INR") -> dict:
    selected = _date_filter(start, end)
    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    previous = _date_filter(previous_start, previous_end)
    current_rows = query_rows(
        f"SELECT COALESCE(SUM(total_sales), 0) AS recorded_sales, "
        f"COALESCE(SUM(total_orders), 0) AS total_orders, "
        f"COALESCE(SUM(total_items), 0) AS items_sold FROM {DAILY} "
        f"WHERE currency = '{currency}' AND {selected}", 1,
    )
    previous_rows = query_rows(
        f"SELECT COALESCE(SUM(total_sales), 0) AS recorded_sales, "
        f"COALESCE(SUM(total_orders), 0) AS total_orders FROM {DAILY} "
        f"WHERE currency = '{currency}' AND {previous}", 1,
    )
    current = current_rows[0] if current_rows else {}
    prior = previous_rows[0] if previous_rows else {}
    sales, orders = _float(current.get("recorded_sales")), _float(current.get("total_orders"))
    prior_sales, prior_orders = _float(prior.get("recorded_sales")), _float(prior.get("total_orders"))
    return {
        "recorded_sales": sales,
        "total_orders": int(orders),
        "average_order_value": sales / orders if orders else 0,
        "items_sold": int(_float(current.get("items_sold"))),
        "previous_period": {
            "start_date": previous_start.isoformat(),
            "end_date": previous_end.isoformat(),
            "recorded_sales_change_pct": ((sales - prior_sales) / abs(prior_sales) * 100) if prior_sales else None,
            "total_orders_change_pct": ((orders - prior_orders) / abs(prior_orders) * 100) if prior_orders else None,
        },
        "date_range": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "currency": currency,
    }


def sales_trend(start: date, end: date, currency: str, granularity: str = "week") -> list[dict]:
    if granularity not in {"day", "week", "month"}:
        raise ValueError("granularity must be day, week, or month")
    date_unit = {"day": "day", "week": "week", "month": "month"}[granularity]
    return query_rows(
        f"SELECT CAST(DATE_TRUNC('{date_unit}', order_date) AS VARCHAR) AS period_start, "
        f"SUM(total_sales) AS recorded_sales FROM {DAILY} "
        f"WHERE currency = '{currency}' AND {_date_filter(start, end)} "
        f"GROUP BY DATE_TRUNC('{date_unit}', order_date) "
        f"ORDER BY DATE_TRUNC('{date_unit}', order_date) LIMIT 500", 500,
    )


def sales_by_dimension(start: date, end: date, currency: str, dimension: str, limit: int) -> list[dict]:
    # `dimension` is selected internally from this fixed allowlist.
    if dimension not in {"restaurant_city", "cuisine"}:
        raise ValueError("Unsupported breakdown dimension")
    alias = "city" if dimension == "restaurant_city" else "cuisine"
    return query_rows(
        f"SELECT TRIM({dimension}) AS {alias}, SUM(total_sales) AS recorded_sales "
        f"FROM {DAILY} WHERE currency = '{currency}' AND {_date_filter(start, end)} "
        f"AND {dimension} IS NOT NULL AND TRIM({dimension}) <> '' "
        f"GROUP BY TRIM({dimension}) ORDER BY recorded_sales DESC LIMIT {limit}", limit,
    )


def top_restaurants(limit: int = 10) -> list[dict]:
    return query_rows(
        f"SELECT restaurant_name, restaurant_city, cuisine, total_orders, completed_orders, "
        f"completed_order_sales, restaurant_rating, avg_delivery_time_min "
        f"FROM {RESTAURANTS} ORDER BY completed_order_sales DESC NULLS LAST LIMIT {limit}", limit,
    )


def restaurant_summary() -> dict:
    rows = query_rows(
        f"SELECT COUNT(DISTINCT restaurant_id) AS restaurant_count, "
        f"AVG(restaurant_rating) AS avg_listed_rating, "
        f"SUM(completed_order_sales) AS completed_order_sales FROM {RESTAURANTS}", 1,
    )
    return rows[0] if rows else {}


def customer_analytics() -> dict:
    customers = query_rows(
        f"SELECT COUNT(DISTINCT user_id) AS customer_count, "
        f"SUM(completed_orders) AS completed_orders, AVG(avg_customer_rating) AS avg_customer_rating "
        f"FROM {CUSTOMERS}", 1,
    )
    ratings = query_rows(
        f"SELECT SUM(rating_1_count) AS rating_1, SUM(rating_2_count) AS rating_2, "
        f"SUM(rating_3_count) AS rating_3, SUM(rating_4_count) AS rating_4, "
        f"SUM(rating_5_count) AS rating_5 FROM {RATINGS}", 1,
    )
    return {
        "scope": "all_time",
        "summary": customers[0] if customers else {},
        "rating_distribution": ratings[0] if ratings else {},
    }


def delivery_analytics() -> dict:
    summary = query_rows(
        f"SELECT SUM(completed_orders) AS completed_orders, "
        f"SUM(orders_with_delivery_time) AS orders_with_delivery_time, "
        f"SUM(avg_delivery_time_min * orders_with_delivery_time) / "
        f"NULLIF(SUM(orders_with_delivery_time), 0) AS weighted_avg_delivery_min "
        f"FROM {DELIVERY} WHERE currency = 'INR'", 1,
    )
    by_city = query_rows(
        f"SELECT restaurant_city AS city, "
        f"SUM(avg_delivery_time_min * orders_with_delivery_time) / "
        f"NULLIF(SUM(orders_with_delivery_time), 0) AS weighted_avg_delivery_min, "
        f"SUM(orders_with_delivery_time) AS orders_with_delivery_time FROM {DELIVERY} "
        "WHERE currency = 'INR' AND restaurant_city IS NOT NULL AND TRIM(restaurant_city) <> '' "
        "GROUP BY restaurant_city ORDER BY weighted_avg_delivery_min DESC LIMIT 10", 10,
    )
    statuses = query_rows(
        f"SELECT order_status, SUM(total_orders) AS total_orders FROM {ORDER_STATUS} "
        "WHERE currency = 'INR' GROUP BY order_status ORDER BY total_orders DESC", 50,
    )
    return {
        "scope": "all_time",
        "summary": summary[0] if summary else {},
        "city_comparison": by_city,
        "order_status": statuses,
    }
