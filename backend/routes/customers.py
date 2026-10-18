from flask import Blueprint, jsonify

from backend.services import dashboard_service as service

customers_bp = Blueprint("customers", __name__)


@customers_bp.get("/customers/analytics")
def customer_analytics():
    return jsonify(service.customer_analytics())
