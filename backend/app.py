from __future__ import annotations

import logging
import os
import uuid

from flask import Flask, g, request

from backend.config import Config
from backend.routes.assistant import assistant_bp
from backend.routes.common import APIError, error_response
from backend.routes.customers import customers_bp
from backend.routes.dashboard import dashboard_bp
from backend.routes.delivery import delivery_bp
from backend.routes.health import health_bp
from backend.routes.restaurants import restaurants_bp


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["SUPPORTED_CURRENCIES"] = {"INR"}
    if test_config:
        app.config.update(test_config)

    app.register_blueprint(health_bp, url_prefix=app.config["API_PREFIX"])
    app.register_blueprint(dashboard_bp, url_prefix=app.config["API_PREFIX"])
    app.register_blueprint(restaurants_bp, url_prefix=app.config["API_PREFIX"])
    app.register_blueprint(customers_bp, url_prefix=app.config["API_PREFIX"])
    app.register_blueprint(delivery_bp, url_prefix=app.config["API_PREFIX"])
    app.register_blueprint(assistant_bp, url_prefix=app.config["API_PREFIX"])

    @app.before_request
    def attach_request_id() -> None:
        g.request_id = str(uuid.uuid4())

    @app.after_request
    def add_security_and_cors_headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        origin = request.headers.get("Origin")
        allowed_origin = app.config["FRONTEND_ORIGIN"]
        if origin == allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return error_response(error.status_code, error.code, error.message)

    @app.errorhandler(404)
    def handle_not_found(_error):
        if request.path.startswith(app.config["API_PREFIX"]):
            return error_response(404, "NOT_FOUND", "The requested API route was not found.")
        return error_response(404, "NOT_FOUND", "The requested resource was not found.")

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.exception("Unhandled API exception (%s)", g.request_id)
        return error_response(500, "INTERNAL_ERROR", "The request could not be completed.")

    if not app.testing:
        logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"},
    )
