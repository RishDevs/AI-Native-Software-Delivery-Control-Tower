"""Demo Target Repository — A FastAPI microservice with intentional bugs for benchmarking.

This service simulates an "inventory management" microservice with:
- CRUD operations for products
- Intentional bugs for the AI agent to fix
- Unit tests
- Prometheus metrics endpoint
- Health check
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

# ── App Setup ─────────────────────────────────────────────────
app = FastAPI(
    title="Inventory Service",
    description="Demo microservice for AI-native delivery pipeline benchmarking",
    version="0.1.0",
)

# ── Prometheus Metrics ────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)
ERROR_COUNT = Counter(
    "http_errors_total",
    "Total HTTP errors",
    ["method", "endpoint", "error_type"],
)

# ── In-Memory Database ────────────────────────────────────────
products_db: dict[str, dict[str, Any]] = {}
_next_id = 1


# ── Models ────────────────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    quantity: int = Field(ge=0)
    category: str = Field(default="general")
    description: str = Field(default="")


class ProductUpdate(BaseModel):
    name: str | None = None
    price: float | None = None
    quantity: int | None = None
    category: str | None = None
    description: str | None = None


class ProductResponse(BaseModel):
    id: str
    name: str
    price: float
    quantity: int
    category: str
    description: str
    created_at: str
    updated_at: str


# ── BUG 1: Missing input validation on discount calculation ──
def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculate discounted price.

    BUG: No validation on discount_percent — can be negative or > 100,
    leading to incorrect prices.
    """
    return price * (1 - discount_percent / 100)


# ── BUG 2: Integer overflow risk in inventory calculation ─────
def calculate_total_value(products: list[dict]) -> float:
    """Calculate total inventory value.

    BUG: No protection against very large numbers that could cause
    floating point issues.
    """
    total = 0
    for p in products:
        total += p["price"] * p["quantity"]
    return total


# ── BUG 3: Missing error handling in search ───────────────────
def search_products(query: str, products: dict) -> list[dict]:
    """Search products by name.

    BUG: Case-sensitive search and no handling of special characters.
    """
    results = []
    for pid, product in products.items():
        if query in product["name"]:  # BUG: case-sensitive
            results.append(product)
    return results


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "product_count": len(products_db),
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.post("/products", response_model=ProductResponse)
async def create_product(product: ProductCreate):
    """Create a new product."""
    global _next_id
    start = time.time()

    try:
        product_id = str(_next_id)
        _next_id += 1
        now = datetime.utcnow().isoformat()

        record = {
            "id": product_id,
            "name": product.name,
            "price": product.price,
            "quantity": product.quantity,
            "category": product.category,
            "description": product.description,
            "created_at": now,
            "updated_at": now,
        }
        products_db[product_id] = record

        REQUEST_COUNT.labels("POST", "/products", "201").inc()
        return ProductResponse(**record)

    except Exception as e:
        ERROR_COUNT.labels("POST", "/products", type(e).__name__).inc()
        raise
    finally:
        REQUEST_LATENCY.labels("POST", "/products").observe(time.time() - start)


@app.get("/products", response_model=list[ProductResponse])
async def list_products(
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
):
    """List all products with optional filters."""
    start = time.time()

    try:
        results = list(products_db.values())

        if category:
            results = [p for p in results if p["category"] == category]

        # BUG 4: min_price filter uses > instead of >=
        if min_price is not None:
            results = [p for p in results if p["price"] > min_price]

        if max_price is not None:
            results = [p for p in results if p["price"] <= max_price]

        REQUEST_COUNT.labels("GET", "/products", "200").inc()
        return [ProductResponse(**p) for p in results]

    except Exception as e:
        ERROR_COUNT.labels("GET", "/products", type(e).__name__).inc()
        raise
    finally:
        REQUEST_LATENCY.labels("GET", "/products").observe(time.time() - start)


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    """Get a specific product by ID."""
    start = time.time()

    try:
        if product_id not in products_db:
            REQUEST_COUNT.labels("GET", "/products/{id}", "404").inc()
            raise HTTPException(status_code=404, detail="Product not found")

        REQUEST_COUNT.labels("GET", "/products/{id}", "200").inc()
        return ProductResponse(**products_db[product_id])

    except HTTPException:
        raise
    except Exception as e:
        ERROR_COUNT.labels("GET", "/products/{id}", type(e).__name__).inc()
        raise
    finally:
        REQUEST_LATENCY.labels("GET", "/products/{id}").observe(time.time() - start)


@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, update: ProductUpdate):
    """Update a product."""
    start = time.time()

    try:
        if product_id not in products_db:
            REQUEST_COUNT.labels("PUT", "/products/{id}", "404").inc()
            raise HTTPException(status_code=404, detail="Product not found")

        product = products_db[product_id]

        # BUG 5: No validation on price update (allows negative)
        if update.name is not None:
            product["name"] = update.name
        if update.price is not None:
            product["price"] = update.price  # BUG: no validation
        if update.quantity is not None:
            product["quantity"] = update.quantity
        if update.category is not None:
            product["category"] = update.category
        if update.description is not None:
            product["description"] = update.description

        product["updated_at"] = datetime.utcnow().isoformat()

        REQUEST_COUNT.labels("PUT", "/products/{id}", "200").inc()
        return ProductResponse(**product)

    except HTTPException:
        raise
    except Exception as e:
        ERROR_COUNT.labels("PUT", "/products/{id}", type(e).__name__).inc()
        raise
    finally:
        REQUEST_LATENCY.labels("PUT", "/products/{id}").observe(time.time() - start)


@app.delete("/products/{product_id}")
async def delete_product(product_id: str):
    """Delete a product."""
    start = time.time()

    try:
        if product_id not in products_db:
            REQUEST_COUNT.labels("DELETE", "/products/{id}", "404").inc()
            raise HTTPException(status_code=404, detail="Product not found")

        del products_db[product_id]

        REQUEST_COUNT.labels("DELETE", "/products/{id}", "200").inc()
        return {"message": "Product deleted", "id": product_id}

    except HTTPException:
        raise
    except Exception as e:
        ERROR_COUNT.labels("DELETE", "/products/{id}", type(e).__name__).inc()
        raise
    finally:
        REQUEST_LATENCY.labels("DELETE", "/products/{id}").observe(time.time() - start)


@app.get("/products/search/{query}")
async def search(query: str):
    """Search products by name."""
    results = search_products(query, products_db)
    return {"query": query, "count": len(results), "results": results}


@app.post("/products/{product_id}/discount")
async def apply_discount(product_id: str, discount_percent: float):
    """Apply a discount to a product."""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")

    product = products_db[product_id]
    original_price = product["price"]
    new_price = calculate_discount(original_price, discount_percent)
    product["price"] = new_price
    product["updated_at"] = datetime.utcnow().isoformat()

    return {
        "product_id": product_id,
        "original_price": original_price,
        "discount_percent": discount_percent,
        "new_price": new_price,
    }


@app.get("/inventory/value")
async def get_inventory_value():
    """Calculate total inventory value."""
    total = calculate_total_value(list(products_db.values()))
    return {"total_value": total, "product_count": len(products_db)}
