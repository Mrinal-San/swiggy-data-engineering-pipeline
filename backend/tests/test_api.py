import os

# Avoid credential and EC2 metadata lookups in local API tests.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

import pytest

from backend.app import create_app
from backend.routes import assistant, customers, dashboard, delivery, restaurants


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_invalid_date_range_is_rejected_without_query(client):
    response = client.get("/api/dashboard/summary?start_date=2026-02-02&end_date=2026-02-01")
    assert response.status_code == 400
    assert response.json["error"]["code"] == "INVALID_DATE_RANGE"


def test_invalid_limit_is_rejected(client):
    response = client.get("/api/restaurants/top?limit=999")
    assert response.status_code == 400
    assert response.json["error"]["code"] == "INVALID_LIMIT"


def test_dashboard_summary_uses_service(monkeypatch, client):
    monkeypatch.setattr(dashboard.service, "dashboard_summary", lambda start, end, currency: {
        "recorded_sales": 12, "total_orders": 2, "currency": currency,
    })
    response = client.get("/api/dashboard/summary?start_date=2026-01-01&end_date=2026-01-07")
    assert response.status_code == 200
    assert response.json["recorded_sales"] == 12


def test_restaurant_endpoint_is_mocked(monkeypatch, client):
    monkeypatch.setattr(restaurants.service, "top_restaurants", lambda limit: [{"restaurant_name": "Mock"}])
    response = client.get("/api/restaurants/top?limit=1")
    assert response.status_code == 200
    assert response.json["data"][0]["restaurant_name"] == "Mock"


def test_customer_and_delivery_analytics_are_mocked(monkeypatch, client):
    monkeypatch.setattr(customers.service, "customer_analytics", lambda: {"scope": "all_time", "summary": {}})
    monkeypatch.setattr(delivery.service, "delivery_analytics", lambda: {"scope": "all_time", "city_comparison": []})
    assert client.get("/api/customers/analytics").json["scope"] == "all_time"
    assert client.get("/api/delivery/analytics").json["city_comparison"] == []


def test_assistant_rejects_empty_question(client):
    response = client.post("/api/assistant/ask", json={"question": "  "})
    assert response.status_code == 400
    assert response.json["error"]["code"] == "INVALID_QUESTION"


def test_assistant_success_is_mocked(monkeypatch, client):
    monkeypatch.setattr(assistant, "ask_question", lambda question: {
        "status": "success", "answer": "Mock result", "columns": [], "rows": [], "sql": "SELECT 1",
    })
    response = client.post("/api/assistant/ask", json={"question": "test"})
    assert response.status_code == 200
    assert response.json["answer"] == "Mock result"
