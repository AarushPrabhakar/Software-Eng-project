import os

# JWT-shaped dummy keys so the Supabase client can be constructed without a real project.
_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiJ9.c2lnbmF0dXJl"
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_ANON_KEY", _JWT)
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", _JWT)
os.environ.setdefault("HANDOVER_CODE_SECRET", "test-secret")

import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

from app import ratelimit
from app.dependencies import get_current_user
from app.main import app
from tests.fake_supabase import FakeSupabase

PATCH_TARGETS = [
    "app.database", "app.dependencies", "app.services", "app.visibility",
    "app.routers.reports", "app.routers.claims", "app.routers.notifications",
    "app.routers.flags", "app.routers.admin", "app.routers.auth",
]

USERS = {
    "u-finder": "Finder",
    "u-owner": "Owner",
    "u-other": "Other",
    "u-admin": "Admin",
}


@pytest.fixture()
def db(monkeypatch):
    import importlib

    fake = FakeSupabase()
    for uid, name in USERS.items():
        fake.add_user(uid, name, role="admin" if uid == "u-admin" else "student")
    for mod in PATCH_TARGETS:
        monkeypatch.setattr(importlib.import_module(mod), "supabase_admin", fake, raising=False)
    ratelimit.reset()
    return fake


@pytest.fixture()
def api(db):
    """Returns call(user_id, method, path, **kw). Authentication is faked via a header."""
    async def fake_user(x_test_user: str = None):  # noqa
        raise AssertionError("replaced below")

    from fastapi import Header

    async def current(x_test_user: str = Header(default=None)):
        if not x_test_user:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="no user")
        return SimpleNamespace(id=x_test_user, email=f"{x_test_user}@thapar.edu")

    app.dependency_overrides[get_current_user] = current
    client = TestClient(app)

    def call(user, method, path, **kw):
        headers = {"X-Test-User": user} if user else {}
        return client.request(method, path, headers=headers, **kw)

    yield call
    app.dependency_overrides.clear()
