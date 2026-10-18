from flask import Blueprint, jsonify

from backend.services import dashboard_service as service

delivery_bp = Blueprint("delivery", __name__)


@delivery_bp.get("/delivery/analytics")
def delivery_analytics():
    # Gold delivery and status models do not include an order-date dimension.
    return jsonify(service.delivery_analytics())
