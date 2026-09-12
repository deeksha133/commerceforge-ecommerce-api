import os
import secrets

os.environ["DATABASE_URL"] = "sqlite:///./test_commerceforge.db"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app, seed_database
from app.models import User
from app.security import hash_password


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(engine)


def register(client, email="student@example.com"):
    response = client.post("/api/auth/register", json={"name": "Student User", "email": email, "password": "StrongPass123!"})
    assert response.status_code == 201
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_health_and_landing(fresh_database):
    client = fresh_database
    landing = client.get("/")
    assert landing.status_code == 200
    assert 'href="/store"' in landing.text
    storefront = client.get("/store")
    assert storefront.status_code == 200
    assert 'id="productGrid"' in storefront.text
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "CommerceForge Developer Console" in docs.text
    assert 'url: "/openapi.json"' in docs.text
    assert client.get("/static/store.js").status_code == 200
    assert client.get("/static/store.css").status_code == 200
    assert client.get("/static/store-extras.css").status_code == 200
    assert client.get("/static/docs.css").status_code == 200
    assert client.get("/static/docs-fixes.css").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/static/reference.css").status_code == 200
    assert "System status" in client.get("/status").text
    assert client.get("/health").json()["status"] == "healthy"
    browser_health = client.get("/health", headers={"Accept": "text/html"}, follow_redirects=False)
    assert browser_health.status_code == 303
    assert browser_health.headers["location"] == "/status"


def test_registration_login_and_profile(fresh_database):
    client = fresh_database
    token = register(client)
    profile = client.get("/api/auth/me", headers=auth(token))
    assert profile.status_code == 200
    assert profile.json()["role"] == "user"
    login = client.post("/api/auth/login", json={"email": "student@example.com", "password": "StrongPass123!"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert client.post("/api/auth/register", json={"name": "Duplicate", "email": "student@example.com", "password": "StrongPass123!"}).status_code == 409


def test_catalog_search_and_filters(fresh_database):
    client = fresh_database
    products = client.get("/api/products").json()
    assert len(products) == 13
    assert len(client.get("/api/categories").json()) == 5
    assert len(client.get("/api/products", params={"search": "keyboard"}).json()) == 1
    assert all(item["stock"] > 0 for item in client.get("/api/products", params={"in_stock": True}).json())
    assert client.get("/api/products/9999").status_code == 404
    seed_database()
    assert len(client.get("/api/products").json()) == 13


def test_admin_permissions_and_product_creation(fresh_database):
    client = fresh_database
    user_token = register(client)
    denied = client.post("/api/categories", json={"name": "Books"}, headers=auth(user_token))
    assert denied.status_code == 403
    admin_password = secrets.token_urlsafe(20)
    with SessionLocal() as db:
        db.add(User(name="Test Administrator", email="test.admin@example.com", password_hash=hash_password(admin_password), role="admin"))
        db.commit()
    admin_login = client.post("/api/auth/login", json={"email": "test.admin@example.com", "password": admin_password})
    admin_token = admin_login.json()["access_token"]
    category = client.post("/api/categories", json={"name": "Books"}, headers=auth(admin_token))
    assert category.status_code == 201
    product = client.post("/api/products", json={"name": "Clean Code Handbook", "description": "A practical guide to maintainable software engineering.", "price": 29.99, "stock": 12, "category_id": category.json()["id"]}, headers=auth(admin_token))
    assert product.status_code == 201
    assert product.json()["category"]["slug"] == "books"


def test_cart_checkout_coupon_inventory_and_history(fresh_database):
    client = fresh_database
    token = register(client)
    headers = auth(token)
    product = client.get("/api/products").json()[0]
    added = client.post("/api/cart/items", json={"product_id": product["id"], "quantity": 2}, headers=headers)
    assert added.status_code == 201
    subtotal = round(product["price"] * 2, 2)
    assert added.json()["total"] == subtotal
    order = client.post("/api/orders/checkout", json={"shipping_address": "221 Market Street, Bengaluru", "coupon_code": "WELCOME10"}, headers=headers)
    assert order.status_code == 201
    assert order.json()["total"] == round(subtotal * .9, 2)
    assert client.get("/api/cart", headers=headers).json()["items"] == []
    assert len(client.get("/api/orders", headers=headers).json()) == 1


def test_reviews_and_validation(fresh_database):
    client = fresh_database
    token = register(client)
    headers = auth(token)
    product_id = client.get("/api/products").json()[0]["id"]
    review = client.post(f"/api/products/{product_id}/reviews", json={"rating": 5, "comment": "Excellent quality"}, headers=headers)
    assert review.status_code == 201
    assert client.post(f"/api/products/{product_id}/reviews", json={"rating": 5, "comment": "Again"}, headers=headers).status_code == 409
    assert client.post(f"/api/products/{product_id}/reviews", json={"rating": 8, "comment": "Invalid"}, headers=headers).status_code == 422
