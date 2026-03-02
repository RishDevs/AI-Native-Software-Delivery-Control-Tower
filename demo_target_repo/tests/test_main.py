"""Unit tests for the demo target inventory service."""

import pytest
from fastapi.testclient import TestClient

from app.main import (
    app,
    calculate_discount,
    calculate_total_value,
    search_products,
    products_db,
)


@pytest.fixture(autouse=True)
def clear_db():
    """Clear the in-memory database before each test."""
    products_db.clear()
    yield
    products_db.clear()


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_product():
    """Create a sample product dict."""
    return {
        "name": "Test Widget",
        "price": 29.99,
        "quantity": 100,
        "category": "widgets",
        "description": "A test widget",
    }


# ── Health Check Tests ────────────────────────────────────────

class TestHealthCheck:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_health_includes_product_count(self, client):
        response = client.get("/health")
        assert response.json()["product_count"] == 0


# ── Product CRUD Tests ────────────────────────────────────────

class TestCreateProduct:
    def test_create_product(self, client, sample_product):
        response = client.post("/products", json=sample_product)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Widget"
        assert data["price"] == 29.99
        assert "id" in data

    def test_create_product_missing_name(self, client):
        response = client.post("/products", json={"price": 10, "quantity": 5})
        assert response.status_code == 422

    def test_create_product_negative_price(self, client):
        response = client.post(
            "/products",
            json={"name": "Bad", "price": -10, "quantity": 5},
        )
        assert response.status_code == 422


class TestListProducts:
    def test_list_empty(self, client):
        response = client.get("/products")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_products(self, client, sample_product):
        client.post("/products", json=sample_product)
        response = client.get("/products")
        assert len(response.json()) == 1

    def test_filter_by_category(self, client, sample_product):
        client.post("/products", json=sample_product)
        client.post("/products", json={**sample_product, "category": "other"})

        response = client.get("/products?category=widgets")
        assert len(response.json()) == 1


class TestGetProduct:
    def test_get_existing_product(self, client, sample_product):
        create_resp = client.post("/products", json=sample_product)
        product_id = create_resp.json()["id"]

        response = client.get(f"/products/{product_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Widget"

    def test_get_nonexistent_product(self, client):
        response = client.get("/products/99999")
        assert response.status_code == 404


class TestUpdateProduct:
    def test_update_name(self, client, sample_product):
        create_resp = client.post("/products", json=sample_product)
        product_id = create_resp.json()["id"]

        response = client.put(
            f"/products/{product_id}",
            json={"name": "Updated Widget"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Widget"

    def test_update_nonexistent(self, client):
        response = client.put("/products/99999", json={"name": "X"})
        assert response.status_code == 404


class TestDeleteProduct:
    def test_delete_product(self, client, sample_product):
        create_resp = client.post("/products", json=sample_product)
        product_id = create_resp.json()["id"]

        response = client.delete(f"/products/{product_id}")
        assert response.status_code == 200

        # Verify deleted
        get_resp = client.get(f"/products/{product_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent(self, client):
        response = client.delete("/products/99999")
        assert response.status_code == 404


# ── Helper Function Tests ─────────────────────────────────────

class TestCalculateDiscount:
    def test_basic_discount(self):
        assert calculate_discount(100, 10) == 90.0

    def test_zero_discount(self):
        assert calculate_discount(100, 0) == 100.0

    def test_full_discount(self):
        assert calculate_discount(100, 100) == 0.0

    # These tests document known bugs:
    def test_negative_discount_bug(self):
        """BUG: Negative discount should be rejected but isn't."""
        # This gives 110.0 — incorrect behavior
        result = calculate_discount(100, -10)
        assert result == 110.0  # Bug: should raise ValueError


class TestCalculateTotalValue:
    def test_basic_total(self):
        products = [
            {"price": 10, "quantity": 5},
            {"price": 20, "quantity": 3},
        ]
        assert calculate_total_value(products) == 110.0

    def test_empty_inventory(self):
        assert calculate_total_value([]) == 0


class TestSearchProducts:
    def test_basic_search(self):
        products = {
            "1": {"name": "Widget A", "id": "1"},
            "2": {"name": "Gadget B", "id": "2"},
        }
        results = search_products("Widget", products)
        assert len(results) == 1

    def test_case_sensitivity_bug(self):
        """BUG: Search is case-sensitive."""
        products = {
            "1": {"name": "Widget A", "id": "1"},
        }
        # Should find "Widget" when searching "widget" but doesn't
        results = search_products("widget", products)
        assert len(results) == 0  # Bug: should be 1
