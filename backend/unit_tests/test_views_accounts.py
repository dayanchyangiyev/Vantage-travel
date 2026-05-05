"""
test_views_accounts.py — Unit tests for accounts app API endpoints.

Endpoints covered:
  POST /api/accounts/register/  → create a new user
  GET  /api/accounts/profile/   → get logged-in user's profile (requires auth)
  POST /api/accounts/token/     → obtain JWT access + refresh tokens
"""

import pytest
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestRegisterView:
    def test_successful_registration_returns_201(self, api_client):
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepass123",
        }
        response = api_client.post("/api/accounts/register/", data=payload, format="json")
        assert response.status_code == 201
        assert User.objects.filter(username="newuser").exists()

    def test_duplicate_username_returns_400(self, api_client):
        User.objects.create_user(username="duplicate", password="pass")
        payload = {
            "username": "duplicate",
            "email": "other@example.com",
            "password": "anotherpass",
        }
        response = api_client.post("/api/accounts/register/", data=payload, format="json")
        assert response.status_code == 400
        assert "username" in response.data

    def test_missing_username_returns_400(self, api_client):
        payload = {"email": "test@example.com", "password": "pass"}
        response = api_client.post("/api/accounts/register/", data=payload, format="json")
        assert response.status_code == 400

    def test_missing_password_returns_400(self, api_client):
        payload = {"username": "nopass", "email": "test@example.com"}
        response = api_client.post("/api/accounts/register/", data=payload, format="json")
        assert response.status_code == 400

    def test_password_is_not_returned_in_response(self, api_client):
        """The password field is write_only — it must never appear in the response."""
        payload = {
            "username": "checkpass",
            "email": "checkpass@example.com",
            "password": "mysecretpassword",
        }
        response = api_client.post("/api/accounts/register/", data=payload, format="json")
        assert "password" not in response.data


@pytest.mark.django_db
class TestProfileView:
    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/accounts/profile/")
        assert response.status_code == 401

    def test_authenticated_returns_user_data(self, auth_client, test_user):
        response = auth_client.get("/api/accounts/profile/")
        assert response.status_code == 200
        assert response.data["username"] == "traveler"

    def test_response_contains_expected_fields(self, auth_client):
        response = auth_client.get("/api/accounts/profile/")
        assert "id" in response.data
        assert "username" in response.data
        assert "email" in response.data


@pytest.mark.django_db
class TestTokenView:
    def test_valid_credentials_return_tokens(self, api_client, test_user, db):
        payload = {"username": "traveler", "password": "securepass123"}
        response = api_client.post("/api/accounts/login/", data=payload, format="json")
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data

    def test_invalid_credentials_return_401(self, api_client):
        payload = {"username": "traveler", "password": "wrongpassword"}
        response = api_client.post("/api/accounts/login/", data=payload, format="json")
        assert response.status_code == 401

    def test_nonexistent_user_returns_401(self, api_client):
        payload = {"username": "ghost", "password": "anything"}
        response = api_client.post("/api/accounts/login/", data=payload, format="json")
        assert response.status_code == 401
