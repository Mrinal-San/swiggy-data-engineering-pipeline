from flask import Blueprint, jsonify

from backend.routes.common import parse_limit
from backend.services import dashboard_service as service

restaurants_bp = Blueprint("restaurants", __name__)


@restaurants_bp.get("/restaurants/top")
def top_restaurants():
    return jsonify({"scope": "all_time", "data": service.top_restaurants(parse_limit())})


@restaurants_bp.get("/restaurants/summary")
def restaurant_summary():
    return jsonify({"scope": "all_time", "data": service.restaurant_summary()})
