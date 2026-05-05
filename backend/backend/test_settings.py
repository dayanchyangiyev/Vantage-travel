"""
test_settings.py — Django settings overrides for the unit test suite.

This file extends the main settings but replaces secret/API credentials
with safe test-only values. No real keys are needed to run tests because
all external API calls are mocked.

Loaded via DJANGO_SETTINGS_MODULE=backend.test_settings in pytest.ini.
"""

from .settings import *  # noqa: F401, F403 — import everything from main settings

# Use a fixed test secret key — never use this in production!
SECRET_KEY = "django-insecure-test-key-only-for-unit-tests-do-not-use"

# Override JWT signing key to match
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY  # noqa: F405

# Use a fast in-memory SQLite database for tests (isolated from dev DB)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable password hashers to make test user creation much faster
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Silence logging during tests
LOGGING = {}

# Stub API credentials — values don't matter since HTTP is mocked
SERPAPI_API_KEY = "test-serpapi-key"
SERPAPI_BASE_URL = "https://serpapi.com/search.json"
GOOGLE_PLACES_API_KEY = "test-places-key"
GOOGLE_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GEONAMES_USERNAME = "test-geonames-user"
GOOGLE_MAPS_API_KEY = "test-maps-key"
