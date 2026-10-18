from flask import Blueprint, jsonify, request

from backend.routes.common import APIError, date_range_args, parse_limit
from backend.services import dashboard_service as service
from backend.services.athena_service import clear_query_cache

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/dashboard/date-range")
def date_range():
    return jsonify(service.available_date_range())


@dashboard_bp.get("/dashboard/summary")
def summary():
    start, end, currency = date_range_args()
    return jsonify(service.dashboard_summary(start, end, currency))


@dashboard_bp.get("/dashboard/sales-trend")
def sales_trend():
    start, end, currency = date_range_args()
    granularity = request.args.get("granularity", "week")
    if granularity not in {"day", "week", "month"}:
        raise APIError(400, "INVALID_GRANULARITY", "granularity must be day, week, or month.")
    return jsonify({"granularity": granularity, "data": service.sales_trend(start, end, currency, granularity)})


@dashboard_bp.get("/dashboard/cities")
def cities():
    start, end, currency = date_range_args()
    return jsonify({"data": service.sales_by_dimension(start, end, currency, "restaurant_city", parse_limit())})


@dashboard_bp.get("/dashboard/cuisines")
def cuisines():
    start, end, currency = date_range_args()
    return jsonify({"data": service.sales_by_dimension(start, end, currency, "cuisine", parse_limit())})


@dashboard_bp.post("/dashboard/refresh")
def refresh():
    clear_query_cache()
    return jsonify({"status": "refreshed"})
