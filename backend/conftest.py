"""
conftest.py — Root-level conftest for the backend/ directory.

This file is discovered by pytest BEFORE any test file conftest is loaded.
Its only job is to ensure Django settings are configured so that imports
in unit_tests/backend/conftest.py (and all test files) can safely use
Django models, serializers, etc.

The DJANGO_SETTINGS_MODULE env var is also set in pytest.ini but this
provides a reliable fallback.
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()
